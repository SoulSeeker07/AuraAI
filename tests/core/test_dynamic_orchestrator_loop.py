"""
Tests for Phase 2: Dynamic Perceive-Reason-Act-Observe Agentic Loop in MasterOrchestrator.

Validates:
1. Multi-step dependent TaskGraph execution in dynamic order.
2. Dynamic task injection via task_plan_update mid-execution.
3. Event emission sequencing (ExecutionStarted, GraphInitialized, NodeStateChanged, ExecutionFinished).
4. Honest tri-state verified flags (None, True, False).
5. Deadlock / unsatisfied dependency handling.
6. Clean suspension on ASK_USER confirmation.
"""

import pytest
from unittest.mock import MagicMock

from core.orchestration import MasterOrchestrator
from core.orchestration.agent_session import AgentSession
from core.orchestration.execution_events import (
    ConfirmationRequiredEvent,
    ExecutionFinishedEvent,
    ExecutionStartedEvent,
    GraphInitializedEvent,
    NodeState,
    NodeStateChangedEvent,
    ReplanTriggeredEvent,
)
from core.orchestration.task_decomposer import PlannerRole, SubTask, TaskGraph
from core.planning.execution_result import ExecutionResult
from core.tools.unified_tool_dispatcher import UnifiedToolDispatcher


from core.backends.backend_registry import BackendRegistry


@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Ensure clean orchestrator singleton before and after each test."""
    MasterOrchestrator.reset_instance()
    BackendRegistry.reset_instance()
    yield
    MasterOrchestrator.reset_instance()
    BackendRegistry.reset_instance()


def make_mock_backend(name="mock_backend", success=True, observations=None, verification_passed=None, policy_action=None):
    backend = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "execute_plan_async", "describe", "health_check"])
    backend.name = name
    backend.capabilities = ["mock.action", "mock.step1", "mock.step2", "mock.dynamic"]
    data = {"backend": name, "action_target": "notepad", "capability": "app_open", "plan_id": "plan_test123"}
    if policy_action:
        data["policy_action"] = policy_action
    if verification_passed is not None:
        data["verification_passed"] = verification_passed

    obs = observations if observations is not None else ([f"Executed successfully"] if success else ["Execution failed"])
    res = ExecutionResult(
        success=success,
        planner="mock_planner",
        goal="mock",
        confidence=1.0 if success else 0.0,
        observations=obs,
        data=data,
    )

    async def execute_plan_async(plan):
        return res

    backend.execute_plan_async = execute_plan_async
    backend.execute_plan.return_value = res
    backend.execute.return_value = res
    return backend


@pytest.mark.asyncio
async def test_dynamic_loop_sequential_dependencies_with_hud_events():
    """Verify that multi-step dependent tasks execute in topological order and emit HUD events."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)
    mock_b = make_mock_backend(success=True, verification_passed=True)
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_b)

    # Build custom 3-step dependent TaskGraph
    graph = TaskGraph(goal="Deploy service")
    t1 = SubTask(
        task_id="t1_build",
        title="Build container",
        required_role=PlannerRole.CODING,
        capability="mock.step1",
        description="Build service",
        dependencies=[],
    )
    t2 = SubTask(
        task_id="t2_test",
        title="Run tests",
        required_role=PlannerRole.CODING,
        capability="mock.step2",
        description="Run test suite",
        dependencies=["t1_build"],
    )
    t3 = SubTask(
        task_id="t3_deploy",
        title="Deploy to prod",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Deploy container",
        dependencies=["t2_test"],
    )
    graph.add_task(t1)
    graph.add_task(t2)
    graph.add_task(t3)
    graph.execution_order = [["t1_build"], ["t2_test"], ["t3_deploy"]]

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    session = AgentSession(goal="Deploy service")
    result = await orchestrator.process_request_async(
        goal_text="Deploy service",
        task_graph=graph,
        session=session,
    )

    assert result.success is True
    assert graph.subtasks["t1_build"].status == "completed"
    assert graph.subtasks["t2_test"].status == "completed"
    assert graph.subtasks["t3_deploy"].status == "completed"

    # Verify event stream
    event_types = [type(e) for e in emitted_events]
    assert event_types[0] == ExecutionStartedEvent
    assert event_types[1] == GraphInitializedEvent
    assert event_types[-1] == ExecutionFinishedEvent

    # Verify state transitions for all 3 tasks: PENDING -> RUNNING -> COMPLETED
    node_events = [e for e in emitted_events if isinstance(e, NodeStateChangedEvent)]
    assert len(node_events) == 6  # 2 events per task (RUNNING, COMPLETED)

    assert node_events[0].task_id == "t1_build"
    assert node_events[0].new_state == NodeState.RUNNING
    assert node_events[1].task_id == "t1_build"
    assert node_events[1].new_state == NodeState.COMPLETED
    assert node_events[1].verified is True

    assert node_events[2].task_id == "t2_test"
    assert node_events[2].new_state == NodeState.RUNNING
    assert node_events[3].task_id == "t2_test"
    assert node_events[3].new_state == NodeState.COMPLETED

    assert node_events[4].task_id == "t3_deploy"
    assert node_events[4].new_state == NodeState.RUNNING
    assert node_events[5].task_id == "t3_deploy"
    assert node_events[5].new_state == NodeState.COMPLETED


