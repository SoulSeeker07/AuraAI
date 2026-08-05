"""
Executive Planner Agent - Goal analysis and task coordination.

The Executive Planner is the central decision-making agent. It:
- Analyzes user goals and objectives
- Breaks complex goals into executable subtasks
- Assigns tasks to appropriate specialized agents
- Coordinates task execution and monitoring
- Manages task dependencies and priorities
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .task_model import Task, TaskInput, TaskPriority, TaskType, create_task


class PlannerAgent:
    """
    The Executive Planner that orchestrates all agent operations.

    The planner:
    1. Analyzes user requests and extracts goals
    2. Decomposes goals into subtasks
    3. Routes tasks to appropriate agents
    4. Monitors execution progress
    5. Handles failures and retries
    6. Coordinatess multi-agent workflows
    """

    def __init__(self, task_manager):
        """
        Initialize the planner.

        Args:
            task_manager: TaskManager instance for task orchestration
        """
        self.task_manager = task_manager
        self._registered_agents: dict[str, Any] = {}
        self._registered_skills: dict[str, dict] = {}

    def register_agent(self, agent_name: str, agent_instance: Any) -> None:
        """
        Register a specialized agent.

        Args:
            agent_name: Name of the agent
            agent_instance: Agent instance
        """
        self._registered_agents[agent_name] = agent_instance

    def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent."""
        if agent_name in self._registered_agents:
            del self._registered_agents[agent_name]

    def register_skill(
        self, skill_name: str, skill_definition: dict, description: str = ""
    ) -> None:
        """
        Register a reusable skill (workflow).

        Args:
            skill_name: Unique skill identifier
            skill_definition: Skill configuration with tasks
            description: Human-readable description
        """
        self._registered_skills[skill_name] = {
            "definition": skill_definition,
            "description": description,
            "registered_at": datetime.now(),
        }

    def unregister_skill(self, skill_name: str) -> None:
        """Unregister a skill."""
        if skill_name in self._registered_skills:
            del self._registered_skills[skill_name]

    def analyze_goal(self, user_request: str) -> dict[str, Any]:
        """
        Analyze a user request and extract the core goal.

        Args:
            user_request: User's natural language request

        Returns:
            Goal analysis with type, components, and priority
        """
        # This is a simplified goal analysis
        # In production, this would use an LLM for semantic understanding

        request_lower = user_request.lower()

        # Detect goal type
        if any(
            word in request_lower
            for word in ["create", "build", "make", "generate", "develop"]
        ):
            goal_type = "creation"
        elif any(
            word in request_lower
            for word in ["research", "learn", "find", "understand", "analyze"]
        ):
            goal_type = "research"
        elif any(word in request_lower for word in ["fix", "debug", "error", "bug"]):
            goal_type = "debug"
        elif any(
            word in request_lower for word in ["organize", "sort", "clean", "manage"]
        ):
            goal_type = "organization"
        else:
            goal_type = "general"

        # Detect priority
        priority = TaskPriority.MEDIUM
        if any(
            word in request_lower for word in ["urgent", "important", "immediately"]
        ):
            priority = TaskPriority.URGENT
        elif any(word in request_lower for word in ["quickly", "soon", "asap"]):
            priority = TaskPriority.HIGH

        return {
            "type": goal_type,
            "request": user_request,
            "priority": priority.value,
            "components": self._extract_goal_components(user_request),
            "suggested_agents": self._suggest_agents(goal_type),
            "confidence": 0.85,
        }

    def _extract_goal_components(self, request: str) -> list[str]:
        """Extract key components from a request."""
        components = []

        # Simple keyword extraction (replace with LLM in production)
        if any(
            word in request.lower() for word in ["python", "flask", "django", "web"]
        ):
            components.append("web_development")

        if any(
            word in request.lower() for word in ["powerpoint", "presentation", "slides"]
        ):
            components.append("presentation")

        if any(word in request.lower() for word in ["code", "program", "script"]):
            components.append("coding")

        if any(word in request.lower() for word in ["pdf", "document", "file"]):
            components.append("document_processing")

        if any(word in request.lower() for word in ["search", "find", "research"]):
            components.append("web_search")

        if not components:
            components.append("general_processing")

        return components

    def _suggest_agents(self, goal_type: str) -> list[str]:
        """Suggest which agents should handle this goal."""
        agent_mapping = {
            "creation": ["coding", "research", "vision"],
            "research": ["research", "learning"],
            "debug": ["coding", "research"],
            "organization": ["desktop", "coding"],
            "general": ["research", "coding", "vision"],
        }
        return agent_mapping.get(goal_type, ["research", "coding"])

    def decompose_goal(
        self, goal_analysis: dict[str, Any], user_context: dict = None
    ) -> list[dict[str, Any]]:
        """
        Decompose a goal into executable subtasks.

        Args:
            goal_analysis: Goal analysis from analyze_goal()
            user_context: Additional context about the user

        Returns:
            List of task configurations
        """
        task_configs = []
        goal_type = goal_analysis.get("type", "general")

        # Create task decomposition based on goal type
        if goal_type == "creation":
            task_configs = self._decompose_creation_goal(goal_analysis)
        elif goal_type == "research":
            task_configs = self._decompose_research_goal(goal_analysis)
        elif goal_type == "debug":
            task_configs = self._decompose_debug_goal(goal_analysis)
        elif goal_type == "organization":
            task_configs = self._decompose_organization_goal(goal_analysis)
        else:
            task_configs = self._decompose_general_goal(goal_analysis)

        # Apply priority and context
        for config in task_configs:
            config["priority"] = goal_analysis.get("priority", "medium")

        return task_configs

    def _decompose_creation_goal(self, goal_analysis: dict) -> list[dict[str, Any]]:
        """Decompose a creation goal (e.g., "Create a Flask website")."""
        return [
            {
                "type": TaskType.RESEARCH_WEB,
                "title": "Research requirements and best practices",
                "description": "Research web development requirements for this project",
                "input": {"scope": "web_development"},
            },
            {
                "type": TaskType.CODE_GENERATE,
                "title": "Generate code structure",
                "description": "Generate initial code structure",
                "input": {"framework": "flask"},
            },
            {
                "type": TaskType.CODE_GENERATE,
                "title": "Implement core functionality",
                "description": "Implement main application features",
                "input": {"feature": "core"},
            },
            {
                "type": TaskType.TEST_GENERATE,
                "title": "Generate test suite",
                "description": "Create unit tests",
                "input": {"coverage": "80%"},
            },
            {
                "type": TaskType.CODE_DOCUMENT,
                "title": "Generate documentation",
                "description": "Create README and API docs",
                "input": {"format": "markdown"},
            },
        ]

    def _decompose_research_goal(self, goal_analysis: dict) -> list[dict[str, Any]]:
        """Decompose a research goal."""
        return [
            {
                "type": TaskType.RESEARCH_WEB,
                "title": "Initial web research",
                "description": "Search for initial information",
                "input": {"depth": "quick"},
            },
            {
                "type": TaskType.DEEP_RESEARCH,
                "title": "Deep dive into topic",
                "description": "Conduct deep research on key aspects",
                "input": {"focus": "main_topic"},
            },
            {
                "type": TaskType.RESEARCH_WEB,
                "title": "Find additional resources",
                "description": "Search for supplementary materials",
                "input": {"depth": "moderate"},
            },
        ]

    def _decompose_debug_goal(self, goal_analysis: dict) -> list[dict[str, Any]]:
        """Decompose a debug goal."""
        return [
            {
                "type": TaskType.CODE_ANALYSIS,
                "title": "Analyze code for issues",
                "description": "Review code for potential bugs",
                "input": {"scope": "project"},
            },
            {
                "type": TaskType.RESEARCH_WEB,
                "title": "Research error solutions",
                "description": "Search for solutions to the error",
                "input": {"error_context": "from_code_analysis"},
            },
            {
                "type": TaskType.CODE_DEBUG,
                "title": "Apply fixes",
                "description": "Apply identified fixes to code",
                "input": {"patches": "multiple"},
            },
            {
                "type": TaskType.TEST_GENERATE,
                "title": "Test fixes",
                "description": "Create tests to verify fixes",
                "input": {"verify": "true"},
            },
        ]

    def _decompose_organization_goal(self, goal_analysis: dict) -> list[dict[str, Any]]:
        """Decompose an organization goal."""
        return [
            {
                "type": TaskType.FILE_SEARCH,
                "title": "Search for files to organize",
                "description": "Find files that need organization",
                "input": {"scope": "downloads"},
            },
            {
                "type": TaskType.FILE_RENAME,
                "title": "Rename files",
                "description": "Apply consistent naming conventions",
                "input": {"pattern": "conventional"},
            },
            {
                "type": TaskType.FILE_MOVE,
                "title": "Move files to correct locations",
                "description": "Organize files by category",
                "input": {"structure": "logical"},
            },
            {
                "type": TaskType.CODE_DOCUMENT,
                "title": "Document organization changes",
                "description": "Record organization strategy",
                "input": {"format": "log"},
            },
        ]

    def _decompose_general_goal(self, goal_analysis: dict) -> list[dict[str, Any]]:
        """Decompose a general goal."""
        return [
            {
                "type": TaskType.RESEARCH_WEB,
                "title": "Initial exploration",
                "description": "Gather basic information",
                "input": {"depth": "quick"},
            },
            {
                "type": TaskType.GENERAL,
                "title": "Execute task",
                "description": "Perform the requested action",
                "input": {"action": "from_request"},
            },
        ]

    async def execute_goal(self, user_request: str, user_context: dict = None) -> Task:
        """
        Execute a user goal from natural language.

        Args:
            user_request: User's natural language request
            user_context: Additional context

        Returns:
            Root task that coordinates the entire workflow
        """
        # Analyze the goal
        goal_analysis = self.analyze_goal(user_request)

        # Decompose into subtasks
        task_configs = self.decompose_goal(goal_analysis, user_context)

        # Create root task
        root_task = create_task(
            task_type=TaskType.GENERAL,
            title=f"Execute: {goal_analysis['request']}",
            description=f"Goal type: {goal_analysis['type']}",
            priority=TaskPriority(goal_analysis.get("priority", "medium").upper()),
            total_steps=len(task_configs),
            context={"goal_analysis": goal_analysis},
        )

        # Register result callback for root task
        def on_complete(task: Task):
            print(f"Goal execution completed: {task.title}")
            print(f"  Status: {task.status.value}")
            print(f"  Progress: {task.progress * 100:.1f}%")
            if task.output:
                print(f"  Output: {task.output.message}")

        root_task.result_callback = on_complete

        # Create subtasks
        for i, config in enumerate(task_configs):
            task = create_task(
                task_type=config.get("type", TaskType.GENERAL),
                title=config.get("title", f"Task {i + 1}"),
                description=config.get("description", ""),
                priority=TaskPriority(config.get("priority", "medium").upper()),
                input=TaskInput(data=config.get("input", {})),
                parent_task_id=root_task.id,
                total_steps=1,
                progress=0.0,
            )

            # Register subtask callback
            def make_subtask_callback(subtask: Task):
                def callback(t: Task):
                    print(f"  Task completed: {t.title} - {t.status.value}")

                return callback

            task.result_callback = make_subtask_callback(task)

            # Add to task manager
            self.task_manager.create_task(task.type.value, task.title, task.description)

        print(f"Planner created workflow: {root_task.title}")
        print(f"  Steps: {len(task_configs)}")
        print(f"  Tasks: {len(root_task.subtasks)}")

        return root_task

    def get_workflow_summary(self, task_id: str) -> dict[str, Any]:
        """
        Get summary of a task workflow.

        Args:
            task_id: Task ID

        Returns:
            Workflow summary
        """
        task = self.task_manager.get_task(task_id)
        if not task:
            return {"error": "Task not found"}

        return {
            "id": task.id,
            "title": task.title,
            "status": task.status.value,
            "progress": task.progress,
            "steps_completed": task.steps_completed,
            "total_steps": task.total_steps,
            "subtasks": [
                self.task_manager.get_task(st_id).to_dict_summary()
                for st_id in task.subtasks
            ],
        }

    def get_registered_skills(self) -> list[dict[str, Any]]:
        """Get list of registered skills."""
        return [
            {"name": name, "description": skill["description"]}
            for name, skill in self._registered_skills.items()
        ]

    def use_skill(self, skill_name: str, skill_input: dict = None) -> Task:
        """
        Execute a registered skill.

        Args:
            skill_name: Name of skill to execute
            skill_input: Input data for the skill

        Returns:
            Task representing skill execution
        """
        skill = self._registered_skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill not registered: {skill_name}")

        definition = skill["definition"]
        input_data = skill_input or {}

        # Extract tasks from skill definition
        tasks = definition.get("tasks", [])

        if not tasks:
            raise ValueError(f"Skill {skill_name} has no tasks defined")

        # Create root task
        root_task = create_task(
            task_type=TaskType.GENERAL,
            title=f"Skill: {skill_name}",
            description=skill["description"],
            total_steps=len(tasks),
            context={"skill_name": skill_name, "skill_input": input_data},
        )

        # Create task configurations from skill definition
        for i, task_config in enumerate(tasks):
            task = create_task(
                task_type=task_config.get("type", TaskType.GENERAL),
                title=task_config.get("title", f"Skill Step {i + 1}"),
                description=task_config.get("description", ""),
                input=TaskInput(
                    data={"skill_input": input_data, **task_config.get("input", {})}
                ),
                parent_task_id=root_task.id,
                total_steps=1,
                progress=0.0,
            )

            # Register callback
            def make_callback(task: Task):
                def callback(t: Task):
                    print(f"  Skill step completed: {t.title} - {t.status.value}")

                return callback

            task.result_callback = make_callback(task)

            # Create task in manager
            self.task_manager.create_task(task.type.value, task.title, task.description)

        return root_task
