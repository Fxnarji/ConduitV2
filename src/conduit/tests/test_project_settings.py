import json
import sys
from pathlib import Path
from conduit.model.project import ProjectConfig
from conduit.model.blender_installer import BlenderInstaller, blender_executable_for


class TestProjectConfigBlenderFields:
    def test_blender_fields_default(self):
        cfg = ProjectConfig(name="Test")
        assert cfg.blender_force_version is False
        assert cfg.blender_version_link is None

    def test_blender_fields_serialization(self):
        cfg = ProjectConfig(
            name="Test",
            blender_force_version=True,
            blender_version_link="Blender5.0/blender-5.0.1-windows-x64.zip",
        )
        data = cfg.to_dict()
        assert data["blender_force_version"] is True
        assert data["blender_version_link"] == "Blender5.0/blender-5.0.1-windows-x64.zip"

    def test_blender_fields_roundtrip(self):
        cfg = ProjectConfig(
            name="Test",
            blender_force_version=True,
            blender_version_link="Blender4.2/blender-4.2.1-linux-x64.zip",
        )
        loaded = ProjectConfig.from_dict(cfg.to_dict())
        assert loaded.blender_force_version is True
        assert loaded.blender_version_link == "Blender4.2/blender-4.2.1-linux-x64.zip"

    def test_blender_fields_backward_compat(self):
        data = {"name": "OldProject", "version": 1}
        cfg = ProjectConfig.from_dict(data)
        assert cfg.blender_force_version is False
        assert cfg.blender_version_link is None


class TestBlenderInstaller:
    def test_status_not_installed(self, tmp_path):
        inst = BlenderInstaller(
            "Blender5.0/blender-5.0.1-windows-x64.zip",
            tmp_path,
        )
        assert not inst.is_installed
        assert "Not installed" in inst.status()

    def test_status_installed(self, tmp_path):
        inst = BlenderInstaller(
            "Blender5.0/blender-5.0.1-windows-x64.zip",
            tmp_path,
        )
        inst.blender_dir.mkdir(parents=True)
        exec_name = "blender.exe" if sys.platform == "win32" else "blender"
        (inst.blender_dir / exec_name).touch()
        assert inst.is_installed
        assert "Installed" in inst.status()

    def test_parse_dirname(self, tmp_path):
        inst = BlenderInstaller(
            "Blender5.0/blender-5.0.1-windows-x64.zip",
            tmp_path,
        )
        assert inst.dirname == "blender-5.0.1-windows-x64"

    def test_url_construction(self, tmp_path):
        inst = BlenderInstaller(
            "Blender5.0/blender-5.0.1-windows-x64.zip",
            tmp_path,
        )
        assert inst.url == (
            "https://download.blender.org/release/"
            "Blender5.0/blender-5.0.1-windows-x64.zip"
        )


class TestBlenderExecutableFinder:
    def test_returns_none_when_dir_missing(self, tmp_path):
        result = blender_executable_for(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_when_no_blender(self, tmp_path):
        install_dir = tmp_path / "02-ressources" / "blender-installs"
        install_dir.mkdir(parents=True)
        (install_dir / "random-file.txt").touch()
        result = blender_executable_for(tmp_path)
        assert result is None

    def test_finds_blender_exe(self, tmp_path):
        install_dir = tmp_path / "02-ressources" / "blender-installs"
        install_dir.mkdir(parents=True)
        blender_dir = install_dir / "blender-5.0.1-windows-x64"
        blender_dir.mkdir()
        exec_name = "blender.exe" if sys.platform == "win32" else "blender"
        (blender_dir / exec_name).touch()

        result = blender_executable_for(tmp_path)
        expected = blender_dir / exec_name
        assert result == expected
