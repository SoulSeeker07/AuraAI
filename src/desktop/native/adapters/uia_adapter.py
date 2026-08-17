"""
UIA Adapter — Windows UI Automation Accessibility Tree Interface
=================================================================
Location: src/desktop/native/adapters/uia_adapter.py

Provides structured access to the Windows UI Automation accessibility tree
via pywinauto's UIA backend. Every public method is COM-thread-safe.

Key design decisions:
- `type_text()` uses clear-then-type semantics (not append) to prevent
  silent data-loss bugs in form fields where existing content isn't visible.
- All COM calls are wrapped via `@com_thread_safe` from `com_threading.py`.
- Element identification uses automation_id > name > control_type priority
  for stability across UI locale changes.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base_adapter import BaseNativeAdapter
from .com_threading import com_thread_safe

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────


@dataclass
class UIAElement:
    """
    Structured representation of a single UI Automation element.

    Attributes:
        control_type: UIA control type name (e.g. "Button", "Edit", "ComboBox").
        name: Human-readable name of the element (may be empty for unlabeled controls).
        automation_id: Stable developer-assigned identifier (preferred for matching).
        class_name: Win32 window class name.
        bounding_rect: Screen coordinates as (left, top, right, bottom).
        is_enabled: Whether the element accepts user input.
        is_offscreen: Whether the element is currently scrolled/hidden off-screen.
        value: Current value for value-holding controls (Edit, Slider, etc.).
        patterns: List of supported UIA patterns (e.g. ["Invoke", "Value", "Toggle"]).
    """

    control_type: str
    name: str
    automation_id: str = ""
    class_name: str = ""
    bounding_rect: tuple[int, int, int, int] = (0, 0, 0, 0)
    is_enabled: bool = True
    is_offscreen: bool = False
    value: str | None = None
    patterns: list[str] = field(default_factory=list)

    @property
    def is_interactable(self) -> bool:
        """Whether this element can likely accept user interaction."""
        return self.is_enabled and not self.is_offscreen

    @property
    def display_name(self) -> str:
        """Best human-readable identifier for this element."""
        if self.name:
            return f"{self.control_type}('{self.name}')"
        if self.automation_id:
            return f"{self.control_type}[{self.automation_id}]"
        return f"{self.control_type}({self.class_name})"


@dataclass
class UIATreeNode:
    """
    A node in the accessibility tree with recursive children.

    Attributes:
        element: The UIAElement at this node.
        children: Child nodes (populated up to the requested depth limit).
        depth: The depth of this node relative to the walk root.
    """

    element: UIAElement
    children: list[UIATreeNode] = field(default_factory=list)
    depth: int = 0


# ── Abstract Adapter ──────────────────────────────────────────────────────────


class UIAAdapter(BaseNativeAdapter, ABC):
    """
    Abstract base for UI Automation adapters.

    Concrete implementations must provide accessibility-tree walking and
    element interaction via the Windows UIA API.
    """

    @abstractmethod
    def find_element(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> UIAElement | None:
        """Find a single element matching the given criteria."""
        ...

    @abstractmethod
    def find_elements(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> list[UIAElement]:
        """Find all elements matching the given criteria."""
        ...

    @abstractmethod
    def get_element_tree(
        self,
        window_title: str,
        depth: int = 3,
    ) -> UIATreeNode | None:
        """Get the accessibility tree rooted at the given window, depth-limited."""
        ...

    @abstractmethod
    def click_element(self, element: UIAElement, window_title: str) -> bool:
        """Click a UI element. Returns True if click dispatched successfully."""
        ...

    @abstractmethod
    def type_text(self, element: UIAElement, text: str, window_title: str) -> bool:
        """
        Clear the element's current content and type new text.

        Semantics: CLEAR-THEN-TYPE (not append). Any existing content in the
        target element is replaced entirely. This prevents silent data-loss bugs
        in form fields where prior content isn't visible to the caller.

        Returns True if text was set successfully.
        """
        ...

    @abstractmethod
    def get_element_value(self, element: UIAElement, window_title: str) -> str | None:
        """Read the current value of a value-holding element."""
        ...

    @abstractmethod
    def invoke_element(self, element: UIAElement, window_title: str) -> bool:
        """Invoke the default action on an element (for buttons/menu items supporting Invoke pattern)."""
        ...

    @abstractmethod
    def select_item(self, element: UIAElement, item_name: str, window_title: str) -> bool:
        """Select a named item in a selection container (combo box, list view, etc.)."""
        ...

    @abstractmethod
    def toggle_element(self, element: UIAElement, window_title: str) -> bool:
        """Toggle a toggleable element (checkbox, toggle button). Returns True if toggled."""
        ...

    @abstractmethod
    def wait_for_element(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.5,
    ) -> UIAElement | None:
        """Poll for an element to appear, returning it or None on timeout."""
        ...


# ── Pywinauto Implementation ─────────────────────────────────────────────────


class PywinautoUIAAdapter(UIAAdapter):
    """
    Primary UIA adapter using pywinauto's UIA backend.

    Every public method is decorated with @com_thread_safe to ensure
    COM is initialized for the calling thread — preventing the
    CO_E_NOTINITIALIZED failures seen with WMI adapters in worker threads.
    """

    NAME = "pywinauto_uia"
    PRIORITY = 10

    @com_thread_safe
    def is_available(self) -> bool:
        """Check if pywinauto UIA backend is functional."""
        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            # Attempt to enumerate top-level windows — a minimal smoke test
            windows = desktop.windows()
            return len(windows) >= 0  # Even 0 windows is valid (unlikely but not broken)
        except Exception as e:
            logger.debug(f"PywinautoUIAAdapter not available: {e}")
            return False

    @com_thread_safe
    def find_element(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> UIAElement | None:
        """Find a single element matching the given criteria in the specified window."""
        try:
            wrapper = self._find_wrapper(window_title, control_type, name, automation_id, depth)
            if wrapper is None:
                return None
            return self._wrapper_to_element(wrapper)
        except Exception as e:
            logger.warning(f"UIA find_element failed: {e}")
            return None

    @com_thread_safe
    def find_elements(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> list[UIAElement]:
        """Find all elements matching the given criteria."""
        try:
            wrappers = self._find_wrappers(window_title, control_type, name, automation_id, depth)
            return [self._wrapper_to_element(w) for w in wrappers]
        except Exception as e:
            logger.warning(f"UIA find_elements failed: {e}")
            return []

    @com_thread_safe
    def get_element_tree(
        self,
        window_title: str,
        depth: int = 3,
    ) -> UIATreeNode | None:
        """Get the accessibility tree rooted at the given window, limited to `depth` levels."""
        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            windows = desktop.windows(title_re=f".*{window_title}.*")
            if not windows:
                logger.info(f"UIA: No window matching '{window_title}'")
                return None

            win = windows[0]
            return self._build_tree(win, current_depth=0, max_depth=depth)
        except Exception as e:
            logger.warning(f"UIA get_element_tree failed: {e}")
            return None

    @com_thread_safe
    def click_element(self, element: UIAElement, window_title: str) -> bool:
        """Click a UI element by re-locating it and dispatching a click or invoke."""
        try:
            wrapper = self._relocate_element(element, window_title)
            if wrapper is None:
                logger.warning(f"UIA: Could not relocate element {element.display_name}")
                return False

            # Prioritize programmatic UIA Invoke pattern (instant, robust in all desktop sessions)
            invoked = False
            try:
                iface = getattr(wrapper, "iface_invoke", None)
                if iface is not None:
                    iface.Invoke()
                    invoked = True
                elif hasattr(wrapper, "invoke"):
                    wrapper.invoke()
                    invoked = True
            except Exception:
                pass

            if not invoked:
                try:
                    wrapper.click_input()
                except Exception:
                    try:
                        wrapper.click()
                    except Exception as e:
                        logger.error(f"UIA click failed: {e}")
                        return False

            logger.info(f"UIA: Clicked {element.display_name}")
            return True
        except Exception as e:
            logger.error(f"UIA click_element failed on {element.display_name}: {e}")
            return False

    @com_thread_safe
    def type_text(self, element: UIAElement, text: str, window_title: str) -> bool:
        """
        Clear existing content and type new text into the element.

        Semantics: CLEAR-THEN-TYPE. Any existing content in the target element
        is selected-all and replaced. This is intentional — append mode creates
        silent data-loss bugs when existing content isn't visible to the caller.

        Returns True if text was set successfully.
        """
        try:
            wrapper = self._relocate_element(element, window_title)
            if wrapper is None:
                logger.warning(f"UIA: Could not relocate element {element.display_name}")
                return False

            # Clear existing content via select-all + delete, then type
            try:
                wrapper.set_edit_text(text)
            except Exception:
                # Fallback: use keyboard simulation
                wrapper.click_input()
                wrapper.type_keys("^a{DELETE}", with_spaces=True)
                wrapper.type_keys(text, with_spaces=True, with_newlines=True)

            logger.info(f"UIA: Typed text into {element.display_name}")
            return True
        except Exception as e:
            logger.error(f"UIA type_text failed on {element.display_name}: {e}")
            return False

    @com_thread_safe
    def get_element_value(self, element: UIAElement, window_title: str) -> str | None:
        """Read the current value of a value-holding element."""
        try:
            wrapper = self._relocate_element(element, window_title)
            if wrapper is None:
                return None

            # Try Value pattern first
            try:
                iface = wrapper.iface_value
                if iface:
                    return iface.CurrentValue
            except Exception:
                pass

            # Fallback to window_text
            try:
                return wrapper.window_text()
            except Exception:
                pass

            return None
        except Exception as e:
            logger.warning(f"UIA get_element_value failed: {e}")
            return None

    @com_thread_safe
    def invoke_element(self, element: UIAElement, window_title: str) -> bool:
        """Invoke the default action (Invoke pattern) on a button or menu item."""
        try:
            wrapper = self._relocate_element(element, window_title)
            if wrapper is None:
                return False

            try:
                iface = wrapper.iface_invoke
                if iface:
                    iface.Invoke()
                    logger.info(f"UIA: Invoked {element.display_name}")
                    return True
            except Exception:
                pass

            # Fallback to click
            wrapper.click_input()
            logger.info(f"UIA: Invoke fallback to click on {element.display_name}")
            return True
        except Exception as e:
            logger.error(f"UIA invoke_element failed on {element.display_name}: {e}")
            return False

    @com_thread_safe
    def select_item(self, element: UIAElement, item_name: str, window_title: str) -> bool:
        """Select a named item in a selection container."""
        try:
            wrapper = self._relocate_element(element, window_title)
            if wrapper is None:
                return False

            wrapper.select(item_name)
            logger.info(f"UIA: Selected '{item_name}' in {element.display_name}")
            return True
        except Exception as e:
            logger.error(f"UIA select_item failed on {element.display_name}: {e}")
            return False

    @com_thread_safe
    def toggle_element(self, element: UIAElement, window_title: str) -> bool:
        """Toggle a toggleable element (checkbox, toggle button)."""
        try:
            wrapper = self._relocate_element(element, window_title)
            if wrapper is None:
                return False

            try:
                iface = wrapper.iface_toggle
                if iface:
                    iface.Toggle()
                    logger.info(f"UIA: Toggled {element.display_name}")
                    return True
            except Exception:
                pass

            # Fallback to click (most toggleable controls respond to click)
            wrapper.click_input()
            logger.info(f"UIA: Toggle fallback to click on {element.display_name}")
            return True
        except Exception as e:
            logger.error(f"UIA toggle_element failed on {element.display_name}: {e}")
            return False

    @com_thread_safe
    def wait_for_element(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.5,
    ) -> UIAElement | None:
        """Poll for an element to appear within the timeout period."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            # Inner find doesn't need COM re-init — we're already in com_scope
            try:
                wrapper = self._find_wrapper(window_title, control_type, name, automation_id)
                if wrapper is not None:
                    return self._wrapper_to_element(wrapper)
            except Exception:
                pass
            time.sleep(poll_interval)

        logger.info(f"UIA: wait_for_element timed out after {timeout_seconds}s")
        return None

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _find_wrapper(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> Any | None:
        """Locate a pywinauto wrapper matching the criteria."""
        wrappers = self._find_wrappers(
            window_title=window_title,
            control_type=control_type,
            name=name,
            automation_id=automation_id,
            depth=depth,
        )
        return wrappers[0] if wrappers else None

    def _find_wrappers(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> list[Any]:
        """Locate all pywinauto wrappers matching the criteria."""
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
        windows = desktop.windows(title_re=f".*{window_title}.*")
        if not windows:
            return []

        win = windows[0]

        # Pywinauto UIA descendants query supports control_type and title
        criteria: dict[str, Any] = {}
        if control_type:
            criteria["control_type"] = control_type
        if name:
            criteria["title"] = name

        try:
            candidates = win.descendants(**criteria) if criteria else win.descendants()
        except Exception:
            try:
                candidates = win.children(**criteria) if criteria else win.children()
            except Exception:
                candidates = []

        if not candidates and not criteria and not automation_id:
            return [win]

        # Post-filter by automation_id if specified (IUIA condition doesn't take auto_id in descendants)
        if automation_id:
            candidates = [
                c
                for c in candidates
                if getattr(getattr(c, "element_info", None), "automation_id", "") == automation_id
            ]

        # Post-filter by name if name wasn't exact match on title
        if name and not criteria.get("title"):
            candidates = [
                c
                for c in candidates
                if name.lower() in (getattr(getattr(c, "element_info", None), "name", "") or "").lower()
            ]

        return candidates

    def _relocate_element(self, element: UIAElement, window_title: str) -> Any | None:
        """Re-locate a UIAElement to get a fresh pywinauto wrapper for interaction."""
        # Prefer automation_id for stability, then name, then control_type
        if element.automation_id:
            return self._find_wrapper(window_title, automation_id=element.automation_id)
        elif element.name:
            return self._find_wrapper(
                window_title, control_type=element.control_type, name=element.name
            )
        else:
            return self._find_wrapper(window_title, control_type=element.control_type)

    def _wrapper_to_element(self, wrapper: Any) -> UIAElement:
        """Convert a pywinauto wrapper to a UIAElement dataclass."""
        try:
            rect = wrapper.rectangle()
            bounding = (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            bounding = (0, 0, 0, 0)

        # Detect supported patterns
        patterns: list[str] = []
        for pattern_name in ("Invoke", "Value", "Toggle", "SelectionItem", "ExpandCollapse", "Scroll"):
            try:
                iface = getattr(wrapper, f"iface_{pattern_name.lower()}", None)
                if iface is not None:
                    patterns.append(pattern_name)
            except Exception:
                pass

        # Get value if available
        value = None
        try:
            iface_val = wrapper.iface_value
            if iface_val:
                value = iface_val.CurrentValue
        except Exception:
            try:
                value = wrapper.window_text()
            except Exception:
                pass

        try:
            control_type = wrapper.element_info.control_type or "Unknown"
        except Exception:
            control_type = "Unknown"

        try:
            name = wrapper.element_info.name or ""
        except Exception:
            name = ""

        try:
            auto_id = wrapper.element_info.automation_id or ""
        except Exception:
            auto_id = ""

        try:
            class_name = wrapper.element_info.class_name or ""
        except Exception:
            class_name = ""

        try:
            is_enabled = wrapper.is_enabled()
        except Exception:
            is_enabled = True

        try:
            is_offscreen = not wrapper.is_visible()
        except Exception:
            is_offscreen = False

        return UIAElement(
            control_type=control_type,
            name=name,
            automation_id=auto_id,
            class_name=class_name,
            bounding_rect=bounding,
            is_enabled=is_enabled,
            is_offscreen=is_offscreen,
            value=value,
            patterns=patterns,
        )

    def _build_tree(self, wrapper: Any, current_depth: int, max_depth: int) -> UIATreeNode:
        """Recursively build a UIATreeNode tree, limited to max_depth."""
        element = self._wrapper_to_element(wrapper)
        node = UIATreeNode(element=element, depth=current_depth)

        if current_depth < max_depth:
            try:
                children = wrapper.children()
                for child in children:
                    child_node = self._build_tree(child, current_depth + 1, max_depth)
                    node.children.append(child_node)
            except Exception:
                pass  # Some elements don't support child enumeration

        return node


class UIAAdapterFactory:
    """Factory for creating UIA adapters with automatic fallback."""

    _adapters: list[type[UIAAdapter]] = [PywinautoUIAAdapter]

    @classmethod
    def get_adapter(cls) -> UIAAdapter:
        """Get the highest-priority available UIA adapter."""
        for adapter_cls in sorted(cls._adapters, key=lambda a: a.PRIORITY):
            adapter = adapter_cls()
            try:
                if adapter.is_available():
                    logger.info(f"UIA adapter selected: {adapter.name}")
                    return adapter
            except Exception as e:
                logger.debug(f"UIA adapter {adapter_cls.NAME} unavailable: {e}")

        logger.warning("No UIA adapter available — returning PywinautoUIAAdapter (may be degraded)")
        return PywinautoUIAAdapter()
