from PyQt5.QtCore import Qt, QItemSelectionModel, QEvent, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem


class RunListWidget(QListWidget):
    selection_changed = pyqtSignal(object, object)

    def __init__(self, run_uuid, parent=None):
        super().__init__(parent)

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
        select_indexes = selected.indexes()
        selected_item = None
        if len(select_indexes) > 0:
            selected_index = select_indexes[0]
            selected_item = self.item(selected_index.row())
        deselect_indexes = deselected.indexes()
        deselected_item = None
        if len(deselect_indexes) > 0:
            deselected_index = deselect_indexes[0]
            deselected_item = self.item(deselected_index.row())
        self.selection_changed.emit(selected_item, deselected_item)
        super().selectionChanged(selected, deselected)
