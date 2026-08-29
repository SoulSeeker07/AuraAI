"""
Unit tests for AppContextRouter (M33)
Location: tests/routing/test_app_context_router.py

Covers:
  - AppContext creation and property inspection
  - Per-app capability mapping for Explorer, Chrome, and VS Code
  - Targetless pure-navigation verb classification (0 vision tokens fast-path)
  - Generic desktop fallback for unrecognized apps
"""

import pytest
from routing.app_context_router import AppContextRouter, AppContext


@pytest.fixture
def router():
    AppContextRouter.reset_instance()
    r = AppContextRouter.get_instance()
    yield r
    AppContextRouter.reset_instance()


class TestAppContextRouter:
    def test_explorer_verb_routing(self, router):
        ctx = AppContext(app_name="explorer.exe", window_handle=1001, window_title="Downloads")
        cap, risk = router.resolve_verb("open", ctx)
        assert cap == "file.open"
        assert risk == "LOW"

        cap_del, risk_del = router.resolve_verb("delete", ctx)
        assert cap_del == "file.delete"
        assert risk_del == "HIGH"

    def test_chrome_verb_routing(self, router):
        ctx = AppContext(app_name="chrome.exe", window_handle=2002, window_title="Google Search", is_browser=True)
        cap_click, risk_click = router.resolve_verb("click", ctx)
        assert cap_click == "browser.click"
        assert risk_click == "LOW"

        cap_scroll, risk_scroll = router.resolve_verb("scroll_down", ctx)
        assert cap_scroll == "browser.scroll_down"
        assert risk_scroll == "LOW"

    def test_vscode_verb_routing(self, router):
        ctx = AppContext(app_name="code.exe", window_handle=3003, window_title="main.py - AuraAI")
        cap_run, risk_run = router.resolve_verb("run", ctx)
        assert cap_run == "terminal.run"
        assert risk_run == "HIGH"

        cap_fix, risk_fix = router.resolve_verb("fix", ctx)
        assert cap_fix == "coding.synthesize_fix"
        assert risk_fix == "HIGH"

    def test_targetless_navigation_classification(self, router):
        assert router.is_targetless_verb("scroll") is True
        assert router.is_targetless_verb("scroll_down") is True
        assert router.is_targetless_verb("back") is True
        assert router.is_targetless_verb("navigate_up") is True
        assert router.is_targetless_verb("click") is False
        assert router.is_targetless_verb("open") is False

    def test_fallback_unrecognized_app(self, router):
        ctx = AppContext(app_name="notepad.exe", window_handle=4004, window_title="Untitled - Notepad")
        cap, risk = router.resolve_verb("save", ctx)
        assert cap == "input.hotkey_save"
        assert risk == "LOW"
