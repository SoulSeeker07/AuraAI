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

from core.backends.adapters.antigravity_backend import AntigravityBackendAdapter
from core.backends.adapters.desktop_backend import DesktopEngineBackend
from core.backends.adapters.gemini_backend import GeminiBackend
from core.backends.adapters.groq_backend import GroqBackend
from core.backends.backend_registry import BackendRegistry
from core.orchestration import (
    MasterOrchestrator,
    PlannerRegistry,
    ResultMerger,
)
from core.planning.execution_result import ExecutionResult
from desktop.native.capability_registry import CapabilityRegistry
from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    reset_desktop_execution_engine,
)
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.planner import DesktopPlanner


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
    m_reg.discover("desktop.native.managers")
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
    assert "Coding Backend (EngineeringManager)" in names


def test_capability_based_routing(clean_registries):
    _, b_reg, _, _ = clean_registries

    # Route coding capability
    code_backend = b_reg.select_best_backend("code.refactor")
    assert code_backend is not None
    assert code_backend.name == "Coding Backend (EngineeringManager)"

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
    assert res.planner in ("desktop", "cognitive_orchestrator")
    assert len(res.observations) >= 1


def test_master_orchestrator_direct_backend_dispatch(clean_registries):
    p_reg, b_reg, _, _ = clean_registries
    orchestrator = MasterOrchestrator(planner_registry=p_reg, backend_registry=b_reg)

    # In M20, code.analyze with target_files performs real AST inspection and succeeds
    res = orchestrator.process_request("code.analyze", parameters={"target_files": ["tests/conftest.py"]})
    assert res.planner in ("coding", "cognitive_orchestrator")
    assert res.success is True


def test_master_orchestrator_blocks_scaffolded_unwired_capabilities_fail_closed(clean_registries):
    """Verify that attempting to execute an unwired scaffolded capability fails closed at Stage 3.2."""
    p_reg, b_reg, _, _ = clean_registries
    orchestrator = MasterOrchestrator(planner_registry=p_reg, backend_registry=b_reg)

    # browser.navigate is currently marked is_live=False in BrowserCapabilityProvider
    res = orchestrator.process_request("browser.navigate", parameters={"url": "https://example.com"})

    # Must fail closed before execution dispatch
    assert res.success is False
    assert res.planner == "CapabilityRegistry"
    assert "validation_errors" in res.data
    assert any("scaffolded (is_live=False)" in err for err in res.data["validation_errors"])
    assert "browser.navigate" in res.data.get("unwired_capabilities", [])
    assert any("Plan validation failed" in obs for obs in res.observations)


def test_master_orchestrator_blocks_cyclic_plan_graph_fail_closed(clean_registries, monkeypatch):
    """Verify that a task graph with cyclic capability dependencies is rejected fail-closed before dispatch."""
    p_reg, b_reg, _, _ = clean_registries
    orchestrator = MasterOrchestrator(planner_registry=p_reg, backend_registry=b_reg)

    from core.capabilities.capability_registry import CapabilityRegistry
    from core.capabilities.models import Capability

    cap_reg = CapabilityRegistry.get_instance()
    cap_reg.register(Capability(name="cycle.a", domain="coding", description="A", is_live=True, requires=["cycle.b"]))
    cap_reg.register(Capability(name="cycle.b", domain="coding", description="B", is_live=True, requires=["cycle.a"]))

    # Direct dispatch with cyclic capabilities
    res = orchestrator.process_request("cycle.a")

    assert res.success is False
    assert res.planner == "CapabilityRegistry"
    assert "validation_errors" in res.data
    assert any("Cyclic capability dependency detected" in err for err in res.data["validation_errors"])


def test_master_orchestrator_domain_routing_with_capability_registry(clean_registries):
    """Verify BackendRegistry uses resolved_domain from CapabilityRegistry to select the appropriate backend."""
    p_reg, b_reg, _, _ = clean_registries
    orchestrator = MasterOrchestrator(planner_registry=p_reg, backend_registry=b_reg)

    # CapabilityRegistry knows 'power.battery' belongs to 'desktop'
    from core.capabilities.capability_registry import CapabilityRegistry
    cap_reg = CapabilityRegistry.get_instance()
    assert cap_reg.resolve_domain("power.battery") == "desktop"

    # Backend selection using resolved domain
    backend = b_reg.select_best_backend("power.battery", domain="desktop")
    assert backend is not None
    assert backend.name == "desktop_engine"