@pytest.mark.asyncio
async def test_dynamic_loop_dynamic_task_plan_injection():
    """Verify that calling task_plan_update dynamically adds a subtask that the loop executes."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)
    mock_b = make_mock_backend(success=True, verification_passed=True)
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_b)

    # Initial graph with 1 subtask
    graph = TaskGraph(goal="Initial goal")
    t1 = SubTask(
        task_id="t1_setup",
        title="Initial Setup",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Do initial setup",
        dependencies=[],
    )
    graph.add_task(t1)
    graph.execution_order = [["t1_setup"]]

    emitted_events = []
    session = AgentSession(goal="Initial goal")
    session.task_graph = graph
    session.event_sink = emitted_events.append
    orchestrator.set_execution_sink(emitted_events.append)

    # Inject dynamic task via UnifiedToolDispatcher
    update_res = await UnifiedToolDispatcher.dispatch(
        "task_plan_update",
        {
            "tasks": [
                {"task_id": "t1_setup", "title": "Initial Setup", "status": "pending"},
                {
                    "task_id": "t2_dynamic_verify",
                    "title": "Dynamic Verification Step",
                    "status": "pending",
                    "dependencies": ["t1_setup"],
                    "capability": "mock.action",
                },
            ]
        },
        session=session,
    )
    assert update_res["status"] == "success"
    assert "t2_dynamic_verify" in graph.subtasks

    # Verify that NodeStateChangedEvent(PENDING) was emitted synchronously at injection time
    pending_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent)
        and e.task_id == "t2_dynamic_verify"
        and e.new_state == NodeState.PENDING
    ]
    assert len(pending_events) >= 1, "Expected synchronous NodeStateChangedEvent(PENDING) upon dynamic task injection"

    result = await orchestrator.process_request_async(
        goal_text="Initial goal",
        task_graph=graph,
        session=session,
    )

    assert result.success is True
    assert graph.subtasks["t1_setup"].status == "completed"
    assert graph.subtasks["t2_dynamic_verify"].status == "completed"

    # Both tasks must have completed in event log
    completed_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent) and e.new_state == NodeState.COMPLETED
    ]
    completed_task_ids = [e.task_id for e in completed_events]
    assert "t1_setup" in completed_task_ids
    assert "t2_dynamic_verify" in completed_task_ids


@pytest.mark.asyncio
async def test_dynamic_loop_deadlock_halts_cleanly():
    """Verify that unsatisfied cyclic dependencies halt cleanly with CANCELLED state."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    graph = TaskGraph(goal="Deadlocked goal")
    t1 = SubTask(
        task_id="t1",
        title="Task 1",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Task 1",
        dependencies=["t2"],
    )
    t2 = SubTask(
        task_id="t2",
        title="Task 2",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Task 2",
        dependencies=["t1"],
    )
    graph.add_task(t1)
    graph.add_task(t2)

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    session = AgentSession(goal="Deadlocked goal")
    result = await orchestrator.process_request_async(
        goal_text="Deadlocked goal",
        task_graph=graph,
        session=session,
    )

    assert result.success is False
    assert graph.subtasks["t1"].status == "cancelled"
    assert graph.subtasks["t2"].status == "cancelled"

    cancelled_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent) and e.new_state == NodeState.CANCELLED
    ]
    assert len(cancelled_events) == 2


