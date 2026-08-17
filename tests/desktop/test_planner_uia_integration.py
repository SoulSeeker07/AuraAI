"""
Integration Tests: Natural Language Planning & Goal Decomposition for UIA Capabilities (uia.*)
==============================================================================================
Validates:
1. Natural Language Goal Parsing & Classification (GoalParser, GoalClassifier)
2. Same-Domain UIA DAG Resolution (DependencyResolver, DesktopPlanner)
3. Cross-Domain Chaining (WindowManager -> UIAManager in TaskDecomposer)
4. Fail-Closed Ambiguity Protection (UIAManager rejects ambiguous multi-match mutations)
5. Confirmation Surfacing across the NL layer (requires_confirmation=True)
6. Universal Capability Registry Graph Validation (fail-closed prerequisite enforcement)
7. Dry-Run Plan Explanation (explain_plan preview)
8. End-to-End Execution & Inter-Step Parameter Propagation
"""

from unittest.mock import MagicMock, patch
import pytest

from core.capabilities.capability_registry import CapabilityRegistry as UniversalCapabilityRegistry
from core.orchestration.task_decomposer import PlannerRole, TaskDecomposer
from desktop.native.adapters.uia_adapter import (
    UIAAdapter,
    UIAElement,
    UIATreeNode,
)
from desktop.native.capability_registry import CapabilityRegistry as NativeCapabilityRegistry
from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    DesktopResult,
    get_desktop_execution_engine,
    reset_desktop_execution_engine,
)
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.uia_manager import UIAManager
from desktop.planner.desktop_plan import DesktopPlan
from desktop.planner.desktop_step import DesktopStep, StepStatus, StepType
from desktop.planner.goal_classifier import GoalClassifier
from desktop.planner.goal_parser import GoalParser
from desktop.planner.planner import DesktopPlanner


@pytest.fixture(autouse=True)
def clean_registries():
    """Ensure clean registry state before and after each test."""
    reset_desktop_execution_engine()
    NativeManagerRegistry.reset_instance()
    UniversalCapabilityRegistry.reset_instance()
    yield
    reset_desktop_execution_engine()
    NativeManagerRegistry.reset_instance()
    UniversalCapabilityRegistry.reset_instance()


# ── 1. Natural Language Goal Parsing & Classification ────────────────────────


def test_goal_parser_extracts_uia_click_intent():
    parser = GoalParser()
    goal = parser.parse("Click the Save button in Notepad")

    assert goal.explicit_capability == "uia.click"
    assert goal.parameters.get("window_title") == "Notepad"
    assert goal.parameters.get("name") == "Save"
    assert goal.parameters.get("control_type") == "Button"


def test_goal_parser_extracts_uia_type_text_intent():
    parser = GoalParser()
    goal = parser.parse("Type 'Hello World' into Search in Notepad")

    assert goal.explicit_capability == "uia.type_text"
    assert goal.parameters.get("window_title") == "Notepad"
    assert goal.parameters.get("name") == "Search"
    assert goal.parameters.get("text") == "Hello World"


def test_goal_parser_extracts_uia_toggle_intent():
    parser = GoalParser()
    goal = parser.parse("Toggle Dark Mode checkbox in Settings")

    assert goal.explicit_capability == "uia.toggle"
    assert goal.parameters.get("window_title") == "Settings"
    assert goal.parameters.get("name") == "Dark Mode"
    assert goal.parameters.get("control_type") == "CheckBox"


def test_goal_parser_extracts_uia_tree_and_find_intent():
    parser = GoalParser()

    tree_goal = parser.parse("Inspect UI tree in Notepad")
    assert tree_goal.explicit_capability == "uia.get_tree"
    assert tree_goal.parameters.get("window_title") == "Notepad"

    find_goal = parser.parse("Find element Submit in Chrome")
    assert find_goal.explicit_capability == "uia.find_element"
    assert find_goal.parameters.get("window_title") == "Chrome"
    assert find_goal.parameters.get("name") == "Submit"


def test_goal_classifier_categorizes_uia():
    classifier = GoalClassifier()

    assert classifier.classify("click Save button in Notepad") == "uia"
    assert classifier.classify("type into search box") == "uia"
    assert classifier.classify("toggle checkbox") == "uia"
    assert classifier.classify("inspect ui tree") == "uia"
    assert classifier.classify("get value of Search") == "uia"


# ── 2. Same-Domain UIA DAG Resolution ────────────────────────────────────────


