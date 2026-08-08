"""
Browser Agent - Specialized Agent for Web Browsing, Shopping, Orders, & Page Interactions.
Location: src/agents/browser_agent.py

Extends BaseAgent to handle autonomous web browsing, e-commerce product search,
cart management, order execution, scrolling, and DOM interaction.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from browser.engine import BrowserEngine
from browser.shopping import ShoppingManager

from .base_agent import AgentCapabilities, AgentResult, AgentState, BaseAgent
from .task_model import TaskType

logger = logging.getLogger(__name__)


class BrowserAgent(BaseAgent):
    """
    Specialized agent for browser navigation, scrolling, clicking, filling forms,
    e-commerce shopping, cart management, and order checkout.
    """

    agent_name: str = "BrowserAgent"
    agent_version: str = "1.0.0"
    agent_description: str = (
        "Handles autonomous web browsing, page scrolling, element interaction, "
        "e-commerce product searches, cart management, and order processing."
    )

    def __init__(
        self,
        agent_id: str = "browser_agent",
        config: dict[str, Any] | None = None,
    ):
        capabilities = AgentCapabilities(
            tasks=[
                TaskType.BROWSER_OPEN.value,
                TaskType.BROWSER_NAVIGATE.value,
                TaskType.BROWSER_SEARCH.value,
                TaskType.BROWSER_SCROLL.value,
                TaskType.BROWSER_CLICK.value,
                TaskType.BROWSER_TYPE.value,
                TaskType.BROWSER_EXTRACT.value,
                TaskType.BROWSER_SHOPPING_SEARCH.value,
                TaskType.BROWSER_ADD_TO_CART.value,
                TaskType.BROWSER_CHECKOUT.value,
                TaskType.BROWSER_ORDER.value,
            ],
            tools=["browser_engine", "shopping_manager"],
            models=["groq", "gemini"],
            priority=85,
            expert_domains=[
                "web_browsing",
                "e_commerce",
                "shopping",
                "order_automation",
                "dom_interaction",
            ],
        )
        super().__init__(agent_id=agent_id, capabilities=capabilities, config=config)
        self.engine = config.get("engine") or BrowserEngine(
            headless=self.config.get("headless", True)
        )
        self.shopping = ShoppingManager(self.engine)

    async def initialize(self) -> bool:
        """Initialize browser resources."""
        await self._set_state(AgentState.INITIALIZED)
        return True

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        """
        Execute a browser, scrolling, or shopping task.

        Args:
            task: Task dictionary containing:
                - task_type: Type of task to perform
                - data: Task parameters (url, query, direction, pixels, platform, selector, etc.)
                - context: Context dictionary

        Returns:
            AgentResult: Structured result object
        """
        self.start_time = time.time()
        await self._set_state(AgentState.WORKING)

        task_type = task.get("task_type", TaskType.BROWSER_NAVIGATE.value)
        if isinstance(task_type, TaskType):
            task_type = task_type.value

        data = task.get("data", {})
        context = task.get("context", {})

        logger.info(f"BrowserAgent executing task: {task_type} with data: {data}")

        try:
            if task_type in [
                TaskType.BROWSER_OPEN.value,
                TaskType.BROWSER_NAVIGATE.value,
            ]:
                result = await self._handle_navigate(data)
            elif task_type == TaskType.BROWSER_SEARCH.value:
                result = await self._handle_search(data)
            elif task_type == TaskType.BROWSER_SCROLL.value:
                result = await self._handle_scroll(data)
            elif task_type == TaskType.BROWSER_CLICK.value:
                result = await self._handle_click(data)
            elif task_type == TaskType.BROWSER_TYPE.value:
                result = await self._handle_type(data)
            elif task_type == TaskType.BROWSER_EXTRACT.value:
                result = await self._handle_extract(data)
            elif task_type == TaskType.BROWSER_SHOPPING_SEARCH.value:
                result = await self._handle_shopping_search(data)
            elif task_type == TaskType.BROWSER_ADD_TO_CART.value:
                result = await self._handle_add_to_cart(data)
            elif task_type in [
                TaskType.BROWSER_CHECKOUT.value,
                TaskType.BROWSER_ORDER.value,
            ]:
                result = await self._handle_order_checkout(data, context)
            else:
                # Default navigation handler for unknown web goals
                result = await self._handle_navigate(data)

            await self._set_state(AgentState.COMPLETED)
            self.end_time = time.time()
            return result

        except Exception as e:
            logger.error(f"BrowserAgent execution error: {e}", exc_info=True)
            await self._set_state(AgentState.FAILED)
            self.end_time = time.time()
            return self._create_result(
                success=False,
                summary=f"Browser task failed: {e}",
                error=str(e),
                confidence=0.0,
            )

    async def _handle_navigate(self, data: dict[str, Any]) -> AgentResult:
        """Handle webpage navigation."""
        url = (
            data.get("url")
            or data.get("target_url")
            or data.get("site")
            or "https://www.google.com"
        )
        nav_info = await self.engine.navigate(url)
        if nav_info.get("success"):
            return self._create_result(
                success=True,
                summary=f"Navigated to {nav_info.get('url')} ({nav_info.get('title')})",
                actions=[f"Navigated to {url}"],
                confidence=0.95,
                data=nav_info,
            )
        return self._create_result(
            success=False,
            summary=f"Failed to navigate to {url}",
            error=nav_info.get("error", "Navigation failed"),
            confidence=0.0,
            data=nav_info,
        )

    async def _handle_search(self, data: dict[str, Any]) -> AgentResult:
        """Handle general web search."""
        query = data.get("query") or data.get("goal_text") or "Python programming"
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        nav_info = await self.engine.navigate(search_url)
        content = await self.engine.get_text_content()

        return self._create_result(
            success=nav_info.get("success", False),
            summary=f"Performed web search for '{query}'",
            actions=[f"Searched web for '{query}'"],
            confidence=0.90,
            data={
                "query": query,
                "search_url": search_url,
                "content_snippet": content[:500],
            },
        )

    async def _handle_scroll(self, data: dict[str, Any]) -> AgentResult:
        """Handle page scrolling (down, up, to bottom, to element, infinite scroll)."""
        direction = data.get("direction", "down").lower()
        pixels = int(data.get("pixels") or data.get("amount") or 500)
        selector = data.get("selector")

        if selector:
            res = await self.engine.scroll_to_element(selector)
            action_desc = f"Scrolled to element '{selector}'"
        elif direction == "up":
            res = await self.engine.scroll_up(pixels)
            action_desc = f"Scrolled up by {pixels}px"
        elif direction == "bottom":
            res = await self.engine.scroll_to_bottom()
            action_desc = "Scrolled to page bottom"
        elif direction == "infinite":
            max_scrolls = int(data.get("max_scrolls", 5))
            res = await self.engine.infinite_scroll(max_scrolls=max_scrolls)
            action_desc = (
                f"Completed infinite scroll ({res.get('scrolls_completed')} pages)"
            )
        else:
            res = await self.engine.scroll_down(pixels)
            action_desc = f"Scrolled down by {pixels}px"

        return self._create_result(
            success=res.get("success", True),
            summary=action_desc,
            actions=[action_desc],
            confidence=0.95,
            data=res,
        )

    async def _handle_click(self, data: dict[str, Any]) -> AgentResult:
        """Handle clicking element by selector or text."""
        selector = data.get("selector") or data.get("text") or data.get("target")
        if not selector:
            return self._create_result(
                success=False,
                summary="No selector provided for click task",
                error="Missing selector",
            )

        res = await self.engine.click(selector)
        return self._create_result(
            success=res.get("success", False),
            summary=f"Clicked element matching '{selector}'",
            actions=[f"Clicked '{selector}'"],
            confidence=0.90 if res.get("success") else 0.20,
            data=res,
        )

    async def _handle_type(self, data: dict[str, Any]) -> AgentResult:
        """Handle typing text into form fields."""
        selector = data.get("selector") or "input"
        text = data.get("text") or data.get("value") or ""
        clear = data.get("clear", True)

        res = await self.engine.type_text(selector, text, clear=clear)
        return self._create_result(
            success=res.get("success", False),
            summary=f"Typed text into '{selector}'",
            actions=[f"Filled '{selector}' with text"],
            confidence=0.90 if res.get("success") else 0.20,
            data=res,
        )

    async def _handle_extract(self, data: dict[str, Any]) -> AgentResult:
        """Extract text or metadata from active page."""
        selector = data.get("selector", "body")
        text = await self.engine.get_text_content(selector)
        page_info = await self.engine.get_page_info()

        return self._create_result(
            success=bool(text),
            summary=f"Extracted page content from '{selector}'",
            actions=["Extracted page text content"],
            confidence=0.95,
            data={
                "text_length": len(text),
                "content": text[:1500],
                "page_info": page_info,
            },
        )

    async def _handle_shopping_search(self, data: dict[str, Any]) -> AgentResult:
        """Handle product search across e-commerce platforms."""
        query = (
            data.get("query") or data.get("product") or data.get("item") or "headphones"
        )
        platform = data.get("platform") or data.get("site") or "amazon"
        max_results = int(data.get("max_results", 5))

        res = await self.shopping.search_products(
            query=query, platform=platform, max_results=max_results
        )

        return self._create_result(
            success=res.get("success", False),
            summary=f"Found {res.get('products_found', 0)} products for '{query}' on {platform}",
            actions=[f"Searched {platform} for '{query}'"],
            confidence=0.92,
            data=res,
        )

    async def _handle_add_to_cart(self, data: dict[str, Any]) -> AgentResult:
        """Handle adding item to shopping cart."""
        product_url = data.get("product_url") or data.get("url")
        selector = data.get("selector")

        res = await self.shopping.add_to_cart(
            product_url=product_url, selector=selector
        )

        return self._create_result(
            success=res.get("success", False),
            summary=res.get("message", "Add to cart attempted"),
            actions=["Clicked Add to Cart"],
            confidence=0.90 if res.get("success") else 0.30,
            data=res,
        )

    async def _handle_order_checkout(
        self, data: dict[str, Any], context: dict[str, Any]
    ) -> AgentResult:
        """Handle order checkout process with safety verification."""
        user_approved = data.get("user_approved") or context.get("user_approved", False)

        res = await self.shopping.proceed_to_checkout(user_approved=user_approved)

        if res.get("requires_approval"):
            return self._create_result(
                success=False,
                summary=res.get("message"),
                warnings=["Order placement halted pending user authorization."],
                suggestions=["Request user approval before finalizing purchase."],
                next_steps=["Prompt user for order approval"],
                confidence=0.50,
                data=res,
            )

        return self._create_result(
            success=res.get("success", False),
            summary="Checkout process initiated successfully.",
            actions=["Initiated order checkout"],
            confidence=0.90,
            data=res,
        )

    async def cleanup(self) -> bool:
        """Clean up browser resources."""
        await self.engine.close()
        await self._set_state(AgentState.DESTROYED)
        return True
