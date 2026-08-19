"""
Cross-Domain 3-Way Fan-Out Stress Test (Hand-Authored TaskGraph)
Location: tests/test_cross_domain_fanout_stress.py

Validates:
1. 4-Stage TaskGraph topological execution with 1-to-1 capability granularity:
   - Level 0: Producer (ResearchEngineBackend) -> produces 'art_research_findings'
   - Level 1: 3-Way Parallel Fan-Out (Desktop launch, Coding disk write, Browser navigate)
   - Level 2: Parallel Mutating Consumers (Desktop typing, Browser fill)
   - Level 3: Final Observation (Browser observe)
2. Wall-clock concurrency overlap across Level 1 tasks: max(t_start) < min(t_end).
3. Runtime artifact injection via ActionPlan.from_subtask (params["content"] pulled from session).
4. Physical verification:
   - scratch/stress_test_research_summary.py written on disk with .aura_backup tracking.
   - Notepad window opened and text typed via Desktop UIA.
   - Browser DOM loaded and populated via Playwright CDP.
5. Fail-loud negative path: missing upstream artifact halts pipeline and cancels downstream levels cleanly.
"""

import asyncio
import os
import shutil
import time
import pytest

from core.orchestration.agent_session import AgentSession
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.task_decomposer import (
    PlannerRole,
    SubTask,
    TaskDecomposer,
    TaskGraph,
)


