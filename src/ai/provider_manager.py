from __future__ import annotations

from collections.abc import Iterable

from ai.exceptions import ProviderNotFoundError
from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse, VisionRequest
from ai.provider import Provider


class ProviderManager:
    def __init__(self, default_provider: str = "groq"):
        self.providers: dict[str, Provider] = {}
        self.default_provider = default_provider

    def register(self, name: str, provider: Provider) -> None:
        self.providers[name] = provider

    def get(self, name: str | None = None) -> Provider:
        provider_name = name or self.default_provider
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ProviderNotFoundError(
                f"AI provider is not registered: {provider_name}"
            )
        return provider

    def set_default(self, name: str) -> None:
        self.get(name)
        self.default_provider = name

    def chat(
        self, request: ChatRequest, provider: str | None = None
    ) -> ProviderResponse:
        return self.get(provider).chat(request)

    def stream(
        self, request: ChatRequest, provider: str | None = None
    ) -> Iterable[str]:
        return self.get(provider).stream(request)

    def vision(
        self, request: VisionRequest, provider: str | None = None
    ) -> ProviderResponse:
        return self.get(provider).vision(request)

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.0,
        provider: str | None = None,
    ) -> Any:
        p = self.get(provider)
        if hasattr(p, "chat_with_tools"):
            return p.chat_with_tools(messages, tools, model=model, temperature=temperature)
        raise NotImplementedError(f"Provider {p} does not support chat_with_tools")

    def capabilities(self, provider: str | None = None) -> ProviderCapabilities:
        return self.get(provider).capabilities
