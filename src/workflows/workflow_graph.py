"""
Workflow Graph

Manages workflow execution with steps, variables, conditions, and loops.
"""


import logging
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta

from .workflow_step import WorkflowStep, StepType, Action, Condition, ErrorHandling
from .models import WorkflowStatus


logger = logging.getLogger(__name__)


class WorkflowGraph:
    """
    Manages workflow execution with steps, variables, and conditions.
    """

    def __init__(self, workflow_id: str, name: str):
        """
        Initialize workflow graph.

        Args:
            workflow_id: Workflow ID
            name: Workflow name
        """
        self.workflow_id = workflow_id
        self.name = name
        self.steps: Dict[str, WorkflowStep] = {}
        self.active = True
        self.completed_at: Optional[datetime] = None

    def add_step(self, step: WorkflowStep) -> 'WorkflowGraph':
        """
        Add a step to the workflow.

        Args:
            step: Workflow step

        Returns:
            Self for chaining
        """
        self.steps[step.step_id] = step
        logger.debug(f"Added step {step.step_id[:8]} to workflow {self.workflow_id[:8]}")
        return self

    def remove_step(self, step_id: str) -> bool:
        """
        Remove a step from the workflow.

        Args:
            step_id: Step ID

        Returns:
            Success
        """
        if step_id not in self.steps:
            return False

        del self.steps[step_id]
        logger.debug(f"Removed step {step_id[:8]} from workflow {self.workflow_id[:8]}")
        return True

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """
        Get step by ID.

        Args:
            step_id: Step ID

        Returns:
            Step or None
        """
        return self.steps.get(step_id)

    def get_step_by_index(self, index: int) -> Optional[WorkflowStep]:
        """
        Get step by index.

        Args:
            index: Step index

        Returns:
            Step or None
        """
        step_ids = list(self.steps.keys())
        if 0 <= index < len(step_ids):
            return self.steps[step_ids[index]]
        return None

    def get_next_step(self, current_step_id: str) -> Optional[str]:
        """
        Get next step ID.

        Args:
            current_step_id: Current step ID

        Returns:
            Next step ID or None
        """
        step_ids = list(self.steps.keys())
        try:
            current_index = step_ids.index(current_step_id)
            if current_index + 1 < len(step_ids):
                return step_ids[current_index + 1]
        except ValueError:
            pass
        return None

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Get steps that can execute in parallel.

        Returns:
            List of parallel execution groups
        """
        # Simple approach: group steps with no dependencies on other steps in same group
        groups: List[List[str]] = []
        remaining_steps = set(self.steps.keys())

        while remaining_steps:
            group = []
            for step_id in list(remaining_steps):
                step = self.steps[step_id]
                if all(dep not in remaining_steps for dep in step.dependencies):
                    group.append(step_id)
                    remaining_steps.remove(step_id)
                    break  # Start new group

            if group:
                groups.append(group)

        return groups

    def get_ready_steps(self) -> List[str]:
        """
        Get steps ready to execute.

        Returns:
            List of ready step IDs
        """
        ready_steps = []

        for step_id, step in self.steps.items():
            if step.status.value == 'ready' or step.status.value == 'pending':
                # Check if all dependencies are completed
                if all(dep_id in self.steps and self.steps[dep_id].status.value in ['completed', 'skipped'] for dep_id in step.dependencies):
                    ready_steps.append(step_id)

        return ready_steps

    def mark_step_started(self, step_id: str):
        """
        Mark step as started.

        Args:
            step_id: Step ID
        """
        if step_id in self.steps:
            self.steps[step_id].mark_started()
            logger.debug(f"Marked step {step_id[:8]} as started")

    def mark_step_completed(self, step_id: str, success: bool, output: Any = None):
        """
        Mark step as completed.

        Args:
            step_id: Step ID
            success: Whether step succeeded
            output: Step output
        """
        if step_id in self.steps:
            self.steps[step_id].mark_completed(success, output)
            logger.debug(f"Marked step {step_id[:8]} as completed: {'success' if success else 'failed'}")

    def mark_step_failed(self, step_id: str, error: str):
        """
        Mark step as failed.

        Args:
            step_id: Step ID
            error: Error message
        """
        if step_id in self.steps:
            self.steps[step_id].mark_failed(error)
            logger.error(f"Marked step {step_id[:8]} as failed: {error}")

    def mark_step_skipped(self, step_id: str, reason: str = ""):
        """
        Mark step as skipped.

        Args:
            step_id: Step ID
            reason: Skip reason
        """
        if step_id in self.steps:
            self.steps[step_id].mark_skipped(reason)
            logger.debug(f"Marked step {step_id[:8]} as skipped: {reason}")

    def update_variable(self, variable_name: str, value: Any):
        """
        Update variable value.

        Args:
            variable_name: Variable name
            value: New value
        """
        if variable_name in self.variables:
            self.variables[variable_name]['value'] = value
        else:
            self.variables[variable_name] = {
                'value': value,
                'description': f'Workflow variable: {variable_name}',
                'modified_at': datetime.now()
            }

    def get_variable(self, variable_name: str) -> Any:
        """
        Get variable value.

        Args:
            variable_name: Variable name

        Returns:
            Variable value or None
        """
        return self.variables.get(variable_name, {}).get('value')

    def evaluate_condition(self, condition: Condition, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition.

        Args:
            condition: Condition to evaluate
            context: Evaluation context

        Returns:
            True if condition is met
        """
        if condition.condition_type == ConditionType.ATTRIBUTE_CHECK:
            # Check if attribute exists and matches value
            attr_name = condition.get('attribute_name', '')
            attr_value = context.get(attr_name)

            if condition.get('expected_value') is not None:
                return attr_value == condition['expected_value']
            else:
                return attr_value is not None

        elif condition.condition_type == ConditionType.VALUE_CHECK:
            # Check if value meets criteria
            value = context.get('value')
            operator = condition.get('operator', '==')

            if operator == '==':
                return value == condition.get('expected_value')
            elif operator == '!=':
                return value != condition.get('expected_value')
            elif operator == '>':
                return value > condition.get('expected_value')
            elif operator == '<':
                return value < condition.get('expected_value')
            elif operator == 'exists':
                return value is not None

        elif condition.condition_type == ConditionType.CUSTOM:
            # Execute custom condition function
            func = condition.get('custom_function')
            if func and callable(func):
                return func(context)

        return False

    def apply_loop(self, loop_step: WorkflowStep, collection: Any, context: Dict[str, Any]) -> List[Any]:
        """
        Apply loop iteration.

        Args:
            loop_step: Loop step
            collection: Collection to iterate over
            context: Execution context

        Returns:
            List of iteration results
        """
        results = []
        loop_type = loop_step.loop_config.get('type', 'for_each')
        item_variable = loop_step.loop_config.get('item_variable', 'item')

        if loop_type == 'for_each':
            for item in collection:
                # Set item in context
                context[item_variable] = item

                # Execute step
                result = self._execute_step(loop_step, context)
                results.append(result)

        elif loop_type == 'while':
            max_iterations = loop_step.loop_config.get('max_iterations', 100)
            iteration = 0
            while iteration < max_iterations:
                context['iteration'] = iteration

                # Check condition
                condition_met = self.evaluate_condition(
                    loop_step.loop_config.get('condition', {}),
                    context
                )

                if not condition_met:
                    break

                # Execute step
                result = self._execute_step(loop_step, context)
                results.append(result)

                iteration += 1

        elif loop_type == 'for_range':
            start = loop_step.loop_config.get('start', 0)
            end = loop_step.loop_config.get('end', 10)
            step = loop_step.loop_config.get('step', 1)

            for i in range(start, end, step):
                context['index'] = i
                context['value'] = i

                # Execute step
                result = self._execute_step(loop_step, context)
                results.append(result)

        return results

    def _execute_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Any:
        """
        Execute a workflow step.

        Args:
            step: Step to execute
            context: Execution context

        Returns:
            Step output
        """
        step.mark_started()

        try:
            # Execute step based on type
            if step.step_type == StepType.ACTION:
                result = self._execute_action(step.action, context)
                step.mark_completed(True, result)
                return result
            elif step.step_type == StepType.WAIT:
                # Wait for specified duration
                wait_time = step.action_config.get('wait_seconds', 1)
                import time
                time.sleep(wait_time)
                step.mark_completed(True, f"Waited {wait_time}s")
                return f"Waited {wait_time}s"
            elif step.step_type == StepType.ECHO:
                # Log message
                message = step.action_config.get('message', '')
                print(f"[ECHO] {message}")
                step.mark_completed(True, message)
                return message
            elif step.step_type == StepType.SET_VARIABLE:
                # Set variable
                var_name = step.action_config.get('variable_name', '')
                var_value = self._resolve_value(step.action_config.get('value', ''), context)
                context[var_name] = var_value
                step.mark_completed(True, var_value)
                return var_value
            elif step.step_type == StepType.CONDITION:
                # Check condition and branch
                condition_met = self.evaluate_condition(step.condition, context)

                if condition_met:
                    # Execute true branch
                    for branch_step_id in step.true_branch:
                        if branch_step_id in self.steps:
                            self._execute_step(self.steps[branch_step_id], context)
                else:
                    # Execute false branch
                    for branch_step_id in step.false_branch:
                        if branch_step_id in self.steps:
                            self._execute_step(self.steps[branch_step_id], context)

                step.mark_completed(True, "Condition checked")
                return "Condition checked"

        except Exception as e:
            error_handling = step.error_handling or ErrorHandling.CONTINUE
            step.mark_failed(str(e))

            if error_handling == ErrorHandling.CONTINUE:
                logger.warning(f"Step {step.step_id[:8]} failed but continuing: {e}")
                return None
            elif error_handling == ErrorHandling.STOP:
                logger.error(f"Step {step.step_id[:8]} failed and stopping: {e}")
                raise
            elif error_handling == ErrorHandling.ASK_USER:
                # Ask user for input
                user_input = input(f"Step {step.step_id[:8]} failed: {e}\nEnter value or 'skip': ")
                if user_input.lower() == 'skip':
                    step.mark_skipped("User skipped")
                    return None
                else:
                    step.mark_completed(True, user_input)
                    return user_input
            elif error_handling == ErrorHandling.RETRY:
                # Retry the step
                max_retries = step.action_config.get('max_retries', 3)
                retry_count = step.action_config.get('retry_count', 0)

                if retry_count < max_retries:
                    step.action_config['retry_count'] = retry_count + 1
                    import time
                    time.sleep(1)
                    return self._execute_step(step, context)
                else:
                    logger.error(f"Step {step.step_id[:8]} failed after {max_retries} retries: {e}")
                    raise

        return None

    def _execute_action(self, action: Action, context: Dict[str, Any]) -> Any:
        """
        Execute an action.

        Args:
            action: Action to execute
            context: Execution context

        Returns:
            Action output
        """
        if action.action_type == Action.Type.GOAL:
            # Execute agent runtime goal
            goal_id = action.get('goal', '')
            # Placeholder - would connect to Agent Runtime
            return f"Goal {goal_id} executed"
        elif action.action_type == Action.Type.TOOL:
            # Execute tool
            tool_name = action.get('tool', '')
            tool_params = action.get('parameters', {})
            # Placeholder - would connect to Tool Execution Engine
            return f"Tool {tool_name} executed with params {tool_params}"
        elif action.action_type == Action.Type.SCRIPT:
            # Execute Python script
            script = action.get('script', '')
            # Placeholder - would execute script
            return f"Script executed"
        elif action.action_type == Action.Type.PROMPT_USER:
            # Prompt user
            prompt_text = action.get('prompt', 'Enter value:')
            user_input = input(prompt_text)
            return user_input

        return None

    def _resolve_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """
        Resolve value from context or literal.

        Args:
            value: Value to resolve
            context: Execution context

        Returns:
            Resolved value
        """
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            # Get from context
            var_name = value[2:-1]
            return context.get(var_name)
        return value

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert workflow graph to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'step_count': len(self.steps),
            'steps': [step.to_dict() for step in self.steps.values()]
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"WorkflowGraph(id={self.workflow_id[:8]}, steps={len(self.steps)}, active={self.active})"
