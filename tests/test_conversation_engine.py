import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse
from ai.provider import Provider
from ai.provider_manager import ProviderManager
from brain.conversation_engine import ConversationEngine
from brain.web_search import WebSearchResult
from Memory import Memory


class FakeProvider(Provider):
    capabilities = ProviderCapabilities(
        name="fake", default_model="fake-model", supports_streaming=True
    )

    def __init__(self):
        self.last_request = None

    def chat(self, request: ChatRequest, **kwargs) -> ProviderResponse:
        self.last_request = request
        return ProviderResponse(
            "provider answer", provider="fake", model=request.model or "fake-model"
        )


class FakeWebSearch:
    def search(self, query: str, limit: int = 5):
        return [
            WebSearchResult(
                title="Fresh Result",
                url="https://example.com/fresh",
                snippet=f"Fresh context for {query}",
            )
        ]


def build_engine(tmp_path):
    memory = Memory(
        db_path=tmp_path / "Memory.db", chat_log_path=tmp_path / "ChatLog.json"
    )
    provider = FakeProvider()
    manager = ProviderManager(default_provider="fake")
    manager.register("fake", provider)
    engine = ConversationEngine(
        memory=memory,
        provider_manager=manager,
        settings={"provider": "fake", "model": "fake-model"},
        username="User",
        assistant_name="Aura",
        model="fake-model",
        web_search=FakeWebSearch(),
    )
    engine.browser_engine = None
    return engine, provider



import pytest


@pytest.mark.asyncio
async def test_conversation_engine_handles_memory_intent_without_provider(tmp_path):
    engine, provider = build_engine(tmp_path)

    result = await engine.process("I'm learning Palo Alto.")

    assert "Palo Alto" in result.text
    assert result.intent.name == "remember_fact"
    assert result.used_provider is False
    assert provider.last_request is None


@pytest.mark.asyncio
async def test_conversation_engine_builds_context_for_provider(tmp_path):
    engine, provider = build_engine(tmp_path)
    await engine.process("I'm learning Palo Alto.")

    result = await engine.process("Tell me more about it")

    assert result.text == "provider answer"
    assert result.intent.name in ("provider_chat", "web_search", "autonomous_browser")
    assert result.used_provider is True
    assert provider.last_request is not None
    assert any(
        "Known user memory" in message.content
        for message in provider.last_request.messages
    )


@pytest.mark.asyncio
async def test_conversation_engine_adds_web_context_for_current_questions(tmp_path):
    engine, provider = build_engine(tmp_path)

    from brain.intent_router import Intent
    engine.intent_router.detect = lambda text, attachments=None: Intent("web_search")
    result = await engine.process("What is the latest Python release?")

    assert result.intent.name == "web_search"



    assert result.used_provider is True
    assert provider.last_request is not None
    assert any(
        "Fresh web context" in message.content
        for message in provider.last_request.messages
    )


@pytest.mark.asyncio
async def test_conversation_engine_desktop_action_dispatches_through_chokepoint(tmp_path, universal_dispatch_spy):
    """Verify that desktop actions route through ExecutionPolicy and MasterOrchestrator._dispatch_plan."""
    engine, _ = build_engine(tmp_path)

    from brain.models import Intent
    engine.intent_router.detect = lambda text, attachments=None: Intent(
        name="desktop_action",
        data={"verb": "minimize", "target": "notepad", "raw": text},
    )

    result = await engine.process("minimize notepad")
    assert "completed successfully" in result.text or "✓" in result.text or "Action" in result.text

    # Verify that universal_dispatch_spy observed the dispatch via _dispatch_plan
    assert len(universal_dispatch_spy.events) == 1
    assert universal_dispatch_spy.events[0].capability == "window.minimize"


