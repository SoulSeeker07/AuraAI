"""
Skill System - Reusable workflow chains.

The Skill System provides:
- Pre-configured task chains
- Skill registration and discovery
- Skill execution
- Skill templates
- Skill management
"""

from __future__ import annotations

from typing import Any, List, Optional, Dict, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .task_model import Task, TaskInput, TaskOutput


class SkillCategory(Enum):
    """Categories for skills."""
    PRODUCTIVITY = "productivity"
    LEARNING = "learning"
    DEVELOPMENT = "development"
    RESEARCH = "research"
    SYSTEM = "system"
    AUTOMATION = "automation"
    CUSTOM = "custom"


@dataclass
class SkillStep:
    """A single step in a skill."""
    agent_type: str
    task_type: str
    input_template: dict[str, Any]
    description: str


@dataclass
class Skill:
    """
    Represents a skill (reusable workflow chain).

    Skills are pre-configured chains of tasks that can be executed
    with minimal user input.
    """
    skill_id: str
    name: str
    description: str
    category: SkillCategory
    steps: List[SkillStep] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    is_public: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    average_rating: float = 0.0
    tags: List[str] = field(default_factory=list)

    def add_step(
        self,
        agent_type: str,
        task_type: str,
        input_template: dict[str, Any],
        description: str = ""
    ):
        """Add a step to the skill."""
        step = SkillStep(
            agent_type=agent_type,
            task_type=task_type,
            input_template=input_template,
            description=description
        )
        self.steps.append(step)

    def to_task_chain(self, input_params: dict[str, Any]) -> List[Task]:
        """
        Convert skill steps to a task chain.

        Args:
            input_params: Parameters to fill into templates

        Returns:
            List of tasks
        """
        tasks = []

        for i, step in enumerate(self.steps):
            # Fill in template with input parameters
            task_input = self._fill_template(step.input_template, input_params)

            task = Task(
                id=f"{self.skill_id}_step_{i}",
                type=step.task_type,
                title=step.name or f"Skill step {i+1}",
                input=task_input,
                priority="MEDIUM",
                description=f"Skill step {i+1}: {step.description}"
            )

            tasks.append(task)

        return tasks

    def _fill_template(
        self,
        template: dict[str, Any],
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Fill template with parameter values.

        Args:
            template: Template dict
            params: Parameter values

        Returns:
            Filled template
        """
        result = {}

        for key, value in template.items():
            if isinstance(value, dict) and "param" in value:
                # Template with parameter reference
                param_key = value["param"]
                result[key] = params.get(param_key, value.get("default", ""))
            else:
                result[key] = value

        return result


class SkillRegistry:
    """
    Manages registered skills.

    Features:
    - Skill registration
    - Skill discovery
    - Skill execution
    - Skill management
    """

    def __init__(self):
        """Initialize the skill registry."""
        self._skills: Dict[str, Skill] = {}
        self._skills_by_category: Dict[SkillCategory, List[Skill]] = {}
        self._callbacks: List[Callable] = []

    def register_callback(self, callback: Callable):
        """Register a callback for skill events."""
        self._callbacks.append(callback)

    def _notify_callback(self, event_type: str, data: dict):
        """Notify all callbacks of an event."""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception:
                pass

    def register_skill(self, skill: Skill) -> bool:
        """
        Register a skill.

        Args:
            skill: Skill to register

        Returns:
            True if registered successfully
        """
        try:
            if skill.skill_id in self._skills:
                return False

            # Add to category index
            if skill.category not in self._skills_by_category:
                self._skills_by_category[skill.category] = []
            self._skills_by_category[skill.category].append(skill)

            # Store skill
            self._skills[skill.skill_id] = skill

            self._notify_callback("register", {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "category": skill.category.value
            })

            return True

        except Exception as e:
            self._notify_callback("register", {"error": str(e)})
            return False

    def unregister_skill(self, skill_id: str) -> bool:
        """
        Unregister a skill.

        Args:
            skill_id: Skill ID to unregister

        Returns:
            True if unregistered successfully
        """
        if skill_id not in self._skills:
            return False

        try:
            skill = self._skills[skill_id]

            # Remove from category index
            if skill.category in self._skills_by_category:
                self._skills_by_category[skill.category].remove(skill)

            # Remove from registry
            del self._skills[skill_id]

            self._notify_callback("unregister", {"skill_id": skill_id})

            return True

        except Exception:
            return False

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get skill by ID."""
        return self._skills.get(skill_id)

    def list_skills(
        self,
        category: Optional[SkillCategory] = None,
        is_public_only: bool = False
    ) -> List[Skill]:
        """
        List all skills.

        Args:
            category: Optional category filter
            is_public_only: Only return public skills

        Returns:
            List of skills
        """
        skills = self._skills.values()

        if category:
            skills = [s for s in skills if s.category == category]

        if is_public_only:
            skills = [s for s in skills if s.is_public]

        return sorted(skills, key=lambda s: s.usage_count, reverse=True)

    def get_skills_by_category(self, category: SkillCategory) -> List[Skill]:
        """Get skills by category."""
        return self._skills_by_category.get(category, []).copy()

    def search_skills(self, query: str) -> List[Skill]:
        """
        Search skills by name or description.

        Args:
            query: Search query

        Returns:
            List of matching skills
        """
        query_lower = query.lower()
        matching_skills = []

        for skill in self._skills.values():
            if query_lower in skill.name.lower() or query_lower in skill.description.lower():
                matching_skills.append(skill)

        return sorted(
            matching_skills,
            key=lambda s: s.usage_count,
            reverse=True
        )

    def execute_skill(
        self,
        skill_id: str,
        input_params: dict[str, Any],
        task_manager
    ) -> List[TaskOutput]:
        """
        Execute a skill.

        Args:
            skill_id: Skill ID to execute
            input_params: Parameters to pass to skill
            task_manager: Task manager for execution

        Returns:
            List of task outputs
        """
        skill = self._skills.get(skill_id)

        if not skill:
            return [TaskOutput(
                success=False,
                message=f"Skill not found: {skill_id}",
                error=f"No skill registered with ID '{skill_id}'"
            )]

        try:
            # Convert skill to task chain
            tasks = skill.to_task_chain(input_params)

            # Execute tasks
            outputs = []
            for task in tasks:
                result = task_manager.execute_task(task)
                outputs.append(result)

                # Increment usage count
                skill.usage_count += 1

                if not result.success:
                    break

            # Update rating based on success
            successes = sum(1 for o in outputs if o.success)
            if successes > 0:
                skill.average_rating = (
                    (skill.average_rating * (skill.usage_count - 1) + successes) / skill.usage_count
                )

            return outputs

        except Exception as e:
            return [TaskOutput(
                success=False,
                message=f"Skill execution failed: {skill.name}",
                error=str(e)
            )]

    def create_skill_from_template(
        self,
        skill_id: str,
        name: str,
        category: SkillCategory,
        steps: List[dict[str, Any]],
        description: str = ""
    ) -> Skill:
        """
        Create a skill from a template.

        Args:
            skill_id: Unique skill ID
            name: Display name
            category: Skill category
            steps: List of step definitions
            description: Skill description

        Returns:
            Created skill
        """
        skill = Skill(
            skill_id=skill_id,
            name=name,
            description=description,
            category=category
        )

        for step in steps:
            skill.add_step(
                agent_type=step.get("agent_type", "unknown"),
                task_type=step.get("task_type", "unknown"),
                input_template=step.get("input_template", {}),
                description=step.get("description", "")
            )

        self.register_skill(skill)
        return skill

    def get_skill_templates(self) -> List[dict[str, Any]]:
        """Get available skill templates."""
        return [
            {
                "id": "summarize_youtube",
                "name": "Summarize YouTube Video",
                "category": "RESEARCH",
                "description": "Summarize a YouTube video using web research",
                "steps": [
                    {"agent_type": "research", "task_type": "web_research", "input_template": {"query": "${video_url}"}},
                    {"agent_type": "research", "task_type": "deep_research", "input_template": {"topic": "${video_title}"}}
                ]
            },
            {
                "id": "weekly_review",
                "name": "Weekly Project Review",
                "category": "PRODUCTIVITY",
                "description": "Review completed work and plan next steps",
                "steps": [
                    {"agent_type": "learning", "task_type": "workflow_list", "input_template": {}},
                    {"agent_type": "coding", "task_type": "code_analysis", "input_template": {"project_path": "${project_path}"}}
                ]
            }
        ]


# Global skill registry instance
_global_skill_registry = None


def get_skill_registry() -> SkillRegistry:
    """Get global skill registry instance."""
    global _global_skill_registry
    if _global_skill_registry is None:
        _global_skill_registry = SkillRegistry()
    return _global_skill_registry
