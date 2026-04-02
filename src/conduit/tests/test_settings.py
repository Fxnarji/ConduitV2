import json
from pathlib import Path
from conduit.model.settings import ClientSettings, _config_path


def test_defaults():
    settings = ClientSettings()
    assert settings.known_projects == []
    assert settings.fetch_interval_minutes == 10
    assert settings.auto_pull_after_fetch is False
    assert settings.pull_on_startup is False


def test_load_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings.load()
    assert settings.fetch_interval_minutes == 10
    assert settings.auto_pull_after_fetch is False


def test_load_corrupt_file_returns_defaults(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text("not valid json{", encoding="utf-8")
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: path)
    settings = ClientSettings.load()
    assert settings.fetch_interval_minutes == 10


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings()
    settings.fetch_interval_minutes = 5
    settings.auto_pull_after_fetch = True
    settings.pull_on_startup = True
    settings.known_projects = ["/path/to/project"]
    settings.save()

    loaded = ClientSettings.load()
    assert loaded.fetch_interval_minutes == 5
    assert loaded.auto_pull_after_fetch is True
    assert loaded.pull_on_startup is True
    assert loaded.known_projects == ["/path/to/project"]


def test_add_project_deduplicates_and_moves_to_front(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings()
    settings.known_projects = ["/a", "/b", "/c"]
    settings.save()

    settings.add_project("/b")
    assert settings.known_projects == ["/b", "/a", "/c"]


def test_add_project_new_path(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings()
    settings.known_projects = ["/a", "/b"]
    settings.save()

    settings.add_project("/c")
    assert settings.known_projects == ["/c", "/a", "/b"]


def test_remove_project(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings()
    settings.known_projects = ["/a", "/b", "/c"]
    settings.save()

    settings.remove_project("/b")
    assert settings.known_projects == ["/a", "/c"]


def test_remove_nonexistent_project_noop(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings()
    settings.known_projects = ["/a"]
    settings.save()

    settings.remove_project("/nonexistent")
    assert settings.known_projects == ["/a"]


def test_get_recent_projects_filters_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings()
    settings.known_projects = [str(tmp_path / "exists1"), "/nonexistent", str(tmp_path / "exists2")]
    settings.save()
    (tmp_path / "exists1").mkdir()
    (tmp_path / "exists2").mkdir()

    result = settings.get_recent_projects()
    assert result == [str(tmp_path / "exists1"), str(tmp_path / "exists2")]


def test_get_recent_projects_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("conduit.model.settings._config_path", lambda: tmp_path / "settings.json")
    settings = ClientSettings()
    paths = [str(tmp_path / str(i)) for i in range(6)]
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)
    settings.known_projects = paths
    settings.save()
    assert len(settings.get_recent_projects(3)) == 3
