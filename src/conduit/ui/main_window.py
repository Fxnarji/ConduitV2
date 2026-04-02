import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QMenu, QInputDialog, QMessageBox,
    QLabel, QFileDialog, QApplication, QProgressBar, QDialog,
)

from conduit.model.nodes import FolderNode, AssetNode, TaskNode
from conduit.model.project import Project
from conduit.model.scanner import scan_data_tree
from conduit.model.settings import ClientSettings
from conduit.model.blender_installer import blender_executable_for
from conduit.git_layer.repo import ConduitRepo, GitError, MergeConflictError
from conduit.model.openers import APP_OPENERS, open_file
from conduit.ui.items import CustomTitleBar
from conduit.ui.main_window_layout.details_pane import DetailPane
from conduit.ui.main_window_layout.folder_pane import FolderPane
from conduit.ui.main_window_layout.tasks_pane import TaskPane
from conduit.ui.main_window_layout.files_pane import FilePane
from conduit.ui.dialogs.new_project_dialog import NewProjectDialog
from conduit.ui.dialogs.clone_dialog import CloneDialog
from conduit.ui.dialogs.commit_dialog import CommitDialog
from conduit.ui.dialogs.settings_dialog import SettingsDialog
from conduit.ui.dialogs.project_settings_dialog import ProjectSettingsDialog

from conduit import __version__


