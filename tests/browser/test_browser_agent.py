"""
Unit tests for BrowserAgent, BrowserEngine, and ShoppingManager.
Location: tests/browser/test_browser_agent.py
"""

import pytest
from src.agents.browser_agent import BrowserAgent
from src.agents.task_model import TaskType
from src.agents.agent_registry import AgentRegistry, AgentType
from src.browser.engine import BrowserEngine
from src.browser.shopping import ShoppingManager, ProductItem
from src.browser.planner.browser_goal_planner import BrowserGoalPlanner
from src.routing.rules.browser_rules import BrowserRules


@pytest.mark.asyncio
async def test_browser_agent_initialization():
    agent = BrowserAgent(agent_id="test_browser_agent", config={"headless": True})
    assert agent.agent_name == "BrowserAgent"
    assert TaskType.BROWSER_SHOPPING_SEARCH.value in agent.capabilities.tasks
    assert TaskType.BROWSER_SCROLL.value in agent.capabilities.tasks
    assert TaskType.BROWSER_CHECKOUT.value in agent.capabilities.tasks

    initialized = await agent.initialize()
    assert initialized is True
    await agent.cleanup()


@pytest.mark.asyncio
async def test_browser_agent_navigate():
    agent = BrowserAgent(agent_id="test_browser_agent", config={"headless": True})
    await agent.initialize()

    task = {
        "task_type": TaskType.BROWSER_NAVIGATE.value,
        "data": {"url": "https://www.example.com"},
    }

    result = await agent.execute(task)
    assert result.success is True
    assert "Navigated to" in result.summary
    await agent.cleanup()


@pytest.mark.asyncio
async def test_browser_agent_scroll():
    agent = BrowserAgent(agent_id="test_browser_agent", config={"headless": True})
    await agent.initialize()

    task = {
        "task_type": TaskType.BROWSER_SCROLL.value,
        "data": {"direction": "down", "pixels": 300},
    }

    result = await agent.execute(task)
    assert result.success is True
    assert "Scrolled down" in result.summary
    await agent.cleanup()


@pytest.mark.asyncio
async def test_browser_agent_shopping_search():
    agent = BrowserAgent(agent_id="test_browser_agent", config={"headless": True})
    await agent.initialize()

    task = {
        "task_type": TaskType.BROWSER_SHOPPING_SEARCH.value,
        "data": {"query": "wireless headphones", "platform": "amazon"},
    }

    result = await agent.execute(task)
    assert result.success is True
    assert "wireless headphones" in result.summary
    assert "products" in result.data
    await agent.cleanup()


@pytest.mark.asyncio
async def test_browser_agent_checkout_requires_approval():
    agent = BrowserAgent(agent_id="test_browser_agent", config={"headless": True})
    await agent.initialize()

    task = {
        "task_type": TaskType.BROWSER_CHECKOUT.value,
        "data": {"user_approved": False},
        "context": {},
    }

    result = await agent.execute(task)
    assert result.success is False
    assert result.data.get("requires_approval") is True
    assert len(result.warnings) > 0
    await agent.cleanup()


@pytest.mark.asyncio
async def test_browser_agent_checkout_with_approval():
    agent = BrowserAgent(agent_id="test_browser_agent", config={"headless": True})
    await agent.initialize()

    task = {
        "task_type": TaskType.BROWSER_CHECKOUT.value,
        "data": {"user_approved": True},
        "context": {},
    }

    result = await agent.execute(task)
    assert result.success is True
    assert "initiated" in result.summary.lower()
    await agent.cleanup()


def test_browser_goal_planner_shopping_intents():
    planner = BrowserGoalPlanner()
    assert planner.can_handle("Shop for laptops on Amazon") is True
    assert planner.can_handle("Add to cart") is True
    assert planner.can_handle("Scroll down the page") is True

    plan = planner.create_plan("Shop for noise canceling headphones on Amazon")
    assert plan["planner_role"] == "browser"
    assert len(plan["steps"]) >= 2
    assert plan["metadata"]["browser_goal"]["intent"] == "shopping"


def test_browser_rules_routing():
    rules = BrowserRules()
    res_shop = rules.route("Find price for iPhone 15 on Amazon")
    assert res_shop is not None
    assert res_shop.capability.value == "browser"

    res_scroll = rules.route("Scroll down")
    assert res_scroll is not None
    assert res_scroll.capability.value == "browser"


def test_agent_registry_contains_browser():
    registry = AgentRegistry()
    agents = registry.get_agent_by_type(AgentType.BROWSER)
    assert len(agents) > 0
    assert agents[0].agent_id == "browser"


def test_backend_registry_contains_playwright_browser():
    from src.core.backends.backend_registry import BackendRegistry
    backend_reg = BackendRegistry.get_instance()
    backend = backend_reg.get_backend("Playwright Browser Engine")
    assert backend is not None
    assert "shopping.search" in backend.capabilities
    assert "shopping.checkout" in backend.capabilities


def test_risk_analyzer_checkout_critical():
    from src.execution.risk_analyzer import RiskAnalyzer, RiskLevel
    analyzer = RiskAnalyzer()
    risk, _ = analyzer.analyze_operation("shopping", "shopping_checkout", {})
    assert risk == RiskLevel.CRITICAL

