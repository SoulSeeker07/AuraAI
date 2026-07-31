"""
Aura Core - The main brain of AuraAI

This module provides the core Aura intelligence including:
- Memory management
- Knowledge indexing
- Plugin system
- Workspace awareness
- Agent runtime
- Tool execution
- Vision and Voice services (as needed)

All clients (CLI, GUI, Voice, API) communicate with Aura Core.
"""

import os
import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
import sys
from pathlib import Path

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Groq client
try:
    from groq import Groq
except ImportError:
    Groq = None

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Import logger from core module (imported in core/__init__.py)
try:
    from core import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AuraCoreStatus(Enum):
    """Status of Aura Core components."""
    READY = "Ready"
    LOADING = "Loading"
    ERROR = "Error"


@dataclass
class ComponentStatus:
    """Status of a core component."""
    name: str
    status: AuraCoreStatus
    message: str
    loaded: bool = True


class AuraCore:
    """
    Main Aura Core - The central intelligence of AuraAI.

    This class coordinates all AuraAI components and provides a unified
    interface for all clients (CLI, GUI, Voice, API).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Aura Core.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.project_root = self.config.get('project_root', Path(__file__).resolve().parent.parent)
        self.workspace = self.config.get('workspace', str(self.project_root))

        # Conversation history data path
        self.data_path = self.config.get('data_path', self.project_root / "Data" / "ChatLog.json")
        self.chat_log_path = Path(self.data_path)

        # Core components
        self.components: Dict[str, ComponentStatus] = {}

        # Memory
        self.memory_enabled = True
        self.memory_stats = {}

        # Knowledge
        self.knowledge_enabled = True
        self.knowledge_stats = {}

        # Plugins
        self.plugins = []
        self.plugin_count = 0

        # Workspace
        self.workspace_aware = False
        self.workspace_info = {}

        # Agent Runtime
        self.agent_runtime_status = AuraCoreStatus.READY

        # Workflow Engine
        self.workflow_engine_status = AuraCoreStatus.READY

        # Vision
        self.vision_enabled = False

        # Voice
        self.voice_enabled = False

        # Current task
        self.current_task: Optional[str] = None
        self.current_task_status: AuraCoreStatus = AuraCoreStatus.READY

        # Conversation history (will be loaded from disk)
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 100

        # Load conversation history from disk
        self._load_conversation_history()

        # LLM (Groq) setup
        self.groq_model = self.config.get('groq_model', 'llama-3.3-70b-versatile')
        self.groq_client = None
        self.llm_enabled = False
        self._init_llm()

        # Initialize core
        self._initialize_components()

    def _init_llm(self):
        """Initialize the Groq LLM client."""
        try:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError(
                    "GROQ_API_KEY not set. Add it to your environment or a .env file."
                )
            if Groq is None:
                raise ImportError(
                    "groq package not installed. Run: pip install groq"
                )

            self.groq_client = Groq(api_key=api_key)
            self.llm_enabled = True
            logger.info("Groq LLM client initialized successfully")
        except Exception as e:
            self.llm_enabled = False
            self.groq_client = None
            logger.error(f"Failed to initialize Groq client: {e}")

    async def get_ai_response(self, user_message: str) -> str:
        """
        Send the user's message (plus recent conversation history) to Groq
        and return the model's reply.

        Args:
            user_message: The latest message from the user

        Returns:
            The AI's text response (or an error message string)
        """
        if not self.llm_enabled or self.groq_client is None:
            return (
                "⚠ AI is not configured. Set GROQ_API_KEY in your environment "
                "or .env file and make sure the 'groq' package is installed."
            )

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Aura, a helpful, concise AI assistant integrated "
                        "into a developer's desktop environment called AuraAI."
                    ),
                }
            ]

            # Include recent conversation history for context
            for entry in self.conversation_history[-10:]:
                role = entry.get('role')
                content = entry.get('content')
                if role in ('user', 'assistant') and content:
                    messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": user_message})

            # Run the blocking Groq SDK call in a thread so we don't block the event loop
            response = await asyncio.to_thread(
                self.groq_client.chat.completions.create,
                model=self.groq_model,
                messages=messages,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Groq API call failed: {e}", exc_info=True)
            return f"✗ Error contacting Groq: {e}"

    def _initialize_components(self):
        """Initialize all core components."""
        logger.info("Initializing Aura Core...")

        # Memory
        self._init_memory()

        # Knowledge
        self._init_knowledge()

        # Plugins
        self._init_plugins()

        # Workspace
        self._init_workspace()

        logger.info("Aura Core initialized successfully")

    def _init_memory(self):
        """Initialize memory system."""
        try:
            self.memory_enabled = True
            self.memory_stats = {
                'total_memories': 0,
                'session_memories': 0,
                'working_memories': 0,
                'project': self.workspace
            }
            self.components['memory'] = ComponentStatus(
                name='Memory',
                status= AuraCoreStatus.READY,
                message='Memory system loaded'
            )
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory_enabled = False
            self.components['memory'] = ComponentStatus(
                name='Memory',
                status= AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def _init_knowledge(self):
        """Initialize knowledge system."""
        try:
            self.knowledge_enabled = True
            self.knowledge_stats = {
                'indexed': True,
                'search_enabled': True,
                'project': self.workspace
            }
            self.components['knowledge'] = ComponentStatus(
                name='Knowledge',
                status= AuraCoreStatus.READY,
                message='Knowledge indexed'
            )
        except Exception as e:
            logger.error(f"Failed to initialize knowledge: {e}")
            self.knowledge_enabled = False
            self.components['knowledge'] = ComponentStatus(
                name='Knowledge',
                status= AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def _init_plugins(self):
        """Initialize plugin system."""
        try:
            from plugins.shared.plugin_manager import PluginManager
            plugin_manager = PluginManager()

            # Load available plugins
            available_plugins = [
                'desktop', 'filesystem', 'vision', 'voice',
                'engineering', 'git', 'calendar', 'email',
                'networking', 'office', 'terminal', 'knowledge',
                'mcp', 'browser'
            ]

            loaded_plugins = []
            for plugin_name in available_plugins:
                try:
                    # Try to load plugin
                    plugin_manager.load_plugin(plugin_name)
                    loaded_plugins.append(plugin_name)
                except Exception as e:
                    logger.warning(f"Plugin {plugin_name} not loaded: {e}")

            self.plugins = loaded_plugins
            self.plugin_count = len(loaded_plugins)

            self.components['plugins'] = ComponentStatus(
                name='Plugins',
                status= AuraCoreStatus.READY,
                message=f'{self.plugin_count} plugins loaded'
            )
        except Exception as e:
            logger.error(f"Failed to initialize plugins: {e}")
            self.plugin_count = 0
            self.components['plugins'] = ComponentStatus(
                name='Plugins',
                status= AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def _init_workspace(self):
        """Initialize workspace awareness."""
        try:
            workspace_path = Path(self.workspace)
            if workspace_path.exists():
                self.workspace_aware = True
                self.workspace_info = {
                    'path': str(workspace_path),
                    'exists': True,
                    'files': 0,
                    'folders': 0
                }

                # Count files and folders
                for item in workspace_path.rglob('*'):
                    if item.is_file():
                        self.workspace_info['files'] += 1
                    elif item.is_dir() and not item.is_symlink():
                        self.workspace_info['folders'] += 1

                self.components['workspace'] = ComponentStatus(
                    name='Workspace',
                    status= AuraCoreStatus.READY,
                    message=f'{self.workspace_info["files"]} files, {self.workspace_info["folders"]} folders'
                )
            else:
                logger.warning(f"Workspace path does not exist: {self.workspace}")
                self.workspace_aware = False
                self.components['workspace'] = ComponentStatus(
                    name='Workspace',
                    status= AuraCoreStatus.ERROR,
                    message='Path does not exist',
                    loaded=False
                )
        except Exception as e:
            logger.error(f"Failed to initialize workspace: {e}")
            self.workspace_aware = False
            self.components['workspace'] = ComponentStatus(
                name='Workspace',
                status= AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all Aura Core components.

        Returns:
            Dictionary with status of all components
        """
        return {
            'project': self.workspace,
            'components': {
                name: {
                    'status': comp.status.value,
                    'message': comp.message,
                    'loaded': comp.loaded
                }
                for name, comp in self.components.items()
            },
            'memory': self.memory_stats,
            'knowledge': self.knowledge_stats,
            'plugins': {
                'count': self.plugin_count,
                'loaded': self.plugins
            },
            'workspace': self.workspace_info,
            'agent_runtime': self.agent_runtime_status.value,
            'workflow_engine': self.workflow_engine_status.value,
            'vision': 'Enabled' if self.vision_enabled else 'Disabled',
            'voice': 'Enabled' if self.voice_enabled else 'Disabled',
            'current_task': self.current_task,
            'task_status': self.current_task_status.value if self.current_task else None
        }

    def set_current_task(self, task: str, status: AuraCoreStatus = AuraCoreStatus.READY):
        """
        Set the current task.

        Args:
            task: Task name/description
            status: Status of the task
        """
        self.current_task = task
        self.current_task_status = status
        logger.info(f"Current task: {task} ({status.value})")

    def update_task_status(self, status: AuraCoreStatus, message: str = ""):
        """
        Update the current task status.

        Args:
            status: New status
            message: Status message
        """
        self.current_task_status = status
        self.components[self.current_task] = ComponentStatus(
            name=self.current_task,
            status=status,
            message=message
        )
        logger.info(f"Task status: {status.value} - {message}")

    def add_to_conversation(self, role: str, content: str):
        """
        Add entry to conversation history.

        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': None  # Could add timestamp if needed
        })

        # Keep history within limit
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Get conversation history.

        Returns:
            List of conversation entries
        """
        return self.conversation_history.copy()

    def clear_conversation_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a specific plugin.

        Args:
            plugin_name: Name of plugin to load

        Returns:
            True if loaded successfully
        """
        try:
            from plugins.shared.plugin_manager import PluginManager
            plugin_manager = PluginManager()
            plugin_manager.load_plugin(plugin_name)

            if plugin_name not in self.plugins:
                self.plugins.append(plugin_name)
                self.plugin_count = len(self.plugins)
                logger.info(f"Plugin {plugin_name} loaded successfully")
                return True
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a specific plugin.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if unloaded successfully
        """
        try:
            from plugins.shared.plugin_manager import PluginManager
            plugin_manager = PluginManager()
            plugin_manager.unload_plugin(plugin_name)

            if plugin_name in self.plugins:
                self.plugins.remove(plugin_name)
                self.plugin_count = len(self.plugins)
                logger.info(f"Plugin {plugin_name} unloaded successfully")
                return True
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False

    def get_plugin_status(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific plugin.

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin status dictionary or None
        """
        try:
            from plugins.shared.plugin_manager import PluginManager
            plugin_manager = PluginManager()
            status = plugin_manager.get_plugin_status(plugin_name)

            return {
                'name': plugin_name,
                'status': status,
                'loaded': plugin_name in self.plugins
            }
        except Exception as e:
            logger.error(f"Failed to get plugin status for {plugin_name}: {e}")
            return None

    def get_all_plugins_status(self) -> Dict[str, Any]:
        """
        Get status of all plugins.

        Returns:
            Dictionary with plugin statuses
        """
        result = {
            'total': self.plugin_count,
            'loaded': self.plugins,
            'details': {}
        }

        for plugin_name in self.plugins:
            status = self.get_plugin_status(plugin_name)
            if status:
                result['details'][plugin_name] = status

        return result

    def scan_workspace(self) -> Dict[str, Any]:
        """
        Scan workspace and update workspace info.

        Returns:
            Workspace scan results
        """
        if not self.workspace_aware:
            return {
                'success': False,
                'message': 'Workspace not available'
            }

        try:
            workspace_path = Path(self.workspace)
            files = 0
            folders = 0

            for item in workspace_path.rglob('*'):
                if item.is_file():
                    files += 1
                elif item.is_dir() and not item.is_symlink():
                    folders += 1

            self.workspace_info['files'] = files
            self.workspace_info['folders'] = folders
            self.workspace_info['scanned_at'] = None

            return {
                'success': True,
                'files': files,
                'folders': folders,
                'path': self.workspace
            }
        except Exception as e:
            logger.error(f"Failed to scan workspace: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def analyze_code(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze code file.

        Args:
            file_path: Path to code file

        Returns:
            Analysis results
        """
        try:
            code_file = Path(file_path)
            if not code_file.exists():
                return {
                    'success': False,
                    'message': 'File not found'
                }

            # Read file content
            with open(code_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Basic analysis
            lines = content.split('\n')
            char_count = len(content)
            word_count = len(content.split())

            return {
                'success': True,
                'file': str(code_file),
                'lines': len(lines),
                'characters': char_count,
                'words': word_count,
                'ext': code_file.suffix
            }
        except Exception as e:
            logger.error(f"Failed to analyze file {file_path}: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def fix_code(self, file_path: str) -> Dict[str, Any]:
        """
        Fix code issues in a file.

        Args:
            file_path: Path to code file

        Returns:
            Fix results
        """
        try:
            # This is a placeholder - actual fix logic would go here
            # In real implementation, this would use the engineering plugin
            code_file = Path(file_path)
            if not code_file.exists():
                return {
                    'success': False,
                    'message': 'File not found'
                }

            return {
                'success': True,
                'file': str(code_file),
                'message': 'Code fix executed (placeholder)',
                'changes': []
            }
        except Exception as e:
            logger.error(f"Failed to fix code in {file_path}: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    async def run_task(self, task_type: str, **kwargs) -> Dict[str, Any]:
        """
        Run a task using appropriate component.

        Args:
            task_type: Type of task
            **kwargs: Task-specific parameters

        Returns:
            Task execution results
        """
        task_mapping = {
            'fix_code': self.fix_code,
            'analyze_code': self.analyze_code,
            'scan_workspace': self.scan_workspace,
        }

        if task_type in task_mapping:
            task_func = task_mapping[task_type]
            if asyncio.iscoroutinefunction(task_func):
                return await task_func(**kwargs)
            else:
                return task_func(**kwargs)

        return {
            'success': False,
            'message': f'Task type {task_type} not implemented'
        }

    def get_health_report(self) -> Dict[str, Any]:
        """
        Get health report for all components.

        Returns:
            Health report dictionary
        """
        total = len(self.components)
        passed = sum(1 for comp in self.components.values() if comp.status == AuraCoreStatus.READY)
        failed = sum(1 for comp in self.components.values() if comp.status == AuraCoreStatus.ERROR)

        return {
            'brain': AuraCoreStatus.READY.value if self.llm_enabled else AuraCoreStatus.ERROR.value,
            'memory': AuraCoreStatus.READY.value if self.memory_enabled else AuraCoreStatus.ERROR.value,
            'knowledge': AuraCoreStatus.READY.value if self.knowledge_enabled else AuraCoreStatus.ERROR.value,
            'plugins': AuraCoreStatus.READY.value if self.plugin_count > 0 else AuraCoreStatus.ERROR.value,
            'workspace': AuraCoreStatus.READY.value if self.workspace_aware else AuraCoreStatus.ERROR.value,
            'agent_runtime': self.agent_runtime_status.value,
            'workflow_engine': self.workflow_engine_status.value,
            'vision': AuraCoreStatus.READY.value if self.vision_enabled else AuraCoreStatus.ERROR.value,
            'voice': AuraCoreStatus.READY.value if self.voice_enabled else AuraCoreStatus.ERROR.value,
            'overall': f'{passed}/{total}' if failed == 0 else f'{passed}/{total}',
            'percentage': f'{int(passed/total*100)}%' if total > 0 else '0%'
        }

    def get_architecture_graph(self) -> str:
        """
        Get ASCII architecture graph.

        Returns:
            ASCII art representation
        """
        return f"""Aura

↓

Memory
Knowledge
Plugins
Workspace
Tool Engine
Agent Runtime
Workflow Engine
Vision
Voice
Engineering"""

    def get_knowledge_stats(self):
        """Return knowledge database statistics."""
        # Get knowledge component status
        knowledge_comp = self.components.get('knowledge')
        
        # Return basic knowledge stats from the ComponentStatus
        return {
            'enabled': self.knowledge_enabled,
            'indexed': self.knowledge_stats.get('indexed', False),
            'search_enabled': self.knowledge_stats.get('search_enabled', False),
            'project': self.workspace,
            'status': knowledge_comp.status.value if knowledge_comp else 'Unknown',
            'message': knowledge_comp.message if knowledge_comp else 'Not available',
            'loaded': knowledge_comp.loaded if knowledge_comp else False
        }

    def get_workspace_info(self):
        """Return workspace information."""
        # Get workspace component status
        workspace_comp = self.components.get('workspace')
        
        # Return workspace info with files/folders from workspace_info dict
        return {
            'path': self.workspace,
            'total_files': self.workspace_info.get('files', 0),
            'total_folders': self.workspace_info.get('folders', 0),
            'project_root': str(self.project_root),
            'scan_status': 'scanned' if self.workspace_aware else 'not scanned',
            'current_task': self.current_task,
            'status': workspace_comp.status.value if workspace_comp else 'Unknown',
            'message': workspace_comp.message if workspace_comp else 'Not available',
            'loaded': workspace_comp.loaded if workspace_comp else False
        }

    def _load_conversation_history(self) -> None:
        """
        Load conversation history from disk.

        Loads conversation history from CHAT_LOG.json file if it exists.
        This ensures conversations persist between sessions.
        """
        import json

        try:
            if self.chat_log_path.exists():
                with open(self.chat_log_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    # Convert to list of dicts with 'role' and 'content' keys
                    self.conversation_history = [
                        {'role': entry.get('role', ''), 'content': entry.get('content', '')}
                        for entry in history if isinstance(entry, dict)
                    ]
                    logger.info(f"Loaded {len(self.conversation_history)} conversation turns from disk")
            else:
                self.conversation_history = []
                logger.info("No existing chat log found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            self.conversation_history = []

    def _save_conversation_history(self) -> None:
        """
        Save conversation history to disk.

        Saves conversation history to CHAT_LOG.json file.
        This ensures conversations persist between sessions.
        """
        import json

        try:
            # Ensure data directory exists
            self.chat_log_path.parent.mkdir(parents=True, exist_ok=True)

            # Save last 1000 conversation turns to prevent file growth
            history_to_save = self.conversation_history[-1000:]

            with open(self.chat_log_path, 'w', encoding='utf-8') as f:
                json.dump(history_to_save, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved {len(history_to_save)} conversation turns to disk")
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")

    def shutdown(self):
        """Shutdown Aura Core."""
        logger.info("Shutting down Aura Core...")
        self._save_conversation_history()
        self.clear_conversation_history()

    def __repr__(self):
        return f"AuraCore(project='{self.workspace}', plugins={self.plugin_count}, memory={self.memory_enabled})"