"""
Unit tests for MacroCompiler (M34)
Location: tests/execution/test_macro_compiler.py

Covers:
  - Sequence hash computation at the step-signature level
  - 3-run identical sequence promotion threshold (>= 0.90 confidence)
  - Non-promotion when DAG step signatures differ
  - Pre-flight live element signature verification
  - Fail-closed MacroDriftError on signature mismatch
  - Workspace scoping isolation (Project X vs Project Y)
"""

from unittest.mock import MagicMock, patch
import pytest

from execution.macro_compiler import (
    MacroCompiler,
    MacroStep,
    CompiledMacro,
    MacroDriftError,
    PROMOTION_SUCCESS_THRESHOLD,
    PROMOTION_CONFIDENCE_THRESHOLD,
)


@pytest.fixture
def compiler():
    MacroCompiler.reset_instance()
    comp = MacroCompiler.get_instance()
    yield comp
    MacroCompiler.reset_instance()


def _make_step(action: str, label: str, x: int = 100, y: int = 200) -> MacroStep:
    return MacroStep(
        action_type=action,
        target_signature={"control_type": "Button", "label": label, "center": (x, y)},
        parameters={"x": x, "y": y},
        fallback_selector=f"#{label.lower().replace(' ', '_')}",
    )


class TestMacroPromotion:
    def test_promotion_on_3_identical_traces(self, compiler):
        steps = [_make_step("click", "Run Tests"), _make_step("click", "View Results")]

        # Run 1
        m1 = compiler.record_trace("run my tests", "code.exe", "D:/Projects/AppA", steps, 0.95)
        assert m1 is None  # Not yet promoted

        # Run 2
        m2 = compiler.record_trace("run my tests", "code.exe", "D:/Projects/AppA", steps, 0.92)
        assert m2 is None  # Not yet promoted

        # Run 3 -> Promoted!
        m3 = compiler.record_trace("run my tests", "code.exe", "D:/Projects/AppA", steps, 0.94)
        assert m3 is not None
        assert isinstance(m3, CompiledMacro)
        assert m3.intent_pattern == "run my tests"
        assert m3.app_name == "code.exe"
        assert m3.success_count == 3
        assert len(m3.steps) == 2

    def test_no_promotion_when_step_signatures_differ(self, compiler):
        steps_a = [_make_step("click", "Button A")]
        steps_b = [_make_step("click", "Button B")]  # Different step signature!

        compiler.record_trace("click button", "chrome.exe", "global", steps_a, 0.95)
        compiler.record_trace("click button", "chrome.exe", "global", steps_b, 0.95)
        m3 = compiler.record_trace("click button", "chrome.exe", "global", steps_a, 0.95)

        # Should NOT promote because 3 consecutive runs did not have identical step signatures
        assert m3 is None

    def test_workspace_scoping_prevents_leakage(self, compiler):
        steps = [_make_step("click", "Deploy")]
        for _ in range(3):
            compiler.record_trace("deploy app", "code.exe", "D:/Projects/ProjectA", steps, 0.95)

        # In ProjectA -> resolves
        res_a = compiler.resolve_macro("deploy app", "code.exe", "D:/Projects/ProjectA")
        assert res_a is not None

        # In ProjectB -> should NOT resolve!
        res_b = compiler.resolve_macro("deploy app", "code.exe", "D:/Projects/ProjectB")
        assert res_b is None


class TestPreflightAndExecution:
    def test_preflight_success_executes_macro(self, compiler):
        steps = [_make_step("click", "Submit")]
        macro = CompiledMacro(
            macro_id="macro_101",
            intent_pattern="submit form",
            app_name="chrome.exe",
            workspace_scope="global",
            steps=steps,
            sequence_hash="hash123",
        )

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_visible.return_value = True
        mock_page.locator.return_value.first = mock_elem
        mock_context.page = mock_page

        success = compiler.execute_macro(macro, mock_context)
        assert success is True
        mock_page.click.assert_called_once_with("#submit")

    def test_preflight_mismatch_raises_drift_error(self, compiler):
        steps = [_make_step("click", "Missing Button")]
        macro = CompiledMacro(
            macro_id="macro_102",
            intent_pattern="click missing",
            app_name="chrome.exe",
            workspace_scope="global",
            steps=steps,
            sequence_hash="hash456",
        )

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_visible.return_value = False  # UI drifted!
        mock_page.locator.return_value.first = mock_elem
        mock_context.page = mock_page

        with pytest.raises(MacroDriftError) as exc_info:
            compiler.execute_macro(macro, mock_context)

        assert "UI drift detected" in str(exc_info.value)
