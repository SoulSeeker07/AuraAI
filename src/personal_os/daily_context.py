"""
Daily Context Engine
Location: src/personal_os/daily_context.py

Synthesizes prioritized tasks, calendar meetings, and project deadlines
from memory, calendar provider, and Personal OS stores to answer
'What do I need to do today?' in < 2 seconds.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from .models import CalendarMeeting, DailyContext, DeadlineItem, TaskItem
from .state_store import PersonalOSStateStore

logger = logging.getLogger(__name__)


class DailyContextEngine:
    """
    Synthesizes multi-source context into a cohesive, prioritized daily agenda.
    """

    def __init__(self, state_store: PersonalOSStateStore | None = None) -> None:
        self.state_store = state_store or PersonalOSStateStore.get_instance()

    def get_daily_context(self, target_date: str | None = None) -> DailyContext:
        """
        Generate DailyContext for today (or specified YYYY-MM-DD date).
        """
        today_str = target_date or datetime.now().strftime("%Y-%m-%d")

        meetings = self._fetch_calendar_events(today_str)
        tasks = self._fetch_tasks(today_str)
        deadlines = self._fetch_deadlines(today_str)

        context = DailyContext(
            date=today_str,
            meetings=meetings,
            tasks=tasks,
            deadlines=deadlines,
        )
        context.summary = context.format_summary()
        return context

    def _fetch_calendar_events(self, date_str: str) -> list[CalendarMeeting]:
        """Fetch meetings for date from CalendarPlugin / Backend if available."""
        meetings: list[CalendarMeeting] = []
        try:
            from plugins.calendar.calendar_plugin import CalendarPlugin

            plugin = CalendarPlugin()
            plugin.load()
            plugin.initialize()
            res = plugin.execute(capability="calendar.list_events", date=date_str)
            if isinstance(res, dict) and "events" in res:
                for ev in res["events"]:
                    meetings.append(
                        CalendarMeeting(
                            title=ev.get("title", "Untitled Meeting"),
                            start_time=ev.get("start_time", "09:00"),
                            end_time=ev.get("end_time"),
                            location=ev.get("location"),
                            attendees=ev.get("attendees", []),
                            description=ev.get("description"),
                        )
                    )
        except Exception as e:
            logger.debug(f"[DailyContextEngine] Calendar fetch notice: {e}")

        # If no events found or plugin unavailable, check state_store preferences/mock storage
        if not meetings:
            stored_events = self.state_store.get_preference(f"calendar_events_{date_str}", [])
            for ev in stored_events:
                meetings.append(
                    CalendarMeeting(
                        title=ev.get("title", "Meeting"),
                        start_time=ev.get("start_time", "10:00"),
                        end_time=ev.get("end_time"),
                        location=ev.get("location"),
                    )
                )

        return meetings

    def _fetch_tasks(self, date_str: str) -> list[TaskItem]:
        """Fetch pending tasks from memory and state store."""
        tasks: list[TaskItem] = []

        # 1. Check stored tasks in PersonalOSStateStore
        cached_tasks = self.state_store.get_preference("tasks_list", [])
        for t in cached_tasks:
            if t.get("status", "PENDING") != "COMPLETED":
                tasks.append(
                    TaskItem(
                        task_id=t.get("task_id", f"task_{len(tasks)+1}"),
                        title=t.get("title", "Task"),
                        priority=t.get("priority", "NORMAL").upper(),
                        status=t.get("status", "PENDING"),
                        due_date=t.get("due_date"),
                        category=t.get("category", "general"),
                    )
                )

        # 2. Check active triggers configured as routines due on target date
        try:
            target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            target_dt = datetime.now()

        triggers = self.state_store.list_triggers(enabled_only=True)
        for trig in triggers:
            if self._is_trigger_due_on(trig.schedule, target_dt):
                priority = trig.metadata.get("priority", "NORMAL").upper() if trig.metadata else "NORMAL"
                tasks.append(
                    TaskItem(
                        task_id=f"routine_{trig.trigger_id}",
                        title=f"Routine: {trig.name} ({trig.goal_text})",
                        priority=priority,
                        category="automation",
                        source="trigger",
                    )
                )

        # 3. Query Cognitive Memory for recent task memories
        try:
            from memory.cognitive_memory import CognitiveMemoryEngine

            mem_engine = CognitiveMemoryEngine()
            recalled = mem_engine.search_memories(query="tasks todo priorities deadlines today", limit=5)
            for m in recalled:
                if "task" in m.content.lower() or "todo" in m.content.lower():
                    tasks.append(
                        TaskItem(
                            task_id=f"mem_{m.memory_id}",
                            title=m.content[:80],
                            priority="NORMAL",
                            source="cognitive_memory",
                        )
                    )
        except Exception as e:
            logger.warning(f"[DailyContextEngine] Cognitive memory recall warning: {e}")

        # If completely empty, provide standard active project awareness tasks
        if not tasks:
            tasks.append(
                TaskItem(
                    task_id="default_dev_1",
                    title="Review active project codebase & milestones",
                    priority="NORMAL",
                    category="development",
                )
            )

        return tasks

    def _fetch_deadlines(self, date_str: str) -> list[DeadlineItem]:
        """Fetch upcoming deadlines."""
        deadlines: list[DeadlineItem] = []
        stored_deadlines = self.state_store.get_preference("deadlines_list", [])
        for d in stored_deadlines:
            deadlines.append(
                DeadlineItem(
                    title=d.get("title", "Milestone Deadline"),
                    due_date=d.get("due_date", date_str),
                    is_overdue=d.get("is_overdue", False),
                    source=d.get("source", "system"),
                )
            )
        return deadlines

    def _match_cron_field(self, pattern: str, value: int, is_dow: bool = False) -> bool:
        """Evaluate whether an integer matches a cron field pattern (*, digit, range, list, step)."""
        pattern = pattern.strip()
        if pattern == "*":
            return True
        if is_dow and pattern in ("0", "7") and value in (0, 7):
            return True
        if pattern.isdigit():
            return int(pattern) == value
        if "-" in pattern:
            try:
                start_v, end_v = map(int, pattern.split("-"))
                return start_v <= value <= end_v
            except ValueError:
                return True
        if "," in pattern:
            try:
                allowed = [int(x) for x in pattern.split(",")]
                if is_dow and (0 in allowed or 7 in allowed) and value in (0, 7):
                    return True
                return value in allowed
            except ValueError:
                return True
        if pattern.startswith("*/"):
            try:
                step = int(pattern[2:])
                return value % step == 0
            except ValueError:
                return True
        return True

    def _is_trigger_due_on(self, schedule: str, target_date: datetime) -> bool:
        """
        Evaluate whether a trigger schedule is active on target_date across all cron date fields.
        Complies with standard POSIX cron semantics:
        - Month must match.
        - If BOTH Day-of-Month (DOM) and Day-of-Week (DOW) are restricted (neither is '*'),
          the trigger fires if EITHER matches (DOM or DOW).
        - If only one is restricted, that restricted field must match.
        - If both are '*', any day in matching months fires.
        """
        if not schedule or schedule.strip() in ("daily", "* * * * *"):
            return True

        parts = schedule.strip().split()
        if len(parts) == 5:
            dom_pattern = parts[2].strip()    # Day of month (1-31)
            month_pattern = parts[3].strip()  # Month (1-12)
            dow_pattern = parts[4].strip()    # Day of week (0-7)

            # Month must match
            if not self._match_cron_field(month_pattern, target_date.month):
                return False

            dom_restricted = dom_pattern != "*"
            dow_restricted = dow_pattern != "*"

            dom_matches = self._match_cron_field(dom_pattern, target_date.day)
            py_weekday = target_date.weekday()
            cron_dow = 7 if py_weekday == 6 else (py_weekday + 1)
            dow_matches = self._match_cron_field(dow_pattern, cron_dow, is_dow=True)

            # Standard POSIX Cron rule:
            # If both dom and dow are restricted, match if DOM or DOW matches.
            if dom_restricted and dow_restricted:
                return dom_matches or dow_matches
            elif dom_restricted:
                return dom_matches
            elif dow_restricted:
                return dow_matches
            else:
                return True

        return True
