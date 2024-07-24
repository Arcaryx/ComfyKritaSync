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
        # Startup

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
        self.setWindowTitle("ComfyUI-Krita Sync")
        main_widget = QWidget(self)
        self.setWidget(main_widget)

        self.text = QLabel("Status: Disconnected")
        self.button_connect = QPushButton("Connect", main_widget)

        main_widget.setLayout(QVBoxLayout())
        main_widget.layout().addWidget(self.text)
        main_widget.layout().addWidget(self.button_connect)

        self.button_connect.clicked.connect(self.comfy_connect)

    def canvasChanged(self, canvas):
        pass

    @pyqtSlot()
    def comfy_connect(self):
        self.text.setText("Status: Connected")
        self.button_connect.setEnabled(False)


Krita.instance().addExtension(ComfyKritaSyncExtension(Krita.instance()))
Krita.instance().addDockWidgetFactory(
    DockWidgetFactory("comfyKritaSync", DockWidgetFactoryBase.DockRight, ComfyKritaSyncDocker)
)
