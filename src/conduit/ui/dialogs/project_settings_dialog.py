from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QDialogButtonBox, QLabel,
    QCheckBox, QProgressBar,
)
from PySide6.QtCore import QThread, Signal

from conduit.model.project import Project
from conduit.model.blender_installer import (
    BlenderInstaller,
    blender_executable_for,
    _detect_platform,
)


class _InstallWorker(QThread):
    progress = Signal(str, int)

    def __init__(self, installer: BlenderInstaller) -> None:
        super().__init__()
        self._installer = installer

    def run(self) -> None:
        self._installer.install()


class ProjectSettingsDialog(QDialog):
    def __init__(self, project: Project, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setMinimumSize(520, 340)
        self._project = project
        self._installer: BlenderInstaller | None = None
        self._worker: _InstallWorker | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Blender Settings</b>"))

        self._force_check = QCheckBox("Enforce Blender version")
        self._force_check.stateChanged.connect(self._on_force_changed)
        layout.addWidget(self._force_check)

        form = QFormLayout()
        form.setSpacing(8)

        self._link_edit = QLineEdit()
        self._link_edit.setPlaceholderText("Blender5.0/blender-5.0.1-windows-x64.zip")
        self._link_edit.textChanged.connect(self._on_link_changed)

        self._platform_label = QLabel()
        self._platform_label.setStyleSheet("color: #888; font-size: 11px;")

        self._url_label = QLabel()
        self._url_label.setStyleSheet("color: #888; font-size: 11px;")
        self._url_label.setWordWrap(True)

        form.addRow("Version link:", self._link_edit)
        form.addRow("Platform:", self._platform_label)
        form.addRow("Download URL:", self._url_label)
        layout.addLayout(form)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._init_btn = QPushButton("Init Blender")
        self._init_btn.setEnabled(False)
        self._init_btn.clicked.connect(self._on_init_blender)
        self._open_dir_btn = QPushButton("Open Install Dir")
        self._open_dir_btn.clicked.connect(self._on_open_install_dir)
        btn_row.addWidget(self._init_btn)
        btn_row.addWidget(self._open_dir_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status_label)

        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_state()
        self._on_link_changed()

    def _load_state(self) -> None:
        cfg = self._project.config
        self._force_check.setChecked(cfg.blender_force_version)
        if cfg.blender_version_link:
            self._link_edit.setText(cfg.blender_version_link)
        self._update_status()

    def _on_force_changed(self) -> None:
        self._update_status()

    def _on_link_changed(self) -> None:
        link = self._link_edit.text().strip()
        platform = _detect_platform()
        self._platform_label.setText(f"{platform} (auto-detected)")
        if link:
            url = f"https://download.blender.org/release/{link}"
            self._url_label.setText(url)
        else:
            self._url_label.setText("—")
        self._init_btn.setEnabled(bool(link) and link.endswith(".zip"))

    def _update_status(self) -> None:
        link = self._link_edit.text().strip()
        if link:
            install_dir = self._project.resources_path / "blender-installs"
            self._installer = BlenderInstaller(link, install_dir)
            self._status_label.setText(self._installer.status())
        elif self._force_check.isChecked():
            self._status_label.setText("No version link set.")
        else:
            self._status_label.setText("")

    def _on_init_blender(self) -> None:
        if not self._installer:
            return
        self._init_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Installing…")

        self._worker = _InstallWorker(self._installer)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _on_progress(self, msg: str, pct: int) -> None:
        self._progress_bar.setValue(pct)
        self._status_label.setText(msg)

    def _on_install_finished(self) -> None:
        self._worker = None
        self._progress_bar.setVisible(False)
        self._init_btn.setEnabled(True)
        self._update_status()

    def _on_open_install_dir(self) -> None:
        install_dir = self._project.resources_path / "blender-installs"
        install_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(install_dir)

    @staticmethod
    def _open_path(path: Path) -> None:
        import subprocess
        import sys
        if sys.platform == "win32":
            import os
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _on_accept(self) -> None:
        link = self._link_edit.text().strip()
        if self._force_check.isChecked() and not link:
            self._status_label.setText("Version link is required when enforcement is enabled.")
            return
        if link and not link.endswith(".zip"):
            self._status_label.setText("Version link must end with .zip")
            return
        cfg = self._project.config
        cfg.blender_force_version = self._force_check.isChecked()
        cfg.blender_version_link = link or None
        self._project.save_config()
        self.accept()
