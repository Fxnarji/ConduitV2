from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

from .nodes import FolderNode, AssetNode
from .scanner import scan_data_tree


@dataclass
class ProjectConfig:
    name: str
    git_remote: str | None = None
    blender_version: str | None = None   # e.g. "4.3.2" — used to install/launch Blender
    lfs_patterns: list[str] = field(default_factory=list)
    version: int = 1
    blender_force_version: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> ProjectConfig:
        # Accept legacy "blender_version_link" so old projects still load.
        blender_version = data.get("blender_version")
        if not blender_version:
            link = data.get("blender_version_link") or ""
            if link:
                # Extract the version number from the old link format
                # e.g. "Blender4.3/blender-4.3.2-windows-x64.zip" → "4.3.2"
                filename = link.split("/")[-1]          # "blender-4.3.2-windows-x64.zip"
                parts    = filename.split("-")          # ["blender", "4.3.2", ...]
                blender_version = parts[1] if len(parts) > 1 else None
        return cls(
            name=data.get("name", "Unnamed Project"),
            git_remote=data.get("git_remote"),
            blender_version=blender_version,
            lfs_patterns=data.get("lfs_patterns", []),
            version=data.get("version", 1),
            blender_force_version=data.get("blender_force_version", False),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "name": self.name,
            "git_remote": self.git_remote,
            "blender_version": self.blender_version,
            "lfs_patterns": self.lfs_patterns,
            "blender_force_version": self.blender_force_version,
        }


class Project:
    DATA_DIR = "00-data"
    CONF_DIR = "01-conf"
    RESOURCES_DIR = "02-ressources"
    CACHE_DIR = "_cache"
    CONF_FILE = "01-conf/project.json"

    def __init__(
        self,
        root_path: Path,
        config: ProjectConfig,
        tree: list[FolderNode | AssetNode],
    ) -> None:
        self.root_path = root_path
        self.config = config
        self.tree = tree

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def data_path(self) -> Path:
        return self.root_path / self.DATA_DIR

    @property
    def conf_path(self) -> Path:
        return self.root_path / self.CONF_DIR

    @property
    def resources_path(self) -> Path:
        return self.root_path / self.RESOURCES_DIR

    @property
    def templates_path(self) -> Path:
        """Per-project templates directory: ``02-ressources/templates/``."""
        return self.resources_path / "templates"

    @property
    def cache_path(self) -> Path:
        return self.root_path / self.CACHE_DIR

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, root_path: Path) -> Project:
        """Open an existing Conduit project from *root_path*.

        Raises FileNotFoundError if the directory or its 00-data sub-directory
        are missing. A missing project.json is tolerated; a default config is
        used instead.
        """
        root_path = root_path.resolve()

        if not root_path.is_dir():
            raise FileNotFoundError(f"Project directory not found: {root_path}")

        data_dir = root_path / cls.DATA_DIR
        if not data_dir.is_dir():
            raise FileNotFoundError(
                f"Not a valid Conduit project (missing 00-data): {root_path}"
            )

        conf_file = root_path / cls.CONF_FILE
        if conf_file.exists():
            config = ProjectConfig.from_dict(
                json.loads(conf_file.read_text(encoding="utf-8"))
            )
        else:
            config = ProjectConfig(name=root_path.name)

        tree = scan_data_tree(data_dir)
        return cls(root_path=root_path, config=config, tree=tree)

    @classmethod
    def create(
        cls,
        root_path: Path,
        name: str,
        git_remote: str | None = None,
        lfs_patterns: list[str] | None = None,
    ) -> "Project":
        """Scaffold a new Conduit project and initialise the git repository."""
        from conduit.git_layer.repo import ConduitRepo
        from conduit.git_layer.lfs import DEFAULT_LFS_PATTERNS

        root_path = root_path.resolve()
        root_path.mkdir(parents=True, exist_ok=True)

        (root_path / cls.DATA_DIR).mkdir(exist_ok=True)
        (root_path / cls.CONF_DIR).mkdir(exist_ok=True)
        (root_path / cls.RESOURCES_DIR).mkdir(exist_ok=True)
        (root_path / cls.RESOURCES_DIR / "templates").mkdir(exist_ok=True)
        cache = root_path / cls.CACHE_DIR
        cache.mkdir(exist_ok=True)
        (cache / ".gitkeep").write_bytes(b"")

        patterns = lfs_patterns or DEFAULT_LFS_PATTERNS
        config = ProjectConfig(name=name, git_remote=git_remote, lfs_patterns=patterns)

        conf_file = root_path / cls.CONF_FILE
        conf_file.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")

        repo = ConduitRepo.init(root_path, patterns)

        to_commit = [root_path / ".gitignore", conf_file]
        gitattributes = root_path / ".gitattributes"
        if gitattributes.exists():
            to_commit.append(gitattributes)
        repo.stage_and_commit(to_commit, "Initial Conduit project scaffold")

        if git_remote:
            repo.set_remote(git_remote)

        tree = scan_data_tree(root_path / cls.DATA_DIR)
        return cls(root_path=root_path, config=config, tree=tree)

    def save_config(self) -> None:
        """Write the current config back to 01-conf/project.json."""
        self.conf_path.mkdir(parents=True, exist_ok=True)
        conf_file = self.root_path / self.CONF_FILE
        conf_file.write_text(
            json.dumps(self.config.to_dict(), indent=2),
            encoding="utf-8",
        )

    def reload_tree(self) -> None:
        """Re-scan 00-data and replace the in-memory tree."""
        self.tree = scan_data_tree(self.data_path)

    def __repr__(self) -> str:
        return f"Project({self.name!r}, root={self.root_path})"
