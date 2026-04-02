from __future__ import annotations
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton, QFrame,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from conduit.git_layer.repo import CommitInfo

_ICON_DIR = Path(__file__).parent.parent / "icons"

_EXTENSION_ICONS: dict[str, str] = {
    ".blend":  "blender.png",
    ".png":    "png.png",
    ".jpg":    "png.png",
    ".jpeg":   "png.png",
    ".tga":    "png.png",
    ".tif":    "png.png",
    ".tiff":   "png.png",
    ".exr":    "png.png",
    ".psd":    "png.png",
    ".spp":    "png.png",
}


def _human_size(n: int) -> str:
    """Return a human-readable byte count, e.g. '42.3 MB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return ""


class FileItem(QWidget):
    """Displays one version entry in the Files pane history list.

    Parameters
    ----------
    version_name:
        Display name for this version, e.g. ``Sign01_modelling_v003.blend``.
    info:
        The CommitInfo for this version (author, message, file_size, …).
    checkout_fn:
        Optional callable ``(commit_hash: str) -> None`` called when the
        user clicks **Get**.
    is_active:
        When ``True``, renders a coloured left-side accent bar and bolds the
        version name to indicate this is the currently checked-out version.
    """

    def __init__(
        self,
        version_name: str,
        info: CommitInfo,
        checkout_fn: Callable[[str], None] | None = None,
        is_active: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName("FileItem")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Active indicator bar (left edge) ---
        if is_active:
            bar = QFrame()
            bar.setObjectName("ActiveIndicator")
            bar.setFixedWidth(4)
            outer.addWidget(bar)

        # --- Main content ---
        inner = QWidget()
        layout = QHBoxLayout(inner)
        layout.setContentsMargins(0, 6, 8, 6)
        layout.setSpacing(6)

        # Icon
        icon_label = QLabel()
        icon_label.setFixedSize(52, 40)
        icon_label.setAlignment(Qt.AlignCenter)  # type: ignore

        ext = Path(version_name).suffix.lower()
        icon_name = _EXTENSION_ICONS.get(ext, "asset.png")
        icon_path = _ICON_DIR / icon_name
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path)).scaled(
                28, 28,
                Qt.KeepAspectRatio,       # type: ignore
                Qt.SmoothTransformation,  # type: ignore
            )
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText("?")

        # Text block
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(version_name)
        name_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)  # type: ignore
        if is_active:
            font = name_label.font()
            font.setBold(True)
            name_label.setFont(font)

        size_str = _human_size(info.file_size) if info.file_size is not None else "—"
        msg = info.message if len(info.message) <= 60 else info.message[:57] + "…"
        meta_text = f'{info.author}  ·  "{msg}"  ·  {size_str}'

        meta_label = QLabel(meta_text)
        meta_label.setObjectName("FileItemMeta")
        meta_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)  # type: ignore

        text_layout.addWidget(name_label)
        text_layout.addWidget(meta_label)

        # Get button
        get_btn = QPushButton("Get")
        get_btn.setObjectName("GetButton")
        get_btn.setFixedSize(46, 26)
        get_btn.setToolTip(f"Restore working file to this version ({info.hash})")
        if checkout_fn is not None:
            commit_hash = info.hash
            get_btn.clicked.connect(lambda: checkout_fn(commit_hash))
        else:
            get_btn.setEnabled(False)

        layout.addWidget(icon_label)
        layout.addLayout(text_layout, 1)
        layout.addWidget(get_btn, 0, Qt.AlignVCenter)  # type: ignore

        outer.addWidget(inner, 1)
