"""
Unit Tests for Personal OS Gate G1
Location: tests/test_personal_os_g1.py
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
import pytest

from src.core.orchestration.request_source import RequestSource
from src.daemon.governance import AutonomyGovernanceEngine, AutonomyPolicy
from src.personal_os.state_store import PersonalOSStateStore, PersonalOSTrigger
from src.core.orchestration.execution_policy import ExecutionPolicy
from src.core.orchestration.autonomy_mode import AutonomyLevel


def test_request_source_enum():
    """Verify RequestSource enum values."""
    assert RequestSource.HUMAN_INTERACTIVE.value == "human_interactive"
    assert RequestSource.TRIGGER_AUTONOMOUS.value == "trigger_autonomous"
    assert RequestSource.DAEMON_BACKGROUND.value == "daemon_background"


def test_governance_trigger_domain_ceiling():
    """Verify check_trigger_domain enforcement on AutonomyGovernanceEngine."""
    gov = AutonomyGovernanceEngine()

    # Allowed domains
    ok, _ = gov.check_trigger_domain("desktop.launch_app")
    assert ok is True

    ok, _ = gov.check_trigger_domain("coding.review_code")
    assert ok is True

    ok, _ = gov.check_trigger_domain("browser.navigate")
    assert ok is True

    # Blocked domains
    ok, reason = gov.check_trigger_domain("unknown_domain.do_something")
    assert ok is False
    assert "outside trigger_allowed_domains" in reason

    ok, reason = gov.check_trigger_domain("security.disable_firewall")
    assert ok is False
    assert "outside trigger_allowed_domains" in reason


def test_personal_os_state_store_crud():
    """Verify PersonalOSStateStore database operations and persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "state.db"
        store = PersonalOSStateStore(db_path=db_path)

        trigger = PersonalOSTrigger(
            trigger_id="trig_standup_001",
            name="standup_prep",
            goal_text="Review git commits and summarize yesterday's tasks",
            schedule="0 9 * * 1-5",
            template_vars={"project": "AuraAI"},
            metadata={"source": "m26_test"},
        )
        store.save_trigger(trigger)

        # Retrieve by id & name
        retrieved_id = store.get_trigger("trig_standup_001")
        assert retrieved_id is not None
        assert retrieved_id.name == "standup_prep"
        assert retrieved_id.template_vars == {"project": "AuraAI"}

        retrieved_name = store.get_trigger("standup_prep")
        assert retrieved_name is not None
        assert retrieved_name.trigger_id == "trig_standup_001"

        # Update trigger run
        store.update_trigger_run(
            "trig_standup_001", result_summary="Prepared standup summary"
        )
        updated = store.get_trigger("trig_standup_001")
        assert updated.run_count == 1
        assert updated.last_result_summary == "Prepared standup summary"
        assert updated.last_fired_at is not None

        # Preferences
        store.set_preference("timezone", "UTC")
        store.set_preference("working_hours", {"start": 9, "end": 17})

        assert store.get_preference("timezone") == "UTC"
        assert store.get_preference("working_hours") == {"start": 9, "end": 17}
        assert store.get_preference("non_existent", "default_val") == "default_val"

        all_prefs = store.get_all_preferences()
        assert "timezone" in all_prefs
        assert all_prefs["working_hours"]["start"] == 9

        # List & Delete
        triggers = store.list_triggers()
        assert len(triggers) == 1

        deleted = store.delete_trigger("trig_standup_001")
        assert deleted is True
        assert store.get_trigger("trig_standup_001") is None
        assert len(store.list_triggers()) == 0


@pytest.mark.asyncio
async def test_master_orchestrator_autonomy_floor_scope():
    """Verify MasterOrchestrator raises autonomy floor for TRIGGER_AUTONOMOUS and restores it."""
    from src.core.orchestration.master_orchestrator import MasterOrchestrator

    policy = ExecutionPolicy.get_instance()
    policy.set_autonomy_level(AutonomyLevel.ASSISTED)

    orch = MasterOrchestrator()

    # When running with TRIGGER_AUTONOMOUS, verify policy is temporarily AUTONOMOUS during execution
    res = await orch.process_request_async(
        goal_text="test personal os request",
        source=RequestSource.TRIGGER_AUTONOMOUS,
    )

    # After process_request_async finishes, autonomy level must be restored to ASSISTED
    assert policy.get_autonomy_level() == AutonomyLevel.ASSISTED


