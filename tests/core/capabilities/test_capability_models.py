"""
Unit Tests for Universal Capability Models
==========================================
Location: tests/core/capabilities/test_capability_models.py
"""

from core.capabilities.models import Capability, PlanGraphError, PlanValidationResult
from core.orchestration.autonomy_mode import ActionRisk


def test_capability_dataclass_initialization():
    """Verify Capability instantiation, default values, and fqn property."""
    cap = Capability(
        name="test.action",
        domain="coding",
        description="A test capability",
        category="testing",
        input_schema={"type": "object", "properties": {"arg": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"res": {"type": "integer"}}},
        risk_level=ActionRisk.MEDIUM,
        permissions=["filesystem:write"],
        is_destructive=True,
        requires=["test.prereq"],
        verifies=["test.verify"],
        rollback_capabilities=["test.undo"],
        tags=["test", "unit"],
    )

    assert cap.name == "test.action"
    assert cap.domain == "coding"
    assert cap.fqn == "coding:test.action"
    assert cap.risk_level == ActionRisk.MEDIUM
    assert cap.is_destructive is True
    assert cap.is_live is True
    assert cap.availability == "online"
    assert cap.requires == ["test.prereq"]
    assert cap.verifies == ["test.verify"]
    assert cap.rollback_capabilities == ["test.undo"]

    # Test serialization to dictionary
    d = cap.to_dict()
    assert d["name"] == "test.action"
    assert d["domain"] == "coding"
    assert d["fqn"] == "coding:test.action"
    assert d["risk_level"] == "medium"
    assert d["is_destructive"] is True
    assert d["requires"] == ["test.prereq"]


def test_plan_validation_result_structure():
    """Verify PlanValidationResult and PlanGraphError structures."""
    res = PlanValidationResult(
        valid=False,
        errors=["Missing capability"],
        warnings=["Non-optimal order"],
        missing_prerequisites=[("task_2", "task_1_cap")],
        unwired_capabilities=["browser.navigate"],
    )

    assert res.valid is False
    assert len(res.errors) == 1
    assert len(res.warnings) == 1
    assert res.missing_prerequisites == [("task_2", "task_1_cap")]
    assert res.unwired_capabilities == ["browser.navigate"]

    err = PlanGraphError("Cyclic dependency")
    assert str(err) == "Cyclic dependency"