def test_dependency_resolver_generates_verified_uia_dag():
    planner = DesktopPlanner()
    plan = planner.create_plan("Click the Save button in Notepad")

    assert len(plan.steps) == 3

    # Step 1: Preparation (uia.find_element)
    assert plan.steps[0].step_type == StepType.PREPARATION
    assert plan.steps[0].capability == "uia.find_element"
    assert plan.steps[0].arguments.get("window_title") == "Notepad"
    assert plan.steps[0].arguments.get("name") == "Save"

    # Step 2: Action (uia.click)
    assert plan.steps[1].step_type == StepType.ACTION
    assert plan.steps[1].capability == "uia.click"
    assert plan.steps[1].requires == ["uia.find_element"]
    assert plan.steps[1].verifies == ["uia.get_value"]

    # Step 3: Verification (uia.get_value)
    assert plan.steps[2].step_type == StepType.VERIFICATION
    assert plan.steps[2].capability == "uia.get_value"


# ── 3. Cross-Domain Chaining (WindowManager -> UIAManager) ───────────────────


def test_task_decomposer_cross_domain_chaining():
    decomposer = TaskDecomposer()
    graph = decomposer.decompose("open notepad and click the Save button")

    assert len(graph.subtasks) == 2
    tasks = list(graph.subtasks.values())

    # Task 1: WindowManager domain (app_open)
    assert tasks[0].required_role == PlannerRole.DESKTOP
    assert tasks[0].capability == "app_open"
    assert tasks[0].parameters.get("app_name") == "notepad"
    assert tasks[0].dependencies == []

    # Task 2: UIAManager domain (uia.click) with cross-domain context & dependency
    assert tasks[1].required_role == PlannerRole.DESKTOP
    assert tasks[1].capability == "uia.click"
    assert tasks[1].parameters.get("name") == "Save"
    assert tasks[1].parameters.get("window_title") == "notepad"
    assert tasks[1].dependencies == [tasks[0].task_id]

    # Level execution order must sequence them Level 1 -> Level 2
    assert len(graph.execution_order) == 2
    assert graph.execution_order[0] == [tasks[0].task_id]
    assert graph.execution_order[1] == [tasks[1].task_id]


# ── 4. Fail-Closed Ambiguity Protection ──────────────────────────────────────


class MockAmbiguousUIAAdapter(UIAAdapter):
    """Mock adapter simulating ambiguous multi-match elements."""

    def __init__(self, elements: list[UIAElement]):
        super().__init__()
        self._elements = elements

    def find_element(self, window_title, control_type=None, name=None, automation_id=None, depth=10):
        return self._elements[0] if len(self._elements) == 1 else None

    def find_elements(self, window_title, control_type=None, name=None, automation_id=None, depth=10):
        return self._elements

    def get_element_tree(self, window_title, depth=3):
        return None

    def get_element_value(self, element, window_title):
        return "val"

    def click_element(self, element, window_title):
        return True

    def type_text(self, element, text, window_title):
        return True

    def invoke_element(self, element, window_title):
        return True

    def toggle_element(self, element, window_title):
        return True

    def select_item(self, element, item_name, window_title):
        return True

    def wait_for_element(self, window_title, control_type=None, name=None, automation_id=None, timeout_seconds=10.0, poll_interval=0.5):
        return self._elements[0] if self._elements else None

    def is_available(self):
        return True



def test_uia_manager_fails_closed_on_ambiguous_element_matches():
    # Two identical buttons named "OK" in different dialog panels
    elem1 = UIAElement(control_type="Button", name="OK", automation_id="btn_ok_1")
    elem2 = UIAElement(control_type="Button", name="OK", automation_id="btn_ok_2")

    adapter = MockAmbiguousUIAAdapter([elem1, elem2])
    manager = UIAManager(adapter=adapter)

    # 1. find_element must fail closed
    res_find = manager.execute("uia.find_element", {"window_title": "TestApp", "name": "OK"})
    assert res_find.success is False
    assert "Ambiguous" in res_find.error
    assert res_find.data.get("ambiguous") is True
    assert res_find.data.get("count") == 2

    # 2. click must NOT execute on element[0] blindly — must fail closed
    res_click = manager.execute("uia.click", {"window_title": "TestApp", "name": "OK"})
    assert res_click.success is False
    assert "Ambiguous" in res_click.error


def test_uia_manager_succeeds_when_criteria_uniquely_identifies_element():
    elem_unique = UIAElement(control_type="Button", name="Save", automation_id="btn_save")
    adapter = MockAmbiguousUIAAdapter([elem_unique])
    manager = UIAManager(adapter=adapter)

    res_find = manager.execute("uia.find_element", {"window_title": "TestApp", "name": "Save"})
    assert res_find.success is True
    assert res_find.data["element"]["name"] == "Save"

    # Click with pre-supplied or resolved unique element succeeds
    with patch.object(adapter, "get_element_value", side_effect=["0", "1"]):
        res_click = manager.execute("uia.click", {"window_title": "TestApp", "name": "Save"})
        assert res_click.success is True
        assert res_click.data["verification_passed"] is True