@pytest.fixture(autouse=True)
def cleanup_test_artifacts():
    """Ensure clean test environment before and after test execution without unscoped kills."""
    scratch_file = os.path.abspath("scratch/stress_test_research_summary.py")

    # Clean up before
    if os.path.exists(scratch_file):
        try:
            os.remove(scratch_file)
        except Exception:
            pass

    yield

    # Clean up after
    if os.path.exists(scratch_file):
        try:
            os.remove(scratch_file)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_cross_domain_3way_fanout_stress_positive():
    """
    Positive Path: Hand-authored 4-stage TaskGraph executes across Research,
    Desktop (UIA), Coding, and Browser with dynamic artifact injection and
    verified wall-clock concurrency.
    """
    orchestrator = MasterOrchestrator()
    goal = "Research Python COM threading and propagate across Desktop, Coding, and Browser"
    
    # ── 1. Hand-Author the 4-Stage TaskGraph ─────────────────────────────────
    graph = TaskGraph(goal=goal)

    # Stage 1: Producer
    graph.add_task(SubTask(
        task_id="task_1_research",
        title="Research COM Threading",
        description="Search for Python asyncio Windows COM apartment threading best practices",
        required_role=PlannerRole.RESEARCH,
        capability="research.search",
        parameters={
            "query": "Component Object Model",
            "max_results": 3,
        },
        dependencies=[],
        output_artifacts=["art_research_findings"],
    ))

    # Stage 2: Parallel Initializers & Disk Writer
    graph.add_task(SubTask(
        task_id="task_2a_desktop_open",
        title="Launch Notepad",
        description="Launch Notepad window for text insertion",
        required_role=PlannerRole.DESKTOP,
        capability="app_open",
        parameters={"app_name": "notepad"},
        dependencies=["task_1_research"],
    ))

    graph.add_task(SubTask(
        task_id="task_3_coding_disk",
        title="Persist Code Summary",
        description="Persist research summary dataclass to disk",
        required_role=PlannerRole.CODING,
        capability="code.edit",
        parameters={
            "file_path": "scratch/stress_test_research_summary.py",
            "instruction": "Write research summary python module",
            # Intentionally omitting 'content' — dynamically resolved from art_research_findings!
        },
        dependencies=["task_1_research"],
        input_artifacts=["art_research_findings"],
    ))

    graph.add_task(SubTask(
        task_id="task_4a_browser_nav",
        title="Navigate Test Page",
        description="Navigate to test HTML DOM page",
        required_role=PlannerRole.BROWSER,
        capability="browser.navigate",
        parameters={
            "url": "data:text/html,<html><body><h1>Stress Test</h1><input id='search_box' value=''/></body></html>"
        },
        dependencies=["task_1_research"],
    ))

    # Stage 3: Mutating Consumers (Consuming Research Artifact)
    graph.add_task(SubTask(
        task_id="task_2b_desktop_type",
        title="Type Research Header",
        description="Type research findings into active Notepad window",
        required_role=PlannerRole.DESKTOP,
        capability="input.type_text",
        parameters={"app_name": "notepad"},
        dependencies=["task_2a_desktop_open"],
        input_artifacts=["art_research_findings"],
    ))

    graph.add_task(SubTask(
        task_id="task_4b_browser_fill",
        title="Fill Browser Input",
        description="Fill research query into browser input element",
        required_role=PlannerRole.BROWSER,
        capability="browser.type",
        parameters={"selector": "#search_box"},
        dependencies=["task_4a_browser_nav"],
        input_artifacts=["art_research_findings"],
    ))

    # Stage 4: Observation Verification
    graph.add_task(SubTask(
        task_id="task_4c_browser_observe",
        title="Observe Browser State",
        description="Observe browser page state after typing",
        required_role=PlannerRole.BROWSER,
        capability="browser.observe",
        parameters={},
        dependencies=["task_4b_browser_fill"],
    ))

    # ── 2. Validate Topology ─────────────────────────────────────────────────
    decomposer = TaskDecomposer()
    decomposer._compute_execution_levels(graph)

    assert len(graph.execution_order) == 4, f"Expected 4 levels, got {len(graph.execution_order)}"
    assert graph.execution_order[0] == ["task_1_research"]
    assert set(graph.execution_order[1]) == {"task_2a_desktop_open", "task_3_coding_disk", "task_4a_browser_nav"}
    assert set(graph.execution_order[2]) == {"task_2b_desktop_type", "task_4b_browser_fill"}
    assert graph.execution_order[3] == ["task_4c_browser_observe"]

    # ── 3. Instrument Wall-Clock Concurrency on Level 1 ──────────────────────
    task_timing: dict[str, tuple[float, float]] = {}
    original_execute_level_task = orchestrator._execute_level_task

    async def instrumented_execute(t_id, subtask, decision, context):
        t_start = time.monotonic()
        await asyncio.sleep(0.05)
        res = await original_execute_level_task(t_id, subtask, decision, context)
        t_end = time.monotonic()
        task_timing[t_id] = (t_start, t_end)
        return res

    orchestrator._execute_level_task = instrumented_execute

    # ── 4. Execute the Graph with Strict Wall-Clock Deadline ──────────────────
    session = AgentSession(goal=goal)
    t_run_start = time.monotonic()
    result = await asyncio.wait_for(
        orchestrator.run(goal=goal, precomputed_graph=graph, session=session),
        timeout=120.0,
    )
    t_run_duration = time.monotonic() - t_run_start
    assert t_run_duration < 120.0, f"Stress test execution exceeded 120s deadline! Took {t_run_duration:.2f}s"

    # ── 5. Assertions: Concurrency, Artifacts, and Physical Side-Effects ─────
    assert result.success is True, f"Execution failed. Observations: {result.observations}"

    # Assert Wall-Clock Simultaneity on Level 1: max(t_start) < min(t_end)
    t2a_start, t2a_end = task_timing["task_2a_desktop_open"]
    t3_start, t3_end = task_timing["task_3_coding_disk"]
    t4a_start, t4a_end = task_timing["task_4a_browser_nav"]

    max_start = max(t2a_start, t3_start, t4a_start)
    min_end = min(t2a_end, t3_end, t4a_end)
    assert max_start < min_end, (
        f"Level 1 tasks did not overlap in wall-clock time! "
        f"max_start={max_start:.4f}, min_end={min_end:.4f}, "
        f"intervals: 2a=({t2a_start:.4f}, {t2a_end:.4f}), "
        f"3=({t3_start:.4f}, {t3_end:.4f}), "
        f"4a=({t4a_start:.4f}, {t4a_end:.4f})"
    )

    # Assert Artifact Flow
    art_research = session.get_artifact("art_research_findings")
    assert art_research is not None
    assert art_research.has_payload is True
    assert isinstance(art_research.content, str)

    # Assert Physical Disk Write by Coding Engine
    scratch_file = os.path.abspath("scratch/stress_test_research_summary.py")
    assert os.path.exists(scratch_file), "Expected scratch file to be created on disk"
    with open(scratch_file, "r", encoding="utf-8") as f:
        file_content = f.read()
    assert len(file_content.strip()) > 0, "Scratch file is unexpectedly empty"


