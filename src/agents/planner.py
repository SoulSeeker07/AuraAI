"""
Planner

Converts goals into executable execution plans.
"""


import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from .goal import Goal
from .task import Task
from .execution_graph import ExecutionGraph
from .models import TaskPriority, TaskRiskLevel, TaskType


logger = logging.getLogger(__name__)


class Planner:
    """
    Converts goals into executable execution plans.

    The Planner analyzes user goals and breaks them down into
    smaller, executable tasks with dependencies and metadata.
    """

    def __init__(
        self,
        on_plan_generated: Optional[Callable[['Planner', ExecutionGraph], None]] = None,
        on_task_created: Optional[Callable[['Planner', Task], None]] = None
    ):
        """
        Initialize planner.

        Args:
            on_plan_generated: Callback when plan is generated
            on_task_created: Callback when task is created
        """
        self.on_plan_generated = on_plan_generated
        self.on_task_created = on_task_created

        logger.debug("Initialized planner")

    def plan_goal(self, goal: Goal) -> ExecutionGraph:
        """
        Convert a goal into an execution plan.

        Args:
            goal: Goal to plan

        Returns:
            Execution graph with tasks
        """
        logger.info(f"Planning goal: {goal.description[:50]}")

        # Create execution graph
        graph = ExecutionGraph(goal)

        # Generate tasks based on goal type
        tasks = self._generate_tasks(goal)

        # Add tasks to graph
        for task in tasks:
            graph.add_task(task)

        # Log the plan
        self._log_plan(graph)

        # Notify callback
        if self.on_plan_generated:
            self.on_plan_generated(self, graph)

        return graph

    def _generate_tasks(self, goal: Goal) -> List[Task]:
        """
        Generate tasks based on goal description.

        Args:
            goal: Goal to generate tasks for

        Returns:
            List of tasks
        """
        tasks = []

        # Detect goal type and generate appropriate tasks
        goal_lower = goal.description.lower()

        # File operations
        if self._is_file_operation(goal_lower):
            tasks.extend(self._plan_file_operation(goal))

        # Git operations
        elif self._is_git_operation(goal_lower):
            tasks.extend(self._plan_git_operation(goal))

        # Network operations
        elif self._is_network_operation(goal_lower):
            tasks.extend(self._plan_network_operation(goal))

        # Document operations
        elif self._is_document_operation(goal_lower):
            tasks.extend(self._plan_document_operation(goal))

        # General task
        else:
            tasks.extend(self._plan_general_task(goal))

        logger.info(f"Generated {len(tasks)} tasks for goal")

        return tasks

    def _plan_general_task(self, goal: Goal) -> List[Task]:
        """
        Plan a general task.

        Args:
            goal: Goal to plan

        Returns:
            List of tasks
        """
        tasks = []

        # Create main task
        main_task = Task(
            goal=goal.description,
            task_type="general",
            priority=self._calculate_priority(goal.priority),
            estimated_duration=goal.estimated_total_duration,
            risk_level=self._calculate_risk(goal.risk_level),
            description=f"Execute general task: {goal.description[:50]}",
            parent_goal_id=goal.goal_id
        )

        if self.on_task_created:
            self.on_task_created(self, main_task)

        tasks.append(main_task)

        return tasks

    def _plan_file_operation(self, goal: Goal) -> List[Task]:
        """
        Plan file operations.

        Args:
            goal: Goal to plan

        Returns:
            List of tasks
        """
        tasks = []

        # File operation tasks
        analyze_task = Task(
            goal=f"Analyze file operation: {goal.description[:50]}",
            task_type="file_operation",
            priority=TaskPriority.HIGH,
            estimated_duration=timedelta(minutes=2),
            risk_level=TaskRiskLevel.MEDIUM,
            description="Analyze file operation requirements",
            parent_goal_id=goal.goal_id
        )

        execute_task = Task(
            goal=f"Execute file operation: {goal.description[:50]}",
            task_type="file_operation",
            priority=TaskPriority.HIGH,
            estimated_duration=timedelta(minutes=5),
            risk_level=self._calculate_risk(goal.risk_level),
            description="Execute file operation",
            dependencies=[analyze_task.task_id],
            parent_goal_id=goal.goal_id
        )

        if self.on_task_created:
            self.on_task_created(self, analyze_task)
            self.on_task_created(self, execute_task)

        tasks.extend([analyze_task, execute_task])

        return tasks

    def _plan_git_operation(self, goal: Goal) -> List[Task]:
        """
        Plan git operations.

        Args:
            goal: Goal to plan

        Returns:
            List of tasks
        """
        tasks = []

        # Git operation tasks
        analyze_task = Task(
            goal=f"Analyze git changes: {goal.description[:50]}",
            task_type="git_operation",
            priority=TaskPriority.HIGH,
            estimated_duration=timedelta(minutes=2),
            risk_level=TaskRiskLevel.MEDIUM,
            description="Analyze git repository state",
            parent_goal_id=goal.goal_id
        )

        create_backup = Task(
            goal=f"Create git backup: {goal.description[:50]}",
            task_type="git_operation",
            priority=TaskPriority.NORMAL,
            estimated_duration=timedelta(minutes=1),
            risk_level=TaskRiskLevel.LOW,
            description="Create backup before operations",
            dependencies=[analyze_task.task_id],
            parent_goal_id=goal.goal_id
        )

        execute_task = Task(
            goal=f"Execute git operation: {goal.description[:50]}",
            task_type="git_operation",
            priority=TaskPriority.HIGH,
            estimated_duration=timedelta(minutes=3),
            risk_level=self._calculate_risk(goal.risk_level),
            description="Execute git operation",
            dependencies=[create_backup.task_id],
            parent_goal_id=goal.goal_id
        )

        if self.on_task_created:
            self.on_task_created(self, analyze_task)
            self.on_task_created(self, create_backup)
            self.on_task_created(self, execute_task)

        tasks.extend([analyze_task, create_backup, execute_task])

        return tasks

    def _plan_network_operation(self, goal: Goal) -> List[Task]:
        """
        Plan network operations.

        Args:
            goal: Goal to plan

        Returns:
            List of tasks
        """
        tasks = []

        # Network operation tasks
        analyze_task = Task(
            goal=f"Analyze network requirements: {goal.description[:50]}",
            task_type="network_operation",
            priority=TaskPriority.NORMAL,
            estimated_duration=timedelta(minutes=2),
            risk_level=TaskRiskLevel.MEDIUM,
            description="Analyze network connectivity",
            parent_goal_id=goal.goal_id
        )

        execute_task = Task(
            goal=f"Execute network operation: {goal.description[:50]}",
            task_type="network_operation",
            priority=TaskPriority.HIGH,
            estimated_duration=timedelta(minutes=5),
            risk_level=self._calculate_risk(goal.risk_level),
            description="Execute network operation",
            dependencies=[analyze_task.task_id],
            parent_goal_id=goal.goal_id
        )

        if self.on_task_created:
            self.on_task_created(self, analyze_task)
            self.on_task_created(self, execute_task)

        tasks.extend([analyze_task, execute_task])

        return tasks

    def _plan_document_operation(self, goal: Goal) -> List[Task]:
        """
        Plan document operations.

        Args:
            goal: Goal to plan

        Returns:
            List of tasks
        """
        tasks = []

        # Document operation tasks
        analyze_task = Task(
            goal=f"Analyze document structure: {goal.description[:50]}",
            task_type="document_operation",
            priority=TaskPriority.NORMAL,
            estimated_duration=timedelta(minutes=2),
            risk_level=TaskRiskLevel.LOW,
            description="Analyze document structure",
            parent_goal_id=goal.goal_id
        )

        process_task = Task(
            goal=f"Process document: {goal.description[:50]}",
            task_type="document_operation",
            priority=TaskPriority.HIGH,
            estimated_duration=timedelta(minutes=5),
            risk_level=TaskRiskLevel.MEDIUM,
            description="Process document",
            dependencies=[analyze_task.task_id],
            parent_goal_id=goal.goal_id
        )

        if self.on_task_created:
            self.on_task_created(self, analyze_task)
            self.on_task_created(self, process_task)

        tasks.extend([analyze_task, process_task])

        return tasks

    def _is_file_operation(self, goal_text: str) -> bool:
        """Check if goal involves file operations."""
        file_keywords = ['create', 'write', 'read', 'delete', 'move', 'copy', 'rename', 'backup', 'file']
        return any(kw in goal_text for kw in file_keywords)

    def _is_git_operation(self, goal_text: str) -> bool:
        """Check if goal involves git operations."""
        git_keywords = ['git', 'commit', 'push', 'pull', 'branch', 'merge', 'commit', 'repository']
        return any(kw in goal_text for kw in git_keywords)

    def _is_network_operation(self, goal_text: str) -> bool:
        """Check if goal involves network operations."""
        network_keywords = ['download', 'upload', 'internet', 'server', 'api', 'request', 'http']
        return any(kw in goal_text for kw in network_keywords)

    def _is_document_operation(self, goal_text: str) -> bool:
        """Check if goal involves document operations."""
        doc_keywords = ['document', 'pdf', 'word', 'excel', 'slide', 'report', 'note']
        return any(kw in goal_text for kw in doc_keywords)

    def _calculate_priority(self, goal_priority: str) -> TaskPriority:
        """Convert goal priority to task priority."""
        priority_map = {
            'HIGH': TaskPriority.HIGH,
            'NORMAL': TaskPriority.NORMAL,
            'LOW': TaskPriority.LOW
        }
        return priority_map.get(goal_priority, TaskPriority.NORMAL)

    def _calculate_risk(self, risk_level: str) -> TaskRiskLevel:
        """Convert goal risk to task risk."""
        risk_map = {
            'LOW': TaskRiskLevel.LOW,
            'MEDIUM': TaskRiskLevel.MEDIUM,
            'HIGH': TaskRiskLevel.HIGH,
            'CRITICAL': TaskRiskLevel.CRITICAL
        }
        return risk_map.get(risk_level, TaskRiskLevel.MEDIUM)

    def _log_plan(self, graph: ExecutionGraph):
        """
        Log the generated plan.

        Args:
            graph: Execution graph to log
        """
        logger.info(f"Generated plan for goal {graph.goal.goal_id[:8]}")
        logger.info(f"  Total tasks: {len(graph.tasks)}")

        # Get parallel execution groups
        parallel_groups = graph.get_parallel_execution_groups()
        logger.info(f"  Parallel groups: {len(parallel_groups)}")

        # Log each task
        for i, task in enumerate(graph.tasks.values(), 1):
            deps = graph.get_task_dependencies(task.task_id)
            logger.info(f"  {i}. {task.task_id[:8]} - {task.goal[:50]} (deps: {len(deps)})")
