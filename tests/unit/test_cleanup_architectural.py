import pytest
import asyncio
from unittest.mock import MagicMock, patch

from core.orchestration.reference_resolver import ReferenceResolver
from core.orchestration.task_decomposer import TaskDecomposer
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.planning.action_plan import ActionPlan
from core.orchestration.confirmation import ActionPlanConfirmation
from core.backends.adapters.desktop_backend import DesktopEngineBackend


def test_pronoun_resolution_open_it():
    # Setup timeline/ownership mocked state
    with patch("core.orchestration.reference_resolver.ResourceOwnershipTracker") as mock_tracker, \
         patch("core.orchestration.reference_resolver.WorldTimeline") as mock_timeline:
        
        # Priority 1: Mock last referenced object in ownership
        mock_owner = MagicMock()
        mock_res = MagicMock()
        mock_res.resource_id = "calc"
        mock_res.details = {"app_name": "calc"}
        mock_owner.get_aura_resources.return_value = [mock_res]
        mock_tracker.get_instance.return_value = mock_owner
        
        resolved_text, metadata = ReferenceResolver.resolve_references("Open it")
        assert resolved_text.lower() == "open calc"
        assert metadata["resolved"] is True
        assert metadata["target"] == "calc"


def test_clause_splitting_decomposition():
    decomposer = TaskDecomposer()
    decision = MagicMock()
    decision.intent_type = MagicMock()
    decision.intent_type.value = "desktop_action"
    
    # Test "open notepad and type hello world"
    graph = decomposer.decompose("open notepad and type hello world", decision)
    subtasks = list(graph.subtasks.values())
    
    # Should split into two subtasks
    assert len(subtasks) == 2
    
    # Verify subtask 1: Open Notepad
    t1 = subtasks[0]
    assert t1.capability == "app_open"
    assert t1.parameters["app_name"] == "notepad"
    
    # Verify subtask 2: Type hello world depending on t1
    t2 = subtasks[1]
    assert t2.capability == "keyboard.type"
    assert t2.parameters["app_name"] == "keyboard"
    assert t2.parameters["text"] == "hello world"
    assert t2.dependencies == [t1.task_id]


@pytest.mark.asyncio
async def test_confirmation_bypass_in_orchestrator():
    orchestrator = MasterOrchestrator.get_instance()
    
    # Setup dummy confirmation
    plan = ActionPlan(
        action="app_open",
        target="calc",
        goal="Open calc",
        capability="app_open",
        arguments={},
        session_id="session_123"
    )
    conf = ActionPlanConfirmation(
        session_id="session_123",
        action_plan=plan,
        prompt="Open calc already open?"
    )
    
    # Mock session
    mock_session = MagicMock()
    mock_session.pending_confirmation = conf
    orchestrator._last_session = mock_session
    
    # Mock resolve_pending_confirmation and _write_memory
    with patch.object(orchestrator, "resolve_pending_confirmation") as mock_resolve, \
         patch.object(orchestrator, "_write_memory") as mock_write:
        
        from core.planning.execution_result import ExecutionResult
        dummy_res = ExecutionResult(success=True, planner="desktop", goal="y", observations=["Confirmed"])
        mock_resolve.return_value = dummy_res
        
        # Invoke process_request_async with "y"
        res = await orchestrator.process_request_async("y")
        
        # Verify it intercepted and resolved confirmation directly
        mock_resolve.assert_called_once_with("y")
        mock_write.assert_called_once()
        assert res == dummy_res
