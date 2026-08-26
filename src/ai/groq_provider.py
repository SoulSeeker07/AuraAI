from __future__ import annotations

import base64
import logging
import re
from typing import Optional

from ai.exceptions import ProviderNotConfiguredError
from ai.key_pool import KeyPool
from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse, VisionRequest
from ai.provider import Provider

logger = logging.getLogger(__name__)


class GroqProvider(Provider):
    def __init__(
        self,
        api_key: str = "",
        default_model: str = "openai/gpt-oss-120b",
        vision_model: str = "qwen/qwen3.6-27b",
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.vision_model = vision_model
        self._key_pool = KeyPool.get_instance()
        self._clients: dict[str, Any] = {}
        self.capabilities = ProviderCapabilities(
            name="groq",
            default_model=default_model,
            supports_streaming=True,
            supports_vision=True,
            supports_tools=False,
            supports_images=True,
            token_limit=131072,
        )

    def chat(self, request: ChatRequest) -> ProviderResponse:
        text = "".join(self.stream(request))
        model = request.model or self.default_model
        return ProviderResponse(text=text.strip(), provider="groq", model=model)

    def stream(self, request: ChatRequest):
        model = request.model or self.default_model
        if "8b-instant" in model or "llama-3.1" in model:
            model = self.default_model

        def _do_stream(key: str):
            client = self._get_client(key)
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": message.role, "content": message.content}
                        for message in request.messages
                    ],
                    stream=True,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=1,
                )
                return response
            except Exception as e:
                # If requested model is not found or unsupported, fallback to default primary model
                if model != self.default_model:
                    return client.chat.completions.create(
                        model=self.default_model,
                        messages=[
                            {"role": message.role, "content": message.content}
                            for message in request.messages
                        ],
                        stream=True,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        top_p=1,
                    )
                raise

        # Execute stream with automatic key failover
        try:
            response = self._key_pool.execute_with_failover(_do_stream, service="groq")
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except RuntimeError:
            # If KeyPool has no keys or failed over completely, fall back to direct api_key if provided
            if self.api_key:
                client = self._get_client(self.api_key)
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": message.role, "content": message.content}
                        for message in request.messages
                    ],
                    stream=True,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=1,
                )
                for chunk in response:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            else:
                raise

    def vision(self, request: VisionRequest) -> ProviderResponse:
        model = request.model or self.vision_model
        encoded = base64.b64encode(request.image.path.read_bytes()).decode("utf-8")
        image_url = f"data:{request.image.mime_type};base64,{encoded}"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are AuraAI desktop assistant. Directly describe what is visible on the screen clearly and concisely for the user. "
                    "Mention active applications, editor files, open code, terminal commands, or UI windows. "
                    "Do not output internal chain-of-thought analysis, planning steps, or 'The user wants me to'."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ]

        def _do_vision(key: str):
            client = self._get_client(key)
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_completion_tokens=request.max_tokens,
                top_p=1,
                stream=False,
            )

        response = self._key_pool.execute_with_failover(_do_vision, service="groq")
        text = response.choices[0].message.content or ""
        # Clean thinking tags if present
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
        if "<think>" in text:
            parts = text.split("<think>")
            text = parts[0].strip() if parts[0].strip() else (parts[-1].split("</think>")[-1].strip() if "</think>" in text else "")
        return ProviderResponse(text=text.strip(), provider="groq", model=model)

    def _get_client(self, api_key: Optional[str] = None):
        key = api_key or self.api_key
        if not key:
            try:
                key = self._key_pool.get_active_key("groq")
            except RuntimeError as exc:
                raise ProviderNotConfiguredError("GROQ_API_KEY is not configured.") from exc

        if key in self._clients:
            return self._clients[key]

        try:
            from groq import Groq
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "The groq package is not installed."
            ) from exc

        client = Groq(api_key=key)
        self._clients[key] = client
        return client
