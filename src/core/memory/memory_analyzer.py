"""
Memory Analyzer

Analyzes text to determine if it should be stored in memory and how important it is.
"""

import logging
import re
from typing import Any

from .memory_types import CategoryType, ImportanceLevel, MemoryAnalysisResult

logger = logging.getLogger(__name__)


class MemoryAnalyzer:
    """
    Analyzes text to determine memory storage decisions.

    Determines:
        - Should we store this text?
        - How important is it?
        - What category does it belong to?
        - What key should we use?
        - Confidence level in the decision
    """

    def __init__(self, provider_manager=None):
        """
        Initialize Memory Analyzer.

        Args:
            provider_manager: Optional LLM provider for intelligent analysis
        """
        self.provider_manager = provider_manager

    async def analyze(self, text: str) -> MemoryAnalysisResult:
        """
        Analyze text and determine if it should be stored.

        Args:
            text: Text to analyze

        Returns:
            MemoryAnalysisResult with decision
        """
        if not text or len(text.strip()) < 2:
            return MemoryAnalysisResult(
                should_store=False,
                importance=ImportanceLevel.LOW,
                category=CategoryType.PERSONAL,
                key=None,
                confidence=0.0,
                metadata={},
            )

        # Check if text is too simple (noise)
        if self._is_too_simple(text):
            return MemoryAnalysisResult(
                should_store=False,
                importance=ImportanceLevel.LOW,
                category=CategoryType.PERSONAL,
                key=None,
                confidence=0.0,
                metadata={"reason": "too_simple"},
            )

        # Check for explicit remember/forget commands
        if self._is_forget_command(text):
            return MemoryAnalysisResult(
                should_store=False,
                importance=ImportanceLevel.LOW,
                category=CategoryType.PERSONAL,
                key=None,
                confidence=0.0,
                metadata={"reason": "forget_command"},
            )

        # Check for sensitive data patterns
        if self._is_sensitive_data(text):
            importance = ImportanceLevel.CRITICAL
            key = self._extract_sensitive_key(text)
        else:
            importance = self._determine_importance(text)
            key = self._extract_key(text)

        # Determine category
        category = await self._classify_category(text)

        # Confidence scoring
        confidence = self._calculate_confidence(text, importance, category, key)

        # Extract metadata
        metadata = self._extract_metadata(text, importance, category, key)

        return MemoryAnalysisResult(
            should_store=True,
            importance=importance,
            category=category,
            key=key,
            confidence=confidence,
            metadata=metadata,
        )

    def _is_too_simple(self, text: str) -> bool:
        """Check if text is too simple to be stored (noise)."""
        words = text.lower().split()
        word_count = len(words)

        # Too short or too common
        if word_count < 2:
            return True

        # Common filler words that make text meaningless
        common_words = {
            "hello",
            "hi",
            "hey",
            "thanks",
            "ok",
            "yeah",
            "no",
            "yes",
            "um",
            "uh",
        }
        if words[0] in common_words and word_count == 1:
            return True

        return False

    def _is_forget_command(self, text: str) -> bool:
        """Check if text is an explicit forget command."""
        forget_patterns = [
            r"forget\s+(?:my\s+)?(.+)",
            r"delete\s+(?:my\s+)?(.+)",
            r"remove\s+(?:my\s+)?(.+)",
            r"unremember\s+(?:my\s+)?(.+)",
            r"make\s+(?:me\s+)?forget\s+(?:my\s+)?(.+)",
        ]

        for pattern in forget_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _is_sensitive_data(self, text: str) -> bool:
        """Check if text contains sensitive data."""
        sensitive_patterns = [
            r"\b(key|secret|password|api\s*key)\b",
            r"\b(token|credential)\b",
            r"\b(api\s*[0-9a-f]{32,64})\b",
            r"\b(sk-[0-9a-zA-Z]{32,})\b",
            r"\b(private\s*)?key\s*[=:]\s*[^\s,;.!?]+",
        ]

        return any(
            re.search(pattern, text, re.IGNORECASE) for pattern in sensitive_patterns
        )

    def _extract_sensitive_key(self, text: str) -> str:
        """Extract the key for sensitive data."""
        patterns = [
            r"forget\s+(?:my\s+)?(?:the\s+)?(?:api\s+)?key\s*(?:of\s+)?(?:for\s+)?(.+)",
            r"forget\s+(?:my\s+)?(?:the\s+)?(?:api\s+)?key",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                key = match.group(1).strip() if match.groups() else "api_key"
                return self._normalize_key(key)

        return "api_key"

    def _determine_importance(self, text: str) -> ImportanceLevel:
        """Determine importance level of text."""
        words = text.lower().split()
        word_count = len(words)

        # Critical importance
        critical_keywords = ["important", "vital", "crucial", "must", "never forget"]
        if any(kw in words for kw in critical_keywords):
            return ImportanceLevel.CRITICAL

        # High importance
        high_keywords = [
            "remember",
            "keep",
            "save",
            "file",
            "note",
            "always",
            "importantly",
        ]
        if any(kw in words for kw in high_keywords):
            return ImportanceLevel.HIGH

        # Medium importance (default)
        return ImportanceLevel.MEDIUM

    async def _classify_category(self, text: str) -> CategoryType:
        """
        Classify text into a memory category using LLM if available.

        Falls back to keyword-based classification if no LLM.
        """
        if self.provider_manager:
            try:
                category = await self._llm_classify(text)
                if category:
                    return category
            except Exception as e:
                logger.debug(f"LLM classification failed: {e}")

        # Keyword-based classification
        return self._keyword_classify(text)

    async def _llm_classify(self, text: str) -> CategoryType | None:
        """
        Use LLM to classify text into a category.

        Note: This would require prompt engineering and response parsing
        for production use.
        """
        # For now, return None to use keyword-based classification
        return None

    def _keyword_classify(self, text: str) -> CategoryType:
        """Keyword-based category classification."""
        text_lower = text.lower()

        # Preference-related (CHECK FIRST to avoid false positives)
        if any(
            kw in text_lower
            for kw in ["like", "prefer", "favorite", "choice", "enjoy", "ide"]
        ):
            return CategoryType.PREFERENCES

        # Personal (CHECK FIRST to catch personal references)
        if any(
            kw in text_lower
            for kw in [
                "personal",
                "remember",
                "keep",
                "privacy",
                "confidential",
                "secret",
            ]
        ):
            return CategoryType.PERSONAL

        # People-related
        if any(
            kw in text_lower
            for kw in ["name", "person", "friend", "colleague", "manager", "boss"]
        ):
            return CategoryType.PEOPLE

        # Device-related
        if any(
            kw in text_lower
            for kw in ["computer", "laptop", "phone", "device", "screen"]
        ):
            return CategoryType.DEVICES

        # Skill-related
        if any(
            kw in text_lower
            for kw in ["learn", "practice", "skill", "improve", "master"]
        ):
            return CategoryType.SKILLS

        # Goal-related
        if any(
            kw in text_lower
            for kw in ["goal", "target", "achieve", "win", "success", "objective"]
        ):
            return CategoryType.GOALS

        # Coding-related (CHECK BEFORE FILES to prioritize code context)
        # Check for API endpoints (not personal API keys) or common coding phrases
        if "api" in text_lower and (
            "endpoint" in text_lower
            or "route" in text_lower
            or "function" in text_lower
            or "class" in text_lower
            or "code" in text_lower
            or "import" in text_lower
        ):
            return CategoryType.CODING
        # Check for fixing code errors
        if "fix" in text_lower and (
            "import" in text_lower or "error" in text_lower or "bug" in text_lower
        ):
            return CategoryType.CODING

        # File-related
        if any(
            kw in text_lower
            for kw in ["file", "document", "report", "data", "backup", "save"]
        ):
            return CategoryType.FILES

        # Project-related
        if any(
            kw in text_lower
            for kw in ["project", "task", "deadline", "milestone", "team", "workflow"]
        ):
            return CategoryType.PROJECTS

        # Networking
        if any(
            kw in text_lower
            for kw in ["network", "server", "cloud", "database", "api", "service"]
        ):
            return CategoryType.NETWORKING

        # Default to personal
        return CategoryType.PERSONAL

    def _extract_key(self, text: str) -> str:
        """Extract a key from text for storing the memory."""
        # Try to extract a question or statement that could be a key
        words = text.split()

        # If it's a question, use the topic
        if text.strip().endswith("?"):
            topic = " ".join(words[:3])
            return self._normalize_key(topic)

        # If it's a statement, try to extract the key concept
        if len(words) >= 2:
            # Take first 2-3 words as the key
            topic = " ".join(words[:3])
            return self._normalize_key(topic)

        return "general"

    def _normalize_key(self, key: str) -> str:
        """Normalize key for storage."""
        # Remove special characters, lowercase
        key = key.lower()
        key = re.sub(r"[^\w\s-]", "", key)
        key = re.sub(r"\s+", "_", key)
        return key.strip("_")[:50]

    def _calculate_confidence(
        self, text: str, importance: ImportanceLevel, category: CategoryType, key: str
    ) -> float:
        """Calculate confidence score for the memory decision."""
        score = 0.5  # Base score

        # Increase confidence for important memories
        score += importance.value * 0.1

        # Increase confidence for well-formed keys
        if key and len(key) > 3:
            score += 0.1

        # Increase confidence for categorized memories
        score += 0.1

        # Cap at 1.0
        return min(score, 1.0)

    def _extract_metadata(
        self, text: str, importance: ImportanceLevel, category: CategoryType, key: str
    ) -> dict[str, Any]:
        """Extract additional metadata from text."""
        metadata = {
            "text_length": len(text),
            "word_count": len(text.split()),
            "contains_sensitive": self._is_sensitive_data(text),
        }

        # Add importance metadata
        if importance != ImportanceLevel.MEDIUM:
            metadata["importance_reason"] = importance.name.lower()

        return metadata
