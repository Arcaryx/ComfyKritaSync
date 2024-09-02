from PyQt5.QtCore import Qt, QItemSelectionModel, QEvent
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QListWidget, QAbstractItemView

from krita_sync.util import docker_document


class RunListWidget(QListWidget):
    def __init__(self, docker, frame, run_uuid, parent=None):
        super().__init__(parent)

        self.docker = docker
        self.frame = frame
        self.run_uuid = run_uuid
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def discard_image(self, item):
        selected_item_index = self.indexFromItem(item)
        if selected_item_index.isValid():
            self.takeItem(selected_item_index.row())

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
            elif event and event.type() == QEvent.KeyPress and self.selectionModel().isSelected(index) and (key_modifiers & Qt.ControlModifier) and event.key() == Qt.Key_Space:
                return QItemSelectionModel.Deselect | self.selection_behavior_flags()
            return QItemSelectionModel.Clear | QItemSelectionModel.Toggle | self.selection_behavior_flags()

        return super().selectionCommand(index, event)

    def selectionChanged(self, selected, deselected):
        document, document_id = docker_document(self.docker)

        deselected_indexes = deselected.indexes()
        if len(deselected_indexes) > 0:
            deselected_index = deselected_indexes[0]
            deselected_item = self.item(deselected_index.row())
            self.frame.remove_item_preview(deselected_item)

        select_indexes = selected.indexes()
        if len(select_indexes) > 0:
            selected_index = select_indexes[0]
            selected_item = self.item(selected_index.row())

            self.frame.show_item_preview(selected_item)

            if self.frame.selected_item is not None and self != self.frame.selected_item.listWidget():
                # TODO: See if we can just get the selection model from the list widget and set that to have no selection instead
                self.frame.selected_item.listWidget().setCurrentItem(None)
            self.frame.selected_item = selected_item
            self.frame.selected_item_uuid[document_id] = selected_item.data(Qt.ItemDataRole.UserRole)["image_uuid"]
        else:
            self.frame.selected_item = None
            self.frame.selected_item_uuid.pop(document_id)

        super().selectionChanged(selected, deselected)
