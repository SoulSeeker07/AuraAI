"""
Base Agent Class for Multi-Agent Intelligence System
All specialized agents inherit from this base class.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""

    CREATED = "created"
    INITIALIZED = "initialized"
    ASSIGNED = "assigned"
    WORKING = "working"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"


@dataclass
class AgentCapabilities:
    """Defines what an agent can do."""

    tasks: list[str] = field(default_factory=list)  # Supported task types
    tools: list[str] = field(default_factory=list)  # Available tools
    models: list[str] = field(default_factory=list)  # Supported models
    priority: int = 50  # Priority for task assignment (1-100)
    dependencies: list[str] = field(default_factory=list)  # Agent dependencies
    expert_domains: list[str] = field(default_factory=list)  # Domain expertise


@dataclass
class AgentResult:
    """Standardized result format from all agents."""

    agent_name: str
    success: bool
    summary: str = ""
    actions: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self):
        """Normalize confidence score."""
        if not 0 <= self.confidence <= 1.0:
            self.confidence = max(0.0, min(1.0, self.confidence))


class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents.

    Each agent is:
    - Stateless by default (fresh instance for each task)
    - Specialized in a specific domain
    - Runs independently
    - Returns structured results
    - Cannot call other agents directly (must go through Orchestrator)
    """

    # Class-level agent registry information
    agent_name: str = "BaseAgent"
    agent_version: str = "1.0.0"
    agent_description: str = ""

    def __init__(
        self,
        agent_id: str,
        capabilities: AgentCapabilities,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the agent.

        Args:
            agent_id: Unique identifier for this agent instance
            capabilities: What this agent can do
            config: Configuration for this agent
        """
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.config = config or {}
        self.state = AgentState.CREATED

        # Performance tracking
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.execution_time: float = 0.0

        # Input and output
        self.input: dict[str, Any] = {}
        self.output: AgentResult = None

        logger.info(f"Initialized {self.agent_name} (ID: {agent_id})")

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the agent resources.

        Returns:
            bool: True if initialization successful
        """
        pass

    @abstractmethod
    async def execute(self, task: dict[str, Any]) -> AgentResult:
        """
        Execute the assigned task.

        Args:
            task: Task dictionary containing:
                - task_type: Type of task to perform
                - data: Task-specific data
                - context: Additional context from orchestrator

        Returns:
            AgentResult: Structured result containing summary, actions, etc.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """
        Clean up resources used by this agent.

        Returns:
            bool: True if cleanup successful
        """
        pass

    async def _set_state(self, new_state: AgentState) -> None:
        """Update agent state with logging."""
        logger.debug(
            f"{self.agent_name} state transition: {self.state.name} -> {new_state.name}"
        )
        self.state = new_state

    def _get_execution_time(self) -> float:
        """Calculate and return execution time."""
        if self.start_time is None:
            return 0.0

        end_time = self.end_time or time.time()
        self.execution_time = end_time - self.start_time
        return self.execution_time

    def _create_result(
        self,
        success: bool,
        summary: str = "",
        actions: list[str] = None,
        files_modified: list[str] = None,
        confidence: float = 0.0,
        warnings: list[str] = None,
        suggestions: list[str] = None,
        next_steps: list[str] = None,
        data: dict[str, Any] = None,
        error: str | None = None,
    ) -> AgentResult:
        """
        Create a standardized AgentResult.

        Returns:
            AgentResult: Standardized result object
        """
        return AgentResult(
            agent_name=self.agent_name,
            success=success,
            summary=summary,
            actions=actions or [],
            files_modified=files_modified or [],
            confidence=confidence,
            warnings=warnings or [],
            suggestions=suggestions or [],
            next_steps=next_steps or [],
            data=data or {},
            error=error,
        )

    def __str__(self) -> str:
        """String representation of agent."""
        return f"{self.agent_name}(ID: {self.agent_id}, State: {self.state.name})"

    def __repr__(self) -> str:
        """Detailed representation of agent."""
        return f"<{self.agent_name} agent_id={self.agent_id} state={self.state.name}>"
