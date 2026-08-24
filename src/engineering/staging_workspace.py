"""
Staging Workspace & Concurrency Lock Manager
Location: src/engineering/staging_workspace.py

Manages isolated staging workspaces, Git branch creation, and OS-level atomic
concurrency locking to ensure single-task-at-a-time execution.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class RepositoryLockError(Exception):
    """Raised when an autonomous task cannot acquire the exclusive repository lock."""
    pass


class StagingWorkspace:
    """
    Manages the lifecycle of an isolated engineering staging workspace.
    """

    def __init__(
        self,
        task_id: str,
        repo_root: str | Path | None = None,
        staging_parent: str | Path | None = None,
    ):
        self.task_id = task_id
        self.repo_root = Path(repo_root or os.getcwd()).resolve()
        self.staging_dir = Path(staging_parent or (self.repo_root / ".aura_staging")).resolve()
        self.task_staging_path = self.staging_dir / f"task_{self.task_id}"
        self.lock_file_path = self.staging_dir / ".lock"
        self.branch_name = f"aura/task-{self.task_id}"
        
        self._lock_fd: int | None = None
        self._is_locked = False

    def acquire_lock(self, timeout_seconds: float = 2.0) -> None:
        """
        Acquire an exclusive OS-level atomic lock on the repository staging area.
        Prevents concurrent autonomous tasks from colliding.
        """
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Open lock file with read/write access
            fd = os.open(str(self.lock_file_path), os.O_RDWR | os.O_CREAT, 0o666)
            if sys.platform == "win32":
                try:
                    # Non-blocking lock (LK_NBLCK) on byte 0
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                except (IOError, OSError) as exc:
                    os.close(fd)
                    raise RepositoryLockError(
                        f"Failed to acquire exclusive repository lock ({self.lock_file_path}): another engineering task is active."
                    ) from exc
            else:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (IOError, OSError) as exc:
                    os.close(fd)
                    raise RepositoryLockError(
                        f"Failed to acquire exclusive repository lock: {exc}"
                    ) from exc
            
            self._lock_fd = fd
            self._is_locked = True
        except RepositoryLockError:
            raise
        except Exception as exc:
            raise RepositoryLockError(f"Unexpected error acquiring repository lock: {exc}") from exc

    def release_lock(self) -> None:
        """Release the OS-level atomic repository lock."""
        if self._is_locked and self._lock_fd is not None:
            try:
                if sys.platform == "win32":
                    try:
                        msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    try:
                        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                os.close(self._lock_fd)
            except Exception:
                pass
            finally:
                self._lock_fd = None
                self._is_locked = False

    def prepare_staging(self) -> Path:
        """
        Create task staging workspace directory.
        """
        if not self._is_locked:
            self.acquire_lock()
        self.task_staging_path.mkdir(parents=True, exist_ok=True)
        return self.task_staging_path

    def cleanup_staging(self) -> None:
        """Clean up task staging files and release lock."""
        try:
            if self.task_staging_path.exists():
                shutil.rmtree(self.task_staging_path, ignore_errors=True)
        finally:
            self.release_lock()

    def __enter__(self) -> StagingWorkspace:
        self.prepare_staging()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup_staging()


__all__ = [
    "StagingWorkspace",
    "RepositoryLockError",
]
