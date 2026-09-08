"""
Unit & Integration Tests for ProceduralFailureLedger & Tier 2 Circuit Breaker
Location: tests/unit/test_procedural_failure_ledger.py

Validates:
1. Deterministic error normalization & fingerprint stability.
2. Tier 1 persistent SQLite storage, occurrence counts, and anti-pattern retrieval.
3. Tier 2 session-scoped circuit breaker (3 consecutive strikes -> escalation).
4. Countermeasure resolution and strike reset.
5. Strict isolation from ConsolidationEngine (failed sessions drop from positive memory).
6. Integration with UnifiedToolDispatcher circuit breaker tripping.
"""

import os
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from memory.procedural_failure_ledger import (
    ProceduralFailureLedger,
    FailureRecord,
    CircuitBreakerResult,
)
from memory.consolidation_engine import ConsolidationEngine
from memory.cognitive_memory import CognitiveMemoryEngine
from memory.models import MemoryItem


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_memory.db"


@pytest.fixture
def ledger(temp_db: Path) -> ProceduralFailureLedger:
    return ProceduralFailureLedger(db_path=temp_db, circuit_breaker_threshold=3)


def test_fingerprint_normalization_stability(ledger: ProceduralFailureLedger):
    """
    Ensure dynamic tokens (memory addresses, line numbers, Windows/POSIX paths, timestamps, UUIDs)
    normalize to identical canonical messages and fingerprints.
    """
    err_win_1 = (
        "FileNotFoundError: [Errno 2] No such file: 'C:\\Users\\Bob\\Workspace\\AuraAI\\app.py' "
        "at line 42 (0x7ffe42a1) [timestamp: 2026-09-08T10:00:00Z] session: 123e4567-e89b-12d3-a456-426614174000"
    )
    err_win_2 = (
        "FileNotFoundError: [Errno 2] No such file: 'D:\\Dev\\OtherPath\\server.py' "
        "at line 999 (0x000001B42) [timestamp: 2026-09-08T11:15:30Z] session: 987fcdeb-51a2-43f1-b987-123456789abc"
    )
    err_posix = (
        "FileNotFoundError: [Errno 2] No such file: '/var/www/aura/core.py' "
        "at line 10 (0x55aa12ff) [timestamp: 2026-09-08T12:00:00Z] session: 00000000-0000-0000-0000-000000000000"
    )

    t1, msg1, fp1 = ledger.normalize_error("edit_file", err_win_1)
    t2, msg2, fp2 = ledger.normalize_error("edit_file", err_win_2)
    t3, msg3, fp3 = ledger.normalize_error("edit_file", err_posix)

    assert t1 == "FileNotFoundError"
    assert t2 == "FileNotFoundError"
    assert t3 == "FileNotFoundError"

    # All three disparate errors collapse to the exact same canonical template and hash
    assert msg1 == msg2 == msg3
    assert fp1 == fp2 == fp3

    # Different tool or error type produces a different fingerprint
    _, _, fp_other_tool = ledger.normalize_error("read_file", err_win_1)
    assert fp_other_tool != fp1

    _, _, fp_other_err = ledger.normalize_error("edit_file", "PermissionError: Access denied")
    assert fp_other_err != fp1


def test_tier1_persistent_storage_and_occurrence_count(ledger: ProceduralFailureLedger):
    """Verify failure insertion, repeated occurrence incrementing, and anti-pattern prompt formatting."""
    fp = None
    for i in range(4):
        res = ledger.record_failure(
            tool_name="terminal_run_command",
            error=f"ProcessError: Command failed with exit code 1 at line {i} (0x{i:04x})",
            anti_pattern="Terminal command syntax was invalid",
            session_id="sess_1",
        )
        fp = res.fingerprint

    # Retrieve from DB
    records = ledger.get_anti_patterns(tool_name="terminal_run_command")
    assert len(records) == 1
    assert records[0].fingerprint == fp
    assert records[0].occurrence_count == 4
    assert records[0].tool_name == "terminal_run_command"
    assert records[0].resolved_at is None

    # Prompt block formatting
    prompt_block = ledger.format_anti_patterns_prompt(tool_name="terminal_run_command")
    assert "<procedural_anti_patterns>" in prompt_block
    assert "Terminal command syntax was invalid" in prompt_block
    assert "Failed 4 times" in prompt_block


