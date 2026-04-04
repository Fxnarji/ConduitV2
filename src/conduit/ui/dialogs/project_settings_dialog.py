from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QLabel,
    QCheckBox, QProgressBar, QMessageBox,
)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent

from conduit.model.project import Project
from conduit.model.blender_installer import (
    BlenderInstaller,
    blender_executable_for,
    _detect_platform,
)


class _InstallWorker(QThread):
    progress = Signal(str, int)
    error    = Signal(str)
    finished = Signal()

    def __init__(self, installer: BlenderInstaller) -> None:
        super().__init__()
        self._installer = installer

    def run(self) -> None:
        self._installer.progress_callback = self.progress.emit
        try:
            self._installer.install()
        except Exception as e:
            self.error.emit(str(e))
        self.finished.emit()


class _SyncWorker(QThread):
    done        = Signal()
    done_local  = Signal()   # committed but no remote to push to
    error       = Signal(str)

    def __init__(self, repo, conf_file: Path) -> None:
        super().__init__()
        self._repo      = repo
        self._conf_file = conf_file

    def run(self) -> None:
        try:
            self._repo.stage_and_commit(
                [self._conf_file], "Update project settings"
            )
            if self._repo.has_remote():
                self._repo.push()
                self.done.emit()
            else:
                self.done_local.emit()
        except Exception as e:
            self.error.emit(str(e))


class ProjectSettingsDialog(QDialog):
    def __init__(self, project: Project, repo=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setMinimumSize(520, 360)
        self._project      = project
        self._repo         = repo
        self._installer:   BlenderInstaller | None = None
        self._worker:      _InstallWorker | None   = None
        self._sync_worker: _SyncWorker | None      = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Blender Settings</b>"))

        self._force_check = QCheckBox("Enforce Blender version")
        self._force_check.stateChanged.connect(self._on_version_changed)
        layout.addWidget(self._force_check)

        form = QFormLayout()
        form.setSpacing(8)

        self._version_edit = QLineEdit()
        self._version_edit.setPlaceholderText("e.g. 4.3.2")
        self._version_edit.textChanged.connect(self._on_version_changed)

        self._platform_label = QLabel()
        self._platform_label.setStyleSheet("color: #888; font-size: 11px;")

        self._url_label = QLabel()
        self._url_label.setStyleSheet("color: #888; font-size: 11px;")
        self._url_label.setWordWrap(True)

        form.addRow("Version:", self._version_edit)
        form.addRow("Platform:", self._platform_label)
        form.addRow("Download URL:", self._url_label)
        layout.addLayout(form)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._init_btn = QPushButton("Install Blender")
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

        # --- Bottom button row ---
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self._apply_btn = QPushButton("Apply && Sync")
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._on_apply_sync)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(self._apply_btn)
        bottom_row.addWidget(cancel_btn)
        layout.addLayout(bottom_row)

        self._load_state()

    # ------------------------------------------------------------------
    # Worker cleanup on close
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._wait_for_workers()
        event.accept()

    def _wait_for_workers(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.wait()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        cfg = self._project.config
        self._force_check.setChecked(cfg.blender_force_version)
        if cfg.blender_version:
            self._version_edit.setText(cfg.blender_version)
        self._on_version_changed()

    def _parse_version(self) -> str:
        """Return the trimmed version string, e.g. '4.3.2'."""
        return self._version_edit.text().strip()

    def _version_is_valid(self, v: str) -> bool:
        parts = v.split(".")
        return len(parts) == 3 and all(p.isdigit() for p in parts)

    def _on_version_changed(self) -> None:
        v = self._parse_version()
        platform = _detect_platform()
        self._platform_label.setText(f"{platform} (auto-detected)")

        if v and self._version_is_valid(v):
            install_dir = self._project.resources_path / "blender-installs"
            self._installer = BlenderInstaller(v, install_dir)
            self._url_label.setText(self._installer.url)
            self._init_btn.setEnabled(True)
            self._status_label.setText(self._installer.status())
        else:
            self._installer = None
            self._url_label.setText("—" if not v else "Invalid format — use X.Y.Z (e.g. 4.3.2)")
            self._init_btn.setEnabled(False)
            if not v and self._force_check.isChecked():
                self._status_label.setText("Version is required when enforcement is enabled.")
            else:
                self._status_label.setText("")

    # ------------------------------------------------------------------
    # Blender installation
    # ------------------------------------------------------------------

    def _on_init_blender(self) -> None:
        if not self._installer:
            return
        self._init_btn.setEnabled(False)
        self._apply_btn.setEnabled(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Installing…")

        self._worker = _InstallWorker(self._installer)
        self._worker.progress.connect(self._on_progress)
        self._worker.error.connect(self._on_install_error)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _on_progress(self, msg: str, pct: int) -> None:
        self._progress_bar.setValue(pct)
        self._status_label.setText(msg)

    def _on_install_error(self, msg: str) -> None:
        self._status_label.setText(f"Install failed: {msg}")

    def _on_install_finished(self) -> None:
        if self._worker is None:
            return
        self._worker = None
        self._progress_bar.setVisible(False)
        self._init_btn.setEnabled(True)
        self._apply_btn.setEnabled(True)
        self._on_version_changed()   # refresh status label

    # ------------------------------------------------------------------
    # Open install dir
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Apply & Sync
    # ------------------------------------------------------------------

    def _on_apply_sync(self) -> None:
        v = self._parse_version()
        if self._force_check.isChecked() and not v:
            self._status_label.setText("Version is required when enforcement is enabled.")
            return
        if v and not self._version_is_valid(v):
            self._status_label.setText("Invalid format — use X.Y.Z (e.g. 4.3.2)")
            return

        cfg = self._project.config
        cfg.blender_force_version = self._force_check.isChecked()
        cfg.blender_version       = v or None
        self._project.save_config()

        if not self._repo:
            self.accept()
            return

        self._apply_btn.setEnabled(False)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Syncing…")

        conf_file = self._project.root_path / self._project.CONF_FILE
        self._sync_worker = _SyncWorker(self._repo, conf_file)
        self._sync_worker.done.connect(self._on_sync_done)
        self._sync_worker.done_local.connect(self._on_sync_done_local)
        self._sync_worker.error.connect(self._on_sync_error)
        self._sync_worker.start()

    def _on_sync_done(self) -> None:
        self._sync_worker = None
        self.accept()

    def _on_sync_done_local(self) -> None:
        self._sync_worker = None
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        self._apply_btn.setEnabled(True)
        self._status_label.setText("Saved and committed — no remote configured, push skipped.")

    def _on_sync_error(self, msg: str) -> None:
        self._sync_worker = None
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        self._apply_btn.setEnabled(True)
        QMessageBox.warning(self, "Sync failed", msg)
