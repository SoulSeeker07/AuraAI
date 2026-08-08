"""
Regression tests for Intent Routing and Slot Filling.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.orchestration import DecisionEngine, IntentType, MasterOrchestrator
from Memory import FavoriteEditorQuestion, Memory, PendingQuestion


@pytest.fixture(autouse=True)
def patch_memory_db(tmp_path):
    # Dynamically patch Memory.__init__ to use temp db paths for complete test isolation
    original_init = Memory.__init__
    db_path = tmp_path / "Memory.db"
    chat_path = tmp_path / "ChatLog.json"

    def patched_init(self, *args, **kwargs):
        p_db = kwargs.get("db_path") or (args[0] if len(args) > 0 else None)
        p_chat = kwargs.get("chat_log_path") or (args[1] if len(args) > 1 else None)
        original_init(self, db_path=p_db or db_path, chat_log_path=p_chat or chat_path)

    Memory.__init__ = patched_init
    yield
    Memory.__init__ = original_init


@pytest.mark.asyncio
async def test_remember_favorite_editor_routing():
    # Initialize orchestrator
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    goal = "Remember that my favorite editor is VS Code"

    # 1. Assert intent routing is classified as MEMORY + memory_write capability
    engine = DecisionEngine()
    outcome = engine.evaluate(goal=goal)
    assert outcome.intent_type == IntentType.MEMORY
    assert outcome.capability == "memory_write"
    assert outcome.preferred_planner == "memory"

    # 2. Run through the full orchestrator
    result = await orchestrator.process_request_async(goal_text=goal)

    assert result.success is True

    memory = Memory()
    assert memory.favorite_editor == "VS Code"

    # Verify no coding/desktop backend was called
    assert result.planner == "memory"
    assert result.data["backend"] == "MemoryBackend"
    assert result.data["capability"] == "memory_write"


@pytest.mark.asyncio
async def test_memory_recall_routing():
    # Initialize orchestrator
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    # Pre-populate memory
    memory = Memory()
    memory.upsert_fact("preference", "favorite_editor", "VS Code")

    goal = "What is my favorite editor?"

    # 1. Assert intent routing is classified as MEMORY + memory_read capability
    engine = DecisionEngine()
    outcome = engine.evaluate(goal=goal)
    assert outcome.intent_type == IntentType.MEMORY
    assert outcome.capability == "memory_read"
    assert outcome.preferred_planner == "memory"

    # 2. Run through the full orchestrator
    result = await orchestrator.process_request_async(goal_text=goal)

    assert result.success is True
    assert any("VS Code" in obs for obs in result.observations)
    assert result.planner == "memory"
    assert result.data["backend"] == "MemoryBackend"
    assert result.data["capability"] == "memory_read"


@pytest.mark.asyncio
async def test_session_summary_routing():
    # Initialize orchestrator
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    # Add a mock previous interaction
    memory = Memory()
    memory.remember_exchange("Open VS Code", "VS Code opened", "desktop")

    goal = "Summarize today's session"

    # 1. Assert intent routing is classified as SESSION + session_summary capability
    engine = DecisionEngine()
    outcome = engine.evaluate(goal=goal)
    assert outcome.intent_type == IntentType.SESSION
    assert outcome.capability == "session_summary"

    # 2. Run through the full orchestrator
    result = await orchestrator.process_request_async(goal_text=goal)

    assert result.success is True
    # The summary observation should contain the previous action
    summary_obs = result.observations[0]
    assert "Open VS Code" in summary_obs
    assert "Today's Aura Session" in summary_obs
    assert "Artifacts" in summary_obs
    assert "Verification" in summary_obs

    # Verify the SessionSummaryArtifact was added to artifacts
    assert len(result.artifacts) == 1
    assert result.artifacts[0].artifact_type == "session_summary"


@pytest.mark.asyncio
async def test_favorite_editor_question_slot_filling():
    # Initialize orchestrator
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    pending_question = FavoriteEditorQuestion()
    answer = "VS Code"

    result = await orchestrator.process_request_async(
        goal_text=answer, context=pending_question
    )

    assert result.success is True

    memory = Memory()
    assert memory.favorite_editor == "VS Code"
    assert pending_question.slot_value == "VS Code"
    assert result.planner == "none"
    assert result.data["backend"] == "none"


@pytest.mark.asyncio
async def test_pending_question_context():
    # Initialize orchestrator
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    goal = "VS Code"
    context = PendingQuestion("favorite_editor")

    result = await orchestrator.process_request_async(goal_text=goal, context=context)

    assert result.success is True
    assert context.slot_value == "VS Code"

    memory = Memory()
    assert memory.favorite_editor == "VS Code"
    assert result.planner == "none"
    assert result.data["backend"] == "none"


@pytest.mark.asyncio
async def test_vs_code_alone_is_not_coding():
    # Verify that VS Code alone is treated as a desktop/app request, not coding
    engine = DecisionEngine()
    goal = "VS Code"
    outcome = engine.evaluate(goal=goal)
    assert outcome.intent_type == IntentType.DESKTOP_ACTION
