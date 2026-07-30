"""
Plugin System - Allows loading and executing custom plugins.

The Plugin System provides:
- Plugin loading from files
- Plugin registration and discovery
- Plugin execution in task context
- Plugin lifecycle management
- Plugin communication with agents
"""

from __future__ import annotations

from typing import Any, List, Optional, Type, Callable
import importlib
import importlib.util
from pathlib import Path
from abc import ABC, abstractmethod

from .task_model import Task, TaskOutput, TaskType


class PluginBase(ABC):
    """
    Base class for all plugins.

    Plugins can register with the agent system and be executed as tasks.
    """

    @abstractmethod
    def get_plugin_name(self) -> str:
        """Get the name of the plugin."""
        pass

    @abstractmethod
    def get_plugin_version(self) -> str:
        """Get the version of the plugin."""
        pass

    @abstractmethod
    def get_plugin_description(self) -> str:
        """Get the description of the plugin."""
        pass

    @abstractmethod
    def get_plugin_capabilities(self) -> List[str]:
        """Get list of capabilities provided by this plugin."""
        pass

    def on_load(self):
        """Called when plugin is loaded."""
        pass

    def on_unload(self):
        """Called when plugin is unloaded."""
        pass


class PluginContext:
    """
    Context passed to plugin execution.

    Provides access to agent system components.
    """

    def __init__(self, task_manager, agent_registry, knowledge_manager=None):
        self.task_manager = task_manager
        self.agent_registry = agent_registry
        self.knowledge_manager = knowledge_manager


class PluginRegistry:
    """
    Manages registered plugins.

    Features:
    - Plugin loading from files
    - Plugin registration
    - Plugin execution
    - Plugin lifecycle management
    """

    def __init__(self):
        """Initialize the plugin registry."""
        self._plugins: Dict[str, PluginBase] = {}
        self._contexts: Dict[str, PluginContext] = {}
        self._callbacks: List[Callable] = []

    def register_callback(self, callback: Callable):
        """Register a callback for plugin events."""
        self._callbacks.append(callback)

    def _notify_callback(self, event_type: str, data: dict):
        """Notify all callbacks of an event."""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception:
                pass

    def load_plugin_from_file(self, file_path: str) -> bool:
        """
        Load a plugin from a Python file.

        Args:
            file_path: Path to plugin file

        Returns:
            True if loaded successfully
        """
        try:
            module_name = Path(file_path).stem

            spec = importlib.util.spec_from_file_location(module_name, file_path)

            if spec is None or spec.loader is None:
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for PluginBase subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if isinstance(attr, type) and issubclass(attr, PluginBase):
                    if attr is PluginBase:
                        continue

                    plugin = attr()
                    self.register_plugin(plugin)

            self._notify_callback("load", {"file_path": file_path, "status": "success"})
            return True

        except Exception as e:
            self._notify_callback("load", {"file_path": file_path, "status": "failed", "error": str(e)})
            return False

    def load_plugin_directory(self, directory: str) -> int:
        """
        Load all plugins from a directory.

        Args:
            directory: Path to directory containing plugins

        Returns:
            Number of plugins loaded
        """
        directory = Path(directory)
        loaded = 0

        if not directory.exists():
            return loaded

        for plugin_file in directory.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue

            if self.load_plugin_from_file(str(plugin_file)):
                loaded += 1

        return loaded

    def register_plugin(self, plugin: PluginBase) -> bool:
        """
        Register a plugin.

        Args:
            plugin: Plugin instance to register

        Returns:
            True if registered successfully
        """
        try:
            plugin_name = plugin.get_plugin_name()

            # Initialize plugin
            plugin.on_load()

            self._plugins[plugin_name] = plugin
            self._notify_callback("register", {
                "plugin_name": plugin_name,
                "version": plugin.get_plugin_version(),
                "capabilities": plugin.get_plugin_capabilities()
            })

            return True

        except Exception as e:
            self._notify_callback("register", {"error": str(e)})
            return False

    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        Unregister a plugin.

        Args:
            plugin_name: Name of plugin to unregister

        Returns:
            True if unregistered successfully
        """
        if plugin_name not in self._plugins:
            return False

        try:
            plugin = self._plugins[plugin_name]
            plugin.on_unload()

            del self._plugins[plugin_name]
            self._notify_callback("unregister", {"plugin_name": plugin_name})

            return True

        except Exception:
            return False

    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """Get plugin by name."""
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> List[dict[str, Any]]:
        """List all registered plugins."""
        return [
            {
                "name": name,
                "version": plugin.get_plugin_version(),
                "description": plugin.get_plugin_description(),
                "capabilities": plugin.get_plugin_capabilities()
            }
            for name, plugin in self._plugins.items()
        ]

    def get_plugins_by_capability(self, capability: str) -> List[PluginBase]:
        """Get plugins that provide a specific capability."""
        return [
            plugin
            for plugin in self._plugins.values()
            if capability in plugin.get_plugin_capabilities()
        ]

    def execute_plugin(
        self,
        plugin_name: str,
        task: Task,
        context: PluginContext
    ) -> TaskOutput:
        """
        Execute a plugin.

        Args:
            plugin_name: Name of plugin to execute
            task: Task to execute
            context: Plugin context

        Returns:
            Task execution result
        """
        plugin = self._plugins.get(plugin_name)

        if not plugin:
            return TaskOutput(
                success=False,
                message=f"Plugin not found: {plugin_name}",
                error=f"No plugin registered with name '{plugin_name}'"
            )

        try:
            # Execute plugin
            result = self._execute_plugin_impl(plugin, task, context)

            return TaskOutput(
                success=result.success,
                message=result.message,
                data=result.data,
                error=result.error
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message=f"Plugin execution failed: {plugin_name}",
                error=str(e)
            )

    def _execute_plugin_impl(
        self,
        plugin: PluginBase,
        task: Task,
        context: PluginContext
    ) -> TaskOutput:
        """
        Execute plugin implementation.

        Args:
            plugin: Plugin instance
            task: Task to execute
            context: Plugin context

        Returns:
            Task execution result
        """
        # In production, this would invoke plugin's task handler
        # For demo, return a placeholder response
        return TaskOutput(
            success=True,
            message=f"Plugin '{plugin.get_plugin_name()}' executed",
            data={
                "plugin": plugin.get_plugin_name(),
                "task_type": task.type.value,
                "version": plugin.get_plugin_version()
            }
        )


class PluginAPI:
    """
    API provided to plugins for interacting with the system.
    """

    def __init__(self, plugin_registry: PluginRegistry, context: PluginContext):
        self.registry = plugin_registry
        self.context = context

    def execute_plugin(self, plugin_name: str, task: Task) -> TaskOutput:
        """Execute another plugin."""
        return self.registry.execute_plugin(plugin_name, task, self.context)

    def get_agent_for_capability(self, capability: str):
        """Get agent for a specific capability."""
        return self.context.agent_registry.find_agent_for_capability(capability)

    def get_task_manager(self):
        """Get task manager."""
        return self.context.task_manager

    def get_knowledge_manager(self):
        """Get knowledge manager."""
        return self.context.knowledge_manager


# Global plugin registry instance
_global_plugin_registry = None


def get_plugin_registry() -> PluginRegistry:
    """Get global plugin registry instance."""
    global _global_plugin_registry
    if _global_plugin_registry is None:
        _global_plugin_registry = PluginRegistry()
    return _global_plugin_registry