def _bundled_templates_dir() -> Path:
    """Return the app's built-in seed templates dir (bundled with the exe)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "resources" / "templates"
    return Path(__file__).parents[3] / "resources" / "templates"


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _GitWorker(QThread):
    success = Signal(str)
    error   = Signal(str)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self._fn     = fn
        self._args   = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.success.emit(str(result) if result is not None else "")
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Conduit")
        self.setWindowFlags(Qt.FramelessWindowHint)  # type: ignore
        self.resize(1200, 600)

        self._project:        Project | None = None
        self._repo:           ConduitRepo | None = None
        self._worker:         _GitWorker | None = None
        self._fetch_worker:   _GitWorker | None = None
        self._commits_behind: int = 0
        self._settings:        ClientSettings = ClientSettings.load()
        self._blender_opener: dict[str, str] = {}

        self._fetch_timer = QTimer(self)
        self._fetch_timer.setInterval(self._settings.fetch_interval_minutes * 60 * 1000)
        self._fetch_timer.timeout.connect(self._on_fetch_tick)

        # --- Central widget ---
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Title bar ---
        self.title_bar = CustomTitleBar(self)
        root.addWidget(self.title_bar)

        # --- Toolbar ---
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet("border: none;")
        root.addWidget(self.toolbar)
        self._build_toolbar()

        # --- Panes ---
        self.folder_pane = FolderPane()
        self.task_pane   = TaskPane()
        self.file_pane   = FilePane()
        self.detail_pane = DetailPane(self)

        pane_layout = QHBoxLayout()
        pane_layout.setContentsMargins(4, 4, 4, 4)
        pane_layout.setSpacing(4)
        pane_layout.addWidget(self.folder_pane.widget(), 3)
        pane_layout.addWidget(self.task_pane.widget(),   2)
        pane_layout.addWidget(self.file_pane.widget(),   6)
        pane_layout.addWidget(self.detail_pane.widget(), 2)
        root.addLayout(pane_layout)

        # --- Footer ---
        self._version_label = QLabel(f"Conduit {__version__}")
        self._project_label = QLabel("No project loaded")
        self._status_label  = QLabel("")
        self._progress_bar  = QProgressBar()
        self._setup_footer(root)

        # --- Pane signals ---
        self.folder_pane.tree_view.clicked.connect(self._on_folder_clicked)
        self.task_pane.list_widget.itemClicked.connect(self._on_task_clicked)

        # --- File pane wiring ---
        self.file_pane.set_template_callback(self._on_template_picked)
        self.file_pane.set_checkout_callback(self._on_checkout_version)

        # --- Detail pane wiring ---
        self.detail_pane.commit_push_btn.clicked.connect(self._on_commit_and_push)
        self.detail_pane.pull_btn.clicked.connect(self._on_pull)
        self.detail_pane.lock_btn.clicked.connect(self._on_lock)
        self.detail_pane.unlock_btn.clicked.connect(self._on_unlock)
        self.detail_pane.open_btn.clicked.connect(self._on_open_file)

        # --- Context menus ---
        self.folder_pane.widget().setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore
        self.folder_pane.widget().customContextMenuRequested.connect(self._folder_context_menu)

        self.task_pane.widget().setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore
        self.task_pane.widget().customContextMenuRequested.connect(self._task_context_menu)

        self.file_pane.widget().setContextMenuPolicy(Qt.CustomContextMenu)  # type: ignore
        self.file_pane.widget().customContextMenuRequested.connect(self._file_context_menu)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        self.toolbar.addAction("Projects").triggered.connect(self._show_projects_menu)
        self.toolbar.addAction("Project Settings").triggered.connect(self._open_project_settings)
        self.toolbar.addAction("Settings").triggered.connect(self._open_settings)
        self.toolbar.addAction("Console").triggered.connect(self._open_console)

    def _show_projects_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("New Project…", self._new_project)

        recent = self._settings.get_recent_projects(5)
        if recent:
            for path in recent:
                label = Path(path).name
                action = menu.addAction(label)
                action.triggered.connect(lambda checked, p=path: self._open_project_path(Path(p)))
            menu.addSeparator()

        menu.addAction("Open Project…",  self._open_project)
        menu.addAction("Clone Project…", self._clone_project)
        pos = self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft())
        menu.exec_(pos)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _setup_footer(self, layout: QVBoxLayout) -> None:
        footer = QWidget()
        footer.setFixedHeight(26)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(10, 0, 10, 0)
        fl.setSpacing(10)

        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedSize(160, 14)
        self._progress_bar.setVisible(False)

        fl.addWidget(self._version_label)
        fl.addStretch()
        fl.addWidget(self._status_label)
        fl.addWidget(self._progress_bar)
        fl.addWidget(self._project_label)
        layout.addWidget(footer)

    def _set_status(self, msg: str, colour: str = "#aaaaaa") -> None:
        self._status_label.setText(msg)
        self._status_label.setStyleSheet(f"color: {colour}; font-size: 11px;")

    def _refresh_footer(self) -> None:
        if self._project:
            parts = [self._project.name]
            remote = self._repo.get_remote_url() if self._repo else None
            if remote:
                parts.append(remote)
            if self._commits_behind > 0:
                parts.append(f"{self._commits_behind} commits available ↓")
            self._project_label.setText("  ·  ".join(parts))
        else:
            self._project_label.setText("No project loaded")

    # ------------------------------------------------------------------
    # Background fetch
    # ------------------------------------------------------------------

    def _on_fetch_tick(self) -> None:
        """Run a silent background fetch and update the commits-behind counter."""
        if not self._repo or not self._repo.has_remote():
            return
        if self._fetch_worker and self._fetch_worker.isRunning():
            return
        worker = _GitWorker(self._repo.fetch)
        worker.success.connect(lambda _: self._after_silent_fetch())
        worker.error.connect(lambda _: None)
        self._fetch_worker = worker
        worker.start()

    def _after_silent_fetch(self) -> None:
        self._fetch_worker = None
        if not self._repo:
            return
        self._commits_behind = self._repo.commits_behind()
        self._refresh_footer()
        if (
            self._settings.auto_pull_after_fetch
            and self._commits_behind > 0
            and self._repo.has_remote()
        ):
            self._on_pull()

    # ------------------------------------------------------------------
    # Project loading
    # ------------------------------------------------------------------

    def load_project(self, project: Project, repo: ConduitRepo | None) -> None:
        self._project        = project
        self._repo           = repo
        self._commits_behind = 0
        self.folder_pane.refresh_tree(project.tree)
        self.task_pane.clear()
        self.file_pane.clear()
        self.file_pane.set_templates_dir(project.templates_path)
        self.detail_pane.set_task(None, None, None)
        self.detail_pane.set_repo_enabled(repo is not None)
        self._refresh_footer()
        self._set_status("Project loaded", "#88cc88")

        self._fetch_timer.stop()
        self._fetch_timer.setInterval(self._settings.fetch_interval_minutes * 60 * 1000)
        self._settings.add_project(project.root_path)
        self._refresh_blender_opener()
        if repo is not None and repo.has_remote():
            self._on_fetch_tick()
            self._fetch_timer.start()
            if self._settings.pull_on_startup:
                self._on_pull()

    # ------------------------------------------------------------------
    # Pane selection handlers
    # ------------------------------------------------------------------

    def _on_folder_clicked(self, index) -> None:
        node = self.folder_pane.get_selected_node()
        if not isinstance(node, AssetNode):
            self.task_pane.clear()
            self.file_pane.clear()
            self.detail_pane.set_task(None, None, None)
            self.detail_pane.set_checked_out_version(None)
            return
        self.task_pane.populate(node.tasks)
        self.file_pane.clear()
        self.detail_pane.set_task(None, None, None)
        self.detail_pane.set_checked_out_version(None)

    def _on_task_clicked(self, item) -> None:
        task: TaskNode | None = item.data(Qt.UserRole)  # type: ignore
        if not task:
            return
        self.file_pane.populate(task, self._repo)
        self._update_detail_pane(task)

    def _update_detail_pane(self, task: TaskNode | None) -> None:
        """Refresh task info, lock status, and active version in the detail pane."""
        if not task:
            self.detail_pane.set_task(None, None, None)
            self.detail_pane.set_checked_out_version(None)
            return
        file_path  = self.file_pane.get_current_file()
        lock_owner: str | None = None
        if self._repo and file_path:
            lock_owner = self._repo.lfs_lock_status(file_path)
        self.detail_pane.set_task(task.name, file_path, lock_owner)
        self.detail_pane.set_checked_out_version(self.file_pane.get_active_version_name())

    # ------------------------------------------------------------------
    # Git actions (commit/push/pull)
    # ------------------------------------------------------------------

    def _on_commit_and_push(self) -> None:
        if not self._repo:
            return

        selected_task = self.task_pane.get_selected_task()
        selected_node = self.folder_pane.get_selected_node()

        if selected_task:
            scope = selected_task.path
        elif isinstance(selected_node, AssetNode):
            scope = selected_node.path
        else:
            scope = self._project.data_path if self._project else None

        changed = self._repo.changed_files(under=scope)
        if not changed:
            QMessageBox.information(self, "Nothing to commit",
                                    "No changed files in the selected scope.")
            return

        dlg = CommitDialog(parent=self)
        if dlg.exec() != CommitDialog.Accepted:
            return

        msg        = dlg.message
        has_remote = self._repo.has_remote()

        def commit_then_push():
            self._repo.stage_and_commit(changed, msg)
            if has_remote:
                self._repo.push()

        def on_success(_: str) -> None:
            self._set_status("Committed & pushed" if has_remote else "Committed", "#88cc88")
            task = self.task_pane.get_selected_task()
            if task:
                self.file_pane.populate(task, self._repo)
                self._update_detail_pane(task)

        self._run_git_async(
            commit_then_push,
            on_success=on_success,
            on_error=lambda e: QMessageBox.warning(self, "Commit & Push failed", e),
            status_msg="Committing & pushing…" if has_remote else "Committing…",
        )

    def _on_pull(self) -> None:
        if not self._repo:
            return
        if not self._repo.has_remote():
            QMessageBox.warning(self, "No remote", "This project has no remote configured.")
            return

        # Pre-flight: warn if incoming files overlap with local uncommitted changes
        incoming = self._repo.incoming_files()
        if incoming:
            local_changed = set(self._repo.changed_files())
            overlap = [f for f in incoming if f in local_changed]
            if overlap:
                names = "\n".join(f"  \u2022 {f.name}" for f in overlap)
                reply = QMessageBox.warning(
                    self,
                    "Local changes will be overwritten",
                    f"These files have uncommitted local changes and will be "
                    f"overwritten by the pull:\n\n{names}\n\nContinue?",
                    QMessageBox.Yes | QMessageBox.Cancel,  # type: ignore
                )
                if reply != QMessageBox.Yes:  # type: ignore
                    return

        self._run_git_async(
            self._repo.pull,
            on_success=self._after_pull,
            on_error=self._on_pull_error,
            status_msg="Pulling…",
        )

    def _on_pull_error(self, msg: str) -> None:
        if self._repo:
            conflicts = self._repo.conflicted_files()
            if conflicts:
                self._handle_merge_conflicts(conflicts)
                return
        QMessageBox.warning(self, "Pull failed", msg)

    def _handle_merge_conflicts(self, conflicts: list[Path]) -> None:
        from conduit.ui.dialogs.conflict_dialog import ConflictDialog
        dlg = ConflictDialog(conflicts, parent=self)
        if dlg.exec() != ConflictDialog.Accepted:
            # User chose Cancel Merge — abort and restore pre-pull state
            try:
                self._repo.abort_merge()
                self._set_status("Merge aborted", "#e8c46a")
            except GitError as e:
                QMessageBox.warning(self, "Abort failed", str(e))
            return

        try:
            for f, choice in dlg.resolutions.items():
                if choice == "ours":
                    self._repo.resolve_ours(f)
                else:
                    self._repo.resolve_theirs(f)
            self._repo.commit_merge()
            self._set_status("Conflicts resolved", "#88cc88")
            self._after_pull("")
        except GitError as e:
            QMessageBox.warning(self, "Resolution failed", str(e))

    def _after_pull(self, _: str) -> None:
        self._set_status("Pulled", "#88cc88")
        self._commits_behind = 0
        self._refresh_footer()
        if self._project:
            self._project.reload_tree()
            self.folder_pane.refresh_tree(self._project.tree)
            self.task_pane.clear()
            self.file_pane.clear()
            self.detail_pane.set_task(None, None, None)
            self.detail_pane.set_checked_out_version(None)

    # ------------------------------------------------------------------
    # Version checkout
    # ------------------------------------------------------------------

    def _on_checkout_version(self, commit_hash: str) -> None:
        file_path = self.file_pane.get_current_file()
        if not file_path or not self._repo:
            return
        try:
            self._repo.checkout_version(file_path, commit_hash)
        except GitError as e:
            QMessageBox.warning(self, "Checkout failed", str(e))
            return
        self.file_pane.refresh_header()
        self.file_pane.set_active_commit(commit_hash)
        self.detail_pane.set_checked_out_version(self.file_pane.get_active_version_name())
        self._set_status(f"Restored {commit_hash}", "#88cc88")

    # ------------------------------------------------------------------
    # Lock / Unlock / Open
    # ------------------------------------------------------------------

    def _on_lock(self) -> None:
        file_path = self.detail_pane.get_file_path()
        if not file_path or not self._repo:
            return
        try:
            self._repo.lfs_lock(file_path)
            self._set_status("File locked", "#88cc88")
        except GitError as e:
            QMessageBox.warning(self, "Lock failed", str(e))
            return
        self._update_detail_pane(self.task_pane.get_selected_task())

    def _on_unlock(self) -> None:
        file_path = self.detail_pane.get_file_path()
        if not file_path or not self._repo:
            return
        try:
            self._repo.lfs_unlock(file_path)
            self._set_status("File unlocked", "#88cc88")
        except GitError as e:
            QMessageBox.warning(self, "Unlock failed", str(e))
            return
        self._update_detail_pane(self.task_pane.get_selected_task())

    def _on_open_file(self) -> None:
        file_path = self.detail_pane.get_file_path()
        if not file_path or not file_path.exists():
            QMessageBox.information(self, "No file", "No file to open.")
            return

        if file_path.suffix.lower() == ".blend":
            enforced = self._project and self._project.config.blender_force_version
            blender_exe = self._blender_opener.get(".blend")

            if enforced and not blender_exe:
                link = self._project.config.blender_version_link or ""
                url_display = f"https://download.blender.org/release/{link}"
                reply = QMessageBox.question(
                    self,
                    "Blender Not Installed",
                    f"Blender is enforced for this project but is not installed.\n\n"
                    f"Download from:\n{url_display}\n\nDownload now?",
                    QMessageBox.Yes | QMessageBox.No,  # type: ignore
                )
                if reply == QMessageBox.Yes:  # type: ignore
                    self._open_project_settings()
                return

            if blender_exe:
                import subprocess
                subprocess.Popen([blender_exe, "--app-template", "conduit", str(file_path)])
                return

        open_file(file_path, APP_OPENERS)

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _run_git_async(self, fn, *, on_success, on_error, status_msg: str) -> None:
        self._set_status(status_msg, "#e8c46a")
        self._progress_bar.setVisible(True)
        self.detail_pane.set_repo_enabled(False)

        worker = _GitWorker(fn)
        worker.success.connect(lambda msg: self._git_done(on_success, msg))
        worker.error.connect(lambda msg: self._git_error(on_error, msg))
        self._worker = worker
        worker.start()

    def _git_done(self, on_success, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self.detail_pane.set_repo_enabled(self._repo is not None)
        self._worker = None
        on_success(msg)

    def _git_error(self, on_error, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self.detail_pane.set_repo_enabled(self._repo is not None)
        self._set_status("Error", "#f88888")
        self._worker = None
        on_error(msg)

    # ------------------------------------------------------------------
    # Projects menu actions
    # ------------------------------------------------------------------

    def _new_project(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() != NewProjectDialog.Accepted:
            return
        try:
            project = Project.create(dlg.project_path, dlg.project_name, dlg.remote_url)
            self._seed_templates(project)
            repo    = ConduitRepo.open(project.root_path)
            self.load_project(project, repo)
        except Exception as e:
            QMessageBox.warning(self, "Could not create project", str(e))

    @staticmethod
    def _seed_templates(project: Project) -> None:
        """Copy bundled default templates into the new project's template directory."""
        import shutil
        src = _bundled_templates_dir()
        if not src.is_dir():
            return
        dest = project.templates_path
        dest.mkdir(parents=True, exist_ok=True)
        for tmpl in src.iterdir():
            if tmpl.is_file():
                target = dest / tmpl.name
                if not target.exists():   # never overwrite existing templates
                    shutil.copy2(tmpl, target)

    def _open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Conduit Project")
        if not path:
            return
        self._open_project_path(Path(path))

    def _open_project_path(self, path: Path) -> None:
        try:
            project = Project.load(path)
            repo    = ConduitRepo.open(path)
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Not a Conduit project", str(e))
            return
        except GitError:
            repo = None
        self.load_project(project, repo)

    def _clone_project(self) -> None:
        dlg = CloneDialog(self)
        if dlg.exec() != CloneDialog.Accepted:
            return

        dest = dlg.dest_path
        url  = dlg.url

        def do_clone():
            ConduitRepo.clone(url, dest)

        def on_success(_: str) -> None:
            try:
                project = Project.load(dest)
                repo    = ConduitRepo.open(dest)
                self.load_project(project, repo)
            except Exception as e:
                QMessageBox.warning(self, "Could not open cloned project", str(e))

        self._run_git_async(
            do_clone,
            on_success=on_success,
            on_error=lambda msg: QMessageBox.warning(self, "Clone failed", msg),
            status_msg="Cloning…",
        )

    # ------------------------------------------------------------------
    # Context menus
    # ------------------------------------------------------------------

    def _folder_context_menu(self, pos) -> None:
        menu = QMenu(self.folder_pane.widget())
        menu.addAction("New Folder", self._add_folder)
        menu.addAction("New Asset",  self._add_asset)
        menu.addSeparator()
        menu.addAction("Show in Explorer", self._show_node_in_explorer)
        menu.exec_(self.folder_pane.widget().mapToGlobal(pos))

    def _task_context_menu(self, pos) -> None:
        menu = QMenu(self.task_pane.widget())
        menu.addAction("New Modelling Task",  lambda: self._add_task("modelling"))
        menu.addAction("New Texturing Task",  lambda: self._add_task("texturing"))
        menu.addAction("New Animation Task",  lambda: self._add_task("animation"))
        menu.addSeparator()
        menu.addAction("New Custom Task",     lambda: self._add_task(""))
        menu.exec_(self.task_pane.widget().mapToGlobal(pos))

    def _file_context_menu(self, pos) -> None:
        menu = QMenu(self.file_pane.widget())
        menu.addAction("Open in Explorer", self._open_in_explorer)
        menu.exec_(self.file_pane.widget().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Creation actions
    # ------------------------------------------------------------------

    def _add_folder(self) -> None:
        if not self._project:
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return

        selected = self.folder_pane.get_selected_node()
        if isinstance(selected, FolderNode):
            parent_path = selected.path
            parent_item = self.folder_pane.model.itemFromIndex(
                self.folder_pane.tree_view.currentIndex()
            )
        else:
            parent_path = self._project.data_path
            parent_item = None

        new_path = parent_path / name.strip()
        new_path.mkdir(parents=True, exist_ok=True)
        new_node = FolderNode(
            path=new_path,
            parent=selected if isinstance(selected, FolderNode) else None,
        )
        self.folder_pane.append_folder(parent_item, new_node)

    def _add_asset(self) -> None:
        if not self._project:
            return
        selected = self.folder_pane.get_selected_node()
        if not isinstance(selected, FolderNode):
            QMessageBox.warning(self, "Invalid Selection", "Select a Folder first.")
            return

        name, ok = QInputDialog.getText(self, "New Asset", "Asset name:")
        if not ok or not name.strip():
            return

        import json
        from conduit.model.nodes import ASSET_MARKER
        asset_path = selected.path / name.strip()
        asset_path.mkdir(parents=True, exist_ok=True)
        (asset_path / ASSET_MARKER).write_text(
            json.dumps({"version": 1}), encoding="utf-8"
        )

        new_node = AssetNode(path=asset_path, parent=selected)
        parent_item = self.folder_pane.model.itemFromIndex(
            self.folder_pane.tree_view.currentIndex()
        )
        self.folder_pane.append_asset(parent_item, new_node)

    def _add_task(self, preset_name: str) -> None:
        if not self._project:
            return
        selected = self.folder_pane.get_selected_node()
        if not isinstance(selected, AssetNode):
            QMessageBox.warning(self, "Invalid Selection", "Select an Asset first.")
            return

        if preset_name:
            name = preset_name
        else:
            name, ok = QInputDialog.getText(self, "New Task", "Task name:")
            if not ok or not name.strip():
                return
            name = name.strip()

        if name.lower() in {t.name.lower() for t in selected.tasks}:
            QMessageBox.information(self, "Duplicate", f"'{name}' already exists.")
            return

        task_path = selected.path / name
        task_path.mkdir(parents=True, exist_ok=True)

        new_task = TaskNode(path=task_path, parent=selected)
        selected.tasks.append(new_task)
        self.task_pane.append_task(new_task)

    def _on_template_picked(self, task: TaskNode, template_path: Path) -> None:
        import shutil
        asset_name = task.parent.name if task.parent else "asset"
        dest_name  = f"{asset_name}_{task.name}{template_path.suffix}"
        dest       = task.path / dest_name
        shutil.copy2(template_path, dest)
        if self._repo:
            try:
                self._repo.stage_file(dest)
            except GitError:
                pass
        self.file_pane.populate(task, self._repo)
        self._update_detail_pane(task)

    def _show_node_in_explorer(self) -> None:
        node   = self.folder_pane.get_selected_node()
        target = node.path if node else (self._project.data_path if self._project else None)
        if target:
            self._open_path(target)

    def _open_in_explorer(self) -> None:
        import subprocess
        file_path = self.file_pane.get_current_file()
        if not file_path:
            task = self.task_pane.get_selected_task()
            if task:
                self._open_path(task.path)
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{file_path}"])
        else:
            self._open_path(file_path.parent)

    @staticmethod
    def _open_path(path: Path) -> None:
        import subprocess, os
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    # ------------------------------------------------------------------
    # Toolbar stubs
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == QDialog.Accepted:
            self._fetch_timer.setInterval(self._settings.fetch_interval_minutes * 60 * 1000)

    def _open_project_settings(self) -> None:
        if not self._project:
            QMessageBox.information(self, "No Project", "Open a project first.")
            return
        dlg = ProjectSettingsDialog(self._project, self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_blender_opener()

    def _refresh_blender_opener(self) -> None:
        if self._project and self._project.config.blender_force_version:
            exe = blender_executable_for(self._project.root_path)
            self._blender_opener = {".blend": str(exe)} if exe else {}
        else:
            self._blender_opener = {}

    def _open_console(self) -> None:
        QMessageBox.information(self, "Console", "Console — coming soon.")
