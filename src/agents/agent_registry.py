"""
Agent Registry - Central registry for all agents.

The Agent Registry manages:
- Agent registration and registration
- Agent lookup by type and capability
- Agent lifecycle management
- Agent coordination
- Capability-based discovery
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from .browser_agent import BrowserAgent
from .coding_agent import CodingAgent
from .desktop_agent import DesktopAgent
from .learning_agent import LearningAgent
from .planner_agent import PlannerAgent
from .research_agent import ResearchAgent
from .task_model import Task, TaskType
from .vision_agent import VisionAgent
from .voice_agent import VoiceAgent


class AgentCapability(Enum):
    """Capabilities that agents can register for."""

    CODE_ANALYSIS = "code_analysis"
    CODE_REFACTORING = "code_refactoring"
    CODE_GENERATION = "code_generation"
    CODE_DEBUGGING = "code_debugging"
    TEST_GENERATION = "test_generation"
    DOCUMENTATION = "documentation"

    WEB_RESEARCH = "web_research"
    DEEP_RESEARCH = "deep_research"
    DOCUMENT_RESEARCH = "document_research"

    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_READING = "document_reading"
    DIAGRAM_UNDERSTANDING = "diagram_understanding"
    UI_EXPLANATION = "ui_explanation"

    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    WAKE_WORD_DETECTION = "wake_word_detection"
    VOICE_COMMAND_RECOGNITION = "voice_command_recognition"

    WORKFLOW_STORAGE = "workflow_storage"
    WORKFLOW_RETRIEVAL = "workflow_retrieval"
    WORKFLOW_OPTIMIZATION = "workflow_optimization"

    DESKTOP_CONTROL = "desktop_control"
    APPLICATION_MANAGEMENT = "application_management"
    FILE_OPERATIONS = "file_operations"
    SYSTEM_CONTROLS = "system_controls"
    BROWSER_MANAGEMENT = "browser_management"
    BROWSER_SHOPPING = "browser_shopping"
    BROWSER_SCROLLING = "browser_scrolling"
    BROWSER_INTERACTION = "browser_interaction"
    BROWSER_AUTOMATION = "browser_automation"

    ALL = "all"


class AgentType(Enum):
    """Types of specialized agents."""

    PLANNER = "planner"
    DESKTOP = "desktop"
    CODING = "coding"
    RESEARCH = "research"
    VISION = "vision"
    VOICE = "voice"
    LEARNING = "learning"
    BROWSER = "browser"


class Agent:
    """
    Represents a registered agent.

    Attributes:
        agent_id: Unique identifier for the agent
        agent_type: Type of agent
        agent_class: Class type of the agent
        capabilities: List of capabilities provided by this agent
        instance: Instance of the agent
        priority: Execution priority (0-100, higher is better)
        metadata: Additional metadata about the agent
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        agent_class: type,
        capabilities: list[AgentCapability],
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.agent_class = agent_class
        self.capabilities = capabilities
        self.priority = priority
        self.metadata = metadata or {}
        self.instance = None

    def instantiate(self, *args, **kwargs) -> Any:
        """Instantiate the agent with given parameters."""
        if self.instance is None:
            self.instance = self.agent_class(*args, **kwargs)
        return self.instance

    def supports_capability(self, capability: AgentCapability) -> bool:
        """Check if agent supports a capability."""
        return (
            capability in self.capabilities or AgentCapability.ALL in self.capabilities
        )


