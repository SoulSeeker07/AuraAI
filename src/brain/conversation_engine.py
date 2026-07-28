from __future__ import annotations

import datetime as dt
import mimetypes
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ai.exceptions import ProviderError
from ai.models import ChatRequest, VisionRequest
from ai.provider_manager import ProviderManager
from brain.context_builder import ContextBuilder
from brain.intent_router import IntentRouter
from brain.models import (
    ConversationAttachment,
    ConversationContext,
    ConversationResult,
    Intent,
    image_attachment_from_conversation,
)
from brain.web_search import WebSearchClient
from brain.deep_research_manager import DeepResearchManager
from brain.models import WebSearchResultSimple, DeepResearchResult, IntentName
from Memory import Memory, MemoryFact


class ConversationEngine:
    def __init__(
        self,
        memory: Memory,
        provider_manager: ProviderManager,
        settings: dict[str, Any] | None = None,
        username: str = "User",
        assistant_name: str = "Aura",
        model: str | None = None,
        web_search: WebSearchClient | None = None,
        deep_research_enabled: bool = True,
    ):
        self.memory = memory
        self.provider_manager = provider_manager
        self.settings = settings or {}
        self.model = model
        self.intent_router = IntentRouter(memory)
        self.context_builder = ContextBuilder(memory, self.settings, username, assistant_name)
        self.web_search = web_search or WebSearchClient()
        self._cancel_requested = False
        self.deep_research_manager = (
            DeepResearchManager(provider_manager) if deep_research_enabled else None
        )
        self._use_deep_research = deep_research_enabled

    def process(
        self,
        user_input: str,
        attachments: list[ConversationAttachment] | None = None,
    ) -> ConversationResult:
        user_input = user_input.strip()
        if not user_input:
            return ConversationResult("Ask me something and I will help.", Intent("provider_chat"))

        intent = self.intent_router.detect(user_input, attachments)
        
        # Check if deep research should be used
        if intent.name == "deep_research" and self._use_deep_research and self.deep_research_manager:
            deep_research_results = self._perform_deep_research(user_input, intent)
            web_results = self._format_deep_research_results(deep_research_results)
        else:
            web_results = self._lookup_web(user_input, intent)
        
        context = self.context_builder.build(user_input, intent, attachments, web_results)

        if intent.name == "remember_fact":
            facts = list(intent.data.get("facts", []))
            self.intent_router.remember_detected_facts(facts)
            text = self._fact_ack(facts)
            self._save_turn(context, text)
            return ConversationResult(text, intent, remembered_facts=facts)

        local_answer = self._answer_local_intent(intent)
        if local_answer is not None:
            self._save_turn(context, local_answer)
            return ConversationResult(local_answer, intent)

        if intent.name == "vision":
            return self._process_vision(context)

        if intent.name == "web_search" and not web_results:
            text = (
                "I tried to fetch real-time web results, but the web lookup returned no usable results. "
                "I should not answer this from stale model knowledge."
            )
            self._save_turn(context, text)
            return ConversationResult(text, intent)

        return self._process_provider_chat(context)

    def stream(
        self,
        user_input: str,
        attachments: list[ConversationAttachment] | None = None,
    ) -> Iterable[str]:
        self._cancel_requested = False
        result = self.process(user_input, attachments)
        yield result.text

    def cancel(self) -> None:
        self._cancel_requested = True

    def make_image_attachment(self, image_path: Path | str) -> ConversationAttachment:
        path = Path(image_path)
        mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
        return ConversationAttachment(path=path, mime_type=mime_type)

    def _process_provider_chat(self, context: ConversationContext) -> ConversationResult:
        try:
            response = self.provider_manager.chat(
                ChatRequest(
                    messages=context.messages,
                    model=self.model,
                    temperature=0.7,
                    max_tokens=1024,
                    metadata=context.metadata,
                )
            )
            text = self._format_answer(response.text.replace("</s>", ""))
            self._save_turn(context, text)
            return ConversationResult(
                text=text,
                intent=context.intent,
                used_provider=True,
                provider=response.provider,
                model=response.model,
            )
        except ProviderError as exc:
            text = (
                "I saved that locally. The AI provider is not available yet, so I can answer "
                f"memory questions now. {type(exc).__name__}: {exc}"
            )
            self._save_turn(context, text)
            return ConversationResult(text, context.intent)
        except Exception as exc:
            text = f"I saved that locally, but the AI provider request failed: {type(exc).__name__}: {exc}"
            self._save_turn(context, text)
            return ConversationResult(text, context.intent)

    def _lookup_web(self, user_input: str, intent: Intent) -> list[dict[str, str]]:
        if intent.name != "web_search":
            return []
        if self.settings.get("web_search_enabled", True) is False:
            return []

        try:
            results = self.web_search.search(user_input, limit=5)
        except Exception:
            return []

        return [
            {"title": result.title, "url": result.url, "snippet": result.snippet}
            for result in results
        ]
    
    def _perform_deep_research(
        self,
        query: str,
        intent: Intent,
    ) -> DeepResearchResult:
        """
        Perform deep research using the DeepResearchManager.
        
        Args:
            query: User query
            intent: Detected intent
            
        Returns:
            DeepResearchResult with findings
        """
        import asyncio
        
        # Use asyncio to run the async perform_research method
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                self.deep_research_manager.perform_research(
                    query=query,
                    context=None,
                )
            )
            return result
        finally:
            loop.close()
    
    def _format_deep_research_results(
        self,
        deep_research_result: DeepResearchResult,
    ) -> list[dict[str, str]]:
        """
        Format DeepResearchResult into the web_results format expected by context_builder.
        
        Args:
            deep_research_result: Deep research result
            
        Returns:
            List of web results in dict format
        """
        # Format main search results
        web_results = []
        
        for result in deep_research_result.main_results:
            web_results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
            })
        
        # Add page contents as additional sources
        for page in deep_research_result.page_contents:
            web_results.append({
                "title": page.title,
                "url": page.url,
                "snippet": page.main_text[:200] + "..." if len(page.main_text) > 200 else page.main_text,
            })
        
        return web_results

    def _process_vision(self, context: ConversationContext) -> ConversationResult:
        image = next((item for item in context.attachments if item.mime_type.startswith("image/")), None)
        if image is None:
            text = "I did not receive an image to analyze."
            self._save_turn(context, text)
            return ConversationResult(text, context.intent)

        try:
            response = self.provider_manager.vision(
                VisionRequest(
                    prompt=(
                        f"{context.user_input}\n\n"
                        "Describe the visible screen briefly and focus on useful details. "
                        "If there is code, errors, or UI state, mention the important parts."
                    ),
                    image=image_attachment_from_conversation(image),
                )
            )
            text = self._format_answer(response.text)
            text = text or "I captured the screen, but the vision model returned an empty answer."
            self._save_turn(context, text)
            return ConversationResult(
                text=text,
                intent=context.intent,
                used_provider=True,
                provider=response.provider,
                model=response.model,
            )
        except ProviderError as exc:
            text = (
                "I captured your screen, but vision is not available yet. "
                f"{type(exc).__name__}: {exc}"
            )
            self._save_turn(context, text)
            return ConversationResult(text, context.intent)
        except Exception as exc:
            text = f"I captured your screen, but vision analysis failed: {type(exc).__name__}: {exc}"
            self._save_turn(context, text)
            return ConversationResult(text, context.intent)

    def _answer_local_intent(self, intent: Intent) -> str | None:
        if intent.name == "memory_summary":
            return self.memory.summarize()

        if intent.name == "local_time":
            now = dt.datetime.now().astimezone()
            return now.strftime("Today is %A, %B %d, %Y. Current time: %H:%M:%S %Z.")

        if intent.name == "profile_lookup":
            name = self.memory.fact_value("profile", "name")
            return f"Your name is {name}." if name else "I do not know your name yet."

        if intent.name == "projects_lookup":
            return self._list_answer("Projects I remember", self.memory.values_for_category("projects"))

        if intent.name == "skills_lookup":
            skills = self.memory.values_for_category("skills")
            if intent.data.get("wants_count"):
                return f"You have {len(skills)} skill{'s' if len(skills) != 1 else ''} saved: {', '.join(skills) or 'none yet'}."
            return self._list_answer("Skills I remember", skills)

        if intent.name == "goals_lookup":
            return self._list_answer("Goals I remember", self.memory.values_for_category("goals"))

        if intent.name == "preferences_lookup":
            return self._list_answer("Preferences I remember", self.memory.values_for_category("preferences"))

        if intent.name == "capability_status":
            enabled = self.settings.get("web_search_enabled", True) is not False
            if enabled:
                return (
                    "Yes. Aura can attempt real-time web lookup for current/latest questions, "
                    "then pass those fresh results into the AI provider as context."
                )
            return "Web search is currently disabled in Aura settings."

        return None

    def _save_turn(self, context: ConversationContext, answer: str) -> None:
        topic = self._infer_topic(context.user_input)
        self.memory.record_turn(context.user_input, answer, topic)
        self.memory.remember_exchange(context.user_input, answer, topic)

    def _fact_ack(self, facts: list[MemoryFact]) -> str:
        if len(facts) == 1 and facts[0].category == "profile" and facts[0].key == "name":
            return f"Got it. Your name is {facts[0].value}."

        grouped: dict[str, list[str]] = {}
        for fact in facts:
            grouped.setdefault(fact.category, []).append(fact.value)

        parts = []
        for category in sorted(grouped):
            values = sorted(set(grouped[category]))
            parts.append(f"{category.title()}: {', '.join(values)}")
        return "Remembered. " + " | ".join(parts)

    def _infer_topic(self, query: str) -> str:
        words = [word for word in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(word) > 3]
        if not words:
            return "General"
        return " ".join(words[:3]).title()

    def _list_answer(self, title: str, values: list[str]) -> str:
        if not values:
            return f"{title}: none saved yet."
        return f"{title}: {', '.join(values)}."

    def _format_answer(self, text: str) -> str:
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
