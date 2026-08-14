"""
Repository Manager

Monitors and maintains a live model of the repository state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RepositoryHealth(Enum):
    """Repository health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class RepositoryState:
    """Live model of repository state."""

    path: Path
    name: str = ""
    language: str = "unknown"
    framework: str = "unknown"
    modules: list[str] = field(default_factory=list)
    architecture: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)
    entrypoints: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    documentation: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    configs: list[str] = field(default_factory=list)
    git_branch: str = "main"
    git_status: str = "clean"
    health: RepositoryHealth = RepositoryHealth.UNKNOWN
    size: int = 0
    file_count: int = 0
    folder_count: int = 0
    last_sync: datetime = field(default_factory=datetime.now)
    active_files: list[Path] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)
    last_commit: str | None = None
    commit_count: int = 0
    open_issues: int = 0
    code_coverage: float = 0.0
    technical_debt: float = 0.0
    cyclomatic_complexity_avg: float = 0.0
    documentation_coverage: float = 0.0

    def is_up_to_date(self) -> bool:
        """Check if repository is up to date."""
        return self.git_status == "clean"

    def get_health_score(self) -> float:
        """Calculate health score (0-100)."""
        score = 100.0

        # Deduct for issues
        if self.open_issues > 0:
            score -= min(self.open_issues * 5, 50)

        # Deduct for debt
        score -= self.technical_debt * 5

        # Deduct for poor coverage
        score -= (1.0 - self.code_coverage) * 50

        return max(0.0, min(100.0, score))


