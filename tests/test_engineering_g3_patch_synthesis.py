"""
Gate G3 Automated Verification Suite — Patch Synthesis & Test Immunity Engine
Location: tests/test_engineering_g3_patch_synthesis.py

Verifies:
- G3-1: Synthesizes valid AST code diffs and unified diff text.
- G3-2: Test-File Immunity raises RewardHackingViolation when modifying existing test files.
- G3-3: Test-File Immunity blocks edits to conftest.py, pytest.ini, and pyproject.toml.
- G3-4: ADD_TEST task type permits adding net-new test files.
- G3-5: Syntax validation rejects syntactically malformed candidate patches before disk write.
- G3-6: Path containment blocks directory traversal attacks.
"""

import tempfile
from pathlib import Path
import pytest

from core.orchestration.request_source import RequestSource
from engineering.safety_ceiling import (
    ProtectedCeilingViolation,
    RewardHackingViolation,
)
from engineering.workspace_policy import WorkspaceTraversalError
from engineering.patch_synthesizer import (
    CodePatch,
    PatchSynthesizer,
)


def test_patch_synthesizer_generates_valid_ast_diff():
    """G3-1: Verifies patch synthesizer creates clean unified diffs for valid code."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_file = root / "src" / "math_lib" / "calc.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")

        synthesizer = PatchSynthesizer(repo_root=root)
        new_code = (
            "def divide(a, b):\n"
            "    if b == 0:\n"
            "        raise ValueError('Cannot divide by zero')\n"
            "    return a / b\n"
        )

        patch = synthesizer.synthesize_file_patch(
            target_file="src/math_lib/calc.py",
            new_content=new_code,
            task_type="BUG_FIX",
            source=RequestSource.DAEMON_BACKGROUND,
        )

        assert isinstance(patch, CodePatch)
        assert patch.file_path == "src/math_lib/calc.py"
        assert "Cannot divide by zero" in patch.new_content
        assert "+    if b == 0:" in patch.diff_text
        assert "+        raise ValueError('Cannot divide by zero')" in patch.diff_text

        # Apply patch and verify written content
        written = synthesizer.apply_patch(patch)
        assert written.exists()
        assert "Cannot divide by zero" in written.read_text(encoding="utf-8")


def test_test_file_immunity_raises_reward_hacking_violation():
    """G3-2: Verifies editing existing test files raises RewardHackingViolation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        test_file = root / "tests" / "test_calc.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_divide(): assert True\n", encoding="utf-8")

        synthesizer = PatchSynthesizer(repo_root=root)

        with pytest.raises(RewardHackingViolation) as exc_info:
            synthesizer.synthesize_file_patch(
                target_file="tests/test_calc.py",
                new_content="def test_divide(): assert 1 == 1\n",
                task_type="BUG_FIX",
                source=RequestSource.DAEMON_BACKGROUND,
            )
        assert "Test-File Immunity" in str(exc_info.value)


def test_test_immunity_blocks_conftest_and_pyproject_toml():
    """G3-3: Verifies modifying test configs raises ProtectedCeilingViolation or RewardHackingViolation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        synthesizer = PatchSynthesizer(repo_root=root)

        # conftest.py is protected
        with pytest.raises((ProtectedCeilingViolation, RewardHackingViolation)):
            synthesizer.synthesize_file_patch(
                target_file="conftest.py",
                new_content="import pytest\n",
                task_type="BUG_FIX",
                source=RequestSource.DAEMON_BACKGROUND,
            )

        # pyproject.toml is protected
        with pytest.raises((ProtectedCeilingViolation, RewardHackingViolation)):
            synthesizer.synthesize_file_patch(
                target_file="pyproject.toml",
                new_content="[tool.pytest]\n",
                task_type="BUG_FIX",
                source=RequestSource.DAEMON_BACKGROUND,
            )


def test_add_test_task_permits_net_new_test_file():
    """G3-4: Verifies adding brand new test files under ADD_TEST task type is permitted."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        synthesizer = PatchSynthesizer(repo_root=root)

        patch = synthesizer.synthesize_file_patch(
            target_file="tests/test_new_feature.py",
            new_content="def test_feature():\n    assert True\n",
            task_type="ADD_TEST",
            is_new_file=True,
            source=RequestSource.DAEMON_BACKGROUND,
        )

        assert patch.is_new_file is True
        assert patch.file_path == "tests/test_new_feature.py"


def test_patch_synthesizer_syntax_validation():
    """G3-5: Verifies syntactically invalid Python code is rejected before writing to disk."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_file = root / "src" / "broken.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("def ok(): pass\n", encoding="utf-8")

        synthesizer = PatchSynthesizer(repo_root=root)
        invalid_code = "def broken(:\n    return\n"

        with pytest.raises(SyntaxError) as exc_info:
            synthesizer.synthesize_file_patch(
                target_file="src/broken.py",
                new_content=invalid_code,
                task_type="BUG_FIX",
                source=RequestSource.DAEMON_BACKGROUND,
            )
        assert "syntactically invalid" in str(exc_info.value)


def test_patch_synthesizer_respects_workspace_root():
    """G3-6: Verifies path traversal attacks outside workspace root are rejected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        synthesizer = PatchSynthesizer(repo_root=root)

        with pytest.raises(WorkspaceTraversalError):
            synthesizer.synthesize_file_patch(
                target_file="../escape.py",
                new_content="x = 1\n",
                task_type="BUG_FIX",
                source=RequestSource.DAEMON_BACKGROUND,
            )


def test_apply_patch_reauthorizes_write_blocking_tampered_patch():
    """G3-7: Verifies apply_patch re-checks WorkspacePolicy, blocking modified CodePatch objects."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        synthesizer = PatchSynthesizer(repo_root=root)

        # Manually constructed CodePatch pointing at a protected ceiling file
        tampered_patch = CodePatch(
            file_path="src/core/orchestration/execution_policy.py",
            original_content="",
            new_content="# Injected code\n",
            diff_text="",
        )

        # apply_patch must reject writing to protected path
        with pytest.raises(ProtectedCeilingViolation):
            synthesizer.apply_patch(tampered_patch, source=RequestSource.DAEMON_BACKGROUND)

        # Manually constructed CodePatch attempting path traversal
        traversal_patch = CodePatch(
            file_path="../outside.py",
            original_content="",
            new_content="# Injected code\n",
            diff_text="",
        )
        with pytest.raises(WorkspaceTraversalError):
            synthesizer.apply_patch(traversal_patch, source=RequestSource.DAEMON_BACKGROUND)
