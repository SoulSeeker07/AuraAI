"""
Phase 2B Architectural Freeze Validation Suite

Formally validates that Phase 2B (Native Layer) meets all architectural standards:
1. Capability Graph Integrity (no orphan capability references in requires/verifies/rollback).
2. Boot Report Accuracy (reports all loaded managers, active adapters, health, and simulation mode).
3. Execution Simulation (destructive capabilities bypass physical calls in simulation mode).
4. Native Manager Purity Audit (zero cross-cutting leakage inside manager classes).
5. End-to-End Orchestration (all executions route through DesktopExecutionEngine & NativeManagerRegistry).
"""

import importlib
import inspect
import pkgutil
from typing import Any

import pytest

from desktop.native.adapters.network_adapter import DummyNetworkAdapter
from desktop.native.capability_registry import CapabilityRegistry, RiskLevel
from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    reset_desktop_execution_engine,
)
from desktop.native.managers.base_manager import BaseNativeManager
from desktop.native.managers.native_manager_registry import (
    HealthStatus,
    NativeManagerRegistry,
)
from desktop.native.managers.network_manager import NetworkManager
from desktop.native.native_exceptions import NativeError


@pytest.fixture
def registry():
    NativeManagerRegistry.reset_instance()
    reg = NativeManagerRegistry.get_instance()
    reg.discover("desktop.native.managers")
    yield reg
    NativeManagerRegistry.reset_instance()


@pytest.fixture
def cap_registry():
    return CapabilityRegistry()


@pytest.fixture
def engine(registry, cap_registry):
    reset_desktop_execution_engine()
    eng = DesktopExecutionEngine(
        manager_registry=registry,
        registry=cap_registry,
        config=ExecutionConfig(simulation_mode=True),
    )
    yield eng
    reset_desktop_execution_engine()


# ==================== 1. Capability Graph Integrity ====================


def test_capability_graph_integrity(cap_registry):
    """Verify all graph references (requires, verifies, rollback_capabilities) map to valid descriptors."""
    all_caps = {desc.name for desc in cap_registry.list_all()}
    assert len(all_caps) >= 100, f"Expected 100+ capabilities, found {len(all_caps)}"

    orphans_requires = []
    orphans_verifies = []
    orphans_rollback = []

    for desc in cap_registry.list_all():
        for req in desc.requires:
            if req not in all_caps:
                orphans_requires.append((desc.name, req))

        for ver in desc.verifies:
            if ver not in all_caps:
                orphans_verifies.append((desc.name, ver))

        for rb in desc.rollback_capabilities:
            if rb not in all_caps:
                orphans_rollback.append((desc.name, rb))

    assert (
        not orphans_requires
    ), f"Orphan 'requires' references found: {orphans_requires}"
    assert (
        not orphans_verifies
    ), f"Orphan 'verifies' references found: {orphans_verifies}"
    assert (
        not orphans_rollback
    ), f"Orphan 'rollback_capabilities' references found: {orphans_rollback}"


# ==================== 2. Boot Report Accuracy ====================


def test_boot_report_accuracy(registry):
    """Verify get_boot_report() outputs complete diagnostic readiness."""
    report = registry.get_boot_report(simulation_mode=True)

    assert "Aura Desktop Boot" in report
    assert "WindowManager" in report
    assert "ClipboardManager" in report
    assert "DisplayManager" in report
    assert "AudioManager" in report
    assert "PowerManager" in report
    assert "NetworkManager" in report
    assert "Manager Registry" in report
    assert "Capabilities Mapped" in report
    assert "Simulation Mode" in report
    assert "Enabled" in report
    assert "Desktop Ready" in report


# ==================== 3. Execution Simulation ====================


def test_execution_simulation_intercepts_destructive_actions(engine):
    """Verify destructive/high-risk actions bypass OS execution in simulation mode."""
    destructive_caps = [
        "shutdown",
        "restart",
        "power.shutdown",
        "power.restart",
        "network.disable_adapter",
    ]

    for cap in destructive_caps:
        result = engine.execute(
            goal=f"test {cap}", capability=cap, adapter_name="Wi-Fi"
        )
        assert (
            result.success is True
        ), f"Capability {cap} should succeed in simulation mode"
        assert (
            result.data.get("simulated") is True
        ), f"Capability {cap} should set simulated=True"
        assert result.data.get("status") == "simulated_execution"


# ==================== 4. Manager Purity Audit ====================


def test_manager_purity_audit():
    """Verify native managers do NOT import or execute cross-cutting pipeline concerns."""
    pkg = importlib.import_module("src.desktop.native.managers")
    pkg_path = getattr(pkg, "__path__")

    forbidden_tokens = [
        "PermissionChecker",
        "MetricsRecorder",
        "RollbackFramework",
        "NativeDiagnostics",
        "get_metrics_recorder",
    ]

    leaks = []

    for _, module_name, is_pkg in pkgutil.walk_packages(
        pkg_path, prefix="src.desktop.native.managers."
    ):
        if is_pkg or module_name.endswith(".base_manager"):
            continue
        mod = importlib.import_module(module_name)
        source = inspect.getsource(mod)

        for token in forbidden_tokens:
            if token in source:
                leaks.append((module_name, token))

    assert (
        not leaks
    ), f"Cross-cutting concern leakage detected in native managers: {leaks}"


