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

    def chat(self, request: ChatRequest) -> ProviderResponse:
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
    return engine, provider


def test_conversation_engine_handles_memory_intent_without_provider(tmp_path):
    engine, provider = build_engine(tmp_path)

    result = engine.process("I'm learning Palo Alto.")

    assert result.text == "Remembered. Skills: Palo Alto"
    assert result.intent.name == "remember_fact"
    assert result.used_provider is False
    assert provider.last_request is None


def test_conversation_engine_builds_context_for_provider(tmp_path):
    engine, provider = build_engine(tmp_path)
    engine.process("I'm learning Palo Alto.")

    result = engine.process("Explain OSPF")

    assert result.text == "provider answer"
    assert result.intent.name == "provider_chat"
    assert result.used_provider is True
    assert provider.last_request is not None
    assert any(
        "Known user memory" in message.content
        for message in provider.last_request.messages
    )


def test_conversation_engine_adds_web_context_for_current_questions(tmp_path):
    engine, provider = build_engine(tmp_path)

    result = engine.process("What is the latest Python release?")

    assert result.intent.name == "web_search"
    assert result.used_provider is True
    assert provider.last_request is not None
    assert any(
        "Fresh web context" in message.content
        for message in provider.last_request.messages
    )
