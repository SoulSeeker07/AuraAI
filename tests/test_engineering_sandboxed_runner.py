"""
Adversarial Verification Suite for SandboxedPytestRunnerAdapter (TD-008)
Location: tests/test_engineering_sandboxed_runner.py

Verifies 5 security acceptance gates:
1. Gate 1: Lifecycle and Fail-Closed Invariant on unavailable sandbox.
2. Gate 2: Protected ceiling file modification blocked by NTFS (governance.py / technical_debt.md).
3. Gate 3: General workspace write/creation blocked by NTFS (blanket RX on workspace).
4. Gate 4: Secret file (.env) read access blocked by explicit NTFS DENY rule.
5. Gate 5: Subprocess environment credential scrubbing (zero API keys leaked).
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
import shutil
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from src.engineering.test_runner import SandboxedPytestRunnerAdapter, PytestRunnerAdapter


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def staging_dir(repo_root: Path) -> Path:
    staging = repo_root / ".aura_staging" / "test_adversarial_runner"
    staging.mkdir(parents=True, exist_ok=True)
    yield staging
    shutil.rmtree(staging, ignore_errors=True)


class MockUnavailableSandbox:
    def is_available(self) -> bool:
        return False

    def execute(self, *args, **kwargs):
        raise RuntimeError("Should not be called")


# ---------------------------------------------------------------------------
# Gate 1: Lifecycle & Fail-Closed Invariant
# ---------------------------------------------------------------------------

def test_g1_lifecycle_and_fail_closed(repo_root: Path, staging_dir: Path):
    """
    Gate 1: Verifies SandboxedPytestRunnerAdapter fails closed with RuntimeError
    when the sandbox provider is unavailable, refusing to execute unconfined.
    """
    # 1. Test fail-closed guard
    failing_runner = SandboxedPytestRunnerAdapter(
        repo_root=repo_root,
        staging_dir=staging_dir,
        sandbox=MockUnavailableSandbox(),
    )
    with pytest.raises(RuntimeError, match="Fail-Closed Security Invariant"):
        failing_runner.run_tests(test_path="tests/unit/test_empty.py")


# ---------------------------------------------------------------------------
# Gate 2: Protected Ceiling Write Block
# ---------------------------------------------------------------------------

def test_g2_protected_ceiling_write_block(repo_root: Path, staging_dir: Path):
    """
    Gate 2: Adversarial probe attempting to mutate or truncate protected ceiling files
    (governance.py or technical_debt.md) must be blocked by NTFS with PermissionError.
    """
    ceiling_targets = [
        repo_root / "src" / "daemon" / "governance.py",
        repo_root / "docs" / "technical_debt.md",
    ]
    # Snapshot bytes
    snapshots = {t: t.read_bytes() for t in ceiling_targets if t.exists()}

    probe_test_file = staging_dir / "test_adversarial_ceiling_probe.py"
    probe_code = """
import pytest
from pathlib import Path

def test_malicious_ceiling_mutation():
    target = Path("docs/technical_debt.md").resolve()
    target.write_text("# MALICIOUS_MUTATION_ATTEMPT\\n", encoding="utf-8")
