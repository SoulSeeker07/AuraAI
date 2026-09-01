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

    def test_terminal_and_powershell_routing(self, router):
        ctx_wt = AppContext(app_name="windowsterminal.exe", window_handle=5001, window_title="PowerShell 7")
        cap, risk = router.resolve_verb("run", ctx_wt)
        assert cap == "terminal.run"
        assert risk == "HIGH"

        cap_clr, _ = router.resolve_verb("clear", ctx_wt)
        assert cap_clr == "terminal.clear"

        ctx_ps = AppContext(app_name="powershell.exe", window_handle=5002)
        cap_ps, _ = router.resolve_verb("execute", ctx_ps)
        assert cap_ps == "terminal.run"

    def test_slack_and_spotify_routing(self, router):
        ctx_slack = AppContext(app_name="slack.exe", window_handle=6001)
        cap_send, _ = router.resolve_verb("send", ctx_slack)
        assert cap_send == "slack.send_message"

        ctx_spot = AppContext(app_name="spotify.exe", window_handle=6002)
        cap_play, _ = router.resolve_verb("play", ctx_spot)
        assert cap_play == "audio.play"
        cap_vol, _ = router.resolve_verb("volume_up", ctx_spot)
        assert cap_vol == "audio.volume_up"

    def test_cross_app_intent_detection(self, router):
        # 1. Direct switch
        is_cross, src, tgt = router.detect_cross_app_intent("switch to Chrome and search", current_app="code.exe")
        assert is_cross is True
        assert src == "code.exe"
        assert tgt == "chrome.exe"

        # 2. "in <app>, <action>"
        is_cross2, src2, tgt2 = router.detect_cross_app_intent("in VS Code, run tests", current_app="chrome.exe")
        assert is_cross2 is True
        assert tgt2 == "code.exe"

        # 3. Cross-app upload/paste transfer
        is_cross3, _, tgt3 = router.detect_cross_app_intent("paste to Discord", current_app="explorer.exe")
        assert is_cross3 is True
        assert tgt3 == "discord.exe"

        # 4. Intra-app non-cross intent
        is_cross4, _, _ = router.detect_cross_app_intent("scroll down and click link", current_app="chrome.exe")
        assert is_cross4 is False
