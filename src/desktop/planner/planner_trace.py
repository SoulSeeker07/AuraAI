"""
Planner Trace
Captures structured, step-by-step execution trees for debugging and GUI timeline visualization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PlannerTraceNode:
    """
    Node in a PlannerTrace representing a stage or step in execution.
    """

    stage: str  # Parse, Classify, Graph, Resolve, Optimize, Execute, Verify, Complete
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannerTrace:
    """
    Complete trajectory trace for a DesktopPlan execution.
    """

    trace_id: str
    goal: str
    nodes: list[PlannerTraceNode] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str | None = None
    is_successful: bool = False

    def add_node(
        self, stage: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        """Add a trace node."""
        self.nodes.append(
            PlannerTraceNode(
                stage=stage,
                message=message,
                details=details or {},
            )
        )

    def complete(self, success: bool) -> None:
        """Mark trace as completed."""
        self.end_time = datetime.now().isoformat()
        self.is_successful = success

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "goal": self.goal,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_successful": self.is_successful,
            "total_nodes": len(self.nodes),
            "nodes": [
                {
                    "stage": n.stage,
                    "message": n.message,
                    "timestamp": n.timestamp,
                    "details": n.details,
                }
                for n in self.nodes
            ],
        }
