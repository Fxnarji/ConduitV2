from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QFileDialog, QDialogButtonBox, QLabel,
)


class NewProjectDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("MyProject")

        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText("Choose a folder…")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        loc_row = QHBoxLayout()
        loc_row.addWidget(self._location_edit)
        loc_row.addWidget(browse_btn)

        self._remote_edit = QLineEdit()
        self._remote_edit.setPlaceholderText("https://github.com/user/repo.git  (optional)")

        form.addRow("Project name:", self._name_edit)
        form.addRow("Location:", loc_row)
        form.addRow("Git remote:", self._remote_edit)

        self._info = QLabel("")
        self._info.setStyleSheet("color: #f88;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(self._info)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select parent folder")
        if path:
            self._location_edit.setText(path)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            self._info.setText("Project name is required.")
            return
        if not self._location_edit.text().strip():
            self._info.setText("Location is required.")
            return
        self.accept()

    # ------------------------------------------------------------------

    @property
    def project_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def project_path(self) -> Path:
        return Path(self._location_edit.text().strip()) / self.project_name

    @property
    def remote_url(self) -> str | None:
        v = self._remote_edit.text().strip()
        return v or None
