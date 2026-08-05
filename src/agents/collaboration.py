"""
Collaboration System - Manages agent-to-agent communication and result merging.

Agents never call each other directly. All collaboration goes through the
CollaborationSystem, which ensures clean dependencies and proper result merging.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConflictResolution(Enum):
    """Conflict resolution strategies."""

    MERGE = "merge"  # Merge conflicting information
    FIRST_WINS = "first_wins"  # First agent's result takes precedence
    LAST_WINS = "last_wins"  # Last agent's result takes precedence
    RESOLVE_SEQUENTIALLY = "resolve_sequentially"  # Handle conflicts step by step
    MERGE_SUMMARY = "merge_summary"  # Only merge summaries


@dataclass
class AgentContribution:
    """Individual agent's contribution to a task."""

    agent_name: str
    result: dict[str, Any]
    priority: float = 1.0
    timestamp: float = 0.0

    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp == 0.0:
            self.timestamp = self.priority


@dataclass
class TaskCollaboration:
    """Represents a task being handled by multiple agents."""

    task_id: str
    task_description: str
    agents_involved: list[str]
    contributions: list[AgentContribution] = field(default_factory=list)
    conflicts_found: list[dict[str, Any]] = field(default_factory=list)
    resolution_strategy: ConflictResolution = ConflictResolution.MERGE_SUMMARY
    status: str = "pending"  # pending, resolving, complete, failed


