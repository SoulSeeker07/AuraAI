"""
Agent Runtime

The main orchestrator for autonomous goal execution.
Transforms Aura from a command executor to a goal-driven autonomous system.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .approval_manager import ApprovalManager
from .dependency_manager import DependencyManager
from .execution_graph import ExecutionGraph
from .execution_history import EventType, ExecutionHistory
from .goal import Goal
from .models import GoalStatus
from .planner import Planner
from .progress_manager import ProgressManager
from .recovery_manager import RecoveryManager
from .scheduler import Scheduler
from .task import Task

logger = logging.getLogger(__name__)


class AgentRuntime:
    """
    The main orchestrator for autonomous goal execution.

    The Agent Runtime transforms Aura from a command executor into a
    goal-driven autonomous system capable of planning, coordinating,
    executing, and completing complex multi-step goals.
    """

    def __init__(
        self,
        on_goal_start: Callable[["AgentRuntime", Goal], None] | None = None,
        on_goal_complete: Callable[["AgentRuntime", Goal], None] | None = None,
        on_goal_fail: Callable[["AgentRuntime", Goal, str], None] | None = None,
        on_agent_ready: Callable[["AgentRuntime"], None] | None = None,
    ):
        """
        Initialize Agent Runtime.

        Args:
            on_goal_start: Callback when goal starts
            on_goal_complete: Callback when goal completes
            on_goal_fail: Callback when goal fails
            on_agent_ready: Callback when agent is ready
        """
        # Callbacks
        self.on_goal_start = on_goal_start
        self.on_goal_complete = on_goal_complete
        self.on_goal_fail = on_goal_fail
        self.on_agent_ready = on_agent_ready

        # Core components
        self.planner = Planner(
            on_plan_generated=self._on_plan_generated,
            on_task_created=self._on_task_created,
        )
        self.scheduler = Scheduler(
            on_task_complete=self._on_task_complete,
            on_task_fail=self._on_task_fail,
            on_task_progress=self._on_task_progress,
        )
        self.dependency_manager = None
        self.approval_manager = ApprovalManager()
        self.recovery_manager = RecoveryManager(
            on_recover=self._on_recover,
            on_fail_permanently=self._on_fail_permanently,
            on_pause=self._on_pause,
        )
        self.progress_manager = ProgressManager()
        self.execution_history = ExecutionHistory()
        self.goal_memory = None

        # State
        self.current_goal: Goal | None = None
        self.execution_graph: ExecutionGraph | None = None
        self.is_running = False
        self.execution_thread: threading.Thread | None = None

        logger.info("Agent Runtime initialized")

        if self.on_agent_ready:
            self.on_agent_ready(self)

    def create_goal(self, description: str, **kwargs) -> str:
        """
        Create a new goal.

        Args:
            description: Goal description
            **kwargs: Additional goal parameters

        Returns:
            Goal ID
        """
        goal = Goal(description=description, **kwargs)

        self.execution_history.log_goal_created(goal.goal_id, description)

        logger.info(f"Created goal {goal.goal_id[:8]}: {description[:50]}")

        return goal.goal_id

    def plan_goal(self, goal_id: str) -> bool:
        """
        Plan a goal (convert to execution plan).

        Args:
            goal_id: Goal ID to plan

        Returns:
            True if planning succeeded
        """
        goal = self._get_goal(goal_id)
        if not goal:
            logger.error(f"Goal {goal_id[:8]} not found")
            return False

        # Create execution graph
        graph = self.planner.plan_goal(goal)

        # Initialize dependency manager
        self.dependency_manager = DependencyManager(graph)

        # Initialize goal memory
        self.goal_memory = type(
            "GoalMemory",
            (),
            {
                "goal_id": goal_id,
                "goal_description": description,
                "variables": {},
                "intermediate_results": {},
                "generated_files": {},
                "task_outputs": {},
                "current_step": "",
                "step_progress": 0.0,
                "created_at": datetime.now(),
                "last_accessed": datetime.now(),
                "memory_size": 0,
                "set_variable": lambda name, value, persistent=False: None,
                "get_variable": lambda name: None,
                "set_intermediate_result": lambda key, result, desc="": None,
                "get_intermediate_result": lambda key: None,
                "add_generated_file": lambda filename, filepath: None,
                "get_generated_file": lambda filename: None,
                "store_task_output": lambda task_id, output: None,
                "get_task_output": lambda task_id: None,
                "update_step": lambda step, progress: None,
                "get_memory_summary": lambda: {},
                "export_to_dict": lambda: {},
                "get_persistent_data": lambda: {},
                "get_context_for_task": lambda task_id: {},
                "_update_memory_size": lambda: None,
                "cleanup": lambda: None,
            },
        )

        # Initialize progress manager
        self.progress_manager.reset_for_new_goal(goal)

        self.execution_graph = graph

        logger.info(f"Goal {goal_id[:8]} planned successfully")
        return True

    def execute_goal(self, goal_id: str) -> bool:
        """
        Execute a goal.

        Args:
            goal_id: Goal ID to execute

        Returns:
            True if execution succeeded
        """
        # Check if already running
        if self.is_running:
            logger.error("Agent is already running a goal")
            return False

        # Get and plan goal
        if not self.plan_goal(goal_id):
            return False

        goal = self.execution_graph.goal
        self.current_goal = goal

        # Mark goal as started
        goal.mark_started()
        self.execution_history.log_goal_started(goal_id, len(goal.tasks))
        self.execution_history.update_goal_progress(goal)

        if self.on_goal_start:
            self.on_goal_start(self, goal)

        # Start execution
        self.is_running = True
        self.execution_thread = threading.Thread(
            target=self._execution_loop, args=(goal_id,), daemon=True
        )
        self.execution_thread.start()

        logger.info(f"Started execution of goal {goal_id[:8]}")
        return True

    def pause_goal(self, goal_id: str) -> bool:
        """
        Pause a running goal.

        Args:
            goal_id: Goal ID to pause

        Returns:
            True if paused successfully
        """
        goal = self._get_goal(goal_id)
        if not goal or not goal.is_active:
            return False

        # Stop scheduler
        self.scheduler.cancel_all()
        self.is_running = False

        goal.status = GoalStatus.PAUSED
        self.execution_history.log_event(
            EventType.PAUSED, goal_id=goal_id, detail="Goal paused"
        )

        logger.info(f"Paused goal {goal_id[:8]}")
        return True

    def resume_goal(self, goal_id: str) -> bool:
        """
        Resume a paused goal.

        Args:
            goal_id: Goal ID to resume

        Returns:
            True if resumed successfully
        """
        goal = self._get_goal(goal_id)
        if not goal or goal.status != GoalStatus.PAUSED:
            return False

        goal.status = GoalStatus.RUNNING
        self.is_running = True
        self.execution_thread = threading.Thread(
            target=self._execution_loop, args=(goal_id,), daemon=True
        )
        self.execution_thread.start()

        self.execution_history.log_event(
            EventType.RESUMED, goal_id=goal_id, detail="Goal resumed"
        )

        logger.info(f"Resumed goal {goal_id[:8]}")
        return True

    def cancel_goal(self, goal_id: str) -> bool:
        """
        Cancel a goal.

        Args:
            goal_id: Goal ID to cancel

        Returns:
            True if cancelled successfully
        """
        goal = self._get_goal(goal_id)
        if not goal:
            return False

        # Cancel all tasks
        self.scheduler.cancel_all()
        self.is_running = False

        # Mark goal as cancelled
        goal.mark_cancelled()
        self.execution_history.log_event(
            EventType.GOAL_CANCELLED, goal_id=goal_id, detail="Goal cancelled"
        )

        logger.info(f"Cancelled goal {goal_id[:8]}")
        return True

    def get_progress(self, goal_id: str) -> float | None:
        """
        Get goal progress.

        Args:
            goal_id: Goal ID

        Returns:
            Progress (0.0 - 1.0)
        """
        return self.progress_manager.get_goal_progress(goal_id)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get runtime statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "is_running": self.is_running,
            "current_goal_id": self.current_goal.goal_id if self.current_goal else None,
            "execution_graph": (
                self.execution_graph.to_dict() if self.execution_graph else {}
            ),
            "scheduler_stats": self.scheduler.get_execution_stats(),
            "progress_stats": self.progress_manager.get_statistics(),
            "history_stats": self.execution_history.get_statistics(),
        }

    def _execution_loop(self, goal_id: str):
        """
        Main execution loop.

        Args:
            goal_id: Goal ID to execute
        """
        logger.info(f"Execution loop started for goal {goal_id[:8]}")

        try:
            # Schedule the execution graph
            self.scheduler.schedule_graph(self.execution_graph)

            # Wait for completion
            self.scheduler.wait_for_completion()

            # Check for failures
            failed_tasks = self.scheduler.get_failed_tasks()
            if failed_tasks:
                logger.error(
                    f"Goal {goal_id[:8]} completed with {len(failed_tasks)} failed tasks"
                )
                self.current_goal.mark_failed(f"{len(failed_tasks)} tasks failed")
                self.execution_history.log_goal_failed(
                    goal_id, f"{len(failed_tasks)} tasks failed"
                )
                if self.on_goal_fail:
                    self.on_goal_fail(
                        self, self.current_goal, f"{len(failed_tasks)} tasks failed"
                    )
            else:
                logger.info(f"Goal {goal_id[:8]} completed successfully")
                self.current_goal.mark_completed()
                self.execution_history.log_goal_completed(
                    goal_id, self.current_goal.duration.total_seconds()
                )
                if self.on_goal_complete:
                    self.on_goal_complete(self, self.current_goal)

        except Exception as e:
            logger.error(f"Goal {goal_id[:8]} failed with error: {e}", exc_info=True)
            self.current_goal.mark_failed(str(e))
            self.execution_history.log_error(goal_id, error=str(e))
            if self.on_goal_fail:
                self.on_goal_fail(self, self.current_goal, str(e))

        finally:
            self.is_running = False
            self.current_goal = None
            self.execution_graph = None
            self.goal_memory = None

            logger.info(f"Execution loop stopped for goal {goal_id[:8]}")

    # Callback methods
    def _on_plan_generated(self, planner: Planner, graph: ExecutionGraph):
        """Called when plan is generated."""
        self.execution_graph = graph

    def _on_task_created(self, planner: Planner, task: Task):
        """Called when task is created."""
        self.execution_history.log_task_created(
            task.task_id, graph.goal.goal_id, task.goal
        )

    def _on_task_complete(self, scheduler: Scheduler, task: Task):
        """Called when task completes."""
        self.execution_history.log_task_completed(
            task.task_id,
            graph.goal.goal_id,
            task.duration.total_seconds() if task.duration else 0,
        )

        if self.current_goal:
            self.execution_graph.update_goal_progress(task)

    def _on_task_fail(self, scheduler: Scheduler, task: Task):
        """Called when task fails."""
        self.execution_history.log_task_failed(
            task.task_id, graph.goal.goal_id, task.error or "Unknown error"
        )

        # Handle recovery
        recovery_action = self.recovery_manager.handle_task_failure(task)
        self.execution_history.log_recovery_applied(
            task.task_id, graph.goal.goal_id, recovery_action
        )

    def _on_task_progress(self, scheduler: Scheduler, task: Task, progress: float):
        """Called when task progress updates."""
        detail = self.progress_manager.get_progress_summary(task.task_id).get(
            "last_detail", ""
        )

        self.execution_history.log_progress_update(
            task.task_id, graph.goal.goal_id, progress, detail
        )

        self.progress_manager.update_task_progress(task, progress, detail)

    def _on_recover(self, manager: RecoveryManager, task: Task, action: str):
        """Called when recovery is applied."""
        logger.info(f"Recovery applied: {action} for task {task.task_id[:8]}")

    def _on_fail_permanently(self, manager: RecoveryManager, task: Task):
        """Called when task fails permanently."""
        logger.error(f"Task {task.task_id[:8]} failed permanently")

    def _on_pause(self, manager: RecoveryManager, task: Task):
        """Called when task is paused."""
        logger.warning(f"Task {task.task_id[:8]} paused")

    # Helper methods
    def _get_goal(self, goal_id: str) -> Goal | None:
        """Get goal by ID."""
        if self.current_goal and self.current_goal.goal_id == goal_id:
            return self.current_goal

        return None
