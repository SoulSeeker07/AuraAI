"""
Universal Execution Trace
General purpose execution trajectory trace for all Aura agent subsystems (Desktop, Research, Coding, Browser).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExecutionTraceNode:
    """
    Node in an ExecutionTrace representing a stage or step in execution.
    """

    stage: str  # Parse, Classify, Plan, Optimize, Execute, Verify, Evaluate, Complete
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """
    Universal execution trajectory trace.
    """

    trace_id: str
    agent_subsystem: str  # 'desktop', 'research', 'coding', 'browser'
    goal: str
    nodes: list[ExecutionTraceNode] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str | None = None
    is_successful: bool = False
    quality_score: float = 0.0

    def add_node(
        self,
        stage: str,
        message: str,
        duration_ms: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Add a trajectory node."""
        self.nodes.append(
            ExecutionTraceNode(
                stage=stage,
                message=message,
                duration_ms=duration_ms,
                details=details or {},
            )
        )

    def complete(self, success: bool, score: float = 100.0) -> None:
        """Mark trace as completed."""
        self.end_time = datetime.now().isoformat()
        self.is_successful = success
        self.quality_score = score

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "agent_subsystem": self.agent_subsystem,
            "goal": self.goal,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_successful": self.is_successful,
            "quality_score": self.quality_score,
            "total_nodes": len(self.nodes),
            "nodes": [
                {
                    "stage": n.stage,
                    "message": n.message,
                    "timestamp": n.timestamp,
                    "duration_ms": n.duration_ms,
                    "details": n.details,
                }
                for n in self.nodes
            ],
        }
