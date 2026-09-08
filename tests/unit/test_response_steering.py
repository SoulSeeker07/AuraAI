"""
Unit Tests for Response Steering Controller (response.steer)
Location: tests/unit/test_response_steering.py
"""

import time
import pytest
from src.voice.response_steering import (
    ActionType,
    ResponseSteeringController,
    SteerEvent,
    SteerPolicy,
)


def test_01_steer_policy_classification():
    """Verify that user interruptions are correctly classified into CANCEL, STEER, or NOOP."""
    # Cancels
    assert SteerPolicy.classify("stop") == ActionType.CANCEL
    assert SteerPolicy.classify("cancel") == ActionType.CANCEL
    assert SteerPolicy.classify("shut up") == ActionType.CANCEL
    assert SteerPolicy.classify("never mind") == ActionType.CANCEL
    assert SteerPolicy.classify("stop speaking") == ActionType.CANCEL

    # Steers: explicit high-confidence redirection
    assert SteerPolicy.classify("actually, focus on architecture") == ActionType.STEER
    assert SteerPolicy.classify("wait, only check security") == ActionType.STEER
    assert SteerPolicy.classify("don't check the whole thing, check tests instead") == ActionType.STEER
    assert SteerPolicy.classify("switch to python 3.12") == ActionType.STEER
    assert SteerPolicy.classify("change to dark mode") == ActionType.STEER
    assert SteerPolicy.classify("explain the database schema instead") == ActionType.STEER
    assert SteerPolicy.classify("wait, actually, no, do X instead") == ActionType.STEER
    assert SteerPolicy.classify("only show me the error logs") == ActionType.STEER

    # Pause: exact match on pause phrases
    assert SteerPolicy.classify("pause") == ActionType.PAUSE
    assert SteerPolicy.classify("hold on") == ActionType.PAUSE
    assert SteerPolicy.classify("hang on") == ActionType.PAUSE
    assert SteerPolicy.classify("wait a sec") == ActionType.PAUSE
    assert SteerPolicy.classify("wait a second") == ActionType.PAUSE
    assert SteerPolicy.classify("hold that thought") == ActionType.PAUSE

    # Resume: exact match on resume phrases
    assert SteerPolicy.classify("resume") == ActionType.RESUME
    assert SteerPolicy.classify("continue") == ActionType.RESUME
    assert SteerPolicy.classify("keep going") == ActionType.RESUME
    assert SteerPolicy.classify("go ahead") == ActionType.RESUME
    assert SteerPolicy.classify("unpause") == ActionType.RESUME

    # Steer vs Pause Boundary: Leading pause phrase with directive is STEER, not PAUSE
    assert SteerPolicy.classify("hold on, only check the database") == ActionType.STEER
    assert SteerPolicy.classify("wait, actually, no, do X instead") == ActionType.STEER

    # Fail-Closed / Filler-Only Guards: Conversational fillers without redirection MUST NOT steer
    assert SteerPolicy.classify("actually") == ActionType.CANCEL
    assert SteerPolicy.classify("wait") == ActionType.CANCEL
    assert SteerPolicy.classify("um") == ActionType.CANCEL

    # Ambiguous / non-directive statement fails closed to NOOP (treated as a standard new turn, not a mid-turn steer)
    assert SteerPolicy.classify("the sky is blue today") == ActionType.NOOP

    # Empty / whitespace
    assert SteerPolicy.classify("") == ActionType.NOOP
    assert SteerPolicy.classify("   ") == ActionType.NOOP


def test_02_response_steering_lifecycle():
    """Verify start_response, record_emitted_chunk, and complete_response state tracking."""
    controller = ResponseSteeringController()

    assert not controller.is_generating_or_speaking()

    controller.start_response("resp_101", "Explain how AI agents work")
    assert controller.is_generating_or_speaking()

    controller.record_emitted_chunk("First, you need to define the agent loop.")
    controller.record_emitted_chunk("Second, you connect tools.")

    emitted = controller.get_emitted_text()
    assert "First, you need to define the agent loop." in emitted
    assert "Second, you connect tools." in emitted

    controller.complete_response("resp_101")
    assert not controller.is_generating_or_speaking()


