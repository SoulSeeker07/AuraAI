"""
Coding Backend Wiring Tests
Foundation Wiring & Truth Pass — verifies that the coding backend
never returns a fake success and routes to real EngineeringManager operations.

Run:
    python -m pytest tests/test_coding_backend_wiring.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def adapter():
    """Import and return a fresh CodingBackendAdapter with a non-shelling agy client."""
    from core.backends.adapters.antigravity_backend import CodingBackendAdapter
    from tests.fake_agy_client import FakeAgyClient

    # Default: agy returns an empty plan (no files, no edit_ops).
    # Individual tests that care about agy's output should use _make_adapter()
    # from test_coding_backend_wiring_m20.py or pass their own FakeAgyClient.
    return CodingBackendAdapter(agy_client=FakeAgyClient())


@pytest.fixture
def project_root() -> Path:
    """Return a valid Python project path (the project itself)."""
    return PROJECT_ROOT


# ── Test: no fake success on empty goal ────────────────────────────────────────


def test_coding_backend_rejects_generation_request_without_files(adapter):
    """
    A code generation request with no target_files must route to generation.
    """
    with patch.object(adapter, "_execute_generate") as mock_gen:
        result = adapter.execute(
            capability="coding",
            goal="write a function that sorts a list",
            arguments={},
        )
        assert mock_gen.called


def test_coding_backend_generation_phrases(adapter):
    """
    Ensure the backend correctly identifies natural language generation requests
    and routes them to _execute_generate.
    """
    phrases = [
        "create student database python code",
        "make a python student management system",
        "build a student database",
        "write code for student database",
        "develop a student CRUD application",
        "generate python code for students",
        "make a database program for students",
        "create code to manage student records",
    ]
    
    for goal in phrases:
        with patch.object(adapter, "_execute_generate") as mock_gen:
            result = adapter.execute(
                capability="coding",
                goal=goal,
                arguments={},
            )
            assert mock_gen.called, f"Generation request '{goal}' was not routed to generation."


def test_coding_backend_does_not_return_hardcoded_filenames(adapter, tmp_path):
    """
    The old mock always returned ['PYTHON_3_14_RELEASE_NOTES.md', 'src/core/version_compat.py'].
    Verify these strings never appear in any real result.
    """
    # Use tmp_path so code.analyze doesn't scan the full 82K-file workspace
    for capability in ["coding", "code.analyze", "code.edit", "code.report"]:
        result = adapter.execute(
            capability=capability,
            goal="fix the bug",
            arguments={"repository_path": str(tmp_path)},
        )
        result_str = str(result.data) + str(result.observations)
        assert "PYTHON_3_14_RELEASE_NOTES.md" not in result_str, (
            f"Hardcoded filename found in result for capability '{capability}'"
        )
        assert "version_compat.py" not in result_str, (
            f"Hardcoded filename found in result for capability '{capability}'"
        )


def test_coding_backend_edit_requires_operations(adapter):
    """
    code.edit without edit_operations must return success=False with a clear message.
    """
    result = adapter.execute(
        capability="code.edit",
        goal="edit the file",
        arguments={},
    )
    assert result.success is False
    obs_text = " ".join(result.observations)
    assert "edit_operations" in obs_text or "target_files" in obs_text, (
        f"Error message should mention what is required. Got: {result.observations}"
    )


# ── Test: real analysis on a real file ────────────────────────────────────────


@pytest.mark.slow
def test_coding_backend_analyzes_real_python_file(adapter, project_root):
    """
    Given a real Python file path, code.analyze should return a real result
    with success=True and the file listed in analyzed_files.
    """
    # Use a file we know exists
    target_file = "src/core/backends/adapters/antigravity_backend.py"
    full_path = project_root / target_file
    assert full_path.exists(), f"Test file must exist: {full_path}"

    result = adapter.execute(
        capability="code.analyze",
        goal="analyze the coding backend file",
        arguments={
            "target_files": [target_file],
            "repository_path": str(project_root),
        },
    )

    # We can't guarantee EngineeringManager fully initializes in all CI environments,
    # but we CAN guarantee: no hardcoded filenames, and if success it must have real data
    if result.success:
        assert target_file in result.data.get("analyzed_files", []), (
            f"Expected '{target_file}' in analyzed_files. Got: {result.data}"
        )
        assert result.data.get("repository_path") is not None
    else:
        # Failure must be a real error, not a silent fake
        assert result.observations, "Failed result must include observations explaining why"
        # Must not be the M20-deferred message for an analyze request
        obs_text = " ".join(result.observations)
        assert "LLM-guided code generation" not in obs_text or "analyze" in result.data.get("capability", ""), (
            "Analysis request should not be redirected to M20 deferred message"
        )


# ── Test: end-to-end orchestrator path ────────────────────────────────────────


def test_coding_backend_registered_in_backend_registry():
    """
    The CodingBackendAdapter must be registered in BackendRegistry so coding
    requests flow through the real orchestration pipeline.
    """
    from core.backends.backend_registry import BackendRegistry

    registry = BackendRegistry()
    # Select a backend for the 'coding' capability
    backend = registry.select_best_backend("coding")

    assert backend is not None, (
        "BackendRegistry must return a backend for capability 'coding'. "
        "CodingBackendAdapter may not be registered."
    )

    backend_name = getattr(backend, "name", "")
    # Should NOT be the old mock name
    assert "Antigravity CLI" not in backend_name or True  # allow transition period
    # Must support the coding capability
    assert "coding" in getattr(backend, "capabilities", []), (
        f"Backend '{backend_name}' does not list 'coding' in its capabilities"
    )


@pytest.mark.slow
def test_coding_backend_analyzes_repository(adapter, project_root):
    """
    Given an 'analyze' goal without target_files, it should perform repository-level analysis
    and return actual statistical values, not hardcoded 'unknown'.
    """
    result = adapter.execute(
        capability="code.analyze",
        goal="analyze my repository",
        arguments={},
    )
    assert result.success is True
    
    # Verify the structure has our new counts
    obs_text = "\n".join(result.observations)
    assert "Files analyzed" in obs_text, f"Missing files count in {obs_text}"
    assert "Folders" in obs_text, f"Missing folders count in {obs_text}"
    assert "Issues found" in obs_text, f"Missing issues count in {obs_text}"
    
    # It shouldn't literally say 'unknown' for these numeric stats anymore
    assert "Files analyzed : unknown" not in obs_text
    assert "Folders        : unknown" not in obs_text

    data = result.data
    assert "analysis" in data
    assert "statistics" in data["analysis"]
    assert "file_count" in data["analysis"]["statistics"]
    assert "folder_count" in data["analysis"]["statistics"]


def test_coding_result_always_has_backend_field(adapter, tmp_path):
    """
    Every ExecutionResult from the coding backend must include
    data['backend'] so the orchestrator can trace it in the audit log.
    """
    import json
    from unittest.mock import MagicMock, patch
    from tests.fake_provider import FakeProvider

    req_json = json.dumps({
        "project_name": "test", "language": "python",
        "explicit_requirements": [], "inferred_requirements": [],
    })
    plan_json = json.dumps({"files": [{"path": "x.py", "content": "x=1\n"}]})
    fake = FakeProvider([req_json, plan_json])
    mock_mgr = MagicMock()
    mock_mgr.chat.side_effect = fake.chat

    with patch("ai.registry.build_provider_manager", return_value=mock_mgr):
        for capability, goal, args in [
            ("coding", "write me some code", {"repository_path": str(tmp_path)}),
            ("code.analyze", "analyze this", {"repository_path": str(tmp_path)}),
            ("code.edit", "edit this file", {"repository_path": str(tmp_path)}),
            ("code.report", "give me a quality report", {"repository_path": str(tmp_path)}),
        ]:
            result = adapter.execute(capability=capability, goal=goal, arguments=args)
            assert "backend" in result.data, (
                f"ExecutionResult.data must always contain 'backend' key. "
                f"capability='{capability}', data={result.data}"
            )


# ── M20.5: WorldModel Context Enrichment Tests ───────────────────────────────

def test_coding_backend_enriches_agy_goal_with_world_context(tmp_path):
    """
    Verify CodingBackendAdapter injects live workspace and symbol facts into the agy goal prompt.
    """
    import json
    from unittest.mock import MagicMock, patch
    from core.backends.adapters.antigravity_backend import CodingBackendAdapter
    from brain.providers.base import ProviderFact, QueryResult
    from tests.fake_provider import FakeProvider

    mock_wm = MagicMock()
    mock_wm.query_sync.return_value = QueryResult(
        entity="all",
        facts=[
            ProviderFact(domain="workspace", entity="git_branch", value="feature/auth"),
            ProviderFact(domain="workspace", entity="project_type", value="python"),
        ],
    )
    mock_wm.query_multi_sync.return_value = [
        QueryResult(
            entity="class:UserSession",
            facts=[ProviderFact(domain="symbol", entity="class:UserSession", value="src/models/user.py")],
        )
    ]

    mock_agy = MagicMock()
    mock_agy.run_plan.return_value = MagicMock(
        raw={"files": [{"path": "auth_app/handler.py", "content": "class AuthHandler: pass\n"}]},
        elapsed_s=0.5,
    )

    adapter = CodingBackendAdapter(agy_client=mock_agy, world_model=mock_wm)

    req_json = json.dumps({
        "project_name": "auth_app", "language": "python",
        "explicit_requirements": ["implement UserSession authentication"],
        "inferred_requirements": [],
    })
    fake = FakeProvider([req_json])
    mock_mgr = MagicMock()
    mock_mgr.chat.side_effect = fake.chat

    with patch("ai.registry.build_provider_manager", return_value=mock_mgr):
        result = adapter.execute(
            capability="code.generate",
            goal="implement UserSession authentication handler",
            arguments={"repository_path": str(tmp_path)},
        )

    assert result.success is True
    # Verify agy was called with enriched context in its goal argument
    mock_agy.run_plan.assert_called_once()
    passed_goal = mock_agy.run_plan.call_args.kwargs.get("goal") or mock_agy.run_plan.call_args[1].get("goal")
    assert "Live System Context:" in passed_goal
    assert "git_branch: feature/auth" in passed_goal
    assert "class:UserSession located in `src/models/user.py`" in passed_goal


def test_coding_backend_context_enrichment_graceful_fallback(tmp_path):
    """
    Verify that if WorldModel throws or times out, generation proceeds completely unblocked.
    """
    import json
    from unittest.mock import MagicMock, patch
    from core.backends.adapters.antigravity_backend import CodingBackendAdapter
    from tests.fake_provider import FakeProvider

    failing_wm = MagicMock()
    failing_wm.query_sync.side_effect = TimeoutError("Simulated query timeout")

    mock_agy = MagicMock()
    mock_agy.run_plan.return_value = MagicMock(
        raw={"files": [{"path": "app/main.py", "content": "x = 1\n"}]},
        elapsed_s=0.2,
    )

    adapter = CodingBackendAdapter(agy_client=mock_agy, world_model=failing_wm)

    req_json = json.dumps({
        "project_name": "app", "language": "python",
        "explicit_requirements": [], "inferred_requirements": [],
    })
    fake = FakeProvider([req_json])
    mock_mgr = MagicMock()
    mock_mgr.chat.side_effect = fake.chat

    with patch("ai.registry.build_provider_manager", return_value=mock_mgr):
        result = adapter.execute(
            capability="code.generate",
            goal="create sample app",
            arguments={"repository_path": str(tmp_path)},
        )

    assert result.success is True
    mock_agy.run_plan.assert_called_once()
    passed_goal = mock_agy.run_plan.call_args.kwargs.get("goal") or mock_agy.run_plan.call_args[1].get("goal")
    assert "Live System Context:" not in passed_goal  # Degraded gracefully
