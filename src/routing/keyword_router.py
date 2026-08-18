"""
Keyword Router (Level 1)

Fast local detection of requests using keyword/pattern matching.

This is Level 1 of the three-level routing system.
It handles simple requests almost instantly without AI.

Responsibility:
    - Choose the best capability to handle the request
    - Not to understand the request in detail

Priority Handling:
    1. Local Capability (fastest)
    2. Plugin
    3. Memory
    4. Knowledge
    5. Agent
    6. LLM
"""

import logging
from typing import Any

from .capability_types import CapabilityPriority, CapabilityType
from .routing_result import RoutingResult

logger = logging.getLogger(__name__)


class KeywordRouter:
    """
    Fast keyword-based router for simple requests.

    This router uses pattern matching to route requests to the appropriate
    capability. It handles the majority of common requests without AI.
    """

    def __init__(self):
        """Initialize keyword router."""
        self.rules = self._build_rules()

    def _build_rules(self) -> dict[str, list[dict[str, Any]]]:
        """
        Build keyword rules for different capabilities.

        Returns:
            Dictionary mapping capability types to keyword rules
        """
        rules = {
            CapabilityType.DESKTOP: [
                # Window management
                {
                    "keywords": [
                        "minimize",
                        "minimise",
                        "maximize",
                        "maximise",
                        "maximize all",
                        "maximise all",
                    ],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": False,
                },
                {
                    "keywords": ["close", "close all", "close window"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": False,
                },
                {
                    "keywords": ["hide", "hide all"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                # Application management
                {
                    "keywords": ["open", "launch", "start", "run"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["quit", "force quit", "terminate", "kill"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": True,
                },
                {
                    "keywords": ["close application"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                # System operations
                {
                    "keywords": ["shutdown", "power off", "reboot", "restart"],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": ["sleep", "hibernate", "lock", "log out"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.FILESYSTEM: [
                # File operations
                {
                    "keywords": ["create", "new", "make"],
                    "confidence": 0.80,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": [
                        "delete",
                        "remove",
                        "trash",
                        "recycle",
                        "destroy",
                        "erase",
                    ],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": [
                        "move",
                        "rename",
                        "rename file",
                        "rename folder",
                        "change name",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": False,
                },
                {
                    "keywords": ["copy", "duplicate", "clone"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["compress", "archive", "zip", "unzip"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["delete all", "clear", "wipe", "format"],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": ["read", "view", "show", "display", "open file"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.BROWSER: [
                {
                    "keywords": ["search", "find", "look for", "browse"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["open", "visit", "navigate to", "go to"],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["close", "quit"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["new tab", "open new tab"],
                    "confidence": 0.80,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.VISION: [
                {
                    "keywords": ["analyze", "describe", "explain", "what is"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["read", "extract text", "ocr", "recognize"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["what is in", "what do you see", "identify"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.MEMORY: [
                {
                    "keywords": ["remember", "store", "save", "keep", "note"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": False,
                },
                {
                    "keywords": [
                        "forget",
                        "erase memory",
                        "remove memory",
                        "delete from memory",
                    ],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": False,
                },
                {
                    "keywords": [
                        "what do you remember",
                        "recall",
                        "retrieve",
                        "summarize my memories",
                        "my facts",
                    ],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["profile", "my preferences", "my habits"],
                    "confidence": 0.80,
                    "priority": CapabilityPriority.LOW,
                    "requires_permission": False,
                },
            ],
            CapabilityType.KNOWLEDGE: [
                {
                    "keywords": [
                        "explain",
                        "what is",
                        "how does",
                        "describe",
                        "tell me about",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["summarize", "shorten", "brief", "concise"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["create summary", "generate summary"],
                    "confidence": 0.80,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.TERMINAL: [
                {
                    "keywords": [
                        "run command",
                        "execute command",
                        "terminal",
                        "shell",
                        "command line",
                        "powershell",
                        "cmd",
                    ],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": ["run script", "execute script", "bash"],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
            ],
            CapabilityType.INPUT: [
                {
                    "keywords": [
                        "click at",
                        "click on",
                        "double click",
                        "right click",
                    ],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": [
                        "type text",
                        "press key",
                        "hotkey",
                        "keyboard shortcut",
                        "press enter",
                        "press escape",
                    ],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": [
                        "drag",
                        "scroll mouse",
                        "move mouse",
                        "mouse position",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": True,
                },
            ],
            CapabilityType.SCREEN_ACTION: [
                {
                    "keywords": [
                        "find on screen",
                        "locate on screen",
                        "find button",
                        "find element",
                        "click the button",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": [
                        "capture screen",
                        "take screenshot",
                        "screen capture",
                        "screenshot",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.NOTIFICATION: [
                {
                    "keywords": [
                        "notify",
                        "notification",
                        "send notification",
                        "toast",
                        "alert me",
                        "show alert",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.SCHEDULER: [
                {
                    "keywords": [
                        "schedule",
                        "remind me",
                        "set reminder",
                        "in 10 minutes",
                        "every hour",
                        "every day",
                        "at 5pm",
                        "cron",
                        "recurring",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.EMAIL: [
                {
                    "keywords": [
                        "send email",
                        "compose email",
                        "email",
                        "mail",
                        "inbox",
                        "read email",
                        "check email",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["reply to email", "forward email", "draft email"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.CALENDAR: [
                {
                    "keywords": [
                        "calendar",
                        "event",
                        "meeting",
                        "schedule meeting",
                        "appointment",
                        "create event",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["todo", "to-do", "task list", "create task"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.OFFICE: [
                {
                    "keywords": [
                        "create document",
                        "word document",
                        "spreadsheet",
                        "excel",
                        "presentation",
                        "powerpoint",
                        "create pdf",
                        "merge pdf",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
                {
                    "keywords": ["read document", "extract text", "convert document"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.DOCKER: [
                {
                    "keywords": [
                        "docker",
                        "container",
                        "docker compose",
                        "docker image",
                        "docker build",
                        "docker pull",
                    ],
                    "confidence": 0.95,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": True,
                },
            ],
            CapabilityType.MCP: [
                {
                    "keywords": [
                        "mcp",
                        "model context protocol",
                        "tool server",
                        "mcp server",
                        "connect mcp",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.SOFTWARE: [
                {
                    "keywords": [
                        "install software",
                        "uninstall",
                        "update software",
                        "winget",
                        "choco",
                        "scoop",
                        "pip install",
                        "npm install",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": True,
                },
                {
                    "keywords": ["list installed", "installed software", "installed apps"],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": False,
                },
            ],
            CapabilityType.SECURITY: [
                {
                    "keywords": [
                        "firewall",
                        "vpn",
                        "antivirus",
                        "security scan",
                        "virus scan",
                        "windows defender",
                    ],
                    "confidence": 0.90,
                    "priority": CapabilityPriority.HIGH,
                    "requires_permission": True,
                },
                {
                    "keywords": [
                        "clear history",
                        "clear cache",
                        "clear temp files",
                        "privacy",
                    ],
                    "confidence": 0.85,
                    "priority": CapabilityPriority.MEDIUM,
                    "requires_permission": True,
                },
            ],
        }

        return rules

    def route(self, text: str) -> RoutingResult | None:
        """
        Route request using keyword matching.

        This is Level 1 - fast local detection without AI.

        Args:
            text: User request text

        Returns:
            RoutingResult if a rule matches, None otherwise
        """
        text_lower = text.lower().strip()

        # Check each capability type for matching rules
        for capability_type, rule_list in self.rules.items():
            for rule in rule_list:
                for keyword in rule["keywords"]:
                    if keyword in text_lower:
                        logger.debug(
                            f"Keyword match: {capability_type.value} -> {keyword} "
                            f"(confidence: {rule['confidence']})"
                        )
                        return self._create_routing_result(
                            capability_type,
                            rule["confidence"],
                            rule["priority"],
                            rule["requires_permission"],
                            keyword,
                        )

        return None

    def _create_routing_result(
        self,
        capability_type: CapabilityType,
        confidence: float,
        priority: CapabilityPriority,
        requires_permission: bool,
        matched_keyword: str = "",
    ) -> RoutingResult:
        """
        Create a RoutingResult from rule data.

        Args:
            capability_type: The capability type
            confidence: Confidence score
            priority: Priority level
            requires_permission: Whether permission is required
            matched_keyword: The keyword that triggered the match

        Returns:
            RoutingResult object
        """
        result = RoutingResult(
            capability=capability_type,
            confidence=confidence,
            priority=priority,
            requires_permission=requires_permission,
        )

        result.metadata["matched_keyword"] = matched_keyword
        result.metadata["routing_level"] = "level1"  # Keyword-based routing

        if requires_permission:
            result.set_permission_required("confirmation")

        return result

    def get_priority_order(self) -> list[CapabilityType]:
        """
        Get the priority order of capabilities.

        Returns:
            List of capability types in priority order
        """
        return [
            CapabilityType.DESKTOP,
            CapabilityType.INPUT,
            CapabilityType.SCREEN_ACTION,
            CapabilityType.TERMINAL,
            CapabilityType.FILESYSTEM,
            CapabilityType.BROWSER,
            CapabilityType.NOTIFICATION,
            CapabilityType.SCHEDULER,
            CapabilityType.VISION,
            CapabilityType.EMAIL,
            CapabilityType.CALENDAR,
            CapabilityType.OFFICE,
            CapabilityType.DOCKER,
            CapabilityType.MCP,
            CapabilityType.SOFTWARE,
            CapabilityType.SECURITY,
            CapabilityType.MEMORY,
            CapabilityType.KNOWLEDGE,
            CapabilityType.PROVIDER,
        ]