class AgentRegistry:
    """
    Central registry for managing all agents.

    Features:
    - Register agents with capabilities
    - Lookup agents by type or capability
    - Instantiate agents when needed
    - Prioritize agents for task execution
    - Manage agent lifecycle
    """

    _instance: AgentRegistry | None = None

    def __new__(cls):
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the registry."""
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._agents: dict[str, Agent] = {}
        self._agents_by_type: dict[AgentType, list[Agent]] = {}
        self._agents_by_capability: dict[AgentCapability, list[Agent]] = {}
        self._logger = logging.getLogger(__name__)
        self._initialized = True

    def register_agent(
        self,
        agent_id: str,
        agent_type: AgentType,
        agent_class: type,
        capabilities: list[AgentCapability],
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Register an agent type.

        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type of the agent
            agent_class: Class of the agent
            capabilities: Capabilities provided by the agent
            priority: Execution priority (0-100)
            metadata: Additional metadata
        """
        agent = Agent(
            agent_id=agent_id,
            agent_type=agent_type,
            agent_class=agent_class,
            capabilities=capabilities,
            priority=priority,
            metadata=metadata,
        )

        self._agents[agent_id] = agent

        # Index by type
        if agent_type not in self._agents_by_type:
            self._agents_by_type[agent_type] = []
        self._agents_by_type[agent_type].append(agent)

        # Index by capability
        for capability in capabilities:
            if capability not in self._agents_by_capability:
                self._agents_by_capability[capability] = []
            self._agents_by_capability[capability].append(agent)

        self._logger.info(
            f"Registered agent: {agent_id} ({agent_type.value}) with capabilities: {[c.value for c in capabilities]}"
        )

    def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        if agent_id in self._agents:
            agent = self._agents[agent_id]

            # Remove from type index
            if agent.agent_type in self._agents_by_type:
                self._agents_by_type[agent.agent_type].remove(agent)

            # Remove from capability index
            for capability in agent.capabilities:
                if capability in self._agents_by_capability:
                    self._agents_by_capability[capability].remove(agent)

            # Remove from main registry
            del self._agents[agent_id]

            self._logger.info(f"Unregistered agent: {agent_id}")

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get agent by ID."""
        return self._agents.get(agent_id)

    def get_agent_by_type(self, agent_type: AgentType) -> list[Agent]:
        """Get all agents of a specific type."""
        return self._agents_by_type.get(agent_type, [])

    def get_agent_by_capability(self, capability: AgentCapability) -> list[Agent]:
        """Get all agents that support a capability."""
        return self._agents_by_capability.get(capability, [])

    def instantiate_agent(self, agent_id: str, *args, **kwargs) -> Any:
        """Instantiate a specific agent."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        return agent.instantiate(*args, **kwargs)

    def find_agent_for_task(self, task: Task) -> Agent | None:
        """
        Find the best agent to handle a task.

        Args:
            task: Task to handle

        Returns:
            Best matching agent or None
        """
        # Get task type
        task_type = task.type.value

        # Map TaskType to AgentCapability
        # TaskType uses snake_case, AgentCapability uses PascalCase
        capability_mapping = {
            TaskType.RESEARCH_WEB.value: AgentCapability.WEB_RESEARCH,
            TaskType.RESEARCH_DOCUMENT.value: AgentCapability.DOCUMENT_RESEARCH,
            TaskType.DEEP_RESEARCH.value: AgentCapability.DEEP_RESEARCH,
            TaskType.CODE_ANALYSIS.value: AgentCapability.CODE_ANALYSIS,
            TaskType.CODE_REFACTOR.value: AgentCapability.CODE_REFACTORING,
            TaskType.CODE_DEBUG.value: AgentCapability.CODE_DEBUGGING,
            TaskType.CODE_GENERATE.value: AgentCapability.CODE_GENERATION,
            TaskType.TEST_GENERATE.value: AgentCapability.TEST_GENERATION,
            TaskType.CODE_DOCUMENT.value: AgentCapability.DOCUMENTATION,
            TaskType.IMAGE_ANALYSIS.value: AgentCapability.IMAGE_ANALYSIS,
            TaskType.DOCUMENT_READ.value: AgentCapability.DOCUMENT_READING,
            TaskType.DIAGRAM_UNDERSTAND.value: AgentCapability.DIAGRAM_UNDERSTANDING,
            TaskType.UI_EXPLANATION.value: AgentCapability.UI_EXPLANATION,
            TaskType.SPEECH_TO_TEXT.value: AgentCapability.SPEECH_TO_TEXT,
            TaskType.TEXT_TO_SPEECH.value: AgentCapability.TEXT_TO_SPEECH,
            TaskType.VOICE_INTERACTION.value: AgentCapability.VOICE_COMMAND_RECOGNITION,
            TaskType.WORKFLOW_STORE.value: AgentCapability.WORKFLOW_STORAGE,
            TaskType.WORKFLOW_RETRIEVE.value: AgentCapability.WORKFLOW_RETRIEVAL,
            TaskType.LEARN_SUCCESS.value: AgentCapability.WORKFLOW_OPTIMIZATION,
            TaskType.LEARN_FAILURE.value: AgentCapability.WORKFLOW_OPTIMIZATION,
            TaskType.FACT_RETRIEVE.value: AgentCapability.WORKFLOW_STORAGE,
            TaskType.FACT_ADD.value: AgentCapability.WORKFLOW_STORAGE,
            TaskType.FACT_UPDATE.value: AgentCapability.WORKFLOW_STORAGE,
            # Desktop control capabilities
            TaskType.APP_OPEN.value: AgentCapability.APPLICATION_MANAGEMENT,
            TaskType.APP_CLOSE.value: AgentCapability.APPLICATION_MANAGEMENT,
            TaskType.FILE_SEARCH.value: AgentCapability.FILE_OPERATIONS,
            TaskType.FILE_RENAME.value: AgentCapability.FILE_OPERATIONS,
            TaskType.FILE_MOVE.value: AgentCapability.FILE_OPERATIONS,
            TaskType.SCREENSHOT.value: AgentCapability.DESKTOP_CONTROL,
            TaskType.CLIPBOARD_READ.value: AgentCapability.DESKTOP_CONTROL,
            TaskType.SYSTEM_VOLUME.value: AgentCapability.SYSTEM_CONTROLS,
            TaskType.LOCK_WORKSTATION.value: AgentCapability.SYSTEM_CONTROLS,
            TaskType.BROWSER_OPEN.value: AgentCapability.BROWSER_MANAGEMENT,
            TaskType.WINDOW_MAXIMIZE.value: AgentCapability.APPLICATION_MANAGEMENT,
            TaskType.WINDOW_MINIMIZE.value: AgentCapability.APPLICATION_MANAGEMENT,
        }

        # Try to find agent by capability mapping
        capability = capability_mapping.get(task_type)
        if capability:
            agents = self.get_agent_by_capability(capability)
            if agents:
                # Return highest priority agent
                return max(agents, key=lambda a: a.priority)

        # If no exact match, return any agent that can handle it
        # For now, return the first available agent
        for agents in self._agents_by_capability.values():
            if agents:
                return max(agents, key=lambda a: a.priority)

        return None

    def find_agents_for_capability(self, capability: AgentCapability) -> list[Agent]:
        """
        Find all agents that can handle a capability.

        Args:
            capability: Capability to check

        Returns:
            List of agents supporting the capability
        """
        agents = self.get_agent_by_capability(capability)

        # Sort by priority (highest first)
        return sorted(agents, key=lambda a: a.priority, reverse=True)

    def get_all_agents(self) -> list[Agent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_agent_count(self) -> int:
        """Get total number of registered agents."""
        return len(self._agents)

    def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_agents": len(self._agents),
            "agents_by_type": {
                type.value: len(agents) for type, agents in self._agents_by_type.items()
            },
            "agents_by_capability": {
                cap.value: len(agents)
                for cap, agents in self._agents_by_capability.items()
            },
            "prioritized_capabilities": [
                {
                    "capability": cap.value,
                    "agent_count": len(agents),
                    "priority": max(a.priority for a in agents) if agents else 0,
                }
                for cap, agents in self._agents_by_capability.items()
                if agents
            ],
        }


