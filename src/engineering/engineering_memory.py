"""
Engineering Memory

Stores engineering decisions and learnings.

This module enables Aura to:
- Remember architecture decisions
- Track known bugs
- Remember technical debt
- Store refactoring history
- Remember design discussions
- Remember coding standards
- Store review notes
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EngineeringDecision:
    """Represents an engineering decision."""

    key: str
    decision: str
    rationale: str
    date: str
    author: str
    status: str  # "decided", "implemented", "reviewed", "deprecated"
    tags: list[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "decision": self.decision,
            "rationale": self.rationale,
            "date": self.date,
            "author": self.author,
            "status": self.status,
            "tags": self.tags or [],
        }


@dataclass
class KnownBug:
    """Represents a known bug."""

    id: str
    title: str
    description: str
    severity: str  # "critical", "high", "medium", "low"
    status: str  # "known", "in_progress", "fixed", "verified"
    date_reported: str
    files_affected: list[str] = None
    fix_suggestions: list[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "date_reported": self.date_reported,
            "files_affected": self.files_affected or [],
            "fix_suggestions": self.fix_suggestions or [],
        }


@dataclass
class TechnicalDebt:
    """Represents a technical debt item."""

    id: str
    description: str
    effort: str  # "small", "medium", "large", "huge"
    category: str  # "refactoring", "documentation", "testing", "architecture"
    priority: str  # "low", "medium", "high"
    date_created: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "effort": self.effort,
            "category": self.category,
            "priority": self.priority,
            "date_created": self.date_created,
        }


class EngineeringMemory:
    """
    Stores engineering decisions and learnings.

    Usage:
        memory = EngineeringMemory(repository_path="/path/to/repo")

        # Store a decision
        memory.store_decision(
            key="use_fastapi",
            decision="Use FastAPI for API layer",
            rationale="FastAPI has better async support and type hints",
            author="dev_team"
        )

        # Store a known bug
        memory.store_bug(
            title="Login fails on Safari",
            description="Users can't login on Safari browser",
            severity="high",
            status="known"
        )

        # Get all decisions
        decisions = memory.get_decisions()

        # Get known bugs
        bugs = memory.get_known_bugs()

        # Search decisions
        decisions = memory.search_decisions("fastapi")
    """

    def __init__(self, repository_path: Path):
        """
        Initialize the Engineering Memory.

        Args:
            repository_path: Path to the repository
        """
        self.repository_path = Path(repository_path).resolve()
        self._decisions: list[EngineeringDecision] = []
        self._bugs: list[KnownBug] = []
        self._debt: list[TechnicalDebt] = []

        # Load from file if exists
        self._load()

    def store_decision(
        self,
        key: str,
        decision: str,
        rationale: str,
        author: str,
        status: str = "decided",
        tags: list[str] | None = None,
    ) -> EngineeringDecision:
        """
        Store an engineering decision.

        Args:
            key: Decision key
            decision: The decision made
            rationale: Rationale for the decision
            author: Person who made the decision
            status: Status of the decision
            tags: Optional tags

        Returns:
            EngineeringDecision
        """
        decision_obj = EngineeringDecision(
            key=key,
            decision=decision,
            rationale=rationale,
            date=str(datetime.now()),
            author=author,
            status=status,
            tags=tags or [],
        )

        self._decisions.append(decision_obj)
        self._save()

        return decision_obj

    def store_bug(
        self,
        title: str,
        description: str,
        severity: str = "medium",
        status: str = "known",
        files_affected: list[str] | None = None,
    ) -> KnownBug:
        """
        Store a known bug.

        Args:
            title: Bug title
            description: Bug description
            severity: Bug severity
            status: Bug status
            files_affected: Files affected

        Returns:
            KnownBug
        """
        bug_obj = KnownBug(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            severity=severity,
            status=status,
            date_reported=str(datetime.now()),
            files_affected=files_affected or [],
        )

        self._bugs.append(bug_obj)
        self._save()

        return bug_obj

    def add_technical_debt(
        self,
        description: str,
        effort: str = "medium",
        category: str = "refactoring",
        priority: str = "medium",
    ) -> TechnicalDebt:
        """
        Add technical debt item.

        Args:
            description: Description of technical debt
            effort: Effort required
            category: Category of technical debt
            priority: Priority

        Returns:
            TechnicalDebt
        """
        debt_obj = TechnicalDebt(
            id=str(uuid.uuid4())[:8],
            description=description,
            effort=effort,
            category=category,
            priority=priority,
            date_created=str(datetime.now()),
        )

        self._debt.append(debt_obj)
        self._save()

        return debt_obj

    def get_decisions(self, status: str | None = None) -> list[EngineeringDecision]:
        """
        Get engineering decisions.

        Args:
            status: Optional status filter

        Returns:
            List of decisions
        """
        if status:
            return [d for d in self._decisions if d.status == status]
        return self._decisions.copy()

    def get_known_bugs(self, status: str | None = None) -> list[KnownBug]:
        """
        Get known bugs.

        Args:
            status: Optional status filter

        Returns:
            List of bugs
        """
        if status:
            return [b for b in self._bugs if b.status == status]
        return self._bugs.copy()

    def get_technical_debt(self, priority: str | None = None) -> list[TechnicalDebt]:
        """
        Get technical debt items.

        Args:
            priority: Optional priority filter

        Returns:
            List of technical debt
        """
        if priority:
            return [d for d in self._debt if d.priority == priority]
        return self._debt.copy()

    def search_decisions(self, query: str) -> list[EngineeringDecision]:
        """
        Search decisions by query.

        Args:
            query: Search query

        Returns:
            List of matching decisions
        """
        query_lower = query.lower()
        return [
            d
            for d in self._decisions
            if query_lower in d.key.lower() or query_lower in d.decision.lower()
        ]

    def get_decision(self, key: str) -> EngineeringDecision | None:
        """
        Get a specific decision by key.

        Args:
            key: Decision key

        Returns:
            EngineeringDecision or None
        """
        for d in self._decisions:
            if d.key == key:
                return d
        return None

    def get_bugs_by_severity(self, severity: str) -> list[KnownBug]:
        """
        Get bugs by severity.

        Args:
            severity: Severity level

        Returns:
            List of bugs
        """
        return [b for b in self._bugs if b.severity == severity]

    def _save(self):
        """Save engineering memory to file."""
        try:
            memory_file = self.repository_path / ".aura_engineering_memory.json"
            data = {
                "decisions": [d.to_dict() for d in self._decisions],
                "bugs": [b.to_dict() for b in self._bugs],
                "technical_debt": [t.to_dict() for t in self._debt],
            }
            memory_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving engineering memory: {e}")

    def _load(self):
        """Load engineering memory from file."""
        try:
            memory_file = self.repository_path / ".aura_engineering_memory.json"

            if not memory_file.exists():
                return

            data = json.loads(memory_file.read_text(encoding="utf-8"))

            self._decisions = [
                EngineeringDecision(**d) for d in data.get("decisions", [])
            ]
            self._bugs = [KnownBug(**b) for b in data.get("bugs", [])]
            self._debt = [TechnicalDebt(**t) for t in data.get("technical_debt", [])]

            logger.info(
                f"Loaded engineering memory with {len(self._decisions)} decisions"
            )
        except Exception as e:
            logger.error(f"Error loading engineering memory: {e}")
