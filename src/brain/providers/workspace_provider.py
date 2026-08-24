"""
Workspace World Model Provider
Location: src/brain/providers/workspace_provider.py

Provides workspace perception: git status/branch, modified files, project type,
and .gitignore-filtered file tree structure via WorkspaceWalker.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Executor
from pathlib import Path
from typing import Any

try:
    from workspace.editor_tracker import EditorTracker
    from workspace.git_context import GitContext
    from workspace.project_detector import ProjectDetector
    from workspace.workspace_walker import WorkspaceWalker
except (ImportError, ModuleNotFoundError):
    EditorTracker = None  # type: ignore
    GitContext = None  # type: ignore
    ProjectDetector = None  # type: ignore
    WorkspaceWalker = None  # type: ignore
from .base import IWorldProvider, ProviderFact


class WorkspaceProvider(IWorldProvider):
    """
    World model provider for repository and filesystem workspace perception.
    """

    def __init__(
        self,
        root: Path | str | None = None,
        git_context: GitContext | None = None,
        project_detector: ProjectDetector | None = None,
        editor_tracker: EditorTracker | None = None,
        executor: Executor | None = None,
    ):
        self.root: Path = Path(root).resolve() if root else Path.cwd().resolve()
        self.git_context = git_context or GitContext(cache_ttl_seconds=30)
        self.project_detector = project_detector or ProjectDetector()
        self.editor_tracker = editor_tracker or EditorTracker(root=self.root)
        self.walker = WorkspaceWalker(root=self.root, respect_gitignore=True, max_files=1000)
        self._executor = executor

    @property
    def domain(self) -> str:
        return "workspace"

    async def get_state(self) -> dict[str, Any]:
        """Fetch full workspace perception dictionary."""
        loop = asyncio.get_running_loop()
        
        # Git query
        if self._executor:
            repo = await loop.run_in_executor(self._executor, self.git_context.get_git_repo_sync, str(self.root))
        else:
            repo = self.git_context.get_git_repo_sync(str(self.root))

        # Project detection query
        try:
            if self._executor:
                proj_res = await loop.run_in_executor(
                    self._executor, self.project_detector._detect_project_at_path, self.root
                )
            else:
                proj_res = self.project_detector._detect_project_at_path(self.root)
            proj_type = (
                proj_res.project.type.value
                if proj_res and proj_res.project and hasattr(proj_res.project, "type")
                else "unknown"
            )
        except Exception:
            proj_type = "unknown"

        # Active editor file query
        try:
            if self._executor:
                active_editor = await loop.run_in_executor(
                    self._executor, self.editor_tracker.get_active_editor_file_sync, self.root.name, self.root
                )
            else:
                active_editor = self.editor_tracker.get_active_editor_file_sync(self.root.name, self.root)
        except Exception:
            active_editor = None

        return {
            "root": str(self.root),
            "project_type": proj_type,
            "git_branch": repo.branch if repo else "",
            "uncommitted_changes": repo.uncommitted_changes if repo else 0,
            "modified_files": repo.modified_files if repo else [],
            "is_dirty": repo.is_dirty if repo else False,
            "active_editor": active_editor or {},
        }

    async def query(self, entity: str) -> list[ProviderFact]:
        """
        Query workspace domain for specific entities.
        
        Supported entity queries:
          - "active_file" / "active_editor" / "active_document" / "open_file"
          - "git_branch" / "current_branch" / "branch"
          - "uncommitted_changes" / "dirty_files" / "is_dirty"
          - "project_type" / "project_info" / "root"
          - "file_tree" / "files"
        """
        facts: list[ProviderFact] = []
        entity_norm = entity.strip().lower()
        state = await self.get_state()

        if entity_norm in ("active_file", "active_editor", "active_document", "open_file", "all"):
            active_editor_data = state.get("active_editor") or {}
            if active_editor_data and active_editor_data.get("relative_path"):
                facts.append(
                    ProviderFact(
                        domain=self.domain,
                        entity="active_file",
                        value=active_editor_data.get("relative_path"),
                    )
                )

        if entity_norm in ("git_branch", "current_branch", "branch", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="git_branch",
                    value=state["git_branch"],
                )
            )

        if entity_norm in ("dirty_files", "modified_files", "uncommitted_changes", "is_dirty", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="uncommitted_changes",
                    value=state["uncommitted_changes"],
                )
            )
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="modified_files",
                    value=state["modified_files"],
                )
            )

        if entity_norm in ("project_type", "project", "root", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="project_type",
                    value=state["project_type"],
                )
            )
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="project_root",
                    value=state["root"],
                )
            )

        if entity_norm in ("file_tree", "files", "workspace_files"):
            loop = asyncio.get_running_loop()
            if self._executor:
                files = await loop.run_in_executor(self._executor, self.walker.walk_files, "*", False)
            else:
                files = self.walker.walk_files(raise_on_limit=False)

            rel_files = [f.relative_to(self.root).as_posix() for f in files]
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="file_tree",
                    value=rel_files[:100],  # Bound return to first 100 entries for prompt safety
                )
            )

        return facts
