"""
Permission Analyzer

Analyzes requests to determine what permissions are required.

The router should also determine if a request is sensitive and requires
explicit user confirmation.
"""

import logging
from typing import Any

from .risk_levels import get_risk_level, needs_confirmation

logger = logging.getLogger(__name__)


class PermissionAnalyzer:
    """
    Analyzes requests to determine permission requirements.

    This helps Aura understand when user confirmation is needed for
    potentially dangerous operations.
    """

    def __init__(self):
        """Initialize permission analyzer."""
        pass

    def analyze_request(
        self, text: str, operation_type: str = None, **details
    ) -> dict[str, Any]:
        """
        Analyze a request and determine what permissions are required.

        Args:
            text: The user request text
            operation_type: Type of operation (e.g., "file", "desktop", "network")
            **details: Additional details about the operation

        Returns:
            Dictionary with permission information
        """
        risk_level = get_risk_level(operation_type, details)
        needs_confirmation = needs_confirmation(risk_level)

        result = {
            "requires_permission": needs_confirmation,
            "permission_level": risk_level,
            "risk_level": risk_level,
            "confirmation_type": "explicit" if needs_confirmation else "none",
        }

        logger.debug(f"Permission analysis: {risk_level} for {operation_type}")

        return result

    def check_desktop_operation(self, text: str) -> dict[str, Any]:
        """
        Analyze desktop-related operations.

        Examples:
            - Shutdown computer
            - Minimize windows
            - Open application

        Args:
            text: User request text

        Returns:
            Permission analysis result
        """
        text_lower = text.lower()

        critical_ops = [
            "shutdown",
            "power off",
            "restart",
            "reboot",
            "hibernate",
            "sleep",
            "lock",
            "logout",
        ]

        high_ops = [
            "force quit",
            "terminate",
            "kill",
            "close all",
            "minimize all",
            "maximize all",
        ]

        medium_ops = ["open", "start", "launch", "run"]

        if any(op in text_lower for op in critical_ops):
            return self.analyze_request(text, "desktop_operation", risk="critical")
        elif any(op in text_lower for op in high_ops):
            return self.analyze_request(text, "desktop_operation", risk="high")
        elif any(op in text_lower for op in medium_ops):
            return self.analyze_request(text, "desktop_operation", risk="medium")

        return self.analyze_request(text, "desktop_operation", risk="low")

    def check_file_operation(self, text: str) -> dict[str, Any]:
        """
        Analyze file-related operations.

        Examples:
            - Delete file
            - Rename file
            - Compress folder
            - Read file

        Args:
            text: User request text

        Returns:
            Permission analysis result
        """
        text_lower = text.lower()

        critical_ops = [
            "delete system",
            "delete windows",
            "format",
            "wipe",
            "destroy",
            "remove completely",
        ]

        high_ops = [
            "delete file",
            "delete folder",
            "remove file",
            "delete everything",
            "trash",
            "recycle bin",
        ]

        medium_ops = [
            "rename",
            "move",
            "copy",
            "compress",
            "archive",
            "read",
            "write",
            "edit",
        ]

        if any(op in text_lower for op in critical_ops):
            return self.analyze_request(text, "file_operation", risk="critical")

        # Check for system paths
        system_paths = [
            "/system",
            "\\system",
            "\\windows",
            "/windows",
            "\\program files",
            "/program files",
        ]
        for path in system_paths:
            if path in text_lower:
                return self.analyze_request(text, "file_operation", risk="high")

        if any(op in text_lower for op in high_ops):
            return self.analyze_request(text, "file_operation", risk="high")
        elif any(op in text_lower for op in medium_ops):
            return self.analyze_request(text, "file_operation", risk="medium")

        return self.analyze_request(text, "file_operation", risk="low")

    def check_network_operation(self, text: str) -> dict[str, Any]:
        """
        Analyze network-related operations.

        Examples:
            - Firewall rules
            - Network connections
            - Internet access

        Args:
            text: User request text

        Returns:
            Permission analysis result
        """
        text_lower = text.lower()

        critical_ops = [
            "block all",
            "deny all",
            "disable firewall",
            "stop all connections",
            "kill network",
        ]

        high_ops = [
            "block port",
            "block website",
            "block ip",
            "delete firewall rule",
            "block network",
        ]

        medium_ops = ["check connection", "ping", "trace route", "find network devices"]

        if any(op in text_lower for op in critical_ops):
            return self.analyze_request(text, "network_operation", risk="critical")
        elif any(op in text_lower for op in high_ops):
            return self.analyze_request(text, "network_operation", risk="high")
        elif any(op in text_lower for op in medium_ops):
            return self.analyze_request(text, "network_operation", risk="medium")

        return self.analyze_request(text, "network_operation", risk="low")

    def check_plugin_operation(self, text: str) -> dict[str, Any]:
        """
        Analyze plugin-based operations.

        Plugin-based operations typically have known risk levels
        determined by the plugin itself.

        Args:
            text: User request text

        Returns:
            Permission analysis result (default to medium risk)
        """
        return self.analyze_request(text, "plugin_operation", risk="medium")

    def check_ai_operation(self, text: str) -> dict[str, Any]:
        """
        Analyze AI/LLM-based operations.

        These are generally safe but may require AI resources.

        Args:
            text: User request text

        Returns:
            Permission analysis result
        """
        return self.analyze_request(text, "ai_operation", risk="low")

    def check_for_sensitivity(self, text: str) -> list[str]:
        """
        Check if request contains sensitive information.

        Returns list of potential sensitive topics.

        Args:
            text: User request text

        Returns:
            List of sensitive topics found
        """
        text_lower = text.lower()

        sensitive_keywords = [
            "password",
            "api key",
            "secret",
            "token",
            "credential",
            "social security",
            "credit card",
            "ssn",
            "personal information",
            "private",
            "confidential",
        ]

        sensitive_topics = []

        for keyword in sensitive_keywords:
            if keyword in text_lower:
                sensitive_topics.append(keyword)

        return sensitive_topics
