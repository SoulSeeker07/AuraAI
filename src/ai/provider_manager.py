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
            "diagram": "gemini",
            "svg": "gemini",
            "art": "gemini",
            "sketch": "gemini",
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

    def resolve_provider(
        self, request: ChatRequest | None = None, provider: str | None = None
    ) -> str:
        if provider:
            return self.role_mappings.get(provider, provider)

        # Dynamic routing if provider is not explicitly passed:
        if request and request.messages:
            # 1. Token threshold: >= 5000 tokens goes directly to Gemini
            total_chars = sum(len(str(getattr(m, "content", "") or "")) for m in request.messages)
            est_tokens = total_chars // 4
            if est_tokens >= 5000 and "gemini" in self.providers:
                return "gemini"

            # 2. Inspect latest user message for specialized domain keywords
            user_content = ""
            for m in reversed(request.messages):
                role = getattr(m, "role", "")
                if role == "user":
                    user_content = str(getattr(m, "content", "") or "").lower()
                    break

            if user_content and "gemini" in self.providers:
                diagram_kw = (
                    "flowchart", "diagram", "schematic", "mermaid", "system architecture",
                    "sequence diagram", "state machine", "process map", "entity relationship",
                    "er diagram", "data flow diagram", "architecture of"
                )
                svg_kw = (
                    "svg", "mockup", "wireframe", "ui design", "screen design", "layout design",
                    "screen layout", "interface screen", "visual layout", "draw an svg",
                    "svg graphic", "svg illustration"
                )
                code_kw = (
                    "frontend", "backend", "fullstack", "react", "vue", "angular", "svelte",
                    "nextjs", "next.js", "html", "css", "tailwind", "javascript", "typescript",
                    "fastapi", "flask", "django", "express", "node.js", "nodejs", "api endpoint",
                    "rest api", "graphql", "database schema", "write code", "write a function",
                    "write a script", "refactor code", "refactor this", "code for", "implement class",
                    "coding"
                )
                if any(k in user_content for k in diagram_kw + svg_kw + code_kw):
                    return "gemini"

        return self.default_provider

    def chat(
        self, request: ChatRequest, provider: str | None = None
    ) -> ProviderResponse:
        resolved = self.resolve_provider(request, provider)
        return self.get(resolved).chat(request)

    def stream(
        self, request: ChatRequest, provider: str | None = None
    ) -> Iterable[str]:
        resolved = self.resolve_provider(request, provider)
        return self.get(resolved).stream(request)

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
        target = provider
        if target is None:
            total_chars = sum(len(str(m.get("content", ""))) for m in messages if isinstance(m, dict))
            est_tokens = total_chars // 4
            if est_tokens >= 5000 and "gemini" in self.providers:
                target = "gemini"
        p = self.get(target)
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
