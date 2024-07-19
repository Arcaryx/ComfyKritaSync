from krita import Krita, DockWidget, DockWidgetFactory, DockWidgetFactoryBase  # type: ignore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *


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


Krita.instance().addDockWidgetFactory(
    DockWidgetFactory("comfyKritaSyncDocker", DockWidgetFactoryBase.DockRight, ComfyKritaSyncDocker)
)
