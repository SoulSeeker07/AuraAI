"""
Unit and Integration Tests for Persistent Structural Memory (ProjectIndex).
"""

import os
import sys
import threading
import time
from pathlib import Path
import pytest

from engineering.project_index import ProjectIndex, SymbolRecord
from engineering.code_editor import CodeEditor
from engineering.ast_manager import ASTManager
from engineering.symbol_graph import SymbolGraph, SymbolType
from engineering.dependency_graph import DependencyGraph


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Creates a temporary repository structure with python files."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Create module A
    mod_a = repo / "service_a.py"
    mod_a.write_text(
        '''"""Service A Module."""

def authenticate_user(username: str, token: str = "default") -> bool:
    """Authenticate a user given their token."""
    return len(username) > 0 and len(token) > 0

class UserManager:
    """Manages users."""
    def get_user(self, user_id: int):
        """Retrieve user by ID."""
        return {"id": user_id}
''',
        encoding="utf-8",
    )

    # Create module B
    mod_b = repo / "service_b.py"
    mod_b.write_text(
        '''"""Service B Module."""
import service_a
from service_a import authenticate_user

def process_login(username: str) -> bool:
    """Processes login by calling authenticate."""
    return authenticate_user(username, "tok_123")
''',
        encoding="utf-8",
    )

    return repo


def test_cold_scan_populates_symbols(temp_repo: Path):
    db_path = temp_repo / ".aura" / "memory" / "project_index.sqlite3"
    index = ProjectIndex(repo_root=temp_repo, db_path=db_path)

    stats = index.scan()
    assert stats["updated"] == 2
    assert stats["unchanged"] == 0
    assert stats["deleted"] == 0

    # Verify find_symbol
    auth_syms = index.find_symbol("authenticate_user")
    assert len(auth_syms) >= 1
    auth = auth_syms[0]
    assert auth.name == "authenticate_user"
    assert "service_a.authenticate_user" in auth.qualified_name
    assert "token: str = 'default'" in auth.signature or 'token: str = "default"' in auth.signature
    assert "Authenticate a user" in (auth.docstring or "")

    # Verify class and method
    mgr_syms = index.find_symbol("UserManager")
    assert len(mgr_syms) == 1
    assert mgr_syms[0].symbol_type == "class"

    method_syms = index.find_symbol("get_user")
    assert len(method_syms) == 1
    assert method_syms[0].symbol_type == "method"

    # Verify get_file_symbols
    file_a = str(temp_repo / "service_a.py")
    file_a_syms = index.get_file_symbols(file_a)
    names = [s.name for s in file_a_syms]
    assert "authenticate_user" in names
    assert "UserManager" in names
    assert "get_user" in names


def test_unchanged_file_not_reparsed(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    stats1 = index.scan()
    assert stats1["updated"] == 2

    # Second scan: zero re-parses, all unchanged (mtime fast path)
    stats2 = index.scan()
    assert stats2["unchanged"] == 2
    assert stats2["updated"] == 0
    assert stats2["deleted"] == 0


def test_mtime_touch_behavior(temp_repo: Path):
    """Touching a file (modifying mtime without changing content) updates mtime in DB but skips re-parsing."""
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    mod_a = temp_repo / "service_a.py"
    # Update mtime into the future
    future_time = time.time() + 100
    os.utime(mod_a, (future_time, future_time))

    stats = index.scan()
    # Hash matches -> counted as unchanged, zero re-parsing of symbols
    assert stats["unchanged"] == 2
    assert stats["updated"] == 0


def test_changed_file_rereparses(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    # Modify service_a.py
    mod_a = temp_repo / "service_a.py"
    time.sleep(0.01)
    mod_a.write_text(
        '''"""Modified Service A."""

def updated_auth(user: str) -> bool:
    """Updated auth doc."""
    return True
''',
        encoding="utf-8",
    )

    stats = index.scan()
    assert stats["updated"] == 1
    assert stats["unchanged"] == 1
    assert stats["deleted"] == 0

    # Old symbol should be gone, new symbol present
    assert len(index.find_symbol("authenticate_user")) == 0
    assert len(index.find_symbol("UserManager")) == 0
    assert len(index.find_symbol("updated_auth")) == 1


def test_deleted_file_cascades(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    # Delete service_b.py
    mod_b = temp_repo / "service_b.py"
    mod_b.unlink()

    stats = index.scan()
    assert stats["deleted"] == 1
    assert stats["unchanged"] == 1

    # service_b symbols and callers should be gone
    assert len(index.find_symbol("process_login")) == 0


def test_live_invalidation(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    mod_a = temp_repo / "service_a.py"
    mod_a.write_text(
        '''def live_created_func():
    """Live created doc."""
    return 42
''',
        encoding="utf-8",
    )

    # Invalidate single file without full scan
    success = index.invalidate_file(mod_a)
    assert success is True

    syms = index.find_symbol("live_created_func")
    assert len(syms) == 1
    assert syms[0].docstring == "Live created doc."


def test_code_editor_live_invalidation(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    ast_mgr = ASTManager(repository_path=temp_repo)
    sym_graph = SymbolGraph(repository_path=temp_repo, index=index)
    dep_graph = DependencyGraph(repository_path=temp_repo)

    editor = CodeEditor(
        repository_path=temp_repo,
        ast_manager=ast_mgr,
        symbol_graph=sym_graph,
        dependency_graph=dep_graph,
        project_index=index,
    )

    res = editor.edit_file(
        file_path="service_a.py",
        new_content="""def edited_via_code_editor():
    return 'success'
""",
    )
    assert res.success is True

    # Immediate query without full re-scan
    syms = index.find_symbol("edited_via_code_editor")
    assert len(syms) == 1
    assert syms[0].name == "edited_via_code_editor"


def test_get_importers_of(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    importers = index.get_importers_of("service_a")
    assert len(importers) == 1
    assert "service_b.py" in importers[0]


def test_get_callers_of(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    callers = index.get_callers_of("authenticate_user")
    assert len(callers) >= 1
    caller_names = [c.name for c in callers]
    assert "process_login" in caller_names


def test_concurrent_read(temp_repo: Path):
    index = ProjectIndex(repo_root=temp_repo)
    index.scan()

    errors = []

    def reader():
        try:
            for _ in range(20):
                res = index.find_symbol("authenticate_user")
                assert len(res) >= 1
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0


def test_symbol_graph_fallback_without_index(temp_repo: Path):
    """Confirm SymbolGraph.build_from_files() works with index=None (no regression on fallback path)."""
    sym_graph = SymbolGraph(repository_path=temp_repo, index=None)
    assert sym_graph.index is None

    sym_graph.build_from_files()
    assert len(sym_graph._symbols) >= 2  # module symbols created via fallback path
    assert "service_a.service_a" in sym_graph._symbols
    assert "service_b.service_b" in sym_graph._symbols
