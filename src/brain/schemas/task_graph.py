"""
TaskGraph — Directed Acyclic Graph for Execution
================================================

Real work isn't linear. The Planner should produce a DAG, not just an ordered list.

Example:
    Research → Summarize → Save → Open VS Code

Research and opening VS Code could overlap.

    Node: Research
        ↓
    Node: Summarize
        ↓
    Node: Save
        ↓
    Node: Open VS Code
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TaskNode:
    """A single node in the task graph."""

    node_id: str
    engine: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed, cancelled
    result: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "engine": self.engine,
            "action": self.action,
            "parameters": self.parameters,
            "description": self.description,
            "depends_on": self.depends_on,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
        }


@dataclass
class TaskGraph:
    """
    A directed acyclic graph of execution tasks.

    The Planner produces a TaskGraph, not a linear ExecutionMap.
    """

    goal: str
    nodes: list[TaskNode] = field(default_factory=list)
    graph_id: str = field(default_factory=lambda: f"graph_{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def root_nodes(self) -> list[TaskNode]:
        """Nodes with no dependencies."""
        all_deps = set()
        for node in self.nodes:
            all_deps.update(node.depends_on)
        return [n for n in self.nodes if n.node_id not in all_deps]

    @property
    def leaf_nodes(self) -> list[TaskNode]:
        """Nodes that nothing depends on."""
        all_ids = {n.node_id for n in self.nodes}
        has_dependents = set()
        for node in self.nodes:
            has_dependents.update(node.depends_on)
        return [n for n in self.nodes if n.node_id not in has_dependents]

    def get_execution_order(self) -> list[list[TaskNode]]:
        """
        Topological sort into parallel-executable levels.

        Returns levels where each level's nodes can run in parallel.
        """
        remaining = {n.node_id: n for n in self.nodes}
        executed: set[str] = set()
        levels: list[list[TaskNode]] = []

        while remaining:
            # Nodes whose dependencies are all satisfied
            ready = [
                n
                for n in remaining.values()
                if all(dep in executed for dep in n.depends_on)
            ]
            if not ready:
                # Cycle detected — execute remaining sequentially as last resort
                levels.append(list(remaining.values()))
                break
            levels.append(ready)
            for n in ready:
                executed.add(n.node_id)
                remaining.pop(n.node_id, None)

        return levels

    def add_node(
        self,
        engine: str,
        action: str,
        parameters: dict[str, Any] | None = None,
        description: str = "",
        depends_on: list[str] | None = None,
    ) -> TaskNode:
        """Add a node to the graph."""
        node = TaskNode(
            node_id=f"node_{len(self.nodes) + 1}_{uuid.uuid4().hex[:4]}",
            engine=engine,
            action=action,
            parameters=parameters or {},
            description=description,
            depends_on=depends_on or [],
        )
        self.nodes.append(node)
        return node

    def get_node(self, node_id: str) -> TaskNode | None:
        """Get a node by ID."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "goal": self.goal,
            "nodes": [n.to_dict() for n in self.nodes],
            "levels": [
                [n.node_id for n in level] for level in self.get_execution_order()
            ],
            "created_at": self.created_at,
        }


__all__ = ["TaskGraph", "TaskNode"]