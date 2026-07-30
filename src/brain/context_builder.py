from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from brain.execution_state import ExecutionState

from core.memory.memory_manager import MemoryManager
from core.workspace.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds unified context for requests.
    
    This is critical - no component should fetch memory directly.
    Everything goes through ContextBuilder.
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        workspace_manager: WorkspaceManager,
        response_coordinator=None
    ):
        """
        Initialize Context Builder.
        
        Args:
            memory_manager: Memory manager for knowledge access
            workspace_manager: Workspace manager for workspace info
            response_coordinator: Response coordinator for formatting
        """
        self.memory_manager = memory_manager
        self.workspace = workspace_manager
        self.response_coordinator = response_coordinator or None
        logger.info("Context Builder initialized for AuraBrain")
    
    async def build(
        self,
        user_input: str,
        attachments: list = None,
        workspace_info: dict = None,
        conversation_id: str = None
    ) -> Context:
        """
        Build a unified context object.
        
        Args:
            user_input: User's current input
            attachments: List of attachments
            workspace_info: Additional workspace context
            conversation_id: Conversation identifier
        
        Returns:
            Unified Context object
        """
        logger.debug(f"Building context for: {user_input[:50]}...")
        
        # Initialize context
        context = Context()
        context.user_input = user_input
        context.attachments = attachments or []
        context.conversation_id = conversation_id
        context.workspace_info = workspace_info or {}
        
        # Build conversation history
        context.messages = await self._build_conversation_history(conversation_id)
        
        # Build memory facts
        context.memory_facts = await self._build_memory_facts()
        
        # Build workspace context
        context.workspace_context = await self._build_workspace_context()
        
        # Build provider settings
        context.provider_settings = await self._build_provider_settings()
        
        logger.debug(f"Context built: {len(context.messages)} messages, "
                    f"{len(context.memory_facts)} facts")
        
        return context
    
    async def _build_conversation_history(self, conversation_id: str = None) -> list:
        """Build conversation history."""
        messages = []
        
        try:
            # Get recent messages from memory manager
            if hasattr(self.memory_manager, 'get_recent_messages'):
                messages = self.memory_manager.get_recent_messages(limit=10)
        except Exception as e:
            logger.warning(f"Failed to load conversation history: {e}")
        
        return messages
    
    async def _build_memory_facts(self) -> list:
        """Build memory facts."""
        facts = []
        
        try:
            facts = self.memory_manager.get_all_facts()
        except Exception as e:
            logger.warning(f"Failed to load memory facts: {e}")
        
        return facts
    
    async def _build_workspace_context(self) -> dict:
        """Build workspace context."""
        workspace_context = {
            'current_directory': None,
            'git_repository': None,
            'clipboard': None,
            'running_processes': None,
            'active_window': None
        }
        
        try:
            workspace_context['current_directory'] = str(self.workspace.current_directory)
            workspace_context['git_repository'] = self.workspace.get_git_repo()
            workspace_context['clipboard'] = self.workspace.get_clipboard()
        except Exception as e:
            logger.warning(f"Failed to load workspace context: {e}")
        
        return workspace_context
    
    async def _build_provider_settings(self) -> dict:
        """Build provider settings."""
        settings = {
            'default_provider': 'groq',
            'temperature': 0.7,
            'max_tokens': 1024,
            'enable_streaming': True
        }
        
        try:
            if hasattr(self.workspace, 'get_provider_settings'):
                settings = self.workspace.get_provider_settings()
        except Exception as e:
            logger.warning(f"Failed to load provider settings: {e}")
        
        return settings


class Context:
    """Unified context object for a request."""
    
    def __init__(self):
        """Initialize context."""
        self.user_input: str = ""
        self.messages: list = []
        self.memory_facts: list = []
        self.workspace_context: dict = {}
        self.attachments: list = []
        self.provider_settings: dict = {}
        self.conversation_id: str = ""
        self.planned_tasks: list = []  # Tasks from planner
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"Context(conversation_id={self.conversation_id}, "
                f"{len(self.messages)} messages, "
                f"{len(self.memory_facts)} facts, "
                f"{len(self.attachments)} attachments)")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        return {
            'conversation_id': self.conversation_id,
            'user_input': self.user_input,
            'messages': self.messages,
            'memory_facts': self.memory_facts,
            'workspace_context': self.workspace_context,
            'attachments': self.attachments,
            'provider_settings': self.provider_settings,
            'planned_tasks': self.planned_tasks
        }

    def _format_web_results(self, web_results: list[dict[str, str]]) -> str:
        lines = [
            "Fresh web context is available from Aura's web lookup. Use these results for current facts. "
            "Do not say you lack live web access when answering this request. "
            "If the snippets conflict or are incomplete, say what is uncertain."
        ]
        for index, result in enumerate(web_results, start=1):
            lines.append(
                f"{index}. {result.get('title', '')}\n"
                f"URL: {result.get('url', '')}\n"
                f"Snippet: {result.get('snippet', '')}"
            )
        return "\n\n".join(lines)

    def _system_messages(self) -> list[ChatMessage]:
        now = dt.datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S")
        return [
            ChatMessage(
                "system",
                (
                    f"You are {self.assistant_name}, the AI brain for AuraAI. "
                    f"Be concise, helpful, and respectful. The user's name is {self.username}."
                ),
            ),
            ChatMessage("system", f"Current local time: {now}."),
        ]

    def _recent_messages(self, limit: int) -> list[ChatMessage]:
        messages = []
        for item in self.memory.recent_messages(limit=limit):
            role = cast(MessageRole, str(item["role"]))
            messages.append(ChatMessage(role, str(item["content"])))
        return messages
