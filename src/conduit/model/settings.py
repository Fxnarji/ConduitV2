from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ConduitV2" / "settings.json"


@dataclass
class ClientSettings:
    known_projects: list[str] = field(default_factory=list)
    fetch_interval_minutes: int = 10
    auto_pull_after_fetch: bool = False
    pull_on_startup: bool = False

    @classmethod
    def load(cls) -> "ClientSettings":
        path = _config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls(
                    known_projects=data.get("known_projects", []),
                    fetch_interval_minutes=data.get("fetch_interval_minutes", 10),
                    auto_pull_after_fetch=data.get("auto_pull_after_fetch", False),
                    pull_on_startup=data.get("pull_on_startup", False),
                )
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "known_projects": self.known_projects,
                    "fetch_interval_minutes": self.fetch_interval_minutes,
                    "auto_pull_after_fetch": self.auto_pull_after_fetch,
                    "pull_on_startup": self.pull_on_startup,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def add_project(self, root_path: str | Path) -> None:
        path = str(Path(root_path).resolve())
        if path in self.known_projects:
            self.known_projects.remove(path)
        self.known_projects.insert(0, path)
        self.save()

    def remove_project(self, root_path: str | Path) -> None:
        path = str(Path(root_path).resolve())
        if path in self.known_projects:
            self.known_projects.remove(path)
            self.save()

    def get_recent_projects(self, n: int = 5) -> list[str]:
        valid = [p for p in self.known_projects if Path(p).exists()]
        if len(valid) < len(self.known_projects):
            self.known_projects = valid
            self.save()
        return valid[:n]
