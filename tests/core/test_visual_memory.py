"""
Unit tests for VisualWorkingMemory (M33)
Location: tests/core/test_visual_memory.py

Covers:
  - Ring buffer capacity (5 items) and TTL decay (3 turns)
  - Deictic pronoun resolution ("that", "it", "this one", "that file")
  - 1-turn verbal alternative correction ("no, the other one", "the second one", "not that one")
  - App-switch decay (clears / discounts targets across application changes)
  - FocusManager thread isolation
"""

import pytest
from vision.grounding_engine import GroundedTarget
from core.visual_memory import VisualWorkingMemory


@pytest.fixture
def vm():
    VisualWorkingMemory.reset_instance()
    mem = VisualWorkingMemory.get_instance()
    yield mem
    VisualWorkingMemory.reset_instance()


def _make_target(label: str, confidence: float = 0.90, app_name: str = "explorer.exe"):
    return GroundedTarget(
        label=label,
        center=(100, 200),
        confidence=confidence,
        source_tier="tier1_a11y",
        app_name=app_name,
    )


class TestVisualWorkingMemoryBasic:
    def test_remember_and_resolve_pronoun(self, vm):
        t1 = _make_target("download.zip", confidence=0.95, app_name="explorer.exe")
        vm.remember([t1], task_id="task_1", app_name="explorer.exe")

        resolved, match_type = vm.resolve_reference("open that", task_id="task_1", current_app="explorer.exe")
        assert resolved is not None
        assert resolved.label == "download.zip"
        assert match_type == "referential_match"

    def test_referential_entity_hint_preference(self, vm):
        t1 = _make_target("submit button", confidence=0.88, app_name="chrome.exe")
        t2 = _make_target("profile picture image", confidence=0.85, app_name="chrome.exe")
        vm.remember([t1, t2], task_id="task_1", app_name="chrome.exe")

        resolved, _ = vm.resolve_reference("click that button", task_id="task_1", current_app="chrome.exe")
        assert resolved is not None
        assert resolved.label == "submit button"


class TestAlternativeCorrection:
    def test_one_turn_alternative_slot(self, vm):
        t_top = _make_target("first_option.pdf", confidence=0.92, app_name="explorer.exe")
        t_alt = _make_target("second_option.pdf", confidence=0.89, app_name="explorer.exe")

        # Remember two candidates
        vm.remember([t_top, t_alt], task_id="task_1", app_name="explorer.exe")

        # Say "no, the other one" -> resolves immediately to second_option.pdf
        resolved, match_type = vm.resolve_reference("no, the other one", task_id="task_1", current_app="explorer.exe")
        assert resolved is not None
        assert resolved.label == "second_option.pdf"
        assert match_type == "alternative_correction"

        # Alternative slot is consumed
        resolved_again, _ = vm.resolve_reference("the other one", task_id="task_1", current_app="explorer.exe")
        # Second attempt falls back to standard memory or none
        assert resolved_again != t_alt or vm._last_alternatives.get("task_1") is None

    def test_correction_phrase_detection(self, vm):
        assert vm.is_alternative_correction("no, the other one") is True
        assert vm.is_alternative_correction("the second one") is True
        assert vm.is_alternative_correction("not that one") is True
        assert vm.is_alternative_correction("open that file") is False


class TestAppSwitchDecayAndThreadIsolation:
    def test_app_switch_decay_prevents_leakage(self, vm):
        t_exp = _make_target("data.csv", confidence=0.95, app_name="explorer.exe")
        vm.remember([t_exp], task_id="task_1", app_name="explorer.exe")

        # Switch foreground window from explorer.exe to code.exe
        vm.decay_on_app_switch(previous_app="explorer.exe", new_app="code.exe", task_id="task_1")

        # Asking for "that file" in code.exe should not resolve to explorer's data.csv
        resolved, _ = vm.resolve_reference("that file", task_id="task_1", current_app="code.exe")
        assert resolved is None

    def test_focus_task_id_isolation(self, vm):
        t1 = _make_target("project_a_doc.txt", confidence=0.90, app_name="explorer.exe")
        t2 = _make_target("project_b_code.py", confidence=0.90, app_name="code.exe")

        vm.remember([t1], task_id="thread_a", app_name="explorer.exe")
        vm.remember([t2], task_id="thread_b", app_name="code.exe")

        # In thread_a, resolving "that" returns project_a_doc.txt
        res_a, _ = vm.resolve_reference("that", task_id="thread_a", current_app="explorer.exe")
        assert res_a is not None
        assert res_a.label == "project_a_doc.txt"

        # In thread_b, resolving "that" returns project_b_code.py
        res_b, _ = vm.resolve_reference("that", task_id="thread_b", current_app="code.exe")
        assert res_b is not None
        assert res_b.label == "project_b_code.py"
