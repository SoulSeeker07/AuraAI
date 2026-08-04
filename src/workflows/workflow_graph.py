"""
Workflow Graph

Manages workflow execution with steps, variables, conditions, and loops.
"""


import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from .workflow_step import WorkflowStep, ActionType
from .models import StepType, ConditionType, WorkflowStatus


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
        self.variables: Dict[str, Dict[str, Any]] = {}
        self.active = True
        self.status: WorkflowStatus = WorkflowStatus.CREATED
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None

    # ------------------------------------------------------------------
    # Workflow-level status tracking
    # ------------------------------------------------------------------

    def mark_started(self):
        """Mark the workflow as started/active."""
        self.status = WorkflowStatus.ACTIVE
        self.started_at = datetime.now()
        logger.info(f"Workflow {self.workflow_id[:8]} started")

    def mark_completed(self, success: bool = True):
        """Mark the workflow as completed."""
        self.status = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
        self.completed_at = datetime.now()
        logger.info(f"Workflow {self.workflow_id[:8]} marked {self.status.value}")

    def mark_failed(self, error: str):
        """Mark the workflow as failed."""
        self.status = WorkflowStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
        logger.error(f"Workflow {self.workflow_id[:8]} failed: {error}")

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

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
            else:
                # Safety valve: avoid an infinite loop if dependencies form
                # a cycle or reference unknown steps.
                logger.warning(
                    f"Workflow {self.workflow_id[:8]} has unresolved step "
                    f"dependencies among {remaining_steps}; forcing remaining "
                    f"steps into a final group"
                )
                groups.append(list(remaining_steps))
                remaining_steps.clear()

        return groups

    def get_ready_steps(self) -> List[str]:
        """
        Get steps ready to execute.

        Returns:
            List of ready step IDs
        """
        ready_steps = []

        for step_id, step in self.steps.items():
            if step.status.value == 'pending':
                if all(
                    dep_id in self.steps and self.steps[dep_id].status.value in ['completed', 'skipped']
                    for dep_id in step.dependencies
                ):
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
        if step_id not in self.steps:
            return
        step = self.steps[step_id]
        if success:
            step.mark_completed(output)
        else:
            step.mark_failed(str(output) if output is not None else "Step failed")
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

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def update_variable(self, variable_name: str, value: Any):
        """
        Update variable value.

        Args:
            variable_name: Variable name
            value: New value
        """
        if variable_name in self.variables:
            self.variables[variable_name]['value'] = value
            self.variables[variable_name]['modified_at'] = datetime.now()
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

    # ------------------------------------------------------------------
    # Conditions
    # ------------------------------------------------------------------

    def evaluate_condition(self, condition: Optional[Dict[str, Any]], context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition.

        Args:
            condition: Condition dict, shaped like:
                {'condition_type': 'attribute_check' | 'value_check' | 'custom',
                 'attribute_name', 'expected_value', 'operator', 'custom_function'}
            context: Evaluation context

        Returns:
            True if condition is met
        """
        if not condition:
            return False

        condition_type = condition.get('condition_type')

        if condition_type == ConditionType.ATTRIBUTE_CHECK.value:
            attr_name = condition.get('attribute_name', '')
            attr_value = context.get(attr_name)

            if condition.get('expected_value') is not None:
                return attr_value == condition['expected_value']
            return attr_value is not None

        elif condition_type == ConditionType.VALUE_CHECK.value:
            value = context.get('value')
            operator = condition.get('operator', '==')
            expected = condition.get('expected_value')

            if operator == '==':
                return value == expected
            elif operator == '!=':
                return value != expected
            elif operator == '>':
                return value > expected
            elif operator == '<':
                return value < expected
            elif operator == 'exists':
                return value is not None
            return False

        elif condition_type == ConditionType.CUSTOM.value:
            func = condition.get('custom_function')
            if func and callable(func):
                return func(context)
            return False

        return False

    # ------------------------------------------------------------------
    # Loops
    # ------------------------------------------------------------------

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
        loop_config = loop_step.loop or {}
        loop_type = loop_config.get('type', 'for_each')
        item_variable = loop_config.get('item_variable', 'item')

        if loop_type == 'for_each':
            for item in collection:
                context[item_variable] = item
                result = self._execute_step(loop_step, context)
                results.append(result)

        elif loop_type == 'while':
            max_iterations = loop_config.get('max_iterations', 100)
            iteration = 0
            while iteration < max_iterations:
                context['iteration'] = iteration

                condition_met = self.evaluate_condition(loop_config.get('condition'), context)
                if not condition_met:
                    break

                result = self._execute_step(loop_step, context)
                results.append(result)
                iteration += 1

        elif loop_type == 'for_range':
            start = loop_config.get('start', 0)
            end = loop_config.get('end', 10)
            step_size = loop_config.get('step', 1)

            for i in range(start, end, step_size):
                context['index'] = i
                context['value'] = i
                result = self._execute_step(loop_step, context)
                results.append(result)

        return results

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def _execute_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Any:
        """
        Execute a workflow step in-place (used directly by simple callers,
        and internally by apply_loop for loop-body execution).

        Args:
            step: Step to execute
            context: Execution context

        Returns:
            Step output
        """
        step.mark_started()

        try:
            action_config = step.action_config or {}

            if step.step_type == StepType.ACTION:
                result = self._execute_action(action_config, context)
                step.mark_completed(result)
                return result

            elif step.step_type == StepType.WAIT:
                wait_time = action_config.get('wait_seconds', action_config.get('duration', 1))
                time.sleep(wait_time)
                step.mark_completed(f"Waited {wait_time}s")
                return f"Waited {wait_time}s"

            elif step.step_type == StepType.ECHO:
                message = action_config.get('message', '')
                print(f"[ECHO] {message}")
                step.mark_completed(message)
                return message

            elif step.step_type == StepType.SET_VARIABLE:
                var_name = action_config.get('variable_name', '')
                var_value = self._resolve_value(action_config.get('value', ''), context)
                context[var_name] = var_value
                self.update_variable(var_name, var_value)
                step.mark_completed(var_value)
                return var_value

            elif step.step_type == StepType.GET_VARIABLE:
                var_name = action_config.get('variable_name', '')
                var_value = context.get(var_name, self.get_variable(var_name))
                step.mark_completed(var_value)
                return var_value

            elif step.step_type == StepType.CONDITION:
                condition_met = self.evaluate_condition(step.condition, context)
                decision = step.decision or {}

                branch_ids = decision.get('on_true', []) if condition_met else decision.get('on_false', [])
                for branch_step_id in branch_ids:
                    if branch_step_id in self.steps:
                        self._execute_step(self.steps[branch_step_id], context)

                step.mark_completed("Condition checked")
                return "Condition checked"

            else:
                # DECISION, LOOP, PROMPT_USER, MERGE, MERGE_CONFIG are
                # expected to be handled by the caller (WorkflowExecutor)
                # before delegating here. If we get here directly, do our
                # best generic effort so nothing silently no-ops.
                step.mark_completed(None)
                return None

        except Exception as e:
            on_error = step.on_error or 'continue'
            step.mark_failed(str(e))

            if on_error == 'continue':
                logger.warning(f"Step {step.step_id[:8]} failed but continuing: {e}")
                return None
            elif on_error == 'stop':
                logger.error(f"Step {step.step_id[:8]} failed and stopping: {e}")
                raise
            elif on_error == 'ask_user':
                user_input = input(f"Step {step.step_id[:8]} failed: {e}\nEnter value or 'skip': ")
                if user_input.lower() == 'skip':
                    step.mark_skipped("User skipped")
                    return None
                step.mark_completed(user_input)
                return user_input
            elif on_error == 'retry':
                if step.should_retry():
                    step.retry_count += 1
                    time.sleep(1)
                    return self._execute_step(step, context)
                else:
                    logger.error(f"Step {step.step_id[:8]} failed and retries exhausted: {e}")
                    raise
            elif on_error == 'skip':
                step.mark_skipped(f"Skipped due to error: {e}")
                return None

        return None

    def _execute_action(self, action_config: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """
        Execute an action.

        Args:
            action_config: Action configuration dict, expected to contain
                'action_type' (goal/tool/script/prompt_user) plus whatever
                that action type needs.
            context: Execution context

        Returns:
            Action output
        """
        action_type = ActionType(action_config.get('action_type', 'goal'))

        if action_type == ActionType.GOAL:
            goal_id = action_config.get('goal', '')
            # Placeholder - would connect to Agent Runtime
            return f"Goal {goal_id} executed"

        elif action_type == ActionType.TOOL:
            tool_name = action_config.get('tool', '')
            tool_params = action_config.get('parameters', {})
            # Placeholder - would connect to Tool Execution Engine
            return f"Tool {tool_name} executed with params {tool_params}"

        elif action_type == ActionType.SCRIPT:
            script = action_config.get('script', '')
            # Placeholder - would execute script
            return "Script executed"

        elif action_type == ActionType.PROMPT_USER:
            prompt_text = action_config.get('prompt', 'Enter value:')
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
            'status': self.status.value,
            'step_count': len(self.steps),
            'steps': [step.export_to_dict() for step in self.steps.values()]
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"WorkflowGraph(id={self.workflow_id[:8]}, steps={len(self.steps)}, active={self.active})"