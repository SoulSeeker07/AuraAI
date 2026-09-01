import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is in sys.path
src_dir = Path(__file__).resolve().parents[2] / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from ai.exceptions import (
    GeminiQuotaExhaustedError,
    KeyPoolExhaustedError,
    ProviderError,
    ProviderNotFoundError,
)
from ai.gemini_provider import GeminiProvider
from ai.models import ChatMessage, ChatRequest, VisionRequest
from ai.provider_manager import ProviderManager


class TestGeminiProviderUnit:
    """Unit tests with mocked responses for GeminiProvider."""

    @pytest.fixture
    def provider(self):
        return GeminiProvider(api_key="mock_gemini_key", default_model="gemini-3.6-flash")

    def test_capabilities(self, provider):
        caps = provider.capabilities
        assert caps.name == "gemini"
        assert caps.default_model == "gemini-3.6-flash"
        assert caps.supports_streaming is True
        assert caps.supports_vision is False
        assert caps.supports_tools is True

    def test_vision_not_supported(self, provider):
        req = VisionRequest(prompt="Inspect screen", image=MagicMock())
        with pytest.raises(NotImplementedError) as exc:
            provider.vision(req)
        assert "does not support vision" in str(exc.value)

    @patch("google.genai.Client")
    def test_chat_success(self, mock_client_cls, provider):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "def add(a, b): return a + b"
        mock_client.models.generate_content.return_value = mock_response

        with patch.object(provider._key_pool, "execute_with_failover", side_effect=lambda op, service: op("mock_key")):
            req = ChatRequest(messages=[ChatMessage(role="user", content="Write add function")])
            resp = provider.chat(req)

        assert resp.text == "def add(a, b): return a + b"
        assert resp.provider == "gemini"
        assert resp.model == "gemini-3.6-flash"

    @patch("google.genai.Client")
    def test_stream_success(self, mock_client_cls, provider):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        chunk1, chunk2 = MagicMock(), MagicMock()
        chunk1.text = "Hello "
        chunk2.text = "World"
        mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]

        with patch.object(provider._key_pool, "execute_with_failover", side_effect=lambda op, service: op("mock_key")):
            req = ChatRequest(messages=[ChatMessage(role="user", content="Say hello")])
            chunks = list(provider.stream(req))

        assert chunks == ["Hello ", "World"]

    def test_quota_exhausted_429(self, provider):
        err = Exception("429 RESOURCE_EXHAUSTED: Rate limit reached for model gemini-3.6-flash")

        with patch.object(provider._key_pool, "execute_with_failover", side_effect=err):
            req = ChatRequest(messages=[ChatMessage(role="user", content="Test 429")])
            with pytest.raises(GeminiQuotaExhaustedError) as excinfo:
                provider.chat(req)
            assert "Gemini quota exhausted" in str(excinfo.value)

    def test_transient_error_retry(self, provider):
        mock_op = MagicMock()
        mock_op.side_effect = [Exception("503 Server Error"), "Success Response"]

        with patch.object(provider._key_pool, "execute_with_failover", side_effect=mock_op):
            with patch("time.sleep", return_value=None):
                result = provider._execute_with_retry(lambda k: mock_op())
                assert result == "Success Response"
                assert mock_op.call_count == 2

    @patch("google.genai.Client")
    def test_chat_with_tools_wrapper(self, mock_client_cls, provider):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_part = MagicMock()
        mock_part.function_call.name = "calculate_sum"
        mock_part.function_call.args = {"a": 10, "b": 20}

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.text = "Calling calculation tool"
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        messages = [{"role": "user", "content": "Sum 10 and 20"}]
        tools = [{"type": "function", "function": {"name": "calculate_sum", "description": "Add numbers", "parameters": {}}}]

        with patch.object(provider._key_pool, "execute_with_failover", side_effect=lambda op, service: op("mock_key")):
            resp = provider.chat_with_tools(messages, tools)

        assert resp.choices[0].message.content == "Calling calculation tool"
        assert resp.choices[0].message.tool_calls[0].function.name == "calculate_sum"
        assert resp.choices[0].message.tool_calls[0].function.arguments == '{"a": 10, "b": 20}'


class TestProviderManagerRoutingRegression:
    """Regression tests verifying Groq provider routing is unaffected by Gemini addition."""

    def test_provider_manager_routing(self):
        pm = ProviderManager(default_provider="groq")
        mock_groq = MagicMock()
        mock_gemini = MagicMock()

        pm.register("groq", mock_groq)
        pm.register("gemini", mock_gemini)

        # 1. Default routing resolves to Groq
        assert pm.get() == mock_groq
        assert pm.get("groq") == mock_groq

        # 2. Direct Gemini routing
        assert pm.get("gemini") == mock_gemini

        # 3. Role-based routing: code_generation -> gemini
        assert pm.get("code_generation") == mock_gemini

        # 4. Unregistered provider raises ProviderNotFoundError
        with pytest.raises(ProviderNotFoundError):
            pm.get("unregistered_provider")

    def test_chat_with_fallback_degrades_to_groq_on_503_service_unavailable(self):
        from core.backends.adapters.antigravity_backend import CodingBackendAdapter
        from ai.models import ChatRequest, ChatMessage, ProviderResponse

        adapter = CodingBackendAdapter()
        mock_pm = MagicMock()
        mock_pm.chat.side_effect = [
            ProviderError("503 Server Error: High demand on gemini-3.7-flash"),
            ProviderResponse(text="Fallback Groq response on 503", provider="groq", model="groq-model")
        ]

        req = ChatRequest(messages=[ChatMessage(role="user", content="Fix bug")])
        res = adapter._chat_with_fallback(mock_pm, req)

        assert res.text == "Fallback Groq response on 503"
        assert res.provider == "groq"
        assert mock_pm.chat.call_count == 2
        mock_pm.chat.assert_any_call(req, provider="code_generation")
        mock_pm.chat.assert_any_call(req, provider="groq")

    def test_chat_with_fallback_degrades_to_groq_on_quota_exhaustion(self):
        from core.backends.adapters.antigravity_backend import CodingBackendAdapter
        from ai.models import ChatRequest, ChatMessage, ProviderResponse

        adapter = CodingBackendAdapter()
        mock_pm = MagicMock()
        mock_pm.chat.side_effect = [
            GeminiQuotaExhaustedError("429 Rate limit reached"),
            ProviderResponse(text="Fallback Groq response", provider="groq", model="groq-model")
        ]

        req = ChatRequest(messages=[ChatMessage(role="user", content="Fix bug")])
        res = adapter._chat_with_fallback(mock_pm, req)

        assert res.text == "Fallback Groq response"
        assert res.provider == "groq"
        assert mock_pm.chat.call_count == 2
        mock_pm.chat.assert_any_call(req, provider="code_generation")
        mock_pm.chat.assert_any_call(req, provider="groq")
