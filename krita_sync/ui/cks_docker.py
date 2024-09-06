import uuid

from krita import DockWidget  # type: ignore
from PyQt5.QtCore import QSize, pyqtSlot
from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy, QScrollArea

from krita_sync.client_krita import ConnectionState, KritaClient
from krita_sync.ui.gen_history import GenHistoryWidget
from krita_sync.util import docker_document, get_document_name


class NoMinSizeQLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def minimumSizeHint(self):
        return QSize(0, 0)


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
        self.label_document_name = NoMinSizeQLabel("Current Document: -")
        self.label_document_name.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self.label_document_uuid = QLabel(" (-)")
        self.label_document_uuid.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        document_widget.layout().addWidget(self.label_document_name)
        document_widget.layout().addWidget(self.label_document_uuid)
        document_widget.layout().addStretch(1)

        self.button_clear_all = QPushButton("Clear All")
        self.button_clear_all.clicked.connect(self.clear_all)
        document_widget.layout().addWidget(self.button_clear_all)

        # History Widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.history_widget = GenHistoryWidget(main_widget, self)
        scroll_area.setWidget(self.history_widget)
        main_widget.layout().addWidget(scroll_area)

        # Websocket Setup
        client = KritaClient.instance()
        client.websocket_updated.connect(self.websocket_updated)
        self.websocket_updated(client.get_connection_state())

    def canvasChanged(self, canvas):
        if canvas is not None and canvas.view() is not None:
            document, document_uuid = docker_document(self)
            if document is not None:
                document_uuid_short = document_uuid.split("-")[0]
                document_name = get_document_name(document)
                self.label_document_name.setText(f"Current Document: {document_name}")
                self.label_document_uuid.setText(f"({document_uuid_short})")

                KritaClient.instance().document_changed.emit(document_uuid)

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

    @pyqtSlot()
    def clear_all(self):
        document, document_uuid = docker_document(self)
        client = KritaClient.instance()

        if document_uuid in self.history_widget.history_selected_item_uuid:
            self.history_widget.remove_item_preview(self.history_widget.history_selected_item)
            del self.history_widget.history_selected_item_uuid[document_uuid]
            self.history_widget.history_selected_item = None

        client.clear_history_for_document_id(document_uuid)
        self.history_widget.document_changed_handler(document_uuid)

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
