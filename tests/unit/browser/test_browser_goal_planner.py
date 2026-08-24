"""
Unit Tests — BrowserGoalPlanner and SiteRegistry
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from browser.planner.browser_goal import BrowserGoal
from browser.planner.browser_goal_planner import BrowserGoalPlanner
from browser.planner.site_registry import SiteRegistry


class TestBrowserGoalPlanner:
    def test_resolve_instagram_profile_goal(self):
        planner = BrowserGoalPlanner()
        goal = planner.resolve_goal(
            "Open my Instagram profile", {"username": "sreekanta_yr"}
        )
        assert goal.site == "instagram"
        assert goal.intent == "profile"
        assert "sreekanta_yr" in goal.target_url
        assert goal.auth_required is True

    def test_resolve_github_search_goal(self):
        planner = BrowserGoalPlanner()
        goal = planner.resolve_goal("Search GitHub for asyncio", {})
        assert goal.site == "github"
        assert goal.intent == "search"
        assert "github.com/search" in goal.target_url

    def test_create_plan_steps(self):
        planner = BrowserGoalPlanner()
        plan = planner.create_plan(
            "Open my Instagram profile", parameters={"username": "sreekanta_yr"}
        )
        assert plan["planner_role"] == "browser"
        steps = plan["steps"]
        assert len(steps) >= 1
        capabilities = [s["capability"] for s in steps]
        assert "browser.navigate" in capabilities

    def test_site_registry_known_sites(self):
        sites = SiteRegistry.list_sites()
        assert "instagram" in sites
        assert "github" in sites
        assert "linkedin" in sites
        assert "youtube" in sites
        assert "google" in sites
