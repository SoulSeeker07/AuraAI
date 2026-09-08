"""
Unit tests for Antigravity-Style Subagent Completion Notification Pipeline (Piece 2).
Location: tests/unit/test_subagent_notification.py

Tests:
1. Secret & PII output redaction (API keys, private keys, passwords, bearer tokens, credit cards).
2. EventBus event publishing on dispatch, success, and failure.
3. FocusManager buffered notification card enqueue and draining.
4. ActionRisk taxonomy severity mapping.
"""

import asyncio
import time
from typing import Any
import pytest

from core.event_bus import EventBus, Events
from core.focus_manager import FocusManager
from core.orchestration.autonomy_mode import ActionRisk
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.task_worker import (
    WorkerResult,
    CodingProfile,
    ResearchProfile,
    sanitize_worker_output,
)


def test_sanitize_worker_output_redacts_credentials():
    """
    Falsifiable test: sanitize_worker_output must scrub all common API keys,
    passwords, Bearer tokens, private keys, and credit cards.
    """
    raw_text = (
        "Connected to Groq with gsk_abcdef1234567890abcdef1234567890, "
        "OpenAI with sk-proj-1234567890abcdef1234567890, "
        "Anthropic with sk-ant-api03-abcdef1234567890abcdef1234567890, "
        "AWS with AKIAIOSFODNN7EXAMPLE, "
        "Google with AIzaSyD1234567890abcdef123456789012345, "
        "GitHub with ghp_1234567890abcdef12345678901234567890, "
        f"Slack with {'xoxb'}-1234567890-abcdef1234567890, "
        "header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9, "
        "password: 'super_secret_password_123', "
        "credit card: 4111 2222 3333 4444."
    )
    cleaned = sanitize_worker_output(raw_text)

    # Assert no secrets remain in cleaned output
    assert "gsk_" not in cleaned
    assert "sk-proj-" not in cleaned
    assert "sk-ant-" not in cleaned
    assert "AKIAIOSFODNN7EXAMPLE" not in cleaned
    assert "AIzaSyD" not in cleaned
    assert "ghp_" not in cleaned
    assert "xoxb-" not in cleaned
    assert "eyJhbGciOi" not in cleaned
    assert "super_secret_password_123" not in cleaned
    assert "4111 2222 3333 4444" not in cleaned

    # Assert proper redaction tags are inserted
    assert "[REDACTED_API_KEY]" in cleaned
    assert "[REDACTED_SECRET]" in cleaned
    assert "[REDACTED_CARD]" in cleaned

    # Test PEM private key
    pem_text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1u4q8...\n"
        "-----END RSA PRIVATE KEY-----"
    )
    assert sanitize_worker_output(pem_text) == "[REDACTED_PRIVATE_KEY]"

    # Test dictionary scrubbing
    raw_dict = {
        "user": "developer",
        "api_key": "raw_secret_val",
        "password": "my_secret_pass",
        "nested": {
            "token": "tok_xyz987654321",
            "safe_data": "public_info",
        },
    }
    sanitized_dict = sanitize_worker_output(raw_dict)
    assert sanitized_dict["api_key"] == "[REDACTED_SECRET]"
    assert sanitized_dict["password"] == "[REDACTED_SECRET]"
    assert sanitized_dict["nested"]["token"] == "[REDACTED_SECRET]"
    assert sanitized_dict["nested"]["safe_data"] == "public_info"

    # Test WorkerResult scrubbing
    wr = WorkerResult(
        worker_name="worker_test",
        status="SUCCESS",
        task="Fetch gsk_abcdef1234567890abcdef1234567890",
        observations=["Received token: password=my_db_pass_12345"],
        errors=["Failed auth: sk-proj-1234567890abcdef1234567890"],
    )
    sanitized_wr = sanitize_worker_output(wr)
    assert "gsk_" not in sanitized_wr.task
    assert "my_db_pass_12345" not in sanitized_wr.observations[0]
    assert "sk-proj-" not in sanitized_wr.errors[0]

    # Verify WorkerResult.to_dict() is automatically sanitized
    wr_dict = wr.to_dict()
    assert "gsk_" not in wr_dict["task"]
    assert "my_db_pass_12345" not in wr_dict["observations"][0]
    assert "sk-proj-" not in wr_dict["errors"][0]


