"""
Real End-to-End (E2E) Acceptance Test Suite
============================================
Tests true real-world side effects on physical OS, filesystem, and runtime environment.

Unlike Pipeline Architecture tests (which verify internal routing and execution pipeline flow),
E2E Acceptance tests verify physical reality:
- Files actually created on disk with exact expected contents
- Processes actually launched and terminated in Windows OS
- Actual side-effects on the operating system
"""

import os
import time
import pytest
from pathlib import Path

from core.orchestration import MasterOrchestrator, ExecutionBudget
from core.orchestration.execution_policy import ExecutionPolicy


@pytest.mark.asyncio
async def test_e2e_file_creation_and_content_verification(tmp_path):
    """
    E2E Acceptance Test: File Creation & Content Verification
    Sends a request to create and write a file, then physically asserts
    its presence and content on the filesystem using standard OS I/O calls.
    """
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()

    test_file = tmp_path / "e2e_notes.txt"
    test_content = "Real E2E Acceptance Verification Content"

    goal = f"Create file '{test_file}' and write '{test_content}'"
    budget = ExecutionBudget(max_time_seconds=30.0, local_only=True)

    result = await orchestrator.process_request_async(goal_text=goal, budget=budget)

    # 1. Pipeline execution result assertion
    assert result is not None
    assert result.success is True

    # 2. PHYSICAL OS / FILESYSTEM ACCEPTANCE ASSERTION
    assert os.path.exists(test_file), f"Expected physical file {test_file} to exist on disk"

    with open(test_file, "r", encoding="utf-8") as f:
        written_data = f.read()

    assert test_content in written_data, f"Expected '{test_content}' in file, found: '{written_data}'"


@pytest.mark.asyncio
async def test_e2e_physical_notepad_launch_and_teardown():
    """
    E2E Acceptance Test: Win32 Application Physical Lifecycle
    Triggers 'Open Notepad' through MasterOrchestrator, verifies real HWND creation,
    then triggers 'Close Notepad' and verifies physical process destruction.
    """
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()
    policy = ExecutionPolicy.get_instance()

    # 1. Launch via Orchestrator
    launch_result = await orchestrator.process_request_async("Open Notepad")
    assert launch_result.success is True

    # 2. PHYSICAL OS HWND PROBE (No Mocks) - Poll for window creation
    notepad_hwnds = []
    for _ in range(25):
        notepad_hwnds = policy._get_running_windows("notepad", None)
        if len(notepad_hwnds) >= 1:
            break
        time.sleep(0.2)
    assert len(notepad_hwnds) >= 1, "Expected at least 1 physical Notepad top-level HWND"

    # 3. Teardown via Orchestrator
    close_result = await orchestrator.process_request_async("Close Notepad")
    assert close_result.success is True

    # 4. PHYSICAL OS PROCESS DESTRUCTION PROBE - Poll for window closure
    hwnds_after = []
    for _ in range(25):
        hwnds_after = policy._get_running_windows("notepad", None)
        if len(hwnds_after) == 0:
            break
        time.sleep(0.2)
    assert len(hwnds_after) == 0, f"Expected 0 Notepad HWNDs remaining after close, found {len(hwnds_after)}"


