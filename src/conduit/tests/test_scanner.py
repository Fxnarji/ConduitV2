import json
import pytest
from pathlib import Path

from conduit.model.nodes import ASSET_MARKER, FolderNode, AssetNode, TaskNode, FileNode
from conduit.model.scanner import scan_data_tree, scan_task_files


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_tree(tmp_path):
    """
    00-data/
        Props/
            Sign01/          ← .conduitasset present → AssetNode
                modelling/
                    Sign01-modelling.blend
                texturing/
                    Sign01-texturing.spp
            Sign02/          ← no marker → FolderNode (plain sub-folder)
        Environment/         ← FolderNode
            Trees/           ← FolderNode (nested)
    """
    data = tmp_path / "00-data"

    # Props/Sign01 (Asset)
    modelling = data / "Props" / "Sign01" / "modelling"
    texturing = data / "Props" / "Sign01" / "texturing"
    modelling.mkdir(parents=True)
    texturing.mkdir(parents=True)
    (data / "Props" / "Sign01" / ASSET_MARKER).write_text(
        json.dumps({"version": 1}), encoding="utf-8"
    )
    (modelling / "Sign01-modelling.blend").write_bytes(b"")
    (texturing / "Sign01-texturing.spp").write_bytes(b"")

    # Props/Sign02 (plain folder)
    (data / "Props" / "Sign02").mkdir(parents=True)

    # Environment/Trees (nested folders, no assets)
    (data / "Environment" / "Trees").mkdir(parents=True)

    return tmp_path


# ---------------------------------------------------------------------------
# scan_data_tree
# ---------------------------------------------------------------------------

def test_top_level_folders(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    names = {n.name for n in tree}
    assert names == {"Props", "Environment"}


def test_all_top_nodes_are_folders(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    assert all(isinstance(n, FolderNode) for n in tree)


def test_sign01_is_asset(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    child_types = {c.name: type(c) for c in props.children}
    assert child_types["Sign01"] is AssetNode


def test_sign02_is_folder(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    child_types = {c.name: type(c) for c in props.children}
    assert child_types["Sign02"] is FolderNode


def test_asset_has_correct_tasks(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    task_names = {t.name for t in sign01.tasks}
    assert task_names == {"modelling", "texturing"}


def test_all_tasks_are_task_nodes(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    assert all(isinstance(t, TaskNode) for t in sign01.tasks)


def test_nested_folders(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    env = next(n for n in tree if n.name == "Environment")
    assert len(env.children) == 1
    assert env.children[0].name == "Trees"
    assert isinstance(env.children[0], FolderNode)


def test_parent_set_on_folder_children(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    for child in props.children:
        assert child.parent is props


def test_parent_set_on_tasks(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    for task in sign01.tasks:
        assert task.parent is sign01


def test_top_level_nodes_have_no_parent(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    for node in tree:
        assert node.parent is None


def test_skip_hidden_dirs(tmp_path):
    data = tmp_path / "00-data"
    (data / ".hidden_thing").mkdir(parents=True)
    (data / "_cache").mkdir(parents=True)
    (data / "__pycache__").mkdir(parents=True)
    (data / "visible_folder").mkdir(parents=True)
    tree = scan_data_tree(data)
    names = {n.name for n in tree}
    assert names == {"visible_folder"}


def test_asset_marker_dir_itself_not_in_tasks(sample_tree):
    """The .conduitasset file must not create a TaskNode."""
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    task_names = {t.name for t in sign01.tasks}
    assert ASSET_MARKER not in task_names


def test_nonexistent_path_raises():
    with pytest.raises(NotADirectoryError):
        scan_data_tree(Path("/this/path/does/not/exist"))


def test_empty_data_dir(tmp_path):
    data = tmp_path / "00-data"
    data.mkdir()
    assert scan_data_tree(data) == []


# ---------------------------------------------------------------------------
# scan_task_files
# ---------------------------------------------------------------------------

def test_scan_task_files_returns_file_nodes(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    modelling = next(t for t in sign01.tasks if t.name == "modelling")

    files = scan_task_files(modelling)
    assert len(files) == 1
    assert isinstance(files[0], FileNode)


def test_scan_task_files_correct_name(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    modelling = next(t for t in sign01.tasks if t.name == "modelling")

    files = scan_task_files(modelling)
    assert files[0].name == "Sign01-modelling.blend"


def test_scan_task_files_default_status(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    modelling = next(t for t in sign01.tasks if t.name == "modelling")

    files = scan_task_files(modelling)
    assert files[0].git_status == "unknown"


def test_scan_task_files_parent_is_task(sample_tree):
    tree = scan_data_tree(sample_tree / "00-data")
    props = next(n for n in tree if n.name == "Props")
    sign01 = next(c for c in props.children if c.name == "Sign01")
    modelling = next(t for t in sign01.tasks if t.name == "modelling")

    files = scan_task_files(modelling)
    assert files[0].parent is modelling


def test_scan_task_files_skips_hidden(tmp_path):
    task_dir = tmp_path / "modelling"
    task_dir.mkdir()
    (task_dir / "real.blend").write_bytes(b"")
    (task_dir / ".hidden_file").write_bytes(b"")

    from conduit.model.nodes import TaskNode
    task = TaskNode(path=task_dir)
    files = scan_task_files(task)
    names = {f.name for f in files}
    assert "real.blend" in names
    assert ".hidden_file" not in names


def test_scan_task_files_empty_dir(tmp_path):
    task_dir = tmp_path / "empty_task"
    task_dir.mkdir()
    from conduit.model.nodes import TaskNode
    task = TaskNode(path=task_dir)
    assert scan_task_files(task) == []
