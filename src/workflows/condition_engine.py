"""
Condition Engine

Evaluates workflow conditions for decision points and conditional branching.
"""



import logging
from typing import Optional, Dict, Any, Callable, List
import json


logger = logging.getLogger(__name__)


class ConditionEngine:
    """
    Evaluates workflow conditions.
    """

    def __init__(self, variable_manager):
        """
        Initialize condition engine.

        Args:
            variable_manager: VariableManager instance
        """
        self.variable_manager = variable_manager
        self.custom_conditions: Dict[str, Callable] = {}
        logger.info("Condition Engine initialized")

    def evaluate(
        self,
        condition: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Evaluate a condition.

        Args:
            condition: Condition definition with type and parameters
            context: Optional context for evaluation

        Returns:
            True if condition is met, False otherwise
        """
        condition_type = condition.get('type', 'value_check')
        params = condition.get('params', {})

        logger.debug(f"Evaluating condition: {condition_type}")

        if condition_type == 'attribute_check':
            return self._evaluate_attribute_check(params, context or {})
        elif condition_type == 'value_check':
            return self._evaluate_value_check(params, context or {})
        elif condition_type == 'custom':
            return self._evaluate_custom_condition(params.get('condition_id'), context or {})
        else:
            logger.warning(f"Unknown condition type: {condition_type}")
            return False

    def _evaluate_attribute_check(self, params: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate attribute check condition.

        Args:
            params: Condition parameters
            context: Evaluation context

        Returns:
            True if condition is met
        """
        # Check if attribute exists
        attribute = params.get('attribute', '')
        if not attribute:
            return False

        # Get value from context or variables
        value = self.variable_manager.get_variable(attribute)
        if value is None:
            logger.warning(f"Attribute '{attribute}' not found")
            return False

        # Check against expected value
        expected_value = params.get('expected_value')
        if expected_value is not None:
            return value == expected_value

        # Just check if attribute exists
        return True

    def _evaluate_value_check(self, params: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate value check condition.

        Args:
            params: Condition parameters
            context: Evaluation context

        Returns:
            True if condition is met
        """
        variable = params.get('variable', '')
        operator = params.get('operator', '==')
        expected_value = params.get('expected_value')

        if not variable or expected_value is None:
            logger.warning("Value check missing variable or expected_value")
            return False

        # Get value
        actual_value = self.variable_manager.get_variable(variable)

        if actual_value is None:
            logger.warning(f"Variable '{variable}' not found")
            return False

        # Apply operator
        return self._apply_operator(operator, actual_value, expected_value)

    def _apply_operator(self, operator: str, actual_value: Any, expected_value: Any) -> bool:
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
        elif operator == 'in':
            return actual_value in expected_value
        elif operator == 'not in':
            return actual_value not in expected_value
        elif operator == 'contains':
            return expected_value in actual_value
        elif operator == 'not contains':
            return expected_value not in actual_value
        elif operator == 'starts_with':
            return str(actual_value).startswith(expected_value)
        elif operator == 'ends_with':
            return str(actual_value).endswith(expected_value)
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

    def _evaluate_custom_condition(self, condition_id: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate custom condition.

        Args:
            condition_id: Custom condition identifier
            context: Evaluation context

        Returns:
            Result of custom condition
        """
        if condition_id not in self.custom_conditions:
            logger.warning(f"Custom condition '{condition_id}' not found")
            return False

        return self.custom_conditions[condition_id](context)

    def add_custom_condition(
        self,
        condition_id: str,
        condition_func: Callable[[Dict[str, Any]], bool]
    ):
        """
        Add a custom condition function.

        Args:
            condition_id: Condition identifier
            condition_func: Function that evaluates the condition
        """
        self.custom_conditions[condition_id] = condition_func
        logger.info(f"Added custom condition: {condition_id}")

    def evaluate_decision(
        self,
        decision: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> DecisionOutcome:
        """
        Evaluate a decision (branching logic).

        Args:
            decision: Decision definition with conditions and outcomes
            context: Optional context for evaluation

        Returns:
            Decision outcome
        """
        outcomes = decision.get('outcomes', [])
        conditions = decision.get('conditions', [])

        context = context or {}

        # Check each condition in order
        for condition, outcome_key in zip(conditions, outcomes):
            if self.evaluate(condition, context):
                return outcome_key

        # Return default outcome
        default_outcome = decision.get('default_outcome', 'continue')
        return default_outcome

    def get_variable_value(self, variable_name: str, default: Any = None) -> Any:
        """
        Get variable value for condition evaluation.

        Args:
            variable_name: Variable name
            default: Default value if not found

        Returns:
            Variable value
        """
        return self.variable_manager.get_variable(variable_name, default=default)

    def set_variable_value(self, variable_name: str, value: Any):
        """
        Set variable value for condition evaluation.

        Args:
            variable_name: Variable name
            value: Value to set
        """
        self.variable_manager.set_variable(variable_name, value, scope='step')

    def evaluate_batch(self, conditions: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> List[bool]:
        """
        Evaluate multiple conditions.

        Args:
            conditions: List of condition definitions
            context: Optional context for evaluation

        Returns:
            List of boolean results
        """
        results = []
        context = context or {}

        for condition in conditions:
            result = self.evaluate(condition, context)
            results.append(result)

        return results
