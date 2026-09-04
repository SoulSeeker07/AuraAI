"""
Unit tests for VoiceNotchOverlay Cryptographic Ticket Resolution & Dialogue Confirmation
======================================================================================
Verifies:
1. VoiceNotchOverlay subscribes to Events.CONFIRMATION_REQUIRED on core.event_bus.
2. Real cryptographic tickets (tkt_*) route to RealBackendBridge.approve_and_execute_ticket
   and RealBackendBridge.deny_ticket, NEVER invoking MasterOrchestrator.
3. Plain session dialogue confirmations (ASK_USER / ActionPlanConfirmation) route to
   MasterOrchestrator.resolve_pending_confirmation, NEVER invoking RealBackendBridge.
4. Double-click replay defense synchronously disables buttons and drops duplicate calls.
"""

import os
import sys
from unittest.mock import MagicMock, patch
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from gui.widgets.voice_notch_overlay import VoiceNotchOverlay, NotchState
from core.event_bus import EventBus, Events, Event


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_notch_overlay_eventbus_subscription(qapp):
    overlay = VoiceNotchOverlay()
    try:
        assert hasattr(overlay, "_bus_sub_conf")
        event_name, handler = overlay._bus_sub_conf
        assert event_name == Events.CONFIRMATION_REQUIRED
        assert callable(handler)
    finally:
        overlay.close()


def test_notch_overlay_shows_approval_card_on_crypto_event(qapp):
    overlay = VoiceNotchOverlay()
    overlay.show()
    try:
        bus = EventBus.get_instance()
        test_payload = {
            "ticket_id": "tkt_sec_audit_999",
            "action_name": "delete_directory",
            "action_params": {"target": "C:/tmp/test_dir"},
            "risk": "CRITICAL",
            "is_crypto_ticket": True,
        }

        # Publish confirmation required event
        bus.publish(Events.CONFIRMATION_REQUIRED, payload=test_payload)
        qapp.processEvents()

        card = overlay._expanded_panel._approval_card
        assert card.isHidden() is False
        assert overlay._expanded_panel._pending_ticket_id == "tkt_sec_audit_999"
        assert "CRITICAL RISK" in overlay._expanded_panel._app_risk_badge.text()
        assert "tkt_sec_audit_999" in overlay._expanded_panel._app_desc.text()
        assert "delete_directory" in overlay._expanded_panel._app_desc.text()
        assert "CRYPTOGRAPHIC APPROVAL REQUIRED" in overlay._expanded_panel._app_title.text()
        assert overlay._state == NotchState.EXPANDED
    finally:
        overlay.close()


def test_notch_overlay_crypto_ticket_branch_approves_via_backend_bridge(qapp):
    """Branch 1: Real cryptographic ticket must invoke RealBackendBridge, NEVER MasterOrchestrator."""
    overlay = VoiceNotchOverlay()
    overlay.show()
    try:
        overlay._expanded_panel.show_approval_card(
            ticket_id="tkt_sec_crypto_001",
            action_name="terminal_kill_process",
            params={"pid": 1234},
            risk_level="HIGH",
        )
        assert overlay._expanded_panel._approval_card.isHidden() is False
        assert overlay._expanded_panel._is_crypto_ticket is True

        resolved_events = []
        overlay.confirmation_resolved.connect(lambda tkt, app: resolved_events.append((tkt, app)))

        mock_bridge = MagicMock()
        mock_bridge.approve_and_execute_ticket.return_value = {"success": True}
        mock_orch = MagicMock()

        with patch("gui.real_backend_bridge.RealBackendBridge.get_instance", return_value=mock_bridge), \
             patch("core.orchestration.MasterOrchestrator.get_instance", return_value=mock_orch):
            overlay._expanded_panel._btn_approve.click()
            qapp.processEvents()

        # Must invoke RealBackendBridge
        mock_bridge.approve_and_execute_ticket.assert_called_once_with("tkt_sec_crypto_001")
        # Must NEVER invoke MasterOrchestrator for crypto tickets
        mock_orch.resolve_pending_confirmation.assert_not_called()

        assert overlay._expanded_panel._approval_card.isHidden() is True
        assert len(resolved_events) == 1
        assert resolved_events[0] == ("tkt_sec_crypto_001", True)
    finally:
        overlay.close()


def test_notch_overlay_crypto_ticket_branch_denies_via_backend_bridge(qapp):
    """Branch 1 (Deny): Real cryptographic ticket must revoke via RealBackendBridge, NEVER MasterOrchestrator."""
    overlay = VoiceNotchOverlay()
    overlay.show()
    try:
        overlay._expanded_panel.show_approval_card(
            ticket_id="tkt_sec_crypto_002",
            action_name="drop_table",
            params={"table": "users"},
            risk_level="CRITICAL",
        )
        assert overlay._expanded_panel._approval_card.isHidden() is False

        resolved_events = []
        overlay.confirmation_resolved.connect(lambda tkt, app: resolved_events.append((tkt, app)))

        mock_bridge = MagicMock()
        mock_orch = MagicMock()

        with patch("gui.real_backend_bridge.RealBackendBridge.get_instance", return_value=mock_bridge), \
             patch("core.orchestration.MasterOrchestrator.get_instance", return_value=mock_orch):
            overlay._expanded_panel._btn_deny.click()
            qapp.processEvents()

        # Must invoke RealBackendBridge.deny_ticket
        mock_bridge.deny_ticket.assert_called_once_with("tkt_sec_crypto_002")
        # Must NEVER invoke MasterOrchestrator for crypto tickets
        mock_orch.resolve_pending_confirmation.assert_not_called()

        assert overlay._expanded_panel._approval_card.isHidden() is True
        assert len(resolved_events) == 1
        assert resolved_events[0] == ("tkt_sec_crypto_002", False)
    finally:
        overlay.close()


