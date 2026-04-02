from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path


# Marker file that distinguishes an Asset directory from a plain Folder.
# Its presence inside a directory is the single source of truth.
ASSET_MARKER = ".conduitasset"


@dataclass
class BaseNode:
    path: Path
    parent: BaseNode | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return self.path.name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"


@dataclass
class FileNode(BaseNode):
    # Populated by the git layer once a task is selected; defaults to unknown.
    git_status: str = "unknown"  # "clean" | "modified" | "untracked" | "locked" | "unknown"

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()


@dataclass
class TaskNode(BaseNode):
    # Files are populated lazily (scanner.scan_task_files) when the task is selected.
    files: list[FileNode] = field(default_factory=list)


@dataclass
class AssetNode(BaseNode):
    tasks: list[TaskNode] = field(default_factory=list)


@dataclass
class FolderNode(BaseNode):
    # Children are FolderNodes or AssetNodes — never TaskNodes or FileNodes.
    children: list[FolderNode | AssetNode] = field(default_factory=list)
