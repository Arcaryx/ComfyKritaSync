import uuid

from PyQt5.QtGui import QColor, QPixmap, QPainter, QIcon
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QSizePolicy, QListView, QListWidget, QListWidgetItem, QApplication
from PyQt5.QtCore import Qt, QSize

from krita_sync.client_krita import KritaClient
from krita_sync.ui.run_list import RunListWidget
from krita_sync.util import docker_document


class GenHistoryWidget(QFrame):
    def __init__(self, parent, docker):
        super().__init__(parent)
        self.list_widgets = {}
        self.thumb_size = 150
        self.uuid = str(uuid.uuid4())
        self.docker = docker
        self.history_selected_item = None
        # We're leaving this as a tiny memory leak, if it comes back to bite us than ¯\_(ツ)_/¯
        self.history_selected_item_uuid = {}

        self.preview_image_layer_name = "[PREVIEW]"

        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        client = KritaClient.instance()
        client.image_added.connect(self.image_added_handler)
        client.document_changed.connect(self.document_changed_handler)
        client.delete_selected_image.connect(self.discard_image)

    def add_run(self, document, document_id, run_uuid, images_metadata):
        if run_uuid not in self.list_widgets:
            list_widget = RunListWidget(run_uuid, parent=self)
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
            list_widget.itemActivated.connect(self.item_activated_handler)
            list_widget.selection_changed.connect(self.selection_changed_handler)

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
            item.setData(Qt.ItemDataRole.UserRole, image_metadata)
            item.setData(Qt.ItemDataRole.ToolTipRole, f"Target Layer: {image_metadata['krita_layer']}\nClick to toggle preview, double-click to apply.")
            self.list_widgets[run_uuid].addItem(item)

            if document_id in self.history_selected_item_uuid and self.history_selected_item_uuid[document_id] == image_metadata["image_uuid"]:
                layer_name = self.get_item_preview_layer_name(item)

                client = KritaClient.instance()
                client.remove(document, layer_name)

                item.setSelected(True)

        QApplication.processEvents()
        self.adjust_list_widget_height(self.list_widgets[run_uuid])

    def discard_image(self):
        document, document_id = docker_document(self.docker, True)
        if document is None:
            return

        client = KritaClient.instance()

        if document_id in self.history_selected_item_uuid:
            self.remove_item_preview(self.history_selected_item)

            image_uuid = self.history_selected_item_uuid[document_id]
            run_uuid = self.history_selected_item.data(Qt.ItemDataRole.UserRole)["run_uuid"]

            list_widget = self.list_widgets[run_uuid]
            list_widget.discard_image(self.history_selected_item)

            client.discard_image(document_id, run_uuid, image_uuid)

            self.adjust_list_widget_height(list_widget)

            if list_widget.count() == 0:
                self.list_widgets.pop(run_uuid)
                client.run_map[document_id].pop(run_uuid)
                list_widget.deleteLater()

    def image_added_handler(self, document_uuid, run_uuid, images_metadata):
        document, document_id = docker_document(self.docker)
        if document is None:
            return

        if document_id == document_uuid:
            self.add_run(document, document_id, run_uuid, images_metadata)

    def selection_changed_handler(self, selected_item: QListWidgetItem | None, deselected_item: QListWidgetItem | None):
        document, document_id = docker_document(self.docker)

        if deselected_item is not None:
            self.remove_item_preview(deselected_item)

        if selected_item is not None:
            self.show_item_preview(selected_item)

            if self.history_selected_item is not None and selected_item.listWidget() != self.history_selected_item.listWidget():
                # This exists so that when you click between two runs, clicking back fires selectionChanged again
                self.history_selected_item.listWidget().setCurrentItem(None)
            self.history_selected_item = selected_item
            self.history_selected_item_uuid[document_id] = selected_item.data(Qt.ItemDataRole.UserRole)["image_uuid"]

        else:
            self.history_selected_item = None
            self.history_selected_item_uuid.pop(document_id)

    def document_changed_handler(self, changed_document_uuid):
        document, document_id = docker_document(self.docker)
        if document is None or changed_document_uuid != document_id:
            return

        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.history_selected_item = None
        self.list_widgets.clear()

        client = KritaClient.instance()
        if document_id in client.run_map:
            image_runs = client.run_map[document_id]
            for key, value in image_runs.items():
                self.add_run(document, document_id, key, value)

    def item_activated_handler(self, item: QListWidgetItem):
        document, document_id = docker_document(self.docker)
        if document is None:
            return

        image_metadata = item.data(Qt.ItemDataRole.UserRole)
        image_uuid = image_metadata["image_uuid"]
        layer_name = image_metadata["krita_layer"]
        client = KritaClient.instance()
        image = client.image_map[image_uuid]

        self.remove_item_preview(item)
        if document is not None and document.rootNode is not None:
            client.create(document, layer_name, image)

    def get_item_preview_layer_name(self, item):
        image_metadata = item.data(Qt.ItemDataRole.UserRole)
        layer_name = image_metadata["krita_layer"]
        layer_name_parts = layer_name.split("/")
        if len(layer_name_parts) > 1:
            layer_name_parts[-1] = f"{self.preview_image_layer_name} {layer_name_parts[-1]}"
            layer_name = "/".join(layer_name_parts)
        else:
            layer_name = f"{self.preview_image_layer_name} {layer_name}"
        return layer_name

    def show_item_preview(self, item: QListWidgetItem):
        document, document_id = docker_document(self.docker)
        if document is None:
            return

        image_metadata = item.data(Qt.ItemDataRole.UserRole)
        image_uuid = image_metadata["image_uuid"]
        layer_name = self.get_item_preview_layer_name(item)

        client = KritaClient.instance()
        image = client.image_map[image_uuid]
        if document is not None and document.rootNode is not None:
            client.create(document, layer_name, image, preview=True)

    def remove_item_preview(self, item):
        document, document_id = docker_document(self.docker)
        if document is None:
            return

        layer_name = self.get_item_preview_layer_name(item)

        client = KritaClient.instance()
        client.remove(document, layer_name)

    def resizeEvent(self, event, **kwargs):
        super().resizeEvent(event, **kwargs)
        for list_widget in self.list_widgets.values():
            self.adjust_list_widget_height(list_widget)

    def adjust_list_widget_height(self, list_widget):
        width = list_widget.viewport().width()
        num_columns = (width - 1) // (self.thumb_size + 6)
        num_rows = (list_widget.count() + num_columns - 1) // num_columns
        list_widget.setFixedHeight(num_rows * (self.thumb_size + 5) + 4)
