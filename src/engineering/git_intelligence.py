"""
Git Intelligence

Handles Git operations and understanding.

This module enables Aura to:
- Understand branches and commits
- Analyze git status
- Suggest git operations
- Track history
- Manage staging and merging
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GitCommit:
    """Represents a git commit."""

    hash: str
    message: str
    author: str
    date: str
    files_changed: list[str]
    lines_added: int
    lines_deleted: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hash": self.hash,
            "message": self.message,
            "author": self.author,
            "date": self.date,
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_deleted": self.lines_deleted,
        }


@dataclass
class GitBranch:
    """Represents a git branch."""

    name: str
    is_current: bool
    is_remote: bool
    last_commit: str
    commit_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "is_current": self.is_current,
            "is_remote": self.is_remote,
            "last_commit": self.last_commit,
            "commit_count": self.commit_count,
        }


class GitIntelligence:
    """
    Handles Git operations and understanding.

    Usage:
        git = GitIntelligence(repository_path="/path/to/repo")

        # Get git status
        status = git.get_status()

        # Get branches
        branches = git.get_branches()

        # Get commits
        commits = git.get_recent_commits(limit=10)

        # Get git statistics
        stats = git.get_statistics()
    """

    def __init__(self, repository_path: Path):
        """
        Initialize the Git Intelligence.

        Args:
            repository_path: Path to the repository
        """
        self.repository_path = Path(repository_path).resolve()

    def get_status(self) -> dict[str, Any]:
        """
        Get git status.

        Returns:
            Dictionary with git status
        """
        try:
            import git

            repo = git.Repo(self.repository_path)

            # Get status
            status = {
                "branch": str(repo.active_branch),
                "working_dir_clean": len(list(repo.iter_changed_files())) == 0,
                "staged": len(list(repo.index.diff("HEAD"))),
                "untracked": len(list(repo.untracked_files)),
                "ahead": len(repo.git.cmd.process_list),
                "behind": 0,
            }

            return status
        except ImportError:
            return {"error": "Git not available"}
        except Exception as e:
            logger.error(f"Error getting git status: {e}")
            return {"error": str(e)}

    def get_branches(self) -> list[GitBranch]:
        """Get all branches."""
        try:
            import git

            repo = git.Repo(self.repository_path)

            branches = []
            for branch in repo.branches:
                branches.append(
                    GitBranch(
                        name=str(branch),
                        is_current=branch == repo.active_branch,
                        is_remote=branch.is_remote(),
                        last_commit=branch.commit.hexsha[:7] if branch.commit else "",
                        commit_count=0,
                    )
                )

            return branches
        except Exception as e:
            logger.error(f"Error getting branches: {e}")
            return []

    def get_recent_commits(self, limit: int = 10) -> list[GitCommit]:
        """
        Get recent commits.

        Args:
            limit: Maximum number of commits

        Returns:
            List of commits
        """
        try:
            import git

            repo = git.Repo(self.repository_path)

            commits = []
            for commit in repo.iter_commits(limit=limit):
                commits.append(
                    GitCommit(
                        hash=commit.hexsha[:7],
                        message=commit.message.strip(),
                        author=commit.author.name,
                        date=commit.committed_datetime.isoformat(),
                        files_changed=(
                            [f.a_path for f in commit.parents[0].diff(commit) if f]
                            if commit.parents
                            else []
                        ),
                        lines_added=0,
                        lines_deleted=0,
                    )
                )

            return commits
        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            return []

    def get_statistics(self) -> dict[str, Any]:
        """
        Get git statistics.

        Returns:
            Dictionary with statistics
        """
        try:
            import git

            repo = git.Repo(self.repository_path)

            return {
                "total_commits": len(list(repo.iter_commits())),
                "branches": len(repo.branches),
                "authors": len(set(c.author.name for c in repo.iter_commits())),
                "recent_activity": len(list(repo.iter_commits(max_count=30))),
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def create_commit(
        self, message: str, files: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Create a git commit.

        Args:
            message: Commit message
            files: Files to commit, or None for all

        Returns:
            Dictionary with result
        """
        try:
            import git

            repo = git.Repo(self.repository_path)

            if files:
                repo.index.add(files)

            repo.index.commit(message)

            return {
                "success": True,
                "message": message,
                "hash": repo.head.commit.hexsha[:7],
            }
        except Exception as e:
            logger.error(f"Error creating commit: {e}")
            return {"success": False, "error": str(e)}

    def suggest_commit_message(self, changes: list[str]) -> str:
        """
        Suggest a commit message based on changes.

        Args:
            changes: List of changed files and their changes

        Returns:
            Suggested commit message
        """
        # Simple heuristic-based suggestion
        return "Update files and improve functionality"

    def get_diff_for_file(self, file_path: str) -> str:
        """
        Get diff for a file.

        Args:
            file_path: Path to file

        Returns:
            Diff as string
        """
        try:
            import git

            repo = git.Repo(self.repository_path)

            return repo.git.diff("HEAD", file_path)
        except Exception as e:
            logger.error(f"Error getting diff: {e}")
            return ""
