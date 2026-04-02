from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QListWidget, QPushButton, QFormLayout, QSpinBox, QCheckBox,
    QDialogButtonBox, QLabel, QFileDialog,
)
from PySide6.QtCore import Qt

from conduit.model.settings import ClientSettings


class SettingsDialog(QDialog):
    def __init__(self, settings: ClientSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(520, 380)
        self._settings = settings

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_projects_tab(), "Projects")
        tabs.addTab(self._build_git_tab(), "Git")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_projects_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Known Projects"))

        self._projects_list = QListWidget()
        self._projects_list.addItems(self._settings.known_projects)
        layout.addWidget(self._projects_list, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._add_project)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_project)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._open_selected)
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addWidget(open_btn)
        row.addStretch()
        layout.addLayout(row)

        return widget

    def _build_git_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(10)

        self._fetch_interval = QSpinBox()
        self._fetch_interval.setRange(1, 60)
        self._fetch_interval.setSuffix(" minutes")
        self._fetch_interval.setValue(self._settings.fetch_interval_minutes)

        self._auto_pull_check = QCheckBox(
            "Automatically pull after each background fetch"
        )
        self._auto_pull_check.setChecked(self._settings.auto_pull_after_fetch)

        self._pull_startup_check = QCheckBox(
            "Pull immediately when opening a project with a remote"
        )
        self._pull_startup_check.setChecked(self._settings.pull_on_startup)

        layout.addRow("Background fetch every:", self._fetch_interval)
        layout.addRow(self._auto_pull_check)
        layout.addRow(self._pull_startup_check)

        return widget

    def _add_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Conduit Project")
        if path:
            self._projects_list.addItem(path)

    def _remove_project(self) -> None:
        row = self._projects_list.currentRow()
        if row >= 0:
            self._projects_list.takeItem(row)

    def _open_selected(self) -> None:
        item = self._projects_list.currentItem()
        if item:
            from conduit.ui.main_window import MainWindow
            w = self.window()
            if isinstance(w, MainWindow):
                w._open_project_path(Path(item.text()))

    def _on_ok(self) -> None:
        self._settings.known_projects = [
            self._projects_list.item(i).text()
            for i in range(self._projects_list.count())
        ]
        self._settings.fetch_interval_minutes = self._fetch_interval.value()
        self._settings.auto_pull_after_fetch = self._auto_pull_check.isChecked()
        self._settings.pull_on_startup = self._pull_startup_check.isChecked()
        self._settings.save()
        self.accept()
