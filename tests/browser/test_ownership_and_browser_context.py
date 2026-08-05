"""
Unit tests for Resource Ownership Tracking and Rich BrowserContext (Semantic Categories & Ownership Filtering).
Location: tests/browser/test_ownership_and_browser_context.py
"""

import pytest
from src.core.orchestration.ownership_tracker import ResourceOwner, ResourceOwnershipTracker
from src.browser.world_model import BrowserTab, BrowserContext, BrowserStateProbe
from src.browser.planner.browser_goal_planner import BrowserGoalPlanner


def test_resource_ownership_tracker():
    tracker = ResourceOwnershipTracker()
    tracker.clear()

    tracker.register_resource("tab", "tab_101", owner=ResourceOwner.AURA, details={"site": "github"})
    tracker.register_resource("tab", "tab_102", owner=ResourceOwner.USER, details={"site": "instagram"})
    tracker.register_resource("window", "win_201", owner=ResourceOwner.AURA)

    assert tracker.is_aura_owned("tab", "tab_101") is True
    assert tracker.is_aura_owned("tab", "tab_102") is False
    assert tracker.get_owner("tab", "tab_102") == ResourceOwner.USER
    assert tracker.get_owner("tab", "untracked_tab") == ResourceOwner.USER

    aura_tabs = tracker.get_aura_resources("tab")
    assert len(aura_tabs) == 1
    assert aura_tabs[0].resource_id == "tab_101"


def test_browser_context_semantic_categories():
    tabs = [
        BrowserTab(tab_id="1", title="Python 3.11 Docs", domain="docs.python.org", semantic_category="documentation"),
        BrowserTab(tab_id="2", title="VS Code API Guide", domain="code.visualstudio.com", semantic_category="documentation"),
        BrowserTab(tab_id="3", title="Amazon.com: Headphones", domain="amazon.com", semantic_category="shopping"),
        BrowserTab(tab_id="4", title="Instagram", domain="instagram.com", semantic_category="social"),
    ]
    ctx = BrowserContext(running_browsers=["chrome"], open_tabs=tabs)

    doc_tabs = ctx.find_tabs_by_category("documentation")
    assert len(doc_tabs) == 2
    assert doc_tabs[0].title == "Python 3.11 Docs"
    assert doc_tabs[1].title == "VS Code API Guide"

    shop_tabs = ctx.find_tabs_by_category("shopping")
    assert len(shop_tabs) == 1
    assert shop_tabs[0].domain == "amazon.com"


def test_semantic_category_inference():
    cat_doc = BrowserStateProbe._infer_semantic_category("Python 3.11 Documentation", "docs.python.org")
    cat_shop = BrowserStateProbe._infer_semantic_category("Amazon.com: Online Shopping", "amazon.com")
    cat_social = BrowserStateProbe._infer_semantic_category("Instagram", "instagram.com")
    cat_code = BrowserStateProbe._infer_semantic_category("GitHub - Repository", "github.com")

    assert cat_doc == "documentation"
    assert cat_shop == "shopping"
    assert cat_social == "social"
    assert cat_code == "code"


def test_planner_close_aura_resources_only():
    planner = BrowserGoalPlanner()

    tabs = [
        BrowserTab(tab_id="1", title="Aura Tab 1", domain="github.com", owner=ResourceOwner.AURA),
        BrowserTab(tab_id="2", title="User Tab 1", domain="instagram.com", owner=ResourceOwner.USER),
        BrowserTab(tab_id="3", title="Aura Tab 2", domain="amazon.com", owner=ResourceOwner.AURA),
    ]
    ctx = BrowserContext(running_browsers=["chrome"], open_tabs=tabs)

    plan = planner.create_plan("Close everything you opened", parameters={"browser_world": ctx})

    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["capability"] == "browser.close_aura_resources"
    aura_tabs_planned = plan["steps"][0]["parameters"]["aura_tabs"]
    assert len(aura_tabs_planned) == 2
    assert all(t["owner"] == "aura" for t in aura_tabs_planned)


def test_planner_close_semantic_documentation_tabs():
    planner = BrowserGoalPlanner()

    tabs = [
        BrowserTab(tab_id="1", title="Python Docs", domain="docs.python.org", semantic_category="documentation"),
        BrowserTab(tab_id="2", title="ChatGPT", domain="chatgpt.com", semantic_category="general"),
        BrowserTab(tab_id="3", title="MDN Web Docs", domain="developer.mozilla.org", semantic_category="documentation"),
    ]
    ctx = BrowserContext(running_browsers=["chrome"], open_tabs=tabs)

    plan = planner.create_plan("Close all documentation tabs", parameters={"browser_world": ctx})

    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["capability"] == "browser.close_semantic_category"
    planned_tabs = plan["steps"][0]["parameters"]["matching_tabs"]
    assert len(planned_tabs) == 2
    assert planned_tabs[0]["title"] == "Python Docs"
    assert planned_tabs[1]["title"] == "MDN Web Docs"
