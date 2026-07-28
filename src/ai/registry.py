from __future__ import annotations

from ai.groq_provider import GroqProvider
from ai.provider_manager import ProviderManager


def build_provider_manager(env: dict[str, str], default_provider: str = "groq") -> ProviderManager:
    manager = ProviderManager(default_provider=default_provider)
    manager.register(
        "groq",
        GroqProvider(
            api_key=env.get("GROQ_API_KEY", ""),
            default_model=env.get("AURA_GROQ_MODEL", "openai/gpt-oss-120b"),
            vision_model=env.get("AURA_GROQ_VISION_MODEL", "qwen/qwen3.6-27b"),
        ),
    )
    return manager
