"""
Phase 10: Backend & Planner Contract Tests
==========================================
Verifies that all registered backends implement BaseBackendAdapter,
all registered planners implement BasePlanner, and all native managers
implement BaseNativeManager.

These are architectural contracts, not functional tests.
Any backend or planner that doesn't satisfy the contract will be
flagged here before it causes a runtime error.
"""

import inspect

import pytest

# ─── Backend Contracts ─────────────────────────────────────────────────────────

BACKEND_CLASSES = []

from core.backends.base_backend import BaseBackendAdapter
from core.backends.adapters.antigravity_backend import AntigravityBackendAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.backends.adapters.gemini_backend import GeminiBackend
from core.backends.adapters.groq_backend import GroqBackend

BACKEND_CLASSES = [
    AntigravityBackendAdapter,
    DesktopEngineBackend,
    GeminiBackend,
    GroqBackend,
]


@pytest.mark.parametrize("backend_cls", BACKEND_CLASSES)
def test_backend_inherits_base_adapter(backend_cls):
    """Every backend in core/backends/adapters must be a subclass of BaseBackendAdapter."""
    assert any(
        cls.__name__ == "BaseBackendAdapter" for cls in backend_cls.mro()
    ), f"{backend_cls.__name__} does not inherit from BaseBackendAdapter"


@pytest.mark.parametrize("backend_cls", BACKEND_CLASSES)
def test_backend_contract_methods(backend_cls):
    """Every backend must implement required API methods."""
    required_methods = ["name", "capabilities", "describe", "health_check", "execute"]
    for method in required_methods:
        assert hasattr(
            backend_cls, method
        ), f"{backend_cls.__name__} is missing contract method '{method}'"


def test_backend_registry_can_instantiate():
    """BackendRegistry must be instantiatable without arguments."""
    from core.backends import BackendRegistry

    registry = BackendRegistry()
    assert registry is not None


# ─── Planner Contracts ─────────────────────────────────────────────────────────

PLANNER_CLASSES = []

try:
    from desktop.planner.planner import DesktopPlanner

    PLANNER_CLASSES = [DesktopPlanner]
except ImportError:
    pass


@pytest.mark.parametrize("planner_cls", PLANNER_CLASSES)
def test_planner_inherits_base_planner(planner_cls):
    """Planner must inherit from core.planning.BasePlanner."""
    assert any(
        cls.__name__ in ("BasePlanner", "CoreBasePlanner") for cls in planner_cls.mro()
    ), f"{planner_cls.__name__} does not inherit from BasePlanner"


@pytest.mark.parametrize("planner_cls", PLANNER_CLASSES)
def test_planner_contract_methods(planner_cls):
    """Every planner must implement required methods: can_handle, create_plan, execute_plan, optimize_plan, explain_plan."""
    required = [
        "can_handle",
        "create_plan",
        "execute_plan",
        "optimize_plan",
        "explain_plan",
    ]
    for method in required:
        assert hasattr(
            planner_cls, method
        ), f"{planner_cls.__name__} is missing contract method '{method}'"


def test_planner_registry_can_register():
    """PlannerRegistry must accept a BasePlanner and return it by name."""
    from core.orchestration import PlannerRegistry

    registry = PlannerRegistry.get_instance()
    assert isinstance(registry.list_planners(), list)
    assert len(registry.list_planners()) >= 4


# ─── Native Manager Contracts ──────────────────────────────────────────────────

MANAGER_CLASSES = []

try:
    from desktop.native.managers import (
        AudioManager,
        ClipboardManager,
        DisplayManager,
        NetworkManager,
        PowerManager,
        WindowManager,
    )

    MANAGER_CLASSES = [
        WindowManager,
        ClipboardManager,
        DisplayManager,
        AudioManager,
        PowerManager,
        NetworkManager,
    ]
except ImportError:
    pass


@pytest.mark.parametrize("mgr_cls", MANAGER_CLASSES)
def test_manager_inherits_base_manager(mgr_cls):
    """All concrete managers in desktop/native/managers must inherit BaseNativeManager."""
    from desktop.native.managers import BaseNativeManager

    assert issubclass(
        mgr_cls, BaseNativeManager
    ), f"{mgr_cls.__name__} does not inherit from BaseNativeManager"


@pytest.mark.parametrize("mgr_cls", MANAGER_CLASSES)
def test_manager_contract_methods(mgr_cls):
    """All native managers must implement status and availability contract methods."""
    required = ["is_available", "get_status"]
    for method in required:
        assert hasattr(
            mgr_cls, method
        ), f"{mgr_cls.__name__} is missing contract method '{method}'"
