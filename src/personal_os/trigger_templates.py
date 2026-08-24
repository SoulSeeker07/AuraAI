"""
Personal OS Trigger Templates
Location: src/personal_os/trigger_templates.py

Provides reusable routine templates for one-command goal-based automation
(e.g., morning standup prep, downloads organization, codebase health check).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .state_store import PersonalOSTrigger

logger = logging.getLogger(__name__)


@dataclass
class TriggerTemplate:
    """Blueprint for creating structured personal automation triggers."""

    name: str
    description: str
    goal_template: str
    default_schedule: str
    required_domains: list[str] = field(default_factory=lambda: ["desktop"])
    default_vars: dict[str, Any] = field(default_factory=dict)

    def build_goal(self, context: dict[str, Any] | None = None) -> str:
        """Resolve template variables into a concrete goal string."""
        merged = dict(self.default_vars)
        if context:
            merged.update(context)

        # Built-in context dynamic defaults
        if "today_date" not in merged:
            merged["today_date"] = datetime.now().strftime("%Y-%m-%d")
        if "current_project" not in merged:
            merged["current_project"] = "AuraAI"

        goal = self.goal_template
        for key, val in merged.items():
            goal = goal.replace(f"{{{key}}}", str(val))
        return goal


class TriggerTemplateRegistry:
    """Registry of pre-configured routine templates for Personal OS."""

    def __init__(self) -> None:
        self._templates: dict[str, TriggerTemplate] = {}
        self._register_default_templates()

    def _register_default_templates(self) -> None:
        self.register(
            TriggerTemplate(
                name="standup_prep",
                description="Prepare morning standup summary with recent git commits & tasks",
                goal_template="Review recent git commits in {current_project}, check pending tasks, and prepare morning standup summary for {today_date}",
                default_schedule="0 9 * * 1-5",
                required_domains=["desktop", "coding", "memory"],
            )
        )
        self.register(
            TriggerTemplate(
                name="organize_downloads",
                description="Sort and organize files in Downloads folder by category",
                goal_template="Organize files in Downloads folder into categorized subdirectories",
                default_schedule="0 18 * * 5",
                required_domains=["desktop"],
            )
        )
        self.register(
            TriggerTemplate(
                name="codebase_health",
                description="Run test suite and inspect repository git working tree",
                goal_template="Run test suite for {current_project} and verify clean working tree",
                default_schedule="0 12 * * *",
                required_domains=["coding", "desktop"],
            )
        )
        self.register(
            TriggerTemplate(
                name="daily_agenda_sync",
                description="Synthesize daily calendar meetings, tasks, and deadlines",
                goal_template="Synthesize daily context and prioritize today's agenda",
                default_schedule="0 8 * * *",
                required_domains=["desktop", "memory"],
            )
        )

    def register(self, template: TriggerTemplate) -> None:
        self._templates[template.name] = template

    def get(self, name: str) -> TriggerTemplate | None:
        return self._templates.get(name)

    def list_templates(self) -> list[TriggerTemplate]:
        return list(self._templates.values())

    def instantiate(
        self,
        template_name: str,
        name: str | None = None,
        schedule: str | None = None,
        custom_vars: dict[str, Any] | None = None,
    ) -> PersonalOSTrigger:
        """Create a PersonalOSTrigger from a template."""
        tmpl = self.get(template_name)
        if tmpl is None:
            raise ValueError(f"Unknown trigger template: '{template_name}'")

        goal = tmpl.build_goal(custom_vars)
        trigger_name = name or tmpl.name
        trigger_sched = schedule or tmpl.default_schedule

        return PersonalOSTrigger(
            trigger_id=f"trig_{trigger_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            name=trigger_name,
            goal_text=goal,
            schedule=trigger_sched,
            template_vars=custom_vars or {},
            metadata={"template": template_name, "required_domains": tmpl.required_domains},
        )
