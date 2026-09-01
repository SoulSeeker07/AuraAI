from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Iterable, Optional

from ai.exceptions import (
    GeminiQuotaExhaustedError,
    KeyPoolExhaustedError,
    ProviderError,
    ProviderNotConfiguredError,
)
from ai.key_pool import KeyPool
from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse, VisionRequest
from ai.provider import Provider

logger = logging.getLogger(__name__)


class GeminiFunctionCallWrapper:
    def __init__(self, name: str, args: dict):
        self.name = name
        self.arguments = json.dumps(args) if isinstance(args, dict) else str(args)


class GeminiToolCallWrapper:
    def __init__(self, call_id: str, name: str, args: dict):
        self.id = call_id
        self.type = "function"
        self.function = GeminiFunctionCallWrapper(name, args)


class GeminiMessageWrapper:
    def __init__(self, content: str | None, tool_calls: list[GeminiToolCallWrapper] | None = None):
        self.content = content
        self.tool_calls = tool_calls or None


class GeminiChoiceWrapper:
    def __init__(self, message: GeminiMessageWrapper):
        self.message = message


class GeminiResponseWrapper:
    def __init__(self, choices: list[GeminiChoiceWrapper]):
        self.choices = choices


class GeminiProvider(Provider):
    """Gemini 3 Flash LLM Provider for Code-Generation and Code-Review tasks."""

    def __init__(
        self,
        api_key: str = "",
        default_model: str = "gemini-3.6-flash",
    ):
        self.api_key = api_key
        self.default_model = default_model
        self._key_pool = KeyPool.get_instance()
        self._clients: dict[str, Any] = {}
        self.capabilities = ProviderCapabilities(
            name="gemini",
            default_model=default_model,
            supports_streaming=True,
            supports_vision=False,
            supports_tools=True,
            supports_images=False,
            token_limit=1048576,
        )

    def _get_client(self, api_key: Optional[str] = None):
        key = api_key or self.api_key
        if not key:
            try:
                key = self._key_pool.get_active_key("gemini")
            except RuntimeError as exc:
                raise ProviderNotConfiguredError("GEMINI_API_KEY is not configured.") from exc

        if key in self._clients:
            return self._clients[key]

        try:
            from google import genai
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "The google-genai package is not installed. Please install google-genai."
            ) from exc

        client = genai.Client(api_key=key)
        self._clients[key] = client
        return client

    def _redact_api_key(self, text: str) -> str:
        if not text:
            return ""
        keys_to_redact = self._key_pool.get_all_keys("gemini")
        if self.api_key:
            keys_to_redact.append(self.api_key)
        clean_text = text
        for k in keys_to_redact:
            if k and k in clean_text:
                clean_text = clean_text.replace(k, f"{k[:4]}...[REDACTED]")
        clean_text = re.sub(r"key=[A-Za-z0-9_\-]+", "key=[REDACTED]", clean_text)
        return clean_text

    def _convert_messages(self, messages: list[dict] | list[Any]) -> tuple[Optional[str], list[Any]]:
        from google.genai import types
        system_instruction: Optional[str] = None
        contents: list[Any] = []

        for m in messages:
            if hasattr(m, "role") and hasattr(m, "content"):
                role = m.role
                content = m.content
            elif isinstance(m, dict):
                role = m.get("role")
                content = m.get("content")
            else:
                continue

            if not content:
                continue

            if role == "system":
                system_instruction = str(content)
            elif role in ("user", "human"):
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=str(content))]))
            elif role in ("assistant", "model"):
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=str(content))]))

        return system_instruction, contents

    def chat(self, request: ChatRequest) -> ProviderResponse:
        model = request.model or self.default_model
        start_time = time.time()

        def _do_chat(key: str):
            client = self._get_client(key)
            from google.genai import types

            sys_inst, contents = self._convert_messages(request.messages)
            config = types.GenerateContentConfig(
                system_instruction=sys_inst,
                temperature=request.temperature or 0.2,
            )
            if request.max_tokens:
                config.max_output_tokens = request.max_tokens

            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

        try:
            response = self._execute_with_retry(_do_chat)
            text = response.text or ""
            latency = time.time() - start_time
            logger.info(
                f"[GeminiProvider] chat success | model={model} | latency={latency:.2f}s"
            )
            return ProviderResponse(text=text.strip(), provider="gemini", model=model)
        except Exception as e:
            redacted_err = self._redact_api_key(str(e))
            logger.error(f"[GeminiProvider] chat error | model={model} | error={redacted_err}")
            if "429" in redacted_err or "quota" in redacted_err.lower():
                raise GeminiQuotaExhaustedError(f"Gemini quota exhausted: {redacted_err}") from e
            raise ProviderError(f"Gemini provider chat failed: {redacted_err}") from e

    def stream(self, request: ChatRequest) -> Iterable[str]:
        model = request.model or self.default_model

        def _do_stream(key: str):
            client = self._get_client(key)
            from google.genai import types

            sys_inst, contents = self._convert_messages(request.messages)
            config = types.GenerateContentConfig(
                system_instruction=sys_inst,
                temperature=request.temperature or 0.2,
            )
            if request.max_tokens:
                config.max_output_tokens = request.max_tokens

            return client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )

        try:
            response_stream = self._execute_with_retry(_do_stream)
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            redacted_err = self._redact_api_key(str(e))
            logger.error(f"[GeminiProvider] stream error | model={model} | error={redacted_err}")
            if "429" in redacted_err or "quota" in redacted_err.lower():
                raise GeminiQuotaExhaustedError(f"Gemini quota exhausted: {redacted_err}") from e
            raise ProviderError(f"Gemini provider stream failed: {redacted_err}") from e

    def vision(self, request: VisionRequest) -> ProviderResponse:
        raise NotImplementedError("GeminiProvider does not support vision.")

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> Any:
        chosen_model = model or self.default_model
        start_time = time.time()

        def _do_tools_call(key: str):
            client = self._get_client(key)
            from google.genai import types

            sys_inst, contents = self._convert_messages(messages)

            gemini_tools = []
            for t in tools:
                if callable(t):
                    gemini_tools.append(t)
                elif isinstance(t, dict):
                    fn_dict = t.get("function", t)
                    name = fn_dict.get("name")
                    desc = fn_dict.get("description", "")
                    params = fn_dict.get("parameters", {})
                    fn_decl = types.FunctionDeclaration(
                        name=name,
                        description=desc,
                        parameters=params,
                    )
                    gemini_tools.append(types.Tool(function_declarations=[fn_decl]))

            config = types.GenerateContentConfig(
                system_instruction=sys_inst,
                temperature=temperature,
                tools=gemini_tools if gemini_tools else None,
            )

            return client.models.generate_content(
                model=chosen_model,
                contents=contents,
                config=config,
            )

        try:
            raw_response = self._execute_with_retry(_do_tools_call)
            latency = time.time() - start_time
            logger.info(
                f"[GeminiProvider] chat_with_tools success | model={chosen_model} | latency={latency:.2f}s"
            )

            tool_calls = []
            text_content = raw_response.text or ""

            if raw_response.candidates:
                candidate = raw_response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for idx, part in enumerate(candidate.content.parts):
                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            args = dict(fc.args) if hasattr(fc.args, "items") else (fc.args or {})
                            call_id = f"call_gemini_{idx}_{int(time.time())}"
                            tool_calls.append(GeminiToolCallWrapper(call_id=call_id, name=fc.name, args=args))

            message_wrapper = GeminiMessageWrapper(content=text_content, tool_calls=tool_calls if tool_calls else None)
            choice_wrapper = GeminiChoiceWrapper(message=message_wrapper)
            return GeminiResponseWrapper(choices=[choice_wrapper])

        except (GeminiQuotaExhaustedError, KeyPoolExhaustedError):
            raise
        except Exception as e:
            redacted_err = self._redact_api_key(str(e))
            logger.error(f"[GeminiProvider] chat_with_tools error | model={chosen_model} | error={redacted_err}")
            if "429" in redacted_err or "quota" in redacted_err.lower():
                raise GeminiQuotaExhaustedError(f"Gemini quota exhausted: {redacted_err}") from e
            raise ProviderError(f"Gemini provider chat_with_tools failed: {redacted_err}") from e

    def _execute_with_retry(self, operation: Any, max_retries: int = 2) -> Any:
        last_exception: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return self._key_pool.execute_with_failover(operation, service="gemini")
            except (KeyPoolExhaustedError, GeminiQuotaExhaustedError):
                raise
            except Exception as exc:
                last_exception = exc
                err_str = str(exc).lower()
                status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                if status_code == 429 or "429" in err_str or "quota" in err_str:
                    raise GeminiQuotaExhaustedError(self._redact_api_key(str(exc))) from exc

                if attempt < max_retries - 1:
                    logger.warning(
                        f"[GeminiProvider] Transient error on attempt {attempt + 1}/{max_retries}: "
                        f"{self._redact_api_key(str(exc))}. Retrying in 1s..."
                    )
                    time.sleep(1.0)
                else:
                    raise
        if last_exception:
            raise last_exception
