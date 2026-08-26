"""
safety_gate.py

Action-level safety gating for autonomous browser tool calls.
Inspects the model's concrete proposed tool calls (rather than fuzzy regexes
on user goal text) to identify high-risk financial, credential, or destructive actions.
Issues audit tickets with TTLs and logs audit ledger events.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TICKET_TTL_SECONDS = 300  # 5 minutes

HIGH_RISK_CLICK_PATTERNS = [
    r"\b(?:place\s+order|buy\s+now|pay\s+now|complete\s+order|submit\s+payment|checkout)\b",
    r"\b(?:confirm\s+purchase|purchase|pay\s+with|transfer\s+money|send\s+payment)\b",
    r"\b(?:delete\s+account|terminate\s+account|cancel\s+subscription)\b",
]

HIGH_RISK_TYPE_PATTERNS = [
    r"\b(?:password|cvv|cvc|card\s*number|credit\s*card|debit\s*card|security\s*code|ssn|pin)\b",
    r"\b(?:2fa|otp|one\s*time\s*password|authenticator\s*code)\b",
]


class SafetyGate:
    """Evaluates safety risks on proposed browser actions and manages authorization tickets."""

    def __init__(self, ticket_file: Optional[Path] = None, ledger_file: Optional[Path] = None):
        aura_dir = Path.home() / ".aura"
        aura_dir.mkdir(parents=True, exist_ok=True)
        self.ticket_file = ticket_file or (aura_dir / "browser_tickets.json")
        self.ledger_file = ledger_file or (aura_dir / "browser_audit_ledger.jsonl")

    # -- Ticket Persistence --------------------------------------------------

    def _load_tickets(self) -> Dict[str, Dict[str, Any]]:
        if self.ticket_file.exists():
            try:
                return json.loads(self.ticket_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_tickets(self, tickets: Dict[str, Dict[str, Any]]) -> None:
        try:
            self.ticket_file.write_text(json.dumps(tickets, indent=2), encoding="utf-8")
        except Exception as ex:
            logger.debug("[SafetyGate] Failed to save tickets: %s", ex)

    def _mint_ticket(self, tool: str, args: Dict[str, Any], goal: str, risk_reason: str) -> str:
        ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
        tickets = self._load_tickets()
        tickets[ticket_id] = {
            "ticket_id": ticket_id,
            "tool": tool,
            "args": args,
            "goal": goal,
            "reason": risk_reason,
            "created_at": time.time(),
        }
        self._save_tickets(tickets)
        return ticket_id

    def redeem_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        ticket_id = ticket_id.strip().upper()
        tickets = self._load_tickets()
        ticket = tickets.get(ticket_id)
        if not ticket:
            return None

        # Check TTL
        if time.time() - ticket.get("created_at", 0) > TICKET_TTL_SECONDS:
            del tickets[ticket_id]
            self._save_tickets(tickets)
            return None

        # Clean up redeemed ticket
        del tickets[ticket_id]
        self._save_tickets(tickets)
        return ticket

    # -- Safety Checks -------------------------------------------------------

    def evaluate_risk(self, tool_name: str, args: Dict[str, Any]) -> tuple[str, Optional[str]]:
        """
        Returns (risk_level, reason).
        risk_level: 'LOW' | 'HIGH'
        """
        if tool_name == "click":
            desc = (args.get("description") or "").lower()
            for pat in HIGH_RISK_CLICK_PATTERNS:
                if re.search(pat, desc, re.IGNORECASE):
                    return "HIGH", f"Click targets high-risk action matching pattern '{pat}': '{desc}'"

        elif tool_name == "type_text":
            desc = (args.get("description") or "").lower()
            for pat in HIGH_RISK_TYPE_PATTERNS:
                if re.search(pat, desc, re.IGNORECASE):
                    return "HIGH", f"Type target asks for credential/financial details matching '{pat}': '{desc}'"

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
        msg = (
            f"🛑 **High-Risk Action Blocked**\n\n"
            f"The browser agent proposed: `{tool_name}({args})`\n"
            f"**Reason:** {reason}\n\n"
            f"To authorize this action, run or say:\n"
            f"`aura confirm {ticket_id}` (Ticket valid for 5 minutes)."
        )
        self.record_outcome(tool_name, args, risk, f"BLOCKED_REQUIRE_TICKET_{ticket_id}")
        return {
            "allowed": False,
            "risk": risk,
            "message": msg,
            "ticket_id": ticket_id,
        }

    # -- Audit Logging -------------------------------------------------------

    def record_outcome(self, tool_name: str, args: Dict[str, Any], risk: str, outcome: str) -> None:
        entry = {
            "timestamp": time.time(),
            "tool": tool_name,
            "args": args,
            "risk": risk,
            "outcome": outcome,
        }
        try:
            with open(self.ledger_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as ex:
            logger.debug("[SafetyGate] Ledger append failed: %s", ex)
