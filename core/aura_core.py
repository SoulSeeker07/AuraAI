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

# Import Memory module for brain integration
try:
    from Memory import Memory
except ImportError:
    Memory = None

# Import research module types
try:
    from src.research import SearchMode, ConflictResolution, ResearchConfig
except ImportError:
    SearchMode = None
    ConflictResolution = None
    ResearchConfig = None

# Import planner module
try:
    from src.research.research_planner import ResearchPlanner
except ImportError:
    ResearchPlanner = None

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

    # Singleton pattern
    _instance: Optional['AuraCore'] = None
    _initialized: bool = False

    def __new__(cls, config: Optional[Dict[str, Any]] = None):
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls, config: Optional[Dict[str, Any]] = None) -> 'AuraCore':
        """Get or create the singleton AuraCore instance."""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Guard the WHOLE body — not just _initialize_components() — so a second
        # AuraCore() call anywhere in the codebase can't wipe out live state.
        if self._initialized:
            self._load_conversation_history()
            return

        self.config = config or {}
        project_root_input = self.config.get('project_root')
        if project_root_input is not None:
            if isinstance(project_root_input, str):
                self.project_root = Path(project_root_input)
            else:
                self.project_root = project_root_input
        else:
            self.project_root = Path(__file__).resolve().parent.parent
        self.workspace = self.config.get('workspace', str(self.project_root))

        self.chat_log_path = Path(self.config.get('data_path', self.project_root / "Data" / "ChatLog.json"))
        self.memory_db_path = Path(self.config.get('memory_db_path', self.project_root / "Memory.db"))

        self.components: Dict[str, ComponentStatus] = {}
        self.memory_enabled = True
        self.memory_stats = {}
        self.knowledge_enabled = True
        self.knowledge_stats = {}
        self.plugins = []
        self.plugin_count = 0
        self.workspace_aware = False
        self.workspace_info = {}
        self.multi_agent_status = AuraCoreStatus.READY
        self.multi_agent_orchestrator = None
        self.multi_agent_registry = None
        self.agent_runtime_status = AuraCoreStatus.READY
        self.agent_runtime = None

        self.research_enabled = False
        self.research_integration = None
        self._research_initialized = False

        self.planner_enabled = False
        self.planner = None
        self.workflow_engine_status = AuraCoreStatus.READY
        self.workflow_engine = None
        self.vision_enabled = False
        self.voice_enabled = False
        self.current_task: Optional[str] = None
        self.current_task_status: AuraCoreStatus = AuraCoreStatus.READY
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 100

        AuraCore._initialized = True
        self.groq_model = self.config.get('groq_model', 'llama-3.3-70b-versatile')
        self.groq_client = None
        self.llm_enabled = False
        self._init_llm()
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
        Send the user's message through the ConversationEngine,
        which handles intent detection, memory integration, and LLM response generation.

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
            # Use ConversationEngine to process the message with memory integration
            conversation_result = await self.conversation_engine.process(user_message)

            # Extract the AI's response text from the conversation result
            return conversation_result.text

        except Exception as e:
            logger.error(f"ConversationEngine processing failed: {e}", exc_info=True)
            return f"✗ Error processing message: {e}"

    def _initialize_components(self):
        """Initialize all core components."""
        logger.info("Initializing Aura Core...")

        # Brain (Memory + ConversationEngine) - must be first to create self.memory
        self._init_brain()

        # Memory - now self.memory exists
        self._init_memory()

        # Research Engine
        self._init_research()

        # Planner
        self._init_planner()

        # Knowledge
        self._init_knowledge()

        # Plugins
        self._init_plugins()

        # Workspace
        self._init_workspace()

        # Multi-Agent Intelligence
        self._init_multi_agent()

        # Agent Runtime
        self._init_agent_runtime()

        # Workflow Engine
        self._init_workflow()

        logger.info("Aura Core initialized successfully")

    def _init_memory(self):
        """Initialize memory system."""
        try:
            self.memory_enabled = True

            # Query actual memory statistics
            total_memories = self.memory.count_memories() if self.memory else 0
            num_categories = self.memory.count_categories() if self.memory else 0

            self.memory_stats = {
                'total_memories': total_memories,
                'num_categories': num_categories,
                'project': self.workspace
            }

            self.components['memory'] = ComponentStatus(
                name='Memory',
                status=AuraCoreStatus.READY,
                message=f'{total_memories} memories, {num_categories} categories'
            )
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory_enabled = False
            self.components['memory'] = ComponentStatus(
                name='Memory',
                status=AuraCoreStatus.ERROR,
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
                status=AuraCoreStatus.READY,
                message='Knowledge indexed'
            )
        except Exception as e:
            logger.error(f"Failed to initialize knowledge: {e}")
            self.knowledge_enabled = False
            self.components['knowledge'] = ComponentStatus(
                name='Knowledge',
                status=AuraCoreStatus.ERROR,
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
                status=AuraCoreStatus.READY,
                message=f'{self.plugin_count} plugins loaded'
            )
        except Exception as e:
            logger.error(f"Failed to initialize plugins: {e}")
            self.plugin_count = 0
            self.components['plugins'] = ComponentStatus(
                name='Plugins',
                status=AuraCoreStatus.ERROR,
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
                    status=AuraCoreStatus.READY,
                    message=f'{self.workspace_info["files"]} files, {self.workspace_info["folders"]} folders'
                )
            else:
                logger.warning(f"Workspace path does not exist: {self.workspace}")
                self.workspace_aware = False
                self.components['workspace'] = ComponentStatus(
                    name='Workspace',
                    status=AuraCoreStatus.ERROR,
                    message='Path does not exist',
                    loaded=False
                )
        except Exception as e:
            logger.error(f"Failed to initialize workspace: {e}")
            self.workspace_aware = False
            self.components['workspace'] = ComponentStatus(
                name='Workspace',
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def _init_brain(self):
        """Initialize brain with Memory and ConversationEngine."""
        # Static counter to track calls
        if not hasattr(self, '_brain_call_count'):
            self._brain_call_count = 0
        self._brain_call_count += 1
        logger.info(f"[_init_brain] ENTERING (call #{self._brain_call_count})")
        try:
            if Memory is None:
                raise ImportError("Memory module not available")

            # Create Memory instance
            self.memory = Memory(db_path=self.memory_db_path, chat_log_path=self.chat_log_path)

            # Create ConversationEngine
            from src.brain.conversation_engine import ConversationEngine
            from ai.provider_manager import ProviderManager

            # Build provider manager
            from src.ai.groq_provider import GroqProvider  # adjust path if it lives elsewhere

            provider_manager = ProviderManager(default_provider='groq')
            provider_manager.register('groq', GroqProvider(api_key=os.environ.get("GROQ_API_KEY", "")))

            # Create ConversationEngine
            self.conversation_engine = ConversationEngine(
                memory=self.memory,
                provider_manager=provider_manager,
                settings={
                    'provider': 'groq',
                    'model': self.groq_model,
                },
                model=self.groq_model,
                aura_core=self
            )

            self.brain_enabled = True
            self.components['brain'] = ComponentStatus(
                name='Brain',
                status=AuraCoreStatus.READY,
                message='Brain initialized with memory'
            )

            logger.info("Brain initialized successfully")
        except Exception as e:
            logger.exception("Failed to initialize brain")
            self.brain_enabled = False
            self.components['brain'] = ComponentStatus(
                name='Brain',
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def _init_research(self):
        """Initialize research engine for live data research."""
        # Static counter to track calls
        if not hasattr(self, '_research_call_count'):
            self._research_call_count = 0
        self._research_call_count += 1
        logger.info(
            f"[_init_research] ENTERING (call #{self._research_call_count}) - "
            f"research_enabled={self.research_enabled}, "
            f"research_integration is None={self.research_integration is None}, "
            f"_research_initialized={self._research_initialized}"
        )
        try:
            logger.info("[_init_research] Creating ResearchEngine...")

            # Import research engine
            from src.research import ResearchEngine, ResearchConfig

            research_settings = self.config.get('research_settings', {})

            # Create ResearchEngine
            research_engine = ResearchEngine(config=ResearchConfig(
                enabled=True,
                default_mode=SearchMode.STANDARD,
                default_max_results=research_settings.get('max_results', 10),
                cache_ttl=research_settings.get('cache_ttl', 1800),
                conflict_resolution=ConflictResolution.AUTO
            ))
            # Add unique identifier to track this instance
            research_engine.__id__ = f"research_engine_{id(self)}"
            logger.info(
                f"[_init_research] Created ResearchEngine with id={research_engine.__id__}, "
                f"object={research_engine}"
            )

            logger.info("[_init_research] Creating ResearchIntegration...")
            from src.brain.research_integration import ResearchIntegration
            self.research_integration = ResearchIntegration(research_engine)
            self.research_integration.__id__ = f"research_integration_{id(self)}"
            logger.info(
                f"[_init_research] Created ResearchIntegration with "
                f"id={self.research_integration.__id__}, object={self.research_integration}"
            )

            self.research_enabled = True
            self._research_initialized = True
            logger.info(
                f"[_init_research] Set research_enabled=True, "
                f"research_integration={self.research_integration}"
            )

            self.components['research'] = ComponentStatus(
                name='Research Engine',
                status=AuraCoreStatus.READY,
                message='Research engine initialized'
            )

            logger.info("Research engine initialized successfully")
        except ImportError as e:
            logger.error(f"[_init_research] ImportError caught: {e}")
            self.research_enabled = False
            self._research_initialized = False
            self.components['research'] = ComponentStatus(
                name='Research Engine',
                status=AuraCoreStatus.ERROR,
                message=f'Research module: {e}',
                loaded=False
            )
        except Exception as e:
            logger.exception(f"[_init_research] Exception caught: {type(e).__name__}: {e}")
            self.research_enabled = False
            self._research_initialized = False
            self.components['research'] = ComponentStatus(
                name='Research Engine',
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def is_research_needed(self, query: str) -> bool:
        """
        Check if research is needed for a query.

        Args:
            query: User query

        Returns:
            True if research is needed
        """
        if not self.research_enabled or self.research_integration is None:
            return False

        return self.research_integration.is_research_needed(query)

    def perform_research(self, query: str, mode: str = 'standard') -> Optional[Dict[str, Any]]:
        """
        Perform research and return results.

        Args:
            query: Research query
            mode: Search mode ('quick', 'standard', 'deep')

        Returns:
            Research results dictionary or None if failed
        """
        logger.info(f"[AuraCore] perform_research() called with query='{query}', mode='{mode}'")
        logger.info(
            f"[AuraCore] research_enabled={self.research_enabled}, "
            f"research_integration is None={self.research_integration is None}"
        )
        logger.info(f"[AuraCore] _research_initialized={self._research_initialized}")
        if self.research_integration and hasattr(self.research_integration, '__id__'):
            logger.info(f"[AuraCore] research_integration.id={self.research_integration.__id__}")
        if self.research_integration and hasattr(self.research_integration.research_engine, '__id__'):
            logger.info(
                f"[AuraCore] research_integration.research_engine.id="
                f"{self.research_integration.research_engine.__id__}"
            )

        if not self.research_enabled or self.research_integration is None:
            logger.warning("[AuraCore] Research is disabled or integration is None")
            return None

        # NOTE: was `from research import SearchMode` (wrong module path,
        # would raise ImportError). Fixed to match the top-of-file import.
        search_mode = SearchMode.STANDARD
        if mode == 'quick':
            search_mode = SearchMode.QUICK
        elif mode == 'deep':
            search_mode = SearchMode.DEEP

        logger.info(f"[AuraCore] Calling research_integration.perform_research() with mode={search_mode}")
        results = self.research_integration.perform_research(query, mode=search_mode)
        logger.info(
            f"[AuraCore] research_integration.perform_research() returned: "
            f"has_results={results.get('has_results', False) if results else False}"
        )
        return results

    def enhance_response_with_research(
        self,
        query: str,
        user_message: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Enhance a response with research findings.

        This method checks if research is needed, performs it, and
        returns a dict with the research findings and a flag indicating
        whether research was used.

        Args:
            query: Original query
            user_message: Full user message
            max_results: Maximum results to include

        Returns:
            Dict with research findings and status
        """
        if not self.research_enabled or self.research_integration is None:
            return {
                "research_used": False,
                "message": "Research not available"
            }

        return self.research_integration.enhance_response_with_research(
            query, user_message, max_results
        )

    def get_research_stats(self) -> Dict[str, Any]:
        """
        Get research engine statistics.

        Returns:
            Statistics dictionary
        """
        if not self.research_enabled or self.research_integration is None:
            return {
                "research_engine_initialized": False,
                "message": "Research not available"
            }

        return self.research_integration.get_research_stats()

    def _init_multi_agent(self):
        """Initialize multi-agent intelligence system."""
        try:
            from src.agents.agent_registry import AgentRegistry
            from src.agents.orchestrator import AgentOrchestrator
            from src.agents.agent_context import ContextManager

            # Create agent registry
            agent_registry = AgentRegistry()

            # Create orchestrator
            orchestrator = AgentOrchestrator(
                agent_registry=agent_registry,
                context_manager=ContextManager()
            )

            # Store orchestrator and registry
            self.multi_agent_orchestrator = orchestrator
            self.multi_agent_registry = agent_registry

            self.components['multi_agent'] = ComponentStatus(
                name='Multi-Agent Intelligence',
                status=AuraCoreStatus.READY,
                message='Multi-agent orchestrator initialized'
            )
        except Exception as e:
            logger.error(f"Failed to initialize multi-agent system: {e}")
            self.components['multi_agent'] = ComponentStatus(
                name='Multi-Agent Intelligence',
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def _init_agent_runtime(self):
        """Initialize agent runtime system."""
        try:
            from src.agents.agent_runtime import AgentRuntime

            # Create agent runtime
            agent_runtime = AgentRuntime()

            # Store agent runtime
            self.agent_runtime = agent_runtime

            self.components['agent_runtime'] = ComponentStatus(
                name='Agent Runtime',
                status=AuraCoreStatus.READY,
                message='Agent runtime initialized'
            )
        except Exception as e:
            logger.exception("Failed to initialize agent runtime")
            self.components['agent_runtime'] = ComponentStatus(
                name='Agent Runtime',
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False
            )

    def _init_workflow(self):
        """Initialize workflow engine system."""
        try:
            from src.workflows.workflow_engine import WorkflowEngine

            # Create workflow engine (agent_runtime will be None initially)
            workflow_engine = WorkflowEngine(agent_runtime=None)

            # Store workflow engine
            self.workflow_engine = workflow_engine

            self.components['workflow_engine'] = ComponentStatus(
                name='Workflow Engine',
                status=AuraCoreStatus.READY,
                message='Workflow engine initialized'
            )
        except Exception as e:
            logger.error(f"Failed to initialize workflow engine: {e}")
            self.components['workflow_engine'] = ComponentStatus(
                name='Workflow Engine',
                status=AuraCoreStatus.ERROR,
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
            'multi_agent': self.multi_agent_status.value,
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

        logger.info(f"Added {role} conversation: {content[:50]}... (Total: {len(self.conversation_history)})")

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
        return """Aura

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

            logger.info(f"Attempting to save {len(history_to_save)} conversation turns to {self.chat_log_path}")

            with open(self.chat_log_path, 'w', encoding='utf-8') as f:
                json.dump(history_to_save, f, indent=2, ensure_ascii=False)
                f.flush()  # Force write to disk
                os.fsync(f.fileno())  # Force sync to disk

            logger.info(f"Successfully saved {len(history_to_save)} conversation turns to disk")
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _init_planner(self):
        """Initialize planner system."""
        try:
            if ResearchPlanner is None:
                logger.warning("ResearchPlanner module not available")
                self.planner_enabled = False
                self.planner = None
                return

            self.planner_enabled = True
            self.planner = ResearchPlanner()
            self.components['planner'] = ComponentStatus(
                name='Planner',
                status=AuraCoreStatus.READY,
                message='ResearchPlanner initialized'
            )
            logger.info("ResearchPlanner initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ResearchPlanner: {e}")
            self.planner_enabled = False
            self.planner = None
            self.components['planner'] = ComponentStatus(
                name='Planner',
                status=AuraCoreStatus.ERROR,
                message=str(e)
            )

    def shutdown(self):
        """Shutdown Aura Core."""
        logger.info("Shutting down Aura Core...")
        self._save_conversation_history()
        self.clear_conversation_history()

    def __repr__(self):
        return f"AuraCore(project='{self.workspace}', plugins={self.plugin_count}, memory={self.memory_enabled})"


# ---------------------------------------------------------------------------
# Default instance helper
#
# IMPORTANT: nothing at module scope constructs AuraCore() anymore. Doing so
# used to run at import time — before main.py had a chance to pass in the
# real config — which silently consumed the one-shot singleton init with
# default settings. Construction now only happens the first time
# get_default_instance() is actually called (or when main.py explicitly
# constructs AuraCore(config) itself, which is the normal startup path).
# ---------------------------------------------------------------------------
_default_instance: Optional['AuraCore'] = None


def get_default_instance() -> Optional['AuraCore']:
    """Get or lazily create the default AuraCore instance."""
    global _default_instance
    if _default_instance is None:
        try:
            _default_instance = AuraCore()
        except Exception as e:
            logger.warning(f"Could not create default AuraCore instance: {e}")
            _default_instance = None
    return _default_instance