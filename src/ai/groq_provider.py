from __future__ import annotations

import base64

from ai.exceptions import ProviderNotConfiguredError
from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse, VisionRequest
from ai.provider import Provider


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
        self._client = None
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
        client = self._get_client()
        model = request.model or self.default_model
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": message.role, "content": message.content} for message in request.messages],
            stream=True,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=1,
        )

        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def vision(self, request: VisionRequest) -> ProviderResponse:
        client = self._get_client()
        model = request.model or self.vision_model
        encoded = base64.b64encode(request.image.path.read_bytes()).decode("utf-8")
        image_url = f"data:{request.image.mime_type};base64,{encoded}"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            temperature=request.temperature,
            max_completion_tokens=request.max_tokens,
            top_p=1,
            stream=False,
        )
        text = response.choices[0].message.content or ""
        return ProviderResponse(text=text.strip(), provider="groq", model=model)

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise ProviderNotConfiguredError("GROQ_API_KEY is not configured.")

        try:
            from groq import Groq
        except ImportError as exc:
            raise ProviderNotConfiguredError("The groq package is not installed.") from exc

        self._client = Groq(api_key=self.api_key)
        return self._client
