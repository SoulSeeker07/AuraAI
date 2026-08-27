"""
browser_session.py

ONE place that launches, owns, and closes a Playwright browser context.

Previously this launch logic (persistent context, profile sync, chrome
args, fallback to non-persistent launch) was copy-pasted three times:
autonomous_browser.py::_execute_playwright_sync,
vision_loop.py::_run_sync, and engine.py::BrowserEngine.start (async
variant). Every tool, every tier, every workflow now gets its `page`
from here instead of relaunching a browser.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BrowserSession:
    """
    Context-manager wrapper around a single persistent Playwright Chromium
    context. Use it like:

        with BrowserSession() as session:
            session.page.goto("https://example.com")
            ... pass session.page around to tools ...

    Only one of these should be alive at a time for a given goal — no more
    "which of three engines actually owns the browser right now" confusion.
    """

    def __init__(self, headless: Optional[bool] = None):
        self.headless = (
            headless
            if headless is not None
            else os.getenv("AURA_BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes")
        )
        self._playwright = None
        self._context = None
        self.page: Any = None

    def __enter__(self) -> "BrowserSession":
        import urllib.request
        from playwright.sync_api import sync_playwright

        channel = os.getenv("AURA_BROWSER_CHANNEL", "chrome")
        cdp_url = os.getenv("AURA_CHROME_CDP_URL", "http://127.0.0.1:9222")
        real_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
        target_profile = os.getenv("AURA_CHROME_PROFILE", "Default")

        common_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--test-type",
            "--window-size=1280,850",
            "--window-position=50,50",
        ]
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self._playwright = sync_playwright().start()

        # 1. Attempt connection to live open Chrome via CDP (highest fidelity, uses your live browser)
        try:
            with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=0.3) as resp:
                if resp.status == 200:
                    browser = self._playwright.chromium.connect_over_cdp(cdp_url)
                    self._context = browser.contexts[0] if browser.contexts else browser.new_context()
                    self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
                    logger.info("[BrowserSession] Connected directly to live Chrome via CDP (%s)", cdp_url)
                    return self
        except Exception:
            pass

        # 2. Sync and launch persistent profile directory (uses user's real Chrome profile & logins)
        user_data_dir = os.getenv(
            "AURA_CHROME_USER_DATA_DIR", str(Path.home() / ".aura" / "browser_profile")
        )
        if not os.getenv("AURA_CHROME_PROFILE"):
            try:
                from browser.profile_sync import discover_target_profile_dir
                target_profile = discover_target_profile_dir("sreekanta")
            except Exception:
                target_profile = "Default"
        else:
            target_profile = os.getenv("AURA_CHROME_PROFILE", "Default")

        try:
            from browser.profile_sync import sync_chrome_profile
            sync_chrome_profile(target_profile_dir=target_profile, aura_user_data_dir=Path(user_data_dir))
        except Exception as ex:
            logger.debug("[BrowserSession] Profile sync notice: %s", ex)

        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel=channel,
                headless=self.headless,
                viewport={"width": 1280, "height": 800},
                user_agent=user_agent,
                args=[f"--profile-directory={target_profile}"] + common_args,
            )
            logger.info("[BrowserSession] Launched persistent context using: %s (profile=%s)", user_data_dir, target_profile)
            self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
            return self
        except Exception as ex:
            logger.warning("[BrowserSession] Persistent context launch failed (%s), falling back to clean context", ex)

        # 3. Fallback to clean context if persistent directory is locked
        try:
            browser = self._playwright.chromium.launch(channel=channel, headless=self.headless, args=common_args)
        except Exception:
            browser = self._playwright.chromium.launch(headless=self.headless, args=common_args)
        self._context = browser.new_context(viewport={"width": 1280, "height": 800}, user_agent=user_agent)
        self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self

    def active_page(self) -> Any:
        """Multi-tab resilience: always return the frontmost live page."""
        if not self._context:
            raise RuntimeError("Browser session has not been started.")
        pages = [p for p in self._context.pages if not p.is_closed()]
        if not pages:
            raise RuntimeError("All browser pages were closed.")
        if self.page is None or self.page.is_closed() or (len(pages) > 1 and self.page != pages[-1]):
            self.page = pages[-1]
            try:
                self.page.bring_to_front()
            except Exception:
                pass
        return self.page

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
