from __future__ import annotations

from brain.models import ConversationAttachment, Intent
from brain.research_decision import ResearchDecision, SearchMode
from Memory import Memory, MemoryFact


class IntentRouter:
    def __init__(self, memory: Memory):
        self.memory = memory
        self.research_decision = ResearchDecision()

    def detect(
        self, user_input: str, attachments: list[ConversationAttachment] | None = None
    ) -> Intent:
        normalized = user_input.lower().strip(" ?!.")
        attachments = attachments or []

        import logging

        logger = logging.getLogger(__name__)

        if attachments and any(
            attachment.mime_type.startswith("image/") for attachment in attachments
        ):
            logger.info("[IntentRouter] Intent detected: vision")
            return Intent("vision")

        if self._asks_about_realtime_capability(normalized):
            logger.info("[IntentRouter] Intent detected: capability_status")
            return Intent("capability_status")

        facts = self.memory.extract_facts(user_input)
        logger.info(f"[IntentRouter] Extracted facts: {facts}")
        if facts and self._is_memory_statement(user_input):
            logger.info(
                "[IntentRouter] Memory statement detected, returning remember_fact intent"
            )
            return Intent("remember_fact", {"facts": facts})

        if normalized in {
            "summarize me",
            "summarize my memory",
            "what do you remember",
        }:
            logger.info("[IntentRouter] Intent detected: memory_summary")
            return Intent("memory_summary")

        if self._asks_for_time_or_date(normalized):
            logger.info("[IntentRouter] Intent detected: local_time")
            return Intent("local_time")

        if "my name" in normalized or normalized in {"who am i", "what is my profile"}:
            logger.info("[IntentRouter] Intent detected: profile_lookup")
            return Intent("profile_lookup")

        if "project" in normalized and any(
            word in normalized for word in ("my", "building", "working")
        ):
            logger.info("[IntentRouter] Intent detected: projects_lookup")
            return Intent("projects_lookup")

        if "skill" in normalized or "skills" in normalized:
            logger.info("[IntentRouter] Intent detected: skills_lookup")
            return Intent(
                "skills_lookup",
                {"wants_count": "how many" in normalized or "count" in normalized},
            )

        if "goal" in normalized or "goals" in normalized:
            logger.info("[IntentRouter] Intent detected: goals_lookup")
            return Intent("goals_lookup")

        if "preference" in normalized or "preferences" in normalized:
            logger.info("[IntentRouter] Intent detected: preferences_lookup")
            return Intent("preferences_lookup")

        # Use ResearchDecision to determine if research is needed
        needs_research, reason, search_mode = self.research_decision.analyze(user_input)

        logger.info(
            f"[IntentRouter] ResearchDecision - Needs research: {needs_research}, Reason: {reason}, Mode: {search_mode.value}"
        )

        if needs_research:
            intent_type = (
                "web_search"
                if search_mode == SearchMode.QUICK
                else (
                    "deep_research" if search_mode == SearchMode.DEEP else "web_search"
                )
            )
            logger.info(f"[IntentRouter] Intent detected: {intent_type}")
            return Intent(intent_type, {"mode": search_mode.value})

        logger.info("[IntentRouter] Intent detected: provider_chat")
        return Intent("provider_chat")

    def remember_detected_facts(self, facts: list[MemoryFact]) -> None:
        for fact in facts:
            self.memory.upsert_fact(fact.category, fact.key, fact.value)

    def _asks_for_time_or_date(self, normalized: str) -> bool:
        # Prevent freshness constraints like "today's exchange rate" from matching
        if any(w in normalized for w in ("rate", "exchange", "conversion", "price")):
            return False
            
        time_words = ("time", "date")
        has_time_word = any(word in normalized for word in time_words)
        
        # Explicitly asking for time or date
        if has_time_word and any(
            phrase in normalized
            for phrase in (
                "what is",
                "what's",
                "tell me",
                "current",
                "what time",
                "what date",
            )
        ):
            return True
            
        return False

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
        capability_terms = (
            "real time",
            "realtime",
            "live data",
            "web search",
            "internet",
        )
        question_terms = ("do you have", "can you", "are you able", "you have")
        return any(term in normalized for term in capability_terms) and any(
            term in normalized for term in question_terms
        )
