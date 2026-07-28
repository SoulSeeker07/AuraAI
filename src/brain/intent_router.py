from __future__ import annotations

from brain.models import ConversationAttachment, Intent
from Memory import Memory, MemoryFact


class IntentRouter:
    def __init__(self, memory: Memory):
        self.memory = memory

    def detect(self, user_input: str, attachments: list[ConversationAttachment] | None = None) -> Intent:
        normalized = user_input.lower().strip(" ?!.")
        attachments = attachments or []

        if attachments and any(attachment.mime_type.startswith("image/") for attachment in attachments):
            return Intent("vision")

        if self._asks_about_realtime_capability(normalized):
            return Intent("capability_status")

        facts = self.memory.extract_facts(user_input)
        if facts and self._is_memory_statement(user_input):
            return Intent("remember_fact", {"facts": facts})

        if normalized in {"summarize me", "summarize my memory", "what do you remember"}:
            return Intent("memory_summary")

        if self._asks_for_time_or_date(normalized):
            return Intent("local_time")

        if "my name" in normalized or normalized in {"who am i", "what is my profile"}:
            return Intent("profile_lookup")

        if "project" in normalized and any(word in normalized for word in ("my", "building", "working")):
            return Intent("projects_lookup")

        if "skill" in normalized or "skills" in normalized:
            return Intent("skills_lookup", {"wants_count": "how many" in normalized or "count" in normalized})

        if "goal" in normalized or "goals" in normalized:
            return Intent("goals_lookup")

        if "preference" in normalized or "preferences" in normalized:
            return Intent("preferences_lookup")

        # Check for deep research intent
        if self._needs_deep_research(normalized):
            return Intent("deep_research")

        # Check for regular web search
        if self._needs_realtime_data(normalized):
            return Intent("web_search")

        return Intent("provider_chat")

    def remember_detected_facts(self, facts: list[MemoryFact]) -> None:
        for fact in facts:
            self.memory.upsert_fact(fact.category, fact.key, fact.value)

    def _asks_for_time_or_date(self, normalized: str) -> bool:
        time_words = ("time", "date", "day", "today")
        return any(word in normalized for word in time_words) and any(
            phrase in normalized
            for phrase in (
                "current",
                "what is",
                "what's",
                "tell me",
                "today",
            )
        )

    def _is_memory_statement(self, user_input: str) -> bool:
        return not user_input.strip().endswith("?")

    def _needs_realtime_data(self, normalized: str) -> bool:
        realtime_terms = (
            "latest",
            "current",
            "today",
            "now",
            "news",
            "price",
            "weather",
            "score",
            "version",
            "release",
            "president",
            "ceo",
        )
        return any(term in normalized for term in realtime_terms)

    def _needs_deep_research(self, normalized: str) -> bool:
        """
        Check if the query requires deep research (multi-source, comparison, analysis).
        
        Args:
            normalized: Normalized user input
            
        Returns:
            True if deep research is needed
        """
        deep_research_patterns = (
            # Comparison queries
            "compare",
            "versus",
            "vs",
            "difference between",
            "which is better",
            "pros and cons",
            "advantages and disadvantages",
            "comparison",
            
            # Research and analysis queries
            "research",
            "analyze",
            "investigate",
            "study",
            
            # Explanation queries
            "explain how",
            "how does",
            "how to",
            "overview of",
            
            # Summarization from web
            "summarize from web",
            "read and summarize",
            "summarize the",
            
            # Read and understand
            "read and explain",
            "read and summarize",
            "read the",
        )
        
        return any(pattern in normalized for pattern in deep_research_patterns)

    def _asks_about_realtime_capability(self, normalized: str) -> bool:
        capability_terms = ("real time", "realtime", "live data", "web search", "internet")
        question_terms = ("do you have", "can you", "are you able", "you have")
        return any(term in normalized for term in capability_terms) and any(
            term in normalized for term in question_terms
        )
