"""
Integration tests for PersonalOS Proactive Ambient Triggers & Cognitive Memory 2.0
Location: tests/unit/test_personal_os_proactive_cognitive_integration.py
"""

import asyncio
from datetime import datetime
import pytest

from src.memory.cognitive_memory import CognitiveMemoryEngine
from src.memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource
from src.personal_os.daily_context import DailyContextEngine
from src.personal_os.models import CalendarMeeting, DailyContext, DeadlineItem, TaskItem
from src.personal_os.state_store import PersonalOSStateStore
from src.personal_os.trigger_templates import TriggerTemplateRegistry
from src.autonomy.trigger_scheduler import TriggerScheduler
from src.autonomy.trigger_registry import TriggerRegistry
from src.autonomy.models import Trigger, TriggerType


@pytest.fixture
def memory_engine(tmp_path):
    """Isolated CognitiveMemoryEngine instance."""
    db_path = tmp_path / "test_cognitive.db"
    return CognitiveMemoryEngine(db_path=str(db_path))


@pytest.fixture
def state_store(tmp_path):
    """Isolated PersonalOSStateStore instance."""
    store_file = tmp_path / "test_personal_os.db"
    return PersonalOSStateStore(db_path=str(store_file))


def test_daily_context_ranked_memory_recall(memory_engine, state_store):
    """Test that DailyContextEngine retrieves tasks ranked by importance and updates access stats."""
    # Seed cognitive memories with varying importance
    mem1 = MemoryItem(
        type=MemoryType.EPISODIC,
        content="Task: Complete the architectural governance boundary verification",
        importance=0.95,
        confidence=0.90,
        project_id="global",
        provenance=MemoryProvenance(source_type=ProvenanceSource.USER_EXPLICIT),
    )
    mem2 = MemoryItem(
        type=MemoryType.EPISODIC,
        content="Task: Clean up temporary debug scratch files",
        importance=0.40,
        confidence=0.70,
        project_id="global",
        provenance=MemoryProvenance(source_type=ProvenanceSource.RUNTIME_SESSION),
    )
    saved1 = memory_engine.store_memory(mem1)
    saved2 = memory_engine.store_memory(mem2)

    engine = DailyContextEngine(state_store=state_store, memory_engine=memory_engine)
    context = engine.get_daily_context(target_date="2026-09-01")

    assert len(context.tasks) >= 2
    # Verify high-importance task is prioritized HIGH
    task_map = {t.title: t for t in context.tasks}
    assert any("governance boundary" in t.title for t in context.tasks)
    gov_task = next(t for t in context.tasks if "governance boundary" in t.title)
    assert gov_task.priority == "HIGH"

    # Verify access count was reinforced in database
    retrieved = memory_engine.get_memory(saved1.memory_id)
    assert retrieved is not None
    assert retrieved.access_count >= 1


def test_daily_context_adapts_to_communication_preference(memory_engine, state_store):
    """Test that DailyContext.format_summary adapts between detailed and concise formats."""
    engine = DailyContextEngine(state_store=state_store, memory_engine=memory_engine)

    # 1. Baseline without concise preference -> Standard detailed markdown
    ctx_default = engine.get_daily_context(target_date="2026-09-01")
    assert "### 📅 Daily Overview" in ctx_default.summary
    assert "#### ⚡ Prioritized Action Items" in ctx_default.summary

    # 2. Learn concise communication preference
    memory_engine.learn_preferences_from_text(
        "Keep everything concise and avoid unnecessary summary text",
        session_id="session_pref_1",
    )

    ctx_concise = engine.get_daily_context(target_date="2026-09-01")
    assert ctx_concise.preferences.get("communication") == "concise"
    # Concise mode uses high-density bullet format
    assert "**📅 Agenda (2026-09-01)**" in ctx_concise.summary
    assert "• **Priorities**:" in ctx_concise.summary


def test_daily_context_environment_tagging(memory_engine, state_store):
    """Test that active tooling and runtime language preferences are tagged in daily summary."""
    memory_engine.learn_preferences_from_text(
        "I prefer python 3.11 for all backend services",
        session_id="session_pref_2",
    )
    memory_engine.learn_preferences_from_text(
        "Let's stick with pnpm going forward",
        session_id="session_pref_3",
    )

    engine = DailyContextEngine(state_store=state_store, memory_engine=memory_engine)
    context = engine.get_daily_context(target_date="2026-09-01")

    assert context.preferences.get("runtime_lang") == "python"
    assert context.preferences.get("tooling") == "pnpm"
    assert "[python | pnpm]" in context.summary


@pytest.mark.asyncio
async def test_trigger_scheduler_dispatches_daily_briefing(memory_engine, state_store):
    """Test that TriggerScheduler can evaluate and fire a daily agenda sync trigger."""
    registry = TriggerRegistry()
    template_reg = TriggerTemplateRegistry()
    template = template_reg.get("daily_agenda_sync")
    assert template is not None

    goal = template.build_goal()
    assert "Synthesize daily context" in goal

    trigger = Trigger(
        trigger_id="daily_agenda_sync_test",
        trigger_type=TriggerType.SCHEDULED,
        action_goal=goal,
        execution_map={"action": "synthesize_daily_context"},
        cron_schedule="* * * * *",
    )
    registry.register_trigger(trigger)

    fired_events = []

    class MockCoordResult:
        success = True
        execution_id = "exec_123"

    class MockCoordinator:
        async def coordinate(self, exec_map):
            fired_events.append(exec_map)
            return MockCoordResult()

    scheduler = TriggerScheduler(
        registry=registry,
        coordinator=MockCoordinator(),
        poll_interval_seconds=0.1,
    )

    # Fire trigger directly via scheduler
    success = await scheduler.fire_trigger(trigger)
    assert success is True
    # Allow background execution task to complete
    await asyncio.sleep(0.05)
    assert len(fired_events) == 1
    assert "Synthesize daily context" in fired_events[0]["goal"]
