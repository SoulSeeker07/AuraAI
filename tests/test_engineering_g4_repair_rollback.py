"""
Gate G4 Automated Verification Suite — Self-Healing Loop & Fail-Closed Rollback Safety
Location: tests/test_engineering_g4_repair_rollback.py

Verifies:
- G4-1: Autonomous engineering loop single-attempt happy path resolution.
- G4-2: Multi-attempt iterative self-healing (attempt 1 fails, attempt 2 succeeds).
- G4-3: Max retries exhausted triggers byte-exact fail-closed rollback (0 residual artifacts).
- G4-4: Reward-hacking test alteration triggers immediate abort & rollback without consuming retries.
- G4-5: Protected-file ceiling violation triggers immediate abort & rollback without consuming retries.
- G4-6: Unhandled runtime exceptions fail closed and restore clean baseline state.
"""

import tempfile
from pathlib import Path
import pytest

from engineering.autonomous_loop import (
    AutonomousEngineeringLoop,
    EngineeringTask,
    LoopExecutionResult,
)
from engineering.fault_localizer import FaultCandidate, FaultLocalizer
from engineering.patch_synthesizer import PatchSynthesizer
from engineering.test_runner import (
    PytestRunnerAdapter,
    StackFrame,
    TestFailureFrame,
    TestRunResult,
    TestRunnerAdapter,
)


class MockTestRunner(TestRunnerAdapter):
    """Controllable test runner for deterministic test simulation."""

    def __init__(self, outcomes: list[bool], failure_file: str = "src/calc.py", failure_line: int = 2):
        self.outcomes = list(outcomes)
        self.failure_file = failure_file
        self.failure_line = failure_line
        self.call_count = 0

    def run_tests(self, test_path: str | Path | None = None, filter_expr: str | None = None, timeout_seconds: int = 120) -> TestRunResult:
        self.call_count += 1
        is_pass = self.outcomes.pop(0) if self.outcomes else True

        if is_pass:
            return TestRunResult(
                success=True,
                total_tests=1,
                passed_tests=1,
                failed_tests=0,
                error_count=0,
                duration_seconds=0.1,
                failure_frames=[],
            )
        else:
            return TestRunResult(
                success=False,
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                error_count=0,
                duration_seconds=0.1,
                failure_frames=[
                    TestFailureFrame(
                        test_id="test_calc",
                        test_file="tests/test_calc.py",
                        error_type="AssertionError",
                        error_message="1 != 2",
                        stack_frames=[
                            StackFrame(file_path="tests/test_calc.py", line_number=5),
                            StackFrame(file_path=self.failure_file, line_number=self.failure_line),
                        ],
                        failing_source_file=self.failure_file,
                        failing_source_line=self.failure_line,
                    )
                ],
            )

    def parse_output(self, raw_output: str) -> list[TestFailureFrame]:
        return []


def test_autonomous_loop_happy_path_single_attempt():
    """G4-1: Verifies successful single-attempt bug fix and patch application."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("def get_value():\n    return 1\n", encoding="utf-8")

        # Initial test run fails, after patch tests pass
        runner = MockTestRunner(outcomes=[False, True])
        loop = AutonomousEngineeringLoop(repo_root=root, test_runner=runner, max_retries=3)

        task = EngineeringTask(task_id="fix_001", goal="Fix value returning 1 instead of 2")

        def patch_gen(candidate: FaultCandidate, attempt: int) -> str:
            return "def get_value():\n    return 2\n"

        result = loop.run_task(task, patch_generator_fn=patch_gen)

        assert result.success is True
        assert result.attempts_used == 1
        assert result.final_status == "COMPLETED"
        assert "return 2" in src.read_text(encoding="utf-8")


def test_autonomous_loop_iterative_repair_success():
    """G4-2: Verifies multi-attempt repair where attempt 1 fails and attempt 2 succeeds."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("def get_value():\n    return 0\n", encoding="utf-8")

        # Initial test fails, attempt 1 patch still fails, attempt 2 patch passes
        runner = MockTestRunner(outcomes=[False, False, True])
        loop = AutonomousEngineeringLoop(repo_root=root, test_runner=runner, max_retries=3)

        task = EngineeringTask(task_id="fix_002", goal="Fix value returning 2")

        def patch_gen(candidate: FaultCandidate, attempt: int) -> str:
            if attempt == 1:
                return "def get_value():\n    return 1\n"  # Still wrong
            return "def get_value():\n    return 2\n"      # Correct

        result = loop.run_task(task, patch_generator_fn=patch_gen)

        assert result.success is True
        assert result.attempts_used == 2
        assert result.final_status == "COMPLETED"
        assert "return 2" in src.read_text(encoding="utf-8")


