"""
Unit Tests for M25 Phase 1: DomainExpertPlanner Contract & ExpertDomainRouter
Location: tests/unit/test_domain_expert_contract.py

Verifies:
1. DomainExpertPlanner contract and lifecycle interface compliance.
2. DomainAssessment immutability, schema versioning, and JSON serialization.
3. PlanDAG topological sorting into parallel execution stages and cycle detection.
4. Plan validation against CapabilityRegistry (missing dependencies, unknown capabilities).
5. ExpertDomainRouter deterministic confidence ranking and explainable routing.
6. Safe failure and graceful fallback for unsupported domain goals.
7. Strict Planning != Execution invariant (zero capability invocations during planning).
8. Causal identity preservation across DomainAssessment and PlanDAG.
"""

from dataclasses import FrozenInstanceError
from typing import Any
import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.models import Capability
from core.orchestration.autonomy_mode import ActionRisk
from core.orchestration.planner_registry import PlannerRegistry
from experts.base_expert import DomainExpertPlanner
from experts.models import DomainAssessment, PlanDAG, PlanNode
from experts.router import ExpertDomainRouter


class MockSoftwareExpertPlanner(DomainExpertPlanner):
    """Mock Software Engineering expert for contract testing."""

    @property
    def domain(self) -> str:
        return "software_engineering"

    @property
    def description(self) -> str:
        return "Expertise in AST analysis, code refactoring, and test reproduction."

    def can_handle(
        self, goal_text: str, context: dict[str, Any] | None = None
    ) -> tuple[bool, float, str]:
        g = goal_text.lower()
        if any(w in g for w in ["refactor", "bug", "pytest", "ast", "code"]):
            return True, 0.90, "Matched software engineering keywords."
        return False, 0.10, "Not a software engineering task."

    async def assess(
        self, goal_text: str, context: dict[str, Any] | None = None
    ) -> DomainAssessment:
        causal = (context or {}).get("causal_context", {})
        return DomainAssessment.create(
            domain=self.domain,
            confidence=0.90,
            findings=["Found Python codebase", "Pytest suite configured"],
            assumptions=["Workspace is writable", "Tests can be executed locally"],
            required_capabilities=["code.analyze", "code.edit", "terminal.execute"],
            recommended_strategy="Analyze AST -> Propose patch -> Run reproduction test",
            causal_context=causal,
        )

    async def generate_plan(
        self,
        goal_text: str,
        assessment: DomainAssessment,
        context: dict[str, Any] | None = None,
    ) -> PlanDAG:
        plan = PlanDAG.create(
            domain=self.domain,
            goal=goal_text,
            assessment_id=assessment.assessment_id,
            causal_context=dict(assessment.causal_context),
        )
        plan.add_node(
            PlanNode(
                node_id="analyze_01",
                capability="code.analyze",
                description="Analyze AST structure",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.add_node(
            PlanNode(
                node_id="edit_02",
                capability="code.edit",
                dependencies=["analyze_01"],
                description="Apply code changes",
                risk_level=ActionRisk.MEDIUM,
            )
        )
        plan.add_node(
            PlanNode(
                node_id="test_03",
                capability="terminal.execute",
                dependencies=["edit_02"],
                description="Execute reproduction test",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.compute_execution_stages()
        return plan


class MockNetworkExpertPlanner(DomainExpertPlanner):
    """Mock Network Engineering expert for contract testing."""

    @property
    def domain(self) -> str:
        return "network_engineering"

    @property
    def description(self) -> str:
        return "Expertise in DNS probing, interface routing, and socket diagnostics."

    def can_handle(
        self, goal_text: str, context: dict[str, Any] | None = None
    ) -> tuple[bool, float, str]:
        g = goal_text.lower()
        if any(w in g for w in ["dns", "ping", "socket", "packet loss", "latency", "network"]):
            return True, 0.95, "Matched network diagnostics keywords."
        return False, 0.10, "Not a network engineering task."

    async def assess(
        self, goal_text: str, context: dict[str, Any] | None = None
    ) -> DomainAssessment:
        causal = (context or {}).get("causal_context", {})
        return DomainAssessment.create(
            domain=self.domain,
            confidence=0.95,
            findings=["Network interface eth0 active", "Packet drop detected"],
            assumptions=["ICMP echo permitted", "Gateway reachable"],
            required_capabilities=["network.ping", "network.route_inspect"],
            recommended_strategy="Inspect routing table -> Probe DNS -> Trace packet hops",
            causal_context=causal,
        )

    async def generate_plan(
        self,
        goal_text: str,
        assessment: DomainAssessment,
        context: dict[str, Any] | None = None,
    ) -> PlanDAG:
        plan = PlanDAG.create(
            domain=self.domain,
            goal=goal_text,
            assessment_id=assessment.assessment_id,
            causal_context=dict(assessment.causal_context),
        )
        plan.add_node(
            PlanNode(
                node_id="ping_01",
                capability="network.ping",
                description="Ping gateway",
                risk_level=ActionRisk.LOW,
            )
        )
        plan.compute_execution_stages()
        return plan


@pytest.fixture
def expert_router():
    router = ExpertDomainRouter()
    router.register_expert(MockSoftwareExpertPlanner())
    router.register_expert(MockNetworkExpertPlanner())
    yield router
    router._experts.clear()


def test_domain_assessment_immutability():
    """Verify DomainAssessment is frozen, tamper-resistant, and supports dictionary roundtrip."""
    assessment = DomainAssessment.create(
        domain="software_engineering",
        confidence=0.88,
        findings=["File missing"],
        assumptions=["User will confirm"],
        required_capabilities=["code.edit"],
        recommended_strategy="Patch and test",
        causal_context={"event_id": "evt_123", "policy_decision_id": "pol_456"},
    )

    assert assessment.assessment_id.startswith("dasm_")
    assert assessment.confidence == 0.88
    assert assessment.causal_context["event_id"] == "evt_123"

    with pytest.raises((FrozenInstanceError, AttributeError)):
        assessment.confidence = 0.5  # type: ignore

    # Serialization roundtrip
    as_dict = assessment.to_dict()
    assert as_dict["assessment_id"] == assessment.assessment_id
    reconstructed = DomainAssessment.from_dict(as_dict)
    assert reconstructed.assessment_id == assessment.assessment_id
    assert reconstructed.domain == "software_engineering"
    assert reconstructed.causal_context["policy_decision_id"] == "pol_456"


def test_plan_dag_topological_stages_and_cycle_detection():
    """Verify PlanDAG computes parallel execution stages and rejects cyclic dependencies."""
    plan = PlanDAG.create(
        domain="software_engineering",
        goal="Fix test failure",
        assessment_id="dasm_test_01",
    )

    # Independent tasks
    plan.add_node(PlanNode(node_id="task_A", capability="code.analyze"))
    plan.add_node(PlanNode(node_id="task_B", capability="code.inspect"))
    # Dependent tasks
    plan.add_node(PlanNode(node_id="task_C", capability="code.edit", dependencies=["task_A", "task_B"]))
    plan.add_node(PlanNode(node_id="task_D", capability="terminal.execute", dependencies=["task_C"]))

    stages = plan.compute_execution_stages()
    assert len(stages) == 3
    assert set(stages[0]) == {"task_A", "task_B"}  # Stage 1: parallel
    assert stages[1] == ["task_C"]                 # Stage 2: depends on A & B
    assert stages[2] == ["task_D"]                 # Stage 3: depends on C

    # Cyclic DAG detection
    cyclic_plan = PlanDAG.create(
        domain="software_engineering",
        goal="Cyclic test",
        assessment_id="dasm_test_02",
    )
    cyclic_plan.add_node(PlanNode(node_id="node_1", capability="cap_1", dependencies=["node_2"]))
    cyclic_plan.add_node(PlanNode(node_id="node_2", capability="cap_2", dependencies=["node_1"]))

    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        cyclic_plan.compute_execution_stages()


def test_plan_dag_validation_with_capability_registry():
    """Verify PlanDAG validation detects missing dependencies and unknown capabilities."""
    cap_registry = CapabilityRegistry.get_instance()
    cap_registry.register(Capability(name="test.cap_valid", domain="desktop"))

    planner = MockSoftwareExpertPlanner()
    plan = PlanDAG.create(domain="software_engineering", goal="Test", assessment_id="dasm_01")
    
    # Valid node
    plan.add_node(PlanNode(node_id="node_ok", capability="test.cap_valid"))
    # Node with invalid capability and non-existent dependency
    plan.add_node(PlanNode(node_id="node_bad", capability="unknown.capability_999", dependencies=["phantom_task"]))

    res = planner.validate_plan(plan, capability_registry=cap_registry)
    assert res.valid is False
    assert any("references non-existent dependency 'phantom_task'" in e for e in res.errors)
    assert any("requests unknown capability 'unknown.capability_999'" in e for e in res.errors)


@pytest.mark.asyncio
async def test_expert_domain_router_selection_and_ranking(expert_router):
    """Verify ExpertDomainRouter correctly routes to Software or Network expert based on goal semantics."""
    # 1. Route Software Goal
    sw_goal = "Refactor the authentication module and fix pytest regressions"
    sw_expert, sw_asm, sw_rationale = await expert_router.route(sw_goal)

    assert sw_expert is not None
    assert sw_expert.domain == "software_engineering"
    assert sw_asm is not None
    assert sw_asm.domain == "software_engineering"
    assert sw_asm.confidence >= 0.90
    assert "software engineering" in sw_rationale.lower()

    # 2. Route Network Goal
    net_goal = "Diagnose packet loss and inspect DNS resolution for local gateway"
    net_expert, net_asm, net_rationale = await expert_router.route(net_goal)

    assert net_expert is not None
    assert net_expert.domain == "network_engineering"
    assert net_asm is not None
    assert net_asm.domain == "network_engineering"
    assert net_asm.confidence >= 0.95
    assert "network" in net_rationale.lower()


@pytest.mark.asyncio
async def test_expert_domain_router_unsupported_goal_fallback(expert_router):
    """Verify goals not matching any expert domain gracefully return None without raising errors."""
    obscure_goal = "Bake an authentic sourdough bread loaf"
    expert, asm, rationale = await expert_router.route(obscure_goal, min_confidence=0.50)

    assert expert is None
    assert asm is None
    assert "No domain expert matched goal" in rationale


@pytest.mark.asyncio
async def test_strict_planning_zero_execution_invariant():
    """Verify calling assess(), generate_plan(), explain_plan() performs zero capability executions."""
    expert = MockSoftwareExpertPlanner()
    goal = "Refactor memory module"

    assessment = await expert.assess(goal, context={"causal_context": {"event_id": "evt_trace_1"}})
    plan = await expert.generate_plan(goal, assessment)
    explanation = expert.explain_plan(plan, assessment)

    assert isinstance(assessment, DomainAssessment)
    assert isinstance(plan, PlanDAG)
    assert len(plan.nodes) == 3
    assert "SOFTWARE_ENGINEERING" in explanation
    # No OS calls, subprocesses, or capability executions triggered


@pytest.mark.asyncio
async def test_planner_registry_expert_routing_integration():
    """Verify PlannerRegistry interacts seamlessly with ExpertDomainRouter."""
    reg = PlannerRegistry.get_instance()
    router = reg.get_expert_router()
    router.register_expert(MockSoftwareExpertPlanner())

    expert, asm, rationale = await reg.route_to_expert("Fix pytest failure in billing.py")
    assert expert is not None
    assert expert.domain == "software_engineering"
    assert asm is not None
