"""
safety_gate.py

Action-level safety gating for autonomous browser tool calls.
Inspects the model's concrete proposed tool calls (rather than fuzzy regexes
on user goal text) to identify high-risk financial, credential, or destructive actions.
Unified under CryptographicApprovalAuthority with AUTH- tickets and audit ledger events.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from browser.patterns import is_high_risk_click, is_high_risk_type, sanitize_browser_args
from core.orchestration.autonomy_mode import ActionRisk
from desktop.native.security.approval_authority import CryptographicApprovalAuthority

logger = logging.getLogger(__name__)

TICKET_TTL_SECONDS = 300  # 5 minutes


class SafetyGate:
    """Evaluates safety risks on proposed browser actions and manages authorization tickets."""

    def __init__(self, ticket_file: Optional[Path] = None, ledger_file: Optional[Path] = None):
        aura_dir = Path.home() / ".aura"
        aura_dir.mkdir(parents=True, exist_ok=True)
        self.ticket_file = ticket_file or (aura_dir / "browser_tickets.json")
        self.ledger_file = ledger_file or (aura_dir / "browser_audit_ledger.jsonl")

    # -- Ticket Management (Unified under CryptographicApprovalAuthority) ---

    def _mint_ticket(self, tool: str, args: Dict[str, Any], goal: str, risk_reason: str) -> str:
        """Mint a cryptographically signed AUTH- ticket with redacted sensitive parameters."""
        auth = CryptographicApprovalAuthority.get_instance()
        sanitized_args = sanitize_browser_args(tool, args)
        sanitized_args["_browser_goal"] = goal
        sanitized_args["_risk_reason"] = risk_reason

        ticket_id = auth.create_ticket(
            action_type=f"browser.{tool}",
            target=goal[:100] if goal else f"browser.{tool}",
            parameters=sanitized_args,
            ttl_seconds=TICKET_TTL_SECONDS,
            description=f"Browser action '{tool}' requires approval: {risk_reason}",
        )
        return ticket_id

    def redeem_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Validate and redeem an unexpired AUTH- ticket."""
        ticket_id = ticket_id.strip()
        auth = CryptographicApprovalAuthority.get_instance()
        ticket = auth.get_ticket(ticket_id)
        if not ticket:
            return None

        # Check if already redeemed
        if ticket.is_redeemed:
            return None

        # Check TTL
        if time.time() > ticket.expires_at:
            return None

        return {
            "ticket_id": ticket.ticket_id,
            "action_type": ticket.action_type,
            "target": ticket.target,
            "parameters": ticket.metadata or {},
        }

    # -- Safety Checks -------------------------------------------------------

    def evaluate_risk(self, tool_name: str, args: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        Returns (risk_level, reason).
        risk_level: 'LOW' | 'HIGH'
        """
        desc = (args.get("description") or "").lower()

        if tool_name in ("click", "click_by_coordinates"):
            if is_high_risk_click(desc):
                return "HIGH", f"Click targets high-risk action: '{desc}'"

        elif tool_name in ("type_text", "type"):
            if is_high_risk_type(desc):
                return "HIGH", f"Type target asks for credential or financial details: '{desc}'"

        return "LOW", None

    def check(
        self,
        tool_name: str,
        args: Dict[str, Any],
        goal: str,
        authorized: bool = False,
    ) -> Dict[str, Any]:
        """
        Check if a proposed tool call is allowed.
        """
        risk, reason = self.evaluate_risk(tool_name, args)

        if risk == "LOW" or authorized:
            return {
                "allowed": True,
                "risk": risk,
                "message": "Action approved.",
                "ticket_id": None,
            }

        # High risk and unauthorized -> mint confirmation ticket and halt
        ticket_id = self._mint_ticket(tool_name, args, goal, reason or "High risk action")
        sanitized_args = sanitize_browser_args(tool_name, args)
        msg = (
            f"🛑 **High-Risk Browser Action Blocked**\n\n"
            f"The browser agent proposed: `{tool_name}({sanitized_args})`\n"
            f"**Reason:** {reason}\n\n"
            f"To authorize this action, run or say:\n"
            f"`aura confirm {ticket_id}` (Ticket valid for 5 minutes)."
        )
        self.record_outcome(tool_name, sanitized_args, risk, f"BLOCKED_REQUIRE_TICKET_{ticket_id}")
        return {
            "allowed": False,
            "risk": risk,
            "message": msg,
            "ticket_id": ticket_id,
        }

    # -- Audit Logging -------------------------------------------------------

    def record_outcome(self, tool_name: str, args: Dict[str, Any], risk: str, outcome: str) -> None:
        sanitized_args = sanitize_browser_args(tool_name, args)
        entry = {
            "timestamp": time.time(),
            "tool": tool_name,
            "args": sanitized_args,
            "risk": risk,
            "outcome": outcome,
        }
        try:
            with open(self.ledger_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as ex:
            logger.debug("[SafetyGate] Ledger append failed: %s", ex)
