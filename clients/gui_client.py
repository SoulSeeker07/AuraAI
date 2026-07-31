"""
AuraAI GUI Client

Graphical user interface client for AuraAI.
Provides API for QML interface to communicate with Aura Core.
"""

import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from core.aura_core import AuraCore
from core import logger


@dataclass
class ComponentStatus:
    """Status of a GUI component."""
    name: str
    status: str
    message: str
    loaded: bool


class GUIClient:
    """
    GUI client for AuraAI.
    Provides API for QML interface to communicate with Aura Core.
    """

    def __init__(self, aura_core: AuraCore):
        """
        Initialize GUI client.

        Args:
            aura_core: AuraCore instance
        """
        self.aura_core = aura_core

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all Aura Core components.

        Returns:
            Dictionary with status of all components
        """
        return self.aura_core.get_status()

    def get_component_status(self, component_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific component.

        Args:
            component_name: Name of component

        Returns:
            Component status dictionary or None
        """
        status = self.aura_core.get_status()
        components = status.get('components', {})

        if component_name in components:
            return {
                'name': component_name,
                'status': components[component_name]['status'],
                'message': components[component_name]['message'],
                'loaded': components[component_name]['loaded']
            }
        return None

    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics.

        Returns:
            Memory statistics dictionary
        """
        return self.aura_core.memory_stats

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """
        Get knowledge statistics.

        Returns:
            Knowledge statistics dictionary
        """
        return self.aura_core.knowledge_stats

    def get_workspace_info(self) -> Dict[str, Any]:
        """
        Get workspace information.

        Returns:
            Workspace information dictionary
        """
        return self.aura_core.workspace_info

    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific plugin.

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin status dictionary or None
        """
        return self.aura_core.get_plugin_status(plugin_name)

    def get_all_plugins_status(self) -> Dict[str, Any]:
        """
        Get status of all plugins.

        Returns:
            Dictionary with plugin statuses
        """
        return self.aura_core.get_all_plugins_status()

    def get_plugin_list(self) -> List[str]:
        """
        Get list of loaded plugins.

        Returns:
            List of plugin names
        """
        return self.aura_core.plugins.copy()

    def get_conversation_history(self, limit: int = 50) -> List[Dict[str, str]]:
        """
        Get conversation history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of conversation entries
        """
        history = self.aura_core.get_conversation_history()
        return history[-limit:] if limit > 0 else history

    def clear_conversation_history(self) -> bool:
        """
        Clear conversation history.

        Returns:
            True if successful
        """
        self.aura_core.clear_conversation_history()
        return True

    def add_conversation_entry(self, role: str, content: str) -> bool:
        """
        Add entry to conversation history.

        Args:
            role: 'user' or 'assistant'
            content: Message content

        Returns:
            True if successful
        """
        self.aura_core.add_to_conversation(role, content)
        return True

    def get_health_report(self) -> Dict[str, Any]:
        """
        Get health report for all components.

        Returns:
            Health report dictionary
        """
        return self.aura_core.get_health_report()

    def get_architecture_graph(self) -> str:
        """
        Get ASCII architecture graph.

        Returns:
            ASCII art representation
        """
        return self.aura_core.get_architecture_graph()

    def scan_workspace(self) -> Dict[str, Any]:
        """
        Scan workspace and update workspace info.

        Returns:
            Workspace scan results
        """
        return self.aura_core.scan_workspace()

    def analyze_code(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze code file.

        Args:
            file_path: Path to code file

        Returns:
            Analysis results
        """
        return self.aura_core.analyze_code(file_path)

    def fix_code(self, file_path: str) -> Dict[str, Any]:
        """
        Fix code issues in a file.

        Args:
            file_path: Path to code file

        Returns:
            Fix results
        """
        return self.aura_core.fix_code(file_path)

    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a specific plugin.

        Args:
            plugin_name: Name of plugin to load

        Returns:
            True if loaded successfully
        """
        return self.aura_core.load_plugin(plugin_name)

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a specific plugin.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if unloaded successfully
        """
        return self.aura_core.unload_plugin(plugin_name)

    def set_current_task(self, task: str) -> None:
        """
        Set the current task.

        Args:
            task: Task name/description
        """
        self.aura_core.set_current_task(task, AuraCoreStatus.READY)

    def update_task_status(self, status: str, message: str = "") -> None:
        """
        Update the current task status.

        Args:
            status: Status string
            message: Status message
        """
        status_enum = AuraCoreStatus(status)
        self.aura_core.update_task_status(status_enum, message)

    def get_current_task(self) -> Optional[str]:
        """
        Get current task.

        Returns:
            Current task name or None
        """
        return self.aura_core.current_task

    def get_tasks(self) -> List[str]:
        """
        Get list of all tasks.

        Returns:
            List of task names
        """
        # Get all component names except core components
        return [name for name in self.aura_core.components.keys()
                if name not in ['Memory', 'Knowledge', 'Plugins', 'Workspace']]

    def get_tasks_status(self) -> Dict[str, str]:
        """
        Get status of all tasks.

        Returns:
            Dictionary mapping task names to status strings
        """
        return {
            name: comp.status.value
            for name, comp in self.aura_core.components.items()
            if name not in ['Memory', 'Knowledge', 'Plugins', 'Workspace']
        }

    def get_available_commands(self) -> List[str]:
        """
        Get list of available commands.

        Returns:
            List of command names
        """
        commands = [
            'status', 'chat', 'memory', 'knowledge', 'workspace', 'plugins',
            'tasks', 'history', 'workflow', 'agents', 'engineering', 'doctor',
            'graph', 'help', 'reload', 'quit'
        ]
        return commands

    def get_command_help(self, command: str) -> Optional[Dict[str, str]]:
        """
        Get help information for a command.

        Args:
            command: Command name

        Returns:
            Help dictionary with description and usage
        """
        help_info = {
            'status': {
                'description': 'Show system status',
                'usage': 'status',
                'returns': 'Status dictionary'
            },
            'chat': {
                'description': 'Start interactive chat',
                'usage': 'chat',
                'returns': 'Chat session'
            },
            'memory': {
                'description': 'Show memory statistics',
                'usage': 'memory',
                'returns': 'Memory stats'
            },
            'knowledge': {
                'description': 'Show knowledge statistics',
                'usage': 'knowledge',
                'returns': 'Knowledge stats'
            },
            'workspace': {
                'description': 'Show workspace info',
                'usage': 'workspace',
                'returns': 'Workspace info'
            },
            'plugins': {
                'description': 'Show plugin status',
                'usage': 'plugins',
                'returns': 'Plugin status'
            },
            'tasks': {
                'description': 'Show task status',
                'usage': 'tasks',
                'returns': 'Task status'
            },
            'history': {
                'description': 'Show conversation history',
                'usage': 'history',
                'returns': 'History entries'
            },
            'workflow': {
                'description': 'Show workflow status',
                'usage': 'workflow',
                'returns': 'Workflow status'
            },
            'agents': {
                'description': 'Show agent information',
                'usage': 'agents',
                'returns': 'Agent info'
            },
            'engineering': {
                'description': 'Show engineering tools',
                'usage': 'engineering',
                'returns': 'Engineering tools'
            },
            'doctor': {
                'description': 'Run health check',
                'usage': 'doctor',
                'returns': 'Health report'
            },
            'graph': {
                'description': 'Show architecture graph',
                'usage': 'graph',
                'returns': 'Architecture diagram'
            },
            'help': {
                'description': 'Show help information',
                'usage': 'help',
                'returns': 'Help text'
            },
            'reload': {
                'description': 'Reload configuration',
                'usage': 'reload',
                'returns': 'None'
            },
            'quit': {
                'description': 'Exit application',
                'usage': 'quit',
                'returns': 'None'
            }
        }
        return help_info.get(command)

    def shutdown(self) -> None:
        """Shutdown Aura Core."""
        self.aura_core.shutdown()

    async def send_message(self, message: str) -> str:
        """
        Send a message and get AI response.

        Args:
            message: User message

        Returns:
            AI response
        """
        # Add to conversation
        self.aura_core.add_to_conversation('user', message)

        # Placeholder - in real implementation, this would call the AI API
        response = f"I received: {message}"
        self.aura_core.add_to_conversation('assistant', response)

        return response

    def get_project_root(self) -> str:
        """
        Get project root path.

        Returns:
            Project root path
        """
        return self.aura_core.project_root

    def get_workspace_path(self) -> str:
        """
        Get workspace path.

        Returns:
            Workspace path
        """
        return self.aura_core.workspace
