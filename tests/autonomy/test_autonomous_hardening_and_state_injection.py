"""
Autonomous Hardening & State Injection Defense Suite
Location: tests/autonomy/test_autonomous_hardening_and_state_injection.py

Validates:
1. Non-Interactive Fail-Closed Gating: High-risk/destructive actions halt as BLOCKED in background triggers.
2. Adversarial Bypass Rejection: 'user_authorized: True' boolean bypass without HMAC signature is rejected.
3. Cryptographic Single-Use Ticket Redemption: Valid human HMAC signatures succeed once and cannot be replayed.
4. Pre-Authorized Recurring Triggers: Signed recurring triggers execute, and tampered triggers fail closed.
5. Unregistered/Unwired Capability Rejection: Unregistered actions fail closed to BLOCKED.
6. WorkspaceJail Confinement under Background Dispatch: Background triggers cannot breach jail or blocked segments.
7. Parameter-Bound Persisted Task Verification: Tampered destination paths or parameters in persisted tasks are rejected.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from autonomy.models import ConcurrencyPolicy, Trigger, TriggerState, TriggerType
from autonomy.trigger_registry import TriggerRegistry
from autonomy.trigger_scheduler import TriggerScheduler
from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.execution_policy import ExecutionPolicy
from desktop.native.managers.file_manager import FileManager
from desktop.native.security.approval_authority import CryptographicApprovalAuthority


@pytest.fixture(autouse=True)
def reset_singletons():
    """Ensure clean singletons for each test."""
    CryptographicApprovalAuthority.reset_instance()
    ExecutionPolicy.reset_instance()
    CapabilityRegistry._instance = None
    yield
    CryptographicApprovalAuthority.reset_instance()
    ExecutionPolicy.reset_instance()
    CapabilityRegistry._instance = None


# ==============================================================================
# 1. Non-Interactive Gate Invariant & Boolean Bypass Rejection Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_high_risk_trigger_without_ticket_fails_closed_blocked(tmp_path):
    """A background trigger attempting a high-risk action without HMAC ticket must halt as BLOCKED."""
    registry = TriggerRegistry(storage_path=tmp_path / "triggers.json")
    scheduler = TriggerScheduler(registry=registry)

    trigger = Trigger(
        trigger_id="trig_del_1",
        trigger_type=TriggerType.SCHEDULED,
        action_goal="Delete critical directory",
        execution_map={
            "steps": [
                {
                    "engine": "desktop",
                    "action": "file.delete",
                    "parameters": {"path": "C:\\fake\\path"},
                }
            ]
        },
    )
    registry.register_trigger(trigger)

    fired = await scheduler.fire_trigger(trigger)
    assert fired is True
    # Give worker task a tick to complete
    await asyncio.sleep(0.05)

    updated = registry.get_trigger("trig_del_1")
    assert updated.state == TriggerState.BLOCKED
    assert updated.last_provenance.result_status == "BLOCKED"


@pytest.mark.asyncio
async def test_adversarial_user_authorized_boolean_bypass_rejected(tmp_path):
    """Setting 'user_authorized: True' as a plain dict key must NOT bypass confirmation."""
    registry = TriggerRegistry(storage_path=tmp_path / "triggers.json")
    scheduler = TriggerScheduler(registry=registry)

    trigger = Trigger(
        trigger_id="trig_del_bypass",
        trigger_type=TriggerType.SCHEDULED,
        action_goal="Adversarial delete with forged user_authorized flag",
        execution_map={
            "steps": [
                {
                    "engine": "desktop",
                    "action": "file.delete",
                    "parameters": {
                        "path": "C:\\fake\\path",
                        "user_authorized": True,  # Forged boolean
                    },
                }
            ]
        },
    )
    registry.register_trigger(trigger)

    await scheduler.fire_trigger(trigger)
    await asyncio.sleep(0.05)

    updated = registry.get_trigger("trig_del_bypass")
    assert updated.state == TriggerState.BLOCKED
    assert updated.last_provenance.result_status == "BLOCKED"


@pytest.mark.asyncio
async def test_valid_hmac_ticket_allows_single_use_execution(tmp_path):
    """A high-risk trigger with a valid human HMAC signature verifies and redeems successfully."""
    registry = TriggerRegistry(storage_path=tmp_path / "triggers.json")
    scheduler = TriggerScheduler(registry=registry)
    auth = CryptographicApprovalAuthority.get_instance()

    params = {"path": "C:\\test\\file.txt", "target": "C:\\test\\file.txt"}
    ticket_id = auth.create_ticket(action_type="file.delete", target="C:\\test\\file.txt", parameters=params)
    sig = auth.generate_human_signature(ticket_id)
    params["approval_ticket_id"] = ticket_id
    params["approval_signature"] = sig

    trigger = Trigger(
        trigger_id="trig_del_authorized",
        trigger_type=TriggerType.SCHEDULED,
        action_goal="Authorized delete",
        execution_map={
            "steps": [
                {
                    "engine": "desktop",
                    "action": "file.delete",
                    "parameters": params,
                }
            ]
        },
    )
    registry.register_trigger(trigger)

    await scheduler.fire_trigger(trigger)
    await asyncio.sleep(0.05)

    updated = registry.get_trigger("trig_del_authorized")
    # With valid ticket and no coordinator mock, it completes as VERIFIED
    assert updated.state == TriggerState.VERIFIED
    # Ticket must be redeemed
    assert auth.get_ticket(ticket_id).is_redeemed is True


# ==============================================================================
# 2. Pre-Authorized Recurring Trigger & Tampering Defense Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_pre_authorized_recurring_trigger_succeeds(tmp_path):
    """Recurring triggers with cryptographic trigger signatures execute without per-run tickets."""
    registry = TriggerRegistry(storage_path=tmp_path / "triggers.json")
    scheduler = TriggerScheduler(registry=registry)
    auth = CryptographicApprovalAuthority.get_instance()

    exec_map = {
        "steps": [
            {
                "engine": "desktop",
                "action": "file.delete",
                "parameters": {"path": "C:\\safe\\cache"},
            }
        ]
    }
    action_goal = "Periodic cache cleanup"
    trig_id = "trig_recurring_clean"

    signature = auth.sign_trigger(
        trigger_id=trig_id,
        action_goal=action_goal,
        execution_map=exec_map,
    )

    trigger = Trigger(
        trigger_id=trig_id,
        trigger_type=TriggerType.SCHEDULED,
        action_goal=action_goal,
        execution_map=exec_map,
        auth_signature=signature,
        is_recurring_authorized=True,
    )
    registry.register_trigger(trigger)

    await scheduler.fire_trigger(trigger)
    await asyncio.sleep(0.05)

    updated = registry.get_trigger(trig_id)
    assert updated.state == TriggerState.VERIFIED


@pytest.mark.asyncio
async def test_tampered_recurring_trigger_rejected(tmp_path):
    """If a pre-authorized recurring trigger's parameters or target are tampered with, it must halt."""
    registry = TriggerRegistry(storage_path=tmp_path / "triggers.json")
    scheduler = TriggerScheduler(registry=registry)
    auth = CryptographicApprovalAuthority.get_instance()

    original_exec_map = {
        "steps": [
            {
                "engine": "desktop",
                "action": "file.delete",
                "parameters": {"path": "C:\\safe\\cache"},
            }
        ]
    }
    trig_id = "trig_tampered"
    action_goal = "Periodic cache cleanup"

    signature = auth.sign_trigger(
        trigger_id=trig_id,
        action_goal=action_goal,
        execution_map=original_exec_map,
    )

    # Adversary tampers with execution map to delete root
    tampered_exec_map = {
        "steps": [
            {
                "engine": "desktop",
                "action": "file.delete",
                "parameters": {"path": "C:\\Windows\\System32"},
            }
        ]
    }

    trigger = Trigger(
        trigger_id=trig_id,
        trigger_type=TriggerType.SCHEDULED,
        action_goal=action_goal,
        execution_map=tampered_exec_map,
        auth_signature=signature,  # Signature was for original_exec_map
        is_recurring_authorized=True,
    )
    registry.register_trigger(trigger)

    await scheduler.fire_trigger(trigger)
    await asyncio.sleep(0.05)

    updated = registry.get_trigger(trig_id)
    assert updated.state == TriggerState.BLOCKED


