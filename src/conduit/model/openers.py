"""
Infrastructure for opening files with specific applications.

APP_OPENERS maps file extensions (lowercase, with leading dot) to the full
path of the binary to use for that type. A value of None means "use the
OS system default" (os.startfile on Windows, open on macOS, xdg-open on Linux).

Add entries here as new DCCs are supported, e.g.:
    ".blend": r"C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",
    ".spp":   r"C:\\Program Files\\Adobe\\Adobe Substance 3D Painter\\Adobe Substance 3D Painter.exe",
"""

from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

# Extension → binary path (str) or None for OS default.
APP_OPENERS: dict[str, str | None] = {}


def open_file(path: Path, openers: dict[str, str | None] | None = None) -> None:
    """Open *path* using the configured binary, falling back to the OS default."""
    resolved = openers or {}
    binary = resolved.get(path.suffix.lower())

    if binary:
        subprocess.Popen([binary, str(path)])
        return

    # OS default
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
