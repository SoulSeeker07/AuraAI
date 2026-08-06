"""
Unit tests for WorldDiffEngine and MasterOrchestrator Self-Knowledge Context Layer.
Location: tests/browser/test_world_diff_and_self_knowledge.py
"""

import pytest

from src.browser.world_model import BrowserContext, BrowserTab
from src.core.orchestration.master_orchestrator import MasterOrchestrator
from src.core.orchestration.ownership_tracker import (
    ResourceOwner,
    ResourceOwnershipTracker,
)
from src.core.orchestration.world_diff import WorldDiff, WorldDiffEngine
from src.core.orchestration.world_snapshot import DesktopStateSnapshot


def test_world_diff_engine_computation():
    snap1 = DesktopStateSnapshot(
        running_processes=["chrome", "code"],
        focused_window_title="Visual Studio Code",
        browser_context=BrowserContext(
            running_browsers=["chrome"],
            open_tabs=[BrowserTab(tab_id="1", title="GitHub", domain="github.com")],
        ),
    )

    snap2 = DesktopStateSnapshot(
        running_processes=["chrome", "code", "spotify"],
        focused_window_title="Spotify",
        browser_context=BrowserContext(
            running_browsers=["chrome"],
            open_tabs=[
                BrowserTab(tab_id="1", title="GitHub", domain="github.com"),
                BrowserTab(tab_id="2", title="Instagram", domain="instagram.com"),
            ],
        ),
    )

    diff = WorldDiffEngine.compute_diff(snap1, snap2)

    assert "spotify" in diff.new_processes
    assert "Instagram" in diff.new_tabs
    assert diff.focused_window_changed is True
    assert diff.previous_focused == "Visual Studio Code"
    assert diff.current_focused == "Spotify"
    assert "Started processes: spotify" in diff.summary()


@pytest.mark.asyncio
async def test_master_orchestrator_self_knowledge_context():
    tracker = ResourceOwnershipTracker.get_instance()
    tracker.clear()
    tracker.register_resource(
        "tab", "tab_test", owner=ResourceOwner.AURA, details={"goal": "Research"}
    )

    orchestrator = MasterOrchestrator.get_instance()
    res = await orchestrator.process_request_async("What capabilities do you have?")

    assert res.success is True
    assert orchestrator._last_result is not None or res.observations is not None
