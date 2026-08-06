"""
Milestone 16 AI Orchestration Integration Test Suite

Tests:
1. PlannerRegistry registration and resolution.
2. BackendRegistry capability-based scoring and discovery.
3. BackendAdapters (DesktopEngineBackend, GroqBackend, GeminiBackend, AntigravityBackend).
4. ResultMerger aggregating multi-planner ExecutionResults.
5. MasterOrchestrator end-to-end request processing.
"""

import pytest

from core.backends.backend_registry import BackendRegistry
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.backends.adapters.gemini_backend import GeminiBackend
from core.backends.adapters.groq_backend import GroqBackend
from core.backends.adapters.antigravity_backend import AntigravityBackendAdapter

from core.orchestration import (
    MasterOrchestrator,
    PlannerRegistry,
    ResultMerger,
)
from core.planning.execution_result import ExecutionResult
from src.desktop.native.capability_registry import CapabilityRegistry
from src.desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    reset_desktop_execution_engine,
)
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry
from src.desktop.planner import DesktopPlanner


@pytest.fixture
def clean_registries():
    PlannerRegistry.reset_instance()
    BackendRegistry.reset_instance()
    reset_desktop_execution_engine()

    p_reg = PlannerRegistry.get_instance()
    b_reg = BackendRegistry.get_instance()
    b_reg._backends.clear()  # Clear auto-registered default backends

    # Discover native desktop managers
    m_reg = NativeManagerRegistry.get_instance()
    m_reg.discover("src.desktop.native.managers")
    c_reg = CapabilityRegistry()
    engine = DesktopExecutionEngine(
        manager_registry=m_reg,
        registry=c_reg,
        config=ExecutionConfig(simulation_mode=True),
    )

    # Register Backends
    b_reg.register(DesktopEngineBackend(engine=engine))
    b_reg.register(GroqBackend())
    b_reg.register(GeminiBackend())
    b_reg.register(AntigravityBackendAdapter())

    # Register Desktop Planner
    planner = DesktopPlanner(engine=engine, registry=c_reg)
    p_reg.register("desktop", planner)

    yield p_reg, b_reg, planner, engine
    reset_desktop_execution_engine()
    PlannerRegistry.reset_instance()
    BackendRegistry.reset_instance()


def test_planner_registry(clean_registries):
    p_reg, _, planner, _ = clean_registries
    assert "desktop" in p_reg.list_planners()
    assert p_reg.get_planner("desktop") is planner


def test_backend_registry_discovery(clean_registries):
    _, b_reg, _, _ = clean_registries
    backends = b_reg.list_all_backends()
    assert len(backends) == 4

    names = [b["name"] for b in backends]
    assert "desktop_engine" in names
    assert "groq" in names
    assert "gemini" in names
    assert "Antigravity CLI" in names


def test_capability_based_routing(clean_registries):
    _, b_reg, _, _ = clean_registries

    # Route coding capability
    code_backend = b_reg.select_best_backend("code.refactor")
    assert code_backend is not None
    assert code_backend.name == "Antigravity CLI"

    # Route fast reasoning capability
    fast_backend = b_reg.select_best_backend("chat.fast")
    assert fast_backend is not None
    assert fast_backend.name == "groq"

    # Route deep reasoning capability
    deep_backend = b_reg.select_best_backend("reason.deep")
    assert deep_backend is not None
    assert deep_backend.name == "gemini"


def test_result_merger():
    merger = ResultMerger()
    r1 = ExecutionResult(
        success=True,
        planner="desktop",
        goal="check volume",
        confidence=0.98,
        observations=["Volume is 50%"],
    )
    r2 = ExecutionResult(
        success=True,
        planner="antigravity",
        goal="refactor code",
        confidence=0.96,
        observations=["Refactored 2 files"],
    )

    merged = merger.merge([r1, r2], goal="Multimodal goal")
    assert merged.success is True
    assert merged.planner == "master_orchestrator"
    assert len(merged.observations) == 2
    assert merged.confidence == 0.97


def test_master_orchestrator_desktop_dispatch(clean_registries):
    p_reg, b_reg, _, _ = clean_registries
    orchestrator = MasterOrchestrator(planner_registry=p_reg, backend_registry=b_reg)

    res = orchestrator.process_request("check battery status")
    assert res.success is True
    assert res.planner == "cognitive_orchestrator"
    assert len(res.observations) >= 1


def test_master_orchestrator_direct_backend_dispatch(clean_registries):
    p_reg, b_reg, _, _ = clean_registries
    orchestrator = MasterOrchestrator(planner_registry=p_reg, backend_registry=b_reg)

    res = orchestrator.process_request("code.refactor")
    assert res.success is True
    assert res.planner == "cognitive_orchestrator"
