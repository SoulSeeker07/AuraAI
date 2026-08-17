"""
Test UIAManager, UIAAdapter, COM Threading & Capability Graph Integration
==========================================================================
Location: tests/desktop/test_uia_manager.py

Comprehensive tests covering:
1. COM Thread Safety Utilities (com_scope, com_thread_safe in worker threads).
2. UIA Data Models (UIAElement, UIATreeNode).
3. UIAAdapter hierarchy and mock adapter execution.
4. Clear-then-type semantics for type_text.
5. UIAManager native structure (zero forbidden cross-cutting symbols).
6. Auto-discovery and registration in NativeManagerRegistry.
7. Verification logic: flagging unchanged state on no-op clicks vs. passing on genuine state change.
8. Native CapabilityRegistry descriptor attributes: HIGH risk, requires_confirmation, is_destructive.
9. First real population and validation of requires/verifies/rollback_capabilities DAG fields.
10. DesktopCapabilityProvider projection into canonical universal Capabilities.
11. Universal CapabilityRegistry validate_plan_graph() transitive dependency validation on real UIA graph.
12. Safe read-only live OS smoke test.
"""

from __future__ import annotations

import concurrent.futures
import inspect
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
src_root = os.path.join(project_root, "src")
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from core.capabilities.capability_registry import CapabilityRegistry as UniversalCapabilityRegistry
from core.capabilities.models import Capability, PlanValidationResult
from core.capabilities.providers.desktop_provider import DesktopCapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk
from desktop.native.adapters.com_threading import com_scope, com_thread_safe
from desktop.native.adapters.uia_adapter import (
    PywinautoUIAAdapter,
    UIAAdapter,
    UIAAdapterFactory,
    UIAElement,
    UIATreeNode,
)
from desktop.native.capability_registry import (
    CapabilityDescriptor,
    CapabilityRegistry as NativeCapabilityRegistry,
    PermissionRequired,
    RiskLevel,
    get_capability_registry,
)
from desktop.native.desktop_result import DesktopResult
from desktop.native.managers import native_manager_registry
import desktop.native.managers.uia_manager as uia_module
from desktop.native.managers.base_manager import HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.uia_manager import UIAManager


def setup_function():
    """Reset registry singletons before each test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singletons after each test."""
    NativeManagerRegistry.reset_instance()


# ── 1. COM Thread Safety Utilities ────────────────────────────────────────────


def test_com_threading_scope_and_decorator_multithreaded():
    """Test com_scope and @com_thread_safe execute safely in concurrent worker threads."""

    @com_thread_safe
    def worker_func(x: int) -> int:
        # Simulate COM work inside decorated function
        return x * 2

    # Run in ThreadPoolExecutor (worker threads where COM would otherwise be uninitialized)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker_func, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert sorted(results) == [i * 2 for i in range(10)]

    # Test com_scope directly
    with com_scope():
        val = 42
    assert val == 42


# ── 2. Data Models ────────────────────────────────────────────────────────────


def test_uia_element_and_tree_models():
    """Test UIAElement and UIATreeNode models."""
    elem = UIAElement(
        control_type="Button",
        name="Save",
        automation_id="btn_save",
        class_name="ButtonClass",
        bounding_rect=(10, 20, 100, 50),
        is_enabled=True,
        is_offscreen=False,
        value=None,
        patterns=["Invoke"],
    )

    assert elem.is_interactable is True
    assert elem.display_name == "Button('Save')"

    unnamed_elem = UIAElement(
        control_type="Edit",
        name="",
        automation_id="txt_input",
    )
    assert unnamed_elem.display_name == "Edit[txt_input]"

    generic_elem = UIAElement(
        control_type="Pane",
        name="",
        automation_id="",
        class_name="ContentPane",
    )
    assert generic_elem.display_name == "Pane(ContentPane)"

    node = UIATreeNode(element=elem, depth=0)
    child_node = UIATreeNode(element=unnamed_elem, depth=1)
    node.children.append(child_node)

    assert len(node.children) == 1
    assert node.children[0].depth == 1