# ==================== 5. End-to-End Engine Orchestration ====================


def test_end_to_end_engine_orchestration(engine):
    """Verify execution routes through DesktopExecutionEngine & NativeManagerRegistry."""
    goals = [
        ("list open windows", "list_windows", "window"),
        ("read text from clipboard", "clipboard.read_text", "clipboard"),
        ("list display monitors", "list_displays", "display"),
        ("get master volume", "get_volume", "audio"),
        ("get battery level", "power.battery", "power"),
        ("get local ip address", "network.local_ip", "network"),
    ]

    for goal, expected_cap, expected_manager in goals:
        res = engine.execute(goal=goal)
        assert (
            res.success is True
        ), f"Goal '{goal}' failed with error: {res.error}, discovered cap: {res.capability}"
        assert (
            res.capability == expected_cap
        ), f"Goal '{goal}' expected cap {expected_cap}, got {res.capability}"
        assert res.manager == expected_manager
        assert res.metrics.get("total_duration_ms") is not None
        assert "passed" in res.verification


# ==================== 6. Fail-Closed Manager Discovery & Registration ====================


def test_fail_closed_manager_exclusion_during_discovery(monkeypatch, caplog):
    """Verify discover() continues when a manager fails registration: excludes the broken one, registers healthy ones."""
    import types

    class BrokenManager(BaseNativeManager):
        NAME = "broken_test_manager"
        PRIORITY = 50

        @property
        def name(self) -> str:
            return self.NAME

        @property
        def capabilities(self) -> list[str]:
            return ["test.broken_cap"]

        def register_capabilities(self, capabilities: list[str]) -> None:
            raise RuntimeError("Deliberate registration failure in test")

        def execute(self, capability: str, goal: str, args: dict) -> Any:
            pass

    class HealthyManager(BaseNativeManager):
        NAME = "healthy_test_manager"
        PRIORITY = 60

        @property
        def name(self) -> str:
            return self.NAME

        @property
        def capabilities(self) -> list[str]:
            return ["test.healthy_cap"]

        def register_capabilities(self, capabilities: list[str]) -> None:
            self._registered_caps = list(capabilities)

        def execute(self, capability: str, goal: str, args: dict) -> Any:
            return "healthy_result"

    # Create synthetic module containing both test managers
    synthetic_mod = types.ModuleType("desktop.native.managers.test_synthetic")
    synthetic_mod.BrokenManager = BrokenManager
    synthetic_mod.HealthyManager = HealthyManager

    NativeManagerRegistry.reset_instance()
    reg = NativeManagerRegistry.get_instance()

    try:
        # 1. Direct registration rejection: Attempting to register broken manager directly must raise NativeError
        with pytest.raises(NativeError) as exc_info:
            reg.register(BrokenManager())

        assert "broken_test_manager" in str(exc_info.value)
        assert "cannot be registered" in str(exc_info.value)

        # 2. Mock discovery to include the synthetic module in walk_packages
        orig_walk_packages = pkgutil.walk_packages
        orig_import_module = importlib.import_module

        def mock_walk_packages(path, prefix=""):
            yield from orig_walk_packages(path, prefix=prefix)
            # Yield our synthetic module as part of the package traversal
            yield (None, f"{prefix}test_synthetic", False)

        def mock_import_module(name, package=None):
            if name.endswith(".test_synthetic") or name == "desktop.native.managers.test_synthetic":
                return synthetic_mod
            return orig_import_module(name, package=package)

        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk_packages)
        monkeypatch.setattr(importlib, "import_module", mock_import_module)

        # 3. Run discover() across the package
        with caplog.at_level("WARNING"):
            registered_names = reg.discover("desktop.native.managers")

        # 4. Assert continue-on-failure discovery semantics:
        # - BrokenManager was excluded
        assert "broken_test_manager" not in registered_names
        assert reg.get("broken_test_manager") is None
        assert reg.resolve("test.broken_cap") is None

        # - HealthyManager succeeded and is mapped
        assert "healthy_test_manager" in registered_names
        assert reg.get("healthy_test_manager") is not None
        assert reg.resolve("test.healthy_cap") is reg.get("healthy_test_manager")

        # - Real native managers were not aborted and registered cleanly
        assert "window" in registered_names
        assert "clipboard" in registered_names
        assert "power" in registered_names

        # 5. Assert diagnostic log summary accurately reported the exclusion
        assert "EXCLUDED (1): ['broken_test_manager']" in caplog.text

    finally:
        NativeManagerRegistry.reset_instance()
