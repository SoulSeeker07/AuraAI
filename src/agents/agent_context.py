"""
AgentContext - Context allocation and filtering system for multi-agent orchestration.

Each agent receives filtered context appropriate to their specialization.
No agent has access to everything.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentContextType(Enum):
    """Types of context available."""

    REPOSITORY = "repository"  # Source code repository
    WORKSPACE = "workspace"  # File system workspace
    KNOWLEDGE = "knowledge"  # Knowledge base
    MEMORY = "memory"  # Memory store
    INTERNET = "internet"  # Web search capability
    CONFIGURATION = "configuration"  # System configurations
    RUNNING_APPS = "running_apps"  # Active applications
    PLUGINS = "plugins"  # Available plugins
    PROCESS = "process"  # Process information
    NETWORK = "network"  # Network topology and configs
    SECURITY = "security"  # Security information
    VISION = "vision"  # Vision capabilities
    VOICE = "voice"  # Voice capabilities


@dataclass
class AgentContext:
    """
    Context allocated to an agent.

    Contains only the information relevant to that agent's specialty.
    """

    agent_name: str
    context_type: AgentContextType
    available_data: dict[str, Any] = field(default_factory=dict)
    filtered_data: dict[str, Any] = field(default_factory=dict)
    restrictions: list[str] = field(default_factory=list)  # What's forbidden
    priority: float = 1.0  # Importance level
    max_items: int = 100  # Maximum items to provide

    def __post_init__(self):
        """Apply filtering and restrictions to available data."""
        self._apply_filtering()

    def _apply_filtering(self):
        """Apply filtering based on context type and restrictions."""
        if self.context_type == AgentContextType.WORKSPACE:
            self.filtered_data = self._filter_workspace()
        elif self.context_type == AgentContextType.REPOSITORY:
            self.filtered_data = self._filter_repository()
        elif self.context_type == AgentContextType.NETWORK:
            self.filtered_data = self._filter_network()
        elif self.context_type == AgentContextType.SECURITY:
            self.filtered_data = self._filter_security()
        elif self.context_type == AgentContextType.KNOWLEDGE:
            self.filtered_data = self._filter_knowledge()
        elif self.context_type == AgentContextType.MEMORY:
            self.filtered_data = self._filter_memory()
        else:
            # Default: provide all available data (no special filtering)
            self.filtered_data = deepcopy(self.available_data)

        # Apply max items limit
        self.filtered_data = self._limit_items()

        # Apply restrictions
        for restriction in self.restrictions:
            if restriction in self.filtered_data:
                del self.filtered_data[restriction]

    def _filter_workspace(self) -> dict[str, Any]:
        """Filter for desktop/workspace context."""
        workspace_data = {}

        # File system structure
        if "files" in self.available_data:
            workspace_data["files"] = self.available_data["files"][: self.max_items]

        # Running processes
        if "processes" in self.available_data:
            workspace_data["processes"] = self.available_data["processes"]

        # Clipboard
        if "clipboard" in self.available_data:
            workspace_data["clipboard"] = self.available_data["clipboard"]

        # Desktop notifications
        if "notifications" in self.available_data:
            workspace_data["notifications"] = self.available_data["notifications"]

        return workspace_data

    def _filter_repository(self) -> dict[str, Any]:
        """Filter for coding repository context."""
        repo_data = {}

        # Source code
        if "source_code" in self.available_data:
            repo_data["source_code"] = self.available_data["source_code"]

        # Dependencies
        if "dependencies" in self.available_data:
            repo_data["dependencies"] = self.available_data["dependencies"]

        # Git history
        if "git_history" in self.available_data:
            repo_data["git_history"] = self.available_data["git_history"]

        # Architecture
        if "architecture" in self.available_data:
            repo_data["architecture"] = self.available_data["architecture"]

        # Tests
        if "tests" in self.available_data:
            repo_data["tests"] = self.available_data["tests"]

        return repo_data

    def _filter_network(self) -> dict[str, Any]:
        """Filter for networking context."""
        network_data = {}

        # Router configurations
        if "routers" in self.available_data:
            network_data["routers"] = self.available_data["routers"]

        # Network topology
        if "topology" in self.available_data:
            network_data["topology"] = self.available_data["topology"]

        # Firewall configs
        if "firewalls" in self.available_data:
            network_data["firewalls"] = self.available_data["firewalls"]

        # VPN configs
        if "vpn" in self.available_data:
            network_data["vpn"] = self.available_data["vpn"]

        # Network logs
        if "logs" in self.available_data:
            network_data["logs"] = self.available_data["logs"]

        # Packet captures
        if "pcaps" in self.available_data:
            network_data["pcaps"] = self.available_data["pcaps"]

        return network_data

    def _filter_security(self) -> dict[str, Any]:
        """Filter for security context."""
        security_data = {}

        # User permissions
        if "permissions" in self.available_data:
            security_data["permissions"] = self.available_data["permissions"]

        # Credentials
        if "credentials" in self.available_data:
            security_data["credentials"] = self.available_data["credentials"]

        # Threat detection
        if "threats" in self.available_data:
            security_data["threats"] = self.available_data["threats"]

        # Security logs
        if "security_logs" in self.available_data:
            security_data["security_logs"] = self.available_data["security_logs"]

        # Risk assessment
        if "risk_assessment" in self.available_data:
            security_data["risk_assessment"] = self.available_data["risk_assessment"]

        return security_data

    def _filter_knowledge(self) -> dict[str, Any]:
        """Filter for knowledge base context."""
        knowledge_data = {}

        # Knowledge entries
        if "entries" in self.available_data:
            knowledge_data["entries"] = self.available_data["entries"]

        # Documents
        if "documents" in self.available_data:
            knowledge_data["documents"] = self.available_data["documents"]

        # Citations
        if "citations" in self.available_data:
            knowledge_data["citations"] = self.available_data["citations"]

        return knowledge_data

    def _filter_memory(self) -> dict[str, Any]:
        """Filter for memory context."""
        memory_data = {}

        # Memory entries
        if "entries" in self.available_data:
            memory_data["entries"] = self.available_data["entries"]

        # Recent memories
        if "recent" in self.available_data:
            memory_data["recent"] = self.available_data["recent"]

        return memory_data

    def _limit_items(self) -> dict[str, Any]:
        """Limit number of items in each category."""
        limited = {}

        for key, value in self.filtered_data.items():
            if isinstance(value, list) and len(value) > self.max_items:
                limited[key] = value[: self.max_items]
            elif isinstance(value, dict):
                # Limit dict items
                limited[key] = {
                    k: v for i, (k, v) in enumerate(value.items()) if i < self.max_items
                }
            else:
                limited[key] = value

        return limited

    def get_relevant_context(self, query: str) -> dict[str, Any]:
        """
        Get context relevant to a specific query.

        Args:
            query: Search query to find relevant context

        Returns:
            Filtered context relevant to query
        """
        relevant = {}

        for key, value in self.filtered_data.items():
            # Simple string matching for relevance
            if isinstance(value, str) and query.lower() in value.lower():
                relevant[key] = value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and query.lower() in item.lower():
                        if key not in relevant:
                            relevant[key] = []
                        relevant[key].append(item)
                    elif isinstance(item, dict) and query.lower() in str(item).lower():
                        if key not in relevant:
                            relevant[key] = []
                        relevant[key].append(item)

        return relevant


@dataclass
class ContextManager:
    """
    Manages context allocation for all agents.

    The Aura Brain provides the same context to all agents, but each agent
    receives only their relevant portion.
    """

    # Global context (provided by Aura Brain)
    global_context: dict[str, Any] = field(default_factory=dict)

    # Agent-specific context allocations
    agent_contexts: dict[str, AgentContext] = field(default_factory=dict)

    # Agent context requirements
    agent_requirements: dict[str, list[AgentContextType]] = field(default_factory=dict)

    def add_agent_requirement(
        self, agent_name: str, required_context: list[AgentContextType]
    ) -> None:
        """
        Define what context an agent needs.

        Args:
            agent_name: Name of the agent
            required_context: List of context types required
        """
        self.agent_requirements[agent_name] = required_context

    def allocate_context(self, agent_name: str) -> AgentContext:
        """
        Allocate appropriate context to an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentContext with filtered information
        """
        # Determine required context types
        required_types = self.agent_requirements.get(agent_name, [])

        # Default to workspace context if none specified
        if not required_types:
            required_types = [AgentContextType.WORKSPACE]

        # Create context with available data
        context = AgentContext(
            agent_name=agent_name,
            context_type=required_types[0],  # Use first required type
            available_data=self.global_context,
            priority=1.0,
        )

        # Store in registry
        self.agent_contexts[agent_name] = context

        return context

    def get_context(self, agent_name: str) -> AgentContext | None:
        """
        Get context for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentContext or None if not allocated
        """
        return self.agent_contexts.get(agent_name)

    def update_global_context(self, key: str, value: Any) -> None:
        """
        Update global context available to all agents.

        Args:
            key: Context key
            value: Context value
        """
        self.global_context[key] = value

    def get_all_context_types(self) -> dict[str, list[AgentContextType]]:
        """
        Get all agent requirements organized by context type.

        Returns:
            Dictionary mapping context types to agents that need it
        """
        context_usage = {}

        for agent_name, required_types in self.agent_requirements.items():
            for context_type in required_types:
                if context_type not in context_usage:
                    context_usage[context_type] = []
                context_usage[context_type].append(agent_name)

        return context_usage

    def summarize_context_usage(self) -> dict[str, Any]:
        """
        Get summary of context usage across agents.

        Returns:
            Summary dictionary
        """
        summary = {
            "total_agents": len(self.agent_requirements),
            "total_context_types": len(
                set(
                    type_
                    for req_list in self.agent_requirements.values()
                    for type_ in req_list
                )
            ),
            "by_context_type": {},
        }

        for context_type, agents in self.get_all_context_types().items():
            summary["by_context_type"][context_type.value] = {
                "count": len(agents),
                "agents": agents,
            }

        return summary


# Predefined context requirements for each agent type
AGENT_CONTEXT_REQUIREMENTS = {
    "CodingAgent": [
        AgentContextType.REPOSITORY,
        AgentContextType.WORKSPACE,
        AgentContextType.KNOWLEDGE,
        AgentContextType.MEMORY,
    ],
    "ResearchAgent": [
        AgentContextType.KNOWLEDGE,
        AgentContextType.INTERNET,
        AgentContextType.MEMORY,
    ],
    "DesktopAgent": [
        AgentContextType.WORKSPACE,
        AgentContextType.PLUGINS,
        AgentContextType.RUNNING_APPS,
    ],
    "NetworkingAgent": [
        AgentContextType.NETWORK,
        AgentContextType.CONFIGURATION,
        AgentContextType.SECURITY,
    ],
    "VisionAgent": [AgentContextType.VISION],
    "VoiceAgent": [AgentContextType.VOICE],
    "SecurityAgent": [AgentContextType.SECURITY, AgentContextType.CONFIGURATION],
    "DocumentationAgent": [
        AgentContextType.KNOWLEDGE,
        AgentContextType.REPOSITORY,
        AgentContextType.MEMORY,
    ],
}
