"""
Research Capability Provider
============================
Location: src/core/capabilities/providers/research_provider.py

Provides capability descriptors for the Research Engine and deep synthesis subsystem.
"""

from __future__ import annotations

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


class ResearchCapabilityProvider(ICapabilityProvider):
    """Provider for web search, source collection, and multi-source evidence synthesis."""

    DOMAIN = "research"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = self._build_capabilities()

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def _build_capabilities(self) -> dict[str, Capability]:
        caps = [
            Capability(
                name="research.search",
                domain=self.DOMAIN,
                description="Query web sources and extract ranked references for factual research.",
                category="search",
                input_schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {"type": "array"},
                        "count": {"type": "integer"},
                        "query": {"type": "string"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["network:search"],
                execution_backend="research_engine",
                is_live=True,
                availability="online",
                requires=[],
                verifies=[],
                tags=["research", "search", "web"],
            ),
            Capability(
                name="research.synthesize",
                domain=self.DOMAIN,
                description="Synthesize multi-source research evidence into structured answers with citations.",
                category="synthesis",
                input_schema={
                    "type": "object",
                    "required": ["topic", "sources"],
                    "properties": {
                        "topic": {"type": "string"},
                        "sources": {"type": "array"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "citations": {"type": "array"},
                        "confidence_score": {"type": "number"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["ai:generate"],
                execution_backend="research_engine",
                is_live=True,
                availability="online",
                requires=["research.search"],
                verifies=[],
                tags=["research", "synthesis", "citations"],
            ),
            Capability(
                name="research.deep_query",
                domain=self.DOMAIN,
                description="Multi-round autonomous deep research loop exploring sub-questions and cross-verifying claims.",
                category="deep_research",
                input_schema={
                    "type": "object",
                    "required": ["question"],
                    "properties": {
                        "question": {"type": "string"},
                        "rounds": {"type": "integer", "default": 3},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "comprehensive_report": {"type": "string"},
                        "confidence_score": {"type": "number"},
                        "citations": {"type": "array"},
                    },
                },
                risk_level=ActionRisk.MEDIUM,
                permissions=["network:search", "ai:generate"],
                execution_backend="research_engine",
                is_live=True,
                availability="online",
                requires=["research.search", "research.synthesize"],
                verifies=[],
                tags=["research", "deep_research", "investigation"],
            ),
        ]
        return {cap.name: cap for cap in caps}

    def list_capabilities(self) -> list[Capability]:
        return list(self._capabilities.values())

    def get_capability(self, name: str) -> Capability | None:
        return self._capabilities.get(name)
