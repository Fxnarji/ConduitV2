from datetime import datetime

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt

from conduit.git_layer.repo import CommitInfo


def _human_size(n: int) -> str:
    """Return a human-readable byte count, e.g. '42.3 MB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"  # unreachable, satisfies type checkers


def _relative_date(dt: datetime) -> str:
    """Return a friendly relative date string like '3d ago' or 'just now'."""
    delta = datetime.now() - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            mins = delta.seconds // 60
            return "just now" if mins == 0 else f"{mins}m ago"
        return f"{hours}h ago"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    if days < 30:
        return f"{days // 7}w ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


class HistoryItem(QWidget):
    """One row in the commit-history list inside the Files pane."""

    def __init__(self, info: CommitInfo) -> None:
        super().__init__()
        self.setObjectName("HistoryItem")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 7, 10, 7)
        root.setSpacing(3)

        # --- Row 1: commit message ---
        msg_label = QLabel(info.message)
        msg_label.setObjectName("HistoryMessage")
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore

        # --- Row 2: author · date (left)  +  file size (right) ---
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(0)

        date_str = _relative_date(info.date)
        meta_text = f"{info.author}  ·  {date_str}"
        meta_label = QLabel(meta_text)
        meta_label.setObjectName("HistoryMeta")
        meta_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # type: ignore

        size_label = QLabel(
            _human_size(info.file_size) if info.file_size is not None else "—"
        )
        size_label.setObjectName("HistorySize")
        size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore

        meta_row.addWidget(meta_label, 1)
        meta_row.addWidget(size_label)

        root.addWidget(msg_label)
        root.addLayout(meta_row)
