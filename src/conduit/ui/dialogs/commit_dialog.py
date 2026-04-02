from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox,
)


class CommitDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Commit")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Commit message:"))
        self._msg_edit = QLineEdit()
        self._msg_edit.setPlaceholderText("Describe your changes…")
        layout.addWidget(self._msg_edit)

        self._info = QLabel("")
        self._info.setStyleSheet("color: #f88;")
        layout.addWidget(self._info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self._msg_edit.text().strip():
            self._info.setText("Commit message is required.")
            return
        self.accept()

    @property
    def message(self) -> str:
        return self._msg_edit.text().strip()
