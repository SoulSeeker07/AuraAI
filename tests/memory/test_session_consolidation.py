"""
Tests for M2 session consolidation pipeline:
  - _consolidate() calls long_term.store() only for policy-passing candidates
  - Policy-failing candidates are silently dropped
  - Consolidation failure (e.g. LTM error) never raises
  - Per-turn extraction is NOT called from add_assistant_turn()
  - close_session() idempotency: second call is a no-op
"""
import threading
import pytest
from unittest.mock import MagicMock, patch, call

from memory.manager.memory_manager import MemoryManager
from memory.manager.short_term_memory import Turn
from core.config import ENABLE_LONG_TERM_MEMORY


# ---------------------------------------------------------------------------
# Helper: build a MemoryManager with LTM enabled for consolidation tests
# ---------------------------------------------------------------------------

def _make_manager_with_ltm():
    """Returns a MemoryManager with a mocked LongTermMemory."""
    pm = MagicMock()
    mgr = MemoryManager(provider_manager=pm)
    # Inject a mock LongTermMemory regardless of ENABLE_LONG_TERM_MEMORY flag
    mgr.long_term = MagicMock()
    return mgr


# ---------------------------------------------------------------------------
# Test: _consolidate() applies policy and only stores approved facts
# ---------------------------------------------------------------------------

def test_consolidate_stores_approved_rejects_policy_failures():
    mgr = _make_manager_with_ltm()

    mgr.long_term.extract_candidates.return_value = [
        # Should pass policy
        {"fact": "User's favorite browser is Firefox", "topic": "preferences", "importance": 5},
        # Should fail policy (importance too low)
        {"fact": "User said hello", "topic": "general", "importance": 1},
        # Should fail policy (hard exclusion: password)
        {"fact": "User's password is hunter2", "topic": "security", "importance": 5},
    ]

    transcript = [
        Turn(role="user", content="My favorite browser is Firefox."),
        Turn(role="assistant", content="Got it, I'll remember that."),
    ]

    # Patch ENABLE_LONG_TERM_MEMORY so _consolidate() runs
    with patch("memory.manager.memory_manager.ENABLE_LONG_TERM_MEMORY", True):
        mgr._consolidate(transcript)

    # Only the first candidate should be stored
    mgr.long_term.store.assert_called_once_with(
        fact="User's favorite browser is Firefox",
        topic="preferences",
        importance=5,
    )


def test_consolidate_empty_transcript_is_no_op():
    mgr = _make_manager_with_ltm()
    with patch("memory.manager.memory_manager.ENABLE_LONG_TERM_MEMORY", True):
        mgr._consolidate([])
    mgr.long_term.extract_candidates.assert_not_called()


def test_consolidate_ltm_failure_does_not_raise():
    """Memory failure must never propagate to caller."""
    mgr = _make_manager_with_ltm()
    mgr.long_term.extract_candidates.side_effect = RuntimeError("LTM exploded")

    transcript = [Turn(role="user", content="test")]
    with patch("memory.manager.memory_manager.ENABLE_LONG_TERM_MEMORY", True):
        # Must NOT raise
        mgr._consolidate(transcript)


# ---------------------------------------------------------------------------
# Test: per-turn extraction is NOT called from add_assistant_turn()
# ---------------------------------------------------------------------------

def test_per_turn_extraction_removed():
    """
    add_assistant_turn() must NOT call extract_candidates() or extract_and_store()
    on every reply (M2 regression guard).
    """
    mgr = _make_manager_with_ltm()

    with patch("memory.manager.memory_manager.ENABLE_LONG_TERM_MEMORY", True):
        mgr.add_user_turn("Hello Aura")
        mgr.add_assistant_turn("Hi there!", user_text="Hello Aura")
        mgr.add_user_turn("What can you do?")
        mgr.add_assistant_turn("I can help with many things.", user_text="What can you do?")

    # extract_candidates must NOT have been called per-turn
    mgr.long_term.extract_candidates.assert_not_called()


# ---------------------------------------------------------------------------
# Test: close_session() idempotency
# ---------------------------------------------------------------------------

def test_close_session_idempotent():
    """
    Calling close_session() twice on the same session must trigger
    extract_candidates() exactly once.
    """
    mgr = _make_manager_with_ltm()
    mgr.long_term.extract_candidates.return_value = []

    mgr.add_user_turn("My favorite IDE is VS Code")
    mgr.add_assistant_turn("Good choice.")

    with patch("memory.manager.memory_manager.ENABLE_LONG_TERM_MEMORY", True):
        # First close — should trigger consolidation
        mgr.close_session()

        # Give the daemon thread a moment to complete
        threading.Event().wait(0.2)

        # Second close — should be a no-op
        mgr.close_session()

    # extract_candidates should have been called exactly once
    assert mgr.long_term.extract_candidates.call_count == 1, (
        f"extract_candidates called {mgr.long_term.extract_candidates.call_count} times "
        f"— expected 1 (idempotency violation)"
    )


def test_close_session_empty_buffer_is_no_op():
    mgr = _make_manager_with_ltm()
    with patch("memory.manager.memory_manager.ENABLE_LONG_TERM_MEMORY", True):
        mgr.close_session()   # nothing in buffer
    mgr.long_term.extract_candidates.assert_not_called()


# ---------------------------------------------------------------------------
# Test: timeout expiry triggers consolidation via add_user_turn()
# ---------------------------------------------------------------------------

def test_timeout_expiry_triggers_consolidation():
    """
    When ShortTermMemory expires on add_user_turn(), _consolidate() must be
    called with the previous session's transcript.
    """
    pm = MagicMock()
    mgr = MemoryManager(provider_manager=pm, short_term_kwargs={"session_timeout": 0.01})
    mgr.long_term = MagicMock()
    mgr.long_term.extract_candidates.return_value = []

    import time
    mgr.add_user_turn("First session message")
    mgr.add_assistant_turn("Response")

    # Wait for timeout to expire
    time.sleep(0.05)

    with patch("memory.manager.memory_manager.ENABLE_LONG_TERM_MEMORY", True):
        with patch.object(mgr, "_consolidate", wraps=mgr._consolidate) as mock_consolidate:
            mgr.add_user_turn("New session starts here")
            # Give thread time to dispatch
            threading.Event().wait(0.1)
            assert mock_consolidate.called, (
                "_consolidate() not called after session timeout expiry"
            )
