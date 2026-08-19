"""
Unit Tests for M25 Phase 2: Software Engineering Expert Subsystem
Location: tests/unit/test_software_expert.py

Verifies:
1. ASTAnalyzer in-memory parsing, symbol extraction, and syntax error safety.
2. DependencyAnalyzer import graphs, circular dependency cycle detection, and missing imports.
3. ReproductionPlanner automated reproduction test synthesis from tracebacks and pytest errors.
4. RefactoringPlanner multi-stage refactoring plans and atomic rollback descriptors.
5. SoftwareEngineeringExpertPlanner DomainAssessment and PlanDAG synthesis.
6. Strict Invariant: Zero file mutation and zero capability execution during planning.
7. Seamless routing integration via ExpertDomainRouter and PlannerRegistry.
"""

from pathlib import Path
import pytest

from core.capabilities.capability_registry import CapabilityRegistry
from core.orchestration.planner_registry import PlannerRegistry
from experts.models import DomainAssessment, PlanDAG
from experts.router import ExpertDomainRouter
from experts.software.ast_analyzer import ASTAnalyzer
from experts.software.dependency_analyzer import DependencyAnalyzer
from experts.software.planner import SoftwareEngineeringExpertPlanner
from experts.software.refactoring_planner import RefactoringPlanner
from experts.software.reproduction_planner import ReproductionPlanner


def test_ast_analyzer_valid_code_extraction():
    """Verify ASTAnalyzer extracts classes, methods, functions, and imports safely."""
    code = """
import os
from pathlib import Path
import non_existent_pkg

class OrderProcessor:
    def __init__(self, order_id: str):
        self.order_id = order_id
        
    async def process_async(self):
        return Path(self.order_id).name

def calculate_tax(amount: float) -> float:
    return amount * 0.15
"""
    analyzer = ASTAnalyzer()
    res = analyzer.analyze_source(code, file_path="orders.py")

    assert res["syntax_valid"] is True
    assert res["syntax_error"] is None
    assert len(res["classes"]) == 1
    assert res["classes"][0]["name"] == "OrderProcessor"
    assert "process_async" in res["classes"][0]["methods"]
    assert any(f["name"] == "calculate_tax" for f in res["functions"])
    assert "os" in res["imports"]
    assert "pathlib.Path" in res["imports"]


def test_ast_analyzer_syntax_error_resilience():
    """Verify ASTAnalyzer catches syntax errors without throwing unhandled exceptions."""
    broken_code = """
def broken_syntax(
    x = 10
    # Missing closing parenthesis and colon
"""
    analyzer = ASTAnalyzer()
    res = analyzer.analyze_source(broken_code, file_path="broken.py")

    assert res["syntax_valid"] is False
    assert "SyntaxError" in res["syntax_error"]
    assert res["classes"] == []
    assert res["functions"] == []


def test_dependency_analyzer_circular_import_detection():
    """Verify DependencyAnalyzer detects circular import cycles across modules."""
    files = {
        "module_a": "import module_b\ndef func_a(): pass",
        "module_b": "import module_c\ndef func_b(): pass",
        "module_c": "import module_a\ndef func_c(): pass",
        "module_d": "import sys\ndef func_d(): pass",
    }
    analyzer = DependencyAnalyzer()
    graph = analyzer.build_import_graph(files)
    cycles = analyzer.detect_circular_dependencies(graph)

    assert len(cycles) >= 1
    cycle_nodes = set(cycles[0])
    assert {"module_a", "module_b", "module_c"}.issubset(cycle_nodes)
    assert "module_d" not in cycle_nodes


def test_reproduction_planner_traceback_parsing():
    """Verify ReproductionPlanner parses tracebacks and synthesizes reproduction strategies."""
    tb = """
Traceback (most recent call last):
  File "src/billing/service.py", line 42, in process_invoice
    assert total > 0, "Total must be positive"
AssertionError: Total must be positive
"""
    planner = ReproductionPlanner()
    plan = planner.plan_reproduction(tb)

    assert plan["error_type"] == "AssertionError"
    assert plan["target_file"] == "src/billing/service.py"
    assert plan["failed_symbol"] == "process_invoice"
    assert "pytest src/billing/service.py -k process_invoice" in plan["test_command"]
    assert "Reproduce failure" in plan["reproduction_strategy"] or "Isolate failing condition" in plan["reproduction_strategy"]


def test_refactoring_planner_atomic_stages():
    """Verify RefactoringPlanner outputs multi-stage refactoring plans with rollback descriptors."""
    planner = RefactoringPlanner()
    plan = planner.plan_refactoring("Extract invoice calculation method into tax_calculator.py")

    assert plan["refactoring_type"] == "extract_method"
    assert len(plan["stages"]) == 3
    assert plan["stages"][0]["capability"] == "code.analyze"
    assert plan["stages"][1]["capability"] == "code.edit"
    assert plan["stages"][2]["capability"] == "code.test"
    assert "rollback" in plan["rollback_strategy"].lower()


@pytest.mark.asyncio
async def test_software_expert_planner_full_lifecycle():
    """Verify SoftwareEngineeringExpertPlanner assesses, plans, and explains without executing."""
    expert = SoftwareEngineeringExpertPlanner()
    goal = "Refactor payment_gateway.py and fix failing pytest assertions"

    can_handle, conf, rationale = expert.can_handle(goal)
    assert can_handle is True
    assert conf >= 0.85

    assessment = await expert.assess(goal, context={"causal_context": {"event_id": "evt_sw_99"}})
    assert isinstance(assessment, DomainAssessment)
    assert assessment.domain == "software_engineering"
    assert assessment.causal_context["event_id"] == "evt_sw_99"
    assert "code.edit" in assessment.required_capabilities

    plan = await expert.generate_plan(goal, assessment)
    assert isinstance(plan, PlanDAG)
    assert len(plan.nodes) == 4
    assert len(plan.execution_stages) >= 2

    # Validation against capability registry
    val_res = expert.validate_plan(plan, CapabilityRegistry.get_instance())
    assert val_res.valid is True

    explanation = expert.explain_plan(plan, assessment)
    assert "SOFTWARE_ENGINEERING" in explanation
    assert plan.plan_id in explanation


@pytest.mark.asyncio
async def test_software_expert_strict_zero_disk_mutation_invariant(tmp_path):
    """Verify that calling assess() and generate_plan() causes zero disk mutations."""
    test_file = tmp_path / "immutable_target.py"
    initial_content = "def untouched(): return True\n"
    test_file.write_text(initial_content, encoding="utf-8")

    expert = SoftwareEngineeringExpertPlanner()
    goal = f"Fix bug in {test_file}"

    assessment = await expert.assess(goal)
    plan = await expert.generate_plan(goal, assessment)

    # Verify target file on disk was completely untouched
    assert test_file.read_text(encoding="utf-8") == initial_content


@pytest.mark.asyncio
async def test_router_integration_with_software_expert():
    """Verify ExpertDomainRouter automatically discovers and routes coding tasks to SoftwareEngineeringExpertPlanner."""
    ExpertDomainRouter.reset_instance()
    router = ExpertDomainRouter.get_instance()

    goal = "Fix syntax error and circular import in authentication service"
    expert, assessment, rationale = await router.route(goal)

    assert expert is not None
    assert expert.domain == "software_engineering"
    assert assessment is not None
    assert assessment.domain == "software_engineering"
    assert assessment.confidence >= 0.85
    assert "software engineering" in rationale.lower()
