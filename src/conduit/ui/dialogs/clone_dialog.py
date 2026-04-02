from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QFileDialog, QDialogButtonBox, QLabel,
)


class CloneDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Clone Project")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://github.com/user/repo.git")

        self._dest_edit = QLineEdit()
        self._dest_edit.setPlaceholderText("Choose destination folder…")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        dest_row = QHBoxLayout()
        dest_row.addWidget(self._dest_edit)
        dest_row.addWidget(browse_btn)

        form.addRow("Repository URL:", self._url_edit)
        form.addRow("Clone into:", dest_row)

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
        path = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if path:
            self._dest_edit.setText(path)

    def _on_accept(self) -> None:
        if not self._url_edit.text().strip():
            self._info.setText("Repository URL is required.")
            return
        if not self._dest_edit.text().strip():
            self._info.setText("Destination folder is required.")
            return
        self.accept()

    # ------------------------------------------------------------------

    @property
    def url(self) -> str:
        return self._url_edit.text().strip()

    @property
    def dest_path(self) -> Path:
        dest = Path(self._dest_edit.text().strip())
        repo_name = self.url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        dest = dest / repo_name
        return dest
