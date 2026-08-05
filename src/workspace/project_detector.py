"""
Project Detector

Automatically detects current projects (git repos, Python, Node, etc.).
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import CurrentProject, GitRepository, ProjectType

logger = logging.getLogger(__name__)


@dataclass
class ProjectDetectionResult:
    """Result of project detection"""

    project: CurrentProject | None
    detected_at: str
    method: str


class ProjectDetector:
    """
    Auto-detects the current project from the filesystem.

    Checks for:
    - Git repositories
    - Python projects (pyproject.toml, setup.py, etc.)
    - Node projects (package.json)
    - .NET projects (.csproj, .sln)
    - Go projects (go.mod)
    - Rust projects (Cargo.toml)
    - Java projects (pom.xml, build.gradle)
    """

    # Project type markers
    PYTHON_MARKERS = {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "py.typed",
        "tox.ini",
        "poetry.lock",
        "Pipfile.lock",
    }

    NODE_MARKERS = {"package.json", "node_modules", "yarn.lock", "pnpm-lock.yaml"}

    DOTNET_MARKERS = {".csproj", ".sln", ".fsproj", ".vbproj", "packages.config"}

    GO_MARKERS = {"go.mod", "go.sum", "go.work"}

    RUST_MARKERS = {"Cargo.toml", "Cargo.lock"}

    JAVA_MARKERS = {"pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"}

    def __init__(self):
        """Initialize project detector"""
        self._cache: dict = {}
        self._cache_ttl = 60  # Cache for 60 seconds

    async def detect_current_project(
        self, project_path: str | None = None
    ) -> CurrentProject | None:
        """
        Detect the current active project.

        Args:
            project_path: Optional path to start detection from. If None, uses current directory.

        Returns:
            CurrentProject object or None if no project detected
        """
        try:
            # Use cache if available
            cache_key = project_path or os.getcwd()
            if cache_key in self._cache:
                cached_result, cached_time = self._cache[cache_key]
                if datetime.now() - cached_time < self._cache_ttl:
                    return cached_result

            # Get project path
            if project_path:
                search_path = Path(project_path).resolve()
            else:
                search_path = Path.cwd().resolve()

            logger.debug(f"Detecting project at: {search_path}")

            # Walk up directory tree
            current_path = search_path
            while current_path != current_path.parent:
                result = self._detect_project_at_path(current_path)

                if result.project:
                    # Cache the result
                    self._cache[cache_key] = (result.project, datetime.now())
                    logger.info(
                        f"Detected project: {result.project.name} at {result.project.path}"
                    )
                    return result.project

                # Move up to parent directory
                current_path = current_path.parent

            # No project found
            self._cache[cache_key] = (None, datetime.now())
            logger.debug("No project detected")
            return None

        except Exception as e:
            logger.error(f"Failed to detect project: {e}")
            return None

    def _detect_project_at_path(self, path: Path) -> ProjectDetectionResult:
        """
        Detect if a path contains a project.

        Args:
            path: Path to check

        Returns:
            ProjectDetectionResult
        """
        # Check for Git repository first
        git_repo = self._check_git_repo(path)
        if git_repo:
            return ProjectDetectionResult(
                project=CurrentProject(
                    path=str(path),
                    name=git_repo.repo_name,
                    type=ProjectType.UNKNOWN,  # Type detected separately
                    git_repo=git_repo,
                    detected_at=datetime.now(),
                ),
                detected_at=datetime.now().isoformat(),
                method="git",
            )

        # Check for other project types
        project_type = self._detect_project_type(path)
        if project_type != ProjectType.UNKNOWN:
            project_name = path.name
            return ProjectDetectionResult(
                project=CurrentProject(
                    path=str(path),
                    name=project_name,
                    type=project_type,
                    detected_at=datetime.now(),
                ),
                detected_at=datetime.now().isoformat(),
                method=project_type.value,
            )

        # No project found
        return ProjectDetectionResult(
            project=None, detected_at=datetime.now().isoformat(), method="none"
        )

    def _check_git_repo(self, path: Path) -> GitRepository | None:
        """
        Check if a path is a git repository.

        Args:
            path: Path to check

        Returns:
            GitRepository object or None
        """
        try:
            # Check for .git directory
            git_dir = path / ".git"
            if git_dir.exists() and git_dir.is_dir():
                # Try to get branch from .git/HEAD
                head_file = git_dir / "HEAD"
                if head_file.exists():
                    with open(head_file) as f:
                        head_content = f.read()
                        if "ref: refs/heads/" in head_content:
                            branch = head_content.split("ref: refs/heads/")[-1].strip()
                            # Try to get remote URL
                            remote_file = git_dir / "config"
                            remote_url = None
                            if remote_file.exists():
                                try:
                                    with open(remote_file) as f:
                                        config_content = f.read()
                                        # Try to find remote URL
                                        for line in config_content.split("\n"):
                                            if "url = " in line:
                                                remote_url = line.split("url = ")[
                                                    -1
                                                ].strip()
                                                break
                                except Exception:
                                    pass
                        else:
                            branch = "detached HEAD"

                        return GitRepository(
                            path=str(path), branch=branch, remote_url=remote_url
                        )

            # Try to run git commands
            import subprocess

            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    cwd=str(path),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    repo_path = result.stdout.strip()
                    if repo_path:
                        # Get branch
                        branch_result = subprocess.run(
                            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        branch = branch_result.stdout.strip()

                        # Get remote URL
                        remote_result = subprocess.run(
                            ["git", "config", "--get", "remote.origin.url"],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        remote_url = remote_result.stdout.strip()

                        # Get modified files
                        status_result = subprocess.run(
                            ["git", "status", "--porcelain"],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )

                        modified_files = []
                        for line in status_result.stdout.strip().split("\n"):
                            if line:
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    modified_files.append(parts[1])

                        return GitRepository(
                            path=repo_path,
                            branch=branch,
                            remote_url=remote_url,
                            modified_files=modified_files,
                            is_dirty=bool(modified_files),
                        )
            except Exception as e:
                logger.debug(f"Git command failed: {e}")

        except Exception as e:
            logger.error(f"Failed to check git repo: {e}")

        return None

    def _detect_project_type(self, path: Path) -> ProjectType:
        """
        Detect project type based on file markers.

        Args:
            path: Path to check

        Returns:
            ProjectType
        """
        for marker in self.PYTHON_MARKERS:
            if (path / marker).exists():
                return ProjectType.PYTHON

        for marker in self.NODE_MARKERS:
            if (path / marker).exists():
                return ProjectType.NODE

        for marker in self.DOTNET_MARKERS:
            if (path / marker).exists():
                return ProjectType.DOTNET

        for marker in self.GO_MARKERS:
            if (path / marker).exists():
                return ProjectType.GO

        for marker in self.RUST_MARKERS:
            if (path / marker).exists():
                return ProjectType.RUST

        for marker in self.JAVA_MARKERS:
            if (path / marker).exists():
                return ProjectType.JAVA

        return ProjectType.UNKNOWN

    async def detect_project_by_path(self, path: str) -> CurrentProject | None:
        """
        Detect project at specific path.

        Args:
            path: Path to check

        Returns:
            CurrentProject or None
        """
        return await self.detect_current_project(path)

    def clear_cache(self):
        """Clear the project detection cache"""
        self._cache.clear()
        logger.debug("Project detection cache cleared")

    def cleanup(self):
        """Clean up resources"""
        self.clear_cache()