@pytest.mark.asyncio
async def test_dynamic_loop_ask_user_suspends_and_emits_event():
    """Verify that ASK_USER halts the dynamic loop and emits ConfirmationRequiredEvent."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)
    mock_b = make_mock_backend(
        success=False,
        policy_action="ask_user",
        observations=["Delete database? Are you sure?"],
    )
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_b)

    graph = TaskGraph(goal="High-risk action")
    t1 = SubTask(
        task_id="t1_confirm",
        title="Delete database",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Delete DB",
        dependencies=[],
    )
    t2 = SubTask(
        task_id="t2_after",
        title="Post cleanup",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Post cleanup",
        dependencies=["t1_confirm"],
    )
    graph.add_task(t1)
    graph.add_task(t2)
    graph.execution_order = [["t1_confirm"], ["t2_after"]]

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    session = AgentSession(goal="High-risk action")
    result = await orchestrator.process_request_async(
        goal_text="High-risk action",
        task_graph=graph,
        session=session,
    )

    assert result.success is False
    assert session.pending_confirmation is not None

    conf_events = [e for e in emitted_events if isinstance(e, ConfirmationRequiredEvent)]
    assert len(conf_events) == 1
    assert conf_events[0].task_id == "t1_confirm"
    assert "Delete database?" in conf_events[0].prompt


@pytest.mark.asyncio
async def test_dynamic_loop_self_healing_on_failure():
    """Verify that a failing subtask triggers self-healing retry, emits ReplanTriggeredEvent, and succeeds."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ExecutionResult(
                success=False,
                planner="mock_planner",
                goal="mock",
                confidence=0.0,
                observations=["Connection timed out on initial attempt"],
                data={"backend": "mock_backend", "capability": "mock.action"},
            )
        return ExecutionResult(
            success=True,
            planner="mock_planner",
            goal="mock",
            confidence=1.0,
            observations=["Connection established on retry"],
            data={"backend": "mock_backend", "capability": "mock.action", "verification_passed": True},
        )

    mock_b = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "execute_plan_async"])
    mock_b.name = "mock_backend"
    mock_b.capabilities = ["mock.action"]

    async def execute_plan_async(plan):
        return side_effect()

    mock_b.execute_plan_async = execute_plan_async
    mock_b.execute_plan = side_effect
    mock_b.execute = side_effect
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_b)

    graph = TaskGraph(goal="Self-healing test")
    t1 = SubTask(
        task_id="t1_flake",
        title="Flaky network call",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Call external API",
        dependencies=[],
        max_retries=1,
    )
    graph.add_task(t1)
    graph.execution_order = [["t1_flake"]]

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    session = AgentSession(goal="Self-healing test")
    result = await orchestrator.process_request_async(
        goal_text="Self-healing test",
        task_graph=graph,
        session=session,
    )

    assert result.success is True
    assert graph.subtasks["t1_flake"].status == "completed"
    assert call_count == 2
    assert t1.attempt_count == 1

    # Verify that ReplanTriggeredEvent was emitted
    replan_events = [e for e in emitted_events if isinstance(e, ReplanTriggeredEvent)]
    assert len(replan_events) == 1
    assert "t1_flake" in replan_events[0].reason
    assert "self-healing retry" in replan_events[0].reason.lower()

    # Verify node state progression: RUNNING -> PENDING (replan retry) -> RUNNING -> COMPLETED
    node_events = [e for e in emitted_events if isinstance(e, NodeStateChangedEvent) and e.task_id == "t1_flake"]
    assert any(e.new_state == NodeState.PENDING and "Retry 1/1" in (e.error or "") for e in node_events)
    assert node_events[-1].new_state == NodeState.COMPLETED
    assert node_events[-1].verified is True


