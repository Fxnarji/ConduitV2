import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import git

from .lfs import DEFAULT_LFS_PATTERNS, _run, is_lfs_available, write_gitattributes
from conduit.model.ignore import GITIGNORE_PATTERNS


@dataclass
class CommitInfo:
    hash: str
    author: str
    date: datetime
    message: str
    file_size: int | None = None  # bytes; None if unknown or file deleted in that commit


class GitError(Exception):
    """User-facing git error. The message is shown directly in the UI."""


class MergeConflictError(GitError):
    """Raised when a pull results in binary merge conflicts needing manual resolution."""

    def __init__(self, message: str, conflicted: list[Path]) -> None:
        super().__init__(message)
        self.conflicted: list[Path] = conflicted


class ConduitRepo:

    def __init__(self, repo: git.Repo) -> None:
        self._repo = repo

    @property
    def path(self) -> Path:
        return Path(self._repo.working_dir)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def init(cls, path: Path, lfs_patterns: list[str] | None = None) -> "ConduitRepo":
        """Initialise a new git repo and optionally set up LFS."""
        path = path.resolve()
        repo = git.Repo.init(str(path))

        if is_lfs_available():
            _run(["git", "lfs", "install"], cwd=path, check=True)
            write_gitattributes(path, lfs_patterns or DEFAULT_LFS_PATTERNS)

        gitignore_content = "\n".join(GITIGNORE_PATTERNS) + "\n"
        (path / ".gitignore").write_text(gitignore_content, encoding="utf-8")
        return cls(repo)

    @classmethod
    def open(cls, path: Path) -> "ConduitRepo":
        """Open an existing git repository."""
        try:
            repo = git.Repo(str(path), search_parent_directories=True)
            return cls(repo)
        except git.InvalidGitRepositoryError:
            raise GitError(f"No git repository found at:\n{path}")

    @classmethod
    def clone(cls, url: str, dest: Path) -> "ConduitRepo":
        """Clone a remote repository to dest."""
        try:
            repo = git.Repo.clone_from(url, str(dest))
            repo.git.checkout("master")
        except git.GitCommandError as e:
            raise GitError(f"Clone failed:\n{e.stderr.strip()}") from e

        if is_lfs_available():
            try:
                _run(["git", "lfs", "install"], cwd=dest, check=True)
                _run(["git", "lfs", "pull"], cwd=dest, check=True)
            except subprocess.CalledProcessError:
                pass

        return cls(repo)

    # ------------------------------------------------------------------
    # Remote
    # ------------------------------------------------------------------

    def set_remote(self, url: str, name: str = "origin") -> None:
        if name in [r.name for r in self._repo.remotes]:
            self._repo.remotes[name].set_url(url)
        else:
            self._repo.create_remote(name, url)

    def get_remote_url(self, name: str = "origin") -> str | None:
        for r in self._repo.remotes:
            if r.name == name:
                return next(r.urls, None)
        return None

    def has_remote(self, name: str = "origin") -> bool:
        return name in [r.name for r in self._repo.remotes]

    # ------------------------------------------------------------------
    # Commit / Push / Pull
    # ------------------------------------------------------------------

    def stage_and_commit(self, scope: Path | None, message: str) -> None:
        """Stage all changes within *scope* (or the whole repo if None) and commit.

        Uses the scope directory as the git working directory so that path
        encoding — including special characters like brackets — is handled
        entirely by git rather than by Python path manipulation.
        """
        work_dir = scope.resolve() if scope else self.path.resolve()
        try:
            _run(["git", "add", "--", "."], cwd=work_dir, check=True)
            staged = _run(["git", "diff", "--cached", "--quiet"], cwd=self.path)
            if staged.returncode == 0:
                raise GitError("Nothing to commit")
            _run(["git", "commit", "-m", message], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Commit failed:\n{(e.stderr or '').strip()}") from e

    def stage_file(self, file_path: Path) -> None:
        """Ensure the file's extension is LFS-tracked, then stage the file.

        Safe to call even when LFS is not installed — falls back to plain staging.
        """
        if not isinstance(file_path, Path):
            raise GitError(f"Invalid path type: {type(file_path).__name__}")
        if is_lfs_available() and file_path.suffix:
            pattern = f"*{file_path.suffix.lower()}"
            try:
                _run(["git", "lfs", "track", pattern], cwd=self.path, check=True)
                gitattributes = self.path / ".gitattributes"
                if gitattributes.exists():
                    _run(["git", "add", "--", self._rel(gitattributes).as_posix()], cwd=self.path, check=True)
            except subprocess.CalledProcessError:
                pass

        try:
            _run(["git", "add", "--", self._rel(file_path).as_posix()], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Could not stage file:\n{(e.stderr or '').strip()}") from e

    def push(self, remote: str = "origin") -> None:
        try:
            branch = self._current_branch()
            _run(["git", "push", remote, f"{branch}:{branch}"], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Push failed:\n{(e.stderr or '').strip()}") from e

    def fetch(self, remote: str = "origin") -> None:
        """Download remote refs without touching the working tree."""
        try:
            _run(["git", "fetch", remote], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Fetch failed:\n{(e.stderr or '').strip()}") from e

    def pull(self, remote: str = "origin") -> None:
        try:
            self._repo.remote(remote).pull()
        except ValueError as e:
            raise GitError(f"Pull failed:\n{e}") from e
        except git.GitCommandError as e:
            conflicts = self.conflicted_files()
            if conflicts:
                raise MergeConflictError(
                    "Pull resulted in merge conflicts that need resolution.",
                    conflicted=conflicts,
                ) from e
            raise GitError(f"Pull failed:\n{e.stderr.strip()}") from e

    def commits_behind(self) -> int:
        """Number of commits on FETCH_HEAD not yet in HEAD (0 if unknown)."""
        try:
            result = _run(["git", "rev-list", "HEAD..FETCH_HEAD", "--count"], cwd=self.path)
            return int(result.stdout.strip() or "0")
        except Exception:
            return 0

    def incoming_files(self) -> list[Path]:
        """Files that will change when FETCH_HEAD is merged into HEAD.

        Returns an empty list when FETCH_HEAD doesn't exist yet (no fetch run).
        """
        try:
            result = _run(["git", "diff", "--name-only", "HEAD...FETCH_HEAD"], cwd=self.path)
            return [
                self.path / line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]
        except Exception:
            return []

    def conflicted_files(self) -> list[Path]:
        """Files currently in a merge conflict state (unmerged)."""
        try:
            result = _run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=self.path)
            return [
                self.path / line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]
        except Exception:
            return []

    def resolve_ours(self, file_path: Path) -> None:
        """Resolve a binary merge conflict by keeping the local (ours) version."""
        rel = self._rel(file_path).as_posix()
        try:
            _run(["git", "checkout", "--ours", "--", rel], cwd=self.path, check=True)
            _run(["git", "add", "--", rel], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Resolve failed:\n{(e.stderr or '').strip()}") from e

    def resolve_theirs(self, file_path: Path) -> None:
        """Resolve a binary merge conflict by taking the remote (theirs) version."""
        rel = self._rel(file_path).as_posix()
        try:
            _run(["git", "checkout", "--theirs", "--", rel], cwd=self.path, check=True)
            _run(["git", "add", "--", rel], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Resolve failed:\n{(e.stderr or '').strip()}") from e

    def abort_merge(self) -> None:
        """Abort an in-progress merge, restoring the pre-pull state."""
        try:
            _run(["git", "merge", "--abort"], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Abort merge failed:\n{(e.stderr or '').strip()}") from e

    def commit_merge(self) -> None:
        """Finalise a resolved merge with an automatic commit."""
        try:
            _run(["git", "commit", "-m", "Resolve merge conflict (binary)"], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Commit failed:\n{(e.stderr or '').strip()}") from e

    def checkout_version(self, file_path: Path, commit_hash: str) -> None:
        """Restore the working-tree file to its state at *commit_hash*.

        For LFS-tracked files git will invoke the smudge filter automatically,
        downloading the correct object from the LFS server if needed.
        """
        rel = self._rel(file_path).as_posix()
        try:
            _run(["git", "checkout", commit_hash, "--", rel], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Checkout failed:\n{(e.stderr or '').strip()}") from e

    # ------------------------------------------------------------------
    # LFS locking
    # ------------------------------------------------------------------

    def lfs_lock_status(self, file_path: Path) -> str | None:
        """Return the locker's username if the file is LFS-locked, else None.

        Queries the LFS server; may be slow on high-latency connections.
        Returns None when LFS is unavailable or on any error.
        """
        if not is_lfs_available():
            return None
        rel = self._rel(file_path).as_posix()
        try:
            result = _run(["git", "lfs", "locks"], cwd=self.path)
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2 and parts[0].strip() == rel:
                    return parts[1].strip()
        except Exception:
            pass
        return None

    def lfs_lock(self, file_path: Path) -> None:
        """Acquire an LFS lock on *file_path*."""
        rel = self._rel(file_path).as_posix()
        try:
            _run(["git", "lfs", "lock", rel], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Lock failed:\n{(e.stderr or '').strip()}") from e

    def lfs_unlock(self, file_path: Path) -> None:
        """Release an LFS lock on *file_path*."""
        rel = self._rel(file_path).as_posix()
        try:
            _run(["git", "lfs", "unlock", rel], cwd=self.path, check=True)
        except subprocess.CalledProcessError as e:
            raise GitError(f"Unlock failed:\n{(e.stderr or '').strip()}") from e

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status_of(self, file_path: Path) -> str:
        rel = self._rel(file_path).as_posix()

        if rel in self._repo.untracked_files:
            return "untracked"

        for d in self._repo.index.diff(None):       # unstaged
            if d.a_path == rel:
                return "modified"

        try:
            for d in self._repo.index.diff("HEAD"): # staged
                if d.a_path == rel or d.b_path == rel:
                    return "modified"
        except Exception:
            pass

        return "clean"

    def statuses(self, paths: list[Path]) -> dict[Path, str]:
        """Return {path: status} for a list of file paths."""
        untracked = set(self._repo.untracked_files)

        modified: set[str] = set()
        for d in self._repo.index.diff(None):
            modified.add(d.a_path)
        try:
            for d in self._repo.index.diff("HEAD"):
                modified.add(d.a_path)
                if d.b_path:
                    modified.add(d.b_path)
        except Exception:
            pass

        result: dict[Path, str] = {}
        for p in paths:
            rel = self._rel(p).as_posix()
            if rel in untracked:
                result[p] = "untracked"
            elif rel in modified:
                result[p] = "modified"
            else:
                result[p] = "clean"
        return result

    def changed_files(self, under: Path | None = None) -> list[Path]:
        """All modified/untracked files, optionally filtered to a subtree."""
        repo_root = self.path.resolve()

        untracked = {repo_root / p for p in self._repo.untracked_files}

        modified: set[Path] = set()
        for d in self._repo.index.diff(None):
            modified.add(repo_root / d.a_path)
        try:
            for d in self._repo.index.diff("HEAD"):
                modified.add(repo_root / d.a_path)
        except Exception:
            pass

        all_changed = [
            p for p in untracked | modified
            if p.is_absolute() and p.resolve().is_relative_to(repo_root)
        ]

        if under:
            import os
            under = Path(os.path.normpath(str(under))).resolve()
            all_changed = [p for p in all_changed if p.is_relative_to(under)]

        return sorted(all_changed)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def log_of(self, file_path: Path, max_count: int = 50) -> list[CommitInfo]:
        rel = self._rel(file_path)
        rel_posix = rel.as_posix()
        try:
            commits = list(self._repo.iter_commits(paths=str(rel), max_count=max_count))
        except Exception:
            return []
        return [
            CommitInfo(
                hash=c.hexsha[:7],
                author=str(c.author),
                date=datetime.fromtimestamp(c.committed_date),
                message=c.message.strip(),
                file_size=self._file_size_at(c.hexsha, rel_posix),
            )
            for c in commits
        ]

    def _file_size_at(self, commit_hash: str, rel_posix: str) -> int | None:
        """Return the file's byte-size as stored at *commit_hash*.

        For LFS-tracked files the pointer is parsed to extract the real size.
        For regular blobs the raw blob size is returned.
        Returns None if the file didn't exist in that commit or on any error.
        """
        try:
            ls = _run(["git", "ls-tree", commit_hash, "--", rel_posix], cwd=self.path)
            line = ls.stdout.strip()
            if not line:
                return None
            blob_hash = line.split()[2]

            size_out = _run(["git", "cat-file", "-s", blob_hash], cwd=self.path)
            blob_size = int(size_out.stdout.strip())

            if blob_size < 512:
                ptr = _run(["git", "cat-file", "-p", blob_hash], cwd=self.path).stdout
                if "git-lfs" in ptr:
                    for ptr_line in ptr.splitlines():
                        if ptr_line.startswith("size "):
                            return int(ptr_line[5:])

            return blob_size
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rel(self, path: Path | str) -> Path:
        if isinstance(path, str):
            path = Path(path)
        if not path.is_absolute():
            raise GitError(
                f"Internal error — relative path passed to _rel():\n"
                f"  path: {path!r}\n"
                f"  (expected an absolute path inside {self.path!r})"
            )
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.path.resolve())
        except ValueError:
            raise GitError(
                f"Path is outside repository:\n"
                f"  path: {path!r}\n"
                f"  resolved: {resolved!r}\n"
                f"  repo: {self.path!r}"
            )

    def _current_branch(self) -> str:
        try:
            result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=self.path)
            return result.stdout.strip() or "main"
        except Exception:
            return "main"
