"""
Git Context

Provides git repository information and status.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import json

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

    def __init__(self):
        """Initialize git context"""
        self._cache: dict = {}
        self._cache_ttl = 30  # Cache for 30 seconds

    async def get_git_repo(self, path: Optional[str] = None) -> Optional[GitRepository]:
        """
        Get git repository information for a path.

        Args:
            path: Path to git repository. If None, uses current directory.

        Returns:
            GitRepository object or None if not in git repo
        """
        try:
            # Use cache if available
            cache_key = path or str(Path.cwd().resolve())
            if cache_key in self._cache:
                cached_result, cached_time = self._cache[cache_key]
                if datetime.now() - cached_time < self._cache_ttl:
                    return cached_result

            # Determine path
            if path:
                repo_path = Path(path).resolve()
            else:
                repo_path = Path.cwd().resolve()

            # Check if it's a git repository
            if not self._is_git_repo(repo_path):
                return None

            # Get repository information
            repo = GitRepository(path=str(repo_path))

            # Get branch
            try:
                branch_result = subprocess.run(
                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                repo.branch = branch_result.stdout.strip()
            except Exception as e:
                logger.debug(f"Failed to get branch: {e}")
                repo.branch = 'unknown'

            # Get remote URL
            try:
                remote_result = subprocess.run(
                    ['git', 'config', '--get', 'remote.origin.url'],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                repo.remote_url = remote_result.stdout.strip()
            except Exception as e:
                logger.debug(f"Failed to get remote URL: {e}")

            # Get commit hash
            try:
                commit_result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                repo.commit_hash = commit_result.stdout.strip()[:7]
            except Exception as e:
                logger.debug(f"Failed to get commit hash: {e}")

            # Get modified files
            try:
                status_result = subprocess.run(
                    ['git', 'status', '--porcelain'],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                repo.modified_files = []
                for line in status_result.stdout.strip().split('\n'):
                    if line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            repo.modified_files.append(parts[1])
                repo.uncommitted_changes = len(repo.modified_files)
                repo.is_dirty = len(repo.modified_files) > 0
            except Exception as e:
                logger.debug(f"Failed to get modified files: {e}")
                repo.is_dirty = False

            # Cache the result
            self._cache[cache_key] = (repo, datetime.now())
            logger.debug(f"Git repository detected: {repo.branch} at {repo_path}")

            return repo

        except Exception as e:
            logger.error(f"Failed to get git repository: {e}")
            return None

    async def get_modified_files(self, path: Optional[str] = None) -> List[str]:
        """
        Get list of modified files in repository.

        Args:
            path: Path to repository. If None, uses current directory.

        Returns:
            List of modified file paths
        """
        try:
            repo = await self.get_git_repo(path)
            if repo:
                return repo.modified_files
            return []
        except Exception as e:
            logger.error(f"Failed to get modified files: {e}")
            return []

    async def get_uncommitted_changes(self, path: Optional[str] = None) -> int:
        """
        Get count of uncommitted changes.

        Args:
            path: Path to repository. If None, uses current directory.

        Returns:
            Number of uncommitted changes
        """
        try:
            repo = await self.get_git_repo(path)
            if repo:
                return repo.uncommitted_changes
            return 0
        except Exception as e:
            logger.error(f"Failed to get uncommitted changes: {e}")
            return 0

    async def get_recent_commits(self, path: Optional[str] = None, count: int = 5) -> List[dict]:
        """
        Get recent commit history.

        Args:
            path: Path to repository. If None, uses current directory.
            count: Number of commits to retrieve.

        Returns:
            List of commit dictionaries
        """
        try:
            # Use cache
            cache_key = f"{path}:{count}" if path else f"cwd:{count}"
            if cache_key in self._cache:
                cached_result, cached_time = self._cache[cache_key]
                if datetime.now() - cached_time < self._cache_ttl:
                    return cached_result

            # Determine path
            if path:
                repo_path = Path(path).resolve()
            else:
                repo_path = Path.cwd().resolve()

            # Check if it's a git repository
            if not self._is_git_repo(repo_path):
                return []

            # Get recent commits
            try:
                result = subprocess.run(
                    ['git', 'log', '--oneline', '-n', str(count)],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                commits = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        # Format: "hash message"
                        parts = line.strip().split(maxsplit=1)
                        commit_hash = parts[0][:7]
                        commit_message = parts[1] if len(parts) > 1 else ''

                        commits.append({
                            'hash': commit_hash,
                            'message': commit_message
                        })

                # Cache the result
                self._cache[cache_key] = (commits, datetime.now())
                return commits

            except Exception as e:
                logger.debug(f"Failed to get recent commits: {e}")
                return []

        except Exception as e:
            logger.error(f"Failed to get recent commits: {e}")
            return []

    async def get_current_branch(self, path: Optional[str] = None) -> Optional[str]:
        """
        Get current branch name.

        Args:
            path: Path to repository. If None, uses current directory.

        Returns:
            Branch name or None
        """
        try:
            repo = await self.get_git_repo(path)
            if repo:
                return repo.branch
            return None
        except Exception as e:
            logger.error(f"Failed to get current branch: {e}")
            return None

    async def get_remote_url(self, path: Optional[str] = None) -> Optional[str]:
        """
        Get remote repository URL.

        Args:
            path: Path to repository. If None, uses current directory.

        Returns:
            Remote URL or None
        """
        try:
            repo = await self.get_git_repo(path)
            if repo:
                return repo.remote_url
            return None
        except Exception as e:
            logger.error(f"Failed to get remote URL: {e}")
            return None

    async def get_commit_hash(self, path: Optional[str] = None) -> Optional[str]:
        """
        Get current commit hash.

        Args:
            path: Path to repository. If None, uses current directory.

        Returns:
            Commit hash or None
        """
        try:
            repo = await self.get_git_repo(path)
            if repo:
                return repo.commit_hash
            return None
        except Exception as e:
            logger.error(f"Failed to get commit hash: {e}")
            return None

    def _is_git_repo(self, path: Path) -> bool:
        """
        Check if a path is a git repository.

        Args:
            path: Path to check

        Returns:
            True if it's a git repository
        """
        try:
            # Check for .git directory
            if (path / '.git').exists() and (path / '.git').is_dir():
                return True

            # Try to run git rev-parse
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5
            )

            return result.returncode == 0

        except Exception:
            return False

    async def get_repo_name(self, path: Optional[str] = None) -> Optional[str]:
        """
        Get repository name from path.

        Args:
            path: Path to repository. If None, uses current directory.

        Returns:
            Repository name or None
        """
        try:
            repo = await self.get_git_repo(path)
            if repo:
                return repo.repo_name
            return None
        except Exception as e:
            logger.error(f"Failed to get repo name: {e}")
            return None

    def clear_cache(self):
        """Clear the git context cache"""
        self._cache.clear()
        logger.debug("Git context cache cleared")

    def cleanup(self):
        """Clean up resources"""
        self.clear_cache()
