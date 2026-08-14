"""
M20 Coding Intelligence regression tests.

All tests inject a FakeAgyClient so no subprocess is spawned.
Groq calls (requirement extraction + repair) are mocked via FakeProvider.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tests.fake_agy_client import FakeAgyClient
from tests.fake_provider import FakeProvider


# ── Helpers ───────────────────────────────────────────────────────────────────

def _req_resp(name="test_proj", lang="python"):
    return json.dumps({
        "project_name": name,
        "language": lang,
        "explicit_requirements": ["test"],
        "inferred_requirements": [],
    })


def _plan_resp(files: list[dict]):
    return json.dumps({"files": files})


def _make_adapter(agy_client=None):
    """Return a fresh CodingBackendAdapter with the given agy_client injected."""
    from core.backends.adapters.antigravity_backend import CodingBackendAdapter
    return CodingBackendAdapter(
        agy_client=agy_client or FakeAgyClient()
    )


def _groq_mock(responses: list[str]):
    """Return a mock ProviderManager whose .chat() cycles through responses."""
    fake = FakeProvider(responses)
    mock_mgr = MagicMock()
    mock_mgr.chat.side_effect = fake.chat
    return mock_mgr


# ── code.generate — agy path ──────────────────────────────────────────────────

class TestGenerateAgy:
    def test_success_uses_agy_plan(self, tmp_path):
        """agy returns a valid CodeGenerationPlan — no Groq call for the plan step."""
        agy = FakeAgyClient(responses=[
            {"files": [{"path": "hello.py", "content": "print('hello world')\n"}]}
        ])
        adapter = _make_adapter(agy)

        # Only Groq call is requirement extraction
        with patch("ai.registry.build_provider_manager") as mock_build:
            mock_build.return_value = _groq_mock([_req_resp()])
            result = adapter.execute(
                capability="code.generate",
                goal="say hello",
                arguments={"repository_path": tmp_path},
            )

        assert result.success is True
        assert agy.call_count == 1
        assert (tmp_path / "hello.py").exists()
        obs = "\n".join(result.observations)
        assert "Plan source     : agy" in obs
        assert "Syntax          : PASS" in obs

    def test_agy_timeout_falls_back_to_groq(self, tmp_path):
        """agy times out → Groq fallback produces the plan."""
        from core.backends.adapters.agy_subprocess_client import AgyTimeoutError
        agy = FakeAgyClient(error=AgyTimeoutError(45.0))
        adapter = _make_adapter(agy)

        groq_plan = _plan_resp([{"path": "fallback.py", "content": "x = 1\n"}])
        with patch("ai.registry.build_provider_manager") as mock_build:
            mock_build.return_value = _groq_mock([_req_resp(), groq_plan])
            result = adapter.execute(
                capability="code.generate",
                goal="do something",
                arguments={"repository_path": tmp_path},
            )

        assert result.success is True
        obs = "\n".join(result.observations)
        assert "Plan source     : groq" in obs

    def test_both_agy_and_groq_fail_returns_error(self, tmp_path):
        """If both agy and Groq fallback fail, result is honest failure."""
        from core.backends.adapters.agy_subprocess_client import AgyTimeoutError
        agy = FakeAgyClient(error=AgyTimeoutError(45.0))
        adapter = _make_adapter(agy)

        with patch("ai.registry.build_provider_manager") as mock_build:
            # Groq returns garbage for plan step
            mock_build.return_value = _groq_mock([_req_resp(), "not json at all"])
            result = adapter.execute(
                capability="code.generate",
                goal="do something",
                arguments={"repository_path": tmp_path},
            )

        assert result.success is False

    def test_workspace_policy_blocks_traversal(self, tmp_path):
        """WorkspacePolicy must still block path traversal even from agy plans."""
        agy = FakeAgyClient(responses=[
            {"files": [{"path": "../../../evil.py", "content": "import os"}]}
        ])
        adapter = _make_adapter(agy)

        with patch("ai.registry.build_provider_manager") as mock_build:
            mock_build.return_value = _groq_mock([_req_resp()])
            result = adapter.execute(
                capability="code.generate",
                goal="be evil",
                arguments={"repository_path": tmp_path},
            )

        assert result.success is False
        obs = "\n".join(result.observations)
        assert "Policy violation" in obs
        assert "Path traversal is not allowed" in obs

    def test_workspace_policy_blocks_existing_file_overwrite(self, tmp_path):
        """WorkspacePolicy must block silent overwrite of an existing file."""
        existing = tmp_path / "existing.py"
        existing.write_text("# original\n", encoding="utf-8")

        agy = FakeAgyClient(responses=[
            {"files": [{"path": "existing.py", "content": "# overwrite"}]}
        ])
        adapter = _make_adapter(agy)

        with patch("ai.registry.build_provider_manager") as mock_build:
            mock_build.return_value = _groq_mock([_req_resp()])
            result = adapter.execute(
                capability="code.generate",
                goal="overwrite file",
                arguments={"repository_path": tmp_path},
            )

        assert result.success is False
        # Original file must be untouched
        assert existing.read_text(encoding="utf-8") == "# original\n"

    def test_syntax_repair_loop(self, tmp_path):
        """Syntax failure triggers Groq repair; repaired content is written."""
        bad_py = "print('hello'   # syntax error"
        good_py = "print('hello')\n"
        agy = FakeAgyClient(responses=[
            {"files": [{"path": "bad.py", "content": bad_py}]}
        ])
        adapter = _make_adapter(agy)

        repair_resp = _plan_resp([{"path": "bad.py", "content": good_py}])
        with patch("ai.registry.build_provider_manager") as mock_build:
            mock_build.return_value = _groq_mock([_req_resp(), repair_resp])
            result = adapter.execute(
                capability="code.generate",
                goal="print hello",
                arguments={"repository_path": tmp_path},
            )

        assert result.success is True
        assert (tmp_path / "bad.py").read_text(encoding="utf-8") == good_py
        obs = "\n".join(result.observations)
        assert "Repairs         : 1" in obs

    def test_max_repair_retries_exhausted(self, tmp_path):
        """After 3 attempts the file is marked FAIL without infinite loop."""
        bad_py = "class 123:\n  pass"
        agy = FakeAgyClient(responses=[
            {"files": [{"path": "broken.py", "content": bad_py}]}
        ])
        adapter = _make_adapter(agy)

        with patch("ai.registry.build_provider_manager") as mock_build:
            # Groq keeps returning the same broken code on every repair
            mock_build.return_value = _groq_mock(
                [_req_resp()] + [_plan_resp([{"path": "broken.py", "content": bad_py}])] * 5
            )
            result = adapter.execute(
                capability="code.generate",
                goal="create broken class",
                arguments={"repository_path": tmp_path},
            )

        assert result.success is False
        obs = "\n".join(result.observations)
        assert "Syntax          : FAIL" in obs
        assert "Validation failed after 3 attempts" in obs


# ── code.edit — agy inference path ───────────────────────────────────────────

class TestEditAgy:
    def test_agy_infers_edit_from_goal(self, tmp_path):
        """No explicit edit_operations given — agy infers them from the goal."""
        src = tmp_path / "calc.py"
        src.write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")

        edit_ops = [{"file_path": "calc.py", "new_content": "def divide(a, b):\n    if b == 0:\n        raise ValueError('divide by zero')\n    return a / b\n"}]
        agy = FakeAgyClient(responses=[{"edit_operations": edit_ops}])
        adapter = _make_adapter(agy)

        result = adapter.execute(
            capability="code.edit",
            goal="add division by zero handling",
            arguments={"repository_path": tmp_path},
        )

        assert result.success is True
        assert agy.call_count == 1

    def test_explicit_edit_ops_bypass_agy(self, tmp_path):
        """When edit_operations are provided explicitly agy must NOT be called."""
        src = tmp_path / "f.py"
        src.write_text("x = 1\n", encoding="utf-8")

        agy = FakeAgyClient()  # call_count should stay 0
        adapter = _make_adapter(agy)

        result = adapter.execute(
            capability="code.edit",
            goal="update f.py",
            arguments={
                "repository_path": tmp_path,
                "edit_operations": [{"file_path": "f.py", "new_content": "x = 2\n"}],
            },
        )

        assert agy.call_count == 0

    def test_agy_unavailable_edit_returns_honest_failure(self, tmp_path):
        """agy unavailable and no explicit ops → honest failure, no silent guess."""
        from core.backends.adapters.agy_subprocess_client import AgyNotFoundError
        agy = FakeAgyClient(error=AgyNotFoundError())
        adapter = _make_adapter(agy)

        result = adapter.execute(
            capability="code.edit",
            goal="do something",
            arguments={"repository_path": tmp_path},
        )

        assert result.success is False
        obs = "\n".join(result.observations)
        assert "agy was asked to infer the edit" in obs

    def test_edit_workspace_policy_gate(self, tmp_path):
        """agy-returned edit_operations still go through WorkspacePolicy."""
        agy = FakeAgyClient(responses=[
            {"edit_operations": [{"file_path": "../../escape.py", "new_content": "x=1"}]}
        ])
        adapter = _make_adapter(agy)

        result = adapter.execute(
            capability="code.edit",
            goal="escape",
            arguments={"repository_path": tmp_path},
        )

        assert result.success is False
        obs = "\n".join(result.observations)
        assert "Policy violation" in obs


# ── code.debug — agy-only path ────────────────────────────────────────────────

class TestDebugAgy:
    def test_debug_applies_agy_fix(self, tmp_path):
        """agy returns edit_operations for a bug fix — they are applied."""
        buggy = tmp_path / "auth.py"
        buggy.write_text("def check(pw):\n    if pw = 'secret':  # syntax bug\n        return True\n", encoding="utf-8")

        fix_ops = [{"file_path": "auth.py", "new_content": "def check(pw):\n    if pw == 'secret':\n        return True\n"}]
        agy = FakeAgyClient(responses=[{"edit_operations": fix_ops}])
        adapter = _make_adapter(agy)

        result = adapter.execute(
            capability="code.debug",
            goal="fix the authentication bug",
            arguments={
                "repository_path": tmp_path,
                "error_trace": "SyntaxError: invalid syntax",
                "target_files": ["auth.py"],
            },
        )

        assert result.success is True
        assert "auth.py" in "\n".join(result.observations)
        # Confirm error_trace and target_files ended up in the agy prompt
        assert "SyntaxError" in agy.last_goal
        assert "auth.py" in agy.last_goal

    def test_debug_no_groq_fallback(self, tmp_path):
        """code.debug has no Groq fallback — unavailable agy → honest failure."""
        from core.backends.adapters.agy_subprocess_client import AgyNotFoundError
        agy = FakeAgyClient(error=AgyNotFoundError())
        adapter = _make_adapter(agy)

        result = adapter.execute(
            capability="code.debug",
            goal="fix bug",
            arguments={"repository_path": tmp_path},
        )

        assert result.success is False
        obs = "\n".join(result.observations)
        assert "agy is unavailable" in obs
        assert "no Groq fallback" in obs

    def test_debug_routed_from_goal_text(self, tmp_path):
        """'debug why X crashes' in goal text alone routes to _execute_debug."""
        fix_ops = [{"file_path": "app.py", "new_content": "# fixed\n"}]
        agy = FakeAgyClient(responses=[{"edit_operations": fix_ops}])
        adapter = _make_adapter(agy)

        (tmp_path / "app.py").write_text("# original\n", encoding="utf-8")

        result = adapter.execute(
            capability="coding",
            goal="debug why the parser crashes on empty input",
            arguments={"repository_path": tmp_path},
        )

        # Should route to _execute_debug via operation="debug"
        assert result.success is True
        assert agy.call_count == 1