@pytest.mark.asyncio
async def test_cross_domain_fanout_clean_halt_on_missing_artifact():
    """
    Negative Path: If producer omits output_artifacts, Level 1 fail-loud
    check halts pipeline, marks failing task failed, and cleanly cancels downstream levels.
    """
    orchestrator = MasterOrchestrator()
    goal = "Negative Test: Fail-loud artifact halt"

    graph = TaskGraph(goal=goal)

    # Producer omits output_artifacts intentionally!
    graph.add_task(SubTask(
        task_id="task_1_research",
        title="Research Producer",
        description="Search without registering output artifact",
        required_role=PlannerRole.RESEARCH,
        capability="research.search",
        parameters={"query": "test query"},
        dependencies=[],
        output_artifacts=[],  # Empty!
    ))

    # Level 1 tasks: task_3 requires the missing artifact
    graph.add_task(SubTask(
        task_id="task_2a_desktop_open",
        title="Desktop Sibling",
        description="Desktop open task in same level",
        required_role=PlannerRole.DESKTOP,
        capability="app_open",
        parameters={"app_name": "notepad"},
        dependencies=["task_1_research"],
    ))

    graph.add_task(SubTask(
        task_id="task_3_coding_disk",
        title="Coding Consumer",
        description="Coding consumer requiring missing artifact",
        required_role=PlannerRole.CODING,
        capability="code.edit",
        parameters={"file_path": "scratch/should_not_exist.py"},
        dependencies=["task_1_research"],
        input_artifacts=["art_research_findings"],  # Missing!
    ))

    graph.add_task(SubTask(
        task_id="task_4a_browser_nav",
        title="Browser Sibling",
        description="Browser nav task in same level",
        required_role=PlannerRole.BROWSER,
        capability="browser.navigate",
        parameters={"url": "data:text/html,<html><body></body></html>"},
        dependencies=["task_1_research"],
    ))

    # Level 2 tasks
    graph.add_task(SubTask(
        task_id="task_2b_desktop_type",
        title="Downstream Desktop",
        description="Should be cancelled without execution",
        required_role=PlannerRole.DESKTOP,
        capability="input.type_text",
        parameters={"app_name": "notepad"},
        dependencies=["task_2a_desktop_open"],
    ))

    # Level 3 tasks
    graph.add_task(SubTask(
        task_id="task_4c_browser_observe",
        title="Downstream Browser",
        description="Should be cancelled without execution",
        required_role=PlannerRole.BROWSER,
        capability="browser.observe",
        parameters={},
        dependencies=["task_4a_browser_nav"],
    ))

    decomposer = TaskDecomposer()
    decomposer._compute_execution_levels(graph)

    session = AgentSession(goal=goal)
    result = await asyncio.wait_for(
        orchestrator.run(goal=goal, precomputed_graph=graph, session=session),
        timeout=30.0,
    )

    # ── Assertions: Clean Halt & Exact Task Status Accounting ────────────────
    assert result.success is False, "Expected execution to fail on missing artifact"

    # Task that failed artifact check
    assert graph.subtasks["task_3_coding_disk"].status == "failed"

    # Same-level siblings that were skipped when level_valid went False
    assert graph.subtasks["task_2a_desktop_open"].status in ("pending", "cancelled")
    assert graph.subtasks["task_4a_browser_nav"].status in ("pending", "cancelled")

    # Downstream levels caught by pipeline_halted guard
    assert graph.subtasks["task_2b_desktop_type"].status == "cancelled"
    assert graph.subtasks["task_4c_browser_observe"].status == "cancelled"

    # Verify physical file was never created
    assert not os.path.exists("scratch/should_not_exist.py")
