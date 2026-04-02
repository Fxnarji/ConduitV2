from __future__ import annotations
from pathlib import Path

from .nodes import FolderNode, AssetNode, TaskNode, FileNode, ASSET_MARKER
from .ignore import is_ignored


# Directory names that are never included in the tree regardless of location.
_SKIP_NAMES: frozenset[str] = frozenset({".git", "_cache", "__pycache__"})


def scan_data_tree(data_path: Path) -> list[FolderNode | AssetNode]:
    """Walk *data_path* (the project's 00-data directory) and return a list of
    top-level FolderNode / AssetNode objects.

    Rules:
    - A directory containing a .conduitasset file is an AssetNode.
    - All other directories are FolderNodes.
    - Folders recurse; Assets do not (their direct children become TaskNodes).
    - Hidden directories (starting with '.'), _cache, and __pycache__ are skipped.
    """
    if not data_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {data_path}")

    return _scan_dir(data_path, parent=None)


def _scan_dir(path: Path, parent: FolderNode | None) -> list[FolderNode | AssetNode]:
    nodes: list[FolderNode | AssetNode] = []

    try:
        entries = sorted(path.iterdir(), key=lambda e: e.name.lower())
    except PermissionError:
        return nodes

    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name in _SKIP_NAMES or entry.name.startswith("."):
            continue

        if (entry / ASSET_MARKER).exists():
            node = AssetNode(path=entry, parent=parent)
            node.tasks = _scan_asset(node)
            nodes.append(node)
        else:
            node = FolderNode(path=entry, parent=parent)
            node.children = _scan_dir(entry, parent=node)
            nodes.append(node)

    return nodes


def _scan_asset(asset: AssetNode) -> list[TaskNode]:
    """Return TaskNodes for each subdirectory directly inside an Asset."""
    tasks: list[TaskNode] = []

    try:
        entries = sorted(asset.path.iterdir(), key=lambda e: e.name.lower())
    except PermissionError:
        return tasks

    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        tasks.append(TaskNode(path=entry, parent=asset))

    return tasks


def scan_task_files(task: TaskNode) -> list[FileNode]:
    """Scan a task directory for files (non-recursive).

    Called lazily when a task is selected in the UI, not during the initial
    tree scan. The returned FileNodes have git_status='unknown' until the git
    layer fills them in.
    """
    files: list[FileNode] = []

    try:
        entries = sorted(task.path.iterdir(), key=lambda e: e.name.lower())
    except PermissionError:
        return files

    for entry in entries:
        if entry.is_file() and not entry.name.startswith(".") and not is_ignored(entry.name):
            files.append(FileNode(path=entry, parent=task, git_status="unknown"))

    return files
