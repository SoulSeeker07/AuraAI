"""
Knowledge Retrieval Ranking Engine

Handles result ranking with multiple scoring strategies.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import RetrievalResult, SourceType

logger = logging.getLogger(__name__)


@dataclass
class RankConfig:
    """Configuration for ranking strategy."""

    enable_relevance_score: bool = True
    relevance_weight: float = 0.4

    enable_workspace_score: bool = True
    workspace_weight: float = 0.2

    enable_recency_score: bool = True
    recency_weight: float = 0.2

    enable_importance_score: bool = True
    importance_weight: float = 0.2

    workspace_importance_map: dict[str, float] | None = None
    recency_decay_days: int = 30
    importance_decay_days: int = 90


class RankingEngine:
    """
    Engine for ranking retrieval results with multiple strategies.
    """

    def __init__(self, config: RankConfig | None = None):
        """
        Initialize ranking engine.

        Args:
            config: Ranking configuration
        """
        self.config = config or RankConfig()
        self.workspace_importance = self.config.workspace_importance_map or {}

        logger.info("Ranking engine initialized")

    def rank_results(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """
        Rank results using multiple scoring strategies.

        Args:
            results: List of RetrievalResult objects

        Returns:
            Reranked list of RetrievalResult objects
        """
        if not results:
            return results

        logger.info(f"Ranking {len(results)} results")

        # Calculate scores for each result
        for result in results:
            result.final_score = self._calculate_score(result)

        # Sort by final score
        results.sort(key=lambda x: x.final_score, reverse=True)

        # Update ranks
        for rank, result in enumerate(results):
            result.rank = rank + 1

        logger.info(f"Ranking complete. Top result score: {results[0].final_score:.3f}")
        return results

    def _calculate_score(self, result: RetrievalResult) -> float:
        """
        Calculate final score using multiple strategies.

        Args:
            result: RetrievalResult to score

        Returns:
            Final score (0-1)
        """
        score = 0.0
        weights = []

        # Relevance score (from vector/semantic search)
        if self.config.enable_relevance_score:
            relevance = self._calculate_relevance_score(result)
            score += relevance * self.config.relevance_weight
            weights.append(self.config.relevance_weight)

        # Workspace score
        if self.config.enable_workspace_score:
            workspace = self._calculate_workspace_score(result)
            score += workspace * self.config.workspace_weight
            weights.append(self.config.workspace_weight)

        # Recency score
        if self.config.enable_recency_score:
            recency = self._calculate_recency_score(result)
            score += recency * self.config.recency_weight
            weights.append(self.config.recency_weight)

        # Importance score
        if self.config.enable_importance_score:
            importance = self._calculate_importance_score(result)
            score += importance * self.config.importance_weight
            weights.append(self.config.importance_weight)

        # Normalize if we added scores
        if weights:
            score = score / sum(weights)

        return score

    def _calculate_relevance_score(self, result: RetrievalResult) -> float:
        """
        Calculate relevance score from original search score.

        Args:
            result: RetrievalResult to score

        Returns:
            Normalized relevance score (0-1)
        """
        # Relevance is already normalized (0-1 from vector search)
        return result.score

    def _calculate_workspace_score(self, result: RetrievalResult) -> float:
        """
        Calculate workspace importance score.

        Args:
            result: RetrievalResult to score

        Returns:
            Workspace score (0-1)
        """
        if not self.config.enable_workspace_score:
            return 0.0

        project = result.chunk.project

        # Check if project has explicit importance weight
        if project and project in self.workspace_importance:
            return self.workspace_importance[project]

        # Default weights by source type
        source_type = result.chunk.source_type.value
        source_weights = {
            SourceType.PYTHON.value: 1.0,
            SourceType.MARKDOWN.value: 0.8,
            SourceType.PDF.value: 0.7,
            SourceType.HTML.value: 0.6,
            SourceType.JSON.value: 0.5,
            SourceType.DOCX.value: 0.5,
            SourceType.PPTX.value: 0.4,
            SourceType.CSV.value: 0.4,
        }

        return source_weights.get(source_type, 0.5)

    def _calculate_recency_score(self, result: RetrievalResult) -> float:
        """
        Calculate recency score based on document modification date.

        Args:
            result: RetrievalResult to score

        Returns:
            Recency score (0-1)
        """
        if not self.config.enable_recency_score:
            return 0.0

        # Get modification date
        modified_at = result.chunk.updated_at or result.chunk.created_at

        if not modified_at:
            return 0.5  # Default to neutral if no date

        # Calculate days since modification
        days_ago = (datetime.now() - modified_at).days

        # Exponential decay: score = exp(-days / decay_days)
        decay = self.config.recency_decay_days
        score = math.exp(-days_ago / decay)

        return max(0.0, min(1.0, score))

    def _calculate_importance_score(self, result: RetrievalResult) -> float:
        """
        Calculate importance score based on chunk type and tags.

        Args:
            result: RetrievalResult to score

        Returns:
            Importance score (0-1)
        """
        if not self.config.enable_importance_score:
            return 0.0

        # Base importance by chunk type
        chunk_type = result.chunk.chunk_type.value
        type_importance = {
            "SECTION": 0.5,
            "FUNCTION": 0.8,
            "CLASS": 0.9,
            "MODULE": 0.85,
            "DOCUMENTATION": 0.7,
            "EXAMPLE": 0.6,
            "CONCEPT": 0.7,
            "NOTICE": 0.4,
            "WELCOME": 0.3,
            "ERROR": 0.8,
        }

        score = type_importance.get(chunk_type, 0.5)

        # Boost by tags
        for tag in result.chunk.tags:
            tag_importance = {
                "important": 0.2,
                "critical": 0.3,
                "reference": 0.15,
                "archived": -0.2,
                "deprecated": -0.15,
            }

            if tag in tag_importance:
                score += tag_importance[tag]

        # Clamp to 0-1
        return max(0.0, min(1.0, score))

    def rank_by_workspace(
        self,
        results: list[RetrievalResult],
        project_weights: dict[str, float] | None = None,
    ) -> list[RetrievalResult]:
        """
        Rank results by workspace (project) importance.

        Args:
            results: List of RetrievalResult objects
            project_weights: Optional project weights mapping

        Returns:
            Reranked list of RetrievalResult objects
        """
        # Update workspace importance if provided
        if project_weights:
            self.workspace_importance = project_weights

        # Apply ranking
        return self.rank_results(results)

    def rank_by_recency(
        self, results: list[RetrievalResult], recency_decay_days: int = 30
    ) -> list[RetrievalResult]:
        """
        Rank results by recency.

        Args:
            results: List of RetrievalResult objects
            recency_decay_days: Days for half-life decay

        Returns:
            Reranked list of RetrievalResult objects
        """
        self.config.recency_decay_days = recency_decay_days

        # Apply ranking
        return self.rank_results(results)

    def rank_by_importance(
        self, results: list[RetrievalResult]
    ) -> list[RetrievalResult]:
        """
        Rank results by importance (chunk type and tags).

        Args:
            results: List of RetrievalResult objects

        Returns:
            Reranked list of RetrievalResult objects
        """
        return self.rank_results(results)

    def get_ranking_stats(self, results: list[RetrievalResult]) -> dict[str, Any]:
        """
        Get statistics about ranking.

        Args:
            results: List of RetrievalResult objects

        Returns:
            Dictionary with ranking statistics
        """
        if not results:
            return {"total_results": 0, "average_final_score": 0.0}

        scores = [r.final_score for r in results]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        # Score distribution
        distribution = {}
        for score in scores:
            bucket = int(score * 10) * 0.1
            distribution[bucket] = distribution.get(bucket, 0) + 1

        return {
            "total_results": len(results),
            "average_final_score": avg_score,
            "min_score": min_score,
            "max_score": max_score,
            "score_distribution": distribution,
        }

    def set_workspace_importance(self, project_weights: dict[str, float]):
        """
        Set workspace (project) importance weights.

        Args:
            project_weights: Mapping of project names to weights
        """
        self.workspace_importance = project_weights
        logger.info(f"Updated workspace importance weights: {project_weights}")

    def reset_workspace_importance(self):
        """Reset workspace importance weights to defaults."""
        self.workspace_importance = self.config.workspace_importance_map or {}
        logger.info("Reset workspace importance weights")

    def get_workspace_importance(self) -> dict[str, float]:
        """
        Get current workspace importance weights.

        Returns:
            Dictionary of project weights
        """
        return self.workspace_importance.copy()

    def set_recency_decay(self, decay_days: int):
        """
        Set recency decay period.

        Args:
            decay_days: Days for half-life decay
        """
        self.config.recency_decay_days = decay_days
        logger.info(f"Set recency decay to {decay_days} days")

    def get_scores_by_component(
        self, results: list[RetrievalResult]
    ) -> dict[str, list[float]]:
        """
        Get scores broken down by component.

        Args:
            results: List of RetrievalResult objects

        Returns:
            Dictionary with scores for each component
        """
        component_scores = {
            "relevance": [],
            "workspace": [],
            "recency": [],
            "importance": [],
        }

        for result in results:
            # Get individual components
            relevance = self._calculate_relevance_score(result)
            workspace = self._calculate_workspace_score(result)
            recency = self._calculate_recency_score(result)
            importance = self._calculate_importance_score(result)

            component_scores["relevance"].append(relevance)
            component_scores["workspace"].append(workspace)
            component_scores["recency"].append(recency)
            component_scores["importance"].append(importance)

        return component_scores

    def filter_by_min_score(
        self, results: list[RetrievalResult], min_score: float = 0.5
    ) -> list[RetrievalResult]:
        """
        Filter results below minimum score.

        Args:
            results: List of RetrievalResult objects
            min_score: Minimum score threshold

        Returns:
            Filtered list of results
        """
        filtered = [r for r in results if r.final_score >= min_score]
        logger.info(
            f"Filtered {len(results) - len(filtered)} results below score {min_score}"
        )
        return filtered

    def select_top_results(
        self, results: list[RetrievalResult], n: int = 5
    ) -> list[RetrievalResult]:
        """
        Select top N results.

        Args:
            results: List of RetrievalResult objects
            n: Number of results to select

        Returns:
            Top N results
        """
        return results[:n]
