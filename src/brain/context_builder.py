from __future__ import annotations

import datetime as dt
from typing import Any, cast

from ai.models import ChatMessage, MessageRole
from brain.models import ConversationAttachment, ConversationContext, Intent
from Memory import Memory


class ContextBuilder:
    def __init__(
        self,
        memory: Memory,
        settings: dict[str, Any],
        username: str = "User",
        assistant_name: str = "Aura",
    ):
        self.memory = memory
        self.settings = settings
        self.username = username
        self.assistant_name = assistant_name

    def build(
        self,
        user_input: str,
        intent: Intent,
        attachments: list[ConversationAttachment] | None = None,
        web_results: list[dict[str, str]] | None = None,
    ) -> ConversationContext:
        memory_context = self.memory.get_context()
        messages = self._system_messages()
        if memory_context:
            messages.append(ChatMessage("system", f"Known user memory:\n{memory_context}"))
        if web_results:
            messages.append(ChatMessage("system", self._format_web_results(web_results)))
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
