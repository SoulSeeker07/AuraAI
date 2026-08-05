"""
Approval Manager

Manages approval requirements for risky operations.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .models import TaskRiskLevel

logger = logging.getLogger(__name__)


class ApprovalManager:
    """
    Manages approval requirements for risky operations.

    The Approval Manager integrates with the Permission Manager (Milestone 5)
    to pause execution and request user approval before executing critical tasks.
    """

    def __init__(
        self,
        on_approval_request: (
            Callable[["ApprovalManager", str, str, str, str], bool] | None
        ) = None,
        on_approval_granted: (
            Callable[["ApprovalManager", str, str], None] | None
        ) = None,
        on_approval_denied: Callable[["ApprovalManager", str, str], None] | None = None,
        approval_timeout: int = 300,  # 5 minutes
    ):
        """
        Initialize approval manager.

        Args:
            on_approval_request: Callback when approval is requested
            on_approval_granted: Callback when approval is granted
            on_approval_denied: Callback when approval is denied
            approval_timeout: Timeout for approval in seconds
        """
        self.on_approval_request = on_approval_request
        self.on_approval_granted = on_approval_granted
        self.on_approval_denied = on_approval_denied
        self.approval_timeout = approval_timeout

        # Approval state
        self.active_approvals: dict[str, dict] = {}
        self.total_approvals_requested = 0
        self.total_approvals_granted = 0
        self.total_approvals_denied = 0

        logger.debug("Initialized approval manager")

    def requires_approval(self, task_risk_level: TaskRiskLevel, task_type: str) -> bool:
        """
        Check if a task requires approval.

        Args:
            task_risk_level: Risk level of the task
            task_type: Type of task

        Returns:
            True if approval is required
        """
        # Critical tasks always require approval
        if task_risk_level == TaskRiskLevel.CRITICAL:
            return True

        # High risk tasks for certain types require approval
        critical_types = [
            "delete",
            "remove",
            "overwrite",
            "shutdown",
            "format",
            "reset",
        ]
        if task_risk_level == TaskRiskLevel.HIGH and any(
            t in task_type.lower() for t in critical_types
        ):
            return True

        return False

    def request_approval(
        self,
        approval_id: str,
        task_id: str,
        task_description: str,
        risk_level: str,
        required_by: str,
    ) -> bool:
        """
        Request user approval for a task.

        Args:
            approval_id: Unique approval ID
            task_id: ID of the task requiring approval
            task_description: Description of the task
            risk_level: Risk level of the task
            required_by: Task or component requesting approval

        Returns:
            True if approved, False if denied or timeout
        """
        self.total_approvals_requested += 1

        approval = {
            "approval_id": approval_id,
            "task_id": task_id,
            "description": task_description,
            "risk_level": risk_level,
            "required_by": required_by,
            "requested_at": datetime.now(),
            "timeout_at": datetime.now() + self.approval_timeout,
            "granted": False,
            "denied": False,
            "denied_reason": None,
        }

        self.active_approvals[approval_id] = approval

        logger.warning(
            f"Approval requested: {approval_id[:8]} "
            f"({risk_level} level) - {task_description[:60]}"
        )

        if self.on_approval_request:
            approved = self.on_approval_request(
                self, task_description, risk_level, required_by, approval_id
            )
        else:
            # Default behavior: auto-approve unless CRITICAL
            approved = risk_level != "CRITICAL"

        if approved:
            self.grant_approval(approval_id)
        else:
            self.deny_approval(approval_id)

        return approved

    def grant_approval(self, approval_id: str) -> bool:
        """
        Grant approval for a request.

        Args:
            approval_id: ID of approval to grant

        Returns:
            True if granted, False if not found
        """
        if approval_id not in self.active_approvals:
            logger.error(f"Approval {approval_id[:8]} not found")
            return False

        approval = self.active_approvals[approval_id]
        approval["granted"] = True
        approval["granted_at"] = datetime.now()
        self.total_approvals_granted += 1

        logger.info(f"Approval granted: {approval_id[:8]}")
        logger.info(f"  Description: {approval['description'][:60]}")
        logger.info(f"  Risk level: {approval['risk_level']}")
        logger.info(f"  Requested by: {approval['required_by']}")

        if self.on_approval_granted:
            self.on_approval_granted(self, approval_id, approval["description"])

        # Clean up approval after granting
        del self.active_approvals[approval_id]

        return True

    def deny_approval(self, approval_id: str, reason: str | None = None) -> bool:
        """
        Deny approval for a request.

        Args:
            approval_id: ID of approval to deny
            reason: Reason for denial

        Returns:
            True if denied, False if not found
        """
        if approval_id not in self.active_approvals:
            logger.error(f"Approval {approval_id[:8]} not found")
            return False

        approval = self.active_approvals[approval_id]
        approval["denied"] = True
        approval["denied_reason"] = reason
        self.total_approvals_denied += 1

        logger.warning(f"Approval denied: {approval_id[:8]}")
        if reason:
            logger.warning(f"  Reason: {reason}")

        if self.on_approval_denied:
            self.on_approval_denied(self, approval_id, approval["description"])

        # Clean up approval after denial
        del self.active_approvals[approval_id]

        return True

    def get_approval_status(self, approval_id: str) -> dict | None:
        """
        Get the status of an approval request.

        Args:
            approval_id: ID of approval

        Returns:
            Approval status dictionary or None if not found
        """
        approval = self.active_approvals.get(approval_id)
        if approval:
            # Add current status
            status = {
                "approval_id": approval["approval_id"],
                "task_id": approval["task_id"],
                "description": approval["description"],
                "risk_level": approval["risk_level"],
                "required_by": approval["required_by"],
                "status": "PENDING",
                "requested_at": approval["requested_at"].isoformat(),
                "granted_at": None,
                "denied_at": None,
                "granted": False,
                "denied": False,
                "denied_reason": None,
            }

            if approval["granted"]:
                status["status"] = "GRANTED"
                status["granted_at"] = approval["granted_at"].isoformat()
                status["granted"] = True

            if approval["denied"]:
                status["status"] = "DENIED"
                status["denied_at"] = approval["granted_at"].isoformat()
                status["denied"] = True
                status["denied_reason"] = approval["denied_reason"]

            return status

        return None

    def check_pending_approvals(self) -> list[dict]:
        """
        Get all pending approvals.

        Returns:
            List of pending approval statuses
        """
        pending = []

        for approval_id, approval in self.active_approvals.items():
            status = {
                "approval_id": approval["approval_id"],
                "task_id": approval["task_id"],
                "description": approval["description"],
                "risk_level": approval["risk_level"],
                "required_by": approval["required_by"],
                "status": "PENDING",
                "requested_at": approval["requested_at"].isoformat(),
            }
            pending.append(status)

        return pending

    def get_expired_approvals(self) -> list[str]:
        """
        Get IDs of expired approvals.

        Returns:
            List of expired approval IDs
        """
        expired = []
        current_time = datetime.now()

        for approval_id, approval in self.active_approvals.items():
            if approval["granted"]:
                continue  # Don't expire granted approvals

            if current_time > approval["timeout_at"]:
                expired.append(approval_id)

        return expired

    def reject_expired_approvals(self):
        """Reject all expired approvals."""
        expired = self.get_expired_approvals()

        for approval_id in expired:
            self.deny_approval(approval_id, "Approval timeout")

        logger.info(f"Rejected {len(expired)} expired approvals")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get approval manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_approvals_requested": self.total_approvals_requested,
            "total_approvals_granted": self.total_approvals_granted,
            "total_approvals_denied": self.total_approvals_denied,
            "pending_approvals": len(self.active_approvals),
            "active_approvals": [
                self.get_approval_status(aid) for aid in self.active_approvals.keys()
            ],
            "approval_rate": (
                (self.total_approvals_granted / self.total_approvals_requested * 100)
                if self.total_approvals_requested > 0
                else 0.0
            ),
        }

    def cleanup(self):
        """Clean up pending approvals."""
        expired = self.get_expired_approvals()
        for approval_id in expired:
            self.deny_approval(approval_id, "Timeout cleanup")

        logger.info(f"Cleanup completed: {len(expired)} approvals rejected")
