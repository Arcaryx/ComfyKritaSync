from krita import Krita, Extension  # type: ignore


class TestExtension(Extension):

    def __init__(self, parent):
        # This is initialising the parent, always important when subclassing.
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        pass


# And add the extension to Krita's list of extensions:
Krita.instance().addExtension(TestExtension(Krita.instance()))
