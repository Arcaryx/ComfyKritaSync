import os

from krita import Krita  # type: ignore

def docker_document(source_docker, require_active_window=False):
    windows = Krita.instance().windows()
    selected_window = None
    for window in windows:
        if require_active_window and Krita.instance().activeWindow() != window:
            continue
        dockers = window.dockers()
        if source_docker in dockers:
            selected_window = window
            break
    if selected_window is None or selected_window.activeView() is None or selected_window.activeView().document() is None:
        return None, None
    document = selected_window.activeView().document()
    document_uuid = document.rootNode().uniqueId().toString()[1:-1]
    return document, document_uuid


def get_document_name(document):
    document_name = document.fileName()
    if (document_name is None) or (document_name == ""):
        return document.name()
    else:
        return os.path.basename(document.fileName())


