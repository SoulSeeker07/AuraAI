"""
Browser Goal Planner
Location: src/browser/planner/browser_goal_planner.py

Goal-oriented browser planner that inherits from BasePlanner.
Reasons in terms of high-level page goals, not DOM click/type sequences.
"""

from __future__ import annotations

import logging
from typing import Any

from core.planning.base_planner import BasePlanner

from .browser_goal import BrowserGoal
from .site_registry import SiteRegistry

logger = logging.getLogger(__name__)


class BrowserGoalPlanner(BasePlanner):
    """
    Page-goal reasoning planner for browser tasks.
    """

    def can_handle(self, goal_text: str) -> bool:
        goal_lower = goal_text.lower()
        return any(
            w in goal_lower
            for w in [
                "browse",
                "web",
                "navigate",
                "url",
                "site",
                "page",
                "open chrome",
                "shop",
                "buy",
                "cart",
                "order",
                "checkout",
                "scroll",
                "price",
            ]
        ) or any(site in goal_lower for site in SiteRegistry.list_sites())

    def create_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from browser.world_model import BrowserStateProbe, BrowserWorldModel

        params = parameters or {}
        world_model: BrowserWorldModel = (
            params.get("browser_world") or BrowserStateProbe.probe_state()
        )
        goal = self.resolve_goal(goal_text, params)

        steps: list[dict[str, Any]] = []
        step_id = 1
        goal_lower = goal_text.lower()

        # Handle Close Intents ("Close Instagram", "Close Chrome", "Close everything you opened", "Close documentation tabs")
        if "close" in goal_lower:
            from core.orchestration.ownership_tracker import ResourceOwner

            site_target = goal.site
            matching_tabs = world_model.find_tabs(site_target)

            if any(
                phrase in goal_lower
                for phrase in [
                    "everything you opened",
                    "all aura tabs",
                    "aura opened",
                    "clean up aura",
                ]
            ):
                aura_tabs = world_model.find_tabs_by_owner(ResourceOwner.AURA)
                steps.append(
                    {
                        "step_id": f"step_{step_id}",
                        "description": f"Close all tabs spawned by Aura AI ({len(aura_tabs)} tabs found), leaving user tabs open",
                        "capability": "browser.close_aura_resources",
                        "parameters": {"aura_tabs": [t.to_dict() for t in aura_tabs]},
                    }
                )
            elif "documentation" in goal_lower or "docs" in goal_lower:
                doc_tabs = world_model.find_tabs_by_category("documentation")
                steps.append(
                    {
                        "step_id": f"step_{step_id}",
                        "description": f"Close all documentation tabs ({len(doc_tabs)} tabs found)",
                        "capability": "browser.close_semantic_category",
                        "parameters": {
                            "category": "documentation",
                            "matching_tabs": [t.to_dict() for t in doc_tabs],
                        },
                    }
                )
            elif "every" in goal_lower or "all" in goal_lower:
                steps.append(
                    {
                        "step_id": f"step_{step_id}",
                        "description": f"Close all matching {site_target} tabs across all browsers ({len(matching_tabs)} tabs found)",
                        "capability": "browser.close_all_tabs",
                        "parameters": {
                            "site": site_target,
                            "matching_tabs": [t.to_dict() for t in matching_tabs],
                        },
                    }
                )
            elif (
                "chrome" in goal_lower
                and "tab" not in goal_lower
                and site_target == "google"
            ):
                steps.append(
                    {
                        "step_id": f"step_{step_id}",
                        "description": "Close Chrome application process",
                        "capability": "browser.close_app",
                        "parameters": {"browser": "chrome"},
                    }
                )
            elif len(matching_tabs) > 1:
                browsers_found = list({t.browser_name for t in matching_tabs})
                steps.append(
                    {
                        "step_id": f"step_{step_id}",
                        "description": f"Ask user which browser tab to close ({', '.join(browsers_found)})",
                        "capability": "browser.resolve_close_ambiguity",
                        "parameters": {
                            "site": site_target,
                            "browsers_found": browsers_found,
                            "matching_tabs": [t.to_dict() for t in matching_tabs],
                        },
                    }
                )
            elif len(matching_tabs) == 1:
                target_tab = matching_tabs[0]
                steps.append(
                    {
                        "step_id": f"step_{step_id}",
                        "description": f"Close single {site_target} tab in {target_tab.browser_name} (leave other tabs open)",
                        "capability": "browser.close_tab",
                        "parameters": {"tab": target_tab.to_dict()},
                    }
                )
            else:
                steps.append(
                    {
                        "step_id": f"step_{step_id}",
                        "description": f"Locate and close {site_target} tab",
                        "capability": "browser.close_tab",
                        "parameters": {"site": site_target},
                    }
                )

            return {
                "planner_role": "browser",
                "goal": goal_text,
                "steps": steps,
                "metadata": {
                    "browser_goal": goal.to_dict(),
                    "state_reuse": "tab_close",
                },
            }

        # Handle Open / Navigation / Shopping Intents (State Reuse Rule 1-6)
        matching_tabs = world_model.find_tabs(goal.site)

        if matching_tabs:
            target_tab = matching_tabs[0]
            steps.append(
                {
                    "step_id": f"step_{step_id}",
                    "description": f"Reuse existing open {goal.site} tab in {target_tab.browser_name} (Focus window/tab)",
                    "capability": "browser.switch_tab",
                    "parameters": {
                        "tab": target_tab.to_dict(),
                        "action": "focus_existing_tab",
                    },
                }
            )
            step_id += 1
        elif world_model.has_browser():
            steps.append(
                {
                    "step_id": f"step_{step_id}",
                    "description": f"Reuse running browser and open new tab for {goal.target_url or goal.site}",
                    "capability": "browser.navigate",
                    "parameters": {
                        "site": goal.site,
                        "target_url": goal.target_url,
                        "action": "open_new_tab",
                    },
                }
            )
            step_id += 1
        else:
            steps.append(
                {
                    "step_id": f"step_{step_id}",
                    "description": f"Launch preferred browser and navigate to {goal.target_url or goal.site}",
                    "capability": "browser.navigate",
                    "parameters": {
                        "site": goal.site,
                        "target_url": goal.target_url,
                        "action": "launch_browser",
                    },
                }
            )
            step_id += 1

        if goal.intent == "shopping":
            steps.append(
                {
                    "step_id": f"step_{step_id}",
                    "description": f"Search products on {goal.site}",
                    "capability": "shopping.search",
                    "parameters": goal.to_dict(),
                }
            )
        elif goal.intent in ["cart", "add_to_cart"]:
            steps.append(
                {
                    "step_id": f"step_{step_id}",
                    "description": f"Add product to cart on {goal.site}",
                    "capability": "shopping.cart",
                    "parameters": goal.to_dict(),
                }
            )
        elif goal.intent in ["order", "checkout"]:
            steps.append(
                {
                    "step_id": f"step_{step_id}",
                    "description": f"Initiate order checkout on {goal.site} (CRITICAL risk level)",
                    "capability": "shopping.checkout",
                    "parameters": goal.to_dict(),
                }
            )
        elif goal.intent == "scroll":
            steps.append(
                {
                    "step_id": f"step_{step_id}",
                    "description": f"Scroll page content on {goal.site}",
                    "capability": "browser.scroll",
                    "parameters": goal.to_dict(),
                }
            )

        return {
            "planner_role": "browser",
            "goal": goal_text,
            "steps": steps,
            "metadata": {
                "browser_goal": goal.to_dict(),
                "world_state": world_model.to_dict(),
                "reuse_decision": (
                    "focused_tab"
                    if matching_tabs
                    else ("new_tab" if world_model.has_browser() else "launch_browser")
                ),
            },
        }

    def optimize_plan(self, plan: Any) -> Any:
        return plan

    def execute_plan(self, plan: Any) -> Any:
        return plan

    def explain_plan(
        self,
        goal_text: str,
        capability: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = self.create_plan(goal_text, capability, parameters)
        return {
            "description": f"Browser Goal Planner plan for: {goal_text}",
            "steps": plan.get("steps", []),
        }

    def resolve_goal(self, goal_text: str, parameters: dict[str, Any]) -> BrowserGoal:
        goal_lower = goal_text.lower()

        detected_site = "google"
        for site_name in SiteRegistry.list_sites():
            if site_name in goal_lower:
                detected_site = site_name
                break

        site_profile = SiteRegistry.get_site(detected_site)
        username = (
            parameters.get("username") or parameters.get("recalled_username") or ""
        )

        if "buy" in goal_lower or "order" in goal_lower or "checkout" in goal_lower:
            intent = "order"
            target_url = (
                site_profile.base_url if site_profile else "https://www.amazon.com"
            )
        elif "add to cart" in goal_lower or "cart" in goal_lower:
            intent = "add_to_cart"
            target_url = (
                site_profile.base_url if site_profile else "https://www.amazon.com"
            )
        elif "shop" in goal_lower or "product" in goal_lower or "price" in goal_lower:
            intent = "shopping"
            query = parameters.get("query", goal_text)
            target_url = (
                site_profile.search_url_template.format(query=query)
                if site_profile and site_profile.search_url_template
                else f"https://www.amazon.com/s?k={query}"
            )
        elif "scroll" in goal_lower:
            intent = "scroll"
            target_url = (
                site_profile.base_url if site_profile else "https://www.google.com"
            )
        elif "profile" in goal_lower or "my account" in goal_lower:
            intent = "profile"
            target_url = (
                site_profile.profile_url_template.format(username=username)
                if site_profile and site_profile.profile_url_template and username
                else (site_profile.base_url if site_profile else "")
            )
        elif "search" in goal_lower or "find" in goal_lower or "look up" in goal_lower:
            intent = "search"
            query = parameters.get("query", goal_text)
            target_url = (
                site_profile.search_url_template.format(query=query)
                if site_profile and site_profile.search_url_template
                else ""
            )
        else:
            intent = "navigate"
            target_url = (
                site_profile.base_url if site_profile else "https://www.google.com"
            )

        return BrowserGoal(
            site=detected_site,
            intent=intent,
            target_url=target_url,
            auth_required=site_profile.auth_required if site_profile else False,
            parameters={"username": username, "goal_text": goal_text},
            fallback_prompt=(
                f"Please provide your {detected_site} username"
                if intent == "profile" and not username
                else ""
            ),
        )
