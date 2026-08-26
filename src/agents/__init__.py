"""
Agent System - Multi-agent framework for Aura AI

This package provides the complete agent framework for autonomous Aura operations.

The system consists of:
- Core components (task model, task manager)
- Specialized agents (planner, desktop, coding, research, vision, voice, learning)
- Agent coordination (registry, integration framework)
- Safety and extensibility (safety layer, plugin system, skill system)
- Monitoring and configuration (observability, configuration)
"""

from __future__ import annotations

from .agent_registry import (
    AgentCapability,
    AgentRegistry,
    AgentType,
    register_builtin_agents,
)
from .autonomous_coding_agent import AutonomousCodingAgent
from .coding_agent import CodingAgent
from .config import (
    ConfigManager,
    Configuration,
    LoggingSettings,
    ModelSettings,
    PerformanceSettings,
    PluginSettings,
    ProviderType,
    ResearchSettings,
    SafetySettings,
    get_config_manager,
)
from .desktop_agent import DesktopAgent
from .integration import (
    AgentCoordination,
    AgentCoordinator,
    CoordinationStrategy,
    execute_multi_agent_task,
)
from .learning_agent import LearningAgent
from .observability import (
    Metric,
    MetricCollector,
    MetricType,
    Observability,
    TaskExecutionEvent,
    TaskMonitor,
    get_observability,
)
from .planner_agent import PlannerAgent
from .plugin_system import (
    PluginAPI,
    PluginBase,
    PluginContext,
    PluginRegistry,
    get_plugin_registry,
)
from .research_agent import ResearchAgent
from .safety_layer import (
    OperationContext,
    OperationType,
    SafetyDecision,
    SafetyLayer,
    get_safety_layer,
    require_confirmation,
)
from .skill_system import (
    Skill,
    SkillCategory,
    SkillRegistry,
    SkillStep,
    get_skill_registry,
)
from .task_manager import TaskManager
from .task_model import Task, TaskInput, TaskOutput, TaskPriority, TaskStatus, TaskType
from .vision_agent import VisionAgent
from .voice_agent import VoiceAgent

__version__ = "2.0.0"

__all__ = [
    # Core components
    "Task",
    "TaskStatus",
    "TaskPriority",
    "TaskType",
    "TaskInput",
    "TaskOutput",
    "TaskManager",
    # Agent registry
    "AgentRegistry",
    "AgentType",
    "AgentCapability",
    "register_builtin_agents",
    # Integration
    "AgentCoordinator",
    "CoordinationStrategy",
    "AgentCoordination",
    "execute_multi_agent_task",
    # Safety layer
    "SafetyLayer",
    "OperationType",
    "OperationContext",
    "SafetyDecision",
    "get_safety_layer",
    "require_confirmation",
    # Plugin system
    "PluginBase",
    "PluginRegistry",
    "PluginContext",
    "PluginAPI",
    "get_plugin_registry",
    # Skill system
    "SkillRegistry",
    "Skill",
    "SkillStep",
    "SkillCategory",
    "get_skill_registry",
    # Observability
    "Observability",
    "MetricCollector",
    "Metric",
    "MetricType",
    "TaskMonitor",
    "TaskExecutionEvent",
    "get_observability",
    # Configuration
    "ConfigManager",
    "Configuration",
    "ModelSettings",
    "PluginSettings",
    "SafetySettings",
    "LoggingSettings",
    "PerformanceSettings",
    "ResearchSettings",
    "get_config_manager",
    "ProviderType",
    # Specialized agents
    "PlannerAgent",
    "DesktopAgent",
    "CodingAgent",
    "ResearchAgent",
    "VisionAgent",
    "VoiceAgent",
    "LearningAgent",
]

# Convenience imports for common use cases
__all_for_agents__ = [
    "AgentRegistry",
    "TaskManager",
    "SafetyLayer",
    "PluginRegistry",
    "SkillRegistry",
    "ConfigManager",
    "Observability",
]

# Default instances for quick access
_global_task_manager: Optional[TaskManager] = None
_global_agent_registry: Optional[AgentRegistry] = None
_global_safety_layer: Optional[SafetyLayer] = None
_global_plugin_registry: Optional[PluginRegistry] = None
_global_skill_registry: Optional[SkillRegistry] = None
_global_config_manager: Optional[ConfigManager] = None
_global_observability: Optional[Observability] = None


def get_task_manager() -> TaskManager:
    """Get global task manager instance."""
    global _global_task_manager
    if _global_task_manager is None:
        _global_task_manager = TaskManager()
    return _global_task_manager


def get_agent_registry() -> AgentRegistry:
    """Get global agent registry instance."""
    global _global_agent_registry
    if _global_agent_registry is None:
        _global_agent_registry = AgentRegistry()
        register_builtin_agents(_global_agent_registry)
    return _global_agent_registry


def get_safety_layer_singleton() -> SafetyLayer:
    """Get global safety layer instance."""
    global _global_safety_layer
    if _global_safety_layer is None:
        _global_safety_layer = SafetyLayer()
    return _global_safety_layer


def get_plugin_registry_singleton() -> PluginRegistry:
    """Get global plugin registry instance."""
    global _global_plugin_registry
    if _global_plugin_registry is None:
        _global_plugin_registry = PluginRegistry()
    return _global_plugin_registry


def get_skill_registry_singleton() -> SkillRegistry:
    """Get global skill registry instance."""
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = SkillRegistry()
    return _global_skill_registry


def get_config_manager_singleton() -> ConfigManager:
    """Get global config manager instance."""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager


def get_observability_singleton() -> Observability:
    """Get global observability instance."""
    global _global_observability
    if _global_observability is None:
        _global_observability = Observability()
    return _global_observability


# Initialize global instances
get_task_manager()
get_agent_registry()
get_safety_layer_singleton()
get_plugin_registry_singleton()
get_skill_registry_singleton()
get_config_manager_singleton()
get_observability_singleton()

__version__ = "2.0.0"
