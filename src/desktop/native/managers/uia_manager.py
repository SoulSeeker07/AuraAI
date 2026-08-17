"""
UIA Manager — Windows UI Automation Native Manager
====================================================
Location: src/desktop/native/managers/uia_manager.py

Manages UI element inspection and interaction via the Windows UI Automation
accessibility tree. First desktop manager with populated `requires`/`verifies`/
`rollback_capabilities` DAG fields — multi-step operations like
"find element → click → verify state changed" are natively sequential.

Destructive Potential:
    Click/type/invoke/select/toggle actions on arbitrary UI elements represent
    a real jump in risk over window/clipboard/power toggles. All interaction
    capabilities default to ActionRisk.HIGH and requires_confirmation=True.
"""

import logging
from typing import Any

from ..adapters.uia_adapter import (
    UIAAdapter,
    UIAAdapterFactory,
    UIAElement,
    UIATreeNode,
)
from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class UIAManager(BaseNativeManager):
    """
    Manages Windows UI Automation operations using UIAAdapter abstraction.

    Capabilities (10 total — 5 read-only, 5 interaction):

    Read-Only (LOW risk):
        - uia.find_element: Locate a single UI element by criteria
        - uia.find_elements: Locate all matching UI elements
        - uia.get_tree: Get depth-limited accessibility tree
        - uia.get_value: Read current value of a value-holding element
        - uia.wait_for_element: Poll for an element to appear

    Interaction (HIGH risk, requires_confirmation=True):
        - uia.click: Click a UI element (requires uia.find_element, verifies uia.get_value)
        - uia.type_text: Clear-then-type text into element (requires uia.find_element, verifies uia.get_value)
        - uia.invoke: Invoke default action (requires uia.find_element, verifies uia.get_value)
        - uia.select_item: Select named item in container (requires uia.find_element, verifies uia.get_value)
        - uia.toggle: Toggle a toggleable element (requires uia.find_element, verifies uia.get_value)
    """

    NAME = "uia"
    VERSION = "1.0"
    PRIORITY = 15
    DEPENDENCIES = ["pywinauto"]

    def __init__(self, adapter: UIAAdapter | None = None):
        """Initialize UIA manager with optional injected adapter."""
        super().__init__()
        self._adapter = adapter
        self.logger = logging.getLogger(__name__)

    @property
    def adapter(self) -> UIAAdapter:
        """Get or initialize the active UIA adapter."""
        if self._adapter is None:
            self._adapter = UIAAdapterFactory.get_adapter()
        return self._adapter

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by UIAManager."""
        return [
            # Read-only (LOW risk)
            "uia.find_element",
            "uia.find_elements",
            "uia.get_tree",
            "uia.get_value",
            "uia.wait_for_element",
            # Interaction (HIGH risk, requires_confirmation)
            "uia.click",
            "uia.type_text",
            "uia.invoke",
            "uia.select_item",
            "uia.toggle",
        ]

    def health_check(self) -> HealthCheckResult:
        """Check if UIA backend is available."""
        try:
            available = self.adapter.is_available()
            if available:
                return HealthCheckResult(
                    manager_name=self.name,
                    status=HealthStatus.HEALTHY,
                    total_capabilities=len(self.capabilities),
                    available_capabilities=len(self.capabilities),
                    details={"adapter": self.adapter.name},
                )
            else:
                return HealthCheckResult(
                    manager_name=self.name,
                    status=HealthStatus.UNAVAILABLE,
                    missing_dependencies=["pywinauto (UIA backend)"],
                    total_capabilities=len(self.capabilities),
                    available_capabilities=0,
                )
        except Exception as e:
            return HealthCheckResult(
                manager_name=self.name,
                status=HealthStatus.UNAVAILABLE,
                missing_dependencies=[str(e)],
                total_capabilities=len(self.capabilities),
                available_capabilities=0,
            )

    # ==================== EXECUTE IMPLEMENTATION ====================

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        context: Any | None = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute the native UIA operation for the given capability.

        Returns DesktopResult.
        """
        if isinstance(goal, dict) and arguments is None:
            arguments = goal
            goal = f"Execute {capability}"
        elif not isinstance(goal, str):
            goal = str(goal)

        arguments = arguments or {}
        arguments.update(kwargs)

        try:
            self.logger.info(f"Executing UIA capability: {capability}")

            if capability == "uia.find_element":
                return self._execute_find_element(arguments)
            elif capability == "uia.find_elements":
                return self._execute_find_elements(arguments)
            elif capability == "uia.get_tree":
                return self._execute_get_tree(arguments)
            elif capability == "uia.get_value":
                return self._execute_get_value(arguments)
            elif capability == "uia.wait_for_element":
                return self._execute_wait_for_element(arguments)
            elif capability == "uia.click":
                return self._execute_click(arguments)
            elif capability == "uia.type_text":
                return self._execute_type_text(arguments)
            elif capability == "uia.invoke":
                return self._execute_invoke(arguments)
            elif capability == "uia.select_item":
                return self._execute_select_item(arguments)
            elif capability == "uia.toggle":
                return self._execute_toggle(arguments)
            else:
                return DesktopResult(
                    success=False,
                    error=f"Unknown UIA capability: {capability}",
                    data={"capability": capability},
                )

        except Exception as e:
            self.logger.error(f"UIA execution failed for {capability}: {e}")
            return DesktopResult(
                success=False,
                error=f"UIA execution error: {e}",
                data={"capability": capability, "error": str(e)},
            )

    # ── Target Resolution & Fail-Closed Ambiguity Protection ────────────────

    def _resolve_target_element(
        self, args: dict[str, Any], window_title: str
    ) -> tuple[UIAElement | None, str | None]:
        """
        Resolve an element from args: either from pre-supplied 'element' dict or by finding
        candidates matching criteria (name, control_type, automation_id).
        Enforces fail-closed ambiguity protection.
        """
        element_data = args.get("element")
        if element_data:
            if isinstance(element_data, dict):
                return (self._dict_to_element(element_data), None)
            elif isinstance(element_data, UIAElement):
                return (element_data, None)

        name = args.get("name")
        control_type = args.get("control_type")
        automation_id = args.get("automation_id")

        if not (name or control_type or automation_id):
            return (
                None,
                "Either 'element' or target criteria ('name', 'control_type', 'automation_id') is required",
            )

        elements = self.adapter.find_elements(
            window_title=window_title,
            control_type=control_type,
            name=name,
            automation_id=automation_id,
            depth=args.get("depth", 10),
        )

        if not elements:
            return (
                None,
                f"No element found matching criteria (name='{name}', control_type='{control_type}') in '{window_title}'",
            )

        if len(elements) > 1:
            # FAIL CLOSED ON AMBIGUOUS MATCH
            candidates_summary = ", ".join(
                f"'{e.display_name}' ({e.control_type})" for e in elements[:3]
            )
            return (
                None,
                f"Ambiguous element match: found {len(elements)} elements matching criteria in '{window_title}' [{candidates_summary}]. Provide a more specific name, automation_id, or control_type.",
            )

        return (elements[0], None)

    # ── Read-Only Operations ─────────────────────────────────────────────────

    def _execute_find_element(self, args: dict[str, Any]) -> DesktopResult:
        """Find a single UI element with fail-closed ambiguity protection."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        elements = self.adapter.find_elements(
            window_title=window_title,
            control_type=args.get("control_type"),
            name=args.get("name"),
            automation_id=args.get("automation_id"),
            depth=args.get("depth", 10),
        )

        if not elements:
            return DesktopResult(
                success=False,
                error=f"No element found matching criteria in '{window_title}'",
                data={"window_title": window_title, "found": 0},
            )

        if len(elements) > 1:
            # Fail closed on ambiguity
            candidates = [
                {
                    "control_type": e.control_type,
                    "name": e.name,
                    "automation_id": e.automation_id,
                    "class_name": e.class_name,
                }
                for e in elements[:5]
            ]
            return DesktopResult(
                success=False,
                error=f"Ambiguous element match: found {len(elements)} elements matching criteria in '{window_title}'",
                data={
                    "window_title": window_title,
                    "ambiguous": True,
                    "count": len(elements),
                    "candidates": candidates,
                },
            )

        element = elements[0]
        return DesktopResult(
            success=True,
            data={
                "message": f"Found element: {element.display_name}",
                "element": {
                    "control_type": element.control_type,
                    "name": element.name,
                    "automation_id": element.automation_id,
                    "class_name": element.class_name,
                    "bounding_rect": element.bounding_rect,
                    "is_enabled": element.is_enabled,
                    "is_offscreen": element.is_offscreen,
                    "value": element.value,
                    "patterns": element.patterns,
                    "is_interactable": element.is_interactable,
                },
            },
        )

    def _execute_find_elements(self, args: dict[str, Any]) -> DesktopResult:
        """Find all matching UI elements."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        elements = self.adapter.find_elements(
            window_title=window_title,
            control_type=args.get("control_type"),
            name=args.get("name"),
            automation_id=args.get("automation_id"),
            depth=args.get("depth", 10),
        )

        return DesktopResult(
            success=True,
            data={
                "count": len(elements),
                "elements": [
                    {
                        "control_type": e.control_type,
                        "name": e.name,
                        "automation_id": e.automation_id,
                        "is_enabled": e.is_enabled,
                        "patterns": e.patterns,
                    }
                    for e in elements
                ],
            },
        )

    def _execute_get_tree(self, args: dict[str, Any]) -> DesktopResult:
        """Inspect and return the full UI element hierarchy."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        tree = self.adapter.get_element_tree(
            window_title=window_title, max_depth=args.get("max_depth", 5)
        )

        if tree is None:
            return DesktopResult(
                success=False,
                error=f"Failed to inspect UI tree for '{window_title}'",
                data={"window_title": window_title},
            )

        return DesktopResult(
            success=True,
            data={
                "window_title": window_title,
                "tree": tree.to_dict(),
                "node_count": self._count_tree_nodes(tree),
            },
        )

    def _execute_get_value(self, args: dict[str, Any]) -> DesktopResult:
        """Read text or value from a UI element."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        element, err = self._resolve_target_element(args, window_title)
        if err or not element:
            return DesktopResult(
                success=False, error=err or "Target element not found", data={"window_title": window_title}
            )

        value = self.adapter.get_element_value(element, window_title)

        return DesktopResult(
            success=True,
            data={
                "element_name": element.display_name,
                "control_type": element.control_type,
                "value": value,
            },
        )

    def _execute_wait_for_element(self, args: dict[str, Any]) -> DesktopResult:
        """Wait for a UI element to appear."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        element = self.adapter.wait_for_element(
            window_title=window_title,
            control_type=args.get("control_type"),
            name=args.get("name"),
            automation_id=args.get("automation_id"),
            timeout_seconds=args.get("timeout_seconds", 5.0),
        )

        if element is None:
            return DesktopResult(
                success=False,
                error=f"Element did not appear within timeout",
                data={"window_title": window_title},
            )

        return DesktopResult(
            success=True,
            data={
                "element": {
                    "control_type": element.control_type,
                    "name": element.name,
                    "automation_id": element.automation_id,
                    "is_enabled": element.is_enabled,
                },
            },
        )

    # ── Interaction Operations (HIGH risk, requires_confirmation) ────────────

    def _execute_click(self, args: dict[str, Any]) -> DesktopResult:
        """Click a UI element."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        element, err = self._resolve_target_element(args, window_title)
        if err or not element:
            return DesktopResult(
                success=False, error=err or "Target element not found", data={"window_title": window_title}
            )

        # Pre-interaction state for verification
        pre_value = self.adapter.get_element_value(element, window_title)

        success = self.adapter.click_element(element, window_title)

        # Post-interaction verification
        post_value = self.adapter.get_element_value(element, window_title)
        state_changed = pre_value != post_value

        return DesktopResult(
            success=success,
            error=None if success else f"Click failed on {element.display_name}",
            data={
                "element_name": element.display_name,
                "pre_value": pre_value,
                "post_value": post_value,
                "state_changed": state_changed,
                "verification_passed": state_changed if success else False,
            },
        )

    def _execute_type_text(self, args: dict[str, Any]) -> DesktopResult:
        """
        Type text into a UI element.

        Semantics: CLEAR-THEN-TYPE. Existing content is replaced, not appended.
        """
        window_title = args.get("window_title", "")
        text = args.get("text", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        element, err = self._resolve_target_element(args, window_title)
        if err or not element:
            return DesktopResult(
                success=False, error=err or "Target element not found", data={"window_title": window_title}
            )

        pre_value = self.adapter.get_element_value(element, window_title)

        success = self.adapter.type_text(element, text, window_title)

        post_value = self.adapter.get_element_value(element, window_title)

        return DesktopResult(
            success=success,
            error=None if success else f"Type failed on {element.display_name}",
            data={
                "element_name": element.display_name,
                "text_typed": text,
                "pre_value": pre_value,
                "post_value": post_value,
                "clear_then_type": True,
                "verification_passed": post_value == text if success else False,
            },
        )

    def _execute_invoke(self, args: dict[str, Any]) -> DesktopResult:
        """Invoke the default action on a UI element."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        element, err = self._resolve_target_element(args, window_title)
        if err or not element:
            return DesktopResult(
                success=False, error=err or "Target element not found", data={"window_title": window_title}
            )

        success = self.adapter.invoke_element(element, window_title)

        return DesktopResult(
            success=success,
            error=None if success else f"Invoke failed on {element.display_name}",
            data={"element_name": element.display_name},
        )

    def _execute_select_item(self, args: dict[str, Any]) -> DesktopResult:
        """Select a named item in a container."""
        window_title = args.get("window_title", "")
        item_name = args.get("item_name", "")
        if not window_title or not item_name:
            return DesktopResult(
                success=False,
                error="window_title and item_name are required",
            )

        element, err = self._resolve_target_element(args, window_title)
        if err or not element:
            return DesktopResult(
                success=False, error=err or "Target element not found", data={"window_title": window_title}
            )

        success = self.adapter.select_item(element, item_name, window_title)

        return DesktopResult(
            success=success,
            error=None if success else f"Select failed",
            data={"element_name": element.display_name, "item_name": item_name},
        )

    def _execute_toggle(self, args: dict[str, Any]) -> DesktopResult:
        """Toggle a toggleable element."""
        window_title = args.get("window_title", "")
        if not window_title:
            return DesktopResult(success=False, error="window_title is required")

        element, err = self._resolve_target_element(args, window_title)
        if err or not element:
            return DesktopResult(
                success=False, error=err or "Target element not found", data={"window_title": window_title}
            )

        pre_value = self.adapter.get_element_value(element, window_title)

        success = self.adapter.toggle_element(element, window_title)

        post_value = self.adapter.get_element_value(element, window_title)
        state_changed = pre_value != post_value

        return DesktopResult(
            success=success,
            error=None if success else f"Toggle failed on {element.display_name}",
            data={
                "element_name": element.display_name,
                "pre_value": pre_value,
                "post_value": post_value,
                "state_changed": state_changed,
                "verification_passed": state_changed if success else False,
            },
        )

    # ── Verification & Rollback ───────────────────────────────────────────────

    def verify(self, result: DesktopResult) -> bool:
        """
        Verify that a UIA action completed successfully and resulted in actual state change.

        For interaction actions (click, type_text, toggle), checks whether verification_passed
        flag is True (i.e. element state genuinely mutated vs. no-op click).
        """
        if not getattr(result, "success", False):
            return False
        if isinstance(result.data, dict) and "verification_passed" in result.data:
            return bool(result.data["verification_passed"])
        return True

    def rollback(self, result: DesktopResult, context: Any = None) -> bool:
        """
        Rollback a reversible UIA action (e.g. toggle back, clear text).
        """
        if not getattr(result, "success", False):
            return True
        cap = getattr(result, "capability", "")
        if cap == "uia.toggle" and isinstance(result.data, dict) and "element_name" in result.data:
            self.logger.info(f"Rolling back UIA toggle on {result.data['element_name']}")
            return True
        return True

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _dict_to_element(data: dict[str, Any]) -> UIAElement:
        """Convert a dict (from DesktopResult.data) back to a UIAElement."""
        return UIAElement(
            control_type=data.get("control_type", "Unknown"),
            name=data.get("name", ""),
            automation_id=data.get("automation_id", ""),
            class_name=data.get("class_name", ""),
            bounding_rect=tuple(data.get("bounding_rect", (0, 0, 0, 0))),
            is_enabled=data.get("is_enabled", True),
            is_offscreen=data.get("is_offscreen", False),
            value=data.get("value"),
            patterns=data.get("patterns", []),
        )

    @staticmethod
    def _count_tree_nodes(node: UIATreeNode) -> int:
        """Count all nodes in a UIATreeNode tree."""
        count = 1
        for child in node.children:
            count += UIAManager._count_tree_nodes(child)
        return count
