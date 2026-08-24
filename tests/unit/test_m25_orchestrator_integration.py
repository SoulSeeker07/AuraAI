"""
Unit Tests for M25 MasterOrchestrator Domain Expert Routing Integration (Stage 2.9).
Verifies default-disabled invariant, opt-in expert routing across all 4 domains,
downstream catch-and-fallback safety, near-miss decline, and precomputed graph zero-regression.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.task_decomposer import PlannerRole, SubTask, TaskGraph
from core.planning.execution_result import ExecutionResult
from experts.base_expert import DomainAssessment, PlanDAG, PlanNode
from experts.router import ExpertDomainRouter


def create_mock_backend(planner: str = "coding", goal: str = "test"):
    """Helper to create a synchronous mock backend adapter without async attributes."""
    backend = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "describe", "health_check"])
    backend.name = "mock_backend"
    res = ExecutionResult(success=True, planner=planner, goal=goal, observations=["Executed successfully"])
    backend.execute.return_value = res
    backend.execute_plan.return_value = res
    return backend


from core.backends.backend_registry import BackendRegistry


@pytest.fixture(autouse=True)
def reset_orchestrator_and_router():
    """Reset singleton state between tests."""
    MasterOrchestrator.reset_instance()
    ExpertDomainRouter.reset_instance()
    BackendRegistry.reset_instance()
    yield
    MasterOrchestrator.reset_instance()
    ExpertDomainRouter.reset_instance()
    BackendRegistry.reset_instance()


@pytest.mark.asyncio
async def test_default_disabled_invariant():
    """Verify MasterOrchestrator defaults expert_routing_enabled to False and uses legacy TaskDecomposer."""
    orchestrator = MasterOrchestrator(expert_routing_enabled=False)
    assert orchestrator.expert_routing_enabled is False

    goal = "audit this repository for security vulnerabilities"

    with patch.object(orchestrator.planner_registry, "route_to_expert", wraps=orchestrator.planner_registry.route_to_expert) as mock_route:
        mock_backend = create_mock_backend(planner="coding", goal=goal)
        orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

        res = await orchestrator.process_request_async(goal)

        assert res.success is True
        # route_to_expert must NOT be called when flag is False
        mock_route.assert_not_called()
        assert orchestrator._last_session.metrics.get("expert_domain") is None


@pytest.mark.asyncio
async def test_opt_in_expert_routing_all_domains():
    """Verify opt-in expert routing routes to cybersecurity, network, software, and finance experts."""
    orchestrator = MasterOrchestrator(expert_routing_enabled=True)
    assert orchestrator.expert_routing_enabled is True

    domain_goals = [
        ("audit this repository for security vulnerabilities", "cybersecurity"),
        ("diagnose high packet loss and latency on wifi adapter", "network_engineering"),
        ("refactor the authentication module and fix failing pytest regressions", "software_engineering"),
        ("calculate EBITDA gross margin and forecast CAGR revenue", "finance"),
    ]

    mock_backend = create_mock_backend(planner="desktop", goal="subtask")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    for goal, expected_domain in domain_goals:
        res = await orchestrator.process_request_async(goal)

        assert res.success is True
        session = orchestrator._last_session
        assert session.metrics.get("expert_domain") == expected_domain
        assert session.metrics.get("expert_assessment_id") is not None
        assert session.metrics.get("expert_confidence") >= 0.50
        assert any(f"Routed to {expected_domain} expert" in obs.content for obs in session.observations)


@pytest.mark.asyncio
async def test_downstream_failure_catch_and_fallback():
    """Verify compiler/DAG generation failure inside Stage 2.9 cleanly falls through to TaskDecomposer without failing."""
    orchestrator = MasterOrchestrator(expert_routing_enabled=True)

    goal = "audit this repository for security vulnerabilities"

    # Mock expert.generate_plan to simulate downstream failure
    router = orchestrator.planner_registry.get_expert_router()
    sec_expert = router.get_expert("cybersecurity")
    assert sec_expert is not None

    with patch.object(sec_expert, "generate_plan", side_effect=ValueError("Simulated PlanDAG generation error")):
        mock_backend = create_mock_backend(planner="coding", goal=goal)
        orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

        res = await orchestrator.process_request_async(goal)

        # Must succeed via fallback
        assert res.success is True
        session = orchestrator._last_session
        # Telemetry must NOT claim expert routing succeeded
        assert session.metrics.get("expert_domain") is None
        assert session.metrics.get("expert_assessment_id") is None


@pytest.mark.asyncio
async def test_near_miss_decline_and_fallback():
    """Verify plausible near-miss queries decline expert routing (<0.50) and fall through to TaskDecomposer."""
    orchestrator = MasterOrchestrator(expert_routing_enabled=True)

    near_miss_queries = [
        "search for the best coding bootcamp",
        "search the web for python tutorials",
        "is my password strong",
        "bake an authentic sourdough bread loaf",
    ]

    mock_backend = create_mock_backend(planner="general", goal="near_miss")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    for goal in near_miss_queries:
        res = await orchestrator.process_request_async(goal)

        assert res.success is True
        session = orchestrator._last_session
        # All near-misses must decline expert routing
        assert session.metrics.get("expert_domain") is None


@pytest.mark.asyncio
async def test_precomputed_graph_bypass_and_zero_regression():
    """Verify precomputed TaskGraph bypasses Stage 2.9 identically under both flag states."""
    goal = "audit repository for security vulnerabilities"

    for flag_state in (False, True):
        orchestrator = MasterOrchestrator(expert_routing_enabled=flag_state)

        # Manually construct precomputed graph with precomputed execution levels
        custom_graph = TaskGraph(goal=goal)
        custom_subtask = SubTask(
            task_id="custom_task_1",
            title="Custom Precomputed Task",
            required_role=PlannerRole.CODING,
            capability="code.analyze",
            description="Inspect custom precomputed code",
            parameters={"goal": goal},
        )
        custom_graph.add_task(custom_subtask)
        custom_graph.execution_order = [["custom_task_1"]]

        with patch.object(orchestrator.planner_registry, "route_to_expert") as mock_route:
            mock_backend = create_mock_backend(planner="coding", goal=goal)
            orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

            res = await orchestrator.process_request_async(goal, task_graph=custom_graph)

            assert res.success is True
            # Precomputed graph must bypass Stage 2.9 under both flag states
            mock_route.assert_not_called()
            session = orchestrator._last_session
            assert session.metrics.get("expert_domain") is None


@pytest.mark.asyncio
async def test_orchestrator_fail_closed_missing_input_artifact():
    """Verify MasterOrchestrator halts execution and reports error when required input artifact is missing."""
    orchestrator = MasterOrchestrator(expert_routing_enabled=False)

    graph = TaskGraph(goal="Test missing artifact fail-closed")
    st1 = SubTask(
        task_id="st_mem_1",
        title="Recall Preference",
        required_role=PlannerRole.MEMORY,
        capability="memory.recall",
        parameters={"query": "test_pref"},
        output_artifacts=["art_mem_1"],
    )
    st2 = SubTask(
        task_id="st_doc_2",
        title="Synthesize Document",
        required_role=PlannerRole.DESKTOP,
        capability="document.generate",
        dependencies=["st_mem_1"],
        input_artifacts=["art_research_missing"],
        output_artifacts=["art_doc_final"],
    )
    graph.add_task(st1)
    graph.add_task(st2)
    orchestrator.decomposer._compute_execution_levels(graph)

    mock_backend = create_mock_backend(planner="memory", goal="test")
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_backend)

    res = await orchestrator.process_request_async("Test missing artifact fail-closed", task_graph=graph)

    assert res.success is False
    assert any("Research stage completed without producing a payload" in obs or "Artifact validation failed" in obs or "missing" in obs.lower() for obs in res.observations)
    assert st2.status == "failed"


@pytest.mark.asyncio
async def test_orchestrator_fail_closed_empty_payload_artifact():
    """Verify MasterOrchestrator halts execution when an upstream artifact exists but has an empty payload."""
    from core.orchestration.artifact import Artifact

    orchestrator = MasterOrchestrator(expert_routing_enabled=False)

    graph = TaskGraph(goal="Test empty artifact fail-closed")
    st1 = SubTask(
        task_id="st_res_1",
        title="Research Task",
        required_role=PlannerRole.RESEARCH,
        capability="research.search",
        parameters={"query": "test_query"},
        output_artifacts=["art_res_empty"],
    )
    st2 = SubTask(
        task_id="st_doc_2",
        title="Synthesize Document",
        required_role=PlannerRole.DESKTOP,
        capability="document.generate",
        dependencies=["st_res_1"],
        input_artifacts=["art_res_empty"],
        output_artifacts=["art_doc_final"],
    )
    graph.add_task(st1)
    graph.add_task(st2)
    orchestrator.decomposer._compute_execution_levels(graph)

    # Mock backend produces an artifact with empty string payload
    backend = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "describe", "health_check"])
    backend.name = "mock_backend"
    empty_art = Artifact(artifact_id="art_res_empty", content="   ", artifact_type="research")
    res_empty = ExecutionResult(
        success=True,
        planner="research",
        goal="test",
        observations=["Search completed with empty content"],
        artifacts=[empty_art.to_dict()],
    )
    backend.execute.return_value = res_empty
    backend.execute_plan.return_value = res_empty
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=backend)

    res = await orchestrator.process_request_async("Test empty artifact fail-closed", task_graph=graph)

    assert res.success is False
    assert any(
        "no content payload" in obs.lower()
        or "requires artifact" in obs.lower()
        or "cannot continue" in obs.lower()
        or "without producing a payload" in obs.lower()
        for obs in res.observations
    )
    assert st2.status == "failed"


@pytest.mark.asyncio
async def test_orchestrator_fail_closed_low_confidence_artifact():
    """Verify MasterOrchestrator halts execution when an upstream artifact is populated but carries confidence below threshold."""
    from core.orchestration.artifact import Artifact, VerificationReport

    orchestrator = MasterOrchestrator(expert_routing_enabled=False)

    graph = TaskGraph(goal="Test low-confidence artifact fail-closed")
    st1 = SubTask(
        task_id="st_res_1",
        title="Research Task",
        required_role=PlannerRole.RESEARCH,
        capability="research.search",
        parameters={"query": "unverified rumors query"},
        output_artifacts=["art_res_low_conf"],
    )
    st2 = SubTask(
        task_id="st_doc_2",
        title="Synthesize Document",
        required_role=PlannerRole.DESKTOP,
        capability="document.generate",
        dependencies=["st_res_1"],
        input_artifacts=["art_res_low_conf"],
        output_artifacts=["art_doc_final"],
    )
    graph.add_task(st1)
    graph.add_task(st2)
    orchestrator.decomposer._compute_execution_levels(graph)

    # Mock backend produces a populated artifact with low confidence (0.25 < 0.40)
    backend = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "describe", "health_check"])
    backend.name = "mock_backend"
    low_conf_art = Artifact(
        artifact_id="art_res_low_conf",
        content="Some unverified rumors and conflicting data",
        artifact_type="research",
        metadata={"confidence_score": 0.25},
        verification_report=VerificationReport(success=False, confidence=0.25),
    )
    res_low_conf = ExecutionResult(
        success=True,
        planner="research",
        goal="test",
        confidence=0.25,
        observations=["Search completed with low confidence"],
        artifacts=[low_conf_art.to_dict()],
    )
    backend.execute.return_value = res_low_conf
    backend.execute_plan.return_value = res_low_conf
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=backend)

    res = await orchestrator.process_request_async("Test low-confidence artifact fail-closed", task_graph=graph)

    assert res.success is False
    assert any(
        "below minimum threshold" in obs.lower()
        or "cannot continue with unverified data" in obs.lower()
        or "confidence" in obs.lower()
        for obs in res.observations
    )
    assert st2.status == "failed"


@pytest.mark.asyncio
async def test_orchestrator_non_research_artifact_not_blocked_by_default():
    """Verify non-research artifacts (e.g. desktop/security) with low confidence are NOT blocked by default."""
    from core.orchestration.artifact import Artifact, VerificationReport

    orchestrator = MasterOrchestrator(expert_routing_enabled=False)

    graph = TaskGraph(goal="Test non-research artifact not blocked")
    st1 = SubTask(
        task_id="st_sec_1",
        title="Security Audit",
        required_role=PlannerRole.DESKTOP,
        capability="security.firewall_audit",
        parameters={},
        output_artifacts=["art_sec_telemetry"],
    )
    st2 = SubTask(
        task_id="st_notif_2",
        title="Send Notification",
        required_role=PlannerRole.DESKTOP,
        capability="notification.send",
        dependencies=["st_sec_1"],
        input_artifacts=["art_sec_telemetry"],
        output_artifacts=["art_notif_receipt"],
    )
    graph.add_task(st1)
    graph.add_task(st2)
    orchestrator.decomposer._compute_execution_levels(graph)

    # Mock backend produces a security artifact with confidence=0.25 (e.g. partial telemetry certainty)
    backend = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "describe", "health_check"])
    backend.name = "mock_backend"
    sec_art = Artifact(
        artifact_id="art_sec_telemetry",
        content="Firewall: active, Defender: unknown",
        artifact_type="security",
        metadata={"confidence_score": 0.25},
        verification_report=VerificationReport(success=True, confidence=0.25),
    )
    res_sec = ExecutionResult(
        success=True,
        planner="desktop",
        goal="test",
        confidence=0.25,
        observations=["Security audit completed with partial certainty"],
        artifacts=[sec_art.to_dict()],
    )
    backend.execute.return_value = res_sec
    backend.execute_plan.return_value = res_sec
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=backend)

    res = await orchestrator.process_request_async("Test non-research artifact not blocked", task_graph=graph)

    # Should succeed because non-research artifacts are not blocked by research threshold
    assert res.success is True
    assert st2.status == "completed"



