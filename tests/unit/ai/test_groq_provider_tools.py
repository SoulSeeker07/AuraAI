"""
tests/unit/ai/test_groq_provider_tools.py
=========================================
Unit tests verifying GroqProvider.chat_with_tools:
- Dynamic model selection (default text model vs vision model on image_url presence)
- Explicit model override
- KeyPool failover and fallback key handling
"""

from unittest.mock import MagicMock
import pytest
from ai.groq_provider import GroqProvider


def test_chat_with_tools_selects_default_text_model_when_text_only(monkeypatch):
    provider = GroqProvider(default_model="openai/gpt-oss-120b", vision_model="qwen/qwen3.6-27b")
    mock_client = MagicMock()
    monkeypatch.setattr(provider, "_get_client", lambda key: mock_client)
    monkeypatch.setattr(provider._key_pool, "execute_with_failover", lambda fn, service: fn("test_key"))

    messages = [{"role": "user", "content": "What is 2 + 2?"}]
    tools = [{"type": "function", "function": {"name": "calc"}}]

    provider.chat_with_tools(messages=messages, tools=tools, model=None)

    assert mock_client.chat.completions.create.called
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "openai/gpt-oss-120b"


def test_chat_with_tools_selects_vision_model_when_image_present(monkeypatch):
    provider = GroqProvider(default_model="openai/gpt-oss-120b", vision_model="qwen/qwen3.6-27b")
    mock_client = MagicMock()
    monkeypatch.setattr(provider, "_get_client", lambda key: mock_client)
    monkeypatch.setattr(provider._key_pool, "execute_with_failover", lambda fn, service: fn("test_key"))

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,123"}},
            ],
        }
    ]
    tools = [{"type": "function", "function": {"name": "inspect"}}]

    provider.chat_with_tools(messages=messages, tools=tools, model=None)

    assert mock_client.chat.completions.create.called
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "qwen/qwen3.6-27b"


def test_chat_with_tools_respects_explicit_model_override(monkeypatch):
    provider = GroqProvider(default_model="openai/gpt-oss-120b", vision_model="qwen/qwen3.6-27b")
    mock_client = MagicMock()
    monkeypatch.setattr(provider, "_get_client", lambda key: mock_client)
    monkeypatch.setattr(provider._key_pool, "execute_with_failover", lambda fn, service: fn("test_key"))

    messages = [{"role": "user", "content": "text"}]
    tools = []

    provider.chat_with_tools(messages=messages, tools=tools, model="openai/gpt-oss-20b")

    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "openai/gpt-oss-20b"


def test_chat_with_tools_falls_back_when_keypool_exhausted(monkeypatch):
    provider = GroqProvider(api_key="env_fallback_key", default_model="openai/gpt-oss-120b")
    mock_client = MagicMock()
    monkeypatch.setattr(provider, "_get_client", lambda key: mock_client)

    # KeyPool raises rate limit exhaustion
    from ai.exceptions import KeyPoolExhaustedError
    def raise_exhausted(fn, service):
        raise KeyPoolExhaustedError("All keys rate-limited (429 RateLimitError).")

    monkeypatch.setattr(provider._key_pool, "execute_with_failover", raise_exhausted)
    monkeypatch.setattr(provider._key_pool, "get_all_keys", lambda service: ["exhausted_key_1", "exhausted_key_2"])

    messages = [{"role": "user", "content": "hello"}]
    tools = []

    provider.chat_with_tools(messages=messages, tools=tools)

    assert mock_client.chat.completions.create.called
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "openai/gpt-oss-120b"


def test_chat_with_tools_image_overrides_explicit_text_model(monkeypatch):
    provider = GroqProvider(default_model="openai/gpt-oss-120b", vision_model="qwen/qwen3.6-27b")
    mock_client = MagicMock()
    monkeypatch.setattr(provider, "_get_client", lambda key: mock_client)
    monkeypatch.setattr(provider._key_pool, "execute_with_failover", lambda fn, service: fn("test_key"))

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Inspect screen"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        }
    ]
    tools = []

    # Explicit text model passed, but image payload requires vision model
    provider.chat_with_tools(messages=messages, tools=tools, model="openai/gpt-oss-20b")

    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "qwen/qwen3.6-27b"


def test_chat_with_tools_real_keypool_exhaustion_triggers_fallback(monkeypatch):
    from ai.key_pool import KeyPool

    # Instantiate real KeyPool with 2 dummy keys
    real_pool = KeyPool(explicit_keys={"groq": ["dummy_key_1", "dummy_key_2"]})
    provider = GroqProvider(api_key="env_fallback_key", default_model="openai/gpt-oss-120b")
    provider._key_pool = real_pool

    mock_fallback_client = MagicMock()

    class FakeRateLimitError(Exception):
        def __init__(self):
            self.status_code = 429
            super().__init__("429 Too Many Requests: Rate limit reached")

    def mock_get_client(key: str):
        if key == "env_fallback_key":
            return mock_fallback_client
        failing_client = MagicMock()
        failing_client.chat.completions.create.side_effect = FakeRateLimitError()
        return failing_client

    monkeypatch.setattr(provider, "_get_client", mock_get_client)

    messages = [{"role": "user", "content": "test"}]
    provider.chat_with_tools(messages=messages, tools=[])

    # Assert fallback client was invoked after both pool keys encountered 429
    assert mock_fallback_client.chat.completions.create.called
    kwargs = mock_fallback_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "openai/gpt-oss-120b"