"""
    probe_test_file.write_text(probe_code, encoding="utf-8")

    runner = SandboxedPytestRunnerAdapter(repo_root=repo_root, staging_dir=staging_dir)

    try:
        res = runner.run_tests(test_path=str(probe_test_file))
        # The test run MUST fail because writing to docs/technical_debt.md raises PermissionError
        assert not res.success, "Adversarial ceiling write test unexpectedly succeeded!"
        assert res.failed_tests >= 1 or res.error_count >= 1, "Expected test failure frame."
        # Verify the failure frame or output contains PermissionError / Access Denied
        assert "PermissionError" in res.raw_output or "Access is denied" in res.raw_output or "Permission denied" in res.raw_output
    finally:
        # Assert byte-for-byte identity and restore if damaged
        for target, original_bytes in snapshots.items():
            current_bytes = target.read_bytes()
            if current_bytes != original_bytes:
                target.write_bytes(original_bytes)
                pytest.fail(f"CONTAINMENT BREACH: Ceiling target '{target.name}' was mutated during test execution!")


# ---------------------------------------------------------------------------
# Gate 3: General Workspace Blanket Write Block
# ---------------------------------------------------------------------------

def test_g3_general_workspace_write_block(repo_root: Path, staging_dir: Path):
    """
    Gate 3: Adversarial probe attempting to write an arbitrary non-ceiling file
    inside the src/ tree must be blocked by NTFS with PermissionError.
    """
    escape_file = repo_root / "src" / "probe_src_escape.py"
    if escape_file.exists():
        escape_file.unlink()

    probe_test_file = staging_dir / "test_adversarial_workspace_probe.py"
    probe_code = """
import pytest
from pathlib import Path

def test_malicious_workspace_escape():
    target = Path("src/probe_src_escape.py").resolve()
    target.write_text("BREACH_ATTEMPT\\n", encoding="utf-8")
"""
    probe_test_file.write_text(probe_code, encoding="utf-8")

    runner = SandboxedPytestRunnerAdapter(repo_root=repo_root, staging_dir=staging_dir)

    try:
        res = runner.run_tests(test_path=str(probe_test_file))
        assert not res.success, "Adversarial workspace write unexpectedly succeeded!"
        assert not escape_file.exists(), "CONTAINMENT BREACH: probe_src_escape.py was created inside src/!"
        assert "PermissionError" in res.raw_output or "Access is denied" in res.raw_output or "Permission denied" in res.raw_output
    finally:
        if escape_file.exists():
            escape_file.unlink()



# ---------------------------------------------------------------------------
# Gate 4: Secret File (.env) Read Block
# ---------------------------------------------------------------------------

def test_g4_secret_file_env_read_block(repo_root: Path, staging_dir: Path):
    """
    Gate 4: Adversarial probe attempting to read .env off disk must be blocked
    by NTFS explicit (N) DENY rule, raising PermissionError.
    """
    env_file = repo_root / ".env"
    if not env_file.exists():
        pytest.skip(".env does not exist in workspace root to verify.")

    probe_test_file = staging_dir / "test_adversarial_env_read_probe.py"
    probe_code = """
import pytest
from pathlib import Path

def test_malicious_env_read():
    content = Path(".env").read_text(encoding="utf-8")
    assert content != ""
"""
    probe_test_file.write_text(probe_code, encoding="utf-8")

    runner = SandboxedPytestRunnerAdapter(repo_root=repo_root, staging_dir=staging_dir)

    res = runner.run_tests(test_path=str(probe_test_file))
    assert not res.success, "Adversarial .env read unexpectedly succeeded!"
    assert "PermissionError" in res.raw_output or "Access is denied" in res.raw_output or "Permission denied" in res.raw_output


# ---------------------------------------------------------------------------
# Gate 5: Subprocess Environment Scrubbing
# ---------------------------------------------------------------------------

def test_g5_subprocess_environment_scrubbing(repo_root: Path, staging_dir: Path):
    """
    Gate 5: Verifies that host credentials and API keys are scrubbed from the
    subprocess environment, so tests cannot inspect os.environ for secrets.
    """
    # Inject host secrets into parent process
    os.environ["GROQ_API_KEY"] = "host_secret_groq_key_xyz"
    os.environ["GITHUB_TOKEN"] = "ghp_host_secret_token_123"

    probe_test_file = staging_dir / "test_env_scrubbing_probe.py"
    probe_code = """
import os
import pytest

def test_verify_no_host_secrets():
    assert "GROQ_API_KEY" not in os.environ, f"GROQ_API_KEY leaked: {os.environ.get('GROQ_API_KEY')}"
    assert "GITHUB_TOKEN" not in os.environ, f"GITHUB_TOKEN leaked: {os.environ.get('GITHUB_TOKEN')}"
