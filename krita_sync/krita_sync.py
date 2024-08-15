import uuid
from typing import cast

from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QGuiApplication
from krita import Krita, Extension, DockWidget, DockWidgetFactory, DockWidgetFactoryBase  # type: ignore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QSize, pyqtSlot, QItemSelectionModel, QEvent

from krita_sync.cks_common.CksBinaryMessage import SendImageKritaJsonPayload
from krita_sync.client_krita import KritaClient, ConnectionState, _get_document_name


def _docker_document(docker):
    windows = Krita.instance().windows()
    for window in windows:
        dockers = window.dockers()
        if docker in dockers:
            break
    if window.activeView() is None or window.activeView().document() is None:
        return None, None
    document = window.activeView().document()
    document_uuid = document.rootNode().uniqueId().toString()[1:-1]
    return document, document_uuid

class MyListWidget(QListWidget):
    def __init__(self, *args, **kwargs):
        super(MyListWidget, self).__init__(*args, **kwargs)

    def selection_behavior_flags(self):
        if self.selectionBehavior == QAbstractItemView.SelectionBehavior.SelectRows:
            return QItemSelectionModel.Rows
        elif self.selectionBehavior == QAbstractItemView.SelectionBehavior.SelectColumns:
            return QItemSelectionModel.Columns
        else:
            return QItemSelectionModel.NoUpdate

    def selectionCommand(self, index, event, q_event=None, *args, **kwargs):
        key_modifiers = Qt.NoModifier
        if event:
            if event.type() in [QEvent.MouseButtonDblClick, QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseMove, QEvent.KeyPress, QEvent.KeyRelease]:
                key_modifiers = event.modifiers()
            else:
                key_modifiers = QGuiApplication.keyboardModifiers()

        if self.selectionMode() == QAbstractItemView.SingleSelection:
            if event and event.type() == QEvent.MouseButtonRelease:
                return QItemSelectionModel.NoUpdate
            if (key_modifiers & Qt.ControlModifier) and self.selectionModel().isSelected(index) and event.type() != QEvent.MouseMove:
                return QItemSelectionModel.Deselect | self.selection_behavior_flags()
            else:
                return QItemSelectionModel.ClearAndSelect | self.selection_behavior_flags()

        return super(MyListWidget, self).selectionCommand(index, event)

class ComfyKritaSyncExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        # Init

    def setup(self):
        client = KritaClient.instance()
        client.connection_coroutine = client.run(client.connect("http://127.0.0.1:8188"))

    def shutdown(self):
        KritaClient.instance().loop.stop()
        KritaClient.instance().loop.close()
        # Shutdown
        pass

    def createActions(self, window):
        # Actions
        pass


