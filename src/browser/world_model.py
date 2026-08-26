"""
Browser Context & State Probe
Location: src/browser/world_model.py

Provides real-time inspection, rich context tracking, semantic tab grouping,
and resource ownership awareness (Aura vs User) for browser state across the OS.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from core.orchestration.ownership_tracker import (
    ResourceOwner,
    ResourceOwnershipTracker,
)

logger = logging.getLogger(__name__)


@dataclass
class BrowserTab:
    """Represents a single detected browser tab with rich state & ownership metadata."""

    tab_id: str
    title: str
    url: str = ""
    domain: str = ""
    browser_name: str = "generic"
    browser_pid: int = 0
    hwnd: int | None = None
    is_active: bool = False
    logged_in: bool = False
    owner: ResourceOwner = ResourceOwner.USER
    semantic_category: str = (
        "general"  # "documentation", "social", "shopping", "code", "entertainment", "general"
    )
    history: list[str] = field(default_factory=list)
    media_playing: bool = False
    shopping_cart: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tab_id": self.tab_id,
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "browser_name": self.browser_name,
            "browser_pid": self.browser_pid,
            "hwnd": self.hwnd,
            "is_active": self.is_active,
            "logged_in": self.logged_in,
            "owner": self.owner.value,
            "semantic_category": self.semantic_category,
            "history": self.history,
            "media_playing": self.media_playing,
            "shopping_cart": self.shopping_cart,
            "metadata": self.metadata,
        }


@dataclass
class BrowserContext:
    """Immutable representation of browser context and tab state across the OS."""

    running_browsers: list[str] = field(default_factory=list)
    open_tabs: list[BrowserTab] = field(default_factory=list)
    focused_tab: BrowserTab | None = None
    last_active_tab: BrowserTab | None = None

    def has_browser(self, browser_name: str = "") -> bool:
        """Check if any browser (or specific browser) is running."""
        if not self.running_browsers:
            return False
        if not browser_name:
            return True
        norm = browser_name.lower().replace(".exe", "").strip()
        return any(norm in b.lower() for b in self.running_browsers)

    def find_tabs(self, query: str) -> list[BrowserTab]:
        """Find open tabs matching domain, title, or query string."""
        q = query.lower().strip()
        matches: list[BrowserTab] = []
        for tab in self.open_tabs:
            if (
                q in tab.title.lower()
                or q in tab.domain.lower()
                or q in tab.url.lower()
            ):
                matches.append(tab)
        return matches

    def find_tabs_by_category(self, category: str) -> list[BrowserTab]:
        """Find open tabs matching a semantic category (e.g. 'documentation', 'shopping')."""
        cat = category.lower().strip()
        return [t for t in self.open_tabs if t.semantic_category.lower() == cat]

    def find_tabs_by_owner(self, owner: ResourceOwner) -> list[BrowserTab]:
        """Find open tabs owned by specified ResourceOwner (AURA vs USER)."""
        return [t for t in self.open_tabs if t.owner == owner]

    def has_tab(self, domain_or_keyword: str) -> bool:
        """Check if a tab for the domain or keyword is open."""
        return len(self.find_tabs(domain_or_keyword)) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "running_browsers": self.running_browsers,
            "open_tabs_count": len(self.open_tabs),
            "open_tabs": [t.to_dict() for t in self.open_tabs],
            "focused_tab": self.focused_tab.to_dict() if self.focused_tab else None,
            "last_active_tab": (
                self.last_active_tab.to_dict() if self.last_active_tab else None
            ),
        }


# Alias for backward compatibility
BrowserWorldModel = BrowserContext


class BrowserStateProbe:
    """
    State probe inspecting running browser processes, window titles, ownership, and semantic categories.
    """

    KNOWN_BROWSERS = {
        "chrome": "Google Chrome",
        "msedge": "Microsoft Edge",
        "firefox": "Mozilla Firefox",
        "brave": "Brave",
        "opera": "Opera",
        "vivaldi": "Vivaldi",
    }

    @classmethod
    def probe_state(cls, playwright_engine: Any = None) -> BrowserContext:
        """
        Probe OS environment and active Playwright engine to construct BrowserContext.
        """
        running_browsers: list[str] = []
        open_tabs: list[BrowserTab] = []
        focused_tab: BrowserTab | None = None
        ownership_tracker = ResourceOwnershipTracker.get_instance()

        # 1. Probe running process list via psutil
        try:
            import psutil

            for proc in psutil.process_iter(["name", "pid"]):
                pname = (
                    (proc.info.get("name") or "").lower().replace(".exe", "").strip()
                )
                for b_key in cls.KNOWN_BROWSERS:
                    if b_key in pname and b_key not in running_browsers:
                        running_browsers.append(b_key)
        except Exception as e:
            logger.debug(f"Process probe error: {e}")

        # 2. Probe window titles via Win32 API
        try:
            import win32gui
            import win32process

            foreground_hwnd = win32gui.GetForegroundWindow()

            def enum_window_callback(hwnd: int, extra: Any):
                nonlocal focused_tab
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return

                title_lower = title.lower()
                matched_browser = None
                for b_key, b_name in cls.KNOWN_BROWSERS.items():
                    if b_name.lower() in title_lower or b_key in title_lower:
                        matched_browser = b_key
                        break

                if matched_browser:
                    if matched_browser not in running_browsers:
                        running_browsers.append(matched_browser)

                    cleaned_title = title
                    for b_name in cls.KNOWN_BROWSERS.values():
                        cleaned_title = re.sub(
                            rf"\s*-\s*{re.escape(b_name)}$",
                            "",
                            cleaned_title,
                            flags=re.IGNORECASE,
                        )
                        cleaned_title = re.sub(
                            rf"\s*—\s*{re.escape(b_name)}$",
                            "",
                            cleaned_title,
                            flags=re.IGNORECASE,
                        )

                    domain = cls._infer_domain_from_title(cleaned_title)
                    category = cls._infer_semantic_category(cleaned_title, domain)
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)

                    tab_id = f"win_{hwnd}"
                    owner = ownership_tracker.get_owner("tab", tab_id)

                    tab = BrowserTab(
                        tab_id=tab_id,
                        title=cleaned_title.strip(),
                        url=f"https://www.{domain}" if domain else "",
                        domain=domain,
                        browser_name=matched_browser,
                        browser_pid=pid,
                        hwnd=hwnd,
                        is_active=(hwnd == foreground_hwnd),
                        owner=owner,
                        semantic_category=category,
                    )

                    open_tabs.append(tab)
                    if hwnd == foreground_hwnd:
                        focused_tab = tab

            win32gui.EnumWindows(enum_window_callback, None)

        except Exception as e:
            logger.debug(f"Win32 window probe error: {e}")

        # 3. Incorporate active Playwright engine tabs if available
        if (
            playwright_engine
            and getattr(playwright_engine, "is_active", False)
            and getattr(playwright_engine, "_context", None)
        ):
            try:
                pages = playwright_engine._context.pages
                for i, page in enumerate(pages):
                    p_title = page.url
                    domain = cls._infer_domain_from_title(page.url)
                    category = cls._infer_semantic_category(page.url, domain)
                    tab_id = f"pw_{i}"
                    owner = (
                        ownership_tracker.get_owner("tab", tab_id) or ResourceOwner.AURA
                    )

                    p_tab = BrowserTab(
                        tab_id=tab_id,
                        title=p_title,
                        url=page.url,
                        domain=domain,
                        browser_name="playwright",
                        is_active=(page == playwright_engine._page),
                        owner=owner,
                        semantic_category=category,
                    )
                    open_tabs.append(p_tab)
                    if "playwright" not in running_browsers:
                        running_browsers.append("playwright")
            except Exception as e:
                logger.debug(f"Playwright page probe error: {e}")

        return BrowserContext(
            running_browsers=running_browsers,
            open_tabs=open_tabs,
            focused_tab=focused_tab,
        )

    @staticmethod
    def _infer_domain_from_title(text: str) -> str:
        """Infer domain name from window or page title."""
        txt = text.lower().strip()
        if "instagram" in txt:
            return "instagram.com"
        elif "github" in txt:
            return "github.com"
        elif "chatgpt" in txt or "openai" in txt:
            return "chatgpt.com"
        elif "youtube" in txt:
            return "youtube.com"
        elif "amazon.in" in txt:
            return "amazon.in"
        elif "amazon" in txt:
            return "amazon.com" if "amazon.com" in txt else "amazon.in"
        elif "ebay" in txt:
            return "ebay.com"
        elif "flipkart" in txt:
            return "flipkart.com"
        elif "google" in txt:
            return "google.com"
        elif "linkedin" in txt:
            return "linkedin.com"
        elif "reddit" in txt:
            return "reddit.com"
        elif "." in txt and " " not in txt:
            return txt
        return ""

    @staticmethod
    def _infer_semantic_category(title: str, domain: str) -> str:
        """Infer semantic category (documentation, social, shopping, code, entertainment, general)."""
        txt = f"{title} {domain}".lower()
        if any(
            w in txt
            for w in [
                "doc",
                "docs",
                "documentation",
                "mdn",
                "python docs",
                "api reference",
                "manual",
                "guide",
            ]
        ):
            return "documentation"
        elif any(
            w in txt
            for w in ["amazon", "ebay", "flipkart", "shop", "cart", "store", "buy"]
        ):
            return "shopping"
        elif any(
            w in txt
            for w in ["instagram", "facebook", "twitter", "x.com", "linkedin", "reddit"]
        ):
            return "social"
        elif any(
            w in txt
            for w in ["github", "gitlab", "vscode", "stackoverflow", "stack overflow"]
        ):
            return "code"
        elif any(
            w in txt for w in ["youtube", "netflix", "spotify", "twitch", "prime video"]
        ):
            return "entertainment"
        return "general"