def test_03_steer_mid_generation_execution():
    """Verify mid-generation steering aborts output, snapshots emitted text, and compiles successor prompt."""
    aborted = []
    def _mock_abort():
        aborted.append(True)

    dispatched_events = []
    def _on_successor(event: SteerEvent, prompt: str):
        dispatched_events.append((event, prompt))

    controller = ResponseSteeringController(on_steer_successor=_on_successor)
    controller.start_response("resp_200", "Analyze all files in the project")
    controller.record_emitted_chunk("Scanning src directory.")
    controller.record_emitted_chunk("Found 50 Python files.")

    # User steers mid-generation
    steer_event = controller.steer(
        "Actually, only analyze the security files",
        on_abort_output=_mock_abort,
    )

    assert len(aborted) == 1
    assert steer_event is not None
    assert steer_event.action == ActionType.STEER
    assert steer_event.steering_input == "Actually, only analyze the security files"
    assert "Scanning src directory" in steer_event.emitted_context
    assert not controller.is_generating_or_speaking()

    assert len(dispatched_events) == 1
    event, prompt = dispatched_events[0]
    assert "Actually, only analyze the security files" in prompt
    assert "Scanning src directory" in prompt
    assert "Do not repeat what was already said" in prompt


def test_04_steer_hard_cancel_behavior():
    """Verify that a hard cancel ('stop') aborts output and returns None without creating a successor."""
    aborted = []
    controller = ResponseSteeringController()
    controller.start_response("resp_300", "Give me a long explanation")
    controller.record_emitted_chunk("Here is part one.")

    event = controller.steer("stop", on_abort_output=lambda: aborted.append(True))
    assert len(aborted) == 1
    assert event is None  # Cancel should not produce a steering successor
    assert not controller.is_generating_or_speaking()


def test_05_voice_turn_pause_and_resume_lifecycle():
    """Verify pause_current_turn holds playback and resume_current_turn continues without cancellation."""
    controller = ResponseSteeringController()
    turn = controller.start_response("resp_400", "Long technical explanation")

    assert not controller.is_paused()
    assert turn.wait_if_paused(timeout=0.01) is True

    # Pause turn
    ok = controller.pause_current_turn(timeout_s=10.0)
    assert ok is True
    assert controller.is_paused()
    assert turn.is_paused() is True
    assert turn.paused_at is not None
    assert turn.wait_if_paused(timeout=0.01) is False

    # Resume turn
    ok = controller.resume_current_turn()
    assert ok is True
    assert not controller.is_paused()
    assert turn.is_paused() is False
    assert turn.paused_at is None
    assert turn.wait_if_paused(timeout=0.01) is True

    controller.complete_response("resp_400")
    assert not controller.is_generating_or_speaking()


def test_06_pause_watchdog_timeout_degrades_cleanly():
    """Verify that an unattended pause degrades cleanly via the watchdog timeout callback."""
    timed_out = []
    controller = ResponseSteeringController()
    turn = controller.start_response("resp_500", "Will be abandoned while paused")

    # Pause with a short 0.1s watchdog
    controller.pause_current_turn(timeout_s=0.1, on_timeout=lambda: timed_out.append(True))
    assert controller.is_paused()

    # Wait for watchdog to fire
    time.sleep(0.2)
    assert len(timed_out) == 1

    controller.complete_response("resp_500")


def test_07_steer_aborts_active_turn_and_prevents_stale_chunks():
    """Verify that steering an in-flight response immediately marks the active turn aborted and closes it."""
    controller = ResponseSteeringController()
    turn = controller.start_response("resp_600", "Explain neural architectures")
    controller.record_emitted_chunk("First, consider transformer attention.")

    assert turn.is_aborted is False
    assert controller.current_turn is turn

    aborted_output = []
    event = controller.steer(
        "Actually, explain database indexing instead",
        on_abort_output=lambda: aborted_output.append(True),
    )

    assert len(aborted_output) == 1, "Physical audio output must be aborted"
    assert event is not None
    assert event.action == ActionType.STEER
    assert turn.is_aborted is True, "Turn must be marked aborted so stream feeders break immediately"
    assert controller.current_turn is None, "Active turn reference must be detached"
    assert not controller.is_generating_or_speaking()