def test_tier2_circuit_breaker_three_strike_escalation(ledger: ProceduralFailureLedger):
    """
    Verify ephemeral per-session circuit breaker:
    - Strikes 1 and 2: tripped=False, escalate_to_user=False
    - Strike 3: tripped=True, escalate_to_user=True
    - Independent session tracking
    """
    err = "TimeoutError: Operation timed out after 30s at line 10"

    # Turn 1
    r1 = ledger.record_failure("browser_navigate_and_read", err, session_id="sess_A")
    assert r1.strikes == 1
    assert not r1.tripped
    assert not r1.escalate_to_user

    # Turn 2
    r2 = ledger.record_failure("browser_navigate_and_read", err, session_id="sess_A")
    assert r2.strikes == 2
    assert not r2.tripped
    assert not r2.escalate_to_user

    # Turn 3 -> Trips circuit breaker!
    r3 = ledger.record_failure("browser_navigate_and_read", err, session_id="sess_A")
    assert r3.strikes == 3
    assert r3.tripped
    assert r3.escalate_to_user
    assert "Circuit breaker TRIPPED" in r3.message

    # Check is_circuit_breaker_tripped
    assert ledger.is_circuit_breaker_tripped("sess_A", fingerprint=r3.fingerprint)
    assert ledger.is_circuit_breaker_tripped("sess_A")

    # Session B is completely unaffected (isolated)
    r_b = ledger.record_failure("browser_navigate_and_read", err, session_id="sess_B")
    assert r_b.strikes == 1
    assert not r_b.tripped
    assert not ledger.is_circuit_breaker_tripped("sess_B")


def test_resolution_marking_and_strike_reset(ledger: ProceduralFailureLedger):
    """Verify recording countermeasure marks persistent record resolved and clears session strikes."""
    err = "PermissionError: [Errno 13] Permission denied: 'C:\\secret.txt'"
    res = ledger.record_failure("read_file", err, session_id="sess_test")
    assert res.strikes == 1
    fp = res.fingerprint

    # Resolve failure
    rows = ledger.record_resolution(
        tool_name="read_file",
        countermeasure="Checked file permissions and verified path is inside workspace",
        fingerprint=fp,
        session_id="sess_test",
    )
    assert rows == 1

    # Tier 2 strikes reset to 0
    assert ledger.get_strikes("sess_test", fp) == 0

    # Unresolved queries exclude it
    active_anti_patterns = ledger.get_anti_patterns(tool_name="read_file", include_resolved=False)
    assert len(active_anti_patterns) == 0

    # Resolved query includes it
    all_anti_patterns = ledger.get_anti_patterns(tool_name="read_file", include_resolved=True)
    assert len(all_anti_patterns) == 1
    assert all_anti_patterns[0].countermeasure is not None
    assert all_anti_patterns[0].resolved_at is not None


def test_consolidation_engine_anti_poisoning_isolation(temp_db: Path):
    """
    Crucial guardrail:
    - ConsolidationEngine drops failed sessions (returns []).
    - Cognitive memories table receives NO rows from failed executions.
    - ProceduralFailureLedger records the failure in its segregated table.
    """
    cog_engine = CognitiveMemoryEngine(db_path=temp_db)
    cons_engine = ConsolidationEngine()

    # Simulate a failed session
    failed_items = cons_engine.consolidate_session(
        session_id="sess_fail_1",
        goal="Run build and deploy",
        execution_success=False,
        observations=["Build error: syntax error in main.py:45"],
        data={"error": "SyntaxError"},
    )
    assert failed_items == []  # Dropped!

    for item in failed_items:
        cog_engine.store_memory(item)

    # cognitive_memories has 0 rows
    with cog_engine._connect() as conn:
        cog_count = conn.execute("SELECT count(*) as c FROM cognitive_memories").fetchone()["c"]
    assert cog_count == 0

    # Record into failure ledger instead
    cog_engine.record_failure(
        tool_name="terminal_run_command",
        error="SyntaxError: invalid syntax at line 45",
        session_id="sess_fail_1",
    )

    # cognitive_memories is STILL 0 (completely unpoisoned)
    with cog_engine._connect() as conn:
        cog_count_after = conn.execute("SELECT count(*) as c FROM cognitive_memories").fetchone()["c"]
    assert cog_count_after == 0

    # procedural_failures table has the failure recorded
    anti_patterns = cog_engine.get_anti_patterns()
    assert len(anti_patterns) == 1
    assert anti_patterns[0].tool_name == "terminal_run_command"


