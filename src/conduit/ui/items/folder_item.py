from pathlib import Path
from PySide6.QtGui import QStandardItem, QIcon
from conduit.model.nodes import FolderNode

_ICON_PATH = Path(__file__).parent.parent / "icons" / "folder.png"


class FolderItem(QStandardItem):
    def __init__(self, node: FolderNode) -> None:
        super().__init__(node.name)
        self.setEditable(False)
        self.setIcon(QIcon(str(_ICON_PATH)))
        self.setData(node, _ROLE)


# Qt.UserRole == 256
_ROLE = 256
