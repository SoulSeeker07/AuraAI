"""
Standalone Integration Test for Cryptographic Human Approval Round-Trip (Qt-Free)
Location: tests/integration/test_approval_authority_roundtrip.py

Verifies the complete lifecycle of HMAC human ticket issuance, signing via
generate_human_signature(), and single-use redemption via verify_and_redeem(),
verifying tamper-resistance, anti-replay, TTL expiry, and substitution prevention.
"""

import time
import pytest
from desktop.native.security.approval_authority import (
    CryptographicApprovalAuthority,
    ApprovalTicket,
)


@pytest.fixture(autouse=True)
def reset_authority():
    """Ensure clean singleton state before and after each test."""
    CryptographicApprovalAuthority.reset_instance()
    yield
    CryptographicApprovalAuthority.reset_instance()


def test_approval_authority_successful_round_trip():
    """Verify happy path: ticket creation -> human signing -> verify & redeem."""
    auth = CryptographicApprovalAuthority.get_instance()

    action_type = "file.delete"
    target = "C:/temp/sensitive_file.txt"
    params = {"force": True, "reason": "user_cleanup"}

    # 1. Issue un-signed ticket
    ticket_id = auth.create_ticket(
        action_type=action_type,
        target=target,
        parameters=params,
        ttl_seconds=60.0,
    )
    assert ticket_id.startswith("tkt_")

    # Ticket should be listed in pending
    pending = auth.get_pending_tickets()
    assert any(t.ticket_id == ticket_id for t in pending)

    # 2. Sign via single signing chokepoint
    signature = auth.generate_human_signature(ticket_id)
    assert signature is not None
    assert isinstance(signature, str)
    assert len(signature) == 64  # SHA-256 hex digest

    # 3. Verify and redeem
    is_valid, msg = auth.verify_and_redeem(
        ticket_id=ticket_id,
        signature=signature,
        action_type=action_type,
        target=target,
        parameters=params,
    )
    assert is_valid is True
    assert "successfully" in msg.lower()

    # 4. Anti-Replay: Second redemption must fail
    is_valid_second, msg_second = auth.verify_and_redeem(
        ticket_id=ticket_id,
        signature=signature,
        action_type=action_type,
        target=target,
        parameters=params,
    )
    assert is_valid_second is False
    assert "already been redeemed" in msg_second.lower()


def test_approval_authority_parameter_tampering_substitution_blocked():
    """Verify that tampering with action parameters or target causes verification failure."""
    auth = CryptographicApprovalAuthority.get_instance()

    action_type = "file.delete"
    target = "C:/temp/safe_file.txt"
    params = {"path": "C:/temp/safe_file.txt"}

    ticket_id = auth.create_ticket(
        action_type=action_type,
        target=target,
        parameters=params,
        ttl_seconds=60.0,
    )
    signature = auth.generate_human_signature(ticket_id)
    assert signature is not None

    # Attack: Substituted target
    is_valid, msg = auth.verify_and_redeem(
        ticket_id=ticket_id,
        signature=signature,
        action_type=action_type,
        target="C:/Windows/System32/critical.dll",
        parameters=params,
    )
    assert is_valid is False
    assert "does not match" in msg.lower()


def test_approval_authority_expired_ticket_rejected():
    """Verify that expired tickets cannot be signed or redeemed."""
    auth = CryptographicApprovalAuthority.get_instance()

    # Create ticket with 0.05s TTL
    ticket_id = auth.create_ticket(
        action_type="terminal.command",
        target="dir",
        ttl_seconds=0.05,
    )
    time.sleep(0.1)

    # Signing after expiration must fail
    signature = auth.generate_human_signature(ticket_id)
    assert signature is None


def test_approval_authority_command_ticket_round_trip():
    """Verify specialized terminal command ticket round-trip."""
    auth = CryptographicApprovalAuthority.get_instance()

    cmd = "git clean -fd"
    cwd = "D:/workspace/repo"

    ticket_id = auth.create_command_ticket(command=cmd, cwd=cwd, ttl_seconds=60.0)
    signature = auth.generate_human_signature(ticket_id)
    assert signature is not None

    is_valid, msg = auth.verify_and_redeem_command(
        ticket_id=ticket_id,
        signature=signature,
        command=cmd,
        cwd=cwd,
    )
    assert is_valid is True
    assert "successfully" in msg.lower()
