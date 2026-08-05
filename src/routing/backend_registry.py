"""
Backend Registry & Provider Selection (Milestone 16 - Phase 3)

Decouples role planners from execution engines. Backends are registered, scored,
and selected dynamically based on required capabilities, latency, cost, and health.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BackendMetadata:
    """Metadata describing a backend provider's status and characteristics."""

    name: str
    capability: str  # e.g., "coding", "research", "desktop", "browser"
    latency_ms: int = 100
    cost_rating: str = "low"  # free, low, medium, high
    health_status: str = "healthy"  # healthy, degraded, unhealthy
    score: float = 0.95
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseBackend(ABC):
    """Abstract base class for all execution backends."""

    def __init__(self, metadata: BackendMetadata):
        self.metadata = metadata

    @abstractmethod
    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute a planned subtask."""
        pass


class NativeDesktopBackend(BaseBackend):
    """Execution backend for native desktop engine operations."""

    def __init__(self):
        super().__init__(
            BackendMetadata(
                name="Native Desktop Engine",
                capability="desktop",
                latency_ms=10,
                cost_rating="free",
                health_status="healthy",
                score=1.0,
            )
        )

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        target = plan.get("target", "Application")
        return {
            "status": "success",
            "backend": self.metadata.name,
            "observation": f"Native Desktop Engine executed action '{plan.get('action')}' on target '{target}'.",
        }


class GroqResearchBackend(BaseBackend):
    """Execution backend for fast research & reasoning using Groq API."""

    def __init__(self):
        super().__init__(
            BackendMetadata(
                name="Groq Research Engine",
                capability="research",
                latency_ms=150,
                cost_rating="low",
                health_status="healthy",
                score=0.92,
            )
        )

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        query = plan.get("query", "")
        return {
            "status": "success",
            "backend": self.metadata.name,
            "observation": f"Summarized research for: {query}",
            "citations": ["Python 3.14 Release Notes (PEP 744)", "Python Docs"],
        }


class GeminiResearchBackend(BaseBackend):
    """Execution backend for deep research & multi-modal reasoning using Gemini."""

    def __init__(self):
        super().__init__(
            BackendMetadata(
                name="Gemini Research Engine",
                capability="research",
                latency_ms=300,
                cost_rating="medium",
                health_status="healthy",
                score=0.96,
            )
        )

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        query = plan.get("query", "")
        return {
            "status": "success",
            "backend": self.metadata.name,
            "observation": f"Deep multi-modal research synthesis for: {query}",
            "citations": ["Official Python 3.14 Specs", "GCP Technical Docs"],
        }


class BrowserEngineBackend(BaseBackend):
    """Execution backend for headless browser interaction."""

    def __init__(self):
        super().__init__(
            BackendMetadata(
                name="Headless Browser Engine",
                capability="browser",
                latency_ms=250,
                cost_rating="free",
                health_status="healthy",
                score=0.90,
            )
        )

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "success",
            "backend": self.metadata.name,
            "observation": f"Browser navigated to target '{plan.get('target')}'.",
        }


class BackendRegistry:
    """
    Central registry holding execution backends.
    Evaluates capabilities, score, health, latency, and cost to pick optimal backends.
    """

    def __init__(self):
        self._backends: dict[str, list[BaseBackend]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(NativeDesktopBackend())
        self.register(GroqResearchBackend())
        self.register(GeminiResearchBackend())
        self.register(BrowserEngineBackend())

    def register(self, backend: BaseBackend) -> None:
        """Register a backend executor."""
        cap = backend.metadata.capability.lower()
        if cap not in self._backends:
            self._backends[cap] = []
        self._backends[cap].append(backend)
        logger.info(
            f"Registered backend: {backend.metadata.name} for capability [{cap}] (Score: {backend.metadata.score})"
        )

    def select_backend(self, capability: str) -> BaseBackend:
        """
        Select the best backend for a capability based on score, health, and latency.

        Args:
            capability: Abstract capability required (e.g., 'coding', 'research', 'desktop')

        Returns:
            Optimal BaseBackend instance
        """
        cap = capability.lower()
        candidates = self._backends.get(cap, [])

        healthy_candidates = [
            b for b in candidates if b.metadata.enabled and b.metadata.health_status != "unhealthy"
        ]

        if not healthy_candidates:
            raise RuntimeError(f"No available healthy backend registered for capability: '{capability}'")

        # Sort candidates by combined score (score - latency penalty)
        def score_fn(b: BaseBackend) -> float:
            latency_penalty = b.metadata.latency_ms / 10000.0
            return b.metadata.score - latency_penalty

        selected = max(healthy_candidates, key=score_fn)
        logger.info(
            f"Selected backend '{selected.metadata.name}' for capability '{capability}' (Final score: {score_fn(selected):.3f})"
        )
        return selected
