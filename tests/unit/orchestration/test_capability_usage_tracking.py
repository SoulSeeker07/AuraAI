import asyncio
import pytest
from pathlib import Path
from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.capability_usage_tracker import CapabilityUsageTracker
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.task_decomposer import SubTask, PlannerRole
from core.orchestration.agent_session import AgentSession
from core.orchestration.request_source import RequestSource

@pytest.fixture
def temp_tracker(tmp_path):
    test_db = tmp_path / "test_cap_usage.db"
    tracker = CapabilityUsageTracker(db_path=test_db)
    CapabilityUsageTracker._instance = tracker
    yield tracker
    CapabilityUsageTracker.reset_instance()


pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_capability_usage_normal_dispatch(temp_tracker):
    orchestrator = MasterOrchestrator.get_instance()
    session = AgentSession(goal="Test battery", session_id="sess_norm_1")
    subtask = SubTask(
        task_id="st_bat_1",
        title="Check battery",
        required_role=PlannerRole.DESKTOP,
        capability="power.battery",
        risk_tier="low",
    )
    context = {"session": session, "source": RequestSource.HUMAN_INTERACTIVE}

    res = await orchestrator._execute_level_task(
        task_id="st_bat_1",
        subtask=subtask,
        decision=None,
        context=context,
    )
    assert res.success is True

    with temp_tracker._connect() as conn:
        row = conn.execute("SELECT capability_id, usage_count, last_risk_level, last_source FROM capability_usage WHERE capability_id = 'power.battery'").fetchone()
    assert row is not None
    assert row[0] == "power.battery"
    assert row[1] == 1
    assert row[2] == "low"
    assert row[3] == "sess_norm_1"


@pytest.mark.asyncio
async def test_capability_usage_preauthorized_fallback(temp_tracker):
    orchestrator = MasterOrchestrator.get_instance()
    session = AgentSession(goal="Preauthorized task", session_id="sess_preauth_2")
    session.data["resumed_ticket_id"] = "ticket_valid_123"
    session.data["resumed_subtask_id"] = "st_win_2"

    subtask = SubTask(
        task_id="st_win_2",
        title="List windows",
        required_role=PlannerRole.DESKTOP,
        capability="list_windows",
        risk_tier="low",
    )
    context = {"session": session, "source": RequestSource.TRIGGER_AUTONOMOUS}

    res = await orchestrator._execute_level_task(
        task_id="st_win_2",
        subtask=subtask,
        decision=None,
        context=context,
    )
    assert res.success is True

    with temp_tracker._connect() as conn:
        row = conn.execute("SELECT capability_id, usage_count, last_risk_level, last_source FROM capability_usage WHERE capability_id = 'list_windows'").fetchone()
    assert row is not None
    assert row[0] == "list_windows"
    assert row[1] == 1
    assert row[2] == "low"
    assert row[3] == "sess_preauth_2"


@pytest.mark.asyncio
async def test_capability_usage_increment_and_coverage(temp_tracker):
    orchestrator = MasterOrchestrator.get_instance()
    session = AgentSession(goal="Test battery 2", session_id="sess_norm_2")
    subtask = SubTask(
        task_id="st_bat_2",
        title="Check battery again",
        required_role=PlannerRole.DESKTOP,
        capability="power.battery",
        risk_tier="low",
    )
    context = {"session": session, "source": RequestSource.HUMAN_INTERACTIVE}

    # Dispatch twice
    await orchestrator._execute_level_task(task_id="st_bat_2a", subtask=subtask, decision=None, context=context)
    await orchestrator._execute_level_task(task_id="st_bat_2b", subtask=subtask, decision=None, context=context)

    with temp_tracker._connect() as conn:
        row = conn.execute("SELECT usage_count FROM capability_usage WHERE capability_id = 'power.battery'").fetchone()
    assert row[0] == 2

    # Check coverage calculation
    all_caps = CapabilityRegistry.get_instance().list()
    all_ids = [c.name for c in all_caps]
    dash = temp_tracker.export_dashboard_json(all_ids)
    cov = dash["coverage"]
    assert cov["total_registered"] == len(all_caps)
    assert cov["used_at_least_once"] == 1
    assert cov["never_used"] == len(all_caps) - 1
    assert cov["coverage_pct"] > 0.0
