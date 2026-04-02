from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy, QLabel
from PySide6.QtCore import Qt


class CustomTitleBar(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._parent = parent
        self.setFixedHeight(30)
        self.setObjectName("CustomTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)

        self._title_label = QLabel(parent.windowTitle())

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # type: ignore

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(40, 30)
        self._close_btn.clicked.connect(parent.close)

        layout.addWidget(self._title_label)
        layout.addWidget(spacer)
        layout.addWidget(self._close_btn)

        self._drag_pos = None

    def set_title(self, text: str) -> None:
        self._title_label.setText(text)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:  # type: ignore
            self._drag_pos = (
                event.globalPosition().toPoint() - self._parent.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() == Qt.LeftButton:  # type: ignore
            self._parent.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
