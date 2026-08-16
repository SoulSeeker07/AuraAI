"""
Layer 0.5: World Model & Multi-Domain Perception Engine
Location: src/brain/world_model.py

The central, unified representation of the user's computing environment.
Tracks:
    * Desktop & Applications (running, focused, PID)
    * Workspace & Repositories (git branch, modified files, file tree)
    * Code Intelligence (AST classes, functions, imports via SymbolGraphProvider)
    * Browser Context (tabs, URLs, active page)
    * Cognitive Memory (user preferences, past decisions)

Features:
    * Multi-domain entity queries (query / query_sync) with pre-filtering and per-domain timeouts
    * Dedicated bounded ThreadPoolExecutor (max_workers=4) preventing thread pool starvation
    * Graceful degradation if any individual provider times out or fails
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from workspace.git_context import GitContext
from .providers.base import IWorldProvider, ProviderFact, QueryResult

logger = logging.getLogger(__name__)


@dataclass
class WorldState:
    """A snapshot of the external computer state."""

    applications: list[dict[str, Any]] = field(default_factory=list)
    focused_window: str = ""
    focused_pid: int | None = None
    browser_tabs: list[dict[str, Any]] = field(default_factory=list)
    workspace: dict[str, Any] = field(default_factory=dict)
    voice: dict[str, Any] = field(default_factory=dict)
    clipboard: str = ""
    is_live: bool = False
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "applications": self.applications,
            "focused_window": self.focused_window,
            "focused_pid": self.focused_pid,
            "browser_tabs": self.browser_tabs,
            "workspace": self.workspace,
            "voice": self.voice,
            "clipboard": self.clipboard,
            "is_live": self.is_live,
            "timestamp": self.timestamp,
        }

    def summarize(self) -> str:
        """Build a compact text summary for the LLM."""
        parts: list[str] = []

        if self.focused_window:
            parts.append(f"Focused Window: {self.focused_window}")
        if self.applications:
            running = [
                a.get("name", "unknown")
                for a in self.applications
                if a.get("running", False)
            ]
            if running:
                parts.append(f"Running Apps: {', '.join(running[:5])}")
        if self.browser_tabs:
            tabs = [t.get("title", t.get("url", "tab")) for t in self.browser_tabs[:5]]
            parts.append(f"Browser Tabs: {', '.join(tabs)}")
        if self.workspace:
            project = self.workspace.get("project", "")
            branch = self.workspace.get("git_branch", "")
            if project:
                parts.append(f"Project: {project}")
            if branch:
                parts.append(f"Git Branch: {branch}")
        if self.clipboard:
            parts.append(f"Clipboard: {self.clipboard[:50]}")
        if self.voice:
            mic = self.voice.get("mic_active", False)
            parts.append(f"Mic: {'Active' if mic else 'Inactive'}")

        return "\n".join(parts) if parts else "No world state available."


class WorldModel:
    """
    Tracks external computer state continuously and provides unified multi-domain querying.
    """

    # Domain-specific default timeout allowances (in seconds)
    DEFAULT_TIMEOUTS: dict[str, float] = {
        "desktop": 0.5,    # Fast Win32/Process checks
        "workspace": 0.8,  # Cached git / file tree
        "browser": 1.5,    # Playwright tab / DOM probes
        "symbol": 2.0,     # AST / mtime graph traversal
        "memory": 2.0,     # Vector / SQLite lookups
    }

    _instance: WorldModel | None = None
    _sync_loop: asyncio.AbstractEventLoop | None = None
    _sync_thread: threading.Thread | None = None
    _sync_lock = threading.Lock()
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> WorldModel:
        """Get or create the global singleton WorldModel instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for test isolation)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.shutdown()
                cls._instance = None

    @classmethod
    def _get_sync_loop(cls) -> asyncio.AbstractEventLoop:
        """Get or lazily start a dedicated, long-lived background event loop for sync queries."""
        import threading
        with cls._sync_lock:
            if cls._sync_loop is None or not cls._sync_loop.is_running():
                loop = asyncio.new_event_loop()
                def _run_loop():
                    asyncio.set_event_loop(loop)
                    loop.run_forever()
                t = threading.Thread(target=_run_loop, daemon=True, name="world-model-sync-loop")
                t.start()
                cls._sync_loop = loop
                cls._sync_thread = t
            return cls._sync_loop

    def __init__(
        self,
        snapshot_provider: Any | None = None,
        git_context: GitContext | None = None,
        providers: list[IWorldProvider] | None = None,
    ):
        """
        Initialize the World Model with a dedicated, bounded thread pool executor.
        """
        self.snapshot_provider = snapshot_provider
        self.git_context = git_context or GitContext(cache_ttl_seconds=30)
        self._state = WorldState()
        
        # Dedicated bounded thread pool (max 4 workers) isolating world model I/O
        # from the global default executor used by voice/audio loops.
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="world-model-worker"
        )
        
        self.providers: list[IWorldProvider] = (
            providers if providers is not None else self._build_default_providers()
        )

    def _build_default_providers(self) -> list[IWorldProvider]:
        """Instantiate default canonical perception providers wired to dedicated executor."""
        from .providers.desktop_provider import DesktopProvider
        from .providers.workspace_provider import WorkspaceProvider
        from .providers.symbol_provider import SymbolGraphProvider
        from .providers.browser_provider import BrowserProvider
        from .providers.memory_provider import MemoryProvider

        return [
            DesktopProvider(executor=self._executor),
            WorkspaceProvider(git_context=self.git_context, executor=self._executor),
            SymbolGraphProvider(executor=self._executor),
            BrowserProvider(executor=self._executor),
            MemoryProvider(executor=self._executor),
        ]

    def register_provider(self, provider: IWorldProvider) -> None:
        """Register an additional perception provider."""
        self.providers.append(provider)

    async def query(
        self,
        entity: str,
        domain: str | None = None,
        timeout: float | None = None,
    ) -> QueryResult:
        """
        Query world model for facts about an entity with strict timeout and domain isolation.

        Note on thread cancellation:
            Python threads executing synchronous C/OS calls cannot be forcibly terminated.
            A timeout here abandons waiting for the coroutine to protect the calling loop's
            latency budget; the isolated dedicated ThreadPoolExecutor ensures background work
            cannot starve default event loop worker slots.

        Args:
            entity: Target entity (e.g. 'active_window', 'git_branch', 'class:App', 'all')
            domain: Optional domain filter ('desktop', 'workspace', 'symbol', 'browser', 'memory')
            timeout: Optional override for query timeout in seconds
        """
        # 1. Pre-filter target providers by domain
        if domain and domain != "all":
            target_providers = [p for p in self.providers if p.domain == domain]
        else:
            target_providers = self.providers

        if not target_providers:
            return QueryResult(
                entity=entity,
                facts=[],
                summary=f"No active provider found for domain '{domain}'.",
            )

        # 2. Build guarded query tasks with per-domain timeouts
        async def _guarded_provider_query(p: IWorldProvider) -> list[ProviderFact]:
            allowance = timeout or self.DEFAULT_TIMEOUTS.get(p.domain, 1.0)
            try:
                return await asyncio.wait_for(p.query(entity), timeout=allowance)
            except asyncio.TimeoutError:
                logger.warning(
                    f"[WorldModel] Provider '{p.domain}' timed out after {allowance}s querying '{entity}'"
                )
                return []
            except Exception as e:
                logger.debug(
                    f"[WorldModel] Provider '{p.domain}' failed querying '{entity}': {e}"
                )
                return []

        # 3. Parallel non-blocking execution with graceful degradation
        results = await asyncio.gather(
            *[_guarded_provider_query(p) for p in target_providers]
        )

        # 4. Flatten facts and generate summary
        all_facts: list[ProviderFact] = [fact for sublist in results for fact in sublist]
        summary = self._format_query_summary(entity, all_facts)

        return QueryResult(entity=entity, facts=all_facts, summary=summary)

    async def query_multi(
        self,
        entities: list[str],
        domain: str | None = None,
        timeout: float | None = None,
    ) -> list[QueryResult]:
        """
        Query multiple entities concurrently in a single batch gather.
        """
        tasks = [self.query(entity=e, domain=domain, timeout=timeout) for e in entities]
        return await asyncio.gather(*tasks)

    def query_sync(
        self,
        entity: str,
        domain: str | None = None,
        timeout: float | None = None,
    ) -> QueryResult:
        """
        Synchronously query the world model without per-call loop construction overhead
        or event loop collisions.
        """
        allowance = timeout or (self.DEFAULT_TIMEOUTS.get(domain, 1.0) if domain else 1.5)
        try:
            sync_loop = self._get_sync_loop()
            future = asyncio.run_coroutine_threadsafe(
                self.query(entity, domain=domain, timeout=timeout), sync_loop
            )
            return future.result(timeout=allowance + 0.5)
        except Exception as e:
            logger.debug(f"[WorldModel] query_sync failed for entity '{entity}': {e}")
            return QueryResult(entity=entity, facts=[], summary="")

    def query_multi_sync(
        self,
        entities: list[str],
        domain: str | None = None,
        timeout: float | None = None,
    ) -> list[QueryResult]:
        """
        Synchronously query multiple entities in a single concurrent batch.
        """
        allowance = timeout or (self.DEFAULT_TIMEOUTS.get(domain, 1.0) if domain else 1.5)
        try:
            sync_loop = self._get_sync_loop()
            future = asyncio.run_coroutine_threadsafe(
                self.query_multi(entities=entities, domain=domain, timeout=timeout), sync_loop
            )
            return future.result(timeout=allowance + 0.5)
        except Exception as e:
            logger.debug(f"[WorldModel] query_multi_sync failed: {e}")
            return [QueryResult(entity=e, facts=[], summary="") for e in entities]

    def _format_query_summary(self, entity: str, facts: list[ProviderFact]) -> str:
        """Format a clean, concise summary of discovered facts consistent with WorldState."""
        if not facts:
            return f"No world model facts discovered for '{entity}'."

        lines = [f"World Model Facts for '{entity}':"]
        for f in facts:
            val_str = str(f.value)
            if isinstance(f.value, list) and len(f.value) > 5:
                val_str = f"{', '.join(str(v) for v in f.value[:5])} (+{len(f.value) - 5} more)"
            lines.append(f"• [{f.domain.title()}] {f.entity}: {val_str}")

        return "\n".join(lines)

    def update(self) -> WorldState:
        """
        Synchronously update the world state from live system probes.
        """
        # 1. Live OS snapshot
        if self.snapshot_provider is not None:
            try:
                snap = self.snapshot_provider.snapshot()
                self._state.focused_window = snap.focused_window_title or ""
                self._state.focused_pid = getattr(snap, "focused_pid", None)
                self._state.applications = [
                    {"name": p, "running": True}
                    for p in getattr(snap, "running_processes", [])[:20]
                ]
                self._state.is_live = getattr(snap, "is_live", False)
            except Exception as e:
                logger.debug(f"World snapshot unavailable: {e}")

        # 2. Workspace state via cached GitContext
        try:
            repo = self.git_context.get_git_repo_sync()
            if repo and repo.branch:
                self._state.workspace["git_branch"] = repo.branch
                self._state.workspace["uncommitted_changes"] = repo.uncommitted_changes
                self._state.workspace["is_dirty"] = repo.is_dirty
        except Exception as e:
            logger.debug(f"GitContext query failed: {e}")

        self._state.timestamp = datetime.now().isoformat()
        return self._state

    async def update_async(self) -> WorldState:
        """
        Asynchronously update the world state without blocking the event loop.
        """
        if self.snapshot_provider is not None:
            try:
                if hasattr(self.snapshot_provider, "snapshot_async"):
                    snap = await self.snapshot_provider.snapshot_async()
                else:
                    snap = self.snapshot_provider.snapshot()
                self._state.focused_window = snap.focused_window_title or ""
                self._state.focused_pid = getattr(snap, "focused_pid", None)
                self._state.applications = [
                    {"name": p, "running": True}
                    for p in getattr(snap, "running_processes", [])[:20]
                ]
                self._state.is_live = getattr(snap, "is_live", False)
            except Exception as e:
                logger.debug(f"World snapshot unavailable: {e}")

        try:
            repo = await self.git_context.get_git_repo()
            if repo and repo.branch:
                self._state.workspace["git_branch"] = repo.branch
                self._state.workspace["uncommitted_changes"] = repo.uncommitted_changes
                self._state.workspace["is_dirty"] = repo.is_dirty
        except Exception as e:
            logger.debug(f"GitContext query failed: {e}")

        self._state.timestamp = datetime.now().isoformat()
        return self._state

    def get_state(self) -> WorldState:
        """Get the current world state."""
        return self._state

    def set_browser_tabs(self, tabs: list[dict[str, Any]]) -> None:
        """Set current browser tabs."""
        self._state.browser_tabs = tabs

    def set_clipboard(self, text: str) -> None:
        """Set current clipboard content."""
        self._state.clipboard = text

    def set_voice_state(self, mic_active: bool) -> None:
        """Set voice/mic state."""
        self._state.voice = {"mic_active": mic_active}

    def set_workspace(self, workspace: dict[str, Any]) -> None:
        """Set workspace state."""
        self._state.workspace = workspace

    def shutdown(self) -> None:
        """Shutdown dedicated thread pool executor."""
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass

    def close(self) -> None:
        """Explicitly close and cleanup WorldModel resources."""
        self.shutdown()

    def __enter__(self) -> WorldModel:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.shutdown()
        except Exception:
            pass


__all__ = ["WorldModel", "WorldState", "IWorldProvider", "ProviderFact", "QueryResult"]