def test_notch_overlay_plain_ask_user_branch_resolves_via_orchestrator(qapp):
    """Branch 2: Plain session dialogue confirmation must invoke MasterOrchestrator, NEVER RealBackendBridge."""
    overlay = VoiceNotchOverlay()
    overlay.show()
    try:
        bus = EventBus.get_instance()
        test_payload = {
            "ticket_id": None,
            "action_name": "launch_new_browser_window",
            "action_params": {"target": "chrome.exe"},
            "risk": "MEDIUM",
            "is_crypto_ticket": False,
            "prompt": "Chrome is already running. Open another instance? (yes / no)",
        }

        # Publish confirmation required event without crypto ticket
        bus.publish(Events.CONFIRMATION_REQUIRED, payload=test_payload)
        qapp.processEvents()

        # UI must render standard confirmation header, without a ticket label
        assert overlay._expanded_panel._approval_card.isHidden() is False
        assert overlay._expanded_panel._is_crypto_ticket is False
        assert "CONFIRMATION REQUIRED" in overlay._expanded_panel._app_title.text()
        assert "Ticket: tkt_" not in overlay._expanded_panel._app_desc.text()

        resolved_events = []
        overlay.confirmation_resolved.connect(lambda tkt, app: resolved_events.append((tkt, app)))

        mock_orch = MagicMock()
        mock_orch.resolve_pending_confirmation.return_value = MagicMock(observations=["Opened another instance."])
        mock_bridge = MagicMock()

        with patch("core.orchestration.MasterOrchestrator.get_instance", return_value=mock_orch), \
             patch("gui.real_backend_bridge.RealBackendBridge.get_instance", return_value=mock_bridge):
            overlay._expanded_panel._btn_approve.click()
            qapp.processEvents()

        # Must invoke MasterOrchestrator
        mock_orch.resolve_pending_confirmation.assert_called_once_with("yes")
        # Must NEVER invoke RealBackendBridge for non-crypto dialogue confirmations
        mock_bridge.approve_and_execute_ticket.assert_not_called()
        mock_bridge.deny_ticket.assert_not_called()

        assert overlay._expanded_panel._approval_card.isHidden() is True
        assert len(resolved_events) == 1
        assert resolved_events[0] == ("", True)
    finally:
        overlay.close()


def test_notch_overlay_double_click_replay_defense(qapp):
    overlay = VoiceNotchOverlay()
    overlay.show()
    try:
        overlay._expanded_panel.show_approval_card(
            ticket_id="tkt_sec_double_click_003",
            action_name="execute_terminal",
            params={"command": "rm -rf /"},
            risk_level="CRITICAL",
        )

        assert overlay._expanded_panel._btn_approve.isEnabled() is True
        assert overlay._expanded_panel._btn_deny.isEnabled() is True

        mock_bridge = MagicMock()
        mock_bridge.approve_and_execute_ticket.return_value = {"success": True}
        mock_orch = MagicMock()

        with patch("gui.real_backend_bridge.RealBackendBridge.get_instance", return_value=mock_bridge), \
             patch("core.orchestration.MasterOrchestrator.get_instance", return_value=mock_orch):
            # First click
            overlay._expanded_panel._btn_approve.click()
            qapp.processEvents()

            # Buttons must be disabled synchronously
            assert overlay._expanded_panel._btn_approve.isEnabled() is False
            assert overlay._expanded_panel._btn_deny.isEnabled() is False
            assert overlay._expanded_panel._pending_ticket_id is None

            # Immediate second invocation (simulating race or secondary event before unmap)
            overlay._expanded_panel._handle_approval_click(True)
            qapp.processEvents()

            # Direct call with None ticket must be dropped
            overlay.resolve_confirmation(None, True, is_crypto=True)

            # Bridge must only have been invoked exactly ONCE
            assert mock_bridge.approve_and_execute_ticket.call_count == 1
            # Orchestrator must NEVER be invoked
            mock_orch.resolve_pending_confirmation.assert_not_called()
    finally:
        overlay.close()


def test_execution_policy_decision_risk_attribute():
    """Verify PolicyDecision carries genuine ActionRisk and passes it to EventBus payload."""
    from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction
    from core.orchestration.autonomy_mode import ActionRisk, AutonomyLevel

    policy = ExecutionPolicy()
    policy.set_autonomy_level(AutonomyLevel.ASSISTED)

    # Gated high-risk action
    decision = policy.evaluate_action("filesystem", "file.delete", {"path": "important.txt"})
    assert decision.action == PolicyAction.ASK_USER
    assert hasattr(decision, "risk")
    assert decision.risk == ActionRisk.HIGH

    # Non-gated low-risk action
    decision_low = policy.evaluate_action("browser", "search")
    assert decision_low.action == PolicyAction.LAUNCH_NEW
    assert decision_low.risk == ActionRisk.LOW