@pytest.mark.asyncio
async def test_e2e_artifact_dag_research_persist_and_open(tmp_path):
    """
    E2E Acceptance Test: Artifact-Driven 4-Stage DAG Orchestration

    Goal: Research Python release, save summary as python_release_summary.txt, open in Notepad.

    4-Stage DAG:
        1. Research → art_research_data
        2. DocumentGenerator → art_markdown_doc
        3. Persist → art_saved_file
        4. Open in Notepad

    Asserts:
    1. 4-stage subtask execution graph constructed.
    2. Physical file exists on disk.
    3. File contains REAL research content, NOT placeholder text.
    4. Content is formatted as markdown with a title header.
    5. Physical Notepad application launched.
    6. Teardown closes Notepad process.
    """
    MasterOrchestrator.reset_instance()
    orchestrator = MasterOrchestrator.get_instance()
    policy = ExecutionPolicy.get_instance()

    target_file = tmp_path / "python_release_summary.txt"

    goal = f"Research the latest Python release, save the summary as '{target_file}' in current workspace, and open that file in Notepad"
    budget = ExecutionBudget(max_time_seconds=30.0, local_only=True)

    result = await orchestrator.process_request_async(goal_text=goal, budget=budget)

    # 1. Verify 4-stage subtask graph metrics
    assert result is not None
    metrics = result.data.get("metrics", {})
    assert metrics.get("subtasks_total", 0) >= 4, (
        f"Expected at least 4 subtasks (Research → DocGen → Persist → Open), "
        f"got {metrics.get('subtasks_total', 0)}"
    )

    # 1.5 Validate the entire artifact chain in the session results
    assert result.artifacts is not None, "Expected artifacts list in result"
    art_research = next((a for a in result.artifacts if a["artifact_id"] == "art_research_data"), None)
    art_markdown = next((a for a in result.artifacts if a["artifact_id"] == "art_markdown_doc"), None)
    art_saved = next((a for a in result.artifacts if a["artifact_id"] == "art_saved_file"), None)

    assert art_research is not None, "art_research_data artifact is missing from result"
    assert art_research["content"].strip() != "", "art_research_data has empty content payload"
    assert "Python" in art_research["content"], "art_research_data content does not contain 'Python'"

    assert art_markdown is not None, "art_markdown_doc artifact is missing from result"
    assert art_markdown["content"].startswith("#"), "art_markdown_doc does not start with '#'"
    assert len(art_markdown["content"]) > 100, "art_markdown_doc content is too short"

    assert art_saved is not None, "art_saved_file artifact is missing from result"
    assert art_saved["location"] == str(target_file), f"art_saved_file location '{art_saved['location']}' does not match target file '{target_file}'"

    # Validate first-class resource fields and VerificationReports
    for art in [art_research, art_markdown, art_saved]:
        assert art.get("session_id") != "", "Expected non-empty session_id on artifact"
        assert art.get("owner") == "aura", "Expected owner to be 'aura'"
        assert art.get("verification_report") is not None, "Expected verification_report to be populated"
        assert art["verification_report"]["success"] is True, "Expected verification success to be True"

    assert art_research["verification_report"]["checks"]["sources_reachable"] is True
    assert art_research["verification_report"]["checks"]["structured_payload"] is True
    assert art_markdown["verification_report"]["checks"]["markdown_generated"] is True
    assert art_saved["verification_report"]["checks"]["document_saved"] is True
    assert art_saved["verification_report"]["checks"]["file_exists"] is True

    # 2. PHYSICAL OS / FILESYSTEM ASSERTIONS
    assert os.path.exists(target_file), f"Expected physical file {target_file} to exist on disk"
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify physical file matches markdown payload exactly
    assert content == art_markdown["content"], "Physical file contents do not match the markdown artifact payload"

    # 3. Content is NOT placeholder — the exact bug we're preventing
    assert "# Artifact Summary" not in content, (
        "File contains placeholder content — research artifact payload "
        "did not propagate through the DAG"
    )
    assert "Generated for:" not in content, (
        "File contains fallback-generated content — the FileManager "
        "silent fallback was triggered instead of real artifact propagation"
    )

    # 4. Content has real substance
    assert len(content) > 50, (
        f"Expected substantial research content, got {len(content)} chars"
    )

    # 5. Content is formatted as markdown (DocumentGenerator stage worked)
    assert content.strip().startswith("#"), (
        "Expected markdown-formatted content with a title header"
    )
    assert "Python 3.14 Release Summary" in content
    assert "Generated:" in content
    assert "https://docs.python.org/3.14/whatsnew/3.14.html" in content
    assert "https://peps.python.org/" in content
    assert "https://www.python.org/downloads/release/python-3140/" in content
    assert "Confidence" in content
    assert "Research Engine" in content
    assert "Coordinator" in content

    # 6. PHYSICAL OS HWND PROBE (Notepad opened with target file) - Poll for window creation
    notepad_hwnds = []
    for _ in range(25):
        notepad_hwnds = policy._get_running_windows("notepad", None)
        if len(notepad_hwnds) >= 1:
            break
        time.sleep(0.2)
    assert len(notepad_hwnds) >= 1, "Expected physical Notepad window running with target artifact"

    # Teardown: Close Notepad
    await orchestrator.process_request_async("Close Notepad")
    
    # Poll for window closure
    hwnds_after = []
    for _ in range(25):
        hwnds_after = policy._get_running_windows("notepad", None)
        if len(hwnds_after) == 0:
            break
        time.sleep(0.2)
    assert len(hwnds_after) == 0


@pytest.mark.asyncio
async def test_e2e_artifact_dag_missing_payload_fails_loudly(tmp_path):
    """
    E2E Acceptance Test: Missing Artifact Payload Validation (Fail-Loud)
    Registers a failing research backend that returns success but empty data.
    Asserts that orchestrator fails loudly at Task 2 (DocGen) without writing a file.
    """
    from core.backends.base_backend import BaseBackendAdapter
    from core.backends.backend_registry import BackendRegistry
    from core.planning.execution_result import ExecutionResult

    class FailingResearchBackend(BaseBackendAdapter):
        @property
        def name(self) -> str:
            return "Gemini Research Engine"

        @property
        def capabilities(self) -> list[str]:
            return ["research", "knowledge.query", "summarize"]

        def describe(self) -> dict:
            return {
                "name": self.name,
                "capabilities": self.capabilities,
                "latency_ms": 150.0,
                "cost": 0.01,
                "is_local": False,
            }

        def health_check(self) -> bool:
            return True

        def execute(self, capability: str, goal: str, arguments: dict = None) -> ExecutionResult:
            return ExecutionResult(
                success=True,
                planner="research",
                goal=goal,
                observations=[],
                data={"backend": self.name, "content": ""},  # EMPTY payload!
            )

    MasterOrchestrator.reset_instance()
    BackendRegistry.reset_instance()
    
    b_reg = BackendRegistry.get_instance()
    # Register the custom failing research backend (overwrites default Gemini research backend)
    b_reg.register(FailingResearchBackend())

    orchestrator = MasterOrchestrator.get_instance()
    target_file = tmp_path / "failed_release_summary.txt"

    goal = f"Research the latest Python release, save the summary as '{target_file}' in current workspace, and open that file in Notepad"
    budget = ExecutionBudget(max_time_seconds=30.0, local_only=True)

    result = await orchestrator.process_request_async(goal_text=goal, budget=budget)

    # 1. Assert orchestration failed
    assert result is not None
    assert result.success is False

    # 2. Assert error message is descriptive and points to Task 2 validation
    assert len(result.observations) >= 1
    expected_err = "Research stage completed without producing a payload. Cannot generate markdown. Execution stopped at Task 2."
    assert any(expected_err in obs for obs in result.observations), (
        f"Expected error message '{expected_err}' in observations: {result.observations}"
    )

    # 3. Assert no file was physically written to disk
    assert not os.path.exists(target_file), "File was written to disk despite empty research payload!"

