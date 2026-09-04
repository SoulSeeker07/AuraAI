import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from core.aura_core import AuraCore
from core.orchestration import MasterOrchestrator
from core.orchestration.agent_session import AgentSession
from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher

@pytest.mark.asyncio
async def test_unified_tool_dispatcher_integration_in_auracore():
    core = AuraCore.get_instance()
    orch = MasterOrchestrator.get_instance()
    
    # Verify UnifiedToolDispatcher provides 14 tools
    tools = UnifiedToolDispatcher.get_tool_definitions()
    assert len(tools) == 14

    # Execute a safe tool through dispatch
    res = await UnifiedToolDispatcher.dispatch("system_get_telemetry", {})
    assert res["status"] == "success"
    assert "cpu_usage" in res

@pytest.mark.asyncio
async def test_high_risk_action_confirmation_lifecycle():
    orch = MasterOrchestrator.get_instance()
    session = AgentSession(goal="Delete files")
    orch._last_session = session

    # Step 1: Dispatch high-risk command -> requires confirmation
    cmd = "rm -rf /some/directory"
    res = await UnifiedToolDispatcher.dispatch("terminal_run_command", {"command": cmd}, session=session)
    assert res["status"] == "confirmation_required"
    assert "ticket_id" in res
    tkt_id = res["ticket_id"]
    assert session.pending_confirmation is not None

    # Step 2: User responds with "no" -> cancels gracefully
    res_cancel = orch.resolve_pending_confirmation("no")
    assert res_cancel is not None
    assert orch.check_pending_confirmation() is None
