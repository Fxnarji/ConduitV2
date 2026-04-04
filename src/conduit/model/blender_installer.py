from __future__ import annotations
import shutil
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


def _detect_platform() -> str:
    if sys.platform == "win32":
        return "windows-x64"
    elif sys.platform == "darwin":
        import platform as plat_module
        arch = plat_module.machine()
        return "darwin-arm64" if arch == "arm64" else "darwin-x64"
    else:
        return "linux-x64"


class BlenderInstaller:
    BASE_URL          = "https://download.blender.org/release"
    BLENDER_EXECUTABLE = "blender.exe" if sys.platform == "win32" else "blender"
    PORTABLE_SUBDIRS  = ["autosaves", "extensions", "config", "scripts"]

    def __init__(
        self,
        version: str,            # e.g. "4.3.2"
        install_directory: Path,
        progress_callback=None,
    ) -> None:
        self.version          = version
        self.install_dir      = install_directory
        self.progress_callback = progress_callback

        platform    = _detect_platform()
        major_minor = ".".join(version.split(".")[:2])       # "4.3"
        self.dirname  = f"blender-{version}-{platform}"      # "blender-4.3.2-windows-x64"
        folder        = f"Blender{major_minor}"               # "Blender4.3"
        filename      = f"{self.dirname}.zip"

        self.url        = f"{self.BASE_URL}/{folder}/{filename}"
        self.blender_dir = self.install_dir / self.dirname
        self.zip_path    = self.install_dir / filename
        self.exec_path   = self.blender_dir / self.BLENDER_EXECUTABLE

    @property
    def is_installed(self) -> bool:
        return self.exec_path.exists()

    def status(self) -> str:
        if self.is_installed:
            return f"Installed \u2713  {self.dirname}"
        return "Not installed"

    def download_blender(self) -> None:
        import urllib.request
        import urllib.error

        if self.zip_path.exists():
            self.zip_path.unlink(missing_ok=True)

        if self.progress_callback:
            self.progress_callback("Connecting…", 0)

        try:
            request = urllib.request.Request(
                self.url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                total_size      = int(response.headers.get("Content-Length") or 0)
                downloaded      = 0
                last_reported_mb = -1

                with open(self.zip_path, "wb") as f:
                    while True:
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            current_mb = downloaded // (5 * 1024 * 1024)
                            if current_mb != last_reported_mb:
                                last_reported_mb = current_mb
                                pct      = int(downloaded / total_size * 100)
                                mb       = downloaded / 1024 / 1024
                                total_mb = total_size / 1024 / 1024
                                if self.progress_callback:
                                    self.progress_callback(
                                        f"{mb:.0f} / {total_mb:.0f} MB", pct
                                    )

            if self.progress_callback:
                self.progress_callback("Download complete", 100)

        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from e
        except TimeoutError as e:
            raise RuntimeError("Connection timed out after 60 seconds") from e

    def unzip_blender(self) -> None:
        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            members = zip_ref.namelist()
            total   = len(members)
            for i, member in enumerate(members):
                zip_ref.extract(member, self.install_dir)
                if i % 500 == 0:
                    pct = int(i / total * 100)
                    if self.progress_callback:
                        self.progress_callback(f"Extracting {pct}%", pct)

        os.remove(self.zip_path)
        if self.progress_callback:
            self.progress_callback("Extracted", 100)

    def isolate_blender_prefs(self) -> None:
        """Create a portable/ directory next to the exe to enable Blender's portable mode."""
        portable_dir = self.blender_dir / "portable"
        for subdir in self.PORTABLE_SUBDIRS:
            os.makedirs(portable_dir / subdir, exist_ok=True)

    def add_app_template(self) -> None:
        src = _bundled_app_template_dir()
        if not src.exists():
            return
        major_minor   = ".".join(self.version.split(".")[:2])   # "4.3"
        template_dest = (
            self.blender_dir
            / major_minor
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
        try:
            self.download_blender()
            self.unzip_blender()
            self.isolate_blender_prefs()
            self.add_app_template()
        except Exception:
            if self.zip_path.exists():
                self.zip_path.unlink(missing_ok=True)
            raise


def blender_executable_for(project_root: Path) -> Path | None:
    from conduit.model.project import Project
    install_dir = project_root / Project.RESOURCES_DIR / "blender-installs"
    if not install_dir.is_dir():
        return None
    for sub in install_dir.iterdir():
        if sub.is_dir() and (sub / BlenderInstaller.BLENDER_EXECUTABLE).exists():
            return sub / BlenderInstaller.BLENDER_EXECUTABLE
    return None