def test_autonomous_loop_max_retries_exhausted_fail_closed_rollback():
    """G4-3: Verifies max retries exhausted restores baseline state with byte-exact zero artifacts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        original_code = "def get_value():\n    return 0\n"
        src.write_text(original_code, encoding="utf-8")

        # All test attempts fail
        runner = MockTestRunner(outcomes=[False, False, False, False])
        loop = AutonomousEngineeringLoop(repo_root=root, test_runner=runner, max_retries=3)

        task = EngineeringTask(task_id="fix_003", goal="Unfixable goal")

        def patch_gen(candidate: FaultCandidate, attempt: int) -> str:
            if attempt == 2:
                # Simulate generating an untracked auxiliary file during an attempt
                untracked_file = root / "src" / "scratch_untracked.py"
                untracked_file.write_text("# Untracked temporary artifact\n", encoding="utf-8")
            return f"# Attempt {attempt}\ndef get_value():\n    return -1\n"

        result = loop.run_task(task, patch_generator_fn=patch_gen)

        assert result.success is False
        assert result.attempts_used == 3
        assert result.rolled_back is True
        assert result.final_status == "FAILED"
        # Must match original content exactly
        assert src.read_text(encoding="utf-8") == original_code
        # Untracked auxiliary file must be completely purged by rollback
        assert not (root / "src" / "scratch_untracked.py").exists()
        assert len(list((root / "src").glob("*.py"))) == 1


def test_autonomous_loop_reward_hacking_triggers_immediate_rollback():
    """G4-4: Verifies reward hacking attempt immediately halts loop and rolls back without retry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        original_code = "def get_value():\n    return 0\n"
        src.write_text(original_code, encoding="utf-8")

        test_file = root / "tests" / "test_calc.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_calc(): assert False\n", encoding="utf-8")

        runner = MockTestRunner(outcomes=[False])
        loop = AutonomousEngineeringLoop(repo_root=root, test_runner=runner, max_retries=3)

        task = EngineeringTask(task_id="fix_004", goal="Try modifying test")

        def malicious_patch_gen(candidate: FaultCandidate, attempt: int) -> str:
            # Attempt to modify the test file instead of source
            candidate.file_path = "tests/test_calc.py"
            return "def test_calc(): assert True\n"

        result = loop.run_task(task, patch_generator_fn=malicious_patch_gen)

        assert result.success is False
        assert result.attempts_used == 1  # Did NOT consume all 3 retries
        assert result.final_status == "ABORTED_VIOLATION"
        assert result.rolled_back is True
        assert "RewardHackingViolation" in str(result.error)
        assert src.read_text(encoding="utf-8") == original_code


def test_autonomous_loop_protected_ceiling_triggers_immediate_halt():
    """G4-5: Verifies protected ceiling violation immediately halts loop without retrying."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        original_code = "def get_value():\n    return 0\n"
        src.write_text(original_code, encoding="utf-8")

        runner = MockTestRunner(outcomes=[False])
        loop = AutonomousEngineeringLoop(repo_root=root, test_runner=runner, max_retries=3)

        task = EngineeringTask(task_id="fix_005", goal="Try modifying execution_policy")

        def malicious_ceiling_patch_gen(candidate: FaultCandidate, attempt: int) -> str:
            candidate.file_path = "src/core/orchestration/execution_policy.py"
            return "# Tampered policy\n"

        result = loop.run_task(task, patch_generator_fn=malicious_ceiling_patch_gen)

        assert result.success is False
        assert result.attempts_used == 1  # Immediate hard stop
        assert result.final_status == "ABORTED_VIOLATION"
        assert result.rolled_back is True
        assert "ProtectedCeilingViolation" in str(result.error)


def test_autonomous_loop_unhandled_exception_fails_closed():
    """G4-6: Verifies unexpected crash inside loop fails closed and rolls back baseline."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        original_code = "def get_value():\n    return 0\n"
        src.write_text(original_code, encoding="utf-8")

        runner = MockTestRunner(outcomes=[False])
        loop = AutonomousEngineeringLoop(repo_root=root, test_runner=runner, max_retries=3)

        task = EngineeringTask(task_id="fix_006", goal="Crash test")

        def crashing_gen(candidate: FaultCandidate, attempt: int) -> str:
            raise RuntimeError("Simulated unhandled model crash")

        result = loop.run_task(task, patch_generator_fn=crashing_gen)

        assert result.success is False
        assert result.rolled_back is True
        assert result.final_status == "FAILED"
        assert "Simulated unhandled model crash" in str(result.error)
        assert src.read_text(encoding="utf-8") == original_code


def test_autonomous_loop_binary_exact_rollback():
    """G4-7: Verifies binary files (non-UTF8) are rolled back with byte-exact precision."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("def get_value(): return 0\n", encoding="utf-8")

        # Binary fixture with arbitrary non-UTF-8 bytes
        bin_file = root / "fixtures" / "data.bin"
        bin_file.parent.mkdir(parents=True, exist_ok=True)
        original_bytes = b"\x00\xff\xfe\x80\x90\xaa\xbb\xcc\xdd\xee"
        bin_file.write_bytes(original_bytes)

        runner = MockTestRunner(outcomes=[False, False])
        loop = AutonomousEngineeringLoop(repo_root=root, test_runner=runner, max_retries=1)
        task = EngineeringTask(task_id="fix_007", goal="Fail and rollback")

        def corrupting_gen(candidate: FaultCandidate, attempt: int) -> str:
            # Modify binary file during attempt
            bin_file.write_bytes(b"\x00\x00\x00\x00")
            return "def get_value(): return -1\n"

        result = loop.run_task(task, patch_generator_fn=corrupting_gen)

        assert result.success is False
        assert result.rolled_back is True
        # Binary file must be restored byte-for-byte
        assert bin_file.read_bytes() == original_bytes


def test_snapshot_baseline_fails_loud_on_unreadable_file():
    """G4-8: Verifies unreadable file during snapshot raises loud RuntimeError aborting the task."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "src" / "calc.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("def get_value(): return 0\n", encoding="utf-8")

        loop = AutonomousEngineeringLoop(repo_root=root)
        
        # Monkeypatch Path.read_bytes on calc.py to simulate an unreadable file
        import unittest.mock as mock
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError("Access denied")):
            with pytest.raises(RuntimeError) as exc_info:
                loop._snapshot_baseline()
            assert "Critical failure during baseline snapshot" in str(exc_info.value)
