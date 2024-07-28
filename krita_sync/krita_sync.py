import uuid

from krita import Krita, Extension, DockWidget, DockWidgetFactory, DockWidgetFactoryBase  # type: ignore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from krita_sync.client_krita import KritaClient


class ComfyKritaSyncExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        # Init

    def setup(self):
        client = KritaClient.instance()
        client.run(client.connect())

    def shutdown(self):
        KritaClient.instance().loop.stop()
        KritaClient.instance().loop.close()
        # Shutdown
        pass

    def createActions(self, window):
        # Actions
        pass


class ComfyKritaSyncDocker(DockWidget):

    def __init__(self):
        super().__init__()
        self.uuid = uuid.uuid4().hex
        self.setWindowTitle("ComfyUI-Krita Sync")
        main_widget = QWidget(self)
        self.setWidget(main_widget)

        self.text = QLabel("Status: Disconnected")
        self.button_connect = QPushButton("Connect", main_widget)

        main_widget.setLayout(QVBoxLayout())
        main_widget.layout().addWidget(self.text)
        main_widget.layout().addWidget(self.button_connect)

        self.button_connect.clicked.connect(self.toggle_connection)

        client = KritaClient.instance()
        client.websocket_updated.connect(self.websocket_updated)
        self.websocket_updated(client.is_connected())

    def canvasChanged(self, canvas):
        pass

    @pyqtSlot()
    def toggle_connection(self):
        client = KritaClient.instance()
        is_connected = client.is_connected()
        if is_connected:
            client.run(client.disconnect())
        else:
            # FIXME: This needs to only be allowed to run once at a time before getting an actual failure back, etc;
            client.run(client.connect())

    def websocket_updated(self, is_connected):
        if is_connected:
            self.text.setText("Status: Connected")
            self.button_connect.setText("Disconnect")
        else:
            self.text.setText("Status: Disconnected")
            self.button_connect.setText("Connect")


Krita.instance().addExtension(ComfyKritaSyncExtension(Krita.instance()))
Krita.instance().addDockWidgetFactory(
    DockWidgetFactory("comfyKritaSync", DockWidgetFactoryBase.DockRight, ComfyKritaSyncDocker)
)