class ResultMerger:
    """
    Merges results from multiple agents into a cohesive output.

    Responsibilities:
    - Combine agent outputs
    - Resolve conflicts
    - Preserve important information
    - Generate unified summary
    - Handle warnings and suggestions
    """

    def __init__(self, strategy: ConflictResolution = ConflictResolution.MERGE_SUMMARY):
        """
        Initialize the ResultMerger.

        Args:
            strategy: Conflict resolution strategy
        """
        self.conflict_strategy = strategy
        self.logger = logging.getLogger(__name__)

    def merge_agent_results(
        self, agent_results: list[dict[str, Any]], task_description: str = ""
    ) -> dict[str, Any]:
        """
        Merge results from multiple agents.

        Args:
            agent_results: List of agent results (dictionaries)
            task_description: Description of the task

        Returns:
            Merged result dictionary
        """
        if not agent_results:
            return {
                "success": False,
                "error": "No agent results to merge",
                "summary": "No agents participated",
            }

        # Track what each agent contributed
        contributions = []

        for i, result in enumerate(agent_results):
            contributions.append(
                AgentContribution(
                    agent_name=result.get("agent_name", f"Agent_{i}"),
                    result=result,
                    priority=result.get("confidence", 0.5),
                )
            )

        # Identify conflicts
        conflicts = self._identify_conflicts(contributions)

        # Resolve conflicts
        merged = self._resolve_conflicts(contributions, conflicts)

        # Add overall summary
        merged["summary"] = self._generate_overall_summary(
            task_description, contributions, conflicts
        )

        merged["conflicts_resolved"] = len(conflicts)
        merged["agents_used"] = len(agent_results)
        merged["successful_agents"] = sum(
            1 for r in agent_results if r.get("success", False)
        )

        return merged

    def _identify_conflicts(
        self, contributions: list[AgentContribution]
    ) -> list[dict[str, Any]]:
        """Identify potential conflicts between agent results."""
        conflicts = []

        # Track what files each agent modified
        files_modified = defaultdict(list)

        for contribution in contributions:
            files = contribution.result.get("files_modified", [])
            for file in files:
                files_modified[file].append(contribution.agent_name)

        # Find files modified by multiple agents
        for file, agents in files_modified.items():
            if len(agents) > 1:
                conflicts.append(
                    {
                        "type": "file_conflict",
                        "file": file,
                        "agents_involved": agents,
                        "description": f"File {file} was modified by multiple agents",
                    }
                )

        # Check for conflicting summaries
        summaries = [(c.agent_name, c.result.get("summary", "")) for c in contributions]

        if len(summaries) > 1:
            # Check if summaries contradict each other
            first_summary = summaries[0][1].lower()
            for i in range(1, len(summaries)):
                agent_name, summary = summaries[i]
                if (
                    first_summary
                    and summary.lower()
                    and first_summary != summary.lower()
                ):
                    conflicts.append(
                        {
                            "type": "summary_conflict",
                            "agents_involved": [summaries[0][0], agent_name],
                            "description": f"Agents {summaries[0][0]} and {agent_name} have conflicting summaries",
                        }
                    )

        return conflicts

    def _resolve_conflicts(
        self, contributions: list[AgentContribution], conflicts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Resolve identified conflicts using the configured strategy."""
        merged = {
            "summary": "",
            "actions": [],
            "files_modified": [],
            "warnings": [],
            "suggestions": [],
            "data": {},
        }

        # Collect all actions
        for contribution in contributions:
            result = contribution.result
            merged["actions"].extend(result.get("actions", []))

        # Remove duplicates
        merged["actions"] = list(set(merged["actions"]))

        # Collect files modified
        files_modified = []
        for contribution in contributions:
            files = contribution.result.get("files_modified", [])
            files_modified.extend(files)

        # Remove duplicates and collect conflicts
        seen_files = set()
        file_conflicts = defaultdict(list)

        for file in files_modified:
            if file in seen_files:
                file_conflicts[file].append(file)
            else:
                seen_files.add(file)
                merged["files_modified"].append(file)

        # Track conflicting files
        for file, conflicts_list in file_conflicts.items():
            merged["warnings"].append(
                f"File {file} was modified by multiple agents: {', '.join(conflicts_list)}"
            )

        # Collect warnings and suggestions
        for contribution in contributions:
            result = contribution.result
            merged["warnings"].extend(result.get("warnings", []))
            merged["suggestions"].extend(result.get("suggestions", []))

        # Merge data fields
        for contribution in contributions:
            for key, value in contribution.result.get("data", {}).items():
                if key not in merged["data"]:
                    merged["data"][key] = value
                elif isinstance(merged["data"][key], list) and isinstance(value, list):
                    merged["data"][key].extend(value)
                elif isinstance(merged["data"][key], dict) and isinstance(value, dict):
                    merged["data"][key].update(value)

        # Remove duplicates from lists
        merged["warnings"] = list(set(merged["warnings"]))
        merged["suggestions"] = list(set(merged["suggestions"]))

        # Use highest confidence
        confidences = [c.result.get("confidence", 0.5) for c in contributions]
        merged["confidence"] = max(confidences) if confidences else 0.5

        return merged

    def _generate_overall_summary(
        self,
        task_description: str,
        contributions: list[AgentContribution],
        conflicts: list[dict[str, Any]],
    ) -> str:
        """Generate an overall summary of the collaboration."""
        if not contributions:
            return "No agent contributions to summarize"

        if not task_description:
            task_description = "A task involving multiple agents"

        # Count successful vs failed agents
        successful = sum(1 for c in contributions if c.result.get("success", False))
        total = len(contributions)

        if successful == total:
            return f"✅ All {total} agents successfully completed {task_description}"
        elif successful > 0:
            return f"✅ {successful}/{total} agents successfully completed {task_description}"
        else:
            return f"❌ No agents successfully completed {task_description}"

    def merge_simple_outputs(self, outputs: list[str]) -> str:
        """
        Merge simple string outputs.

        Args:
            outputs: List of outputs from agents

        Returns:
            Merged output string
        """
        if not outputs:
            return ""

        if len(outputs) == 1:
            return outputs[0]

        # Join with newlines for readability
        merged = "=== Multi-Agent Output ===\n\n"

        for i, output in enumerate(outputs, 1):
            merged += f"--- Agent {i} ---\n{output}\n\n"

        merged += "=== End of Multi-Agent Output ==="

        return merged


class CollaborationSystem:
    """
    Manages agent collaboration patterns.

    Ensures agents never call each other directly.
    All communication goes through this system.
    """

    def __init__(self):
        """Initialize the collaboration system."""
        self.collaborations: dict[str, TaskCollaboration] = {}
        self.logger = logging.getLogger(__name__)

    def register_collaboration(self, collaboration: TaskCollaboration) -> None:
        """
        Register a new collaboration.

        Args:
            collaboration: The collaboration to register
        """
        self.collaborations[collaboration.task_id] = collaboration
        self.logger.info(f"Registered collaboration: {collaboration.task_description}")

    def get_collaboration_status(self, task_id: str) -> TaskCollaboration | None:
        """Get status of a collaboration."""
        return self.collaborations.get(task_id)

    def create_collaboration(
        self, task_id: str, task_description: str, agents: list[str]
    ) -> TaskCollaboration:
        """
        Create a new collaboration.

        Args:
            task_id: Unique ID for the collaboration
            task_description: Description of the task
            agents: Agents involved in the collaboration

        Returns:
            TaskCollaboration instance
        """
        collaboration = TaskCollaboration(
            task_id=task_id,
            task_description=task_description,
            agents_involved=agents,
            status="active",
        )

        self.register_collaboration(collaboration)
        return collaboration

    def register_agent_contribution(
        self,
        task_id: str,
        agent_name: str,
        result: dict[str, Any],
        priority: float = 1.0,
    ) -> bool:
        """
        Register an agent's contribution to a collaboration.

        Args:
            task_id: Collaboration task ID
            agent_name: Name of the agent
            result: Agent's result
            priority: Agent's priority/confidence

        Returns:
            True if successful
        """
        if task_id not in self.collaborations:
            self.logger.error(f"Collaboration {task_id} not found")
            return False

        collaboration = self.collaborations[task_id]

        contribution = AgentContribution(
            agent_name=agent_name, result=result, priority=priority
        )

        collaboration.contributions.append(contribution)

        self.logger.debug(f"Registered contribution from {agent_name} to {task_id}")
        return True

    def get_collaboration_summary(self, task_id: str) -> dict[str, Any]:
        """
        Get a summary of a collaboration's progress.

        Args:
            task_id: Collaboration task ID

        Returns:
            Summary dictionary
        """
        collaboration = self.collaborations.get(task_id)

        if not collaboration:
            return {"error": "Collaboration not found"}

        return {
            "task_id": task_id,
            "task_description": collaboration.task_description,
            "status": collaboration.status,
            "agents_involved": collaboration.agents_involved,
            "contributions_received": len(collaboration.contributions),
            "conflicts_found": len(collaboration.conflicts_found),
            "contributions": [
                {"agent_name": c.agent_name, "priority": c.priority}
                for c in collaboration.contributions
            ],
        }

    def complete_collaboration(self, task_id: str) -> bool:
        """
        Mark a collaboration as complete.

        Args:
            task_id: Collaboration task ID

        Returns:
            True if successful
        """
        if task_id not in self.collaborations:
            return False

        self.collaborations[task_id].status = "complete"
        self.logger.info(f"Completed collaboration: {task_id}")
        return True

    def get_collaboration_stats(self) -> dict[str, Any]:
        """
        Get statistics about all collaborations.

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_collaborations": len(self.collaborations),
            "active_collaborations": 0,
            "completed_collaborations": 0,
            "by_status": defaultdict(int),
        }

        for collaboration in self.collaborations.values():
            stats["by_status"][collaboration.status] += 1

        stats["active_collaborations"] = stats["by_status"].get("active", 0)
        stats["completed_collaborations"] = stats["by_status"].get("complete", 0)

        return dict(stats)

    def get_collaborating_agents(self, task_id: str) -> list[str]:
        """
        Get the list of agents involved in a collaboration.

        Args:
            task_id: Collaboration task ID

        Returns:
            List of agent names
        """
        collaboration = self.collaborations.get(task_id)
        return collaboration.agents_involved if collaboration else []


# Global collaboration system instance
_global_collaboration_system: CollaborationSystem | None = None


def get_collaboration_system() -> CollaborationSystem:
    """Get the global collaboration system instance."""
    global _global_collaboration_system

    if _global_collaboration_system is None:
        _global_collaboration_system = CollaborationSystem()

    return _global_collaboration_system


def get_result_merger(
    strategy: ConflictResolution = ConflictResolution.MERGE_SUMMARY,
) -> ResultMerger:
    """
    Get the global result merger instance.

    Args:
        strategy: Conflict resolution strategy

    Returns:
        ResultMerger instance
    """
    return ResultMerger(strategy)
