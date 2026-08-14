import os
from pathlib import Path

import pytest

from src.engineering.workspace_walker import WorkspaceFileWalker, WorkspaceSizeError, BoundaryEscapeError


@pytest.fixture
def repo_with_ignores(tmp_path: Path):
    """Create a mock repository with .gitignore, .auraignore, and nested files."""
    repo = tmp_path / "mock_repo"
    repo.mkdir()

    # Root .gitignore
    (repo / ".gitignore").write_text("*.log\n/build/\n")
    
    # Root .auraignore
    (repo / ".auraignore").write_text("*.tmp\n")
    
    # Nested .gitignore
    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / ".gitignore").write_text("*.generated.py\n")
    
    # Create some files
    (repo / "main.py").write_text("print('hello')")
    (repo / "error.log").write_text("error")
    (repo / "cache.tmp").write_text("temp")
    
    build_dir = repo / "build"
    build_dir.mkdir()
    (build_dir / "output.bin").write_text("binary")
    
    (src_dir / "app.py").write_text("app")
    (src_dir / "foo.generated.py").write_text("generated")
    
    # Built-in exclusions
    venv_dir = repo / ".venv"
    venv_dir.mkdir()
    (venv_dir / "activate").write_text("activate")
    
    return repo


def test_discovery_ignores_correctly(repo_with_ignores):
    walker = WorkspaceFileWalker(repository_path=repo_with_ignores)
    scope = walker.walk()
    
    files = [f.name for f in scope.files]
    
    # Should include
    assert "main.py" in files
    assert "app.py" in files
    
    # Should ignore (.gitignore)
    assert "error.log" not in files
    assert "output.bin" not in files
    
    # Should ignore (.auraignore)
    assert "cache.tmp" not in files
    
    # Should ignore (nested .gitignore)
    assert "foo.generated.py" not in files
    
    # Should ignore (built-in)
    assert "activate" not in files


def test_explicit_targets_bypass_ignores(repo_with_ignores):
    walker = WorkspaceFileWalker(repository_path=repo_with_ignores)
    
    # Target an ignored file
    target = repo_with_ignores / "src" / "foo.generated.py"
    scope = walker.walk(target_files=[target])
    
    files = [f.name for f in scope.files]
    
    assert "foo.generated.py" in files
    assert "main.py" not in files  # Only targets returned
    assert scope.explicit_count == 1
    assert scope.source == "explicit targets"


def test_boundary_escape_fails(repo_with_ignores):
    walker = WorkspaceFileWalker(repository_path=repo_with_ignores)
    
    # Target a file outside the workspace
    outside_file = repo_with_ignores.parent / "secret.py"
    outside_file.write_text("secret")
    
    with pytest.raises(BoundaryEscapeError):
        walker.walk(target_files=[outside_file])


def test_max_files_cap(repo_with_ignores):
    # Set cap to 1, should fail because there are 2 safe files
    walker = WorkspaceFileWalker(repository_path=repo_with_ignores, max_files=1)
    
    with pytest.raises(WorkspaceSizeError):
        walker.walk()


def test_deterministic_sorting(repo_with_ignores):
    walker = WorkspaceFileWalker(repository_path=repo_with_ignores)
    scope = walker.walk()
    
    # The files should be sorted alphabetically by path
    sorted_files = sorted(scope.files)
    assert scope.files == sorted_files