# Pre-register built-in agents
def register_builtin_agents(registry: AgentRegistry):
    """
    Register all built-in agents with the registry.

    Args:
        registry: AgentRegistry instance
    """
    # Planner Agent
    registry.register_agent(
        agent_id="planner",
        agent_type=AgentType.PLANNER,
        agent_class=PlannerAgent,
        capabilities=[AgentCapability.ALL],
        priority=100,
        metadata={
            "name": "Executive Planner",
            "description": "Coordinates all other agents",
        },
    )

    # Desktop Agent
    registry.register_agent(
        agent_id="desktop",
        agent_type=AgentType.DESKTOP,
        agent_class=DesktopAgent,
        capabilities=[
            AgentCapability.DESKTOP_CONTROL,
            AgentCapability.APPLICATION_MANAGEMENT,
            AgentCapability.FILE_OPERATIONS,
            AgentCapability.SYSTEM_CONTROLS,
            AgentCapability.BROWSER_MANAGEMENT,
        ],
        priority=80,
        metadata={
            "name": "Desktop Agent",
            "description": "Controls desktop environment",
        },
    )

    # Coding Agent
    registry.register_agent(
        agent_id="coding",
        agent_type=AgentType.CODING,
        agent_class=CodingAgent,
        capabilities=[
            AgentCapability.CODE_ANALYSIS,
            AgentCapability.CODE_REFACTORING,
            AgentCapability.CODE_GENERATION,
            AgentCapability.CODE_DEBUGGING,
            AgentCapability.TEST_GENERATION,
            AgentCapability.DOCUMENTATION,
        ],
        priority=75,
        metadata={"name": "Coding Agent", "description": "Analyzes and improves code"},
    )

    # Research Agent
    registry.register_agent(
        agent_id="research",
        agent_type=AgentType.RESEARCH,
        agent_class=ResearchAgent,
        capabilities=[
            AgentCapability.WEB_RESEARCH,
            AgentCapability.DEEP_RESEARCH,
            AgentCapability.DOCUMENT_RESEARCH,
        ],
        priority=70,
        metadata={
            "name": "Research Agent",
            "description": "Performs web and document research",
        },
    )

    # Vision Agent
    registry.register_agent(
        agent_id="vision",
        agent_type=AgentType.VISION,
        agent_class=VisionAgent,
        capabilities=[
            AgentCapability.IMAGE_ANALYSIS,
            AgentCapability.DOCUMENT_READING,
            AgentCapability.DIAGRAM_UNDERSTANDING,
            AgentCapability.UI_EXPLANATION,
        ],
        priority=65,
        metadata={
            "name": "Vision Agent",
            "description": "Analyzes images and documents",
        },
    )

    # Voice Agent
    registry.register_agent(
        agent_id="voice",
        agent_type=AgentType.VOICE,
        agent_class=VoiceAgent,
        capabilities=[
            AgentCapability.SPEECH_TO_TEXT,
            AgentCapability.TEXT_TO_SPEECH,
            AgentCapability.WAKE_WORD_DETECTION,
            AgentCapability.VOICE_COMMAND_RECOGNITION,
        ],
        priority=60,
        metadata={"name": "Voice Agent", "description": "Handles voice interactions"},
    )

    # Learning Agent
    registry.register_agent(
        agent_id="learning",
        agent_type=AgentType.LEARNING,
        agent_class=LearningAgent,
        capabilities=[
            AgentCapability.WORKFLOW_STORAGE,
            AgentCapability.WORKFLOW_RETRIEVAL,
            AgentCapability.WORKFLOW_OPTIMIZATION,
        ],
        priority=55,
        metadata={
            "name": "Learning Agent",
            "description": "Stores and retrieves workflow knowledge",
        },
    )

    # Browser Agent
    registry.register_agent(
        agent_id="browser",
        agent_type=AgentType.BROWSER,
        agent_class=BrowserAgent,
        capabilities=[
            AgentCapability.BROWSER_MANAGEMENT,
            AgentCapability.BROWSER_SHOPPING,
            AgentCapability.BROWSER_SCROLLING,
            AgentCapability.BROWSER_INTERACTION,
            AgentCapability.BROWSER_AUTOMATION,
        ],
        priority=80,
        metadata={
            "name": "Browser Agent",
            "description": "Handles web browsing, shopping, cart, orders, and scrolling",
        },
    )

    logging.info("Registered 8 built-in agents")
