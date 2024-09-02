from krita import Krita, Extension, DockWidget, DockWidgetFactory, DockWidgetFactoryBase  # type: ignore

from krita_sync.client_krita import KritaClient
from krita_sync.ui.cks_docker import ComfyKritaSyncDocker


class ComfyKritaSyncExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        client = KritaClient.instance()
        client.connection_coroutine = client.run(client.connect("http://127.0.0.1:8188"))

    def shutdown(self):
        KritaClient.instance().loop.stop()
        KritaClient.instance().loop.close()

    def createActions(self, window):
        client = KritaClient.instance()
        action = window.createAction("deleteCKSImage", "Delete CKS Image")
        action.triggered.connect(client.delete_cks_image)

Krita.instance().addExtension(ComfyKritaSyncExtension(Krita.instance()))
Krita.instance().addDockWidgetFactory(
    DockWidgetFactory("comfyKritaSync", DockWidgetFactoryBase.DockRight, ComfyKritaSyncDocker)
)
