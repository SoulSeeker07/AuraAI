"""
browser_tools.py

The tools the LLM is allowed to call. This is the fix for vision_loop.py's
core failure mode: instead of asking a non-tool-calling vision model to
guess pixel (x, y) coordinates from a screenshot, hand-repair its truncated
JSON, and retry blindly on "no visible change" — we give a real
tool-calling model a `click(description)` tool, and let Playwright's own
accessibility-tree locators (get_by_role, get_by_text, get_by_label)
resolve "the description" into the actual element. This is strictly more
reliable than coordinate grounding and needs zero screenshot-diff hacks.

Every tool takes/returns plain JSON-serializable data so it drops straight
into an OpenAI/Groq-style tool-calling loop.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from browser.challenge_detection import detect_challenges, url_looks_challenged

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI / Groq function-calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Go to a URL directly. Prefer this over clicking through search results when you already know the target URL (e.g. a site's search-results URL pattern).",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an element identified by visible text, aria-label, role, or placeholder. Describe it the way a person would, e.g. 'Add to Cart button', 'the search box', 'link titled Wireless Mouse'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into an input/textarea identified the same way as click(). Optionally press Enter afterward.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "text": {"type": "string"},
                    "press_enter": {"type": "boolean"},
                },
                "required": ["description", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_by_coordinates",
            "description": "LAST RESORT ONLY — use click(description) first. Only reach for this when click() has already failed on a canvas, WebGL app, video-player control, or icon-only element with no visible text/label/placeholder for click() to match against. Coordinates are pixels on a 1280x800 viewport.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "description": {"type": "string", "description": "What you believe is at these coordinates and why click() couldn't find it."},
                },
                "required": ["x", "y", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the page up or down.",
            "parameters": {
                "type": "object",
                "properties": {"direction": {"type": "string", "enum": ["up", "down"]}},
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Capture a live visual screenshot of the current page to inspect visual layout, logos, canvas, or elements that cannot be read from DOM text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why visual screenshot is needed"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_text",
            "description": "Read the visible text of the page (or a described section/element) so you can reason about it. Use this instead of guessing what's on the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Optional section or element to extract (e.g. 'search results' or 'header'). Pass empty string '' to read the entire page.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Call this when the goal has been accomplished. Summarize the outcome.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Call this when you need a human: payment details, a CAPTCHA/login wall, or any step you should never do autonomously.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
]

TERMINAL_TOOLS = {"done", "ask_user"}


class ToolExecutionError(RuntimeError):
    pass


class BrowserTools:
    """
    Executes tool calls against a live Playwright page. Instantiate with a
    BrowserSession's page; call .execute(tool_name, args) from the agent loop.
    """

    def __init__(self, session: Any):
        self._session = session  # BrowserSession

    @property
    def page(self) -> Any:
        return self._session.active_page()

    # -- element resolution ----------------------------------------------

    def _locate(self, description: str):
        """
        Try multiple accessibility-first and semantic strategies, with suffix normalization.
        Returns a Playwright Locator resolved to the best matching element.
        """
        import re
        page = self.page

        # Clean query: strip leading articles and trailing element type words
        clean_desc = re.sub(r"^(the|a|an)\s+", "", description, flags=re.IGNORECASE).strip()
        stripped_desc = re.sub(r"\s+(button|btn|link|input|textbox|text box|tab|icon|field)$", "", clean_desc, flags=re.IGNORECASE).strip()

        query_variants = [description, clean_desc, stripped_desc]
        seen_queries = list(dict.fromkeys(q for q in query_variants if q))

        for q in seen_queries:
            strategies = [
                lambda query=q: page.get_by_role("button", name=query, exact=False),
                lambda query=q: page.locator(f"input[type='submit'][value*='{query}' i], input[type='button'][value*='{query}' i]"),
                lambda query=q: page.locator(f"#add-to-cart-button, #buy-now-button, [name='submit.add-to-cart'], button:has-text('{query}')"),
                lambda query=q: page.get_by_role("link", name=query, exact=False),
                lambda query=q: page.locator(f"a:has-text('{query}')"),
                lambda query=q: page.get_by_label(query, exact=False),
                lambda query=q: page.locator(f"[aria-label*='{query}' i]"),
                lambda query=q: page.get_by_placeholder(query, exact=False),
                lambda query=q: page.locator(f"[title*='{query}' i]"),
                lambda query=q: page.get_by_text(query, exact=False),
            ]
            for strategy in strategies:
                try:
                    loc = strategy()
                    count = loc.count()
                    if count >= 1:
                        # Find the first visible one if possible
                        for i in range(min(count, 5)):
                            candidate = loc.nth(i)
                            if candidate.is_visible():
                                return candidate
                        return loc.first
                except Exception:
                    continue

        raise ToolExecutionError(
            f"Could not find an element matching '{description}'. "
            f"Try extract_text to inspect the page or specify the exact button/link text."
        )

    # -- tools --------------------------------------------------------------

    def navigate(self, url: str) -> Dict[str, Any]:
        page = self.page
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return self._post_action_snapshot(f"Navigated to {page.url}")

    def click(self, description: str) -> Dict[str, Any]:
        loc = self._locate(description)
        try:
            loc.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass
        try:
            loc.click(timeout=4000)
        except Exception:
            try:
                loc.click(timeout=2000, force=True)
            except Exception:
                loc.evaluate("el => el.click()")
        self.page.wait_for_timeout(500)
        return self._post_action_snapshot(f"Clicked '{description}'")

    def type_text(self, description: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
        loc = self._locate(description)
        loc.fill(text, timeout=5000)
        if press_enter:
            loc.press("Enter")
            self.page.wait_for_timeout(800)
        return self._post_action_snapshot(f"Typed into '{description}'")

    def click_by_coordinates(self, x: int, y: int, description: str = "") -> Dict[str, Any]:
        # Clamp to the viewport so a hallucinated coordinate can't click off-page.
        clamped_x = max(0, min(int(x), 1280))
        clamped_y = max(0, min(int(y), 800))
        self.page.mouse.click(clamped_x, clamped_y)
        self.page.wait_for_timeout(400)
        return self._post_action_snapshot(f"Clicked coordinates ({clamped_x},{clamped_y}) for: {description}")

    def scroll(self, direction: str) -> Dict[str, Any]:
        dy = 600 if direction == "down" else -600
        self.page.mouse.wheel(0, dy)
        self.page.wait_for_timeout(300)
        return self._post_action_snapshot(f"Scrolled {direction}")

    def extract_text(self, description: Optional[str] = None) -> Dict[str, Any]:
        page = self.page
        try:
            desc = (description or "").strip()
            if desc and desc.lower() not in ("null", "none", "body", "page", "main", "all"):
                loc = self._locate(desc)
                tag = loc.evaluate("e => e.tagName.toLowerCase()")
                if tag in ("input", "textarea"):
                    text = loc.get_attribute("value") or loc.input_value() or ""
                else:
                    text = loc.inner_text(timeout=2500)
            else:
                # Prefer central content containers over raw header/footer clutter
                main_locators = [
                    "div.s-main-slot", "[role='main']", "main", "#centerCol", "#search",
                    "#content", "#main-content", "article", "body"
                ]
                text = ""
                for sel in main_locators:
                    try:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            raw = loc.first.inner_text(timeout=1500)
                            if raw and len(raw.strip()) > 50:
                                text = raw
                                break
                    except Exception:
                        continue
                if not text:
                    text = page.locator("body").inner_text(timeout=2000)
        except Exception as ex:
            text = f"(could not extract text: {ex})"

        # Clean excessive whitespace and compress into compact token-efficient representation
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines[:60])  # limit to top 60 relevant lines
        return {"url": page.url, "title": page.title(), "text": cleaned[:2000]}

    def screenshot(self, reason: str = "") -> Dict[str, Any]:
        """Capture a live screenshot and return base64 image data for multimodal visual reasoning."""
        import base64
        page = self.page
        try:
            bytes_data = page.screenshot()
            b64_str = base64.b64encode(bytes_data).decode("utf-8")
            return {
                "screenshot_url": f"data:image/png;base64,{b64_str}",
                "note": f"Captured screenshot ({len(bytes_data)} bytes) for reason: {reason}",
                "url": page.url,
            }
        except Exception as ex:
            return {"error": f"Failed to take screenshot: {ex}"}

    # -- shared post-action bookkeeping --------------------------------------

    def _post_action_snapshot(self, note: str) -> Dict[str, Any]:
        """
        Every tool result carries the same safety-relevant snapshot so the
        agent loop can react uniformly.
        """
        page = self.page
        url_challenge = url_looks_challenged(page.url)
        dom_challenge = None if url_challenge else detect_challenges(page)
        challenge = url_challenge or dom_challenge
        return {
            "note": note,
            "url": page.url,
            "title": page.title(),
            "challenge_detected": challenge,
        }
