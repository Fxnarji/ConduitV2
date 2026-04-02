import subprocess
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


def is_lfs_available() -> bool:
    """Return True only if git-lfs is reachable both via 'git lfs' and as a
    standalone binary — the latter is what git hooks use on Windows."""
    try:
        # Check the git wrapper
        r = subprocess.run(["git", "lfs", "version"], capture_output=True, text=True)
        if r.returncode != 0:
            return False
        # Also verify the standalone binary is on PATH (required by git hooks)
        r2 = subprocess.run(["git-lfs", "version"], capture_output=True)
        return r2.returncode == 0
    except FileNotFoundError:
        return False


def write_gitattributes(repo_path: Path, patterns: list[str]) -> None:
    lines = [f"{p} filter=lfs diff=lfs merge=lfs -text\n" for p in patterns]
    (repo_path / ".gitattributes").write_text("".join(lines), encoding="utf-8")
