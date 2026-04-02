from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton


class ButtonsPane:
    """Git action buttons. Handlers are connected by MainWindow once the git
    layer is available; until then the buttons remain disabled."""

    def __init__(self, parent) -> None:
        self._main_window = parent
        self.group_box = QGroupBox("Git")
        layout = QVBoxLayout(self.group_box)
        layout.setContentsMargins(4, 16, 4, 4)


        layout.addStretch()
    # ------------------------------------------------------------------

    def widget(self) -> QGroupBox:
        return self.group_box


    # ------------------------------------------------------------------

    @staticmethod
    def _make_btn(label: str, layout: QVBoxLayout) -> QPushButton:
        btn = QPushButton(label)
        layout.addWidget(btn)
        return btn
