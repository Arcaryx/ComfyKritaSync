import uuid

from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from krita import Krita, Extension, DockWidget, DockWidgetFactory, DockWidgetFactoryBase  # type: ignore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from krita_sync.client_krita import KritaClient, ConnectionState, _get_document_name


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


class GenHistoryWidget(QListWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.thumb_size = 150

        self.setLayout(QHBoxLayout())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setResizeMode(QListView.Adjust)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFlow(QListView.LeftToRight)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(self.thumb_size, self.thumb_size))
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setFrameStyle(QListWidget.NoFrame)
        self.setDragEnabled(False)

        client = KritaClient.instance()
        client.image_added.connect(self.image_added_handler)
        client.document_changed.connect(self.document_changed_handler)
        self.itemDoubleClicked.connect(self.item_double_clicked_handler)

    def add_run(self, run_uuid, images):
        for image_uuid in images:
            image = KritaClient.instance().image_map[image_uuid]

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
            item.setData(Qt.ItemDataRole.UserRole, image_uuid)
            self.addItem(item)

    def document_changed_handler(self):
        self.clear()
        if (document := Krita.instance().activeDocument()) and document.rootNode() is None:
            return
        current_document_uuid = Krita.instance().activeDocument().rootNode().uniqueId().toString()[1:-1]
        client = KritaClient.instance()
        if current_document_uuid in client.run_map:
            image_runs = client.run_map[current_document_uuid]
            for key, value in image_runs.items():
                self.add_run(key, value)

    def image_added_handler(self, document_uuid, run_uuid, images):
        if (document := Krita.instance().activeDocument()) and document.rootNode() is not None and document.rootNode().uniqueId().toString()[1:-1] == document_uuid:
            self.add_run(run_uuid, images)

    def item_double_clicked_handler(self, item: QListWidgetItem):
        image_uuid = item.data(Qt.ItemDataRole.UserRole)
        client = KritaClient.instance()
        image = client.image_map[image_uuid]
        document = Krita.instance().activeDocument()
        if document is not None and document.rootNode is not None:
            client.create(document, image_uuid, image)


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
        history_widget = GenHistoryWidget(main_widget)
        main_widget.layout().addWidget(history_widget)

        # Websocket Setup
        client = KritaClient.instance()
        client.websocket_updated.connect(self.websocket_updated)
        self.websocket_updated(client.get_connection_state())

    def canvasChanged(self, canvas):
        if canvas is not None and canvas.view() is not None:
            if (document := Krita.instance().activeDocument()) and document in Krita.instance().documents() and document.activeNode() is not None:
                document_uuid = document.rootNode().uniqueId().toString()[1:-1]
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