@pytest.mark.asyncio
async def test_subagent_publishes_event_on_completion():
    """
    Verify EventBus publishes Events.SUBAGENT_COMPLETED with sanitized payload upon completion.
    """
    orchestrator = MasterOrchestrator.get_instance()
    bus = EventBus.get_instance()

    received_events: list[Any] = []

    def on_completed(event):
        received_events.append(event)

    bus.subscribe(Events.SUBAGENT_COMPLETED, on_completed)
    try:
        ack = orchestrator.dispatch_background_subagent(
            task_description="Execute routine telemetry check",
            profile="research",
        )
        assert ack["status"] == "DISPATCHED"

        # Await subagent background task completion
        await ack["task"]

        # Allow quick event loop turn for event dispatch
        await asyncio.sleep(0.05)

        matching = [e for e in received_events if e.payload.get("worker_id") == ack["worker_id"]]
        assert len(matching) == 1, f"Expected 1 SUBAGENT_COMPLETED event for {ack['worker_id']}, got {len(matching)}"

        event_payload = matching[0].payload
        assert event_payload["status"] == "SUCCESS"
        assert event_payload["worker_id"] == ack["worker_id"]
        assert "notification" in event_payload
        assert "finished successfully" in event_payload["notification"]
        assert event_payload["severity"] == "low"
    finally:
        bus.unsubscribe(Events.SUBAGENT_COMPLETED, on_completed)


@pytest.mark.asyncio
async def test_subagent_publishes_event_on_failure():
    """
    Verify EventBus publishes Events.SUBAGENT_FAILED when subagent encounters an unhandled error.
    """
    orchestrator = MasterOrchestrator.get_instance()
    bus = EventBus.get_instance()

    received_failures: list[Any] = []

    def on_failed(event):
        received_failures.append(event)

    def crashing_tool(tool_name: str, params: dict):
        raise RuntimeError("Database connection timed out during indexing")

    bus.subscribe(Events.SUBAGENT_FAILED, on_failed)
    try:
        ack = orchestrator.dispatch_background_subagent(
            task_description="Failing database re-index",
            profile="coding",
            context={"tool": "code.analyze", "params": {}},
            coordinator_callback=crashing_tool,
        )

        res = await ack["task"]
        assert res.status == "FAILED"

        await asyncio.sleep(0.05)

        matching = [e for e in received_failures if e.payload.get("worker_id") == ack["worker_id"]]
        assert len(matching) == 1, f"Expected 1 SUBAGENT_FAILED event, got {len(matching)}"

        event_payload = matching[0].payload
        assert event_payload["status"] == "FAILED"
        assert "Database connection timed out" in event_payload["notification"]
        assert event_payload["severity"] in ("medium", "high")
    finally:
        bus.unsubscribe(Events.SUBAGENT_FAILED, on_failed)


@pytest.mark.asyncio
async def test_subagent_enqueues_focus_manager_notification():
    """
    Verify completed subagents enqueue structured cards into FocusManager.
    """
    orchestrator = MasterOrchestrator.get_instance()
    fm = FocusManager.get_instance()

    # Clear pending notifications
    while fm.drain_pending_notifications():
        pass

    ack = orchestrator.dispatch_background_subagent(
        task_description="Index project markdown references",
        profile="research",
    )

    await ack["task"]
    await asyncio.sleep(0.05)

    pending: list[Any] = []
    while True:
        batch = fm.drain_pending_notifications()
        if not batch:
            break
        pending.extend(batch)

    matching_notifs = [n for n in pending if n.task_id == ack["worker_id"]]
    assert len(matching_notifs) == 1, f"Expected 1 notification for {ack['worker_id']}, found {len(matching_notifs)}"

    notif = matching_notifs[0]
    assert notif.task_id == ack["worker_id"]
    assert "finished successfully" in notif.message
    assert notif.severity == "low"


@pytest.mark.asyncio
async def test_subagent_redacts_secrets_in_event_and_notification():
    """
    Verify that sensitive data returned in worker observations or errors is scrubbed
    before reaching EventBus payloads and FocusManager notification cards.
    """
    orchestrator = MasterOrchestrator.get_instance()
    bus = EventBus.get_instance()
    fm = FocusManager.get_instance()

    while fm.drain_pending_notifications():
        pass
    received_events: list[Any] = []

    def on_completed(event):
        received_events.append(event)

    bus.subscribe(Events.SUBAGENT_COMPLETED, on_completed)

    # Leak simulated credentials inside tool execution output
    def leaky_tool(tool_name: str, params: dict):
        return (
            "Successfully extracted token: gsk_testsecret12345678901234567890 "
            "with password=my_db_secret_key_pass"
        )

    try:
        ack = orchestrator.dispatch_background_subagent(
            task_description="Scrape credentials config",
            profile="coding",
            context={"tool": "code.analyze", "params": {}},
            coordinator_callback=leaky_tool,
        )

        await ack["task"]
        await asyncio.sleep(0.05)

        # 1. Check EventBus payload
        matching = [e for e in received_events if e.payload.get("worker_id") == ack["worker_id"]]
        assert len(matching) == 1
        payload = matching[0].payload
        notif_str = payload["notification"]
        result_str = str(payload["result"])

        assert "gsk_testsecret" not in notif_str
        assert "my_db_secret_key_pass" not in notif_str
        assert "gsk_testsecret" not in result_str
        assert "my_db_secret_key_pass" not in result_str
        assert "[REDACTED_API_KEY]" in result_str
        assert "[REDACTED_SECRET]" in result_str

        # 2. Check FocusManager card
        pending = []
        while True:
            batch = fm.drain_pending_notifications()
            if not batch:
                break
            pending.extend(batch)
        fm_matching = [n for n in pending if n.task_id == ack["worker_id"]]
        assert len(fm_matching) == 1
        fm_card = fm_matching[0].message
        assert "gsk_testsecret" not in fm_card
        assert "my_db_secret_key_pass" not in fm_card
    finally:
        bus.unsubscribe(Events.SUBAGENT_COMPLETED, on_completed)


