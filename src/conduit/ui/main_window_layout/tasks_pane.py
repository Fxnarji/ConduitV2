from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt

from conduit.model.nodes import TaskNode


class TaskPane:
    def __init__(self) -> None:
        self.group_box = QGroupBox("Tasks")
        layout = QVBoxLayout(self.group_box)
        layout.setContentsMargins(4, 16, 4, 4)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def widget(self) -> QGroupBox:
        return self.group_box

    def get_selected_task(self) -> TaskNode | None:
        items = self.list_widget.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole)  # type: ignore

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def populate(self, tasks: list[TaskNode]) -> None:
        self.list_widget.clear()
        for task in tasks:
            item = QListWidgetItem(task.name)
            item.setData(Qt.UserRole, task)  # type: ignore
            self.list_widget.addItem(item)

    def clear(self) -> None:
        self.list_widget.clear()

    def append_task(self, task: TaskNode) -> None:
        item = QListWidgetItem(task.name)
        item.setData(Qt.UserRole, task)  # type: ignore
        self.list_widget.addItem(item)
        self.list_widget.setCurrentItem(item)