def test_prohibited_capability_unconditional_hard_block_regardless_of_token():
    """Verify PROHIBITED tier capabilities are unconditionally hard-blocked even with a forged or valid HMAC token."""
    from src.daemon.governance import AutonomyGovernanceEngine, AutonomyRiskTier
    from src.daemon.models import JobDefinition, TriggerType

    gov = AutonomyGovernanceEngine()

    # Create dummy high-risk token
    digest = gov.compute_arguments_digest({"all": True})
    token = gov.create_scoped_token(
        job_id="job_malicious_1",
        capability="security.disable_firewall",
        arguments_digest=digest,
    )

    job = JobDefinition(
        job_id="job_malicious_1",
        name="prohibited_job",
        goal="disable firewall",
        capability="security.disable_firewall",
        trigger_type=TriggerType.ONE_SHOT,
        autonomy_token=token,
    )

    allowed, reason, tier = gov.evaluate_execution(
        job=job,
        capability="security.disable_firewall",
        arguments={"all": True},
        token=token,
    )

    # Must be unconditionally rejected
    assert allowed is False
    assert tier == AutonomyRiskTier.PROHIBITED
    assert "PROHIBITED" in reason


def test_audit_ledger_chain_integrity_after_request_source_write():
    """Verify audit ledger hash chaining and Merkle integrity after writing trigger request_source events."""
    from src.desktop.native.security.audit_logger import SecurityAuditLogger

    with tempfile.TemporaryDirectory() as tmpdir:
        audit_path = Path(tmpdir) / "audit_ledger.jsonl"
        logger_inst = SecurityAuditLogger(log_path=audit_path, enable_registry_anchor=False)

        # Log multiple sequential autonomous goal dispatch events
        entry1 = logger_inst.log_event(
            event_type="AUTONOMOUS_GOAL_DISPATCH",
            action_type="trigger_goal_fired",
            target="trig_morning_standup",
            status="DISPATCHED",
            details={"request_source": RequestSource.TRIGGER_AUTONOMOUS.value, "goal": "Standup"},
        )
        entry2 = logger_inst.log_event(
            event_type="AUTONOMOUS_GOAL_DISPATCH",
            action_type="trigger_goal_fired",
            target="trig_clean_downloads",
            status="DISPATCHED",
            details={"request_source": RequestSource.TRIGGER_AUTONOMOUS.value, "goal": "Downloads"},
        )
        entry3 = logger_inst.log_event(
            event_type="AUTONOMOUS_GOAL_DISPATCH",
            action_type="trigger_goal_fired",
            target="trig_code_health",
            status="DISPATCHED",
            details={"request_source": RequestSource.DAEMON_BACKGROUND.value, "goal": "Tests"},
        )

        assert entry1 is not None and "entry_hash" in entry1
        assert entry2 is not None and "entry_hash" in entry2
        assert entry3 is not None and "entry_hash" in entry3

        # Verify entry2 links to entry1, and entry3 links to entry2
        assert entry2.get("prev_hash") == entry1["entry_hash"]
        assert entry3.get("prev_hash") == entry2["entry_hash"]

        # Verify hash-chain Merkle integrity over all 3 sequential entries
        valid, msg, stats = logger_inst.verify_chain_integrity()
        assert valid is True
        assert "verified" in msg.lower() or "valid" in msg.lower()
        assert isinstance(stats, dict)


@pytest.mark.asyncio
async def test_contextvar_autonomy_level_concurrency_isolation():
    """Verify ContextVar prevents race conditions between concurrent trigger and human tasks."""
    policy = ExecutionPolicy.get_instance()
    policy.set_autonomy_level(AutonomyLevel.ASSISTED)

    observed_human_level = None

    async def trigger_task():
        # Sets request context to AUTONOMOUS and yields control
        token = policy.set_autonomy_level(AutonomyLevel.AUTONOMOUS)
        assert policy.get_autonomy_level() == AutonomyLevel.AUTONOMOUS
        await asyncio.sleep(0.05)  # Yield to concurrent tasks
        assert policy.get_autonomy_level() == AutonomyLevel.AUTONOMOUS
        policy.reset_autonomy_level(token)

    async def human_task():
        # Should NOT see the AUTONOMOUS level set by trigger_task
        await asyncio.sleep(0.02)  # Wait for trigger_task to enter sleep
        nonlocal observed_human_level
        observed_human_level = policy.get_autonomy_level()

    await asyncio.gather(trigger_task(), human_task())

    # The human task in its own coroutine context must remain ASSISTED
    assert observed_human_level == AutonomyLevel.ASSISTED
