"""
Workflow Builder

Interface for building workflows visually or through natural language.
Provides methods for constructing workflows, defining triggers, setting up variables, and adding steps.
"""


import json
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
import uuid

from .models import (
    WorkflowTriggerType,
    WorkflowPriority,
    StepType,
    ActionType,
    ConditionType,
    LoopType,
    ErrorHandling,
    DecisionOutcome,
    WorkflowStatus
)
from .workflow import Workflow
from .workflow_step import WorkflowStep


class WorkflowBuilder:
    """
    Builder for creating workflows.
    Provides a fluent interface for constructing workflows with triggers, steps, conditions, and loops.
    """

    def __init__(self):
        """Initialize a new workflow builder."""
        self._workflow: Optional[Workflow] = None
        self._steps: List[WorkflowStep] = []
        self._triggers: List[Dict[str, Any]] = []

    def create_workflow(
        self,
        name: str,
        description: str = "",
        priority: WorkflowPriority = WorkflowPriority.NORMAL,
        workflow_type: str = "custom"
    ) -> 'WorkflowBuilder':
        """
        Create a new workflow.

        Args:
            name: Workflow name
            description: Workflow description
            priority: Workflow priority
            workflow_type: Type of workflow (custom, automation, routine, etc.)

        Returns:
            self for method chaining
        """
        workflow_id = str(uuid.uuid4())
        self._workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            priority=priority,
            workflow_type=workflow_type,
            status=WorkflowStatus.DRAFT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            triggers=[],
            steps=[],
            variables={},
            conditions={},
            loops={},
            error_handling=ErrorHandling.CONTINUE
        )
        return self

    def set_trigger(
        self,
        trigger_type: Union[str, WorkflowTriggerType],
        **trigger_data
    ) -> 'WorkflowBuilder':
        """
        Set a trigger for the workflow.

        Args:
            trigger_type: Type of trigger (manual, scheduled, event, workspace, voice, plugin)
            trigger_data: Additional trigger-specific data

        Returns:
            self for method chaining
        """
        if not self._workflow:
            raise ValueError("Create workflow before setting triggers")

        # Convert string to enum if needed
        if isinstance(trigger_type, str):
            trigger_type = WorkflowTriggerType(trigger_type.lower())

        trigger = {
            "id": str(uuid.uuid4()),
            "type": trigger_type.value,
            "data": trigger_data,
            "active": True
        }

        self._workflow.triggers.append(trigger)
        return self

    def add_step(
        self,
        step_id: str,
        action_type: Union[str, ActionType],
        step_type: Union[str, StepType] = StepType.ACTION,
        **kwargs
    ) -> 'WorkflowBuilder':
        """
        Add a step to the workflow.

        Args:
            step_id: Unique step identifier
            action_type: Type of action to execute
            step_type: Type of step (action, wait, condition, loop, etc.)
            **kwargs: Step-specific parameters

        Returns:
            self for method chaining
        """
        if not self._workflow:
            raise ValueError("Create workflow before adding steps")

        # Convert strings to enums if needed
        if isinstance(action_type, str):
            action_type = ActionType(action_type.lower())
        if isinstance(step_type, str):
            step_type = StepType(step_type.lower())

        step = WorkflowStep(
            id=step_id,
            step_type=step_type.value,
            action_type=action_type.value,
            action_config=kwargs,
            condition_type=ConditionType.ATTRIBUTE_CHECK.value if "condition" in kwargs.get("action_config", {}) else None,
            next_step=kwargs.get("next_step"),
            timeout=kwargs.get("timeout"),
            retries=kwargs.get("retries", 0),
            error_handling=kwargs.get("error_handling", ErrorHandling.CONTINUE).value,
            metadata=kwargs.get("metadata", {})
        )

        self._steps.append(step)
        return self

    def add_wait_step(
        self,
        step_id: str,
        duration: Union[int, timedelta],
        unit: str = "seconds"
    ) -> 'WorkflowBuilder':
        """
        Add a wait/delay step.

        Args:
            step_id: Unique step identifier
            duration: Duration to wait
            unit: Unit of duration (seconds, minutes, hours, days)

        Returns:
            self for method chaining
        """
        if isinstance(duration, timedelta):
            duration = duration.total_seconds()

        return self.add_step(
            step_id=step_id,
            action_type=ActionType.WAIT,
            step_type=StepType.WAIT,
            duration=duration,
            unit=unit
        )

    def add_set_variable_step(
        self,
        step_id: str,
        variable_name: str,
        variable_value: Any,
        set_if_empty: bool = True
    ) -> 'WorkflowBuilder':
        """
        Add a variable assignment step.

        Args:
            step_id: Unique step identifier
            variable_name: Name of variable to set
            variable_value: Value to assign
            set_if_empty: Only set if variable doesn't exist

        Returns:
            self for method chaining
        """
        return self.add_step(
            step_id=step_id,
            action_type=ActionType.SET_VARIABLE,
            step_type=StepType.SET_VARIABLE,
            variable_name=variable_name,
            variable_value=variable_value,
            set_if_empty=set_if_empty
        )

    def add_get_variable_step(
        self,
        step_id: str,
        variable_name: str,
        output_variable: str = "output"
    ) -> 'WorkflowBuilder':
        """
        Add a variable retrieval step.

        Args:
            step_id: Unique step identifier
            variable_name: Name of variable to retrieve
            output_variable: Name of variable to store the result

        Returns:
            self for method chaining
        """
        return self.add_step(
            step_id=step_id,
            action_type=ActionType.GET_VARIABLE,
            step_type=StepType.GET_VARIABLE,
            variable_name=variable_name,
            output_variable=output_variable
        )

    def add_condition_step(
        self,
        step_id: str,
        condition_type: Union[str, ConditionType],
        condition_config: Dict[str, Any]
    ) -> 'WorkflowBuilder':
        """
        Add a conditional step.

        Args:
            step_id: Unique step identifier
            condition_type: Type of condition (attribute_check, value_check, custom)
            condition_config: Condition configuration parameters

        Returns:
            self for method chaining
        """
        if isinstance(condition_type, str):
            condition_type = ConditionType(condition_type.lower())

        return self.add_step(
            step_id=step_id,
            action_type=ActionType.NONE,  # Conditions don't execute actions
            step_type=StepType.CONDITION,
            condition_type=condition_type.value,
            condition_config=condition_config
        )

    def add_loop_step(
        self,
        step_id: str,
        loop_type: Union[str, LoopType],
        loop_config: Dict[str, Any]
    ) -> 'WorkflowBuilder':
        """
        Add a loop step.

        Args:
            step_id: Unique step identifier
            loop_type: Type of loop (for_each, while, for_range)
            loop_config: Loop configuration parameters

        Returns:
            self for method chaining
        """
        if isinstance(loop_type, str):
            loop_type = LoopType(loop_type.lower())

        return self.add_step(
            step_id=step_id,
            action_type=ActionType.NONE,
            step_type=StepType.LOOP,
            loop_type=loop_type.value,
            loop_config=loop_config
        )

    def add_for_each_loop(
        self,
        step_id: str,
        collection: str,
        item_variable: str = "item",
        next_step: str = "next"
    ) -> 'WorkflowBuilder':
        """
        Add a for-each loop.

        Args:
            step_id: Unique step identifier
            collection: Name of variable containing collection
            item_variable: Name of variable for current item
            next_step: Step to execute after loop completes

        Returns:
            self for method chaining
        """
        return self.add_loop_step(
            step_id=step_id,
            loop_type=LoopType.FOR_EACH,
            loop_config={
                "collection": collection,
                "item_variable": item_variable,
                "next_step": next_step
            }
        )

    def add_while_loop(
        self,
        step_id: str,
        condition_variable: str,
        condition_operator: str = "==",
        next_step: str = "next"
    ) -> 'WorkflowBuilder':
        """
        Add a while loop.

        Args:
            step_id: Unique step identifier
            condition_variable: Name of variable containing condition
            condition_operator: Comparison operator (==, !=, >, <, >=, <=)
            next_step: Step to execute after loop completes

        Returns:
            self for method chaining
        """
        return self.add_loop_step(
            step_id=step_id,
            loop_type=LoopType.WHILE,
            loop_config={
                "condition_variable": condition_variable,
                "condition_operator": condition_operator,
                "next_step": next_step
            }
        )

    def add_decision_step(
        self,
        step_id: str,
        condition_type: Union[str, ConditionType],
        condition_config: Dict[str, Any]
    ) -> 'WorkflowBuilder':
        """
        Add a decision step for branching.

        Args:
            step_id: Unique step identifier
            condition_type: Type of decision
            condition_config: Condition configuration

        Returns:
            self for method chaining
        """
        if isinstance(condition_type, str):
            condition_type = ConditionType(condition_type.lower())

        return self.add_step(
            step_id=step_id,
            action_type=ActionType.NONE,
            step_type=StepType.DECISION,
            condition_type=condition_type.value,
            condition_config=condition_config
        )

    def add_prompt_user_step(
        self,
        step_id: str,
        prompt: str,
        output_variable: str = "user_input",
        prompt_type: str = "text"
    ) -> 'WorkflowBuilder':
        """
        Add a user prompt step.

        Args:
            step_id: Unique step identifier
            prompt: Prompt text to display
            output_variable: Variable to store user input
            prompt_type: Type of prompt (text, yes_no, selection)

        Returns:
            self for method chaining
        """
        return self.add_step(
            step_id=step_id,
            action_type=ActionType.PROMPT_USER,
            step_type=StepType.PROMPT_USER,
            prompt=prompt,
            output_variable=output_variable,
            prompt_type=prompt_type
        )

    def add_echo_step(
        self,
        step_id: str,
        message: str,
        log_level: str = "info"
    ) -> 'WorkflowBuilder':
        """
        Add an echo/log step.

        Args:
            step_id: Unique step identifier
            message: Message to log
            log_level: Log level (info, warning, error)

        Returns:
            self for method chaining
        """
        return self.add_step(
            step_id=step_id,
            action_type=ActionType.ECHO,
            step_type=StepType.ECHO,
            message=message,
            log_level=log_level
        )

    def add_merge_step(
        self,
        step_id: str,
        source: str,
        target: str,
        merge_config: Dict[str, Any] = None
    ) -> 'WorkflowBuilder':
        """
        Add a merge step.

        Args:
            step_id: Unique step identifier
            source: Name of source variable
            target: Name of target variable
            merge_config: Merge configuration

        Returns:
            self for method chaining
        """
        return self.add_step(
            step_id=step_id,
            action_type=ActionType.MERGE,
            step_type=StepType.MERGE,
            source=source,
            target=target,
            merge_config=merge_config or {}
        )

    def set_error_handling(
        self,
        error_handling: Union[str, ErrorHandling]
    ) -> 'WorkflowBuilder':
        """
        Set error handling strategy.

        Args:
            error_handling: Error handling strategy (continue, stop, ask_user, retry, skip)

        Returns:
            self for method chaining
        """
        if isinstance(error_handling, str):
            error_handling = ErrorHandling(error_handling.lower())

        if self._workflow:
            self._workflow.error_handling = error_handling.value
        return self

    def set_workflow_type(self, workflow_type: str) -> 'WorkflowBuilder':
        """
        Set the workflow type.

        Args:
            workflow_type: Type of workflow (custom, automation, routine, etc.)

        Returns:
            self for method chaining
        """
        if self._workflow:
            self._workflow.workflow_type = workflow_type
        return self

    def set_workflow_description(self, description: str) -> 'WorkflowBuilder':
        """
        Set workflow description.

        Args:
            description: Workflow description

        Returns:
            self for method chaining
        """
        if self._workflow:
            self._workflow.description = description
        return self

    def build(self) -> Workflow:
        """
        Build and return the workflow.

        Returns:
            Workflow object

        Raises:
            ValueError: If workflow hasn't been created
        """
        if not self._workflow:
            raise ValueError("Create workflow before building")

        # Add all steps to workflow
        self._workflow.steps = self._steps

        # Update workflow ID if needed
        if not self._workflow.id:
            self._workflow.id = str(uuid.uuid4())

        return self._workflow

    def build_and_save(self) -> Workflow:
        """
        Build and save the workflow.

        Returns:
            Workflow object

        Raises:
            ValueError: If workflow hasn't been created
        """
        from .workflow_manager import WorkflowManager

        workflow = self.build()
        manager = WorkflowManager()

        # Try to import the workflow
        try:
            manager.import_workflow(workflow.to_dict())
        except Exception as e:
            # If import fails, just return the workflow
            pass

        return workflow

    @staticmethod
    def from_workflow(workflow: Workflow) -> 'WorkflowBuilder':
        """
        Create a builder from an existing workflow.

        Args:
            workflow: Existing workflow

        Returns:
            WorkflowBuilder instance
        """
        builder = WorkflowBuilder()
        builder._workflow = workflow

        # Recreate steps
        for step_dict in workflow.steps:
            builder._steps.append(WorkflowStep(**step_dict))

        return builder


# Convenience functions for quick workflow creation
def create_workflow(
    name: str,
    description: str = "",
    priority: WorkflowPriority = WorkflowPriority.NORMAL,
    **kwargs
) -> WorkflowBuilder:
    """
    Create a new workflow builder.

    Args:
        name: Workflow name
        description: Workflow description
        priority: Workflow priority
        **kwargs: Additional parameters

    Returns:
        WorkflowBuilder instance
    """
    builder = WorkflowBuilder()
    builder.create_workflow(name=name, description=description, priority=priority, **kwargs)
    return builder
