"""
Workflow Orchestrator

Handles multi-capability requests by orchestrating multiple steps.

Example:
    "Find all Python files, summarize them, and create a README"

    Execution Plan:
        1. Filesystem (find Python files)
        2. Knowledge (summarize them)
        3. Provider (generate README)
        4. Export (save the README)

This is the key feature that transforms Aura into a true agent.
"""

import logging
from typing import List, Dict, Any, Optional
from .capability_types import CapabilityType
from .routing_result import RoutingResult

logger = logging.getLogger(__name__)


class WorkflowStep:
    """A single step in a workflow execution."""

    def __init__(self, capability: CapabilityType, step_type: str, data: dict = None):
        """
        Initialize a workflow step.

        Args:
            capability: Capability type for this step
            step_type: Type of step (execute, filter, transform, etc.)
            data: Step-specific data
        """
        self.capability = capability
        self.step_type = step_type
        self.data = data or {}
        self.input_data = None
        self.output_data = None
        self.status = "pending"
        self.error = None

    def __repr__(self) -> str:
        """String representation."""
        return f"WorkflowStep({self.step_type.value}, {self.capability.value}, status={self.status})"


class WorkflowOrchestrator:
    """
    Orchestrates multi-capability workflows.

    This class breaks down complex requests into sequential steps,
    each handled by a different capability.
    """

    def __init__(self):
        """Initialize workflow orchestrator."""
        self.steps: List[WorkflowStep] = []

    def _extract_operations(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract individual operations from a multi-step request.

        This method identifies the main operations in a request and maps them
        to appropriate capabilities and step types.

        Args:
            text: User request text

        Returns:
            List of operations as dictionaries
        """
        text_lower = text.lower()
        operations = []

        # Filesystem operations
        filesystem_ops = [
            {"keywords": ["find", "search", "list", "all"], "capability": CapabilityType.FILESYSTEM,
             "step_type": "execute", "description": "Find files"},
            {"keywords": ["create", "new", "make", "write"], "capability": CapabilityType.FILESYSTEM,
             "step_type": "execute", "description": "Create file"},
            {"keywords": ["delete", "remove", "trash", "recycle", "destroy", "erase"],
             "capability": CapabilityType.FILESYSTEM, "step_type": "execute", "description": "Delete file"},
            {"keywords": ["move", "rename", "change name"], "capability": CapabilityType.FILESYSTEM,
             "step_type": "execute", "description": "Move/Rename file"},
            {"keywords": ["copy", "duplicate", "clone"], "capability": CapabilityType.FILESYSTEM,
             "step_type": "execute", "description": "Copy file"},
            {"keywords": ["compress", "archive", "zip", "unzip"], "capability": CapabilityType.FILESYSTEM,
             "step_type": "execute", "description": "Compress file"},
            {"keywords": ["save", "export", "write to"], "capability": CapabilityType.FILESYSTEM,
             "step_type": "execute", "description": "Save file"},
            {"keywords": ["read", "view", "show", "display"], "capability": CapabilityType.FILESYSTEM,
             "step_type": "execute", "description": "Read file"},
        ]

        # Knowledge/Processing operations
        knowledge_ops = [
            {"keywords": ["summarize", "analyze", "review", "explain", "interpret"],
             "capability": CapabilityType.KNOWLEDGE, "step_type": "execute", "description": "Analyze content"},
            {"keywords": ["search", "lookup", "research"], "capability": CapabilityType.KNOWLEDGE,
             "step_type": "execute", "description": "Search knowledge base"},
            {"keywords": ["compare", "contrast", "difference"], "capability": CapabilityType.KNOWLEDGE,
             "step_type": "execute", "description": "Compare items"},
        ]

        # Provider operations
        provider_ops = [
            {"keywords": ["create", "generate", "write", "make"], "capability": CapabilityType.PROVIDER,
             "step_type": "execute", "description": "Generate content"},
            {"keywords": ["explain", "describe", "clarify"], "capability": CapabilityType.PROVIDER,
             "step_type": "execute", "description": "Explain content"},
            {"keywords": ["transform", "convert", "translate"], "capability": CapabilityType.PROVIDER,
             "step_type": "execute", "description": "Transform content"},
        ]

        # Desktop operations
        desktop_ops = [
            {"keywords": ["open", "launch", "start", "run"], "capability": CapabilityType.DESKTOP,
             "step_type": "execute", "description": "Open application"},
            {"keywords": ["close", "quit", "exit", "force quit"], "capability": CapabilityType.DESKTOP,
             "step_type": "execute", "description": "Close application"},
            {"keywords": ["minimize", "maximize", "restore"], "capability": CapabilityType.DESKTOP,
             "step_type": "execute", "description": "Window management"},
        ]

        # Vision operations
        vision_ops = [
            {"keywords": ["analyze image", "read image", "extract text"], "capability": CapabilityType.VISION,
             "step_type": "execute", "description": "Analyze image"},
            {"keywords": ["describe", "explain"], "capability": CapabilityType.VISION,
             "step_type": "execute", "description": "Describe image"},
        ]

        # Memory operations
        memory_ops = [
            {"keywords": ["remember", "save", "store"], "capability": CapabilityType.MEMORY,
             "step_type": "execute", "description": "Store information"},
            {"keywords": ["recall", "retrieve", "remember"], "capability": CapabilityType.MEMORY,
             "step_type": "execute", "description": "Retrieve information"},
        ]

        # Check all operation types
        all_ops = filesystem_ops + knowledge_ops + provider_ops + desktop_ops + vision_ops + memory_ops

        # Match operations in order of appearance
        for op in all_ops:
            for keyword in op["keywords"]:
                if keyword in text_lower:
                    # Check if we already added this operation (avoid duplicates)
                    if not any(
                        op["capability"] == existing["capability"] and
                        op["step_type"] == existing["step_type"]
                        for existing in operations
                    ):
                        operations.append({
                            "capability": op["capability"],
                            "step_type": op["step_type"],
                            "description": op["description"]
                        })
                        break

        return operations

    def _order_operations(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Order operations based on dependencies.

        Some operations depend on others:
        - Reading files → Analyzing content
        - Finding files → Analyzing them
        - Generating content → Saving it

        Args:
            operations: List of operations

        Returns:
            Ordered list of operations
        """
        if len(operations) <= 1:
            return operations

        # Dependency order: filesystem → knowledge/provider → filesystem (for save)
        # And save operations typically go last

        save_ops = []
        other_ops = []

        for op in operations:
            if op["capability"] == CapabilityType.FILESYSTEM and op["step_type"] == "execute":
                # Check if it's a save/export operation
                if "save" in op["description"].lower() or "export" in op["description"].lower():
                    save_ops.append(op)
                else:
                    other_ops.append(op)
            else:
                other_ops.append(op)

        # Insert save operations at the end
        ordered_ops = other_ops + save_ops

        return ordered_ops

    def plan_workflow(self, text: str) -> List[Dict[str, Any]]:
        """
        Plan a workflow from a multi-step request.

        This method extracts individual operations, orders them, and creates
        a structured workflow plan.

        Args:
            text: User request with multiple steps

        Returns:
            List of workflow steps as dictionaries
        """
        logger.debug(f"Planning workflow from: {text[:100]}...")

        # Extract operations
        operations = self._extract_operations(text)

        if not operations:
            logger.debug("No specific operations detected in request")
            return []

        # Order operations based on dependencies
        operations = self._order_operations(operations)

        # Create WorkflowStep objects
        self.steps = []
        for i, op in enumerate(operations):
            step = WorkflowStep(
                capability=op["capability"],
                step_type=op["step_type"],
                data={
                    "description": op["description"],
                    "operation_index": i
                }
            )
            self.steps.append(step)

        # Add metadata about the workflow
        self.metadata = {
            "total_steps": len(self.steps),
            "source_text": text[:200],
        }

        logger.info(f"Planned {len(self.steps)} workflow steps: {[s.capability.value for s in self.steps]}")
        return [step.as_dict() for step in self.steps]

        # If no specific steps detected, create a simple workflow
        if not steps:
            logger.debug("No specific workflow steps detected")
            return []

        # Create WorkflowStep objects
        self.steps = []
        for step_dict in steps:
            step = WorkflowStep(
                capability=step_dict["capability"],
                step_type=step_dict["step_type"],
                data={"description": step_dict["description"]}
            )
            self.steps.append(step)

        logger.info(f"Planned {len(self.steps)} workflow steps")
        return [step.as_dict() for step in self.steps]

    async def execute_workflow(self) -> Dict[str, Any]:
        """
        Execute the planned workflow.

        This method iterates through the planned steps, executing each one
        in sequence. Steps can call appropriate capability handlers.

        Returns:
            Dictionary with workflow results
        """
        if not self.steps:
            return {
                "success": False,
                "error": "No workflow steps to execute"
            }

        logger.info(f"Starting workflow execution with {len(self.steps)} steps")
        results = []
        final_output = {}

        # Step 1: Validate workflow before execution
        if not self.validate_workflow([step.as_dict() for step in self.steps]):
            return {
                "success": False,
                "error": "Workflow validation failed"
            }

        # Step 2: Execute each step sequentially
        for i, step in enumerate(self.steps):
            logger.info(f"Executing workflow step {i+1}/{len(self.steps)}: {step.step_type.value}")

            try:
                step.status = "running"

                # Execute step based on capability and step type
                step_output = await self._execute_single_step(step, i)

                if step_output is None:
                    raise Exception(f"Failed to execute step {i+1}: No output returned")

                # Store output
                step.output_data = step_output
                step.status = "completed"

                results.append({
                    "step": i + 1,
                    "capability": step.capability.value,
                    "step_type": step.step_type.value,
                    "status": "completed",
                    "output": step_output,
                    "description": step.data.get("description", "")
                })

                logger.debug(f"Step {i+1} completed successfully")

            except Exception as e:
                step.status = "failed"
                step.error = str(e)

                results.append({
                    "step": i + 1,
                    "capability": step.capability.value,
                    "step_type": step.step_type.value,
                    "status": "failed",
                    "error": str(e),
                    "description": step.data.get("description", "")
                })

                logger.error(f"Workflow step {i+1} failed: {e}")
                break  # Stop on failure to prevent cascading errors

        # Step 3: Combine outputs from all successful steps
        for step_result in results:
            if step_result["status"] == "completed":
                output = step_result.get("output", {})
                if isinstance(output, dict):
                    final_output.update(output)

        # Step 4: Compile final result
        workflow_success = all(
            step.status == "completed" for step in self.steps
        )

        return {
            "success": workflow_success,
            "total_steps": len(self.steps),
            "completed_steps": sum(1 for step in self.steps if step.status == "completed"),
            "failed_steps": sum(1 for step in self.steps if step.status == "failed"),
            "steps": results,
            "output": final_output,
            "metadata": self.metadata
        }

    async def _execute_single_step(self, step: WorkflowStep, step_index: int) -> Dict[str, Any]:
        """
        Execute a single workflow step.

        This is a placeholder implementation. In production, this would:
        1. Map the step to an actual capability handler
        2. Call the appropriate handler with step-specific data
        3. Return the output

        Args:
            step: The workflow step to execute
            step_index: Index of the step (for logging)

        Returns:
            Output from the step

        Raises:
            Exception if execution fails
        """
        logger.debug(f"Executing step {step_index+1}: {step.capability.value}")

        # Placeholder execution logic
        # In production, this would:
        # 1. Check the plugin registry for a handler for this capability
        # 2. Call the appropriate capability handler
        # 3. Return the output

        # For now, return a mock output based on step type
        mock_outputs = {
            "execute": {
                "success": True,
                "message": f"Step {step.capability.value} executed successfully",
                "step_data": step.data
            }
        }

        output_type = step.step_type.lower()
        return mock_outputs.get(output_type, {
            "success": True,
            "message": f"Step {step.capability.value} executed"
        })

    def can_orchestrate(self, text: str) -> bool:
        """
        Check if the request can be orchestrated into a workflow.

        This method detects if a request involves multiple steps or operations.

        Args:
            text: User request text

        Returns:
            True if workflow is possible
        """
        text_lower = text.lower()

        # Check for explicit multi-step connectors
        multi_step_connectors = ["and", "then", "after that", "then", "also", "while", "also", "additionally"]
        if any(connector in text_lower for connector in multi_step_connectors):
            return True

        # Check for comma-separated operations
        if "," in text_lower:
            # Count operations by common action verbs
            action_verbs = [
                "find", "search", "list", "create", "write", "generate",
                "delete", "move", "copy", "summarize", "analyze", "explain",
                "open", "close", "save", "export", "compare"
            ]
            operation_count = sum(1 for verb in action_verbs if verb in text_lower)
            if operation_count >= 2:
                return True

        # Check for semicolon-separated operations
        if ";" in text_lower:
            return True

        # Check for "and" between operations (with some context)
        # Look for "verb" + "and" + "verb" pattern
        for i, word in enumerate(text_lower.split()):
            if word == "and" and i > 0:
                # Check if the previous and next words are action verbs
                words_before = text_lower.split()[:i]
                words_after = text_lower.split()[i+1:]

                if words_before and words_after:
                    prev_word = words_before[-1].rstrip(",")
                    next_word = words_after[0].rstrip(",")

                    if prev_word in ["find", "search", "create", "write", "generate",
                                    "delete", "move", "copy", "summarize", "analyze",
                                    "explain", "open", "close", "save", "export"]:
                        return True

        # Check for quotes indicating multiple items
        if ('"' in text_lower or "'" in text_lower) and "," in text_lower:
            return True

        return False

    def validate_workflow(self, steps: List[Dict[str, Any]]) -> bool:
        """
        Validate that a workflow is feasible.

        Args:
            steps: List of workflow steps

        Returns:
            True if workflow is valid
        """
        # Check for circular dependencies
        if len(steps) < 2:
            return False

        # Check for consecutive filesystem operations (could cause issues)
        for i in range(len(steps) - 1):
            if steps[i]["capability"] == "filesystem" and steps[i + 1]["capability"] == "filesystem":
                # This might be okay, but log a warning
                logger.warning(f"Consecutive filesystem operations at step {i+1} and {i+2}")

        return True
