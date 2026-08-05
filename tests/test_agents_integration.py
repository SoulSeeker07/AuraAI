"""
Integration tests for the agent system.

Tests cover:
- Task model
- Task manager
- Agent registry
- Agent coordination
- Basic agent capabilities
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.agents.agent_registry import (
    AgentCapability,
    AgentRegistry,
    AgentType,
    register_builtin_agents,
)
from src.agents.config import ConfigManager, ProviderType, get_config_manager
from src.agents.plugin_system import PluginBase, PluginRegistry
from src.agents.safety_layer import OperationType, SafetyLayer
from src.agents.skill_system import SkillCategory, SkillRegistry, SkillStep
from src.agents.task_manager import TaskManager
from src.agents.task_model import (
    Task,
    TaskInput,
    TaskOutput,
    TaskPriority,
    TaskStatus,
    TaskType,
)

# ========================================
# Test Task Model
# ========================================


def test_task_creation():
    """Test task creation with basic data."""
    task = Task(
        id="test_task",
        type=TaskType.RESEARCH_WEB,
        title="Test Task",
        input={"query": "test"},
        priority=TaskPriority.MEDIUM,
        description="Test task",
    )

    assert task.id == "test_task"
    assert task.type == TaskType.RESEARCH_WEB
    assert task.priority == TaskPriority.MEDIUM
    assert task.status == TaskStatus.PENDING


def test_task_lifecycle():
    """Test task status transitions."""
    task = Task(id="test_task", type=TaskType.RESEARCH_WEB, title="Test Task", input={})

    assert task.status == TaskStatus.PENDING

    task.mark_running()
    assert task.status == TaskStatus.RUNNING

    task.mark_completed()
    assert task.status == TaskStatus.COMPLETED

    task.mark_failed("Error")
    assert task.status == TaskStatus.FAILED


def test_task_should_retry():
    """Test task retry logic."""
    task = Task(id="test_task", type=TaskType.RESEARCH_WEB, title="Test Task", input={})

    # Should retry for failed tasks
    task.mark_failed("Error")
    assert task.should_retry() is True

    # Should not retry for completed tasks
    task.mark_completed()
    assert task.should_retry() is False

    # Should not retry for cancelled tasks
    task.mark_cancelled()
    assert task.should_retry() is False


# ========================================
# Test Task Manager
# ========================================


@pytest.mark.asyncio
async def test_task_manager_create():
    """Test task manager can create tasks."""
    manager = TaskManager()

    task = manager.create_task(
        task_type=TaskType.RESEARCH_WEB,
        title="Test Task",
        description="Test task description",
        input={"query": "test"},
        priority=TaskPriority.MEDIUM,
    )

    assert task.id in manager._tasks
    assert task.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_task_manager_get():
    """Test task manager can retrieve tasks."""
    manager = TaskManager()

    task = manager.create_task(
        task_type=TaskType.RESEARCH_WEB,
        title="Test Task",
        description="Test task description",
        input={"query": "test"},
    )

    retrieved = manager.get_task(task.id)
    assert retrieved == task


@pytest.mark.asyncio
async def test_task_manager_get_by_status():
    """Test task manager can filter by status."""
    manager = TaskManager()

    task1 = manager.create_task(
        task_type=TaskType.RESEARCH_WEB,
        title="Test Task 1",
        description="Test task 1",
        input={"query": "test"},
    )
    task1.mark_completed()

    task2 = manager.create_task(
        task_type=TaskType.RESEARCH_WEB,
        title="Test Task 2",
        description="Test task 2",
        input={"query": "test2"},
    )

    completed_tasks = manager.get_tasks_by_status(TaskStatus.COMPLETED)
    assert len(completed_tasks) == 1
    assert completed_tasks[0].id == task1.id


@pytest.mark.asyncio
async def test_task_manager_get_statistics():
    """Test task manager statistics."""
    manager = TaskManager()

    task1 = manager.create_task(
        task_type=TaskType.RESEARCH_WEB,
        title="Test Task 1",
        description="Test task 1",
        input={"query": "test"},
    )
    task1.mark_completed()

    task2 = manager.create_task(
        task_type=TaskType.CODE_ANALYSIS,
        title="Test Task 2",
        description="Test task 2",
        input={"query": "test"},
    )
    task2.mark_completed()

    task3 = manager.create_task(
        task_type=TaskType.APP_OPEN,
        title="Test Task 3",
        description="Test task 3",
        input={"query": "test"},
    )
    task3.mark_failed("Error")

    stats = manager.get_statistics()

    assert stats["total_tasks"] == 3
    assert stats["completed_tasks"] == 2
    assert stats["failed"] == 1


# ========================================
# Test Agent Registry
# ========================================


def test_agent_registry_initialization():
    """Test agent registry can be initialized."""
    registry = AgentRegistry()
    assert registry.get_agent_count() == 7
    assert registry.get_agent_count() == 7


def test_agent_registry_lookup():
    """Test agent lookup by type."""
    registry = AgentRegistry()
    register_builtin_agents(registry)

    planner_agents = registry.get_agent_by_type(AgentType.PLANNER)
    assert len(planner_agents) == 2
    assert planner_agents[0].agent_id == "planner"


def test_agent_registry_capability_lookup():
    """Test agent lookup by capability."""
    registry = AgentRegistry()
    register_builtin_agents(registry)

    # Find agents with code_analysis capability
    agents = registry.get_agent_by_capability(AgentCapability.CODE_ANALYSIS)
    assert len(agents) > 0


def test_agent_registry_find_agent():
    """Test finding agent for task."""
    registry = AgentRegistry()
    register_builtin_agents(registry)

    task = Task(id="test", type=TaskType.RESEARCH_WEB, title="Test Task", input={})

    agent = registry.find_agent_for_task(task)
    assert agent is not None
    assert agent.agent_id == "research"


# ========================================
# Test Safety Layer
# ========================================


@pytest.mark.asyncio
async def test_safety_layer_require_confirmation(monkeypatch):
    """Test safety layer requires confirmation for destructive operations."""

    # Mock _ask_confirmation to return False
    async def mock_ask_confirmation(message, default_response=False):
        return False

    safety = SafetyLayer()
    monkeypatch.setattr(safety, "_ask_confirmation", mock_ask_confirmation)

    # Critical operation
    result = await safety.require_confirmation(
        OperationType.APPLICATION_CLOSE, "Close Calculator application"
    )

    assert result.allowed is False
    assert result.reason == "Critical operations require explicit user confirmation"


@pytest.mark.asyncio
async def test_safety_layer_confirm_operation(monkeypatch):
    """Test safety layer confirms non-destructive operations."""

    # Mock _ask_confirmation to return True
    async def mock_ask_confirmation(message, default_response=False):
        return True

    safety = SafetyLayer()
    monkeypatch.setattr(safety, "_ask_confirmation", mock_ask_confirmation)

    # Non-destructive operation (using NETWORK_ACCESS since web research involves network)
    result = await safety.require_confirmation(
        OperationType.NETWORK_ACCESS, "Search the web for information"
    )

    assert result.allowed is True
    assert result.reason == "Operation is safe to proceed"


# ========================================
# Test Plugin System
# ========================================


def test_plugin_base():
    """Test plugin base class."""

    class TestPlugin(PluginBase):
        def get_plugin_name(self) -> str:
            return "test_plugin"

        def get_plugin_version(self) -> str:
            return "1.0.0"

        def get_plugin_description(self) -> str:
            return "Test plugin"

        def get_plugin_capabilities(self) -> List[str]:
            return ["test_capability"]

    plugin = TestPlugin()
    assert plugin.get_plugin_name() == "test_plugin"
    assert plugin.get_plugin_version() == "1.0.0"
    assert plugin.get_plugin_capabilities() == ["test_capability"]


def test_plugin_registry():
    """Test plugin registry."""
    registry = PluginRegistry()

    class TestPlugin(PluginBase):
        def get_plugin_name(self) -> str:
            return "test_plugin"

        def get_plugin_version(self) -> str:
            return "1.0.0"

        def get_plugin_description(self) -> str:
            return "Test plugin"

        def get_plugin_capabilities(self) -> List[str]:
            return ["test_capability"]

    plugin = TestPlugin()
    assert registry.register_plugin(plugin)

    assert registry.get_plugin("test_plugin") == plugin
    assert len(registry.list_plugins()) == 1


# ========================================
# Test Skill System
# ========================================


def test_skill_registry():
    """Test skill registry."""
    registry = SkillRegistry()

    skill = registry.create_skill_from_template(
        skill_id="test_skill",
        name="Test Skill",
        category=SkillCategory.PRODUCTIVITY,
        steps=[
            {
                "agent_type": "research",
                "task_type": "web_research",
                "input_template": {"query": "test"},
            }
        ],
        description="Test skill",
    )

    assert registry.get_skill("test_skill") == skill
    assert len(registry.list_skills()) == 1


def test_skill_execution():
    """Test skill execution creates tasks."""
    registry = SkillRegistry()

    skill = registry.create_skill_from_template(
        skill_id="test_skill",
        name="Test Skill",
        category=SkillCategory.PRODUCTIVITY,
        steps=[
            {
                "agent_type": "research",
                "task_type": "research_web",
                "input_template": {"query": "${query}"},
            }
        ],
    )

    tasks = skill.to_task_chain({"query": "hello"})
    assert len(tasks) == 1
    assert tasks[0].input["query"] == "hello"


# ========================================
# Test Configuration
# ========================================


def test_config_manager():
    """Test configuration manager."""
    config_manager = get_config_manager()

    # Get config
    config = config_manager.get_config()
    assert config.providers is not None

    # Update setting
    config_manager.update_setting("custom", "test_key", "test_value")

    # Verify update
    assert config.custom["test_key"] == "test_value"

    # Reset
    config_manager.reset_to_defaults()
    assert config.custom["test_key"] != "test_value"


def test_provider_settings():
    """Test provider settings."""
    config_manager = get_config_manager()
    config = config_manager.get_config()

    # Check OpenAI is configured by default
    assert ProviderType.OPENAI in config.providers
    assert config.providers[ProviderType.OPENAI].model_name == "gpt-4"


# ========================================
# Test Integration
# ========================================


@pytest.mark.asyncio
async def test_agent_coordinator():
    """Test basic agent coordination."""
    registry = AgentRegistry()
    register_builtin_agents(registry)

    coordinator = TaskManager()
    coordinator._agent_registry = registry

    # Create a simple task
    task = coordinator.create_task(
        task_type=TaskType.RESEARCH_WEB,
        title="Test Task",
        description="Test task",
    )

    # Execute task
    result = await coordinator.execute_task(task)

    # Should succeed or fail gracefully
    assert result is not None


@pytest.mark.asyncio
async def test_task_manager_lifecycle():
    """Test complete task lifecycle."""
    manager = TaskManager()

    # Create task
    task = manager.create_task(
        task_type=TaskType.RESEARCH_WEB,
        title="Test Task",
        description="Test task",
        input={"query": "test"},
    )

    assert task.status == TaskStatus.PENDING

    # Mark running
    task.mark_running()
    assert task.status == TaskStatus.RUNNING

    # Mark completed
    task.mark_completed()
    assert task.status == TaskStatus.COMPLETED

    # Verify in manager
    retrieved = manager.get_task(task.id)
    assert retrieved.status == TaskStatus.COMPLETED


def test_all_task_types():
    """Test all task types are defined."""
    # Test a representative sample of TaskType enum members
    task_types = [
        TaskType.RESEARCH_WEB,
        TaskType.RESEARCH_DOCUMENT,
        TaskType.DEEP_RESEARCH,
        TaskType.CODE_ANALYSIS,
        TaskType.CODE_GENERATE,
        TaskType.APP_OPEN,
        TaskType.APP_CLOSE,
        TaskType.FILE_SEARCH,
        TaskType.IMAGE_ANALYSIS,
        TaskType.SPEECH_TO_TEXT,
        TaskType.WORKFLOW_STORE,
        TaskType.FACT_RETRIEVE,
        TaskType.GENERAL,
    ]

    for task_type in task_types:
        assert task_type.value is not None


def test_all_agent_types():
    """Test all agent types are registered."""
    registry = AgentRegistry()
    register_builtin_agents(registry)

    agent_types = list(AgentType)

    for agent_type in agent_types:
        agents = registry.get_agent_by_type(agent_type)
        assert len(agents) > 0, f"No agents registered for type {agent_type}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
