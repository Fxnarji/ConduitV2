from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QTreeView
from PySide6.QtGui import QStandardItemModel
from PySide6.QtCore import Qt

from conduit.model.nodes import FolderNode, AssetNode
from conduit.ui.items import FolderItem, AssetItem


class DeselectableTreeView(QTreeView):
    """QTreeView that clears the selection when clicking empty space."""

    def mousePressEvent(self, event) -> None:
        index = self.indexAt(event.pos())
        if not index.isValid():
            self.clearSelection()
            self.setCurrentIndex(self.model().index(-1, -1))
        super().mousePressEvent(event)


class FolderPane:
    def __init__(self) -> None:
        self.group_box = QGroupBox("Folders")
        layout = QVBoxLayout(self.group_box)
        layout.setContentsMargins(4, 16, 4, 4)

        self.tree_view = DeselectableTreeView()
        self.tree_view.setSelectionMode(QTreeView.SingleSelection)   # type: ignore
        self.tree_view.setSelectionBehavior(QTreeView.SelectRows)    # type: ignore
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setAnimated(True)

        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)

        layout.addWidget(self.tree_view)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def widget(self) -> QGroupBox:
        return self.group_box

    def get_selected_node(self) -> FolderNode | AssetNode | None:
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            return None
        item = self.model.itemFromIndex(indexes[0])
        return item.data(Qt.UserRole)  # type: ignore

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def refresh_tree(self, nodes: list[FolderNode | AssetNode]) -> None:
        """Clear the model and rebuild it from a list of top-level nodes."""
        self.model.clear()
        root = self.model.invisibleRootItem()
        self._populate(root, nodes)

    def _populate(self, parent_item, nodes: list) -> None:
        for node in nodes:
            if isinstance(node, AssetNode):
                item = AssetItem(node)
                parent_item.appendRow(item)
            elif isinstance(node, FolderNode):
                item = FolderItem(node)
                parent_item.appendRow(item)
                self._populate(item, node.children)

    # ------------------------------------------------------------------
    # Incremental helpers (used by MainWindow when creating nodes)
    # ------------------------------------------------------------------

    def append_asset(self, parent_item, node: AssetNode) -> None:
        item = AssetItem(node)
        parent_item.appendRow(item)
        self.tree_view.expand(parent_item.index())
        self.tree_view.setCurrentIndex(item.index())

    def append_folder(self, parent_item, node: FolderNode) -> None:
        item = FolderItem(node)
        if parent_item:
            parent_item.appendRow(item)
        else:
            self.model.invisibleRootItem().appendRow(item)
