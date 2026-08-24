"""
Personal OS Data Models
Location: src/personal_os/models.py

Defines structured models for daily context synthesis, task priorities,
calendar schedules, deadlines, and workspace search results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TaskItem:
    """Individual actionable task."""

    task_id: str
    title: str
    priority: str = "NORMAL"  # CRITICAL, HIGH, NORMAL, LOW
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, BLOCKED
    due_date: str | None = None
    category: str = "general"
    source: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeadlineItem:
    """Time-sensitive milestone or delivery deadline."""

    title: str
    due_date: str
    is_overdue: bool = False
    source: str = "calendar"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CalendarMeeting:
    """Calendar event or scheduled meeting."""

    title: str
    start_time: str
    end_time: str | None = None
    location: str | None = None
    attendees: list[str] = field(default_factory=list)
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyContext:
    """Synthesized daily schedule, priorities, and deadlines."""

    date: str
    meetings: list[CalendarMeeting] = field(default_factory=list)
    tasks: list[TaskItem] = field(default_factory=list)
    deadlines: list[DeadlineItem] = field(default_factory=list)
    summary: str = ""
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "meetings": [m.to_dict() for m in self.meetings],
            "tasks": [t.to_dict() for t in self.tasks],
            "deadlines": [d.to_dict() for d in self.deadlines],
            "summary": self.summary,
            "generated_at": self.generated_at,
        }

    def format_summary(self) -> str:
        """Render a clean human-readable prioritized markdown summary."""
        lines = [f"### 📅 Daily Overview — {self.date}\n"]

        # Meetings section
        if self.meetings:
            lines.append("#### 🤝 Meetings & Schedule")
            for m in self.meetings:
                time_str = m.start_time
                if m.end_time:
                    time_str += f" - {m.end_time}"
                loc = f" ({m.location})" if m.location else ""
                lines.append(f"- **{time_str}**: {m.title}{loc}")
            lines.append("")
        else:
            lines.append("#### 🤝 Meetings & Schedule\n- No scheduled meetings for today.\n")

        # Prioritized Tasks
        lines.append("#### ⚡ Prioritized Action Items")
        if self.tasks:
            priority_order = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}
            sorted_tasks = sorted(
                self.tasks,
                key=lambda t: priority_order.get(t.priority.upper(), 99),
            )
            for t in sorted_tasks:
                badge = f"[{t.priority.upper()}]"
                due = f" (Due: {t.due_date})" if t.due_date else ""
                lines.append(f"- {badge} {t.title}{due}")
            lines.append("")
        else:
            lines.append("- No pending tasks recorded.\n")

        # Deadlines
        if self.deadlines:
            lines.append("#### ⏰ Upcoming Deadlines")
            for d in self.deadlines:
                status = "⚠️ OVERDUE: " if d.is_overdue else ""
                lines.append(f"- {status}{d.title} (Due: {d.due_date})")
            lines.append("")

        return "\n".join(lines)


@dataclass
class SearchResult:
    """Workspace search match."""

    path: str
    filename: str
    line_number: int | None = None
    match_snippet: str | None = None
    score: float = 1.0
    last_modified: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