@pytest.mark.asyncio
async def test_subagent_publishes_dispatched_event():
    """
    Verify EventBus receives Events.SUBAGENT_DISPATCHED upon dispatching a background subagent.
    """
    orchestrator = MasterOrchestrator.get_instance()
    bus = EventBus.get_instance()

    dispatched_events: list[Any] = []

    def on_dispatched(event):
        dispatched_events.append(event)

    bus.subscribe(Events.SUBAGENT_DISPATCHED, on_dispatched)
    try:
        ack = orchestrator.dispatch_background_subagent(
            task_description="Build semantic index cache",
            profile="research",
        )
        assert ack["status"] == "DISPATCHED"

        matching = [e for e in dispatched_events if e.payload.get("worker_id") == ack["worker_id"]]
        assert len(matching) == 1, "Expected Events.SUBAGENT_DISPATCHED event upon dispatch"
        assert matching[0].payload["domain"] == "research"
        assert matching[0].payload["risk"] == "low"

        await ack["task"]
    finally:
        bus.unsubscribe(Events.SUBAGENT_DISPATCHED, on_dispatched)


@pytest.mark.asyncio
async def test_subagent_severity_mapping():
    """
    Verify severity mapping strictly adheres to ActionRisk taxonomy:
    - Success maps to task risk ('low', 'medium')
    - Standard failure maps to 'medium'
    """
    orchestrator = MasterOrchestrator.get_instance()
    bus = EventBus.get_instance()

    events: dict[str, Any] = {}

    def on_completed(event):
        events[event.payload.get("worker_id")] = event.payload

    def on_failed(event):
        events[event.payload.get("worker_id")] = event.payload

    bus.subscribe(Events.SUBAGENT_COMPLETED, on_completed)
    bus.subscribe(Events.SUBAGENT_FAILED, on_failed)

    try:
        # 1. Low-risk success -> 'low'
        ack_low = orchestrator.dispatch_background_subagent(
            task_description="Read-only doc inspection",
            profile="research",
        )
        await ack_low["task"]
        await asyncio.sleep(0.05)
        assert events[ack_low["worker_id"]]["severity"] == "low"

        # 2. Standard failure -> 'medium'
        def fail_tool(name, params):
            raise ValueError("bad parameter")

        ack_fail = orchestrator.dispatch_background_subagent(
            task_description="Process text transformation",
            profile="coding",
            context={"tool": "code.analyze"},
            coordinator_callback=fail_tool,
        )
        await ack_fail["task"]
        await asyncio.sleep(0.05)
        assert events[ack_fail["worker_id"]]["severity"] == "medium"
    finally:
        bus.unsubscribe(Events.SUBAGENT_COMPLETED, on_completed)
        bus.unsubscribe(Events.SUBAGENT_FAILED, on_failed)


@pytest.mark.asyncio
async def test_subagent_rejected_by_policy_does_not_publish_dispatched_event():
    """
    Verify Gate 1 ordering: If a subagent is rejected due to ExecutionPolicy,
    no Events.SUBAGENT_DISPATCHED event is ever published.
    """
    orchestrator = MasterOrchestrator.get_instance()
    bus = EventBus.get_instance()

    dispatched: list[Any] = []

    def on_dispatched(event):
        dispatched.append(event)

    bus.subscribe(Events.SUBAGENT_DISPATCHED, on_dispatched)
    try:
        # code.edit is HIGH risk and requires confirmation in standard autonomy mode
        ack = orchestrator.dispatch_background_subagent(
            task_description="Modify core execution policy file",
            profile="coding",
            context={"tool": "code.edit"},
        )
        assert ack["status"] == "REJECTED_POLICY"
        assert ack["task"] is None

        await asyncio.sleep(0.05)
        matching = [e for e in dispatched if e.payload.get("worker_id") == ack["worker_id"]]
        assert len(matching) == 0, "Rejected subagent must NEVER emit SUBAGENT_DISPATCHED"
    finally:
        bus.unsubscribe(Events.SUBAGENT_DISPATCHED, on_dispatched)

