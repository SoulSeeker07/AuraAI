"""
Freshness Checker - Manages knowledge lifecycle and expiry.

This module determines how long knowledge remains valid based on its category
and automatically checks if facts need to be refreshed.

Knowledge lifetimes:
    Weather: 10 minutes
    News: 1 hour
    Programming Docs: 30 days
    Networking Docs: 30 days
    AI Model Releases: 7 days
    Security Vulnerabilities: 7 days
    OS Updates: 30 days
    Personal Memory: 90 days

If a fact expires, it triggers a refresh in the background.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import threading
import asyncio

from .knowledge_db import KnowledgeFact, KnowledgeDB


class KnowledgeCategory(Enum):
    """Knowledge categories and their default lifetimes."""
    WEATHER = "Weather"
    NEWS = "News"
    PROGRAMMING = "Programming"
    NETWORKING = "Networking"
    CYBERSECURITY = "Cybersecurity"
    AI = "AI"
    OPERATING_SYSTEMS = "Operating Systems"
    FINANCE = "Finance"
    TECHNOLOGY = "Technology"
    SCIENCE = "Science"
    PERSONAL = "Personal Memory"
    CONVERSATION = "Conversation History"


class FreshnessChecker:
    """
    Checks knowledge freshness and manages knowledge lifecycle.

    Features:
    - Calculate default expiry times by category
    - Check if facts are still fresh
    - Manage knowledge refresh cycles
    - Track freshness statistics
    - Background refresh scheduling
    """

    # Default lifetimes in days
    LIFETIME_MAP: Dict[str, int] = {
        "Weather": 0,  # 10 minutes
        "News": 1,  # 1 hour
        "Programming": 30,
        "Networking": 30,
        "Cybersecurity": 7,
        "AI": 7,
        "Operating Systems": 30,
        "Finance": 7,
        "Technology": 14,
        "Science": 30,
        "Personal Memory": 90,
        "Conversation History": 7,
    }

    def __init__(self, knowledge_db: KnowledgeDB = None):
        """
        Initialize freshness checker.

        Args:
            knowledge_db: KnowledgeDB instance
        """
        self.knowledge_db = knowledge_db or KnowledgeDB()
        self._lock = threading.Lock()
        self._refresh_callback = None

    def set_refresh_callback(self, callback: callable) -> None:
        """
        Set a callback function for when knowledge needs refresh.

        Args:
            callback: Function to call when refresh is needed
            Signature: callback(topic: str, fact: KnowledgeFact) -> None
        """
        self._refresh_callback = callback

    def calculate_expiry(
        self,
        fact: KnowledgeFact,
        override_days: int = None
    ) -> str:
        """
        Calculate the expiry date for a fact.

        Args:
            fact: KnowledgeFact to calculate expiry for
            override_days: Override default lifetime (optional)

        Returns:
            Expiry datetime string
        """
        # Use override if provided
        if override_days is not None:
            expiry_date = datetime.now() + timedelta(days=override_days)
        else:
            # Get lifetime from category or default
            category = fact.category
            days = self.LIFETIME_MAP.get(category, 30)
            expiry_date = datetime.now() + timedelta(days=days)

        return expiry_date.strftime("%Y-%m-%d %H:%M:%S")

    def is_fresh(self, fact: KnowledgeFact) -> bool:
        """
        Check if a fact is still fresh (not expired).

        Args:
            fact: KnowledgeFact to check

        Returns:
            True if fresh, False if expired
        """
        try:
            expiry = datetime.strptime(fact.expires, "%Y-%m-%d %H:%M:%S")
            return datetime.now() < expiry
        except (ValueError, AttributeError):
            # If expiry is invalid, assume fresh
            return True

    def get_age_days(self, fact: KnowledgeFact) -> float:
        """
        Get the age of a fact in days.

        Args:
            fact: KnowledgeFact to check

        Returns:
            Age in days (negative if not yet created)
        """
        try:
            created_date = datetime.strptime(fact.updated, "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - created_date).total_seconds() / 86400
        except (ValueError, AttributeError):
            return 0.0

    def get_freshness_score(self, fact: KnowledgeFact) -> float:
        """
        Get a freshness score (0.0 to 1.0).

        Score calculation:
        - 1.0 = Fresh (< 10% of lifetime)
        - 0.5 = Halfway (< 50% of lifetime)
        - 0.0 = Expired (> 100% of lifetime)

        Args:
            fact: KnowledgeFact to score

        Returns:
            Freshness score (0.0 to 1.0)
        """
        try:
            expiry = datetime.strptime(fact.expires, "%Y-%m-%d %H:%M:%S")
            created_date = datetime.strptime(fact.updated, "%Y-%m-%d %H:%M:%S")
            lifetime = (expiry - created_date).total_seconds() / 86400  # in days

            if lifetime <= 0:
                return 0.0

            age_days = (datetime.now() - created_date).total_seconds() / 86400
            age_ratio = age_days / lifetime

            # Score is 1.0 - age_ratio (clamped to 0.0-1.0)
            score = 1.0 - age_ratio
            return max(0.0, min(1.0, score))

        except (ValueError, AttributeError):
            return 0.0

    def get_facts_by_freshness(self, category: Optional[str] = None) -> List[Tuple[KnowledgeFact, float]]:
        """
        Get all facts grouped by freshness score.

        Args:
            category: Filter by category (optional)

        Returns:
            List of (KnowledgeFact, freshness_score) tuples
        """
        with self._lock:
            facts = self.knowledge_db.get_fresh_facts(category=category)

            scored_facts = [(fact, self.get_freshness_score(fact)) for fact in facts]
            return scored_facts

    def get_facts_needing_refresh(
        self,
        category: Optional[str] = None,
        threshold_days: float = None
    ) -> List[KnowledgeFact]:
        """
        Get facts that need refreshing.

        Args:
            category: Filter by category (optional)
            threshold_days: Refresh when age exceeds this many days (optional)

        Returns:
            List of facts that need refreshing
        """
        with self._lock:
            # Get all facts (both fresh and stale)
            if category:
                all_facts = self.knowledge_db.get_facts_by_category(category)
            else:
                all_facts = self.knowledge_db.get_facts(limit=1000)

            # Filter by age threshold
            facts_to_refresh = []
            for fact in all_facts:
                age_days = self.get_age_days(fact)
                if threshold_days is not None and age_days >= threshold_days:
                    facts_to_refresh.append(fact)
                elif not self.is_fresh(fact):
                    facts_to_refresh.append(fact)

            return facts_to_refresh

    def check_and_refresh(
        self,
        topic: str,
        fact: KnowledgeFact
    ) -> bool:
        """
        Check if a fact needs refreshing and trigger callback.

        Args:
            topic: Topic name
            fact: KnowledgeFact to check

        Returns:
            True if fact was expired and callback was triggered
        """
        if not self.is_fresh(fact):
            if self._refresh_callback:
                self._refresh_callback(topic, fact)
            return True
        return False

    def get_category_lifetime(self, category: str) -> int:
        """
        Get the default lifetime for a category.

        Args:
            category: Category name

        Returns:
            Lifetime in days
        """
        return self.LIFETIME_MAP.get(category, 30)

    def get_all_categories(self) -> List[str]:
        """
        Get all knowledge categories.

        Returns:
            List of category names
        """
        return list(self.LIFETIME_MAP.keys())

    def update_lifetime(self, category: str, days: int) -> None:
        """
        Update the default lifetime for a category.

        Args:
            category: Category name
            days: New lifetime in days
        """
        self.LIFETIME_MAP[category] = days

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get freshness checker statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            total_facts = self.knowledge_db.count_facts()

            # Group by category
            categories = self.get_all_categories()
            category_stats = {}

            for category in categories:
                facts = self.knowledge_db.get_facts_by_category(category, limit=1000)
                category_facts = []
                for fact in facts:
                    age_days = self.get_age_days(fact)
                    category_facts.append(age_days)

                category_stats[category] = {
                    "total_facts": len(facts),
                    "avg_age_days": sum(category_facts) / len(category_facts) if category_facts else 0,
                    "total_lifetime_days": sum(self.get_category_lifetime(category) for _ in facts)
                }

            # Calculate overall statistics
            all_facts = self.knowledge_db.get_facts(limit=1000)
            all_scores = [self.get_freshness_score(fact) for fact in all_facts]

            return {
                "total_facts": total_facts,
                "categories_analyzed": len(categories),
                "category_stats": category_stats,
                "avg_freshness_score": sum(all_scores) / len(all_scores) if all_scores else 0,
                "total_lifetime_days": sum(self.get_category_lifetime(cat) for cat in categories)
            }

    async def auto_refresh_all_categories(self, refresh_interval: int = 3600) -> None:
        """
        Automatically refresh all categories at specified intervals.

        Args:
            refresh_interval: Refresh interval in seconds (default: 1 hour)
        """
        while True:
            await asyncio.sleep(refresh_interval)

            with self._lock:
                categories = self.get_all_categories()
                for category in categories:
                    facts = self.get_facts_needing_refresh(category=category)

                    if facts:
                        print(f"[FreshnessChecker] Refreshing {len(facts)} facts in {category}")

                        for fact in facts:
                            if self._refresh_callback:
                                self._refresh_callback(category, fact)

    def start_background_refresh(self, interval_seconds: int = 3600) -> asyncio.Task:
        """
        Start background refresh loop.

        Args:
            interval_seconds: Refresh interval in seconds

        Returns:
            Running asyncio task
        """
        loop = asyncio.get_event_loop()
        task = loop.create_task(self.auto_refresh_all_categories(interval_seconds))
        return task

    def batch_update_facts(
        self,
        facts: List[KnowledgeFact],
        lifetime_override: Optional[int] = None
    ) -> List[KnowledgeFact]:
        """
        Batch update facts with new lifetimes.

        Args:
            facts: List of facts to update
            lifetime_override: Override lifetime for all facts

        Returns:
            List of updated facts
        """
        with self._lock:
            updated_facts = []
            for fact in facts:
                fact.expires = self.calculate_expiry(fact, override_days=lifetime_override)
                updated_facts.append(fact)
            return updated_facts
