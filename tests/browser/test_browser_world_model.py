"""
Unit tests for BrowserWorldModel, BrowserStateProbe, and Cognitive State Reuse in BrowserGoalPlanner.
Location: tests/browser/test_browser_world_model.py
"""

import pytest

from src.browser.planner.browser_goal_planner import BrowserGoalPlanner
from src.browser.world_model import BrowserStateProbe, BrowserTab, BrowserWorldModel
from src.core.orchestration.world_snapshot import (
    DesktopStateSnapshot,
    WorldSnapshotProvider,
)


def test_browser_world_model_search():
    tabs = [
        BrowserTab(
            tab_id="1", title="Instagram", domain="instagram.com", browser_name="chrome"
        ),
        BrowserTab(
            tab_id="2",
            title="GitHub · Repository",
            domain="github.com",
            browser_name="edge",
        ),
        BrowserTab(
            tab_id="3", title="ChatGPT", domain="chatgpt.com", browser_name="firefox"
        ),
    ]
    model = BrowserWorldModel(
        running_browsers=["chrome", "edge", "firefox"], open_tabs=tabs
    )

    assert model.has_tab("instagram") is True
    assert model.has_tab("github") is True
    assert model.has_tab("reddit") is False
    assert len(model.find_tabs("instagram")) == 1
    assert model.find_tabs("instagram")[0].browser_name == "chrome"


def test_browser_state_probe_title_inference():
    domain_insta = BrowserStateProbe._infer_domain_from_title(
        "Instagram - Google Chrome"
    )
    domain_github = BrowserStateProbe._infer_domain_from_title(
        "GitHub · SoulSeeker07/AuraAI - Microsoft Edge"
    )
    domain_chatgpt = BrowserStateProbe._infer_domain_from_title(
        "ChatGPT — Mozilla Firefox"
    )

    assert domain_insta == "instagram.com"
    assert domain_github == "github.com"
    assert domain_chatgpt == "chatgpt.com"


def test_world_snapshot_includes_browser_world():
    provider = WorldSnapshotProvider()
    snap = provider.snapshot()
    assert isinstance(snap, DesktopStateSnapshot)
    assert isinstance(snap.browser_world, BrowserWorldModel)


def test_planner_reuse_existing_tab():
    planner = BrowserGoalPlanner()

    # Pre-populate BrowserWorldModel with Instagram tab in Chrome
    existing_tabs = [
        BrowserTab(
            tab_id="win_101",
            title="Instagram",
            domain="instagram.com",
            browser_name="chrome",
        )
    ]
    world = BrowserWorldModel(running_browsers=["chrome"], open_tabs=existing_tabs)

    plan = planner.create_plan("Open Instagram", parameters={"browser_world": world})

    assert plan["metadata"]["reuse_decision"] == "focused_tab"
    assert len(plan["steps"]) >= 1
    assert plan["steps"][0]["capability"] == "browser.switch_tab"
    assert "Reuse existing open instagram" in plan["steps"][0]["description"]


def test_planner_reuse_running_browser_new_tab():
    planner = BrowserGoalPlanner()

    # Chrome running, but NO Instagram tab open
    world = BrowserWorldModel(running_browsers=["chrome"], open_tabs=[])

    plan = planner.create_plan("Open Instagram", parameters={"browser_world": world})

    assert plan["metadata"]["reuse_decision"] == "new_tab"
    assert plan["steps"][0]["capability"] == "browser.navigate"
    assert plan["steps"][0]["parameters"]["action"] == "open_new_tab"


def test_planner_launch_browser_when_none_running():
    planner = BrowserGoalPlanner()

    # No browsers running
    world = BrowserWorldModel(running_browsers=[], open_tabs=[])

    plan = planner.create_plan("Open Instagram", parameters={"browser_world": world})

    assert plan["metadata"]["reuse_decision"] == "launch_browser"
    assert plan["steps"][0]["capability"] == "browser.navigate"
    assert plan["steps"][0]["parameters"]["action"] == "launch_browser"


def test_planner_close_single_tab_preserves_other_tabs():
    planner = BrowserGoalPlanner()

    tabs = [
        BrowserTab(
            tab_id="1", title="Instagram", domain="instagram.com", browser_name="chrome"
        ),
        BrowserTab(
            tab_id="2", title="ChatGPT", domain="chatgpt.com", browser_name="chrome"
        ),
    ]
    world = BrowserWorldModel(running_browsers=["chrome"], open_tabs=tabs)

    plan = planner.create_plan("Close Instagram", parameters={"browser_world": world})

    assert plan["steps"][0]["capability"] == "browser.close_tab"
    assert "Close single instagram tab" in plan["steps"][0]["description"]


def test_planner_close_ambiguity_resolution():
    planner = BrowserGoalPlanner()

    # Instagram open in both Chrome and Edge
    tabs = [
        BrowserTab(
            tab_id="1", title="Instagram", domain="instagram.com", browser_name="chrome"
        ),
        BrowserTab(
            tab_id="2", title="Instagram", domain="instagram.com", browser_name="edge"
        ),
    ]
    world = BrowserWorldModel(running_browsers=["chrome", "edge"], open_tabs=tabs)

    plan = planner.create_plan("Close Instagram", parameters={"browser_world": world})

    assert plan["steps"][0]["capability"] == "browser.resolve_close_ambiguity"
    assert "Ask user which browser tab to close" in plan["steps"][0]["description"]


def test_planner_close_every_instagram_page():
    planner = BrowserGoalPlanner()

    tabs = [
        BrowserTab(
            tab_id="1", title="Instagram", domain="instagram.com", browser_name="chrome"
        ),
        BrowserTab(
            tab_id="2", title="Instagram", domain="instagram.com", browser_name="edge"
        ),
    ]
    world = BrowserWorldModel(running_browsers=["chrome", "edge"], open_tabs=tabs)

    plan = planner.create_plan(
        "Close every Instagram page", parameters={"browser_world": world}
    )

    assert plan["steps"][0]["capability"] == "browser.close_all_tabs"
