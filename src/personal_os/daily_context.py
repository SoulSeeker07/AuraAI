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

    def __init__(
        self,
        state_store: PersonalOSStateStore | None = None,
        memory_engine: Any | None = None,
    ) -> None:
        self.state_store = state_store or PersonalOSStateStore.get_instance()
        self.memory_engine = memory_engine

    def _get_memory_engine(self) -> Any | None:
        """Lazily initialize CognitiveMemoryEngine if not provided."""
        if self.memory_engine is not None:
            return self.memory_engine
        try:
            from memory.cognitive_memory import CognitiveMemoryEngine

            self.memory_engine = CognitiveMemoryEngine()
            return self.memory_engine
        except Exception as e:
            logger.debug(f"[DailyContextEngine] Cognitive memory init notice: {e}")
            return None

    def get_daily_context(self, target_date: str | None = None) -> DailyContext:
        """
        Generate DailyContext for today (or specified YYYY-MM-DD date).
        """
        today_str = target_date or datetime.now().strftime("%Y-%m-%d")

        mem_engine = self._get_memory_engine()
        preferences: dict[str, str] = {}
        if mem_engine and hasattr(mem_engine, "get_active_preferences"):
            try:
                active_prefs = mem_engine.get_active_preferences()
                for p in active_prefs:
                    cat = p.metadata.get("category", "general")
                    kw = p.metadata.get("keyword", "")
                    if cat and kw:
                        preferences[cat] = kw
            except Exception as e:
                logger.debug(f"[DailyContextEngine] Active preference fetch notice: {e}")

        meetings = self._fetch_calendar_events(today_str)
        tasks = self._fetch_tasks(today_str)
        deadlines = self._fetch_deadlines(today_str)

        context = DailyContext(
            date=today_str,
            meetings=meetings,
            tasks=tasks,
            deadlines=deadlines,
            preferences=preferences,
        )
        context.summary = context.format_summary()
        return context

    def _fetch_calendar_events(self, date_str: str) -> list[CalendarMeeting]:
        """Fetch meetings for date from CalendarPlugin / Backend if available with deduplication."""
        meetings: list[CalendarMeeting] = []
        seen_keys: set[str] = set()

        try:
            from plugins.calendar.calendar_plugin import CalendarPlugin

            plugin = CalendarPlugin()
            plugin.load()
            plugin.initialize()
            res = plugin.execute(capability="calendar.list_events", date=date_str)
            if isinstance(res, dict) and "events" in res:
                for ev in res["events"]:
                    title = ev.get("title", "Untitled Meeting").strip()
                    start_time = ev.get("start_time", "09:00").strip()
                    dedup_key = f"{start_time}_{title.lower()}"
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)
                    meetings.append(
                        CalendarMeeting(
                            title=title,
                            start_time=start_time,
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
                title = ev.get("title", "Meeting").strip()
                start_time = ev.get("start_time", "10:00").strip()
                dedup_key = f"{start_time}_{title.lower()}"
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                meetings.append(
                    CalendarMeeting(
                        title=title,
                        start_time=start_time,
                        end_time=ev.get("end_time"),
                        location=ev.get("location"),
                    )
                )

        return meetings

    def _fetch_tasks(self, date_str: str) -> list[TaskItem]:
        """Fetch pending tasks from memory, triggers, and state store with deduplication."""
        tasks: list[TaskItem] = []
        seen_titles: set[str] = set()

        # 1. Check stored tasks in PersonalOSStateStore
        cached_tasks = self.state_store.get_preference("tasks_list", [])
        for t in cached_tasks:
            if t.get("status", "PENDING") != "COMPLETED":
                raw_title = t.get("title", "Task").strip()
                normalized_title = raw_title.lower()
                if normalized_title in seen_titles:
                    continue
                seen_titles.add(normalized_title)
                tasks.append(
                    TaskItem(
                        task_id=t.get("task_id", f"task_{len(tasks)+1}"),
                        title=raw_title,
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
                routine_title = f"Routine: {trig.name} ({trig.goal_text})".strip()
                if routine_title.lower() in seen_titles:
                    continue
                seen_titles.add(routine_title.lower())
                tasks.append(
                    TaskItem(
                        task_id=f"routine_{trig.trigger_id}",
                        title=routine_title,
                        priority=priority,
                        category="automation",
                        source="trigger",
                    )
                )

        # 3. Query Cognitive Memory with recall_ranked and access reinforcement
        mem_engine = self._get_memory_engine()
        if mem_engine:
            try:
                if hasattr(mem_engine, "recall_ranked"):
                    recalled = mem_engine.recall_ranked(
                        "task todo priority deadline milestone today",
                        limit=10,
                        record_access_stats=True,
                    )
                else:
                    recalled = mem_engine.search_memories(query="task todo priority deadline milestone today", limit=10)

                for m in recalled:
                    content = m.content.strip()
                    importance = getattr(m, "importance", 0.5)
                    prio = "HIGH" if importance >= 0.8 else "NORMAL"
                    norm_content = content[:80].lower()
                    if norm_content in seen_titles:
                        continue

                    if (
                        "task" in content.lower()
                        or "todo" in content.lower()
                        or "deadline" in content.lower()
                        or "milestone" in content.lower()
                        or importance >= 0.8
                    ):
                        seen_titles.add(norm_content)
                        tasks.append(
                            TaskItem(
                                task_id=f"mem_{getattr(m, 'memory_id', 'unknown')}",
                                title=content[:80],
                                priority=prio,
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
