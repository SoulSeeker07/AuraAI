"""
Workflow Loop Engine

Handles workflow loop iterations (for_each, while, for_range).
"""


import logging
from typing import Any, Dict, Optional, List, Callable
from enum import Enum

from .models import LoopType


logger = logging.getLogger(__name__)


class LoopEngine:
    """
    Handles workflow loop iterations.
    """

    def __init__(self):
        """Initialize loop engine."""
        self.logger = logger

    def execute_loop(
        self,
        loop_type: LoopType,
        loop_config: Dict[str, Any],
        context: Dict[str, Any],
        step_runner: Optional[Callable] = None
    ) -> List[Any]:
        """
        Execute a loop.

        Args:
            loop_type: Type of loop
            loop_config: Loop configuration
            context: Current workflow context
            step_runner: Function to run each iteration's steps

        Returns:
            List of loop iteration results
        """
        if loop_type == LoopType.FOR_EACH:
            return self._execute_for_each(loop_config, context, step_runner)
        elif loop_type == LoopType.WHILE:
            return self._execute_while(loop_config, context, step_runner)
        elif loop_type == LoopType.FOR_RANGE:
            return self._execute_for_range(loop_config, context, step_runner)
        else:
            logger.warning(f"Unknown loop type: {loop_type}")
            return []

    def _execute_for_each(
        self,
        loop_config: Dict[str, Any],
        context: Dict[str, Any],
        step_runner: Optional[Callable] = None
    ) -> List[Any]:
        """
        Execute FOR_EACH loop.

        Args:
            loop_config: Loop configuration
            context: Current workflow context
            step_runner: Function to run each iteration

        Returns:
            List of results from each iteration
        """
        items = loop_config.get('items', [])
        item_variable = loop_config.get('item_variable', 'item')
        loop_index_variable = loop_config.get('loop_index_variable', 'loop_index')

        results = []

        for index, item in enumerate(items):
            # Create iteration context
            iteration_context = context.copy()
            iteration_context[item_variable] = item
            iteration_context[loop_index_variable] = index

            # Run step runner
            if step_runner:
                result = step_runner(iteration_context)
                results.append(result)
            else:
                results.append(item)

        logger.info(f"FOR_EACH loop completed with {len(results)} items")
        return results

    def _execute_while(
        self,
        loop_config: Dict[str, Any],
        context: Dict[str, Any],
        step_runner: Optional[Callable] = None
    ) -> List[Any]:
        """
        Execute WHILE loop.

        Args:
            loop_config: Loop configuration
            context: Current workflow context
            step_runner: Function to run each iteration

        Returns:
            List of results from each iteration
        """
        condition = loop_config.get('condition', {})
        max_iterations = loop_config.get('max_iterations', 100)
        iteration_count = 0

        results = []

        while self._evaluate_condition(condition, context):
            # Check max iterations
            if iteration_count >= max_iterations:
                logger.warning(f"WHILE loop hit max iterations: {max_iterations}")
                break

            # Run step runner
            if step_runner:
                result = step_runner(context)
                results.append(result)
            else:
                results.append(None)

            iteration_count += 1

        logger.info(f"WHILE loop completed after {iteration_count} iterations")
        return results

    def _execute_for_range(
        self,
        loop_config: Dict[str, Any],
        context: Dict[str, Any],
        step_runner: Optional[Callable] = None
    ) -> List[Any]:
        """
        Execute FOR_RANGE loop.

        Args:
            loop_config: Loop configuration
            context: Current workflow context
            step_runner: Function to run each iteration

        Returns:
            List of results from each iteration
        """
        start = loop_config.get('start', 0)
        end = loop_config.get('end', 10)
        step = loop_config.get('step', 1)
        index_variable = loop_config.get('index_variable', 'index')

        results = []

        current = start
        for i in range(start, end, step):
            # Create iteration context
            iteration_context = context.copy()
            iteration_context[index_variable] = current

            # Run step runner
            if step_runner:
                result = step_runner(iteration_context)
                results.append(result)
            else:
                results.append(current)

            current += step

        logger.info(f"FOR_RANGE loop completed with {len(results)} iterations")
        return results

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate loop condition.

        Args:
            condition: Condition configuration
            context: Current context

        Returns:
            True if condition is met
        """
        if not isinstance(condition, dict):
            return False

        variable = condition.get('variable', '')
        operator = condition.get('operator', '==')
        expected_value = condition.get('expected_value')

        if not variable or expected_value is None:
            return False

        actual_value = context.get(variable)

        if actual_value is None:
            return False

        # Apply operator
        return self._apply_operator(operator, actual_value, expected_value)

    def _apply_operator(
        self,
        operator: str,
        actual_value: Any,
        expected_value: Any
    ) -> bool:
        """
        Apply comparison operator.

        Args:
            operator: Operator to apply
            actual_value: Actual value
            expected_value: Expected value

        Returns:
            Result of comparison
        """
        if operator == '==':
            return actual_value == expected_value
        elif operator == '!=':
            return actual_value != expected_value
        elif operator == '>':
            return actual_value > expected_value
        elif operator == '<':
            return actual_value < expected_value
        elif operator == '>=':
            return actual_value >= expected_value
        elif operator == '<=':
            return actual_value <= expected_value
        elif operator == 'is_empty':
            return actual_value is None or actual_value == ''
        elif operator == 'is_not_empty':
            return actual_value is not None and actual_value != ''
        elif operator == 'is_true':
            return bool(actual_value) is True
        elif operator == 'is_false':
            return bool(actual_value) is False
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def get_supported_loops(self) -> List[str]:
        """
        Get list of supported loop types.

        Returns:
            List of loop type names
        """
        return [loop_type.value for loop_type in LoopType]
