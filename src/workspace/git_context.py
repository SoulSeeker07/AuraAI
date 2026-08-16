"""
Git Context
Location: src/workspace/git_context.py

Provides git repository information and status with TTL-cached queries.
Features:
- Get repository info (branch, remote, commit hash, dirty status)
- Get modified files and uncommitted changes
- Get recent commits and git diffs
- Thread-safe, non-blocking asynchronous APIs with 30s TTL caching
"""

import asyncio
import logging
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

from .models import GitRepository

logger = logging.getLogger(__name__)


class GitContext:
    """
    Provides git repository information and status.

    Features:
    - Get repository info (branch, remote, commit hash)
    - Get modified files
    - Get uncommitted changes
    - Get recent commits
    - Get git diff for specific files
    """

    def __init__(self, cache_ttl_seconds: int = 30):
        """Initialize git context with valid timedelta TTL and thread-safe lock."""
        self._cache: dict = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._lock = threading.Lock()

    def get_git_repo_sync(self, path: str | None = None) -> GitRepository | None:
        """
        Synchronously get git repository information for a path.

        Args:
            path: Path to git repository. If None, uses current directory.

        Returns:
            GitRepository object or None if not in git repo
        """
        try:
            # Determine path
            if path:
                repo_path = Path(path).resolve()
            else:
                repo_path = Path.cwd().resolve()

            cache_key = str(repo_path)
            with self._lock:
                if cache_key in self._cache:
                    cached_result, cached_time = self._cache[cache_key]
                    if datetime.now() - cached_time < self._cache_ttl:
                        return cached_result

            # Check if it's a git repository
            if not self._is_git_repo(repo_path):
                return None

            # Get repository information
            repo = GitRepository(path=str(repo_path))

            # Get branch
            try:
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                repo.branch = branch_result.stdout.strip()
            except Exception as e:
                logger.debug(f"Failed to get branch: {e}")
                repo.branch = "unknown"

            # Get remote URL
            try:
                remote_result = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                repo.remote_url = remote_result.stdout.strip()
            except Exception as e:
                logger.debug(f"Failed to get remote URL: {e}")

            # Get commit hash
            try:
                commit_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                repo.commit_hash = commit_result.stdout.strip()
            except Exception as e:
                logger.debug(f"Failed to get commit hash: {e}")

            # Get modified files count & status
            try:
                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                lines = [l for l in status_result.stdout.strip().split("\n") if l]
                repo.uncommitted_changes = len(lines)
                repo.modified_files = [l[3:].strip() for l in lines]
            except Exception as e:
                logger.debug(f"Failed to get modified files: {e}")

            # Cache the result under lock
            with self._lock:
                self._cache[cache_key] = (repo, datetime.now())
            return repo

        except Exception as e:
            logger.error(f"Failed to get git repo info: {e}")
            return None

    async def get_git_repo(self, path: str | None = None) -> GitRepository | None:
        """Asynchronously get git repository information without blocking."""
        return await asyncio.to_thread(self.get_git_repo_sync, path)

    def get_recent_commits_sync(
        self, path: str | None = None, count: int = 5
    ) -> list[dict]:
        """Synchronously retrieve recent commits."""
        try:
            if path:
                repo_path = Path(path).resolve()
            else:
                repo_path = Path.cwd().resolve()

            cache_key = f"{repo_path}:{count}"
            with self._lock:
                if cache_key in self._cache:
                    cached_result, cached_time = self._cache[cache_key]
                    if datetime.now() - cached_time < self._cache_ttl:
                        return cached_result

            if not self._is_git_repo(repo_path):
                return []

            result = subprocess.run(
                ["git", "log", "--oneline", "-n", str(count)],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=5,
            )

            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.strip().split(maxsplit=1)
                    commit_hash = parts[0][:7]
                    commit_message = parts[1] if len(parts) > 1 else ""
                    commits.append({"hash": commit_hash, "message": commit_message})

            with self._lock:
                self._cache[cache_key] = (commits, datetime.now())
            return commits

        except Exception as e:
            logger.error(f"Failed to get recent commits: {e}")
            return []

    async def get_recent_commits(
        self, path: str | None = None, count: int = 5
    ) -> list[dict]:
        """Asynchronously retrieve recent commits."""
        return await asyncio.to_thread(self.get_recent_commits_sync, path, count)

    def _is_git_repo(self, path: Path) -> bool:
        """Check if a path is a git repository."""
        try:
            if (path / ".git").exists() and (path / ".git").is_dir():
                return True
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def get_current_branch(self, path: str | None = None) -> str | None:
        """Get current branch name."""
        repo = await self.get_git_repo(path)
        return repo.branch if repo else None

    async def get_uncommitted_changes(self, path: str | None = None) -> int:
        """Get count of uncommitted changes."""
        repo = await self.get_git_repo(path)
        return repo.uncommitted_changes if repo else 0

    async def get_remote_url(self, path: str | None = None) -> str | None:
        """Get remote repository URL."""
        repo = await self.get_git_repo(path)
        return repo.remote_url if repo else None

    async def get_commit_hash(self, path: str | None = None) -> str | None:
        """Get current commit hash."""
        repo = await self.get_git_repo(path)
        return repo.commit_hash if repo else None

    async def get_repo_name(self, path: str | None = None) -> str | None:
        """Get repository name from path."""
        repo = await self.get_git_repo(path)
        return repo.repo_name if repo else None

    def clear_cache(self):
        """Clear the git context cache."""
        with self._lock:
            self._cache.clear()
        logger.debug("Git context cache cleared")

    def cleanup(self):
        """Clean up resources."""
        self.clear_cache()