@pytest.mark.asyncio
async def test_conversation_engine_desktop_action_blocks_high_risk_capability(tmp_path, universal_dispatch_spy):
    """Verify that if a high-risk capability is mapped into desktop action, ExecutionPolicy blocks it."""
    engine, _ = build_engine(tmp_path)

    from brain.models import Intent
    # Simulate a compromised or malicious intent routed to fast-path
    engine.intent_router.detect = lambda text, attachments=None: Intent(
        name="desktop_action",
        data={"verb": "kill", "target": "credentials.txt", "raw": text},
    )

    from unittest.mock import patch
    from core.orchestration.autonomy_mode import ActionRisk

    # Classify the target action as HIGH risk
    with patch("core.orchestration.execution_policy.ExecutionPolicy.evaluate_action") as mock_eval:
        from core.orchestration.execution_policy import PolicyAction, PolicyDecision
        mock_eval.return_value = PolicyDecision(
            action=PolicyAction.ASK_USER,
            message="Requires interactive confirmation",
            app_name="desktop.app_close",
        )

        result = await engine.process("kill credentials.txt")
        assert "requires explicit confirmation before execution" in result.text
        # Assert zero backend dispatches occurred
        assert len(universal_dispatch_spy.events) == 0


@pytest.mark.asyncio
async def test_terminal_ticket_redemption_fails_closed_when_auth_verification_fails(tmp_path):
    """Verify that if verify_and_redeem fails, terminal command execution is aborted."""
    engine, _ = build_engine(tmp_path)
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from core.config import PROJECT_ROOT
    from unittest.mock import patch

    auth = CryptographicApprovalAuthority.get_instance(storage_path=tmp_path / "test_approval_tickets.json")
    ticket_id = auth.create_ticket(
        action_type="terminal_execution",
        target="malicious_command_here",
        parameters={"cwd": str(PROJECT_ROOT)},
        description="Dangerous command",
    )

    with patch.object(auth, "verify_and_redeem", return_value=(False, "Tampered payload")):
        result = await engine.process(f"yes confirm {ticket_id}")
        assert "Security Error: Ticket authorization failed" in result.text
        assert "Command execution aborted" in result.text


@pytest.mark.asyncio
async def test_terminal_ticket_redemption_fails_closed_when_cwd_missing(tmp_path):
    """Verify that if ticket parameters lack 'cwd', terminal execution is aborted."""
    engine, _ = build_engine(tmp_path)
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority

    auth = CryptographicApprovalAuthority.get_instance(storage_path=tmp_path / "test_approval_tickets.json")
    # Create ticket with empty parameters (no cwd)
    ticket_id = auth.create_ticket(
        action_type="terminal_execution",
        target="echo test",
        parameters=None,
        description="Command without cwd",
    )

    result = await engine.process(f"yes confirm {ticket_id}")
    assert "Security Error: Approval ticket has no bound working directory ('cwd')" in result.text
    assert "Execution aborted" in result.text


@pytest.mark.asyncio
async def test_terminal_ticket_redemption_executes_on_valid_verification(tmp_path):
    """Verify that a valid ticket with bound cwd and valid signature executes cleanly."""
    engine, _ = build_engine(tmp_path)
    from desktop.native.security.approval_authority import CryptographicApprovalAuthority
    from core.config import PROJECT_ROOT
    from unittest.mock import patch
    from desktop.native.managers.shell_executor import ShellExecutionResult

    valid_cwd = str(PROJECT_ROOT)
    auth = CryptographicApprovalAuthority.get_instance(storage_path=tmp_path / "test_approval_tickets.json")
    ticket_id = auth.create_ticket(
        action_type="terminal_execution",
        target="git status",
        parameters={"cwd": valid_cwd},
        description="Status command",
    )

    mock_res = ShellExecutionResult(
        success=True,
        stdout="On branch main\nnothing to commit",
        stderr="",
        returncode=0,
        command="git status",
        cwd=valid_cwd,
    )

    with patch("desktop.native.managers.shell_executor.execute_command", return_value=mock_res) as mock_exec:
        result = await engine.process(f"yes confirm {ticket_id}")
        assert "On branch main" in result.text
        mock_exec.assert_called_once_with("git status", cwd=valid_cwd)