# ── 3. Mock UIA Adapter & Semantics ──────────────────────────────────────────


class MockUIAAdapter(UIAAdapter):
    """Mock UIA adapter for deterministic unit testing."""

    NAME = "mock_uia"
    PRIORITY = 50

    def __init__(self):
        super().__init__()
        self._available = True
        self.clicked_elements: list[str] = []
        self.typed_texts: list[tuple[str, str]] = []
        self.toggled_elements: list[str] = []
        self.element_values: dict[str, str] = {}
        self.clear_then_type_called: bool = False

    def is_available(self) -> bool:
        return self._available

    def find_element(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> UIAElement | None:
        if name == "NonExistent":
            return None
        return UIAElement(
            control_type=control_type or "Button",
            name=name or "TestButton",
            automation_id=automation_id or "btn_test",
            class_name="MockButton",
            bounding_rect=(0, 0, 100, 30),
            is_enabled=True,
            is_offscreen=False,
            value=self.element_values.get(name or "TestButton", "Initial"),
            patterns=["Invoke", "Value", "Toggle"],
        )

    def find_elements(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        depth: int = 10,
    ) -> list[UIAElement]:
        return [
            UIAElement(control_type="Button", name="Btn1", automation_id="b1"),
            UIAElement(control_type="Button", name="Btn2", automation_id="b2"),
        ]

    def get_element_tree(
        self,
        window_title: str,
        depth: int = 3,
    ) -> UIATreeNode | None:
        root = UIAElement(control_type="Window", name=window_title)
        root_node = UIATreeNode(element=root, depth=0)
        btn = UIAElement(control_type="Button", name="OK")
        root_node.children.append(UIATreeNode(element=btn, depth=1))
        return root_node

    def click_element(self, element: UIAElement, window_title: str) -> bool:
        self.clicked_elements.append(element.display_name)
        return True

    def type_text(self, element: UIAElement, text: str, window_title: str) -> bool:
        # Clear-then-type: completely overwrites the value
        self.clear_then_type_called = True
        self.typed_texts.append((element.display_name, text))
        self.element_values[element.name] = text
        return True

    def get_element_value(self, element: UIAElement, window_title: str) -> str | None:
        return self.element_values.get(element.name, "Initial")

    def invoke_element(self, element: UIAElement, window_title: str) -> bool:
        return True

    def select_item(self, element: UIAElement, item_name: str, window_title: str) -> bool:
        return True

    def toggle_element(self, element: UIAElement, window_title: str) -> bool:
        self.toggled_elements.append(element.display_name)
        curr = self.element_values.get(element.name, "off")
        self.element_values[element.name] = "on" if curr == "off" else "off"
        return True

    def wait_for_element(
        self,
        window_title: str,
        control_type: str | None = None,
        name: str | None = None,
        automation_id: str | None = None,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.5,
    ) -> UIAElement | None:
        if name == "TimeoutElement":
            return None
        return self.find_element(window_title, control_type, name, automation_id)


def test_uia_type_text_clear_then_type_semantics():
    """Verify that type_text operates with clear-then-type semantics (not append)."""
    mock_adapter = MockUIAAdapter()
    manager = UIAManager(adapter=mock_adapter)

    # Initial state
    mock_adapter.element_values["SearchField"] = "OldQuery"

    res = manager.execute(
        capability="uia.type_text",
        arguments={
            "window_title": "AppWindow",
            "element": {"name": "SearchField", "control_type": "Edit"},
            "text": "NewQuery",
        },
    )

    assert res.success is True
    assert res.data["clear_then_type"] is True
    assert res.data["text_typed"] == "NewQuery"
    assert res.data["post_value"] == "NewQuery"
    assert mock_adapter.clear_then_type_called is True
    assert mock_adapter.element_values["SearchField"] == "NewQuery"


# ── 4. UIAManager Native Structure ───────────────────────────────────────────


def test_uia_manager_native_structure():
    """Test that UIAManager adheres to the pure native manager architecture."""
    mock_adapter = MockUIAAdapter()
    manager = UIAManager(adapter=mock_adapter)

    assert manager.name == "uia"
    assert manager.NAME == "uia"
    assert manager.VERSION == "1.0"
    assert manager.PRIORITY == 15
    assert "pywinauto" in manager.DEPENDENCIES
    assert len(manager.capabilities) == 10

    # Ensure zero cross-cutting concerns in code body
    source = inspect.getsource(uia_module)
    forbidden_symbols = [
        "PermissionMiddleware",
        "MetricsRecorder",
        "DiagnosticsStage",
        "get_desktop_context",
        "NativeEventBus",
    ]
    for symbol in forbidden_symbols:
        assert symbol not in source, f"UIAManager contains forbidden symbol: {symbol}"


# ── 5. Auto-Discovery & Registration ─────────────────────────────────────────


def test_uia_manager_auto_discovery_and_health():
    """Test auto-discovery of UIAManager by NativeManagerRegistry."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("desktop.native.managers")

    assert "uia" in discovered
    manager = registry.get("uia")
    assert manager is not None
    assert isinstance(manager, UIAManager)

    health = manager.health_check()
    assert health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE)
    assert health.manager_name == "uia"


def test_uia_capabilities_registered():
    """Verify all 10 UIA capabilities are registered in NativeManagerRegistry and CapabilityRegistry."""
    manager = UIAManager(adapter=MockUIAAdapter())
    expected_caps = [
        "uia.find_element",
        "uia.find_elements",
        "uia.get_tree",
        "uia.get_value",
        "uia.wait_for_element",
        "uia.click",
        "uia.type_text",
        "uia.invoke",
        "uia.select_item",
        "uia.toggle",
    ]

    for cap in expected_caps:
        assert manager.can_handle(cap) is True

    native_reg = NativeCapabilityRegistry()
    for cap in expected_caps:
        desc = native_reg.get(cap)
        assert desc is not None, f"Capability '{cap}' not found in NativeCapabilityRegistry"
        assert desc.manager == "uia"


# ── 6. Verification: State-Change vs. No-Op Click ─────────────────────────────


def test_uia_click_verification_flags_unchanged_state():
    """
    Mock a no-op click: element found, click dispatched, but state didn't change.
    Assert that the verification logic flags it as failed rather than silently passing.
    """
    mock_adapter = MockUIAAdapter()
    # Adapter where value remains "StaticValue" before and after click
    mock_adapter.element_values["Button"] = "StaticValue"
    manager = UIAManager(adapter=mock_adapter)

    res = manager.execute(
        capability="uia.click",
        arguments={
            "window_title": "AppWindow",
            "element": {"name": "Button", "control_type": "Button"},
        },
    )

    # Click physically succeeded (signal dispatched), but state did not mutate
    assert res.success is True
    assert res.data["state_changed"] is False
    assert res.data["verification_passed"] is False

    # UIAManager.verify() must flag the failure
    assert manager.verify(res) is False


def test_uia_click_verification_passes_on_state_change():
    """When element state mutates following an interaction, verification passes."""
    mock_adapter = MockUIAAdapter()
    manager = UIAManager(adapter=mock_adapter)

    # Toggle mutates state from "off" to "on"
    mock_adapter.element_values["Checkbox"] = "off"

    res = manager.execute(
        capability="uia.toggle",
        arguments={
            "window_title": "AppWindow",
            "element": {"name": "Checkbox", "control_type": "CheckBox"},
        },
    )

    assert res.success is True
    assert res.data["state_changed"] is True
    assert res.data["verification_passed"] is True
    assert manager.verify(res) is True


# ── 7. Capability Descriptors: Risk Gating & DAG Relationships ────────────────


def test_uia_capability_descriptors_risk_and_confirmation():
    """
    Verify that destructive interaction capabilities are gated with HIGH risk
    and requires_confirmation=True, while read-only capabilities are SAFE/LOW.
    """
    native_reg = NativeCapabilityRegistry()

    # Interaction Capabilities (HIGH Risk)
    interaction_caps = ["uia.click", "uia.type_text", "uia.invoke", "uia.select_item", "uia.toggle"]
    for cap_name in interaction_caps:
        desc = native_reg.get(cap_name)
        assert desc is not None
        assert desc.risk_level == RiskLevel.HIGH
        assert desc.requires_confirmation is True
        assert desc.is_destructive is True
        assert desc.permission == PermissionRequired.WRITE

    # Read-Only Capabilities (SAFE/LOW Risk)
    readonly_caps = ["uia.find_element", "uia.find_elements", "uia.get_tree", "uia.get_value"]
    for cap_name in readonly_caps:
        desc = native_reg.get(cap_name)
        assert desc is not None
        assert desc.risk_level in (RiskLevel.SAFE, RiskLevel.LOW)
        assert desc.requires_confirmation is False
        assert desc.is_destructive is False
        assert desc.permission == PermissionRequired.READ


def test_uia_dag_fields_populated():
    """
    Verify that UIA capabilities are the first domain with fully populated
    requires, verifies, and rollback_capabilities DAG fields.
    """
    native_reg = NativeCapabilityRegistry()

    # uia.click requires finding element, verifies reading value
    click_desc = native_reg.get("uia.click")
    assert click_desc.requires == ["uia.find_element"]
    assert click_desc.verifies == ["uia.get_value"]

    # uia.type_text has rollback capability to type/clear
    type_desc = native_reg.get("uia.type_text")
    assert type_desc.requires == ["uia.find_element"]
    assert type_desc.verifies == ["uia.get_value"]
    assert type_desc.supports_undo is True
    assert type_desc.rollback_capabilities == ["uia.type_text"]

    # uia.toggle has self-referential rollback
    toggle_desc = native_reg.get("uia.toggle")
    assert toggle_desc.requires == ["uia.find_element"]
    assert toggle_desc.verifies == ["uia.get_value"]
    assert toggle_desc.supports_undo is True
    assert toggle_desc.rollback_capabilities == ["uia.toggle"]


# ── 8. DesktopCapabilityProvider Projection ───────────────────────────────────


def test_desktop_provider_projects_uia_capabilities():
    """
    Test that DesktopCapabilityProvider dynamically projects native UIA
    descriptors into canonical universal Capabilities with full risk and DAG metadata.
    """
    provider = DesktopCapabilityProvider()
    caps = {c.name: c for c in provider.list_capabilities()}

    assert "uia.click" in caps
    click_cap = caps["uia.click"]
    assert click_cap.domain == "desktop"
    assert click_cap.risk_level == ActionRisk.HIGH
    assert click_cap.requires_confirmation is True
    assert click_cap.is_destructive is True
    assert click_cap.requires == ["uia.find_element"]
    assert click_cap.verifies == ["uia.get_value"]
    assert click_cap.is_live is True

    assert "uia.toggle" in caps
    toggle_cap = caps["uia.toggle"]
    assert toggle_cap.supports_undo is True
    assert toggle_cap.rollback_capabilities == ["uia.toggle"]

    assert "uia.find_element" in caps
    find_cap = caps["uia.find_element"]
    assert find_cap.risk_level == ActionRisk.LOW
    assert find_cap.requires_confirmation is False


# ── 9. Universal Plan Graph DAG Validation ───────────────────────────────────


def test_validate_plan_graph_with_real_uia_descriptors():
    """
    First real-world test of MasterOrchestrator / CapabilityRegistry DAG validation:
    validate_plan_graph(['uia.click']) transitively expands requires: ['uia.find_element'],
    detects zero cycles, confirms all capabilities are live, and validates successfully.
    """
    registry = UniversalCapabilityRegistry()
    provider = DesktopCapabilityProvider()
    registry.register_provider(provider)

    # 1. Direct plan requesting uia.click (which requires uia.find_element)
    res = registry.validate_plan_graph(["uia.click"])
    assert res.valid is True
    assert len(res.errors) == 0
    assert len(res.unwired_capabilities) == 0

    # 2. Multi-step plan
    res_multi = registry.validate_plan_graph(["uia.find_element", "uia.click", "uia.get_value"])
    assert res_multi.valid is True
    assert len(res_multi.errors) == 0


def test_validate_plan_graph_uia_toggle_rollback_non_cyclic():
    """
    Verify that uia.toggle with self-referential rollback_capabilities: ['uia.toggle']
    does not cause a false-positive cycle during dependency validation.
    """
    registry = UniversalCapabilityRegistry()
    provider = DesktopCapabilityProvider()
    registry.register_provider(provider)

    res = registry.validate_plan_graph(["uia.toggle"])
    assert res.valid is True
    assert len(res.errors) == 0


# ── 10. Live OS Safe Read-Only Smoke Test ─────────────────────────────────────


def test_uia_live_read_only_smoke():
    """
    Safe read-only live OS smoke test: checks pywinauto UIA backend availability.
    If running in a supported interactive desktop session, verifies non-destructive
    enumeration.
    """
    adapter = PywinautoUIAAdapter()
    if not adapter.is_available():
        pytest.skip("pywinauto UIA backend is not functional in current session")

    # Safe read-only element find for Windows Taskbar or shell
    elem = adapter.find_element(window_title="", control_type="Pane")
    # Even if no specific element is matched, method must return without throwing COM errors
    assert elem is None or isinstance(elem, UIAElement)


def test_uia_live_winforms_round_trip():
    """
    Real-OS UIA interaction round-trip test against an isolated WinForms test GUI:
    Verifies tree inspection, clear-then-type text replacement, and button click state mutation.
    """
    import subprocess
    import time
    from src.desktop.native.adapters.com_threading import com_scope

    ps_code = """
    Add-Type -AssemblyName System.Windows.Forms
    $form = New-Object Windows.Forms.Form
    $form.Text = "AuraAI WinForms Test"
    $form.Width = 350
    $form.Height = 220

    $tb = New-Object Windows.Forms.TextBox
    $tb.Text = "Initial Value"
    $tb.Top = 20
    $tb.Left = 20
    $tb.Width = 200
    $tb.Name = "TestTextBox"
    $form.Controls.Add($tb)

    $btn = New-Object Windows.Forms.Button
    $btn.Text = "Click Me"
    $btn.Top = 60
    $btn.Left = 20
    $btn.Name = "TestButton"
    $btn.Add_Click({ $tb.Text = "Button Was Clicked" })
    $form.Controls.Add($btn)

    [Windows.Forms.Application]::Run($form)
    """

    proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_code])
    time.sleep(2.0)

    try:
        with com_scope():
            adapter = PywinautoUIAAdapter()
            win_title = "AuraAI WinForms Test"

            # 1. Tree inspection
            tree = adapter.get_element_tree(window_title=win_title, depth=3)
            assert tree is not None
            assert tree.element.control_type == "Window"

            # 2. Locate Edit control
            edit_elem = adapter.find_element(
                window_title=win_title, control_type="Edit", automation_id="TestTextBox"
            )
            assert edit_elem is not None

            # 3. Read initial value
            val0 = adapter.get_element_value(edit_elem, window_title=win_title)
            assert val0 == "Initial Value"

            # 4. Clear-then-type replacement
            ok = adapter.type_text(edit_elem, "New Clean Input", window_title=win_title)
            assert ok is True

            # 5. Immediate value read (UI repaint race check)
            val1 = adapter.get_element_value(edit_elem, window_title=win_title)
            assert val1 == "New Clean Input"
            assert "Initial Value" not in val1

            # 6. Button click and post-click state mutation
            btn_elem = adapter.find_element(
                window_title=win_title, control_type="Button", name="Click Me"
            )
            assert btn_elem is not None
            click_ok = adapter.click_element(btn_elem, window_title=win_title)
            assert click_ok is True

            val2 = adapter.get_element_value(edit_elem, window_title=win_title)
            assert val2 == "Button Was Clicked"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            proc.kill()
