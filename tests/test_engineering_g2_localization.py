"""
Gate G2 Automated Verification Suite — Fault Localization & Test Runner Adapter
Location: tests/test_engineering_g2_localization.py

Verifies:
- G2-1: Pytest runner adapter parses raw failure output into structured TestFailureFrame items.
- G2-2: Fault localizer resolves stack frame line numbers to concrete source AST symbols.
- G2-3: Fault localizer strictly filters out test files from candidate repair coordinates.
- G2-4: Fallback handling when AST contains syntax issues or unknown symbols.
- G2-5: Test runner timeout handling producing structured timeout failure frames.
"""

import tempfile
from pathlib import Path
import pytest

from src.engineering.test_runner import (
    PytestRunnerAdapter,
    StackFrame,
    TestFailureFrame,
)
from src.engineering.fault_localizer import (
    FaultCandidate,
    FaultLocalizer,
)


SAMPLE_PYTEST_OUTPUT = """
============================= test session starts =============================
collecting ... collected 3 items

tests/test_math.py::test_addition PASSED                                 [ 33%]
tests/test_math.py::test_division_by_zero FAILED                         [ 66%]
tests/test_math.py::test_subtraction PASSED                              [100%]

================================== FAILURES ===================================
___________________________ test_division_by_zero ___________________________

    def test_division_by_zero():
>       res = safe_divide(10, 0)

tests/test_math.py:12: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
src/math_lib/calculator.py:25: in safe_divide
    return a / b
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

>   return a / b
E   ZeroDivisionError: division by zero

src/math_lib/calculator.py:25: ZeroDivisionError
=========================== short test summary info ===========================
FAILED tests/test_math.py::test_division_by_zero - ZeroDivisionError: division by zero
========================= 1 failed, 2 passed in 0.15s =========================
"""


def test_pytest_runner_adapter_parse_output():
    """G2-1: Verifies parsing pytest output into structured TestFailureFrame objects."""
    adapter = PytestRunnerAdapter()
    failures = adapter.parse_output(SAMPLE_PYTEST_OUTPUT)

    assert len(failures) == 1
    f = failures[0]
    assert f.test_id == "test_division_by_zero"
    assert f.error_type == "ZeroDivisionError"
    assert "division by zero" in f.error_message
    assert f.failing_source_file == "src/math_lib/calculator.py"
    assert f.failing_source_line == 25


def test_fault_localizer_ast_symbol_mapping():
    """G2-2: Verifies fault localizer maps source line coordinates to AST symbols."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_file = root / "src" / "math_lib" / "calculator.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        
        src_code = (
            "class MathEngine:\n"
            "    def calculate(self, a, b):\n"
            "        return a + b\n\n"
            "def safe_divide(a, b):\n"
            "    # Line 6\n"
            "    res = a / b\n"
            "    return res\n"
        )
        src_file.write_text(src_code, encoding="utf-8")

        failure = TestFailureFrame(
            test_id="test_division",
            test_file="tests/test_math.py",
            error_type="ZeroDivisionError",
            error_message="division by zero",
            stack_frames=[
                StackFrame(file_path="tests/test_math.py", line_number=10),
                StackFrame(file_path="src/math_lib/calculator.py", line_number=7),
            ],
        )

        localizer = FaultLocalizer(repo_root=root)
        candidates = localizer.localize_fault(failure, repo_root=root)

        assert len(candidates) == 1
        c = candidates[0]
        assert c.file_path == "src/math_lib/calculator.py"
        assert c.line_number == 7
        assert c.symbol_name == "safe_divide"
        assert c.symbol_type == "function"
        assert "res = a / b" in c.line_content


def test_fault_localizer_filters_out_test_files():
    """G2-3: Verifies fault localizer strictly filters out test files to enforce test immunity."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        test_file = root / "tests" / "test_math.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_foo(): assert False\n", encoding="utf-8")

        failure = TestFailureFrame(
            test_id="test_foo",
            test_file="tests/test_math.py",
            error_type="AssertionError",
            error_message="assert False",
            stack_frames=[
                StackFrame(file_path="tests/test_math.py", line_number=1),
                StackFrame(file_path="conftest.py", line_number=5),
            ],
        )

        localizer = FaultLocalizer(repo_root=root)
        candidates = localizer.localize_fault(failure, repo_root=root)

        # Both frames are test/fixture files, so candidates must be empty
        assert len(candidates) == 0


