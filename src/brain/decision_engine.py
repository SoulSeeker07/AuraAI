"""
Decision Engine

Routes requests to appropriate handlers based on the request type and context.
This is what makes Aura intelligent - it decides what to do, not just executes.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.agent_registry import AgentRegistry
from agents.task_model import TaskInput
from brain.request import ActionType, AuraRequest
from brain.response_coordinator import ResponseCoordinator
from core.memory.memory_manager import MemoryManager
from core.tools.tool_router import ToolRouter
from core.workspace.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Routes requests to appropriate handlers.

    The Decision Engine is responsible for:
    - Analyzing request type and intent
    - Determining the best action (memory, tool, provider, etc.)
    - Making intelligent routing decisions
    - Avoiding unnecessary LLM calls

    Responsibilities:
        - Check if request is memory query
        - Check if request is tool execution request
        - Check if request is vision request
        - Check if request is voice request
        - Default to provider chat for general questions
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        tool_router: ToolRouter,
        workspace_manager: WorkspaceManager,
        response_coordinator: ResponseCoordinator = None,
        agent_registry: AgentRegistry = None,
        enable_logging: bool = True,
    ):
        """
        Initialize Decision Engine.

        Args:
            memory_manager: Memory manager for knowledge queries
            tool_router: Tool router for plugin/tool execution
            workspace_manager: Workspace manager for desktop/file access
            response_coordinator: Response coordinator for formatting
            agent_registry: Agent registry for intelligent routing
            enable_logging: Whether to log decisions
        """
        self.memory_manager = memory_manager
        self.tool_router = tool_router
        self.workspace = workspace_manager
        self.response_coordinator = response_coordinator
        self.agent_registry = agent_registry
        self.enable_logging = enable_logging

        if enable_logging:
            logger.info("Decision Engine initialized")

    def decide(self, request: AuraRequest, context: Any) -> Decision:
        """
        Decide what Aura should do with the request.

        This is the core decision-making logic. First checks AgentRegistry for
        intelligent routing, then falls back to default logic if no agent found.

        Args:
            request: Incoming request
            context: Built context object

        Returns:
            Decision with action type and parameters
        """
        # Priority 0: Check if we have an agent registry
        if self.agent_registry:
            logger.debug("AgentRegistry available, using agent-based routing")

            # Create TaskInput to determine task type
            task_input = TaskInput(
                data={"text": request.text, "attachments": request.attachments}
            )

            # Try to find appropriate agent for this task
            agent = self.agent_registry.find_agent_for_task(task_input)

            if agent:
                logger.debug(f"AgentRegistry found agent: {agent.agent_type.value}")
                # Route to the found agent
                return Decision(
                    action_type=ActionType.AGENT,
                    tool_name=agent.agent_type.value,
                    params={"agent": agent.agent_type.value},
                )

            logger.debug("AgentRegistry didn't find an agent for this task")

        # Priority 1: Memory queries
        if self._is_memory_query(request.text, context):
            logger.debug("Request identified as memory query")
            return Decision(action_type=ActionType.MEMORY)

        # Priority 2: Tool/Plugin execution requests
        if self._is_tool_request(request.text, context):
            tool_name, params = self._detect_tool(request.text, context)
            logger.debug(f"Request identified as tool request: {tool_name}")
            return Decision(
                action_type=ActionType.TOOL, tool_name=tool_name, params=params
            )

        # Priority 3: Vision requests
        if self._is_vision_request(request.text, request.attachments):
            logger.debug("Request identified as vision request")
            return Decision(action_type=ActionType.VISION)

        # Priority 4: Voice requests (basic detection)
        if request.source.value == "voice":
            logger.debug("Request identified as voice request")
            return Decision(action_type=ActionType.VOICE)

        # Priority 5: Provider chat (default for general questions)
        logger.debug("Request identified as general chat")
        return Decision(action_type=ActionType.PROVIDER)

    def _is_memory_query(self, text: str, context: Any) -> bool:
        """
        Check if this is a memory-related query.

        Examples:
            - "What do you remember about me?"
            - "Summarize my preferences"
            - "What facts do you have?"

        Args:
            text: User input text
            context: Context object

        Returns:
            True if this is a memory query
        """
        if not text:
            return False

        text_lower = text.lower().strip()

        # Direct memory query keywords
        memory_keywords = [
            "remember",
            "what do you know",
            "my facts",
            "profile",
            "preferences",
            "summarize",
            "recall",
            "retrieve",
            "what do you remember",
        ]

        # Check if any memory keyword is present
        if any(keyword in text_lower for keyword in memory_keywords):
            return True

        # Check for conversation context
        if hasattr(context, "conversation_id") and context.conversation_id:
            # If user asks about recent messages or conversation
            if "recent" in text_lower or "last" in text_lower:
                return True

        return False

    def _is_tool_request(self, text: str, context: Any) -> bool:
        """
        Check if this is a tool/plugin execution request.

        Examples:
            - "Open Chrome"
            - "Search for files"
            - "Read this document"
            - "Analyze this screenshot"

        Args:
            text: User input text
            context: Context object

        Returns:
            True if this is a tool request
        """
        if not text:
            return False

        text_lower = text.lower().strip()

        # Action/Verb indicators
        action_indicators = [
            "open",
            "close",
            "create",
            "delete",
            "search",
            "find",
            "read",
            "write",
            "save",
            "analyze",
            "execute",
            "run",
            "browse",
            "navigate",
            "launch",
            "start",
            "stop",
        ]

        # Check if any action indicator is present
        if any(indicator in text_lower for indicator in action_indicators):
            return True

        # Check for file/URL mentions
        if "file://" in text_lower or "http" in text_lower or ".py" in text_lower:
            return True

        return False

    def _detect_tool(self, text: str, context: Any) -> tuple[str, dict]:
        """
        Detect which tool should be executed.

        Args:
            text: User input text
            context: Context object

        Returns:
            Tuple of (tool_name, params)
        """
        text_lower = text.lower().strip()
        params = {}

        # Browser/URL handling
        if "http" in text_lower or "browse" in text_lower or "open" in text_lower:
            # Extract URL
            import re

            urls = re.findall(r"https?://[^\s]+", text)
            if urls:
                return ("browser", {"url": urls[0]})
            return ("browser", {"url": text})

        # File handling
        if "read file" in text_lower or "open file" in text_lower:
            return ("read_file", {})

        # Search handling
        if "search" in text_lower or "find" in text_lower:
            search_query = (
                text_lower.replace("search for", "").replace("find", "").strip()
            )
            return ("search", {"query": search_query})

        # Git handling
        if "git" in text_lower:
            return ("git", {})

        # Default to general tool execution
        # Try to extract the first noun as the tool name
        words = text_lower.split()
        if len(words) > 0:
            # Remove common stop words
            stop_words = {"the", "a", "an", "to", "for", "with", "on", "in", "at"}
            tool_candidates = [
                w for w in words if w not in stop_words and not w.endswith("?")
            ]

            if tool_candidates:
                return (tool_candidates[0], {})

        return ("general", {"text": text})

    def _is_vision_request(self, text: str, attachments: list) -> bool:
        """
        Check if this is a vision/image analysis request.

        Examples:
            - "Analyze this image"
            - "What's in this screenshot?"
            - "Read this document"

        Args:
            text: User input text
            attachments: List of attachments

        Returns:
            True if this is a vision request
        """
        # If request has image attachments, it's a vision request
        if attachments:
            return True

        # Check for vision-related keywords
        text_lower = text.lower().strip()
        vision_keywords = [
            "analyze image",
            "analyze screenshot",
            "read document",
            "what's in this",
            "describe this",
            "recognize",
            "ocr",
            "extract text from image",
            "image recognition",
        ]

        return any(keyword in text_lower for keyword in vision_keywords)


class Decision:
    """
    Represents a decision made by the Decision Engine.

    Attributes:
        action_type: What type of action to take (MEMORY, TOOL, PROVIDER, etc.)
        tool_name: Name of the tool to execute (if TOOL action)
        params: Parameters for the tool (if TOOL action)
    """

    def __init__(
        self, action_type: ActionType, tool_name: str = "", params: dict = None
    ):
        """
        Initialize a decision.

        Args:
            action_type: Type of action
            tool_name: Tool name (if applicable)
            params: Tool parameters (if applicable)
        """
        self.action_type = action_type
        self.tool_name = tool_name
        self.params = params or {}

    def __repr__(self) -> str:
        """String representation."""
        return f"Decision(action_type={self.action_type.value}, tool={self.tool_name})"
