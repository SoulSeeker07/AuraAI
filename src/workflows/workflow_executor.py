"""
Workflow Executor

Executes workflows using Agent Runtime.
Handles step-by-step execution with error handling and recovery.
"""


import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import threading

from .workflow_graph import WorkflowGraph
from .workflow_step import WorkflowStep
from .models import StepType, WorkflowStatus


logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """
    Executes workflows step-by-step.
    """

    def __init__(
        self,
        on_step_start: Optional[Callable[[str, str], None]] = None,
        on_step_complete: Optional[Callable[[str, str, bool, Any], None]] = None,
        on_step_fail: Optional[Callable[[str, str, str], None]] = None,
        on_workflow_start: Optional[Callable[[str], None]] = None,
        on_workflow_complete: Optional[Callable[[str, bool], None]] = None,
        on_workflow_fail: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize workflow executor.

        Args:
            on_step_start: Callback when step starts
            on_step_complete: Callback when step completes
            on_step_fail: Callback when step fails
            on_workflow_start: Callback when workflow starts
            on_workflow_complete: Callback when workflow completes
            on_workflow_fail: Callback when workflow fails
        """
        self.on_step_start = on_step_start
        self.on_step_complete = on_step_complete
        self.on_step_fail = on_step_fail
        self.on_workflow_start = on_workflow_start
        self.on_workflow_complete = on_workflow_complete
        self.on_workflow_fail = on_workflow_fail

        # Running workflows
        self.running_workflows: Dict[str, Dict[str, Any]] = {}

        # Execution thread
        self.execution_thread: Optional[threading.Thread] = None

        logger.info("Workflow Executor initialized")

    def execute_workflow(
        self,
        graph: WorkflowGraph,
        wait_for_completion: bool = True
    ) -> bool:
        """
        Execute a workflow.

        NOTE: this now requires an already-built WorkflowGraph. The
        previous version only took a workflow_id and never actually
        attached a graph to the running-workflow context, so every
        execution failed immediately with "No workflow graph". Callers
        must build/load a WorkflowGraph (with its steps already added)
        before calling this.

        Args:
            graph: The WorkflowGraph to execute (graph.workflow_id is used
                as the tracking key)
            wait_for_completion: Whether to block until the workflow finishes

        Returns:
            Success (workflow started)
        """
        workflow_id = graph.workflow_id
        logger.info(f"Starting workflow {workflow_id[:8]}")

        # Initialize execution context
        self.running_workflows[workflow_id] = {
            'graph': graph,
            'context': {},
            'started_at': datetime.now(),
            'completed_at': None,
            'error': None,
            'finished': False
        }

        # Start workflow execution
        self.execution_thread = threading.Thread(
            target=self._execution_loop,
            args=(workflow_id,),
            daemon=True
        )
        self.execution_thread.start()

        if wait_for_completion:
            return self.wait_for_completion(workflow_id)

        return True

    def pause_workflow(self, workflow_id: str) -> bool:
        """
        Pause a running workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.running_workflows:
            return False

        context = self.running_workflows[workflow_id]
        if context.get('graph'):
            context['graph'].active = False

        logger.info(f"Paused workflow {workflow_id[:8]}")
        return True

    def resume_workflow(self, workflow_id: str) -> bool:
        """
        Resume a paused workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.running_workflows:
            return False

        context = self.running_workflows[workflow_id]
        if context.get('graph'):
            context['graph'].active = True

        logger.info(f"Resumed workflow {workflow_id[:8]}")
        return True

    def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a running workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.running_workflows:
            return False

        context = self.running_workflows[workflow_id]
        if context.get('graph'):
            context['graph'].active = False

        context['error'] = "Workflow cancelled by user"
        context['finished'] = True

        logger.info(f"Cancelled workflow {workflow_id[:8]}")
        return True

    def wait_for_completion(self, workflow_id: str) -> bool:
        """
        Wait for workflow to complete.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.running_workflows:
            return False

        if self.execution_thread and self.execution_thread.is_alive():
            self.execution_thread.join(timeout=None)

        # running_workflows entry is deleted in _execution_loop's finally
        # block once finished, so if it's gone, treat that as completed.
        return True

    def _execution_loop(self, workflow_id: str):
        """
        Main execution loop for workflow.

        Args:
            workflow_id: Workflow ID
        """
        context = self.running_workflows[workflow_id]
        graph = context.get('graph')

        if not graph:
            logger.error(f"Workflow {workflow_id[:8]} has no graph")
            context['error'] = "No workflow graph"
            context['finished'] = True
            return

        try:
            graph.mark_started()
            if self.on_workflow_start:
                self.on_workflow_start(workflow_id)

            logger.info(f"Execution loop started for workflow {workflow_id[:8]}")

            self._execute_workflow_steps(workflow_id, graph, context['context'])

            graph.mark_completed(success=True)
            context['completed_at'] = datetime.now()
            context['finished'] = True

            if self.on_workflow_complete:
                self.on_workflow_complete(workflow_id, True)

            logger.info(f"Workflow {workflow_id[:8]} completed successfully")

        except Exception as e:
            graph.mark_failed(str(e))
            context['completed_at'] = datetime.now()
            context['error'] = str(e)
            context['finished'] = True

            if self.on_workflow_fail:
                self.on_workflow_fail(workflow_id, str(e))

            logger.error(f"Workflow {workflow_id[:8]} failed: {e}", exc_info=True)

        finally:
            if workflow_id in self.running_workflows:
                del self.running_workflows[workflow_id]

    def _execute_workflow_steps(self, workflow_id: str, graph: WorkflowGraph, context: Dict[str, Any]):
        """
        Execute all workflow steps.

        Args:
            workflow_id: Workflow ID
            graph: Workflow graph
            context: Execution context
        """
        parallel_groups = graph.get_parallel_groups()

        logger.info(f"Workflow {workflow_id[:8]} has {len(parallel_groups)} parallel groups")

        for group in parallel_groups:
            for step_id in group:
                if not graph.active:
                    logger.info(f"Workflow {workflow_id[:8]} was paused/cancelled")
                    return

                self._execute_single_step(workflow_id, graph, step_id, context)

            self._wait_for_group_completion(graph, group)

    def _execute_single_step(self, workflow_id: str, graph: WorkflowGraph, step_id: str, context: Dict[str, Any]):
        """
        Execute a single workflow step.

        Args:
            workflow_id: Workflow ID
            graph: Workflow graph
            step_id: Step ID
            context: Execution context
        """
        step = graph.get_step(step_id)
        if not step:
            logger.error(f"Step {step_id[:8]} not found in workflow {workflow_id[:8]}")
            return

        if step.status.value in ['completed', 'skipped']:
            logger.debug(f"Skipping already completed step {step_id[:8]}")
            return

        for dep_id in step.dependencies:
            dep_step = graph.get_step(dep_id)
            if not dep_step or dep_step.status.value not in ['completed', 'skipped']:
                logger.debug(f"Step {step_id[:8]} waiting for dependency {dep_id[:8]}")
                return

        self._execute_step(workflow_id, graph, step, context)

    def _execute_step(self, workflow_id: str, graph: WorkflowGraph, step: WorkflowStep, context: Dict[str, Any]):
        """
        Execute a workflow step.

        Args:
            workflow_id: Workflow ID
            graph: Workflow graph
            step: Step to execute
            context: Execution context
        """
        graph.mark_step_started(step.step_id)
        if self.on_step_start:
            self.on_step_start(workflow_id, step.step_id)

        logger.info(f"Executing step {step.step_id[:8]} in workflow {workflow_id[:8]}")

        result = None

        try:
            action_config = step.action_config or {}

            if step.step_type == StepType.LOOP:
                loop_config = step.loop or {}
                collection = context.get(loop_config.get('collection', 'items'), loop_config.get('items', []))
                results = graph.apply_loop(step, collection, context)

                context[f"{step.step_id}_results"] = results
                context[f"{step.step_id}_count"] = len(results)
                result = results

            elif step.step_type == StepType.DECISION:
                result = self._execute_decision(workflow_id, graph, step, context)

            elif step.step_type == StepType.PROMPT_USER:
                prompt_text = action_config.get('prompt', 'Enter value: ')
                result = input(prompt_text)
                context[f"{step.step_id}_result"] = result

            else:
                result = graph._execute_step(step, context)
                context[f"{step.step_id}_result"] = result

            graph.mark_step_completed(step.step_id, success=True, output=result)
            if self.on_step_complete:
                self.on_step_complete(workflow_id, step.step_id, True, result)

            logger.debug(f"Step {step.step_id[:8]} completed successfully")

        except Exception as e:
            graph.mark_step_failed(step.step_id, str(e))
            if self.on_step_fail:
                self.on_step_fail(workflow_id, step.step_id, str(e))

            logger.error(f"Step {step.step_id[:8]} failed: {e}", exc_info=True)

            on_error = step.on_error or 'continue'

            if on_error == 'stop':
                logger.error(f"Step {step.step_id[:8]} failed and stopping workflow")
                raise
            elif on_error == 'continue':
                logger.info(f"Step {step.step_id[:8]} failed but continuing")
                return
            elif on_error == 'ask_user':
                choice = input(
                    f"Step {step.step_id[:8]} failed: {e}\nContinue (c), Skip (s), or Stop (x)? "
                ).lower()

                if choice == 's':
                    graph.mark_step_skipped(step.step_id, f"User skipped due to: {e}")
                elif choice == 'x':
                    raise
                else:
                    # 'c' or anything else: treat as continue
                    return
            elif on_error == 'skip':
                graph.mark_step_skipped(step.step_id, f"Skipped due to: {e}")
            elif on_error == 'retry':
                if step.should_retry():
                    step.retry_count += 1
                    self._execute_step(workflow_id, graph, step, context)
                else:
                    logger.error(f"Step {step.step_id[:8]} failed after exhausting retries: {e}")
                    raise

    def _execute_decision(self, workflow_id: str, graph: WorkflowGraph, step: WorkflowStep, context: Dict[str, Any]) -> Any:
        """
        Execute a decision step.

        Args:
            workflow_id: Workflow ID
            graph: Workflow graph
            step: Decision step
            context: Execution context

        Returns:
            "Condition checked" marker, matching WorkflowGraph's own
            CONDITION handling, for consistency.
        """
        condition_met = graph.evaluate_condition(step.condition, context)
        decision = step.decision or {}

        branch_ids = decision.get('on_true', []) if condition_met else decision.get('on_false', [])
        for branch_step_id in branch_ids:
            if branch_step_id in graph.steps:
                self._execute_single_step(workflow_id, graph, branch_step_id, context)

        return "Condition checked"

    def _wait_for_group_completion(self, graph: WorkflowGraph, group: List[str]):
        """
        Wait for all steps in a group to complete.

        Args:
            graph: Workflow graph
            group: Step IDs in group
        """
        import time

        while True:
            all_completed = True
            for step_id in group:
                step = graph.get_step(step_id)
                if step and step.status.value not in ['completed', 'skipped', 'failed', 'aborted']:
                    all_completed = False
                    break

            if all_completed:
                break

            time.sleep(0.1)

    def cancel_all(self):
        """Cancel all running workflows."""
        for workflow_id in list(self.running_workflows.keys()):
            self.cancel_workflow(workflow_id)

    def get_running_workflows(self) -> List[str]:
        """
        Get list of running workflow IDs.

        Returns:
            List of workflow IDs
        """
        return list(self.running_workflows.keys())

    def get_workflow_status(self, workflow_id: str) -> Optional[str]:
        """
        Get workflow status.

        Args:
            workflow_id: Workflow ID

        Returns:
            Status string
        """
        if workflow_id not in self.running_workflows:
            return None

        context = self.running_workflows[workflow_id]
        graph = context.get('graph')
        return graph.status.value if graph else None

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Statistics dictionary
        """
        running_ids = list(self.running_workflows.keys())
        return {
            'running_workflow_count': len(running_ids),
            'running_workflows': running_ids
        }