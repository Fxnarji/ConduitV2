from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QWidget,
)
from PySide6.QtCore import Qt


class ConflictDialog(QDialog):
    """Binary conflict resolution dialog.

    Shows each conflicted file with Keep mine / Take theirs buttons.
    The Confirm button is only enabled once every file has a choice.
    Rejecting the dialog (Cancel Merge) means the caller should abort_merge().
    """

    def __init__(self, conflicted_files: list[Path], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Merge Conflicts")
        self.setMinimumWidth(460)

        # resolution: file -> "ours" | "theirs" | None
        self._resolution: dict[Path, str | None] = {f: None for f in conflicted_files}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QLabel(
            "These files conflict with the remote version.\n"
            "Because they are binary files, choose one version for each:"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)  # type: ignore
        layout.addWidget(sep)

        # Scroll area so long conflict lists don't overflow the window
        scroll_content = QWidget()
        rows_layout = QVBoxLayout(scroll_content)
        rows_layout.setSpacing(6)
        rows_layout.setContentsMargins(0, 0, 0, 0)

        for f in conflicted_files:
            self._add_file_row(rows_layout, f)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)  # type: ignore
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)  # type: ignore
        layout.addWidget(sep2)

        # Bottom action row
        self._confirm_btn = QPushButton("Confirm Resolution")
        self._confirm_btn.setEnabled(False)
        abort_btn = QPushButton("Cancel Merge")

        btn_row = QHBoxLayout()
        btn_row.addWidget(abort_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._confirm_btn)
        layout.addLayout(btn_row)

        abort_btn.clicked.connect(self.reject)
        self._confirm_btn.clicked.connect(self.accept)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_file_row(self, layout: QVBoxLayout, f: Path) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)

        label = QLabel(f"  ● {f.name}")
        label.setToolTip(str(f))

        mine_btn   = QPushButton("Keep mine")
        theirs_btn = QPushButton("Take theirs")
        mine_btn.setFixedWidth(100)
        theirs_btn.setFixedWidth(100)

        def _pick(choice: str, m=mine_btn, t=theirs_btn) -> None:
            self._resolution[f] = choice
            m.setStyleSheet("font-weight: bold;" if choice == "ours"   else "")
            t.setStyleSheet("font-weight: bold;" if choice == "theirs" else "")
            self._confirm_btn.setEnabled(
                all(v is not None for v in self._resolution.values())
            )

        mine_btn.clicked.connect(lambda: _pick("ours"))
        theirs_btn.clicked.connect(lambda: _pick("theirs"))

        row.addWidget(label)
        row.addStretch()
        row.addWidget(mine_btn)
        row.addWidget(theirs_btn)
        layout.addLayout(row)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def resolutions(self) -> dict[Path, str]:
        """Mapping of file → "ours" | "theirs" for all resolved files."""
        return {f: v for f, v in self._resolution.items() if v is not None}
