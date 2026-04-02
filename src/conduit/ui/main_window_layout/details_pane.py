from pathlib import Path

from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
)
from PySide6.QtCore import Qt


class DetailPane:
    """Right-hand detail panel.

    Contains all task-level actions: commit/push, pull, lock/unlock, and open.
    Buttons are exposed as public attributes so MainWindow can connect signals.

    Two separate enable states:
    - ``set_repo_enabled(bool)``  — requires a git repo  (commit, push, pull)
    - ``set_task_enabled(bool)``  — requires a task file (lock, unlock, open)
    """

    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._file_path: Path | None = None
        self.locked = False

        self.group_box = QGroupBox("Details")
        layout = QVBoxLayout(self.group_box)
        layout.setContentsMargins(8, 20, 8, 8)
        layout.setSpacing(8)

        # --- Task name ---
        self._task_label = QLabel("—")
        self._task_label.setObjectName("DetailTaskName")
        self._task_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # type: ignore
        self._task_label.setWordWrap(True)
        layout.addWidget(self._task_label)

        layout.addWidget(self._make_separator())

        # --- Git section ---
        layout.addWidget(self._make_section_header("Git"))
        self.commit_push_btn = QPushButton("Push")
        self.pull_btn        = QPushButton("Pull")
        layout.addWidget(self.commit_push_btn)
        layout.addWidget(self.pull_btn)

        layout.addWidget(self._make_separator())

        # --- Lock status section ---
        layout.addWidget(self._make_section_header("Lock Status"))

        self._lock_label = QLabel("—")
        self._lock_label.setObjectName("DetailLockLabel")
        layout.addWidget(self._lock_label)

        lock_row = QHBoxLayout()
        lock_row.setSpacing(6)
        self.lock_btn   = QPushButton("Lock")
        self.unlock_btn = QPushButton("Unlock")
        lock_row.addWidget(self.unlock_btn)
        lock_row.addWidget(self.lock_btn)
        layout.addLayout(lock_row)

        layout.addWidget(self._make_separator())

        # --- File section ---
        layout.addWidget(self._make_section_header("File"))

        self._version_label = QLabel("—")
        self._version_label.setObjectName("DetailVersionLabel")
        self._version_label.setWordWrap(True)
        layout.addWidget(self._version_label)

        self.open_btn = QPushButton("Open")
        self.open_btn.setToolTip(
            "Open the current working-tree file.\n"
            "Click Get on a history entry first to restore a specific version."
        )
        layout.addWidget(self.open_btn)

        layout.addStretch()

        # Start fully disabled
        self.set_repo_enabled(False)
        self.set_task_enabled(False)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def widget(self) -> QGroupBox:
        return self.group_box

    def set_task(
        self,
        task_name: str | None,
        file_path: Path | None,
        lock_owner: str | None,
    ) -> None:
        """Refresh task name and lock status display.

        Call whenever the active task or its lock state changes.
        """
        self._file_path = file_path
        self._task_label.setText(task_name or "—")

        if file_path:
            self._set_lock_display(lock_owner)
            self.set_task_enabled(True)
        else:
            self._lock_label.setText("● No file")
            self._lock_label.setStyleSheet("color: #666666; font-size: 11px;")
            self._version_label.setText("—")
            self.set_task_enabled(False)

    def set_checked_out_version(self, version_name: str | None) -> None:
        """Update the version name shown in the File section.

        Call after populate and after each Get / checkout operation.
        """
        self._version_label.setText(version_name or "—")

    def set_repo_enabled(self, enabled: bool) -> None:
        """Enable/disable buttons that require a git repo (commit & push, pull)."""
        for btn in (self.commit_push_btn, self.pull_btn):
            btn.setEnabled(enabled)

    def set_task_enabled(self, enabled: bool) -> None:
            """Enable/disable buttons that require an active task file."""
            # Include both buttons here; Qt handles disabled + hidden widgets fine.
            for btn in (self.lock_btn, self.unlock_btn, self.open_btn):
                btn.setEnabled(enabled)

    def get_file_path(self) -> Path | None:
        """Return the file path from the last ``set_task()`` call."""
        return self._file_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_lock_display(self, lock_owner: str | None) -> None:
            if lock_owner:
                self.locked = True
                self._lock_label.setText(f"● Locked by {lock_owner}")
                self._lock_label.setStyleSheet("color: #cc6666; font-size: 11px;")
                
                # UI Swap: Show Unlock, Hide Lock
                self.lock_btn.hide()
                self.unlock_btn.show()
            else:
                self.locked = False
                self._lock_label.setText("● Unlocked")
                self._lock_label.setStyleSheet("color: #88cc88; font-size: 11px;")
                
                # UI Swap: Show Lock, Hide Unlock
                self.unlock_btn.hide()
                self.lock_btn.show()

    @staticmethod
    def _make_section_header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("DetailSectionHeader")
        return lbl

    @staticmethod
    def _make_separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)  # type: ignore
        sep.setObjectName("DetailSeparator")
        return sep
