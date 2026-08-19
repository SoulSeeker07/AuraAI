"""
Unit Tests for Milestone 25: PlanDAG to TaskGraph Compiler
Location: tests/unit/test_plandag_compiler.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, os.path.abspath("src"))

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.autonomy_mode import ActionRisk
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.task_decomposer import PlannerRole, TaskGraph
from experts.compiler import PlanDAGCompiler
from experts.models import DomainAssessment, PlanDAG, PlanNode
from experts.router import ExpertDomainRouter


@pytest.fixture
def compiler() -> PlanDAGCompiler:
    return PlanDAGCompiler(capability_registry=CapabilityRegistry.get_instance())


@pytest.fixture
def router() -> ExpertDomainRouter:
    return ExpertDomainRouter()


@pytest.mark.asyncio
async def test_compile_software_expert_plandag(router: ExpertDomainRouter, compiler: PlanDAGCompiler):
    """Verify that a real Software Engineering PlanDAG compiles accurately into a TaskGraph."""
    expert = router.get_expert("software_engineering")
    assert expert is not None

    goal = "Fix circular import in service modules and run regression tests"
    assessment = await expert.assess(goal)
    plan = await expert.generate_plan(goal, assessment)

    task_graph = compiler.compile(plan)
    assert isinstance(task_graph, TaskGraph)
    assert task_graph.goal == goal
    assert len(task_graph.subtasks) == 4
    assert len(task_graph.execution_order) >= 2

    # Verify individual subtasks and role mappings
    sw_discover = task_graph.subtasks["sw_discover_01"]
    assert sw_discover.required_role == PlannerRole.CODING
    assert sw_discover.capability == "workspace.walk"
    assert sw_discover.dependencies == []
    assert sw_discover.input_artifacts == []
    assert sw_discover.output_artifacts == ["art_sw_discover_01"]
    assert sw_discover.parameters["risk_level"] == "low"
    assert sw_discover.parameters["assessment_id"] == assessment.assessment_id
    assert sw_discover.parameters["plan_id"] == plan.plan_id

    sw_edit = task_graph.subtasks["sw_code_edit_03"]
    assert sw_edit.required_role == PlannerRole.CODING
    assert sw_edit.capability == "code.edit"
    assert sw_edit.dependencies == ["sw_ast_analyze_02"]
    assert sw_edit.input_artifacts == ["art_sw_ast_analyze_02"]
    assert sw_edit.output_artifacts == ["art_sw_code_edit_03"]
    assert sw_edit.parameters["risk_level"] == "high"


@pytest.mark.asyncio
async def test_compile_all_four_domain_experts(router: ExpertDomainRouter, compiler: PlanDAGCompiler):
    """Verify that all 4 professional domain expert plans compile without error."""
    test_cases = [
        ("software_engineering", "Refactor authentication layer and verify tests"),
        ("network_engineering", "Diagnose packet loss and trace route to gateway"),
        ("cybersecurity", "Audit firewall rules and scan open ports"),
        ("finance", "Forecast quarterly revenue and compute variance analysis"),
    ]

    for domain, goal in test_cases:
        expert = router.get_expert(domain)
        assert expert is not None

        assessment = await expert.assess(goal)
        plan = await expert.generate_plan(goal, assessment)
        task_graph = compiler.compile(plan)

        assert isinstance(task_graph, TaskGraph)
        assert len(task_graph.subtasks) >= 3
        assert len(task_graph.execution_order) >= 2

        # Verify all subtasks are valid
        for task_id, subtask in task_graph.subtasks.items():
            assert subtask.task_id == task_id
            assert isinstance(subtask.required_role, PlannerRole)
            assert subtask.parameters["assessment_id"] == assessment.assessment_id
            assert subtask.parameters["plan_id"] == plan.plan_id
            assert subtask.parameters["domain"] == domain
            # Artifact consistency
            assert subtask.output_artifacts == [f"art_{task_id}"]
            for dep in subtask.dependencies:
                assert f"art_{dep}" in subtask.input_artifacts


def test_fail_loud_unknown_capability(compiler: PlanDAGCompiler):
    """Verify compiler immediately raises ValueError on unregistered capability."""
    plan = PlanDAG.create(
        domain="software_engineering",
        goal="Do magic",
        assessment_id="dasm_test_01",
    )
    plan.add_node(
        PlanNode(
            node_id="magic_01",
            capability="nonexistent.magic.capability.xyz",
            description="Do impossible action",
        )
    )

    with pytest.raises(ValueError, match="requests unknown capability 'nonexistent.magic.capability.xyz'"):
        compiler.compile(plan)


def test_fail_loud_cyclic_dependency(compiler: PlanDAGCompiler):
    """Verify compiler detects cyclic dependencies and fails loudly."""
    plan = PlanDAG.create(
        domain="software_engineering",
        goal="Cyclic Task",
        assessment_id="dasm_test_02",
    )
    plan.add_node(PlanNode(node_id="node_a", capability="code.analyze", dependencies=["node_b"]))
    plan.add_node(PlanNode(node_id="node_b", capability="code.test", dependencies=["node_a"]))

    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        compiler.compile(plan)


def test_fail_loud_dangling_dependency(compiler: PlanDAGCompiler):
    """Verify compiler rejects dangling/missing dependency references."""
    plan = PlanDAG.create(
        domain="software_engineering",
        goal="Dangling Task",
        assessment_id="dasm_test_03",
    )
    plan.add_node(PlanNode(node_id="node_1", capability="code.analyze", dependencies=["non_existent_node_99"]))

    with pytest.raises(ValueError, match="references non-existent dependency 'non_existent_node_99'"):
        compiler.compile(plan)


def test_fail_loud_empty_plandag(compiler: PlanDAGCompiler):
    """Verify compiler rejects empty PlanDAGs."""
    plan = PlanDAG.create(
        domain="software_engineering",
        goal="Empty Task",
        assessment_id="dasm_test_04",
    )
    with pytest.raises(ValueError, match="Cannot compile empty PlanDAG"):
        compiler.compile(plan)


def test_type_error_on_invalid_input(compiler: PlanDAGCompiler):
    """Verify compiler enforces PlanDAG type check."""
    with pytest.raises(TypeError, match="PlanDAGCompiler expects a PlanDAG instance"):
        compiler.compile({"goal": "not a plandag"}  # type: ignore
    )


@pytest.mark.asyncio
async def test_end_to_end_master_orchestrator_execution_with_compiled_graph(compiler: PlanDAGCompiler):
    """Verify that a compiled TaskGraph executes cleanly through MasterOrchestrator."""
    from core.backends.backend_registry import BackendRegistry
    from core.backends.base_backend import BaseBackendAdapter
    from core.orchestration.artifact import Artifact
    from core.planning.execution_result import ExecutionResult

    plan = PlanDAG.create(
        domain="software_engineering",
        goal="Scan workspace structure and analyze source AST",
        assessment_id="dasm_test_e2e_01",
    )
    plan.add_node(
        PlanNode(
            node_id="sw_walk_01",
            capability="workspace.walk",
            description="Scan workspace structure",
            risk_level=ActionRisk.LOW,
        )
    )
    plan.add_node(
        PlanNode(
            node_id="sw_ast_02",
            capability="code.analyze",
            dependencies=["sw_walk_01"],
            description="Build AST symbol graph",
            risk_level=ActionRisk.LOW,
        )
    )
    plan.compute_execution_stages()

    task_graph = compiler.compile(plan)
    assert len(task_graph.subtasks) == 2
    assert len(task_graph.execution_order) == 2

    class MockCodingBackend(BaseBackendAdapter):
        @property
        def name(self) -> str:
            return "mock_coding_backend"

        @property
        def capabilities(self) -> list[str]:
            return ["workspace.walk", "code.analyze"]

        def health_check(self) -> bool:
            return True

        def describe(self) -> dict[str, Any]:
            return {"name": self.name, "capabilities": self.capabilities}

        def execute(self, capability: str, goal: str = "", arguments: dict[str, Any] | None = None) -> ExecutionResult:
            return ExecutionResult(
                success=True,
                planner="coding",
                goal=goal,
                confidence=1.0,
                observations=[f"Successfully executed {capability}"],
                artifacts=[
                    Artifact(
                        artifact_id=f"art_{capability.replace('.', '_')}",
                        artifact_type="generic",
                        content=f"Payload for {capability}",
                        creator="mock_coding_backend",
                    )
                ],
            )

    backend_reg = BackendRegistry.get_instance()
    mock_backend = MockCodingBackend()
    backend_reg.register(mock_backend)
    backend_reg._capability_map["workspace.walk"] = [mock_backend.name]
    backend_reg._capability_map["code.analyze"] = [mock_backend.name]

    orchestrator = MasterOrchestrator(backend_registry=backend_reg)
    result = await orchestrator.process_request_async(
        goal_text="Scan workspace structure and analyze source AST",
        task_graph=task_graph,
    )

    assert result is not None
    assert result.success is True
    assert len(result.observations) >= 1
    assert result.data.get("subtasks_completed") == 2