def test_fault_localizer_missing_or_invalid_file_fallback():
    """G2-4: Verifies robust handling when referenced file does not exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        failure = TestFailureFrame(
            test_id="test_missing",
            test_file="tests/test_missing.py",
            error_type="FileNotFoundError",
            error_message="file not found",
            stack_frames=[
                StackFrame(file_path="src/non_existent.py", line_number=10),
            ],
        )

        localizer = FaultLocalizer(repo_root=root)
        candidates = localizer.localize_fault(failure, repo_root=root)
        assert len(candidates) == 0


def test_test_runner_timeout_handling():
    """G2-5: Verifies runner adapter parses timeout events cleanly."""
    adapter = PytestRunnerAdapter(python_executable="python")
    # Simulate run result with timeout structure
    res = adapter._build_run_result(
        is_success=False,
        raw_output="FAILED tests/test_slow.py::test_infinite_loop - TimeoutExpired",
    )
    assert res.success is False
    assert len(res.failure_frames) == 1
    assert res.failure_frames[0].test_id == "tests/test_slow.py::test_infinite_loop"


def test_fault_localizer_nested_symbol_resolution():
    """G2-6: Verifies fault localizer selects the innermost enclosing symbol for nested functions/methods."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_file = root / "src" / "nested.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)

        src_code = (
            "class OuterService:\n"
            "    def outer_method(self, x):\n"
            "        def inner_helper(y):\n"
            "            # Line 4\n"
            "            return x + y\n"
            "        return inner_helper(10)\n"
        )
        src_file.write_text(src_code, encoding="utf-8")

        failure = TestFailureFrame(
            test_id="test_nested",
            test_file="tests/test_nested.py",
            error_type="TypeError",
            error_message="unsupported operand",
            stack_frames=[
                StackFrame(file_path="src/nested.py", line_number=5),
            ],
        )

        localizer = FaultLocalizer(repo_root=root)
        candidates = localizer.localize_fault(failure, repo_root=root)

        assert len(candidates) == 1
        c = candidates[0]
        assert c.symbol_name == "inner_helper"
        assert c.symbol_type == "function"
        assert c.start_line == 3
        assert c.end_line == 5


def test_fault_localizer_filters_out_external_and_stdlib_frames():
    """G2-7: Verifies fault localizer strictly filters out frames outside repo_root or in .venv/site-packages."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_file = root / "src" / "worker.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("def do_work(): pass\n", encoding="utf-8")

        # External site-packages file inside a fake venv
        venv_file = root / ".venv" / "Lib" / "site-packages" / "helper.py"
        venv_file.parent.mkdir(parents=True, exist_ok=True)
        venv_file.write_text("def lib_func(): pass\n", encoding="utf-8")

        failure = TestFailureFrame(
            test_id="test_external",
            test_file="tests/test_worker.py",
            error_type="RuntimeError",
            error_message="external crash",
            stack_frames=[
                # stdlib absolute path
                StackFrame(file_path="C:/Python311/Lib/json/decoder.py", line_number=350),
                # site-packages inside venv
                StackFrame(file_path=str(venv_file), line_number=1),
                # valid source frame
                StackFrame(file_path="src/worker.py", line_number=1),
            ],
        )

        localizer = FaultLocalizer(repo_root=root)
        candidates = localizer.localize_fault(failure, repo_root=root)

        # Only src/worker.py should be retained; external stdlib & venv frames are ignored
        assert len(candidates) == 1
        assert candidates[0].file_path == "src/worker.py"
