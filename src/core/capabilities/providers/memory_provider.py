"""
Memory Capability Provider
==========================
Location: src/core/capabilities/providers/memory_provider.py

Provides capability descriptors for the Cognitive Memory subsystem (Episodic & Semantic).
"""

from __future__ import annotations

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


class MemoryCapabilityProvider(ICapabilityProvider):
    """Provider for cognitive memory storage, recall, and search capabilities."""

    DOMAIN = "memory"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = self._build_capabilities()

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def _build_capabilities(self) -> dict[str, Capability]:
        caps = [
            Capability(
                name="memory.store",
                domain=self.DOMAIN,
                description="Persist user preferences, facts, or decision memories into cognitive stores.",
                category="storage",
                input_schema={
                    "type": "object",
                    "required": ["content"],
                    "properties": {
                        "content": {"type": "string"},
                        "memory_type": {"type": "string", "default": "semantic"},
                        "importance": {"type": "number", "default": 0.5},
                    },
                },
                output_schema={"type": "object", "properties": {"memory_id": {"type": "string"}}},
                risk_level=ActionRisk.LOW,
                permissions=["memory:write"],
                execution_backend="memory_engine",
                is_live=True,
                availability="online",
                tags=["memory", "store", "cognitive"],
            ),
            Capability(
                name="memory.recall",
                domain=self.DOMAIN,
                description="Recall relevant context, past decisions, or user facts via vector semantic search.",
                category="retrieval",
                input_schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 5},
                    },
                },
                output_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
                risk_level=ActionRisk.LOW,
                permissions=["memory:read"],
                execution_backend="memory_engine",
                is_live=True,
                availability="online",
                tags=["memory", "recall", "semantic_search"],
            ),
            Capability(
                name="memory.search",
                domain=self.DOMAIN,
                description="Perform keyword and hybrid semantic search across historical memory entries.",
                category="search",
                input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"results": {"type": "array"}}},
                risk_level=ActionRisk.LOW,
                permissions=["memory:read"],
                execution_backend="memory_engine",
                is_live=True,
                availability="online",
                tags=["memory", "search"],
            ),
        ]
        return {cap.name: cap for cap in caps}

    def list_capabilities(self) -> list[Capability]:
        return list(self._capabilities.values())

    def get_capability(self, name: str) -> Capability | None:
        return self._capabilities.get(name)