# ── 5. Confirmation Surfacing across the NL Layer ────────────────────────────


def test_uia_click_requires_confirmation_in_capability_registry():
    univ_reg = UniversalCapabilityRegistry.get_instance()
    cap = univ_reg.get("uia.click")

    assert cap is not None
    assert cap.requires_confirmation is True
    assert cap.is_destructive is True


def test_explain_plan_surfaces_high_risk_and_confirmation_for_nl_goal():
    planner = DesktopPlanner()
    explanation = planner.explain_plan("Click the Save button in Notepad")

    assert explanation["overall_risk_level"] in ("HIGH", "CRITICAL")
    assert explanation["total_steps"] == 3

    click_step = next(s for s in explanation["steps"] if s["capability"] == "uia.click")
    assert click_step["risk_level"] == "HIGH"


# ── 6. Universal Capability Registry Graph Validation ────────────────────────


def test_universal_registry_validates_uia_graph_prerequisites():
    univ_reg = UniversalCapabilityRegistry.get_instance()

    # Valid UIA plan graph: requires satisfied
    valid_res = univ_reg.validate_plan_graph(
        ["uia.find_element", "uia.click", "uia.get_value"], require_live=True
    )
    assert valid_res.valid is True
    assert len(valid_res.errors) == 0

    # Invalid UIA plan graph: missing prerequisite 'uia.find_element' for 'uia.click'
    invalid_res = univ_reg.validate_plan_graph(
        ["uia.click"], require_live=True, require_prerequisites=True
    )
    assert invalid_res.valid is False
    assert any("uia.find_element" in err for err in invalid_res.errors)


# ── 7. End-to-End Execution with Inter-Step Parameter Propagation ────────────


def test_desktop_planner_execute_plan_with_data_propagation():
    elem_dict = {
        "control_type": "Button",
        "name": "Save",
        "automation_id": "btn_save",
        "class_name": "Button",
        "bounding_rect": [100, 100, 180, 130],
        "is_enabled": True,
        "is_offscreen": False,
        "value": "Save",
        "patterns": ["Invoke"],
        "is_interactable": True,
    }

    mock_engine = MagicMock(spec=DesktopExecutionEngine)

    def engine_execute_side_effect(goal, capability, arguments=None):
        if capability == "uia.find_element":
            return DesktopResult(
                success=True,
                manager="UIAManager",
                data={"element": elem_dict, "message": "Found element: Save"},
            )
        elif capability == "uia.click":
            # Verify that element dict was propagated to this step's arguments!
            assert arguments is not None
            assert "element" in arguments
            assert arguments["element"]["name"] == "Save"
            return DesktopResult(
                success=True,
                manager="UIAManager",
                data={
                    "element_name": "Save",
                    "pre_value": "0",
                    "post_value": "1",
                    "state_changed": True,
                    "verification_passed": True,
                },
            )
        elif capability == "uia.get_value":
            assert arguments is not None
            assert "element" in arguments
            return DesktopResult(
                success=True,
                manager="UIAManager",
                data={"element_name": "Save", "value": "1"},
            )
        return DesktopResult(success=True)

    mock_engine.execute.side_effect = engine_execute_side_effect

    planner = DesktopPlanner(engine=mock_engine)
    plan = planner.create_plan("Click the Save button in Notepad")

    executed_plan = planner.execute_plan(plan)

    assert executed_plan.is_complete is True
    assert all(s.status == StepStatus.SUCCESS for s in executed_plan.steps)
    assert executed_plan.steps[1].arguments.get("element") == elem_dict


def test_desktop_backend_surfaces_actionable_ambiguity_observation():
    """Verify that DesktopEngineBackend surfaces candidate counts and advice on ambiguity."""
    from core.backends.adapters.desktop_backend import DesktopEngineBackend

    elem1 = UIAElement(control_type="Button", name="Delete", automation_id="btn_del_1")
    elem2 = UIAElement(control_type="Button", name="Delete", automation_id="btn_del_2")

    adapter = MockAmbiguousUIAAdapter([elem1, elem2])
    manager = UIAManager(adapter=adapter)

    mock_engine = MagicMock(spec=DesktopExecutionEngine)
    mock_engine.execute.return_value = manager.execute(
        "uia.click", {"window_title": "App", "name": "Delete"}
    )
    mock_engine.registry = NativeCapabilityRegistry()

    backend = DesktopEngineBackend(engine=mock_engine)
    result = backend.execute(
        goal="click Delete button",
        capability="uia.click",
        arguments={"window_title": "App", "name": "Delete"},
    )

    assert result.success is False
    assert len(result.observations) > 0
    obs = result.observations[0]
    # Check that error is actionable and lists candidate count and instruction
    assert "Ambiguous element match" in obs
    assert "found 2 elements" in obs
    assert "Provide a more specific name" in obs

