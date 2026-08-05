from __future__ import annotations

import os
import sys
from pathlib import Path

from Memory import CHAT_LOG_FILE, MEMORY_DB, Memory, MemoryFact

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    dotenv_values = None


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ai.registry import build_provider_manager
from brain.conversation_engine import ConversationEngine
from brain.web_search import WebSearchClient


def _load_env() -> dict[str, str]:
    env = dict(os.environ)
    if dotenv_values is not None:
        env.update({k: v for k, v in dotenv_values(PROJECT_ROOT / ".env").items() if v})
    return env


class ChatBot:
    """Compatibility facade over Aura's Conversation Engine."""

    def __init__(
        self,
        db_path: Path | str = MEMORY_DB,
        chat_log_path: Path | str = CHAT_LOG_FILE,
        model: str | None = None,
        memory: Memory | None = None,
    ):
        self.env = _load_env()
        self.model = model or self.env.get("AURA_GROQ_MODEL", "openai/gpt-oss-120b")
        self.provider_name = self.env.get("AURA_AI_PROVIDER", "groq")
        self.username = self.env.get("Username", "User")
        self.assistant_name = self.env.get("Assistantname", "Aura")
        self.memory = memory or Memory(db_path=db_path, chat_log_path=chat_log_path)
        self.provider_manager = build_provider_manager(
            self.env, default_provider=self.provider_name
        )
        self.web_search = WebSearchClient(
            google_api_key=self.env.get("GOOGLE_SEARCH_API_KEY", ""),
            google_search_engine_id=self.env.get("GOOGLE_SEARCH_ENGINE_ID", ""),
        )
        self.engine = ConversationEngine(
            memory=self.memory,
            provider_manager=self.provider_manager,
            settings={
                "provider": self.provider_name,
                "model": self.model,
                "web_search_enabled": self.env.get(
                    "AURA_WEB_SEARCH_ENABLED", "true"
                ).lower()
                == "true",
            },
            username=self.username,
            assistant_name=self.assistant_name,
            model=self.model,
            web_search=self.web_search,
        )

    def ask(self, query: str) -> str:
        return self.engine.process(query).text

    def ask_about_image(self, query: str, image_path: Path | str) -> str:
        attachment = self.engine.make_image_attachment(image_path)
        return self.engine.process(query, attachments=[attachment]).text

    def remember(self, text: str) -> list[MemoryFact]:
        return self.memory.remember(text)

    def forget(self, text: str) -> int:
        return self.memory.forget(text)

    def summarize(self) -> str:
        return self.memory.summarize()

    def get_context(self) -> str:
        return self.memory.get_context()

    def search_memory(self, text: str = "") -> list[MemoryFact]:
        return self.memory.search(text)


_default_bot: ChatBot | None = None


def get_default_bot() -> ChatBot:
    global _default_bot
    if _default_bot is None:
        _default_bot = ChatBot()
    return _default_bot


def ask(query: str) -> str:
    """Convenience helper for callers that do not need to manage a ChatBot instance."""
    return get_default_bot().ask(query)


if __name__ == "__main__":
    bot = get_default_bot()
    while True:
        user_query = input("Ask: ")
        print(bot.ask(user_query))
