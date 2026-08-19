"""
ExpertDomainRouter (M25 Phase 1)
Location: src/experts/router.py

Deterministic routing and confidence-ranked selection of specialized domain experts:
Software Engineering, Network Engineering, Cybersecurity, Financial Analysis.

Architectural Invariants:
1. Explainable Routing: Every routing decision includes matched confidence scores and rationale.
2. Safe Fallback: If no expert matches with >= 0.50 confidence, falls back gracefully to general planners.
3. Thread-Safe: Singleton registry with safe concurrent evaluation.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from .base_expert import DomainExpertPlanner
from .models import DomainAssessment

logger = logging.getLogger(__name__)


class ExpertDomainRouter:
    """
    Central router that identifies and delegates goals to the most qualified DomainExpertPlanner.
    """

    _instance: ExpertDomainRouter | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, register_defaults: bool = True) -> None:
        self._experts: dict[str, DomainExpertPlanner] = {}
        self._router_lock = threading.RLock()
        if register_defaults:
            self._register_default_experts()

    def _register_default_experts(self) -> None:
        try:
            from .software.planner import SoftwareEngineeringExpertPlanner
            self.register_expert(SoftwareEngineeringExpertPlanner())
        except Exception as e:
            logger.warning(f"[ExpertDomainRouter] Failed to register default SoftwareEngineeringExpertPlanner: {e}")

        try:
            from .network.planner import NetworkEngineeringExpertPlanner
            self.register_expert(NetworkEngineeringExpertPlanner())
        except Exception as e:
            logger.warning(f"[ExpertDomainRouter] Failed to register default NetworkEngineeringExpertPlanner: {e}")

        try:
            from .security.planner import CybersecurityExpertPlanner
            self.register_expert(CybersecurityExpertPlanner())
        except Exception as e:
            logger.warning(f"[ExpertDomainRouter] Failed to register default CybersecurityExpertPlanner: {e}")

        try:
            from .finance.planner import FinancialAnalysisExpertPlanner
            self.register_expert(FinancialAnalysisExpertPlanner())
        except Exception as e:
            logger.warning(f"[ExpertDomainRouter] Failed to register default FinancialAnalysisExpertPlanner: {e}")

    @classmethod
    def get_instance(cls) -> "ExpertDomainRouter":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(register_defaults=True)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def register_expert(self, expert: DomainExpertPlanner) -> None:
        """Register a specialized domain expert planner."""
        with self._router_lock:
            domain_key = expert.domain.lower().strip()
            self._experts[domain_key] = expert
            logger.info(f"[ExpertDomainRouter] Registered expert for domain '{domain_key}'.")

    def unregister_expert(self, domain: str) -> None:
        """Unregister an expert planner."""
        with self._router_lock:
            domain_key = domain.lower().strip()
            if domain_key in self._experts:
                del self._experts[domain_key]
                logger.info(f"[ExpertDomainRouter] Unregistered expert for domain '{domain_key}'.")

    def list_experts(self) -> list[str]:
        """List registered domain keys."""
        with self._router_lock:
            return list(self._experts.keys())

    def get_expert(self, domain: str) -> DomainExpertPlanner | None:
        """Retrieve a registered expert by domain name."""
        with self._router_lock:
            return self._experts.get(domain.lower().strip())

    async def route(
        self,
        goal_text: str,
        context: dict[str, Any] | None = None,
        min_confidence: float = 0.50,
    ) -> tuple[DomainExpertPlanner | None, DomainAssessment | None, str]:
        """
        Evaluates registered domain experts against the goal and selects the highest confidence match.

        Returns:
            (selected_expert, domain_assessment, rationale)
        """
        with self._router_lock:
            experts_snapshot = list(self._experts.values())

        if not experts_snapshot:
            return None, None, "No domain experts registered in ExpertDomainRouter."

        candidates: list[tuple[DomainExpertPlanner, float, str]] = []

        for expert in experts_snapshot:
            try:
                can_handle, conf, rationale = expert.can_handle(goal_text, context=context)
                if can_handle and conf >= min_confidence:
                    candidates.append((expert, conf, rationale))
            except Exception as e:
                logger.warning(f"[ExpertDomainRouter] Error evaluating expert '{expert.domain}': {e}")

        if not candidates:
            return None, None, f"No domain expert matched goal with >= {min_confidence:.2f} confidence."

        # Rank candidates by confidence descending
        candidates.sort(key=lambda item: item[1], reverse=True)
        top_expert, top_conf, top_rationale = candidates[0]

        logger.info(
            f"[ExpertDomainRouter] Routed goal to '{top_expert.domain}' "
            f"(Confidence: {top_conf:.2f}, Rationale: {top_rationale})"
        )

        try:
            assessment = await top_expert.assess(goal_text, context=context)
            return top_expert, assessment, top_rationale
        except Exception as e:
            logger.error(f"[ExpertDomainRouter] Failed to generate assessment from expert '{top_expert.domain}': {e}")
            return top_expert, None, f"Expert '{top_expert.domain}' selected but assessment failed: {e}"
