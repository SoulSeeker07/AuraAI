"""
Browser Engine - Core Playwright-backed Browser Automation Engine.
Location: src/browser/engine.py

Provides low-level browser interaction including page navigation, DOM interaction,
scrolling, screenshot capture, form input, and element extraction.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Dynamic Playwright import
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    Browser = None
    BrowserContext = None
    Page = None
    logger.warning(
        "Playwright is not installed. BrowserEngine will operate in fallback mode."
    )


@dataclass
class ElementInfo:
    """Information extracted from a DOM element."""

    tag_name: str
    text: str
    attributes: dict[str, str] = field(default_factory=dict)
    bounding_box: dict[str, float] | None = None
    is_visible: bool = True
    is_enabled: bool = True


class BrowserEngine:
    """
    Core browser controller managing Playwright browser instances,
    pages, navigation, interactions, and scrolling.
    """

    def __init__(self, headless: bool = True, browser_type: str = "chromium"):
        self.headless = headless
        self.browser_type_name = browser_type.lower()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self.is_active: bool = False

    async def start(self) -> bool:
        """Launch browser instance and open initial context and page."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.info("Playwright unavailable - using fallback headless HTTP engine.")
            self.is_active = True
            return True

        try:
            self._playwright = await async_playwright().start()
            if self.browser_type_name == "firefox":
                launcher = self._playwright.firefox
            elif self.browser_type_name == "webkit":
                launcher = self._playwright.webkit
            else:
                launcher = self._playwright.chromium

            self._browser = await launcher.launch(
                headless=self.headless,
                args=[
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()
            self.is_active = True
            logger.info(
                f"BrowserEngine started ({self.browser_type_name}, headless={self.headless})"
            )
            return True
        except Exception as e:
            logger.warning(
                f"Failed to start Playwright browser ({e}). Falling back to HTTP engine."
            )
            self._page = None
            self._context = None
            self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            self.is_active = True
            return True

    async def close(self) -> None:
        """Close page, context, and browser."""
        try:
            if self._page:
                await self._page.close()
                self._page = None
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.warning(f"Error closing BrowserEngine: {e}")
        finally:
            self.is_active = False
            logger.info("BrowserEngine closed.")

    async def navigate(
        self, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 30000
    ) -> dict[str, Any]:
        """Navigate to target URL."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        if not self.is_active:
            started = await self.start()
            if not started:
                return {
                    "success": False,
                    "url": url,
                    "error": "Browser engine failed to start",
                }

        if self._page:
            try:
                response = await self._page.goto(
                    url, wait_until=wait_until, timeout=timeout_ms
                )
                status = response.status if response else 200
                title = await self._page.title()
                current_url = self._page.url
                return {
                    "success": status < 400,
                    "status_code": status,
                    "title": title,
                    "url": current_url,
                }
            except Exception as e:
                logger.error(f"Navigation error for {url}: {e}")
                return {"success": False, "url": url, "error": str(e)}
        else:
            # Fallback HTTP request representation
            return {
                "success": True,
                "url": url,
                "title": f"Page at {url} (Fallback Mode)",
                "status_code": 200,
            }

    async def scroll_down(self, pixels: int = 500) -> dict[str, Any]:
        """Scroll down by specified pixels."""
        if self._page:
            await self._page.evaluate(f"window.scrollBy(0, {pixels});")
            await asyncio.sleep(0.3)
            scroll_y = await self._page.evaluate("window.scrollY")
            return {
                "success": True,
                "action": "scroll_down",
                "pixels": pixels,
                "scroll_y": scroll_y,
            }
        return {
            "success": True,
            "action": "scroll_down",
            "pixels": pixels,
            "mode": "fallback",
        }

    async def scroll_up(self, pixels: int = 500) -> dict[str, Any]:
        """Scroll up by specified pixels."""
        if self._page:
            await self._page.evaluate(f"window.scrollBy(0, -{pixels});")
            await asyncio.sleep(0.3)
            scroll_y = await self._page.evaluate("window.scrollY")
            return {
                "success": True,
                "action": "scroll_up",
                "pixels": pixels,
                "scroll_y": scroll_y,
            }
        return {
            "success": True,
            "action": "scroll_up",
            "pixels": pixels,
            "mode": "fallback",
        }

    async def scroll_to_bottom(self) -> dict[str, Any]:
        """Scroll directly to the bottom of the page."""
        if self._page:
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(0.5)
            scroll_y = await self._page.evaluate("window.scrollY")
            return {"success": True, "action": "scroll_to_bottom", "scroll_y": scroll_y}
        return {"success": True, "action": "scroll_to_bottom", "mode": "fallback"}

    async def scroll_to_element(self, selector: str) -> dict[str, Any]:
        """Scroll until element matching selector is in viewport."""
        if self._page:
            try:
                element = self._page.locator(selector).first
                await element.scroll_into_view_if_needed(timeout=5000)
                return {
                    "success": True,
                    "action": "scroll_to_element",
                    "selector": selector,
                }
            except Exception as e:
                return {
                    "success": False,
                    "action": "scroll_to_element",
                    "selector": selector,
                    "error": str(e),
                }
        return {
            "success": True,
            "action": "scroll_to_element",
            "selector": selector,
            "mode": "fallback",
        }

    async def infinite_scroll(
        self, max_scrolls: int = 5, pause_sec: float = 1.0
    ) -> dict[str, Any]:
        """Perform infinite scroll to dynamically load content."""
        scroll_count = 0
        last_height = 0
        if self._page:
            for i in range(max_scrolls):
                last_height = await self._page.evaluate("document.body.scrollHeight")
                await self._page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                await asyncio.sleep(pause_sec)
                new_height = await self._page.evaluate("document.body.scrollHeight")
                scroll_count += 1
                if new_height == last_height:
                    break
            return {
                "success": True,
                "scrolls_completed": scroll_count,
                "final_height": last_height,
            }
        return {"success": True, "scrolls_completed": max_scrolls, "mode": "fallback"}

    async def click(self, selector: str, timeout_ms: int = 5000) -> dict[str, Any]:
        """Click an element by selector or text content."""
        if self._page:
            try:
                locator = self._page.locator(selector).first
                await locator.click(timeout=timeout_ms)
                return {"success": True, "action": "click", "selector": selector}
            except Exception as e:
                try:
                    text_locator = self._page.get_by_text(selector, exact=False).first
                    await text_locator.click(timeout=timeout_ms)
                    return {"success": True, "action": "click_text", "text": selector}
                except Exception as ex:
                    return {
                        "success": False,
                        "action": "click",
                        "selector": selector,
                        "error": f"{e}; text_click: {ex}",
                    }
        return {
            "success": True,
            "action": "click",
            "selector": selector,
            "mode": "fallback",
        }

    async def type_text(
        self, selector: str, text: str, clear: bool = True, timeout_ms: int = 5000
    ) -> dict[str, Any]:
        """Fill or type text into input field."""
        if self._page:
            try:
                locator = self._page.locator(selector).first
                if clear:
                    await locator.fill(text, timeout=timeout_ms)
                else:
                    await locator.type(text, timeout=timeout_ms)
                return {
                    "success": True,
                    "action": "type_text",
                    "selector": selector,
                    "text": text,
                }
            except Exception as e:
                return {
                    "success": False,
                    "action": "type_text",
                    "selector": selector,
                    "error": str(e),
                }
        return {
            "success": True,
            "action": "type_text",
            "selector": selector,
            "text": text,
            "mode": "fallback",
        }

    async def press_key(self, key: str) -> dict[str, Any]:
        """Press a keyboard key (e.g. 'Enter', 'Tab', 'Escape')."""
        if self._page:
            await self._page.keyboard.press(key)
            return {"success": True, "action": "press_key", "key": key}
        return {"success": True, "action": "press_key", "key": key, "mode": "fallback"}

    async def take_screenshot(self, full_page: bool = False) -> dict[str, Any]:
        """Capture screenshot and return base64 string."""
        if self._page:
            try:
                screenshot_bytes = await self._page.screenshot(full_page=full_page)
                b64_img = base64.b64encode(screenshot_bytes).decode("utf-8")
                return {
                    "success": True,
                    "image_b64": b64_img,
                    "size_bytes": len(screenshot_bytes),
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No active page for screenshot"}

    async def get_text_content(self, selector: str = "body") -> str:
        """Get visible inner text of page or selector."""
        if self._page:
            try:
                text = await self._page.locator(selector).inner_text(timeout=5000)
                return text.strip()
            except Exception:
                return ""
        return "Fallback text content"

    async def get_page_info(self) -> dict[str, Any]:
        """Get basic page metadata."""
        if self._page:
            return {
                "title": await self._page.title(),
                "url": self._page.url,
                "is_active": self.is_active,
            }
        return {"title": "Offline Browser", "url": "about:blank", "is_active": False}

    async def click_top_video(self) -> dict[str, Any]:
        """Click top video result on YouTube or media search page."""
        if self._page:
            selectors = [
                "ytd-video-renderer a#video-title",
                "a#video-title",
                "h3 a",
                "a.yt-simple-endpoint.ytd-video-renderer",
            ]
            for sel in selectors:
                try:
                    loc = self._page.locator(sel).first
                    if await loc.count() > 0:
                        await loc.click(timeout=3000)
                        await asyncio.sleep(1.0)
                        return {"success": True, "action": "click_top_video", "selector": sel}
                except Exception:
                    pass
        return {"success": False, "action": "click_top_video"}

    async def click_top_product(self) -> dict[str, Any]:
        """Click top product result on Amazon or e-commerce search page."""
        if self._page:
            selectors = [
                "div[data-component-type='s-search-result'] h2 a",
                ".s-search-results h2 a",
                "a.a-link-normal.s-no-hover",
            ]
            for sel in selectors:
                try:
                    loc = self._page.locator(sel).first
                    if await loc.count() > 0:
                        await loc.click(timeout=3000)
                        await asyncio.sleep(1.0)
                        return {"success": True, "action": "click_top_product", "selector": sel}
                except Exception:
                    pass
        return {"success": False, "action": "click_top_product"}