"""
    probe_test_file.write_text(probe_code, encoding="utf-8")

    runner = SandboxedPytestRunnerAdapter(repo_root=repo_root, staging_dir=staging_dir)

    res = runner.run_tests(test_path=str(probe_test_file))
    assert res.success, f"Environment scrubbing probe failed: {res.raw_output}"


# ---------------------------------------------------------------------------
# Gate 6: Auto-Executed Root Drop & Git Hook Injection Block (Persistence Escape)
# ---------------------------------------------------------------------------

def test_g6_root_auto_exec_and_git_hook_drop_blocked(repo_root: Path, staging_dir: Path):
    """
    Gate 6: Adversarial probe attempting to plant auto-executed files at the workspace
    root (conftest.py, sitecustomize.py), inject .git/hooks/, or overwrite pre-existing
    configuration files (pyproject.toml) must be strictly blocked by kernel NTFS DENY rules
    with PermissionError, preventing privilege escalation into subsequent human reviewer commands.
    """
    targets = [
        repo_root / "conftest.py",
        repo_root / "sitecustomize.py",
        repo_root / ".git" / "hooks" / "pre-commit",
        repo_root / "probe_root_escape.txt",
    ]
    # Ensure none exist before test
    for t in targets:
        if t.exists():
            t.unlink()

    # Pre-existing file snapshot
    pyproject_file = repo_root / "pyproject.toml"
    original_pyproject_bytes = pyproject_file.read_bytes()

    probe_test_file = staging_dir / "test_adversarial_root_drop_probe.py"
    probe_code = """
import pytest
from pathlib import Path

def test_malicious_root_conftest_drop():
    p = Path("conftest.py").resolve()
    p.write_text("# MALICIOUS_CONFTEST_AUTO_EXEC\\n", encoding="utf-8")

def test_malicious_sitecustomize_drop():
    p = Path("sitecustomize.py").resolve()
    p.write_text("# MALICIOUS_SITECUSTOMIZE_AUTO_EXEC\\n", encoding="utf-8")

def test_malicious_git_hook_drop():
    p = Path(".git/hooks/pre-commit").resolve()
    p.write_text("#!/bin/sh\\n# MALICIOUS_GIT_HOOK\\n", encoding="utf-8")

def test_malicious_root_escape_txt():
    p = Path("probe_root_escape.txt").resolve()
    p.write_text("BREACH_ATTEMPT\\n", encoding="utf-8")

def test_malicious_pyproject_toml_overwrite():
    p = Path("pyproject.toml").resolve()
    p.write_text("[tool.malicious]\\nescape = true\\n", encoding="utf-8")
"""
    probe_test_file.write_text(probe_code, encoding="utf-8")

    runner = SandboxedPytestRunnerAdapter(repo_root=repo_root, staging_dir=staging_dir)

    try:
        res = runner.run_tests(test_path=str(probe_test_file))
        # Test run MUST fail because all five operations raise PermissionError
        assert not res.success, "Adversarial root/hook drop unexpectedly succeeded!"
        assert res.failed_tests >= 1 or res.error_count >= 1, "Expected test failure frames."
        assert "PermissionError" in res.raw_output or "Access is denied" in res.raw_output or "Permission denied" in res.raw_output

        # Verify on physical disk that zero target files were created
        for t in targets:
            assert not t.exists(), f"CRITICAL CONTAINMENT BREACH: Target '{t}' was dropped on physical disk!"

        # Verify pyproject.toml was not mutated
        current_pyproject_bytes = pyproject_file.read_bytes()
        assert current_pyproject_bytes == original_pyproject_bytes, "CRITICAL BREACH: pyproject.toml was overwritten!"
    finally:
        for t in targets:
            if t.exists():
                t.unlink()
        if pyproject_file.read_bytes() != original_pyproject_bytes:
            pyproject_file.write_bytes(original_pyproject_bytes)