class GenHistoryWidget(QFrame):
    def __init__(self, parent, docker):
        super().__init__(parent)
        self.list_widgets = {}
        self.thumb_size = 150
        self.uuid = str(uuid.uuid4())
        self.docker = docker
        self.selected_item = None
        self.last_clicked_item = None

        self.preview_image_layer_name = "[PREVIEW]"

        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        client = KritaClient.instance()
        client.image_added.connect(self.image_added_handler)
        client.document_changed.connect(self.document_changed_handler)

    def add_run(self, run_uuid, images_metadata):
        if run_uuid not in self.list_widgets:
            list_widget = MyListWidget()
            list_widget.setMinimumHeight(self.thumb_size + 2)
            list_widget.setResizeMode(QListView.ResizeMode.Adjust)
            list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            list_widget.setFlow(QListView.Flow.LeftToRight)
            list_widget.setViewMode(QListWidget.ViewMode.IconMode)
            list_widget.setIconSize(QSize(self.thumb_size, self.thumb_size))
            list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
            list_widget.setFrameStyle(QListWidget.NoFrame)
            list_widget.setDragEnabled(False)
            list_widget.itemClicked.connect(self.item_clicked_handler)
            list_widget.itemActivated.connect(self.item_activated_handler)
            list_widget.currentItemChanged.connect(self.current_item_changed_handler)

            list_widget.setStyleSheet("QListWidget { border: 2px solid #475c7d; }")

            self.layout().insertWidget(0, list_widget)
            self.list_widgets[run_uuid] = list_widget

        for image_metadata in images_metadata:
            image = KritaClient.instance().image_map[image_metadata["image_uuid"]]
            scaled_image = image.scaled(self.thumb_size, self.thumb_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            thumb_pixmap = QPixmap(self.thumb_size, self.thumb_size)
            thumb_pixmap.fill(QColor(0, 0, 0, 0))

            painter = QPainter(thumb_pixmap)
            painter.setBackgroundMode(Qt.TransparentMode)

            x = (thumb_pixmap.width() - scaled_image.width()) // 2
            y = (thumb_pixmap.height() - scaled_image.height()) // 2
            painter.drawImage(x, y, scaled_image)
            painter.end()

            item = QListWidgetItem(QIcon(thumb_pixmap), None)
            item.setData(Qt.ItemDataRole.UserRole, image_metadata["image_uuid"])
            item.setData(Qt.ItemDataRole.UserRole+1, image_metadata["krita_layer"])
            item.setData(Qt.ItemDataRole.ToolTipRole, f"Target Layer: {image_metadata['krita_layer']}\nClick to toggle preview, double-click to apply.")
            self.list_widgets[run_uuid].addItem(item)

        QApplication.processEvents()  # TODO: Is there a lighter weight solution for updating the viewport of a list?
        self.adjust_list_widget_height(self.list_widgets[run_uuid])

    def image_added_handler(self, document_uuid, run_uuid, images_metadata):
        document, document_id = _docker_document(self.docker)
        if document is None:
            return

        if document_id == document_uuid:
            self.add_run(run_uuid, images_metadata)

    def document_changed_handler(self):
        document, document_id = _docker_document(self.docker)
        if document is None:
            return

        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.list_widgets.clear()

        client = KritaClient.instance()
        if document_id in client.run_map:
            image_runs = client.run_map[document_id]
            for key, value in image_runs.items():
                self.add_run(key, value)

    def item_clicked_handler(self, item: QListWidgetItem):
        document, document_id = _docker_document(self.docker)
        if document is None:
            return

        print("item_clicked_handler")

        # if self.last_clicked_item == item and item.isSelected():
        #     self.selected_item = None
        #     self.last_clicked_item = None
        #     item.listWidget().setCurrentItem(None)
        # else:
        #     self.last_clicked_item = item

    def item_activated_handler(self, item: QListWidgetItem):
        document, document_id = _docker_document(self.docker)
        if document is None:
            return

        image_uuid = item.data(Qt.ItemDataRole.UserRole)
        layer_name = item.data(Qt.ItemDataRole.UserRole+1)
        client = KritaClient.instance()
        image = client.image_map[image_uuid]

        self.remove_item_preview()
        if document is not None and document.rootNode is not None:
            client.create(document, layer_name, image)

    def show_item_preview(self, item: QListWidgetItem):
        document, document_id = _docker_document(self.docker)
        if document is None:
            return

        image_uuid = item.data(Qt.ItemDataRole.UserRole)
        layer_name = item.data(Qt.ItemDataRole.UserRole+1)
        layer_name_parts = layer_name.split("/")
        if len(layer_name_parts) > 1:
            layer_name_parts[-1] = self.preview_image_layer_name
            layer_name = "/".join(layer_name_parts)
        else:
            layer_name = self.preview_image_layer_name
        client = KritaClient.instance()
        image = client.image_map[image_uuid]
        if document is not None and document.rootNode is not None:
            client.create(document, layer_name, image)

    def remove_item_preview(self):
        document, document_id = _docker_document(self.docker)
        preview_node = document.nodeByName(self.preview_image_layer_name)
        if preview_node is not None:
            preview_node.remove()

    def current_item_changed_handler(self, current: QListWidgetItem, previous: QListWidgetItem):
        print("current_item_changed_handler")
        # TODO: This needs to be here to prevent infinite recursion, but we also need it to not be here for deselection to work, problem for a future us :)
        if current is None:
            if self.selected_item is not None and self.selected_item.listWidget() == previous.listWidget():
                self.remove_item_preview()
            return

        old_selected_item = self.selected_item
        self.selected_item = current

        if old_selected_item is not None and current.listWidget() != old_selected_item.listWidget():
            old_selected_item.listWidget().setCurrentItem(None)

        self.remove_item_preview()
        self.show_item_preview(self.selected_item)

    def resizeEvent(self, event, **kwargs):
        super().resizeEvent(event, **kwargs)
        for list_widget in self.list_widgets.values():
            self.adjust_list_widget_height(list_widget)

    def adjust_list_widget_height(self, list_widget):
        width = list_widget.viewport().width()
        num_columns = (width - 1) // (self.thumb_size + 6)
        num_rows = (list_widget.count() + num_columns - 1) // num_columns
        list_widget.setFixedHeight(num_rows * (self.thumb_size + 5) + 4)


class ComfyKritaSyncDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.uuid = uuid.uuid4().hex
        self.setWindowTitle("ComfyUI-Krita Sync")

        # Main Widget
        main_widget = QWidget(self)
        main_widget.setLayout(QVBoxLayout())
        self.setWidget(main_widget)

        # Connection Widget
        connection_widget = QWidget(main_widget)
        main_widget.layout().addWidget(connection_widget)
        connection_widget.setLayout(QHBoxLayout())
        connection_widget.layout().setContentsMargins(11, 4, 11, 0)
        self.line_url = QLineEdit("http://127.0.0.1:8188")
        connection_widget.layout().addWidget(self.line_url)
        self.label_status = QLabel("D")  # D = Disconnected, R = Reconnecting, C = Connected
        connection_widget.layout().addWidget(self.label_status)
        self.button_connect = QPushButton("Connect")
        self.button_connect.clicked.connect(self.toggle_connection)
        connection_widget.layout().addWidget(self.button_connect)

        # Document Widget
        document_widget = QWidget(main_widget)
        main_widget.layout().addWidget(document_widget)
        document_widget.setLayout(QHBoxLayout())
        document_widget.layout().setContentsMargins(11, 0, 11, 0)
        self.label_document = QLabel("Current Document: -")
        document_widget.layout().addWidget(self.label_document)

        # History Widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        history_widget = GenHistoryWidget(main_widget, self)
        scroll_area.setWidget(history_widget)
        main_widget.layout().addWidget(scroll_area)

        # Websocket Setup
        client = KritaClient.instance()
        client.websocket_updated.connect(self.websocket_updated)
        self.websocket_updated(client.get_connection_state())

    def canvasChanged(self, canvas):
        if canvas is not None and canvas.view() is not None:
            document, document_uuid = _docker_document(self)
            if document is not None:
                document_uuid_short = document_uuid.split("-")[0]
                document_name = _get_document_name(document)
                self.label_document.setText(f"Current Document: {document_name} ({document_uuid_short})")
                KritaClient.instance().document_changed.emit()

    @pyqtSlot()
    def toggle_connection(self):
        client = KritaClient.instance()
        connection_state = client.get_connection_state()
        if connection_state == ConnectionState.Connected:
            client.run(client.disconnect())
        elif connection_state == ConnectionState.Disconnected:
            client.connection_coroutine = client.run(client.connect(self.line_url.text()))
        elif connection_state == ConnectionState.Connecting:
            client.kill_connection_coroutine()

    def websocket_updated(self, state):
        if state == ConnectionState.Disconnected:
            self.label_status.setText("D")
            self.line_url.setEnabled(True)
            self.button_connect.setText("Connect")
        elif state == ConnectionState.Connected:
            self.label_status.setText("C")
            self.line_url.setEnabled(False)
            self.button_connect.setText("Disconnect")
        elif state == ConnectionState.Connecting:
            self.label_status.setText("R")
            self.line_url.setEnabled(False)
            self.button_connect.setText("Cancel")


Krita.instance().addExtension(ComfyKritaSyncExtension(Krita.instance()))
Krita.instance().addDockWidgetFactory(
    DockWidgetFactory("comfyKritaSync", DockWidgetFactoryBase.DockRight, ComfyKritaSyncDocker)
)
