"""
Engineering Dashboard

Provides an overview of repository health and metrics.

This module enables Aura to:
- Show repository health
- Display architecture overview
- Show open issues
- Display quality metrics
- Show TODOs and complexity
- Show dependency graph
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EngineeringDashboard:
    """
    Provides an overview of repository health and metrics.

    Usage:
        dashboard = EngineeringDashboard(
            repository_path="/path/to/repo",
            repository_manager=repo_manager,
            quality_engine=quality_engine,
            symbol_graph=symbol_graph,
            dependency_graph=dependency_graph
        )

        # Get repository analysis
        analysis = dashboard.get_repository_analysis()

        # Get quality report
        quality = dashboard.get_quality_report()

        # Get architecture overview
        architecture = dashboard.get_architecture_overview()

        # Get project cockpit
        cockpit = dashboard.get_project_cockpit()
    """

    def __init__(
        self,
        repository_path: Path,
        repository_manager,
        quality_engine,
        symbol_graph,
        dependency_graph,
    ):
        """
        Initialize the Engineering Dashboard.

        Args:
            repository_path: Path to the repository
            repository_manager: Repository manager
            quality_engine: Quality engine
            symbol_graph: Symbol graph
            dependency_graph: Dependency graph
        """
        self.repository_path = Path(repository_path).resolve()
        self.repository_manager = repository_manager
        self.quality_engine = quality_engine
        self.symbol_graph = symbol_graph
        self.dependency_graph = dependency_graph

    def get_repository_analysis(self) -> dict[str, Any]:
        """
        Get comprehensive repository analysis.

        Returns:
            Dictionary with analysis
        """
        repo_state = self.repository_manager.get_repository_state()

        return {
            "repository": {
                "name": repo_state.name,
                "language": repo_state.language,
                "framework": repo_state.framework,
                "path": str(self.repository_path),
                "health": repo_state.health.value,
                "health_score": repo_state.get_health_score(),
            },
            "statistics": {
                "file_count": repo_state.file_count,
                "folder_count": repo_state.folder_count,
                "size": repo_state.size,
                "tests": len(repo_state.tests),
                "documentation": len(repo_state.documentation),
            },
            "git_status": {
                "branch": repo_state.git_branch,
                "status": repo_state.git_status,
                "last_commit": repo_state.last_commit,
            },
            "quality": {
                "coverage": repo_state.code_coverage,
                "technical_debt": repo_state.technical_debt,
            },
        }

    def get_quality_report(self) -> dict[str, Any]:
        """
        Get quality report.

        Returns:
            Dictionary with quality report
        """
        report = self.quality_engine.analyze_repository()

        return {
            "overall_score": report.overall_score,
            "metrics": {m.name: m.to_dict() for m in report.metrics},
            "issues": report.issues,
            "warnings": report.warnings,
            "recommendations": report.recommendations,
        }

    def get_architecture_overview(self) -> dict[str, Any]:
        """
        Get architecture overview.

        Returns:
            Dictionary with architecture overview
        """
        # Get modules
        modules = self.repository_manager._state.modules

        # Get symbol count
        stats = self.symbol_graph.get_statistics()

        # Get circular dependencies
        cycles = self.dependency_graph.find_circular_dependencies()

        return {
            "modules": modules,
            "total_symbols": stats.get("total_symbols", 0),
            "total_dependencies": stats.get("total_dependencies", 0),
            "circular_dependencies": len(cycles),
            "language": self.repository_manager._state.language,
        }

    def get_project_cockpit(self) -> dict[str, Any]:
        """
        Get the project cockpit (all metrics in one place).

        Returns:
            Dictionary with cockpit information
        """
        return {
            "repository_health": {
                "score": self.repository_manager._state.get_health_score(),
                "status": self.repository_manager._state.health.value,
            },
            "quality": self.get_quality_report(),
            "architecture": self.get_architecture_overview(),
            "open_issues": len(self.quality_engine.get_known_bugs()),
            "technical_debt": len(self.repository_manager._state.technical_debt),
            "repository_stats": self.repository_manager.get_stats(),
            "metrics": {
                "code_coverage": self.repository_manager._state.code_coverage,
                "cyclomatic_complexity_avg": self.repository_manager._state.cyclomatic_complexity_avg,
                "documentation_coverage": self.repository_manager._state.documentation_coverage,
            },
        }

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of the repository.

        Returns:
            Dictionary with summary
        """
        cockpit = self.get_project_cockpit()

        return {
            "overall_health": (
                "healthy"
                if cockpit["repository_health"]["score"] > 70
                else (
                    "degraded"
                    if cockpit["repository_health"]["score"] > 40
                    else "unhealthy"
                )
            ),
            "health_score": cockpit["repository_health"]["score"],
            "quality_score": cockpit["quality"]["overall_score"],
            "architecture_score": 80,  # Placeholder
            "recommendations": self._generate_recommendations(cockpit),
        }

    def _generate_recommendations(self, cockpit: dict[str, Any]) -> list[str]:
        """Generate recommendations based on metrics."""
        recommendations = []

        if cockpit["quality"]["overall_score"] < 70:
            recommendations.append("Improve test coverage")

        if cockpit["architecture"]["circular_dependencies"] > 0:
            recommendations.append("Resolve circular dependencies")

        if cockpit["open_issues"] > 5:
            recommendations.append("Address open issues")

        return recommendations

    def get_repository_health(self) -> dict[str, Any]:
        """Get repository health status."""
        repo_state = self.repository_manager.get_repository_state()

        return {
            "health": repo_state.health.value,
            "health_score": repo_state.get_health_score(),
            "issues": len(self.quality_engine.get_known_bugs()),
            "technical_debt": repo_state.technical_debt,
            "coverage": repo_state.code_coverage,
        }

    def get_recent_changes(self, limit: int = 10) -> list[str]:
        """
        Get recent changes.

        Args:
            limit: Maximum number of changes

        Returns:
            List of recent changes
        """
        return self.repository_manager._state.recent_changes[-limit:]
