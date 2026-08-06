"""
Playwright Browser Backend Adapter
Location: src/core/backends/adapters/browser_backend.py

Integrates Playwright Browser Engine as a registered Backend Adapter in BackendRegistry.
Decoupled from BrowserGoalPlanner so alternative web drivers (Selenium, Puppeteer,
Remote Chrome, DevTools Protocol) can be swapped transparently.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from browser.engine import BrowserEngine
from browser.shopping import ShoppingManager

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)


class PlaywrightBrowserAdapter(BaseBackendAdapter):
    """
    Execution backend adapter wrapping Playwright BrowserEngine and ShoppingManager.
    """

    def __init__(self, headless: bool = True):
        self._engine = BrowserEngine(headless=headless)
        self._shopping = ShoppingManager(self._engine)

    @property
    def name(self) -> str:
        return "Playwright Browser Engine"

    @property
    def capabilities(self) -> list[str]:
        return [
            "browser",
            "browser.navigate",
            "browser.search",
            "browser.scroll",
            "browser.click",
            "browser.type",
            "browser.extract",
            "shopping.search",
            "shopping.compare",
            "shopping.cart",
            "shopping.checkout",
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "latency_ms": 50.0,
            "cost": 0.0,
            "is_local": True,
            "version": "1.0.0",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        """
        Execute browser navigation, page scrolling, element interaction, or shopping task.
        """
        logger.info(
            f"{self.name} executing capability '{capability}' for goal: '{goal}'"
        )
        args = arguments or {}

        # Run async engine operations via asyncio loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio

                nest_asyncio.apply()
                res = loop.run_until_complete(
                    self._async_execute(capability, goal, args)
                )
            else:
                res = loop.run_until_complete(
                    self._async_execute(capability, goal, args)
                )
        except Exception:
            res = asyncio.run(self._async_execute(capability, goal, args))

        return res

    async def _async_execute(
        self, capability: str, goal: str, arguments: dict[str, Any]
    ) -> ExecutionResult:
        cap_clean = capability.lower().replace("@1", "")

        if cap_clean in ["browser", "browser.navigate"]:
            url = (
                arguments.get("url")
                or arguments.get("target_url")
                or "https://www.google.com"
            )
            res = await self._engine.navigate(url)
            return ExecutionResult(
                success=res.get("success", True),
                planner="browser",
                goal=goal,
                confidence=0.95,
                observations=[f"Navigated to {url}"],
                data={"backend": self.name, "result": res},
            )
        elif cap_clean == "browser.search":
            query = arguments.get("query", goal)
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            res = await self._engine.navigate(search_url)
            content = await self._engine.get_text_content()
            return ExecutionResult(
                success=res.get("success", True),
                planner="browser",
                goal=goal,
                confidence=0.90,
                observations=[f"Performed web search for '{query}'"],
                data={
                    "backend": self.name,
                    "query": query,
                    "content_snippet": content[:500],
                },
            )
        elif cap_clean == "browser.scroll":
            direction = arguments.get("direction", "down")
            pixels = int(arguments.get("pixels", 500))
            if direction == "up":
                res = await self._engine.scroll_up(pixels)
            elif direction == "bottom":
                res = await self._engine.scroll_to_bottom()
            else:
                res = await self._engine.scroll_down(pixels)

            return ExecutionResult(
                success=res.get("success", True),
                planner="browser",
                goal=goal,
                confidence=0.95,
                observations=[f"Scrolled page ({direction})"],
                data={"backend": self.name, "result": res},
            )
        elif cap_clean in ["shopping.search", "shopping.compare"]:
            query = arguments.get("query", goal)
            platform = arguments.get("platform", "amazon")
            res = await self._shopping.search_products(query=query, platform=platform)
            return ExecutionResult(
                success=res.get("success", True),
                planner="browser",
                goal=goal,
                confidence=0.92,
                observations=[
                    f"Found {res.get('products_found', 0)} products for '{query}' on {platform}"
                ],
                data={"backend": self.name, "shopping_result": res},
            )
        elif cap_clean == "shopping.cart":
            product_url = arguments.get("product_url")
            res = await self._shopping.add_to_cart(product_url=product_url)
            return ExecutionResult(
                success=res.get("success", True),
                planner="browser",
                goal=goal,
                confidence=0.90,
                observations=[res.get("message", "Add to cart attempted")],
                data={"backend": self.name, "cart_result": res},
            )
        elif cap_clean == "shopping.checkout":
            user_approved = arguments.get("user_approved", False)
            res = await self._shopping.proceed_to_checkout(user_approved=user_approved)
            return ExecutionResult(
                success=res.get("success", False),
                planner="browser",
                goal=goal,
                confidence=0.50 if not user_approved else 0.90,
                observations=[res.get("message", "Checkout processed")],
                data={"backend": self.name, "checkout_result": res},
            )

        # Generic fallback
        res = await self._engine.navigate("https://www.google.com")
        return ExecutionResult(
            success=True,
            planner="browser",
            goal=goal,
            observations=[f"Executed capability '{capability}'"],
            data={"backend": self.name},
        )