@pytest.mark.asyncio
async def test_dynamic_loop_budget_guard():
    """Verify that a task that keeps running without completing terminates cleanly at the budget cap."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    iteration_turns = 0

    def never_completing_backend(*args, **kwargs):
        nonlocal iteration_turns
        iteration_turns += 1
        return ExecutionResult(
            success=True,
            planner="mock_planner",
            goal="mock",
            confidence=1.0,
            observations=["Step executed, spawning next step"],
            data={"backend": "mock_backend", "capability": "mock.action"},
        )

    mock_b = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "execute_plan_async"])
    mock_b.name = "mock_backend"
    mock_b.capabilities = ["mock.action"]

    from core.orchestration.agent_session import ExecutionBudget
    budget = ExecutionBudget(max_iterations=5)
    graph = TaskGraph(goal="Infinite loop goal")
    session = AgentSession(goal="Infinite loop goal", budget=budget)
    session.task_graph = graph

    async def execute_plan_async(plan):
        # Dynamically inject another subtask into graph so uncompleted tasks remain
        tid = f"infinite_task_{iteration_turns + 1}"
        session.task_graph.add_task(SubTask(
            task_id=tid,
            title=f"Infinite task {iteration_turns + 1}",
            required_role=PlannerRole.DESKTOP,
            capability="mock.action",
            description="Infinite loop step",
            dependencies=[],
        ))
        return never_completing_backend()

    mock_b.execute_plan_async = execute_plan_async
    mock_b.execute_plan = never_completing_backend
    mock_b.execute = never_completing_backend
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_b)

    t0 = SubTask(
        task_id="infinite_task_0",
        title="Infinite task 0",
        required_role=PlannerRole.DESKTOP,
        capability="mock.action",
        description="Infinite loop initial step",
        dependencies=[],
    )
    graph.add_task(t0)

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    result = await orchestrator.process_request_async(
        goal_text="Infinite loop goal",
        task_graph=graph,
        session=session,
        budget=budget,
    )

    # Must terminate cleanly with overall failure because budget cap was reached
    assert result.success is False
    assert session.metrics.get("iteration_budget_exceeded") is True

    # Any uncompleted tasks must be cancelled
    uncompleted = [st for st in graph.subtasks.values() if st.status != "completed"]
    assert len(uncompleted) > 0
    for st in uncompleted:
        assert st.status == "cancelled"

    cancelled_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent) and e.new_state == NodeState.CANCELLED
    ]
    assert len(cancelled_events) > 0
    assert any("max iterations budget exceeded" in (e.error or "") for e in cancelled_events)


@pytest.mark.asyncio
async def test_dynamic_loop_exhausted_retries_fails_and_cancels_downstream():
    """Verify that when both retries and fallback fail, the task reaches FAILED and cancels downstream tasks."""
    orchestrator = MasterOrchestrator.get_instance(expert_routing_enabled=False)

    call_history = []

    def failing_backend(action_plan=None, **kwargs):
        cap = getattr(action_plan, "capability", "mock.action")
        call_history.append(cap)
        return ExecutionResult(
            success=False,
            planner="mock_planner",
            goal="mock",
            confidence=0.0,
            observations=[f"Permanent failure executing capability '{cap}'"],
            data={"backend": "mock_backend", "capability": cap},
        )

    mock_b = MagicMock(spec=["name", "capabilities", "execute", "execute_plan", "execute_plan_async"])
    mock_b.name = "mock_backend"
    mock_b.capabilities = ["mock.primary", "mock.fallback", "mock.downstream"]

    async def execute_plan_async(plan):
        return failing_backend(plan)

    mock_b.execute_plan_async = execute_plan_async
    mock_b.execute_plan = failing_backend
    mock_b.execute = failing_backend
    orchestrator.backend_registry.select_best_backend = MagicMock(return_value=mock_b)

    # Graph: t1 has max_retries=1 and a fallback_capability; t2 depends on t1
    graph = TaskGraph(goal="Terminal failure test")
    t1 = SubTask(
        task_id="t1_persistent_fail",
        title="Flaky task with fallback",
        required_role=PlannerRole.DESKTOP,
        capability="mock.primary",
        description="Try primary capability",
        dependencies=[],
        parameters={"max_retries": 1, "fallback_capability": "mock.fallback"},
    )
    t2 = SubTask(
        task_id="t2_dependent",
        title="Downstream task",
        required_role=PlannerRole.DESKTOP,
        capability="mock.downstream",
        description="Should never run because t1 fails terminally",
        dependencies=["t1_persistent_fail"],
    )
    graph.add_task(t1)
    graph.add_task(t2)
    graph.execution_order = [["t1_persistent_fail"], ["t2_dependent"]]

    emitted_events = []
    orchestrator.set_execution_sink(emitted_events.append)

    session = AgentSession(goal="Terminal failure test")
    result = await orchestrator.process_request_async(
        goal_text="Terminal failure test",
        task_graph=graph,
        session=session,
    )

    # 1. Overall result must fail
    assert result.success is False

    # 2. Must be an intentional terminal failure, NOT a budget guard trip
    assert session.metrics.get("iteration_budget_exceeded") is not True

    # 3. Call history must show exactly 3 attempts:
    #    Attempt 1: mock.primary -> fails -> triggers retry (attempt_count=1)
    #    Attempt 2: mock.primary (retry) -> fails -> retries exhausted, triggers fallback (mock.fallback)
    #    Attempt 3: mock.fallback -> fails -> both exhausted -> terminal FAILED
    assert call_history == ["mock.primary", "mock.primary", "mock.fallback"]

    # 4. ReplanTriggeredEvent must fire twice (once for retry, once for fallback)
    replan_events = [e for e in emitted_events if isinstance(e, ReplanTriggeredEvent)]
    assert len(replan_events) == 2
    assert "self-healing retry" in replan_events[0].reason.lower()
    assert "mock.fallback" in replan_events[1].reason

    # 5. t1 must end in FAILED state with verified=False
    assert graph.subtasks["t1_persistent_fail"].status == "failed"
    failed_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent)
        and e.task_id == "t1_persistent_fail"
        and e.new_state == NodeState.FAILED
    ]
    assert len(failed_events) == 1
    assert failed_events[0].verified is False

    # 6. Downstream t2 must NEVER run, and must end in CANCELLED state
    assert "mock.downstream" not in call_history
    assert graph.subtasks["t2_dependent"].status == "cancelled"
    cancelled_events = [
        e for e in emitted_events
        if isinstance(e, NodeStateChangedEvent)
        and e.task_id == "t2_dependent"
        and e.new_state == NodeState.CANCELLED
    ]
    assert len(cancelled_events) == 1
    assert "upstream failure" in (cancelled_events[0].error or "")


@pytest.mark.asyncio
async def test_subtask_role_canonicalization_and_fail_closed():
    """Verify that SubTask canonicalizes valid role strings, rejects invalid role strings with ValueError, and rejects invalid types with TypeError."""
    # 1. Valid string forms canonicalize to PlannerRole
    st_browser = SubTask(
        task_id="st_1",
        title="Browser Task",
        required_role="browser",
        capability="browser.open",
    )
    assert st_browser.required_role is PlannerRole.BROWSER

    st_research = SubTask(
        task_id="st_2",
        title="Research Task",
        required_role="RESEARCH",
        capability="research.search",
    )
    assert st_research.required_role is PlannerRole.RESEARCH

    # 2. Existing enum instance is preserved
    st_coding = SubTask(
        task_id="st_3",
        title="Coding Task",
        required_role=PlannerRole.CODING,
        capability="coding.execute",
    )
    assert st_coding.required_role is PlannerRole.CODING

    # 3. Invalid role string MUST fail closed (ValueError), naming valid options
    with pytest.raises(ValueError) as exc_info:
        SubTask(
            task_id="st_invalid",
            title="Invalid Role Task",
            required_role="quantum_computing",
            capability="mock.action",
        )
    assert "Invalid required_role 'quantum_computing'" in str(exc_info.value)
    assert "Expected one of" in str(exc_info.value)

    # 4. Invalid non-string type MUST fail closed (TypeError)
    with pytest.raises(TypeError) as exc_info_type:
        SubTask(
            task_id="st_type_err",
            title="Type Error Task",
            required_role=12345,  # type: ignore
            capability="mock.action",
        )
    assert "required_role must be a PlannerRole or valid role string" in str(exc_info_type.value)

    # 5. task_plan_update tool fails closed when passed an invalid role string
    session = AgentSession(session_id="test_invalid_role_session")
    session.task_graph = TaskGraph(goal="Role test")

    res = await UnifiedToolDispatcher.dispatch(
        "task_plan_update",
        {
            "tasks": [
                {
                    "task_id": "bad_role_task",
                    "title": "Bad Role",
                    "required_role": "malicious_or_typo_domain",
                }
            ]
        },
        session=session,
    )
    assert res.get("status") == "error"
    assert "Invalid required_role 'malicious_or_typo_domain'" in res.get("error", "")