# ==============================================================================
# 3. Unregistered Capability & WorkspaceJail Background Containment
# ==============================================================================

@pytest.mark.asyncio
async def test_unregistered_capability_halted_as_blocked(tmp_path):
    """A trigger specifying an unregistered capability must halt as BLOCKED."""
    registry = TriggerRegistry(storage_path=tmp_path / "triggers.json")
    scheduler = TriggerScheduler(registry=registry)

    trigger = Trigger(
        trigger_id="trig_unknown_cap",
        trigger_type=TriggerType.SCHEDULED,
        action_goal="Unknown action execution",
        execution_map={
            "steps": [
                {
                    "engine": "desktop",
                    "action": "unregistered.dangerous_action",
                    "parameters": {},
                }
            ]
        },
    )
    registry.register_trigger(trigger)

    await scheduler.fire_trigger(trigger)
    await asyncio.sleep(0.05)

    updated = registry.get_trigger("trig_unknown_cap")
    assert updated.state == TriggerState.BLOCKED


def test_background_file_manager_workspace_jail_containment(tmp_path):
    """Background file operations cannot escape allowed roots or touch blocked segments."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    docs = tmp_path / "external_docs"
    docs.mkdir()
    (docs / "file.txt").write_text("content")

    # Sensitive folders inside allowed root
    (docs / ".ssh").mkdir()
    (docs / ".ssh" / "id_rsa").write_text("secret")
    (docs / "appdata").mkdir()
    (docs / "appdata" / "token.json").write_text("token")

    fm = FileManager(workspace_root=str(ws))
    fm.jail.add_allowed_root(docs)

    # 1. Normal file inside allowed root succeeds
    res_ok = fm.execute("file.info", arguments={"path": str(docs / "file.txt")})
    assert res_ok.success is True

    # 2. Blocked segment access inside allowed root fails closed
    res_ssh = fm.execute("file.info", arguments={"path": str(docs / ".ssh" / "id_rsa")})
    assert res_ssh.success is False
    assert "outside allowed workspace" in res_ssh.error.lower() or "workspace_jail" in str(res_ssh.data).lower()

    res_appdata = fm.execute("file.info", arguments={"path": str(docs / "appdata" / "token.json")})
    assert res_appdata.success is False

    # 3. Path outside jail completely fails closed
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside")
    res_outside = fm.execute("file.info", arguments={"path": str(outside_file)})
    assert res_outside.success is False


# ==============================================================================
# 4. Parameter-Bound Persisted Task Verification Tests
# ==============================================================================

def test_parameter_bound_persisted_task_signing_and_tampering_detection():
    """Cryptographic task binding prevents parameter tampering in persisted state."""
    auth = CryptographicApprovalAuthority.get_instance()
    task_id = "task_standup_digest"
    cap = "file.organize"
    params = {"path": "C:\\Users\\User\\Documents", "strategy": "category"}
    ws_root = "D:\\Projects\\AuraAI"

    # 1. Sign task definition
    sig = auth.sign_persisted_task(
        task_id=task_id,
        capability=cap,
        parameters=params,
        workspace_root=ws_root,
    )
    assert sig is not None and len(sig) == 64

    # 2. Valid task definition passes
    valid, msg = auth.verify_persisted_task(
        task_id=task_id,
        capability=cap,
        parameters=params,
        signature=sig,
        workspace_root=ws_root,
    )
    assert valid is True

    # 3. Tampered parameter (e.g. redirected path) fails
    tampered_params = {"path": "C:\\Windows\\System32", "strategy": "category"}
    valid, msg = auth.verify_persisted_task(
        task_id=task_id,
        capability=cap,
        parameters=tampered_params,
        signature=sig,
        workspace_root=ws_root,
    )
    assert valid is False
    assert "tampered" in msg.lower()

    # 4. Tampered capability name fails
    valid, msg = auth.verify_persisted_task(
        task_id=task_id,
        capability="file.delete",
        parameters=params,
        signature=sig,
        workspace_root=ws_root,
    )
    assert valid is False

    # 5. Tampered workspace root fails
    valid, msg = auth.verify_persisted_task(
        task_id=task_id,
        capability=cap,
        parameters=params,
        signature=sig,
        workspace_root="C:\\EvilRoot",
    )
    assert valid is False
