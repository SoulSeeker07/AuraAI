"""
Routing System - Directs tasks to the most appropriate agents.

The RoutingSystem determines which agent should handle a given task,
considering agent capabilities, priorities, and task requirements.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Routing strategies for task assignment."""

    BEST_MATCH = "best_match"  # Select the single best agent
    CAPABILITY_MATCH = "capability_match"  # Select all capable agents
    PRIORITY_WEIGHTED = "priority_weighted"  # Weight by agent priority
    ROUND_ROBIN = "round_robin"  # Distribute across agents
    FLEXIBLE = "flexible"  # Choose best strategy based on task


class RoutingMode(Enum):
    """Routing modes."""

    DIRECT = "direct"  # Direct task to agent
    DELEGATE = "delegate"  # Delegation pattern
    FALLBACK = "fallback"  # Try primary, then fallback agents
    COLLABORATIVE = "collaborative"  # Multiple agents work together


@dataclass
class TaskRoutingRequest:
    """Request for task routing."""

    task_type: str
    task_description: str
    priority: int = 50  # Task priority (1-100)
    target_agents: list[str] | None = None  # Specific agents to use
    routing_strategy: RoutingStrategy = RoutingStrategy.BEST_MATCH
    routing_mode: RoutingMode = RoutingMode.DIRECT
    required_capabilities: list[str] | None = None
    max_agents: int = 5  # Maximum number of agents to involve
    timeout: int | None = None  # Timeout for routing
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingResult:
    """Result of routing a task."""

    success: bool
    agents_assigned: list[str]
    routing_strategy_used: RoutingStrategy
    routing_mode_used: RoutingMode
    primary_agent: str | None = None
    fallback_agents: list[str] | None = None
    reason: str = ""
    execution_order: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RoutingSystem:
    """
    System for routing tasks to appropriate agents.

    Responsibilities:
    - Select agents for tasks
    - Consider agent capabilities and priorities
    - Handle fallback routing
    - Support multiple routing strategies
    - Track routing decisions
    """

    def __init__(self):
        """Initialize the RoutingSystem."""
        self.agent_registry = None  # Will be set from orchestrator
        self.routing_history: list[dict[str, Any]] = []
        self.round_robin_index: int = 0
        self.logger = logging.getLogger(__name__)

    def set_agent_registry(self, registry) -> None:
        """
        Set the agent registry for routing.

        Args:
            registry: AgentRegistry instance
        """
        self.agent_registry = registry
        self.logger.info("RoutingSystem: Agent registry set")

    def route_task(self, request: TaskRoutingRequest) -> RoutingResult:
        """
        Route a task to appropriate agents.

        Args:
            request: Task routing request

        Returns:
            RoutingResult with agent assignments
        """
        self.logger.info(
            f"Routing task: {request.task_type} ({request.task_description})"
        )

        # Record routing attempt
        routing_attempt = {
            "task_type": request.task_type,
            "task_description": request.task_description,
            "timestamp": datetime.now().isoformat(),
            "priority": request.priority,
        }

        # Apply routing mode
        if request.routing_mode == RoutingMode.DIRECT:
            return self._route_direct(request, routing_attempt)
        elif request.routing_mode == RoutingMode.DELEGATE:
            return self._route_delegate(request, routing_attempt)
        elif request.routing_mode == RoutingMode.FALLBACK:
            return self._route_fallback(request, routing_attempt)
        elif request.routing_mode == RoutingMode.COLLABORATIVE:
            return self._route_collaborative(request, routing_attempt)
        else:
            return self._route_flexible(request, routing_attempt)

    def _route_direct(
        self, request: TaskRoutingRequest, routing_attempt: dict
    ) -> RoutingResult:
        """
        Direct routing - assign to a single agent.

        Args:
            request: Routing request
            routing_attempt: Record for routing history

        Returns:
            RoutingResult
        """
        if request.target_agents:
            # Use specified agents
            agents = self._filter_agents(request.target_agents)
        else:
            # Use best match strategy
            agents = self._select_best_agent(request)
            if not agents:
                return RoutingResult(
                    success=False,
                    agents_assigned=[],
                    routing_strategy_used=request.routing_strategy,
                    routing_mode_used=request.routing_mode,
                    reason="No suitable agent found for task",
                )
            agents = [agents]

        result = RoutingResult(
            success=True,
            agents_assigned=agents,
            routing_strategy_used=request.routing_strategy,
            routing_mode_used=request.routing_mode,
            primary_agent=agents[0] if agents else None,
            reason=f"Direct routing to {len(agents)} agent(s): {', '.join(agents)}",
        )

        routing_attempt["agents_assigned"] = agents
        self.routing_history.append(routing_attempt)

        return result

    def _route_delegate(
        self, request: TaskRoutingRequest, routing_attempt: dict
    ) -> RoutingResult:
        """
        Delegation routing - assign to most capable agent.

        Args:
            request: Routing request
            routing_attempt: Record for routing history

        Returns:
            RoutingResult
        """
        if request.target_agents:
            agents = self._filter_agents(request.target_agents)
        else:
            agents = self._select_best_agent(request)

        if not agents:
            return RoutingResult(
                success=False,
                agents_assigned=[],
                routing_strategy_used=request.routing_strategy,
                routing_mode_used=request.routing_mode,
                reason="No suitable agent found for delegation",
            )

        # Sort by priority (highest first)
        agents = self._sort_by_priority(agents)

        result = RoutingResult(
            success=True,
            agents_assigned=agents,
            routing_strategy_used=request.routing_strategy,
            routing_mode_used=request.routing_mode,
            primary_agent=agents[0],
            reason=f"Delegated to {agents[0]} (primary)",
        )

        routing_attempt["agents_assigned"] = agents
        self.routing_history.append(routing_attempt)

        return result

    def _route_fallback(
        self, request: TaskRoutingRequest, routing_attempt: dict
    ) -> RoutingResult:
        """
        Fallback routing - try primary, then secondary agents.

        Args:
            request: Routing request
            routing_attempt: Record for routing history

        Returns:
            RoutingResult
        """
        # Get capable agents
        capable_agents = self._get_capable_agents(request)

        if not capable_agents:
            return RoutingResult(
                success=False,
                agents_assigned=[],
                routing_strategy_used=request.routing_strategy,
                routing_mode_used=request.routing_mode,
                reason="No capable agents found",
            )

        # Primary agent (highest priority)
        primary = self._get_highest_priority_agent(capable_agents)
        other_agents = [agent for agent in capable_agents if agent != primary]

        # Limit to max_agents
        if len(other_agents) > request.max_agents - 1:
            other_agents = other_agents[: request.max_agents - 1]

        result = RoutingResult(
            success=True,
            agents_assigned=[primary] + other_agents,
            routing_strategy_used=request.routing_strategy,
            routing_mode_used=request.routing_mode,
            primary_agent=primary,
            fallback_agents=other_agents if other_agents else None,
            reason=f"Primary: {primary}, Fallback: {', '.join(other_agents) if other_agents else 'none'}",
        )

        routing_attempt["agents_assigned"] = result.agents_assigned
        routing_attempt["primary_agent"] = primary
        routing_attempt["fallback_agents"] = other_agents
        self.routing_history.append(routing_attempt)

        return result

    def _route_collaborative(
        self, request: TaskRoutingRequest, routing_attempt: dict
    ) -> RoutingResult:
        """
        Collaborative routing - multiple agents work together.

        Args:
            request: Routing request
            routing_attempt: Record for routing history

        Returns:
            RoutingResult
        """
        # Get all capable agents
        capable_agents = self._get_capable_agents(request)

        if not capable_agents:
            return RoutingResult(
                success=False,
                agents_assigned=[],
                routing_strategy_used=request.routing_strategy,
                routing_mode_used=request.routing_mode,
                reason="No capable agents found for collaboration",
            )

        # Sort by priority
        capable_agents = self._sort_by_priority(capable_agents)

        # Limit to max_agents
        if len(capable_agents) > request.max_agents:
            capable_agents = capable_agents[: request.max_agents]

        # Create execution order (highest priority first)
        execution_order = capable_agents

        result = RoutingResult(
            success=True,
            agents_assigned=capable_agents,
            routing_strategy_used=request.routing_strategy,
            routing_mode_used=request.routing_mode,
            primary_agent=capable_agents[0],
            execution_order=execution_order,
            reason=f"Collaborative routing: {len(capable_agents)} agents",
        )

        routing_attempt["agents_assigned"] = capable_agents
        routing_attempt["execution_order"] = execution_order
        self.routing_history.append(routing_attempt)

        return result

    def _route_flexible(
        self, request: TaskRoutingRequest, routing_attempt: dict
    ) -> RoutingResult:
        """
        Flexible routing - choose best strategy based on task.

        Args:
            request: Routing request
            routing_attempt: Record for routing history

        Returns:
            RoutingResult
        """
        # For complex tasks, use collaborative routing
        if self._is_complex_task(request):
            request.routing_strategy = RoutingStrategy.CAPABILITY_MATCH
            request.routing_mode = RoutingMode.COLLABORATIVE
            return self._route_collaborative(request, routing_attempt)

        # For simple tasks, use direct routing
        else:
            request.routing_strategy = RoutingStrategy.BEST_MATCH
            request.routing_mode = RoutingMode.DIRECT
            return self._route_direct(request, routing_attempt)

    def _select_best_agent(self, request: TaskRoutingRequest) -> str | None:
        """
        Select the single best agent for a task.

        Args:
            request: Routing request

        Returns:
            Best agent name or None
        """
        if not self.agent_registry:
            return None

        # Get best agent using agent registry
        best_agent = self.agent_registry.get_best_agent(request.task_type)

        if best_agent and best_agent.is_active:
            return best_agent.agent_name

        return None

    def _get_capable_agents(self, request: TaskRoutingRequest) -> list[str]:
        """
        Get all agents capable of handling the task.

        Args:
            request: Routing request

        Returns:
            List of capable agent names
        """
        if not self.agent_registry:
            return []

        if request.target_agents:
            return self._filter_agents(request.target_agents)

        # Get all agents that can handle the task type
        capable_agents = self.agent_registry.get_agents_by_task(request.task_type)

        # Filter to active agents
        capable_agents = [agent for agent in capable_agents if agent.is_active]

        return [agent.agent_name for agent in capable_agents]

    def _sort_by_priority(self, agent_names: list[str]) -> list[str]:
        """
        Sort agent names by their priority.

        Args:
            agent_names: List of agent names

        Returns:
            Sorted list of agent names
        """
        if not self.agent_registry or not agent_names:
            return agent_names

        scored_agents = []
        for name in agent_names:
            agent = self.agent_registry.get_agent(name)
            if agent:
                scored_agents.append((agent.capabilities.priority, name))

        # Sort by priority (highest first)
        scored_agents.sort(key=lambda x: x[0], reverse=True)

        return [name for _, name in scored_agents]

    def _get_highest_priority_agent(self, agent_names: list[str]) -> str | None:
        """
        Get the highest priority agent from a list.

        Args:
            agent_names: List of agent names

        Returns:
            Highest priority agent name
        """
        if not agent_names:
            return None

        return self._sort_by_priority(agent_names)[0]

    def _filter_agents(self, agent_names: list[str]) -> list[str]:
        """
        Filter agent names to those that exist and are active.

        Args:
            agent_names: List of agent names to filter

        Returns:
            Filtered list of agent names
        """
        if not self.agent_registry:
            return []

        filtered = []
        for name in agent_names:
            agent = self.agent_registry.get_agent(name)
            if agent and agent.is_active:
                filtered.append(name)

        return filtered

    def _is_complex_task(self, request: TaskRoutingRequest) -> bool:
        """
        Determine if a task is complex enough for collaborative routing.

        Args:
            request: Routing request

        Returns:
            True if task is complex
        """
        # Tasks with multiple dependencies are complex
        if request.metadata.get("has_dependencies"):
            return True

        # Tasks with multiple components are complex
        if request.metadata.get("has_multiple_components"):
            return True

        # Long tasks are complex
        if request.timeout and request.timeout > 60:
            return True

        return False

    def get_routing_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get routing history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of routing attempts
        """
        return self.routing_history[-limit:]

    def get_routing_stats(self) -> dict[str, Any]:
        """
        Get statistics about routing.

        Returns:
            Statistics dictionary
        """
        total = len(self.routing_history)
        if total == 0:
            return {"total_routing_attempts": 0}

        # Count by routing mode
        mode_counts = defaultdict(int)
        strategy_counts = defaultdict(int)

        for routing in self.routing_history:
            mode = routing.get("routing_mode", "unknown")
            strategy = routing.get("routing_strategy", "unknown")
            mode_counts[mode] += 1
            strategy_counts[strategy] += 1

        return {
            "total_routing_attempts": total,
            "by_routing_mode": dict(mode_counts),
            "by_routing_strategy": dict(strategy_counts),
            "average_agents_per_task": sum(
                len(r.get("agents_assigned", [])) for r in self.routing_history
            )
            / total,
        }

    def clear_history(self) -> None:
        """Clear routing history."""
        self.routing_history.clear()
        self.round_robin_index = 0
        self.logger.info("Routing history cleared")


# Global routing system instance
_global_routing_system: RoutingSystem | None = None


def get_routing_system() -> RoutingSystem:
    """Get the global routing system instance."""
    global _global_routing_system

    if _global_routing_system is None:
        _global_routing_system = RoutingSystem()

    return _global_routing_system