@pytest.mark.asyncio
async def test_unified_tool_dispatcher_circuit_breaker_integration(temp_db: Path):
    """
    Test UnifiedToolDispatcher integration:
    When a tool execution produces an error repeatedly, the failure ledger tracks strikes
    and trips the circuit breaker on the 3rd consecutive identical failure in that session.
    """
    from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher

    mock_memory = MagicMock()
    ledger = ProceduralFailureLedger(db_path=temp_db, circuit_breaker_threshold=3)
    mock_memory.failure_ledger = ledger

    mock_aura_core = MagicMock()
    mock_aura_core.memory = mock_memory

    mock_session = MagicMock()
    mock_session.session_id = "sess_dispatcher_test"

    # Mock _execute_tool_inner to simulate tool failure
    with patch.object(
        UnifiedToolDispatcher,
        "_execute_tool_inner",
        new=AsyncMock(side_effect=FileNotFoundError("File C:\\nonexistent.txt not found at line 12")),
    ):
        # Call 1
        res1 = await UnifiedToolDispatcher.dispatch(
            "read_file",
            {"path": "C:\\nonexistent.txt"},
            session=mock_session,
            aura_core=mock_aura_core,
        )
        assert res1["status"] == "error"
        assert not res1.get("circuit_breaker_tripped", False)

        # Call 2
        res2 = await UnifiedToolDispatcher.dispatch(
            "read_file",
            {"path": "C:\\nonexistent.txt"},
            session=mock_session,
            aura_core=mock_aura_core,
        )
        assert res2["status"] == "error"
        assert not res2.get("circuit_breaker_tripped", False)

        # Call 3 -> Circuit breaker trips!
        res3 = await UnifiedToolDispatcher.dispatch(
            "read_file",
            {"path": "C:\\nonexistent.txt"},
            session=mock_session,
            aura_core=mock_aura_core,
        )
        assert res3["status"] == "error"
        assert res3.get("circuit_breaker_tripped") is True
        assert res3.get("escalate_to_user") is True
        assert res3.get("strikes") == 3
        assert "Circuit breaker TRIPPED" in res3.get("circuit_breaker_message", "")


def test_context_formatter_with_anti_patterns():
    """Verify MemoryContextFormatter synthesizes <procedural_anti_patterns> tags."""
    from memory.context_formatter import MemoryContextFormatter

    formatter = MemoryContextFormatter()
    anti_patterns = [
        "Tool 'edit_file' failed with FileNotFoundError: File not found",
        "Tool 'terminal_run_command' failed with ProcessError: exit code 1",
    ]

    ctx = formatter.format_planning_context(
        recalled_memories=[],
        anti_patterns=anti_patterns,
    )
    assert "<procedural_anti_patterns>" in ctx
    assert "- Tool 'edit_file' failed with FileNotFoundError" in ctx
    assert "- Tool 'terminal_run_command' failed with ProcessError" in ctx


def test_ambient_context_builder_surfaces_anti_patterns(temp_db: Path):
    """Verify AmbientContextBuilder injects anti-patterns from failure ledger."""
    from core.context.ambient_context_builder import AmbientContextBuilder

    cog_engine = CognitiveMemoryEngine(db_path=temp_db)
    cog_engine.record_failure(
        tool_name="edit_file",
        error="PermissionError: Cannot write to read-only file",
        session_id="sess_ambient_test",
    )

    mock_aura_core = MagicMock()
    mock_memory = MagicMock()
    mock_memory.failure_ledger = cog_engine.failure_ledger
    mock_memory.cognitive = cog_engine
    mock_memory.get_relevant_facts.return_value = []
    mock_aura_core.memory = mock_memory
    mock_aura_core.embedding_warmup = None
    mock_aura_core.speculative_indexer = None

    context = AmbientContextBuilder.build_ambient_context(aura_core=mock_aura_core, query="Can you edit file?")
    assert "<procedural_anti_patterns>" in context
    assert "Tool 'edit_file'" in context
    assert "PermissionError" in context


def test_master_orchestrator_stage7_records_failure_and_resolution(temp_db: Path):
    """Verify MasterOrchestrator._write_memory records failures and resolutions to failure ledger."""
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.orchestration.agent_session import AgentSession
    from core.planning.execution_result import ExecutionResult

    orch = MasterOrchestrator.get_instance()
    orch.memory_db_path = str(temp_db)

    # Initialize Memory with our temp db
    from Memory import Memory
    mem = Memory(db_path=temp_db)

    # 1. Failed execution result
    session_fail = AgentSession(goal="Fix bug in compiler", session_id="sess_orch_fail")
    res_fail = ExecutionResult(
        success=False,
        goal="Fix bug in compiler",
        observations=["Error on line 52: unresolved import"],
        planner="autonomous_planner",
    )

    orch._write_memory(session_fail, res_fail)

    # Verify failure recorded in ledger
    anti_patterns = mem.cognitive.failure_ledger.get_anti_patterns(tool_name="autonomous_planner")
    assert len(anti_patterns) == 1
    assert anti_patterns[0].occurrence_count == 1
    assert anti_patterns[0].resolved_at is None

    # 2. Succeeded execution result resolves it
    session_succ = AgentSession(goal="Fix bug in compiler", session_id="sess_orch_succ")
    res_succ = ExecutionResult(
        success=True,
        goal="Fix bug in compiler",
        observations=["All imports resolved"],
        planner="autonomous_planner",
    )

    orch._write_memory(session_succ, res_succ)

    # Verify resolved
    active_after = mem.cognitive.failure_ledger.get_anti_patterns(tool_name="autonomous_planner", include_resolved=False)
    assert len(active_after) == 0

    all_after = mem.cognitive.failure_ledger.get_anti_patterns(tool_name="autonomous_planner", include_resolved=True)
    assert len(all_after) == 1
    assert all_after[0].resolved_at is not None

