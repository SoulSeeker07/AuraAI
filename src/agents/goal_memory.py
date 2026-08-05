"""
Goal Memory

Manages temporary memory during goal execution.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class GoalMemory:
    """
    Manages temporary memory during goal execution.

    The Goal Memory stores intermediate results, variables, and
    generated files for active goals. It's automatically destroyed
    after completion unless promoted to long-term memory.
    """

    def __init__(self, goal_id: str, goal_description: str):
        """
        Initialize goal memory.

        Args:
            goal_id: ID of the goal
            goal_description: Description of the goal
        """
        self.goal_id = goal_id
        self.goal_description = goal_description

        # Memory storage
        self.variables: dict[str, Any] = {}  # name -> value
        self.intermediate_results: dict[str, Any] = {}  # key -> result
        self.generated_files: dict[str, str] = {}  # filename -> path
        self.task_outputs: dict[str, Any] = {}  # task_id -> output

        # Progress
        self.current_step: str | None = None
        self.step_progress: float = 0.0

        # Metadata
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.memory_size = 0  # bytes

        logger.debug(f"Initialized goal memory for {goal_id[:8]}")

    def set_variable(self, name: str, value: Any, persistent: bool = False):
        """
        Set a variable in memory.

        Args:
            name: Variable name
            value: Variable value
            persistent: Whether to preserve after completion
        """
        self.variables[name] = {
            "value": value,
            "type": type(value).__name__,
            "persistent": persistent,
            "set_at": datetime.now(),
        }
        self._update_memory_size()

        logger.debug(f"Set variable: {name} = {type(value).__name__}")

    def get_variable(self, name: str) -> Any | None:
        """
        Get a variable from memory.

        Args:
            name: Variable name

        Returns:
            Variable value or None
        """
        var_info = self.variables.get(name)
        if var_info:
            self.last_accessed = datetime.now()
            return var_info["value"]
        return None

    def set_intermediate_result(self, key: str, result: Any, description: str = ""):
        """
        Store an intermediate result.

        Args:
            key: Result key
            result: Result value
            description: Description of the result
        """
        self.intermediate_results[key] = {
            "value": result,
            "description": description,
            "stored_at": datetime.now(),
        }
        self._update_memory_size()

        logger.debug(f"Stored intermediate result: {key}")

    def get_intermediate_result(self, key: str) -> Any | None:
        """
        Get an intermediate result.

        Args:
            key: Result key

        Returns:
            Result value or None
        """
        result_info = self.intermediate_results.get(key)
        if result_info:
            self.last_accessed = datetime.now()
            return result_info["value"]
        return None

    def add_generated_file(self, filename: str, filepath: str):
        """
        Track a generated file.

        Args:
            filename: Generated filename
            filepath: Path to the file
        """
        self.generated_files[filename] = {"path": filepath, "added_at": datetime.now()}
        self._update_memory_size()

        logger.debug(f"Added generated file: {filename} -> {filepath}")

    def get_generated_file(self, filename: str) -> str | None:
        """
        Get a generated file path.

        Args:
            filename: Generated filename

        Returns:
            File path or None
        """
        file_info = self.generated_files.get(filename)
        if file_info:
            self.last_accessed = datetime.now()
            return file_info["path"]
        return None

    def store_task_output(self, task_id: str, output: Any):
        """
        Store output from a task.

        Args:
            task_id: ID of the task
            output: Task output
        """
        self.task_outputs[task_id] = {"output": output, "stored_at": datetime.now()}
        self._update_memory_size()

        logger.debug(f"Stored task output for {task_id[:8]}")

    def get_task_output(self, task_id: str) -> Any | None:
        """
        Get output from a task.

        Args:
            task_id: ID of the task

        Returns:
            Task output or None
        """
        output_info = self.task_outputs.get(task_id)
        if output_info:
            self.last_accessed = datetime.now()
            return output_info["output"]
        return None

    def update_step(self, step: str, progress: float):
        """
        Update current step and progress.

        Args:
            step: Current step description
            progress: Progress of current step (0.0 - 1.0)
        """
        self.current_step = step
        self.step_progress = max(0.0, min(1.0, progress))
        self.last_accessed = datetime.now()

        logger.debug(f"Step updated: {step} ({self.step_progress * 100:.1f}%)")

    def get_memory_summary(self) -> dict[str, Any]:
        """
        Get summary of memory contents.

        Returns:
            Memory summary dictionary
        """
        return {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "variables": {
                k: {
                    "type": v["type"],
                    "persistent": v["persistent"],
                    "set_at": v["set_at"].isoformat(),
                }
                for k, v in self.variables.items()
            },
            "intermediate_results": {
                k: {
                    "type": type(v["value"]).__name__,
                    "stored_at": v["stored_at"].isoformat(),
                }
                for k, v in self.intermediate_results.items()
            },
            "generated_files": list(self.generated_files.keys()),
            "task_outputs": list(self.task_outputs.keys()),
            "current_step": self.current_step,
            "step_progress": self.step_progress,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "memory_size": self.memory_size,
            "total_variables": len(self.variables),
            "total_intermediate_results": len(self.intermediate_results),
            "total_generated_files": len(self.generated_files),
            "total_task_outputs": len(self.task_outputs),
        }

    def export_to_dict(self) -> dict[str, Any]:
        """
        Export all memory to dictionary.

        Returns:
            Complete memory as dictionary
        """
        return {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "variables": self.variables,
            "intermediate_results": self.intermediate_results,
            "generated_files": self.generated_files,
            "task_outputs": self.task_outputs,
            "current_step": self.current_step,
            "step_progress": self.step_progress,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "memory_size": self.memory_size,
        }

    def get_persistent_data(self) -> dict[str, Any]:
        """
        Get only persistent data (to be promoted to long-term memory).

        Returns:
            Persistent data dictionary
        """
        return {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "variables": {
                k: v for k, v in self.variables.items() if v.get("persistent", False)
            },
            "intermediate_results": {
                k: v
                for k, v in self.intermediate_results.items()
                if v.get("persistent", False)
            },
            "generated_files": self.generated_files,
            "current_step": self.current_step,
            "step_progress": self.step_progress,
        }

    def get_context_for_task(self, task_id: str) -> dict[str, Any]:
        """
        Get context data for a specific task.

        Args:
            task_id: ID of task

        Returns:
            Context dictionary
        """
        context = {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "current_step": self.current_step,
            "step_progress": self.step_progress,
            "available_files": list(self.generated_files.keys()),
            "stored_variables": list(self.variables.keys()),
            "stored_results": list(self.intermediate_results.keys()),
        }

        return context

    def _update_memory_size(self):
        """Update memory size in bytes."""

        def get_size(obj: Any) -> int:
            if isinstance(obj, str):
                return len(obj.encode("utf-8"))
            elif isinstance(obj, (dict, list)):
                return sum(get_size(item) for item in obj.values())
            else:
                return len(str(obj).encode("utf-8"))

        size = (
            get_size(self.variables)
            + get_size(self.intermediate_results)
            + get_size(self.generated_files)
            + get_size(self.task_outputs)
        )
        self.memory_size = size

    def cleanup(self):
        """Clean up temporary memory."""
        # Keep persistent data, discard rest
        persistent_vars = {
            k: v for k, v in self.variables.items() if v.get("persistent", False)
        }
        persistent_results = {
            k: v
            for k, v in self.intermediate_results.items()
            if v.get("persistent", False)
        }

        self.variables = persistent_vars
        self.intermediate_results = persistent_results
        self.generated_files = {}
        self.task_outputs = {}
        self.current_step = None
        self.step_progress = 0.0

        logger.debug(f"Cleaned up goal memory for {self.goal_id[:8]}")
