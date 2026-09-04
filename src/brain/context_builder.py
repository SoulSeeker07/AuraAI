from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any, cast

from ai.models import ChatMessage, MessageRole
from brain.models import ConversationAttachment, ConversationContext, Intent
from Memory import Memory

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds unified context for requests.

    Supports two modes:
    - Conversation mode: ContextBuilder(memory, settings, username, assistant_name)
    - AuraBrain mode: ContextBuilder(memory_manager=..., workspace_manager=..., ...)
    """

    def __init__(
        self,
        memory: Memory | None = None,
        settings: dict[str, Any] | None = None,
        username: str = "User",
        assistant_name: str = "Aura",
        *,
        memory_manager: Any = None,
        workspace_manager: Any = None,
        response_coordinator: Any = None,
    ):
        self._aura_mode = workspace_manager is not None or response_coordinator is not None

        # TODO(M2): Once M1 is stable, remove old `self.memory` from ContextBuilder
        # and rely exclusively on `memory_manager`.
        self.memory = memory
        self.memory_manager = memory_manager
        self.settings = settings or {}
        self.username = username
        self.assistant_name = assistant_name

        if self._aura_mode:
            self.workspace = workspace_manager
            self.response_coordinator = response_coordinator
            self.assistant_name = assistant_name or "Aura"
            logger.info(f"Context Builder initialized for {self.assistant_name}")

    def build(
        self,
        user_input: str,
        intent: Intent,
        attachments: list[ConversationAttachment] | None = None,
        web_results: list[dict[str, str]] | None = None,
    ) -> ConversationContext:
        """Build context for ConversationEngine."""
        if self._aura_mode:
            raise RuntimeError("Use build_aura() in AuraBrain mode")

        memory_context = self.memory.get_context() if self.memory else ""
        messages = self._system_messages()

        # Inject deterministic ProfileMemory facts (Tier 3: Identity & Preferences)
        try:
            from src.memory.profile_memory import ProfileMemory
            prof_inst = ProfileMemory.get_instance()
            identity = prof_inst.get_identity()
            prefs = prof_inst.get_preferences()
            if identity or prefs:
                prof_lines = []
                if identity:
                    prof_lines.append(f"Identity: {identity}")
                if prefs:
                    prof_lines.append(f"Preferences: {prefs}")
                messages.append(
                    ChatMessage("system", "Verified User Profile (Deterministic):\n" + "\n".join(prof_lines))
                )
        except Exception as e:
            logger.debug(f"[ContextBuilder] ProfileMemory injection skipped: {e}")

        if memory_context:
            messages.append(
                ChatMessage("system", f"Known user memory:\n{memory_context}")
            )
        if web_results:
            messages.append(
                ChatMessage("system", self._format_web_results(web_results))
            )

        # Check for relevant RAG document context only when query warrants it
        if self._should_query_rag(user_input):
            try:
                from knowledge.rag_service import RAGService
                rag_context = RAGService.get_instance().get_relevant_context(user_input)
                if rag_context:
                    messages.append(
                        ChatMessage("system", f"Retrieved Document Knowledge:\n{rag_context}")
                    )
            except Exception:
                pass
            
        if getattr(self, "memory_manager", None):
            mgr_msgs = self.memory_manager.get_context_messages(user_input)
            for m in mgr_msgs:
                role = cast(MessageRole, str(m.get("role", "user")))
                messages.append(ChatMessage(role, str(m.get("content", ""))))
        else:
            messages.extend(self._recent_messages(limit=12))
            
        messages.append(ChatMessage("user", user_input))

        return ConversationContext(
            user_input=user_input,
            intent=intent,
            messages=messages,
            attachments=attachments or [],
            memory=memory_context,
            settings=self.settings,
            web_results=web_results or [],
            metadata={"created_at": dt.datetime.now().isoformat(timespec="seconds")},
        )

    async def build_aura(
        self,
        user_input: str,
        attachments: list | None = None,
        workspace_info: dict | None = None,
        conversation_id: str | None = None,
    ) -> Context:
        """Build context for AuraBrain."""
        if not self._aura_mode:
            raise RuntimeError("build_aura() requires AuraBrain mode initialization")

        logger.debug(f"Building context for: {user_input[:50]}...")

        context = Context()
        context.user_input = user_input
        context.attachments = attachments or []
        context.conversation_id = conversation_id or ""
        context.workspace_info = workspace_info or {}
        context.metadata = {
            "created_at": dt.datetime.now().isoformat(timespec="seconds")
        }

        context.messages = await self._build_conversation_history(conversation_id)
        context.memory_facts = await self._build_memory_facts()
        context.workspace_context = await self._build_workspace_context()
        context.provider_settings = await self._build_provider_settings()

        logger.debug(
            f"Context built: {len(context.messages)} messages, "
            f"{len(context.memory_facts)} facts"
        )

        return context

    async def _build_conversation_history(
        self, conversation_id: str | None = None
    ) -> list:
        """Build conversation history."""
        messages = []

        try:
            if hasattr(self.memory_manager, "get_recent_messages"):
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
            "current_directory": None,
            "git_repository": None,
            "clipboard": None,
            "running_processes": None,
            "active_window": None,
        }

        try:
            workspace_context["current_directory"] = str(
                self.workspace.current_directory
            )
            workspace_context["git_repository"] = self.workspace.get_git_repo()
            workspace_context["clipboard"] = self.workspace.get_clipboard()
        except Exception as e:
            logger.warning(f"Failed to load workspace context: {e}")

        return workspace_context

    async def _build_provider_settings(self) -> dict:
        """Build provider settings."""
        settings = {
            "default_provider": "groq",
            "temperature": 0.7,
            "max_tokens": 1024,
            "enable_streaming": True,
        }

        try:
            if hasattr(self.workspace, "get_provider_settings"):
                settings = self.workspace.get_provider_settings()
        except Exception as e:
            logger.warning(f"Failed to load provider settings: {e}")

        return settings

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
        user_name = self.username
        if self.memory:
            stored_name = self.memory.fact_value("profile", "name") or self.memory.fact_value("person", "name")
            if stored_name:
                user_name = stored_name
        return [
            ChatMessage(
                "system",
                (
                    f"You are {self.assistant_name}, the proactive personal AI companion for {user_name}.\n"
                    "### Core Behavioral Guidelines:\n"
                    "1. **Concise & Direct Responses**: Give straightforward, helpful, and natural answers without conversational filler, boilerplate, or robotic commentary.\n"
                    "2. **Speech & Translation Directness**: When asked to translate, speak, or say a phrase in any language (such as Hindi, Kannada, etc.), output ONLY the direct, natural translation/phrase in that language. Do NOT add pronunciation guides, phonetic brackets, or meta-explanations (like 'feed this into a TTS engine') unless explicitly asked.\n"
                    "3. **Localization & Regional E-Commerce (India / INR / Amazon.in)**: The user is located in India. Always default to Indian market prices in Indian Rupees (INR / ₹) and Indian regional platforms (e.g. Amazon.in, Flipkart) for product, pricing, and shopping queries unless the user specifically specifies another country or currency (such as US, UK, or dollars).\n"
                    "4. **Truthfulness & Telemetry Honesty**: NEVER fabricate, hallucinate, or make up device statuses, connected peripherals, hardware battery levels, or system telemetry that have not been provided in your system context. If live system information is not available, state honestly that the live telemetry is not available."
                ),
            ),
            ChatMessage("system", f"Current local time: {now} (IST, India)."),
        ]

    def _recent_messages(self, limit: int) -> list[ChatMessage]:
        if not self.memory:
            return []
        messages = []
        for item in self.memory.recent_messages(limit=limit):
            role = cast(MessageRole, str(item["role"]))
            messages.append(ChatMessage(role, str(item["content"])))
        return messages

    def _should_query_rag(self, user_input: str) -> bool:
        """Determine if a user query requires RAG vector document search."""
        clean = user_input.lower().strip(" ?!.`'\"~@#$%^&*()_+-=[]{}|;:,<>/\t\r\n")
        if not clean:
            return False

        # Fast skip for short greetings, salutations, or simple system phrases
        if clean in {
            "hi", "hello", "hey", "hey aura", "hi aura", "hello aura",
            "good morning", "good evening", "good afternoon", "good night",
            "how are you", "what's up", "whats up", "sup", "thanks", "thank you",
            "bye", "goodbye", "ok", "okay", "yes", "no", "cool", "great",
            "help", "status", "say hello", "say hi", "ping", "test"
        }:
            return False

        if len(clean.split()) <= 2 and not any(w in clean for w in ("doc", "file", "pdf", "cv", "resume")):
            return False

        doc_keywords = {
            "resume", "cv", "pdf", "docx", "document", "file", "files", "notes",
            "project", "skills", "experience", "education", "report",
            "docs", "documentation", "portfolio", "certifications", "paper",
            "spec", "guide", "summary", "contract", "invoice", "receipt"
        }
        tokens = set(re.findall(r"\w+", clean))
        if tokens & doc_keywords:
            return True

        if len(clean.split()) >= 4 and any(clean.startswith(w) for w in ("what", "who", "where", "how", "tell me", "summarize", "find", "search")):
            return True

        return False


class Context:
    """Unified context object for AuraBrain requests."""

    def __init__(self):
        self.user_input: str = ""
        self.messages: list = []
        self.memory_facts: list = []
        self.workspace_context: dict = {}
        self.attachments: list = []
        self.provider_settings: dict = {}
        self.conversation_id: str = ""
        self.workspace_info: dict = {}
        self.planned_tasks: list = []
        self.metadata: dict = {}

    def __repr__(self) -> str:
        return (
            f"Context(conversation_id={self.conversation_id}, "
            f"{len(self.messages)} messages, "
            f"{len(self.memory_facts)} facts, "
            f"{len(self.attachments)} attachments)"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_input": self.user_input,
            "messages": self.messages,
            "memory_facts": self.memory_facts,
            "workspace_context": self.workspace_context,
            "workspace_info": self.workspace_info,
            "attachments": self.attachments,
            "provider_settings": self.provider_settings,
            "planned_tasks": self.planned_tasks,
            "metadata": self.metadata,
        }
