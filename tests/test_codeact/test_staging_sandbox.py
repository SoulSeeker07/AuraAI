"""
Unit Tests for Staging Sandbox
Location: tests/test_codeact/test_staging_sandbox.py
"""

from pathlib import Path
import pytest
from src.codeact.models import CodeActRequest
from src.codeact.staging_sandbox import StagingSandbox


def test_staging_sandbox_lifecycle():
    req = CodeActRequest(goal="test", output_filename="out.txt")
    with StagingSandbox(req) as sandbox:
        assert sandbox.staging_dir is not None
        assert sandbox.staging_dir.exists()
        staging_path = sandbox.staging_dir

        # Write and execute a simple python script
        script = sandbox.write_script("print('sandbox_ok')\n")
        exit_code, stdout, stderr, dur = sandbox.execute(script, timeout=10.0)

        assert exit_code == 0
        assert "sandbox_ok" in stdout
        assert dur > 0

    # Verify cleanup on exit
    assert not staging_path.exists()


def test_staging_sandbox_input_file_copy(tmp_path):
    # Create input file
    input_file = tmp_path / "sample.csv"
    input_file.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    req = CodeActRequest(
        goal="read csv",
        output_filename="out.txt",
        input_files=[input_file],
    )

    with StagingSandbox(req) as sandbox:
        staged_input = sandbox.staging_dir / "sample.csv"
        assert staged_input.exists()

        script = sandbox.write_script(
            "import csv\n"
            "with open('sample.csv') as f:\n"
            "    print(f.read().strip())\n"
        )
        exit_code, stdout, stderr, _ = sandbox.execute(script, timeout=10.0)
        assert exit_code == 0
        assert "1,2,3" in stdout


def test_staging_sandbox_timeout_handling():
    req = CodeActRequest(goal="sleep loop", output_filename="none.txt")
    with StagingSandbox(req) as sandbox:
        script = sandbox.write_script(
            "import time\n"
            "time.sleep(10)\n"
        )
        exit_code, stdout, stderr, _ = sandbox.execute(script, timeout=1.0)
        assert exit_code == -1
        assert "timeout" in stderr.lower() or "timed out" in stderr.lower()
