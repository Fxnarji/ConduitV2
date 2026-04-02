from __future__ import annotations
import shutil
import subprocess
import zipfile
import sys
import os
from pathlib import Path


def _bundled_templates_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources" / "templates"
    return Path(__file__).parents[3] / "resources" / "templates"


def _bundled_app_template_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "resources" / "blender_app_template"
    return Path(__file__).parents[3] / "resources" / "blender_app_template"


_PLATFORM_MAP = {
    "win32": "windows-x64",
    "darwin-x64": "darwin-x64",
    "darwin-arm64": "darwin-arm64",
    "linux": "linux-x64",
}


def _detect_platform() -> str:
    if sys.platform == "win32":
        return "windows-x64"
    elif sys.platform == "darwin":
        import platform as plat_module
        arch = platform.machine()
        return "darwin-arm64" if arch == "arm64" else "darwin-x64"
    else:
        return "linux-x64"


class BlenderInstaller:
    BASE_URL = "https://download.blender.org/release"
    BLENDER_EXECUTABLE = "blender.exe" if sys.platform == "win32" else "blender"
    PORTABLE_SUBDIRS = ["autosaves", "extensions", "config", "scripts"]

    def __init__(
        self,
        version_link: str,
        install_directory: Path,
        progress_callback=None,
    ) -> None:
        self.version_link = version_link
        self.install_dir = install_directory
        self.progress_callback = progress_callback
        self.dirname = self._parse_dirname()
        self.url = f"{self.BASE_URL}/{version_link}"
        self.blender_dir = self.install_dir / self.dirname
        self.zip_path = self.install_dir / f"{self.dirname}.zip"
        self.exec_path = self.blender_dir / self.BLENDER_EXECUTABLE

    def _parse_dirname(self) -> str:
        link = self.version_link
        if "/" in link:
            return link.split("/")[-1].removesuffix(".zip")
        return link.removesuffix(".zip")

    @property
    def is_installed(self) -> bool:
        return self.exec_path.exists()

    def status(self) -> str:
        if self.is_installed:
            return f"Installed \u2713  {self.dirname}"
        return "Not installed"

    def download_blender(self) -> None:
        import requests
        self.progress_callback and self.progress_callback("Connecting…", 0)
        response = requests.get(self.url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(self.zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size and downloaded % (5 * 1024 * 1024) == 0:
                        pct = int(downloaded / total_size * 100)
                        mb = downloaded / 1024 / 1024
                        total_mb = total_size / 1024 / 1024
                        msg = f"{mb:.0f} / {total_mb:.0f} MB"
                        self.progress_callback and self.progress_callback(msg, pct)

        self.progress_callback and self.progress_callback("Download complete", 100)

    def unzip_blender(self) -> None:
        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            members = zip_ref.namelist()
            total = len(members)
            for i, member in enumerate(members):
                zip_ref.extract(member, self.install_dir)
                if i % 500 == 0:
                    pct = int(i / total * 100)
                    self.progress_callback and self.progress_callback(f"Extracting {pct}%", pct)

        os.remove(self.zip_path)
        self.progress_callback and self.progress_callback("Extracted", 100)

    def isolate_blender_prefs(self) -> None:
        portable_dir = self.blender_dir / "portable"
        for subdir in self.PORTABLE_SUBDIRS:
            os.makedirs(portable_dir / subdir, exist_ok=True)

    def add_app_template(self) -> None:
        src = _bundled_app_template_dir()
        if not src.exists():
            return
        major_minor = self.dirname.split("-")[1].rsplit(".", 1)[0]
        template_dest = (
            self.blender_dir
            / f"{major_minor}"
            / "scripts"
            / "startup"
            / "bl_app_templates_system"
            / "conduit"
        )
        os.makedirs(template_dest, exist_ok=True)
        for item in os.listdir(src):
            src_path = src / item
            dst_path = template_dest / item
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dst_path)

    def install(self) -> None:
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.download_blender()
        self.unzip_blender()
        self.isolate_blender_prefs()
        self.add_app_template()

    def launch(self, blend_file: Path, app_template: str = "conduit") -> None:
        subprocess.Popen(
            [str(self.exec_path), "--app-template", app_template, str(blend_file)]
        )


def blender_executable_for(project_root: Path) -> Path | None:
    install_dir = project_root / "02-ressources" / "blender-installs"
    if not install_dir.is_dir():
        return None
    for sub in install_dir.iterdir():
        if sub.is_dir() and (sub / BlenderInstaller.BLENDER_EXECUTABLE).exists():
            return sub / BlenderInstaller.BLENDER_EXECUTABLE
    return None
