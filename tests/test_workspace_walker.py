"""
Unit & Integration Tests for WorkspaceWalker (M20.4b)

Tests:
  1. Nested .gitignore precedence & scoped overrides
  2. Negation patterns (!important.log) un-ignoring in child directories
  3. Default always-ignore rules when no .gitignore is present
  4. Hard cap (max_files) safety net triggering
  5. Single-path point-check (is_ignored) for live file watchers
  6. Boundary escape safety enforcement
"""

import tempfile
from pathlib import Path
import pytest

from workspace.workspace_walker import (
    BoundaryEscapeError,
    WorkspaceSizeError,
    WorkspaceWalker,
)
from engineering.workspace_walker import WorkspaceFileWalker


@pytest.fixture
def temp_workspace():
    """Create a temporary directory structure for testing workspace walks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir).resolve()
        yield root


def test_nested_gitignore_precedence_and_negations(temp_workspace: Path):
    """
    Verify:
      - Root .gitignore ignores all *.log
      - Nested frontend/.gitignore un-ignores !important.log
      - Nested frontend/sub/.gitignore adds secret.key ignore
    """
    # 1. Create file structure
    (temp_workspace / ".gitignore").write_text("*.log\nbuild/\n", encoding="utf-8")
    
    (temp_workspace / "src").mkdir()
    (temp_workspace / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (temp_workspace / "src" / "debug.log").write_text("log data", encoding="utf-8")
    
    frontend = temp_workspace / "frontend"
    frontend.mkdir()
    (frontend / ".gitignore").write_text("!important.log\n*.tmp\n", encoding="utf-8")
    (frontend / "app.js").write_text("console.log()", encoding="utf-8")
    (frontend / "normal.log").write_text("normal log", encoding="utf-8")
    (frontend / "important.log").write_text("important log", encoding="utf-8")
    (frontend / "draft.tmp").write_text("temp data", encoding="utf-8")
    
    sub = frontend / "sub"
    sub.mkdir()
    (sub / ".gitignore").write_text("secret.key\n", encoding="utf-8")
    (sub / "secret.key").write_text("my-secret", encoding="utf-8")
    (sub / "public.txt").write_text("public data", encoding="utf-8")

    walker = WorkspaceWalker(root=temp_workspace)
    files = walker.walk_files()
    rel_files = [f.relative_to(temp_workspace).as_posix() for f in files]

    # Assertions
    assert "src/main.py" in rel_files
    assert "frontend/app.js" in rel_files
    assert "frontend/important.log" in rel_files  # Negation in child un-ignored this
    assert "frontend/sub/public.txt" in rel_files

    # Ignored files must NOT be in walked files
    assert "src/debug.log" not in rel_files
    assert "frontend/normal.log" not in rel_files
    assert "frontend/draft.tmp" not in rel_files
    assert "frontend/sub/secret.key" not in rel_files


def test_default_always_ignore_without_gitignore(temp_workspace: Path):
    """Verify built-in defaults apply even when no .gitignore file exists."""
    # Create allowed files
    (temp_workspace / "main.py").write_text("x = 1", encoding="utf-8")
    (temp_workspace / "README.md").write_text("# Readme", encoding="utf-8")

    # Create always-ignored paths
    (temp_workspace / ".git").mkdir()
    (temp_workspace / ".git" / "config").write_text("git config", encoding="utf-8")
    
    (temp_workspace / "__pycache__").mkdir()
    (temp_workspace / "__pycache__" / "main.cpython-311.pyc").write_text("bytecode", encoding="utf-8")
    
    (temp_workspace / ".venv").mkdir()
    (temp_workspace / ".venv" / "pyvenv.cfg").write_text("cfg", encoding="utf-8")
    
    (temp_workspace / "node_modules").mkdir()
    (temp_workspace / "node_modules" / "package.json").write_text("{}", encoding="utf-8")

    walker = WorkspaceWalker(root=temp_workspace, respect_gitignore=True)
    files = walker.walk_files()
    rel_files = sorted([f.relative_to(temp_workspace).as_posix() for f in files])

    assert rel_files == ["README.md", "main.py"]


def test_hard_cap_safety_net(temp_workspace: Path):
    """Verify max_files raises WorkspaceSizeError when exceeded."""
    # Create 10 files
    for i in range(10):
        (temp_workspace / f"file_{i}.py").write_text(f"# file {i}", encoding="utf-8")

    # Cap set to 5
    walker = WorkspaceWalker(root=temp_workspace, max_files=5)
    with pytest.raises(WorkspaceSizeError) as exc_info:
        walker.walk_files()

    assert "exceeded safety limit of 5 files" in str(exc_info.value)


def test_point_check_is_ignored(temp_workspace: Path):
    """Verify is_ignored accurately evaluates individual paths for live file events."""
    (temp_workspace / ".gitignore").write_text("*.log\ncache/\n", encoding="utf-8")
    (temp_workspace / "src").mkdir()
    (temp_workspace / "cache").mkdir()

    walker = WorkspaceWalker(root=temp_workspace)

    assert walker.is_ignored(temp_workspace / "src" / "app.py") is False
    assert walker.is_ignored(temp_workspace / "src" / "error.log") is True
    assert walker.is_ignored(temp_workspace / "cache" / "data.bin") is True
    assert walker.is_ignored(temp_workspace / ".venv" / "lib.py") is True
    assert walker.is_ignored(temp_workspace / "__pycache__") is True


def test_boundary_escape_error(temp_workspace: Path):
    """Verify paths outside the workspace boundary raise BoundaryEscapeError."""
    walker = WorkspaceWalker(root=temp_workspace)
    outside_path = temp_workspace.parent / "escape.py"

    with pytest.raises(BoundaryEscapeError):
        walker.is_ignored(outside_path)


def test_custom_ignore_patterns(temp_workspace: Path):
    """Verify custom ignore rules passed at initialization are respected."""
    (temp_workspace / "normal.py").write_text("x = 1", encoding="utf-8")
    (temp_workspace / "temp_experiment.py").write_text("y = 2", encoding="utf-8")

    walker = WorkspaceWalker(root=temp_workspace, custom_ignores=["temp_*"])
    files = walker.walk_files()
    rel_files = [f.relative_to(temp_workspace).as_posix() for f in files]

    assert rel_files == ["normal.py"]


def test_engineering_workspace_file_walker_adapter(temp_workspace: Path):
    """Verify backward-compatible WorkspaceFileWalker adapter returns WorkspaceScope."""
    (temp_workspace / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    (temp_workspace / "test_main.py").write_text("def test(): pass", encoding="utf-8")
    (temp_workspace / "helper.py").write_text("pass", encoding="utf-8")
    (temp_workspace / "draft.tmp").write_text("temp", encoding="utf-8")

    adapter = WorkspaceFileWalker(repository_path=temp_workspace)
    scope = adapter.walk(pattern="test_*.py")

    assert len(scope.files) == 1
    assert scope.files[0].name == "test_main.py"
    assert scope.truncated is False


def test_mtime_cache_invalidation_on_gitignore_edit(temp_workspace: Path):
    """Verify modifying .gitignore dynamically updates point-check cache without restarts."""
    log_file = temp_workspace / "debug.log"
    log_file.write_text("log data", encoding="utf-8")

    walker = WorkspaceWalker(root=temp_workspace)
    assert walker.is_ignored(log_file) is False

    # 1. User adds .gitignore
    import time
    time.sleep(0.01)  # Ensure distinct mtime
    gitignore = temp_workspace / ".gitignore"
    gitignore.write_text("*.log\n", encoding="utf-8")

    # Point check must detect new .gitignore immediately
    assert walker.is_ignored(log_file) is True

    # 2. User edits .gitignore to un-ignore with negation
    time.sleep(0.01)
    gitignore.write_text("!debug.log\n", encoding="utf-8")

    # Point check must detect edited .gitignore immediately
    assert walker.is_ignored(log_file) is False


def test_repo_nested_inside_build_or_dist_ancestor_folder(temp_workspace: Path):
    """Verify project nested inside a CI folder named 'build' or 'dist' is not falsely ignored."""
    ci_build_dir = temp_workspace / "build" / "MyProject"
    ci_build_dir.mkdir(parents=True)
    (ci_build_dir / "src").mkdir()
    (ci_build_dir / "src" / "app.py").write_text("x = 1", encoding="utf-8")
    (ci_build_dir / "build").mkdir()
    (ci_build_dir / "build" / "compiled.bin").write_text("bin", encoding="utf-8")

    walker = WorkspaceWalker(root=ci_build_dir)
    files = walker.walk_files()
    rel_files = [f.relative_to(ci_build_dir).as_posix() for f in files]

    # Project's src/app.py must be discovered (not pruned by ancestor /build/)
    assert "src/app.py" in rel_files
    # Internal project build directory must still be ignored
    assert "build/compiled.bin" not in rel_files


def test_raise_on_limit_flag(temp_workspace: Path):
    """Verify raise_on_limit=False returns bounded list without raising exception."""
    for i in range(10):
        (temp_workspace / f"doc_{i}.txt").write_text(f"text {i}", encoding="utf-8")

    walker = WorkspaceWalker(root=temp_workspace, max_files=4)
    # With raise_on_limit=False, truncates to 4 files
    files = walker.walk_files(raise_on_limit=False)
    assert len(files) == 4


def test_explicit_targets_denylist_enforcement(temp_workspace: Path):
    """Verify explicit targets reject ALWAYS_IGNORE_DIRS (.git, .venv) but permit gitignored files."""
    # Create gitignored file and built-in denylist file
    (temp_workspace / ".gitignore").write_text("my_ignored.txt\n", encoding="utf-8")
    (temp_workspace / "my_ignored.txt").write_text("custom ignore", encoding="utf-8")
    
    (temp_workspace / ".git").mkdir()
    (temp_workspace / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")

    adapter = WorkspaceFileWalker(repository_path=temp_workspace)

    # Explicit target on .gitignore-only file should succeed
    scope = adapter.walk(target_files=["my_ignored.txt"])
    assert len(scope.files) == 1
    assert scope.files[0].name == "my_ignored.txt"

    # Explicit target on .git/HEAD must be rejected with BoundaryEscapeError
    with pytest.raises(BoundaryEscapeError):
        adapter.walk(target_files=[".git/HEAD"])
