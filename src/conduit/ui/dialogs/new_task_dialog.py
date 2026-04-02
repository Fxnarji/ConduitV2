import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QDialogButtonBox, QRadioButton, QButtonGroup, QGroupBox,
)


class NewTaskDialog(QDialog):
    """Asks for a task name and lets the user pick a single template file to copy in."""

    def __init__(self, preset_name: str, templates_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Task")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Task name:"))
        self._name_edit = QLineEdit(preset_name)
        self._name_edit.selectAll()
        layout.addWidget(self._name_edit)

        # Single-selection template list
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._radio_map: dict[QRadioButton, Path] = {}

        templates = sorted(templates_dir.iterdir()) if templates_dir.is_dir() else []
        templates = [t for t in templates if t.is_file()]

        if templates:
            group = QGroupBox("Add template file:")
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(4)

            none_rb = QRadioButton("None")
            none_rb.setChecked(True)
            self._btn_group.addButton(none_rb)
            group_layout.addWidget(none_rb)

            for tmpl in templates:
                rb = QRadioButton(tmpl.name)
                self._btn_group.addButton(rb)
                self._radio_map[rb] = tmpl
                group_layout.addWidget(rb)

            layout.addWidget(group)

        self._info = QLabel("")
        self._info.setStyleSheet("color: #f88;")
        layout.addWidget(self._info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            self._info.setText("Task name is required.")
            return
        self.accept()

    @property
    def task_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def selected_template(self) -> Path | None:
        checked = self._btn_group.checkedButton()
        return self._radio_map.get(checked)  # type: ignore

    def copy_template_to(self, dest: Path) -> Path | None:
        """Copy the selected template into dest. Returns the destination path, or None."""
        tmpl = self.selected_template
        if tmpl is None:
            return None
        dest_file = dest / tmpl.name
        shutil.copy2(tmpl, dest_file)
        return dest_file
