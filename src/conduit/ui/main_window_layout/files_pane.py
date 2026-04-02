from pathlib import Path

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QLabel, QPushButton,
)
from PySide6.QtCore import Qt

from conduit.model.nodes import TaskNode
from conduit.model.scanner import scan_task_files
from conduit.ui.items import FileItem


class FilePane:
    def __init__(self) -> None:
        self._current_task: TaskNode | None = None
        self._current_file: Path | None = None
        self._history: list = []           # cached CommitInfo list from last populate
        self._suffix: str = ""             # file extension, e.g. ".blend"
        self._active_commit_hash: str | None = None
        self._active_version_name: str | None = None
        self._template_callback = None     # callable(task, template_path)
        self._checkout_callback = None     # callable(commit_hash)

        self.group_box = QGroupBox("Files")
        layout = QVBoxLayout(self.group_box)
        layout.setContentsMargins(4, 16, 4, 4)
        layout.setSpacing(4)

        # --- File header: actual filename + current disk size ---
        self._file_header = QLabel("")
        self._file_header.setObjectName("FilePaneHeader")
        self._file_header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore
        self._file_header.setVisible(False)
        layout.addWidget(self._file_header)

        # --- Stacked: page 0 = history list, page 1 = empty/template state ---
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Page 0 – commit history list
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("HistoryList")
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)  # type: ignore
        self.list_widget.setUniformItemSizes(False)
        self.list_widget.setSpacing(4)
        self._stack.addWidget(self.list_widget)

        # Page 1 – empty state
        self._empty_widget = QWidget()
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignCenter)  # type: ignore

        hint = QLabel("No files in this task.\nInitialise with a template:")
        hint.setAlignment(Qt.AlignCenter)  # type: ignore
        hint.setStyleSheet("color: #888; font-size: 11px;")
        empty_layout.addWidget(hint)

        self._tmpl_btn_layout = QVBoxLayout()
        self._tmpl_btn_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)  # type: ignore
        self._tmpl_btn_layout.setSpacing(6)
        empty_layout.addLayout(self._tmpl_btn_layout)

        self._stack.addWidget(self._empty_widget)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def set_templates_dir(self, templates_dir: Path) -> None:
        while self._tmpl_btn_layout.count():
            item = self._tmpl_btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not templates_dir.is_dir():
            return

        for tmpl in sorted(templates_dir.iterdir()):
            if not tmpl.is_file():
                continue
            btn = QPushButton(tmpl.name)
            btn.setFixedWidth(220)
            btn.clicked.connect(lambda _checked, t=tmpl: self._template_btn_clicked(t))
            self._tmpl_btn_layout.addWidget(btn)

    def set_template_callback(self, callback) -> None:
        self._template_callback = callback

    def set_checkout_callback(self, callback) -> None:
        """``callback(commit_hash: str) -> None`` — called when Get is clicked."""
        self._checkout_callback = callback

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def widget(self) -> QGroupBox:
        return self.group_box

    def get_current_file(self) -> Path | None:
        return self._current_file

    def get_active_version_name(self) -> str | None:
        """Return the display version name for the currently active commit."""
        return self._active_version_name

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def populate(self, task: TaskNode, repo=None) -> None:
        """Load the task's file and its git history."""
        self.clear()
        self._current_task = task

        files = scan_task_files(task)
        self._current_file = files[0].path if files else None

        if self._current_file:
            self._show_header(self._current_file)
            if repo:
                self._history = repo.log_of(self._current_file)
                self._suffix  = self._current_file.suffix
                n = len(self._history)
                if self._history:
                    # Newest commit = currently checked out = highest version number
                    self._active_commit_hash = self._history[0].hash
                    self._active_version_name = f"{task.name}_v{n - 1:03}{self._suffix}"
            self._rebuild_history_list()
            self._stack.setCurrentIndex(0)
        else:
            self._stack.setCurrentIndex(1)

    def set_active_commit(self, commit_hash: str) -> None:
        """Mark *commit_hash* as the active (checked-out) version and rebuild the list."""
        if not self._history or not self._current_task:
            return
        n = len(self._history)
        for i, entry in enumerate(self._history):
            if entry.hash == commit_hash:
                version_num = n - 1 - i
                self._active_commit_hash  = commit_hash
                self._active_version_name = (
                    f"{self._current_task.name}_v{version_num:03}{self._suffix}"
                )
                self._rebuild_history_list()
                break

    def clear(self) -> None:
        self.list_widget.clear()
        self._current_task        = None
        self._current_file        = None
        self._history             = []
        self._suffix              = ""
        self._active_commit_hash  = None
        self._active_version_name = None
        self._file_header.setVisible(False)
        self._stack.setCurrentIndex(0)

    def refresh_header(self) -> None:
        """Re-read disk size after a checkout and update the header label."""
        if self._current_file:
            self._show_header(self._current_file)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_history_list(self) -> None:
        self.list_widget.clear()
        n = len(self._history)
        if not n:
            self._add_no_commits_placeholder()
            return
        for i, entry in enumerate(self._history):
            version_num  = n - 1 - i
            version_name = f"{self._current_task.name}_v{version_num:03}{self._suffix}"
            is_active    = (entry.hash == self._active_commit_hash)
            self._add_history_entry(version_name, entry, is_active)

    def _show_header(self, path: Path) -> None:
        try:
            from conduit.ui.items.file_item import _human_size
            size_str = _human_size(path.stat().st_size)
        except OSError:
            size_str = "?"
        self._file_header.setText(f"  {path.name}   ·   {size_str}")
        self._file_header.setVisible(True)

    def _add_history_entry(self, version_name: str, info, is_active: bool = False) -> None:
        widget = FileItem(
            version_name,
            info,
            checkout_fn=self._checkout_callback,
            is_active=is_active,
        )
        item = QListWidgetItem()
        item.setData(Qt.UserRole, info)  # type: ignore
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _add_no_commits_placeholder(self) -> None:
        label_widget = QLabel("File added — no commits yet.")
        label_widget.setAlignment(Qt.AlignCenter)  # type: ignore
        label_widget.setStyleSheet("color: #666; font-size: 11px; padding: 16px;")
        item = QListWidgetItem()
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)  # type: ignore
        item.setSizeHint(label_widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, label_widget)

    def _template_btn_clicked(self, template_path: Path) -> None:
        if self._template_callback and self._current_task:
            self._template_callback(self._current_task, template_path)
