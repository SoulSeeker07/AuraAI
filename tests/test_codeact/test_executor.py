"""
Unit Tests for Dynamic CodeAct Executor State Machine
Location: tests/test_codeact/test_executor.py
"""

from pathlib import Path
import pytest
from src.codeact.drafters import MockDrafter
from src.codeact.executor import DynamicCodeActExecutor
from src.codeact.models import CodeActRequest


def test_executor_single_shot_success(tmp_path):
    script = (
        "with open('report.txt', 'w', encoding='utf-8') as f:\n"
        "    f.write('Report generated successfully with lots of valid content.\\n' * 5)\n"
    )
    drafter = MockDrafter([f"```python\n{script}\n```"])
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="generate report",
        output_filename="report.txt",
    )

    res = executor.run(req)
    assert res.status == "success"
    assert res.output_path is not None
    assert res.output_path.exists()
    assert len(res.attempts) == 1
    assert res.attempts[0].exit_code == 0


def test_executor_repair_after_first_attempt_crash():
    bad_script = "raise RuntimeError('syntax or runtime bug')\n"
    good_script = (
        "with open('out.md', 'w', encoding='utf-8') as f:\n"
        "    f.write('# Clean Output\\n' * 10)\n"
    )

    drafter = MockDrafter([
        f"```python\n{bad_script}\n```",
        f"```python\n{good_script}\n```",
    ])
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="create markdown",
        output_filename="out.md",
    )

    res = executor.run(req)
    assert res.status == "success"
    assert len(res.attempts) == 2
    assert res.attempts[0].exit_code != 0
    assert res.attempts[1].exit_code == 0
    # Check that repair prompt was received by the drafter
    assert len(drafter.prompts_received) == 2
    assert "crashed with exit code" in drafter.prompts_received[1]


def test_executor_static_check_rejection_retry():
    # Attempt 1: imports blocked module (socket)
    disallowed_script = "import socket\nprint(1)\n"
    # Attempt 2: valid code
    valid_script = (
        "with open('data.json', 'w', encoding='utf-8') as f:\n"
        "    f.write('{\"status\": \"ok\", \"count\": 42}')\n"
    )

    drafter = MockDrafter([
        f"```python\n{disallowed_script}\n```",
        f"```python\n{valid_script}\n```",
    ])
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="make json",
        output_filename="data.json",
    )

    res = executor.run(req)
    assert res.status == "success"
    # Static rejection did NOT consume a repair attempt
    assert len(res.attempts) == 1
    assert "Blocked security modules" in drafter.prompts_received[1]


def test_executor_max_retries_exhaustion():
    always_bad = "raise ValueError('persistent error')\n"
    drafter = MockDrafter([
        f"```python\n{always_bad}\n```",
        f"```python\n{always_bad}\n```",
        f"```python\n{always_bad}\n```",
    ])
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="fail task",
        output_filename="never.txt",
        max_repair_attempts=3,
    )

    res = executor.run(req)
    assert res.status == "failed"
    assert len(res.attempts) == 3
    assert "Exhausted 3 attempts" in res.final_error


def test_executor_static_check_exhaustion():
    always_blocked = "import requests\n"
    drafter = MockDrafter([
        f"```python\n{always_blocked}\n```",
        f"```python\n{always_blocked}\n```",
        f"```python\n{always_blocked}\n```",
    ])
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="blocked task",
        output_filename="blocked.txt",
        max_static_retries=2,
    )

    res = executor.run(req)
    assert res.status == "rejected"
    assert len(res.attempts) == 0
    assert "Static safety check failed" in res.final_error


def test_executor_syntax_error_static_repair():
    # Attempt 1: SyntaxError due to unescaped quotes/syntax collision
    syntax_error_script = "text = '''unterminated string literal\n"
    # Attempt 2: Repaired code using json.loads / structured line array
    valid_repaired_script = (
        "import json\n"
        "from pathlib import Path\n"
        "payload = {'title': 'Python Quick Reference', 'code': 'def greet(name):\\\\n    return f\"Hello, {name}!\"'}\n"
        "lines = [f'# {payload[\"title\"]}', '', '```python', payload['code'], '```', '', 'Content here.']\n"
        "Path('cheatsheet.md').write_text('\\\\n'.join(lines), encoding='utf-8')\n"
    )

    drafter = MockDrafter([
        f"```python\n{syntax_error_script}\n```",
        f"```python\n{valid_repaired_script}\n```",
    ])
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="create cheatsheet",
        output_filename="cheatsheet.md",
    )

    res = executor.run(req)
    assert res.status == "success"
    assert res.output_path is not None
    assert res.output_path.exists()
    assert len(res.attempts) == 1
    # Check that static repair prompt alerted about SyntaxError and provided JSON escaping guidance
    assert len(drafter.prompts_received) == 2
    repair_prompt = drafter.prompts_received[1]
    assert "FAILED Python syntax validation" in repair_prompt
    assert "CRITICAL ESCAPING RULE" in repair_prompt
    assert "json.loads" in repair_prompt


def test_executor_markdown_json_escaping_synthesis():
    # Demonstrates synthesis of complex markdown with code blocks and backticks via JSON payload
    script = (
        "import json\n"
        "from pathlib import Path\n"
        "payload = {'title': 'Python Quick Reference', 'code': 'def greet(name):\\\\n    return f\"Hello, {name}!\"'}\n"
        "lines = [f'# {payload[\"title\"]}', '', '## Code Example', '```python', payload['code'], '```', '', 'All examples verified.']\n"
        "Path('quickref.md').write_text('\\\\n'.join(lines), encoding='utf-8')\n"
    )

    drafter = MockDrafter([f"```python\n{script}\n```"])
    executor = DynamicCodeActExecutor(drafter=drafter)

    req = CodeActRequest(
        goal="create markdown quick reference",
        output_filename="quickref.md",
    )

    res = executor.run(req)
    assert res.status == "success"
    assert res.output_path.exists()
    content = res.output_path.read_text(encoding="utf-8")
    assert "# Python Quick Reference" in content
    assert "```python" in content
    assert "def greet(name):" in content



