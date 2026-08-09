"""
Base Expert System Contract
Location: src/experts/base_expert.py

Abstract base class for all Professional Expert Systems.
Rule: Experts analyze and generate DomainActionProposals. They NEVER execute physical OS/browser actions directly.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from .models import DomainType, ExpertAnalysisResult

logger = logging.getLogger(__name__)


class BaseExpertSystem(ABC):
    """
    Abstract contract for Professional Expert Systems.
    """

    @property
    @abstractmethod
    def domain(self) -> DomainType:
        """The domain type handled by this expert system."""
        ...

    @property
    def name(self) -> str:
        """Name identifier of the expert system."""
        return self.domain.value

    @abstractmethod
    def _perform_analysis(
        self, query: str, context: dict[str, Any]
    ) -> ExpertAnalysisResult:
        """Domain-specific analysis logic implemented by subclasses."""
        ...

    def analyze(
        self, query: str, context: dict[str, Any] | None = None
    ) -> ExpertAnalysisResult:
        """
        Public analysis entry point with error isolation.
        Catches any domain expert exception and wraps it in a failed ExpertAnalysisResult
        so expert failures never crash the Aura runtime.
        """
        ctx = context or {}
        logger.info(f"[{self.__class__.__name__}] Analyzing query in domain '{self.domain.value}': '{query}'")

        try:
            result = self._perform_analysis(query, ctx)
            logger.info(
                f"[{self.__class__.__name__}] Analysis complete: success={result.success}, "
                f"findings={len(result.findings)}, proposals={len(result.proposals)}"
            )
            return result
        except Exception as exc:
            logger.error(f"[{self.__class__.__name__}] Analysis failed with exception: {exc}", exc_info=True)
            return ExpertAnalysisResult(
                domain=self.domain,
                success=False,
                summary=f"Analysis in domain '{self.domain.value}' failed due to error: {exc}",
                error=f"{type(exc).__name__}: {exc}",
            )
