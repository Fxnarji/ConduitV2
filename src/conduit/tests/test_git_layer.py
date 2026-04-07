"""Tests for conduit.git_layer.repo (ConduitRepo) and conduit.git_layer.lfs helpers.

All tests that need a real git repo use a temporary directory so they never
touch the actual ConduitV2 repository.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from conduit.git_layer.lfs import write_gitattributes, DEFAULT_LFS_PATTERNS
from conduit.git_layer.repo import (
    CommitInfo,
    ConduitRepo,
    GitError,
    MergeConflictError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git"] + args, cwd=cwd, check=True,
                   capture_output=True, text=True)


def _init_repo(path: Path, *, bare: bool = False) -> None:
    """Initialise a minimal git repo with a first commit so HEAD exists."""
    args = ["init"]
    if bare:
        args.append("--bare")
    _git(args, path)
    if not bare:
        _git(["config", "user.email", "test@example.com"], path)
        _git(["config", "user.name", "Test"], path)
        (path / "README.md").write_text("hello", encoding="utf-8")
        _git(["add", "README.md"], path)
        _git(["commit", "-m", "init"], path)


# ---------------------------------------------------------------------------
# lfs helpers
# ---------------------------------------------------------------------------

class TestWriteGitattributes:
    def test_creates_file(self, tmp_path):
        write_gitattributes(tmp_path, ["*.png", "*.blend"])
        attr = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        assert "*.png filter=lfs" in attr
        assert "*.blend filter=lfs" in attr

    def test_default_patterns_coverage(self, tmp_path):
        write_gitattributes(tmp_path, DEFAULT_LFS_PATTERNS)
        attr = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        for pattern in DEFAULT_LFS_PATTERNS:
            assert pattern in attr

    def test_overwrites_existing(self, tmp_path):
        (tmp_path / ".gitattributes").write_text("old content\n", encoding="utf-8")
        write_gitattributes(tmp_path, ["*.fbx"])
        attr = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
        assert "old content" not in attr
        assert "*.fbx" in attr


# ---------------------------------------------------------------------------
# ConduitRepo.init
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_repo(self, tmp_path):
        with patch("conduit.git_layer.repo.is_lfs_available", return_value=False):
            repo = ConduitRepo.init(tmp_path)
        assert (tmp_path / ".git").is_dir()
        assert isinstance(repo, ConduitRepo)

    def test_creates_gitignore(self, tmp_path):
        with patch("conduit.git_layer.repo.is_lfs_available", return_value=False):
            ConduitRepo.init(tmp_path)
        assert (tmp_path / ".gitignore").exists()

    def test_lfs_setup_called_when_available(self, tmp_path):
        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run, \
             patch("conduit.git_layer.repo.write_gitattributes") as mock_attrs:
            import git as gitpython
            with patch.object(gitpython.Repo, "init") as mock_init:
                mock_init.return_value = MagicMock(working_dir=str(tmp_path))
                ConduitRepo.init(tmp_path)
            mock_run.assert_any_call(
                ["git", "lfs", "install"], cwd=tmp_path.resolve(), check=True
            )
            mock_attrs.assert_called_once()


# ---------------------------------------------------------------------------
# ConduitRepo.open
# ---------------------------------------------------------------------------

class TestOpen:
    def test_opens_valid_repo(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        assert repo.path.resolve() == tmp_path.resolve()

    def test_raises_git_error_for_non_repo(self, tmp_path):
        with pytest.raises(GitError, match="No git repository found"):
            ConduitRepo.open(tmp_path)


# ---------------------------------------------------------------------------
# Remote helpers
# ---------------------------------------------------------------------------

class TestRemote:
    def _make_repo(self, tmp_path):
        _init_repo(tmp_path)
        return ConduitRepo.open(tmp_path)

    def test_has_remote_false_by_default(self, tmp_path):
        repo = self._make_repo(tmp_path)
        assert not repo.has_remote()

    def test_set_and_get_remote(self, tmp_path):
        repo = self._make_repo(tmp_path)
        repo.set_remote("https://example.com/repo.git")
        assert repo.has_remote()
        assert repo.get_remote_url() == "https://example.com/repo.git"

    def test_set_remote_updates_existing(self, tmp_path):
        repo = self._make_repo(tmp_path)
        repo.set_remote("https://first.example.com/repo.git")
        repo.set_remote("https://second.example.com/repo.git")
        assert repo.get_remote_url() == "https://second.example.com/repo.git"

    def test_get_remote_url_none_when_missing(self, tmp_path):
        repo = self._make_repo(tmp_path)
        assert repo.get_remote_url("nonexistent") is None


# ---------------------------------------------------------------------------
# stage_and_commit / stage_file
# ---------------------------------------------------------------------------

class TestCommit:
    def _make_repo(self, tmp_path):
        _init_repo(tmp_path)
        return ConduitRepo.open(tmp_path)

    def test_stage_and_commit(self, tmp_path):
        repo = self._make_repo(tmp_path)
        f = tmp_path / "file.txt"
        f.write_text("content", encoding="utf-8")
        repo.stage_and_commit(None, "add file")
        import git as gitpython
        raw = gitpython.Repo(str(tmp_path))
        assert raw.head.commit.message.strip() == "add file"

    def test_stage_and_commit_with_scope(self, tmp_path):
        repo = self._make_repo(tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.txt").write_text("content", encoding="utf-8")
        repo.stage_and_commit(sub, "add in sub")
        import git as gitpython
        raw = gitpython.Repo(str(tmp_path))
        assert raw.head.commit.message.strip() == "add in sub"

    def test_stage_and_commit_raises_on_nothing_to_commit(self, tmp_path):
        repo = self._make_repo(tmp_path)
        # Repo is clean — nothing to stage
        with pytest.raises(GitError, match="Nothing to commit"):
            repo.stage_and_commit(None, "empty commit")

    def test_stage_file_without_lfs(self, tmp_path):
        repo = self._make_repo(tmp_path)
        f = tmp_path / "asset.txt"
        f.write_text("data", encoding="utf-8")
        with patch("conduit.git_layer.repo.is_lfs_available", return_value=False):
            repo.stage_file(f)
        # file should now be in the index
        import git as gitpython
        raw = gitpython.Repo(str(tmp_path))
        staged = [e.path for e in raw.index.entries.values()]
        assert "asset.txt" in staged

    def test_stage_file_raises_for_missing_file(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with patch("conduit.git_layer.repo.is_lfs_available", return_value=False):
            with pytest.raises(GitError, match="Could not stage file"):
                repo.stage_file(tmp_path / "ghost.txt")

    def test_stage_file_raises_on_invalid_type(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with pytest.raises(GitError, match="Invalid path type"):
            repo.stage_file(None)  # type: ignore


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

class TestStatus:
    def _make_repo(self, tmp_path):
        _init_repo(tmp_path)
        return ConduitRepo.open(tmp_path)

    def test_status_clean_file(self, tmp_path):
        repo = self._make_repo(tmp_path)
        assert repo.status_of(tmp_path / "README.md") == "clean"

    def test_status_untracked_file(self, tmp_path):
        repo = self._make_repo(tmp_path)
        new = tmp_path / "new.txt"
        new.write_text("hi", encoding="utf-8")
        assert repo.status_of(new) == "untracked"

    def test_status_modified_file(self, tmp_path):
        repo = self._make_repo(tmp_path)
        readme = tmp_path / "README.md"
        readme.write_text("changed", encoding="utf-8")
        assert repo.status_of(readme) == "modified"

    def test_statuses_mixed(self, tmp_path):
        repo = self._make_repo(tmp_path)
        readme = tmp_path / "README.md"
        readme.write_text("changed", encoding="utf-8")
        new = tmp_path / "brand_new.txt"
        new.write_text("x", encoding="utf-8")
        result = repo.statuses([readme, new])
        assert result[readme] == "modified"
        assert result[new] == "untracked"

    def test_changed_files_returns_modified_and_untracked(self, tmp_path):
        repo = self._make_repo(tmp_path)
        (tmp_path / "README.md").write_text("changed", encoding="utf-8")
        new = tmp_path / "extra.txt"
        new.write_text("x", encoding="utf-8")
        changed = repo.changed_files()
        changed_names = [p.name for p in changed]
        assert "README.md" in changed_names
        assert "extra.txt" in changed_names

    def test_changed_files_filtered_by_subtree(self, tmp_path):
        repo = self._make_repo(tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()
        inside = sub / "inside.txt"
        inside.write_text("y", encoding="utf-8")
        outside = tmp_path / "outside.txt"
        outside.write_text("z", encoding="utf-8")
        changed = repo.changed_files(under=sub)
        assert all(p.is_relative_to(sub) for p in changed)
        assert any(p.name == "inside.txt" for p in changed)
        assert not any(p.name == "outside.txt" for p in changed)

    def test_changed_files_empty_when_clean(self, tmp_path):
        repo = self._make_repo(tmp_path)
        assert repo.changed_files() == []


# ---------------------------------------------------------------------------
# History / log_of
# ---------------------------------------------------------------------------

class TestHistory:
    def _make_repo_with_history(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.txt"
        f.write_text("v1", encoding="utf-8")
        _git(["add", "asset.txt"], tmp_path)
        _git(["commit", "-m", "add asset"], tmp_path)
        f.write_text("v2", encoding="utf-8")
        _git(["add", "asset.txt"], tmp_path)
        _git(["commit", "-m", "update asset"], tmp_path)
        return repo, f

    def test_log_returns_commits(self, tmp_path):
        repo, f = self._make_repo_with_history(tmp_path)
        log = repo.log_of(f)
        assert len(log) == 2

    def test_log_commit_info_fields(self, tmp_path):
        repo, f = self._make_repo_with_history(tmp_path)
        log = repo.log_of(f)
        ci = log[0]
        assert isinstance(ci, CommitInfo)
        assert len(ci.hash) == 7
        assert ci.message == "update asset"
        assert ci.author

    def test_log_respects_max_count(self, tmp_path):
        repo, f = self._make_repo_with_history(tmp_path)
        log = repo.log_of(f, max_count=1)
        assert len(log) == 1

    def test_log_empty_for_untracked_file(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        assert repo.log_of(tmp_path / "nonexistent.txt") == []


# ---------------------------------------------------------------------------
# checkout_version
# ---------------------------------------------------------------------------

class TestCheckoutVersion:
    def test_restores_file_at_commit(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "data.txt"
        f.write_text("original", encoding="utf-8")
        _git(["add", "data.txt"], tmp_path)
        _git(["commit", "-m", "first"], tmp_path)

        import git as gitpython
        first_hash = gitpython.Repo(str(tmp_path)).head.commit.hexsha

        f.write_text("modified", encoding="utf-8")
        _git(["add", "data.txt"], tmp_path)
        _git(["commit", "-m", "second"], tmp_path)

        repo.checkout_version(f, first_hash)
        assert f.read_text(encoding="utf-8") == "original"

    def test_checkout_bad_hash_raises(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with pytest.raises(GitError, match="Checkout failed"):
            repo.checkout_version(tmp_path / "README.md", "deadbeef")


# ---------------------------------------------------------------------------
# push / fetch / pull (mocked — network)
# ---------------------------------------------------------------------------

class TestPushFetchPull:
    def _make_repo(self, tmp_path):
        _init_repo(tmp_path)
        return ConduitRepo.open(tmp_path)

    def test_push_raises_git_error_on_failure(self, tmp_path):
        repo = self._make_repo(tmp_path)
        # No remote configured → push must fail
        with pytest.raises(GitError, match="Push failed"):
            repo.push()

    def test_fetch_raises_git_error_on_failure(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with pytest.raises(GitError, match="Fetch failed"):
            repo.fetch()

    def test_pull_raises_git_error_on_failure(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with pytest.raises(GitError, match="Pull failed"):
            repo.pull()

    def test_push_calls_correct_subprocess(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with patch("conduit.git_layer.repo._run") as mock_run:
            # Make rev-parse succeed so _current_branch works
            branch_result = MagicMock(stdout="main\n", returncode=0)
            push_result = MagicMock(returncode=0)
            mock_run.side_effect = [branch_result, push_result]
            repo.push("origin")
        calls = mock_run.call_args_list
        push_call = calls[1]
        assert "push" in push_call.args[0]
        assert "origin" in push_call.args[0]

    def test_fetch_calls_correct_subprocess(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.fetch("origin")
        args = mock_run.call_args.args[0]
        assert args == ["git", "fetch", "origin"]

    def test_pull_raises_merge_conflict_error(self, tmp_path):
        repo = self._make_repo(tmp_path)
        conflict_file = tmp_path / "conflict.txt"
        conflict_file.write_text("data", encoding="utf-8")

        import git as gitpython
        with patch.object(repo._repo.remote("origin") if repo.has_remote() else MagicMock(),
                          "pull", side_effect=Exception()):
            pass  # just verify MergeConflictError shape below

        with patch.object(repo._repo, "remote") as mock_remote, \
             patch.object(repo, "conflicted_files", return_value=[conflict_file]):
            import git as gitpython
            mock_remote.return_value.pull.side_effect = gitpython.GitCommandError(
                "pull", 1, stderr="conflict"
            )
            with pytest.raises(MergeConflictError) as exc_info:
                repo.pull()
            assert conflict_file in exc_info.value.conflicted


# ---------------------------------------------------------------------------
# commits_behind / incoming_files / conflicted_files
# ---------------------------------------------------------------------------

class TestDiffHelpers:
    def _make_repo(self, tmp_path):
        _init_repo(tmp_path)
        return ConduitRepo.open(tmp_path)

    def test_commits_behind_returns_zero_without_fetch(self, tmp_path):
        repo = self._make_repo(tmp_path)
        # FETCH_HEAD doesn't exist → should return 0, not raise
        assert repo.commits_behind() == 0

    def test_incoming_files_empty_without_fetch(self, tmp_path):
        repo = self._make_repo(tmp_path)
        assert repo.incoming_files() == []

    def test_conflicted_files_empty_on_clean_repo(self, tmp_path):
        repo = self._make_repo(tmp_path)
        assert repo.conflicted_files() == []

    def test_commits_behind_mocked(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(stdout="3\n", returncode=0)
            assert repo.commits_behind() == 3


# ---------------------------------------------------------------------------
# resolve_ours / resolve_theirs / abort_merge / commit_merge
# ---------------------------------------------------------------------------

class TestMergeResolution:
    def _make_repo(self, tmp_path):
        _init_repo(tmp_path)
        return ConduitRepo.open(tmp_path)

    def test_resolve_ours_calls_correct_commands(self, tmp_path):
        repo = self._make_repo(tmp_path)
        f = tmp_path / "conflict.blend"
        with patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.resolve_ours(f)
        commands = [c.args[0] for c in mock_run.call_args_list]
        assert any("--ours" in cmd for cmd in commands)
        assert any("add" in cmd for cmd in commands)

    def test_resolve_theirs_calls_correct_commands(self, tmp_path):
        repo = self._make_repo(tmp_path)
        f = tmp_path / "conflict.blend"
        with patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.resolve_theirs(f)
        commands = [c.args[0] for c in mock_run.call_args_list]
        assert any("--theirs" in cmd for cmd in commands)

    def test_abort_merge_calls_git_merge_abort(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.abort_merge()
        args = mock_run.call_args.args[0]
        assert args == ["git", "merge", "--abort"]

    def test_abort_merge_raises_on_failure(self, tmp_path):
        repo = self._make_repo(tmp_path)
        # No merge in progress
        with pytest.raises(GitError, match="Abort merge failed"):
            repo.abort_merge()

    def test_commit_merge_raises_on_no_merge(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with pytest.raises(GitError, match="Commit failed"):
            repo.commit_merge()

    def test_resolve_ours_raises_git_error_on_failure(self, tmp_path):
        repo = self._make_repo(tmp_path)
        f = tmp_path / "ghost.blend"
        with pytest.raises(GitError, match="Resolve failed"):
            repo.resolve_ours(f)

    def test_resolve_theirs_raises_git_error_on_failure(self, tmp_path):
        repo = self._make_repo(tmp_path)
        f = tmp_path / "ghost.blend"
        with pytest.raises(GitError, match="Resolve failed"):
            repo.resolve_theirs(f)


# ---------------------------------------------------------------------------
# _current_branch helper
# ---------------------------------------------------------------------------

class TestCurrentBranch:
    def test_returns_branch_name(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        branch = repo._current_branch()
        assert isinstance(branch, str)
        assert branch  # non-empty

    def test_falls_back_to_main_on_error(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with patch("conduit.git_layer.repo._run", side_effect=Exception("oops")):
            assert repo._current_branch() == "main"


# ---------------------------------------------------------------------------
# _rel helper
# ---------------------------------------------------------------------------

class TestRel:
    def test_rel_returns_relative_path(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        abs_path = tmp_path / "sub" / "file.txt"
        rel = repo._rel(abs_path)
        assert rel == Path("sub") / "file.txt"

    def test_rel_accepts_string(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        rel = repo._rel(str(tmp_path / "file.txt"))
        assert rel == Path("file.txt")

    def test_rel_raises_on_path_outside_repo(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        outside_path = Path("C:/")  # Root path is definitely outside
        with pytest.raises(GitError, match="outside repository"):
            repo._rel(outside_path)

    def test_rel_raises_on_list_input(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with pytest.raises((TypeError, AttributeError)):
            repo._rel([])  # List should not be passed


# ---------------------------------------------------------------------------
# MergeConflictError
# ---------------------------------------------------------------------------

class TestMergeConflictError:
    def test_stores_conflicted_paths(self):
        paths = [Path("/repo/a.blend"), Path("/repo/b.psd")]
        err = MergeConflictError("conflicts!", conflicted=paths)
        assert err.conflicted == paths
        assert "conflicts!" in str(err)

    def test_is_subclass_of_git_error(self):
        assert issubclass(MergeConflictError, GitError)


# ---------------------------------------------------------------------------
# ConduitRepo.clone
# ---------------------------------------------------------------------------

class TestClone:
    def test_clone_without_lfs(self, tmp_path):
        import git as gitpython
        with patch.object(gitpython.Repo, "clone_from") as mock_clone, \
             patch("conduit.git_layer.repo.is_lfs_available", return_value=False):
            mock_clone.return_value = MagicMock(working_dir=str(tmp_path / "dest"))
            repo = ConduitRepo.clone("https://example.com/repo.git", tmp_path / "dest")
            assert isinstance(repo, ConduitRepo)
            mock_clone.assert_called_once()

    def test_clone_with_lfs_install_and_pull(self, tmp_path):
        import git as gitpython
        with patch.object(gitpython.Repo, "clone_from") as mock_clone, \
             patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run:
            mock_clone.return_value = MagicMock(working_dir=str(tmp_path / "dest"))
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo = ConduitRepo.clone("https://example.com/repo.git", tmp_path / "dest")
            run_calls = [c[0][0] for c in mock_run.call_args_list]
            assert any("lfs" in c and "install" in c for c in run_calls)
            assert any("lfs" in c and "pull" in c for c in run_calls)

    def test_clone_checkout_error_raises_git_error(self, tmp_path):
        import git as gitpython
        with patch.object(gitpython.Repo, "clone_from", side_effect=gitpython.GitCommandError("clone", 1, stderr="test")):
            with pytest.raises(GitError, match="Clone failed"):
                ConduitRepo.clone("https://example.com/repo.git", tmp_path / "dest")


# ---------------------------------------------------------------------------
# stage_file with LFS
# ---------------------------------------------------------------------------

class TestStageFileLFS:
    def test_stage_file_with_lfs_tracks_pattern(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.blend"
        f.write_text("data", encoding="utf-8")

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.stage_file(f)

            run_args = [c.args[0] for c in mock_run.call_args_list]
            lfs_track_calls = [a for a in run_args if "lfs" in a and "track" in a]
            assert len(lfs_track_calls) == 1
            assert "*.blend" in lfs_track_calls[0]

    def test_stage_file_with_lfs_adds_gitattributes(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.psd"
        f.write_text("data", encoding="utf-8")
        (tmp_path / ".gitattributes").write_text("", encoding="utf-8")

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.stage_file(f)

            run_calls = [c[0][0] for c in mock_run.call_args_list]
            add_calls = [c for c in run_calls if "git" in c and "add" in c]
            assert any(".gitattributes" in c for c in add_calls)

    def test_stage_file_lfs_track_failure_is_silent(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.blend"
        f.write_text("data", encoding="utf-8")

        def run_side_effect(*args, **kwargs):
            if "lfs track" in args[0]:
                raise subprocess.CalledProcessError(1, "git lfs track")
            return MagicMock(returncode=0, stdout="")

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run", side_effect=run_side_effect):
            repo.stage_file(f)


# ---------------------------------------------------------------------------
# LFS lock/unlock/status
# ---------------------------------------------------------------------------

class TestLFSLocking:
    def test_lfs_lock_acquires_lock(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "locked.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.lfs_lock(f)

            run_args = [c.args[0] for c in mock_run.call_args_list]
            lock_calls = [a for a in run_args if "lock" in a]
            assert len(lock_calls) == 1
            assert "locked.blend" in lock_calls[0]

    def test_lfs_lock_raises_on_failure(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "locked.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run", side_effect=subprocess.CalledProcessError(1, "git lfs lock", stderr="already locked")):
            with pytest.raises(GitError, match="Lock failed"):
                repo.lfs_lock(f)

    def test_lfs_unlock_releases_lock(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "locked.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            repo.lfs_unlock(f)

            run_args = [c.args[0] for c in mock_run.call_args_list]
            unlock_calls = [a for a in run_args if "unlock" in a]
            assert len(unlock_calls) == 1
            assert "locked.blend" in unlock_calls[0]

    def test_lfs_unlock_raises_on_failure(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "locked.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run", side_effect=subprocess.CalledProcessError(1, "git lfs unlock", stderr="not locked")):
            with pytest.raises(GitError, match="Unlock failed"):
                repo.lfs_unlock(f)

    def test_lfs_lock_status_returns_locker(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="asset.blend\tjohn_doe\nother.txt\tjane\n")
            status = repo.lfs_lock_status(f)
            assert status == "john_doe"

    def test_lfs_lock_status_returns_none_when_unlocked(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="other.txt\tjohn_doe\n")
            status = repo.lfs_lock_status(f)
            assert status is None

    def test_lfs_lock_status_returns_none_when_lfs_unavailable(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=False):
            status = repo.lfs_lock_status(f)
            assert status is None

    def test_lfs_lock_status_returns_none_on_error(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        f = tmp_path / "asset.blend"

        with patch("conduit.git_layer.repo.is_lfs_available", return_value=True), \
             patch("conduit.git_layer.repo._run", side_effect=Exception("network error")):
            status = repo.lfs_lock_status(f)
            assert status is None


# ---------------------------------------------------------------------------
# is_lfs_available
# ---------------------------------------------------------------------------

class TestIsLfsAvailable:
    def test_returns_true_when_both_commands_succeed(self):
        with patch("conduit.git_layer.lfs._run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="git-lfs/3.0.0"),
                MagicMock(returncode=0, stdout="git-lfs version 3.0.0"),
            ]
            from conduit.git_layer.lfs import is_lfs_available
            assert is_lfs_available() is True

    def test_returns_false_when_git_lfs_fails(self):
        with patch("conduit.git_layer.lfs._run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            from conduit.git_layer.lfs import is_lfs_available
            assert is_lfs_available() is False

    def test_returns_false_when_standalone_fails(self):
        with patch("conduit.git_layer.lfs._run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="git-lfs/3.0.0"),
                MagicMock(returncode=1, stdout=""),
            ]
            from conduit.git_layer.lfs import is_lfs_available
            assert is_lfs_available() is False

    def test_returns_false_when_command_not_found(self):
        with patch("conduit.git_layer.lfs._run", side_effect=FileNotFoundError()):
            from conduit.git_layer.lfs import is_lfs_available
            assert is_lfs_available() is False


# ---------------------------------------------------------------------------
# Exception paths
# ---------------------------------------------------------------------------

class TestExceptionPaths:
    def test_pull_raises_on_no_remote(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with pytest.raises(GitError, match="Pull failed"):
            repo.pull()

    def test_commits_behind_returns_zero_on_exception(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with patch("conduit.git_layer.repo._run", side_effect=Exception("network")):
            assert repo.commits_behind() == 0

    def test_incoming_files_returns_empty_on_exception(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with patch("conduit.git_layer.repo._run", side_effect=Exception("network")):
            assert repo.incoming_files() == []

    def test_conflicted_files_returns_empty_on_exception(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with patch("conduit.git_layer.repo._run", side_effect=Exception("error")):
            assert repo.conflicted_files() == []

    def test_log_of_returns_empty_on_exception(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with patch.object(repo._repo, "iter_commits", side_effect=Exception("error")):
            assert repo.log_of(tmp_path / "file.txt") == []


# ---------------------------------------------------------------------------
# File size at commit
# ---------------------------------------------------------------------------
# File size at commit
# ---------------------------------------------------------------------------

class TestFileSizeAt:
    def test_file_size_at_returns_size(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)

        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if "ls-tree" in cmd:
                return MagicMock(stdout="100644 blob abc123\tfile.txt")
            if "cat-file" in cmd and "-s" in cmd:
                return MagicMock(stdout="5")
            if "cat-file" in cmd and "-p" in cmd:
                return MagicMock(stdout="hello")
            return MagicMock(stdout="")

        with patch("conduit.git_layer.repo._run", side_effect=run_side_effect):
            size = repo._file_size_at("abc123", "file.txt")
            assert size == 5

    def test_file_size_at_returns_none_for_missing_file(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with patch("conduit.git_layer.repo._run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            size = repo._file_size_at("abc123", "missing.txt")
            assert size is None

    def test_file_size_at_parses_lfs_pointer(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)

        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if "ls-tree" in cmd:
                return MagicMock(stdout="100644 blob abc123\tfile.blend")
            if "cat-file" in cmd and "-s" in cmd:
                return MagicMock(stdout="128")
            if "cat-file" in cmd and "-p" in cmd:
                return MagicMock(stdout="version https://git-lfs.github.com/spec/v1\noid sha256:abc123\nsize 1048576\n")
            return MagicMock(stdout="")

        with patch("conduit.git_layer.repo._run", side_effect=run_side_effect):
            size = repo._file_size_at("abc123", "file.blend")
            assert size == 1048576

    def test_file_size_at_returns_none_on_exception(self, tmp_path):
        _init_repo(tmp_path)
        repo = ConduitRepo.open(tmp_path)
        with patch("conduit.git_layer.repo._run", side_effect=Exception("error")):
            size = repo._file_size_at("abc123", "file.txt")
            assert size is None
