"""
E2E Multi-Turn Regression Tests for Vision Dictation (M33)
Location: tests/regression/test_vision_dictation_e2e.py

Comprehensive regression scenarios covering cross-app transitions,
referential memory decay, targetless navigation preservation, and
fail-closed edge cases:
  1. Full multi-turn flow across Explorer -> Chrome -> VS Code
  2. Alternative correction slot invalidation on app switch
  3. Targetless navigation preserving visual memory for subsequent actions
  4. Unknown app graceful fallback and Tier-3 fail-closed behavior
"""

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from core.visual_memory import VisualWorkingMemory
from routing.app_context_router import AppContextRouter, AppContext
from vision.grounding_engine import GroundingEngine, GroundedTarget


def _make_mock_groq_response(text: str):
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    res = MagicMock()
    res.choices = [choice]
    return res


@pytest.fixture(scope="function")
def isolated_core(tmp_path):
    from core.aura_core import AuraCore
    from core.focus_manager import FocusManager

    AuraCore.reset_instance()
    FocusManager.reset_instance()
    VisualWorkingMemory.reset_instance()
    GroundingEngine.reset_instance()
    AppContextRouter.reset_instance()

    with (
        patch("groq.Groq") as MockGroq,
        patch.dict("os.environ", {"GROQ_API_KEY": "gsk_testdummykey1234567890"}),
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_groq_response("Acknowledged.")
        MockGroq.return_value = mock_client

        core = AuraCore(config={
            "project_root": str(tmp_path),
            "memory_db_path": str(tmp_path / "Memory.db"),
        })

        fm_db = tmp_path / "storage" / "focus_threads.db"
        fm_db.parent.mkdir(parents=True, exist_ok=True)
        FocusManager.reset_instance()
        core.focus_manager = FocusManager.get_instance(db_path=fm_db)

        yield core

    AuraCore.reset_instance()
    FocusManager.reset_instance()
    VisualWorkingMemory.reset_instance()
    GroundingEngine.reset_instance()
    AppContextRouter.reset_instance()


class TestVisionDictationE2E:
    def test_multi_turn_cross_app_dictation_flow(self, isolated_core):
        """Validates sequential dictation across 3 different foreground applications."""
        core = isolated_core
        vm = core.visual_memory
        router = core.app_context_router

        # --- Turn 1: Explorer context ---
        exp_ctx = AppContext(app_name="explorer.exe", window_handle=101, window_title="File Explorer")
        with patch.object(router, "detect_current_app", return_value=exp_ctx):
            t1 = GroundedTarget(label="report_final.docx", center=(200, 300), confidence=0.94, source_tier="tier1_a11y", app_name="explorer.exe")
            t2 = GroundedTarget(label="report_draft.docx", center=(200, 350), confidence=0.89, source_tier="tier1_a11y", app_name="explorer.exe")
            vm.remember([t1, t2], task_id="default", app_name="explorer.exe")

            # --- Turn 2: Referential "open that" ---
            augmented = core._vision_dictation_preamble("open that file")
            assert "report_final.docx" in augmented
            assert "(200, 300)" in augmented

            # --- Turn 3: Verbal correction "no, the other one" ---
            corrected = core._vision_dictation_preamble("no, the other one")
            assert "report_draft.docx" in corrected
            assert "(200, 350)" in corrected

        # --- Turn 4: Chrome Navigation Fast-Path ---
        chrome_ctx = AppContext(app_name="chrome.exe", window_handle=202, window_title="Documentation - Chrome", is_browser=True)
        with patch.object(router, "detect_current_app", return_value=chrome_ctx):
            nav_goal = core._vision_dictation_preamble("scroll down")
            assert nav_goal == "scroll down"

        # --- Turn 5: VS Code Context with High-Risk Action ---
        vscode_ctx = AppContext(app_name="code.exe", window_handle=303, window_title="main.py - Visual Studio Code")
        with patch.object(router, "detect_current_app", return_value=vscode_ctx):
            t_code = GroundedTarget(label="main.py", center=(500, 400), confidence=0.96, source_tier="tier1_a11y", app_name="code.exe")
            vm.remember([t_code], task_id="default", app_name="code.exe")

            run_goal = core._vision_dictation_preamble("run it")
            assert "main.py" in run_goal
            cap, risk = router.resolve_verb("run", vscode_ctx)
            assert cap == "terminal.run"
            assert risk == "HIGH"

    def test_alternative_slot_invalidated_on_app_switch(self, isolated_core):
        """
        Switching foreground apps must clear the _last_alternative slot so saying
        'no, the other one' in a new app does not trigger an action on the old app's target.
        """
        core = isolated_core
        vm = core.visual_memory
        router = core.app_context_router

        # In Explorer: two candidates remembered
        exp_ctx = AppContext(app_name="explorer.exe", window_handle=101, window_title="Downloads")
        with patch.object(router, "detect_current_app", return_value=exp_ctx):
            t1 = GroundedTarget(label="setup.exe", center=(150, 200), confidence=0.95, source_tier="tier1_a11y", app_name="explorer.exe")
            t2 = GroundedTarget(label="setup_beta.exe", center=(150, 250), confidence=0.88, source_tier="tier1_a11y", app_name="explorer.exe")
            vm.remember([t1, t2], task_id="default", app_name="explorer.exe")

        # Switch to VS Code
        code_ctx = AppContext(app_name="code.exe", window_handle=303, window_title="VS Code")
        with patch.object(router, "detect_current_app", return_value=code_ctx):
            # Apply app switch decay
            vm.decay_on_app_switch(previous_app="explorer.exe", new_app="code.exe", task_id="default")
            # In VS Code, saying 'no, the other one' must NOT resolve setup_beta.exe
            res = core._vision_dictation_preamble("no, the other one")
            assert "setup_beta.exe" not in res

    def test_targetless_navigation_preserves_visual_memory(self, isolated_core):
        """
        Targetless navigation (e.g. 'scroll down') should NOT clobber visual working
        memory so a subsequent 'click that' still resolves the remembered button.
        """
        core = isolated_core
        vm = core.visual_memory
        router = core.app_context_router

        chrome_ctx = AppContext(app_name="chrome.exe", window_handle=202, window_title="Store - Chrome", is_browser=True)
        with patch.object(router, "detect_current_app", return_value=chrome_ctx):
            t_button = GroundedTarget(label="Add to Cart", center=(800, 600), confidence=0.92, source_tier="tier1_dom", app_name="chrome.exe")
            vm.remember([t_button], task_id="default", app_name="chrome.exe")

            # Navigation turn (scroll down)
            nav = core._vision_dictation_preamble("scroll down")
            assert nav == "scroll down"

            # Subsequent targeted turn: memory should still hold 'Add to Cart'
            click_goal = core._vision_dictation_preamble("click that button")
            assert "Add to Cart" in click_goal
            assert "(800, 600)" in click_goal

    def test_unknown_app_and_tier3_fail_closed(self, isolated_core):
        """
        Validates that unknown applications resolve through default fallback and
        ungrounded targets fail closed gracefully without throwing exceptions.
        """
        core = isolated_core
        router = core.app_context_router
        ge = core.grounding_engine

        custom_ctx = AppContext(app_name="custom_tool.exe", window_handle=999, window_title="Internal Tool")
        with (
            patch.object(router, "detect_current_app", return_value=custom_ctx),
            patch.object(ge, "resolve", return_value=None),
        ):
            # Targeted request for an element that cannot be grounded
            goal = core._vision_dictation_preamble("open imaginary_widget")
            # Should fail closed and return original user goal unchanged
            assert goal == "open imaginary_widget"

            # Verb resolution falls back to default map
            cap, risk = router.resolve_verb("open", custom_ctx)
            assert cap == "app.open"
            assert risk == "LOW"
