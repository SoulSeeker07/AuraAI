"""
Risk Levels

Defines the risk levels for different operations.
Used by the permission analyzer to determine what permissions are required.
"""

from enum import Enum


class RiskLevel(str, Enum):
    """
    Risk levels for operations.

    Higher risk levels require more explicit user confirmation.
    """

    NONE = "none"  # Safe operations that don't require permission
    LOW = "low"  # Safe operations that might need confirmation
    MEDIUM = "medium"  # Operations that could cause issues
    HIGH = "high"  # Operations that are potentially dangerous
    CRITICAL = "critical"  # Operations that could cause system damage or data loss


RISK_LEVELS = {
    "none": {
        "description": "No risk, no permission required",
        "confirmation_required": False,
    },
    "low": {
        "description": "Low risk, optional confirmation",
        "confirmation_required": True,
    },
    "medium": {
        "description": "Medium risk, explicit confirmation needed",
        "confirmation_required": True,
    },
    "high": {
        "description": "High risk, strong confirmation required",
        "confirmation_required": True,
    },
    "critical": {
        "description": "Critical operations, strict confirmation required",
        "confirmation_required": True,
    },
}


def get_risk_level(operation_type: str, details: dict = None) -> str:
    """
    Get risk level for a given operation.

    Args:
        operation_type: Type of operation (file, desktop, network, etc.)
        details: Additional details about the operation

    Returns:
        Risk level string
    """
    details = details or {}

    # Critical operations
    critical_ops = [
        "shutdown",
        "reboot",
        "format",
        "delete_system",
        "modify_registry",
        "kill_process",
        "terminate_all",
    ]

    # High risk operations
    high_ops = [
        "delete_file",
        "delete_directory",
        "delete_all",
        "format_drive",
        "network_delete",
        "modify_firewall",
        "disable_security",
    ]

    # Medium risk operations
    medium_ops = [
        "move_file",
        "rename_file",
        "modify_settings",
        "change_timezone",
        "stop_service",
        "restart_service",
    ]

    # Operation checks
    if details.get("path", "").lower().startswith("/") or details.get(
        "path", ""
    ).lower().startswith("\\"):
        if (
            "system" in str(details.get("path", "")).lower()
            or "windows" in str(details.get("path", "")).lower()
            or "program files" in str(details.get("path", "")).lower()
        ):
            return RiskLevel.CRITICAL.value

    if operation_type.lower() in critical_ops:
        return RiskLevel.CRITICAL.value

    if operation_type.lower() in high_ops:
        return RiskLevel.HIGH.value

    if operation_type.lower() in medium_ops:
        return RiskLevel.MEDIUM.value

    # Default to low
    return RiskLevel.LOW.value


def needs_confirmation(risk_level: str) -> bool:
    """
    Check if confirmation is needed for a given risk level.

    Args:
        risk_level: Risk level string

    Returns:
        True if confirmation is required
    """
    return RISK_LEVELS.get(risk_level, RISK_LEVELS["none"])["confirmation_required"]


def get_risk_description(risk_level: str) -> str:
    """
    Get description of risk level.

    Args:
        risk_level: Risk level string

    Returns:
        Description of the risk level
    """
    return RISK_LEVELS.get(risk_level, RISK_LEVELS["none"])["description"]
