from PyQt6.QtCore import Qt, QItemSelectionModel, QEvent, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem


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
        if self.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows:
            return QItemSelectionModel.SelectionFlag.Rows
        elif self.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectColumns:
            return QItemSelectionModel.SelectionFlag.Columns
        else:
            return QItemSelectionModel.SelectionFlag.NoUpdate

    def selectionCommand(self, index, event, q_event=None, *args, **kwargs):
        key_modifiers = Qt.KeyboardModifier.NoModifier
        if event:
            if event.type() in [
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseMove,
                QEvent.Type.KeyPress,
                QEvent.Type.KeyRelease,
            ]:
                key_modifiers = event.modifiers()
            else:
                key_modifiers = QGuiApplication.keyboardModifiers()

        if self.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection:
            if event and event.type() == QEvent.Type.MouseButtonRelease:
                return QItemSelectionModel.SelectionFlag.NoUpdate
            elif (
                event
                and event.type() == QEvent.Type.KeyPress
                and self.selectionModel().isSelected(index)
                and (key_modifiers & Qt.KeyboardModifier.ControlModifier)
                and event.key() == Qt.Key.Key_Space
            ):
                return QItemSelectionModel.SelectionFlag.Deselect | self.selection_behavior_flags()
            return (
                QItemSelectionModel.SelectionFlag.Clear
                | QItemSelectionModel.SelectionFlag.Toggle
                | self.selection_behavior_flags()
            )

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
