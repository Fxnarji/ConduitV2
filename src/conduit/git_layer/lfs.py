import subprocess
import sys
from pathlib import Path


DEFAULT_LFS_PATTERNS: list[str] = [
    "*.blend", "*.blend1",
    "*.psd", "*.psb",
    "*.spp", "*.sbs", "*.sbsar",
    "*.png", "*.jpg", "*.jpeg", "*.tga", "*.tif", "*.tiff", "*.exr",
    "*.fbx", "*.obj", "*.abc", "*.ma", "*.mb",
    "*.mp4", "*.mov",
    "*.zip", "*.rar", "*.7z",
]


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    """Run subprocess with Windows console window suppression."""
    kwargs: dict = {"capture_output": True, "text": True}
    if cwd is not None:
        kwargs["cwd"] = cwd
    if check:
        kwargs["check"] = True
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


def is_lfs_available() -> bool:
    """Return True only if git-lfs is reachable both via 'git lfs' and as a
    standalone binary — the latter is what git hooks use on Windows."""
    try:
        r = _run(["git", "lfs", "version"])
        if r.returncode != 0:
            return False
        r2 = _run(["git-lfs", "version"])
        return r2.returncode == 0
    except FileNotFoundError:
        return False


def write_gitattributes(repo_path: Path, patterns: list[str]) -> None:
    lines = [f"{p} filter=lfs diff=lfs merge=lfs -text\n" for p in patterns]
    (repo_path / ".gitattributes").write_text("".join(lines), encoding="utf-8")