class RepositoryManager:
    """
    Manages repository state and continuous monitoring.

    Maintains a live model of the repository that includes:
    - File structure
    - Dependencies
    - Architecture
    - Health indicators
    - Git status
    - Recent changes

    Usage:
        manager = RepositoryManager(repository_path="/path/to/repo")

        # Get current state
        state = manager.get_repository_state()

        # Wait for file changes
        state = manager.wait_for_change(timeout=30)

        # Sync manually
        manager.sync()
    """

    def __init__(
        self, 
        repository_path: Path, 
        auto_sync: bool = True, 
        watch_interval: int = 5,
        workspace_walker=None
    ):
        """
        Initialize the Repository Manager.

        Args:
            repository_path: Path to the repository
            auto_sync: Whether to automatically sync on changes
            watch_interval: Interval in seconds for file watching
            workspace_walker: Walker instance for repository discovery
        """
        self.repository_path = Path(repository_path).resolve()
        self.auto_sync = auto_sync
        self.watch_interval = watch_interval

        if workspace_walker is None:
            from .workspace_walker import WorkspaceFileWalker
            self.workspace_walker = WorkspaceFileWalker(repository_path=self.repository_path)
        else:
            self.workspace_walker = workspace_walker

        # Build initial state
        self._build_state()

    def sync(self) -> RepositoryState:
        """
        Sync the repository state.

        Returns:
            Updated repository state
        """
        logger.info(f"Syncing repository: {self.repository_path}")
        self._build_state()
        return self._state

    def _safe_rglob(self, pattern: str) -> list[Path]:
        """Safely find files matching pattern, using WorkspaceFileWalker."""
        try:
            scope = self.workspace_walker.walk(pattern=pattern)
            return scope.files
        except Exception as e:
            logger.warning(f"Error scanning pattern '{pattern}': {e}")
            return []

    def _build_state(self):
        """Build the repository state."""
        self._state = RepositoryState(path=self.repository_path)
        self._state.name = self.repository_path.name

        # Count non-ignored files efficiently
        all_files = [f for f in self._safe_rglob("*") if f.is_file()]
        self._state.file_count = len(all_files)
        self._state.folder_count = len(set(f.parent for f in all_files))
        self._state.size = sum(f.stat().st_size for f in all_files if f.exists())

        # Detect language/framework
        self._detect_language_and_framework()

        # Find entry points
        self._find_entry_points()

        # Find test files
        self._find_test_files()

        # Find documentation
        self._find_documentation()

        # Find assets
        self._find_assets()

        # Find configs
        self._find_configs()

        # Detect git status
        self._detect_git_status()

        # Update health
        self._update_health()

        logger.info(f"Repository state built: {self._state.name}")

    def _detect_language_and_framework(self):
        """Detect the programming language and framework."""
        py_files = self._safe_rglob("*.py")
        js_files = self._safe_rglob("*.js")
        ts_files = self._safe_rglob("*.ts")
        java_files = self._safe_rglob("*.java")
        cpp_files = self._safe_rglob("*.cpp")
        go_files = self._safe_rglob("*.go")
        rs_files = self._safe_rglob("*.rs")

        max_files = max(
            len(py_files),
            len(js_files),
            len(ts_files),
            len(java_files),
            len(cpp_files),
            len(go_files),
            len(rs_files),
        )

        if max_files == len(py_files) and py_files:
            self._state.language = "python"
            if (self.repository_path / "requirements.txt").exists() or (
                self.repository_path / "pyproject.toml"
            ).exists():
                self._state.framework = "python"

        elif max_files == len(ts_files) and ts_files:
            self._state.language = "typescript"
            self._state.framework = (
                "react"
                if any("react" in f.name.lower() for f in ts_files)
                else "unknown"
            )
        elif max_files == len(js_files) and js_files:
            self._state.language = "javascript"
            self._state.framework = "unknown"
        elif max_files == len(java_files) and java_files:
            self._state.language = "java"
            self._state.framework = (
                "spring"
                if any("spring" in f.name.lower() for f in java_files)
                else "unknown"
            )
        elif max_files == len(cpp_files) and cpp_files:
            self._state.language = "cpp"
            self._state.framework = "unknown"
        elif max_files == len(go_files) and go_files:
            self._state.language = "go"
            self._state.framework = "unknown"
        elif max_files == len(rs_files) and rs_files:
            self._state.language = "rust"
            self._state.framework = "unknown"

    def _find_entry_points(self):
        """Find application entry points."""
        if self._state.language == "python":
            self._state.entrypoints.extend(
                str(f) for f in self._safe_rglob("main.py")
            )
            self._state.entrypoints.extend(
                str(f) for f in self._safe_rglob("app.py")
            )
        elif self._state.language == "typescript":
            self._state.entrypoints.extend(
                str(f) for f in self._safe_rglob("index.ts")
            )
            self._state.entrypoints.extend(
                str(f) for f in self._safe_rglob("main.ts")
            )

    def _find_test_files(self):
        """Find test files."""
        patterns = [
            "test_*.py",
            "tests_*.py",
            "*_test.py",
            "*_tests.py",
            "test_*.js",
            "test_*.ts",
            "spec_*.js",
            "spec_*.ts",
            "*_test.js",
            "*_test.ts",
            "*_spec.js",
            "*_spec.ts",
        ]

        for pattern in patterns:
            self._state.tests.extend(
                str(f) for f in self._safe_rglob(pattern)
            )

    def _find_documentation(self):
        """Find documentation files."""
        doc_patterns = [
            "README.md",
            "README.rst",
            "CHANGELOG.md",
            "changelog.md",
            "HISTORY.md",
            "history.md",
            "AUTHORS.md",
            "docs",
            "doc",
            "readme",
        ]

        for pattern in doc_patterns:
            docs = self._safe_rglob(pattern)
            self._state.documentation.extend(str(f) for f in docs)

    def _find_assets(self):
        """Find asset files."""
        asset_patterns = [
            "assets",
            "static",
            "public",
        ]

        for pattern in asset_patterns:
            assets = self._safe_rglob(pattern)
            self._state.assets.extend(str(f) for f in assets if f.is_dir())

    def _find_configs(self):
        """Find configuration files."""
        config_patterns = [
            "package.json",
            "tsconfig.json",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
        ]

        for pattern in config_patterns:
            configs = self._safe_rglob(pattern)
            self._state.configs.extend(str(f) for f in configs)

    def _detect_git_status(self):
        """Detect git status."""
        try:
            import git

            repo = git.Repo(self.repository_path)

            self._state.git_branch = str(repo.active_branch)
            self._state.commit_count = len(list(repo.iter_commits()))

            # Get status
            untracked = len(list(repo.untracked_files))
            staged = len(list(repo.index.diff("HEAD")))

            if untracked == 0 and staged == 0:
                self._state.git_status = "clean"
                self._state.health = RepositoryHealth.HEALTHY
                self._state.last_commit = str(repo.head.commit)
            elif untracked > 0 or staged > 0:
                self._state.git_status = "dirty"
                self._state.health = RepositoryHealth.DEGRADED
            else:
                self._state.git_status = "unknown"
        except ImportError:
            pass
        except Exception:
            pass

    def _update_health(self):
        """Update repository health."""
        if self._state.git_status == "clean":
            self._state.health = RepositoryHealth.HEALTHY
        elif self._state.git_status == "dirty":
            self._state.health = RepositoryHealth.DEGRADED
        else:
            self._state.health = RepositoryHealth.UNKNOWN

    def get_repository_state(self) -> RepositoryState:
        """
        Get the current repository state.

        Returns:
            RepositoryState object
        """
        return self._state

    def is_up_to_date(self) -> bool:
        """Check if repository is up to date."""
        return self._state.is_up_to_date()

    def get_health_score(self) -> float:
        """Get repository health score."""
        return self._state.get_health_score()

    def get_stats(self) -> dict[str, Any]:
        """
        Get repository statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "language": self._state.language,
            "framework": self._state.framework,
            "file_count": self._state.file_count,
            "size": self._state.size,
            "modules": self._state.modules,
            "tests": len(self._state.tests),
            "documentation": len(self._state.documentation),
            "health": self._state.health.value,
            "health_score": self._state.get_health_score(),
            "git_branch": self._state.git_branch,
            "git_status": self._state.git_status,
        }
