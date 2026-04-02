from pathlib import Path
from conduit.model.nodes import (
    BaseNode,
    FolderNode,
    AssetNode,
    TaskNode,
    FileNode,
    ASSET_MARKER,
)


def test_asset_marker_value():
    assert ASSET_MARKER == ".conduitasset"


def test_folder_node_name():
    node = FolderNode(path=Path("/project/00-data/Props"))
    assert node.name == "Props"


def test_asset_node_name():
    node = AssetNode(path=Path("/project/00-data/Props/Sign01"))
    assert node.name == "Sign01"


def test_task_node_name():
    asset = AssetNode(path=Path("/p/00-data/Props/Sign01"))
    task = TaskNode(path=Path("/p/00-data/Props/Sign01/modelling"), parent=asset)
    assert task.name == "modelling"


def test_file_node_extension_lowercase():
    node = FileNode(path=Path("/some/Sign01-modelling.BLEND"))
    assert node.extension == ".blend"


def test_file_node_default_status():
    node = FileNode(path=Path("/some/file.blend"))
    assert node.git_status == "unknown"


def test_parent_reference_preserved():
    asset = AssetNode(path=Path("/p/00-data/Props/Sign01"))
    task = TaskNode(path=Path("/p/00-data/Props/Sign01/modelling"), parent=asset)
    file = FileNode(path=Path("/p/00-data/Props/Sign01/modelling/sign.blend"), parent=task)
    assert task.parent is asset
    assert file.parent is task


def test_folder_children_default_empty():
    folder = FolderNode(path=Path("/p/00-data/Props"))
    assert folder.children == []


def test_asset_tasks_default_empty():
    asset = AssetNode(path=Path("/p/00-data/Props/Sign01"))
    assert asset.tasks == []


def test_task_files_default_empty():
    task = TaskNode(path=Path("/p/00-data/Props/Sign01/modelling"))
    assert task.files == []


def test_repr_contains_class_and_name():
    node = FolderNode(path=Path("/p/00-data/Environment"))
    assert "FolderNode" in repr(node)
    assert "Environment" in repr(node)
