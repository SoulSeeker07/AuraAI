from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from ai.exceptions import ProviderNotFoundError
from ai.models import ChatRequest, ProviderCapabilities, ProviderResponse, VisionRequest
from ai.provider import Provider


class ProviderManager:
    def __init__(self, default_provider: str = "groq"):
        self.providers: dict[str, Provider] = {}
        self.default_provider = default_provider
        self.role_mappings: dict[str, str] = {
            "code_generation": "gemini",
        }

    def register(self, name: str, provider: Provider) -> None:
        self.providers[name] = provider

    def register_role(self, role: str, provider_name: str) -> None:
        self.role_mappings[role] = provider_name

    def get(self, name: str | None = None) -> Provider:
        target_name = name or self.default_provider
        # Resolve role mapping if target_name matches a registered role
        provider_name = self.role_mappings.get(target_name, target_name)
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
        tool_choice: str | dict = "auto",
        timeout: float | None = None,
        provider: str | None = None,
    ) -> Any:
        p = self.get(provider)
        if hasattr(p, "chat_with_tools"):
            return p.chat_with_tools(
                messages,
                tools,
                model=model,
                temperature=temperature,
                tool_choice=tool_choice,
                timeout=timeout,
            )
        raise NotImplementedError(f"Provider {p} does not support chat_with_tools")

    def capabilities(self, provider: str | None = None) -> ProviderCapabilities:
        return self.get(provider).capabilities
