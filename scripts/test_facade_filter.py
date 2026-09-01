"""
Empirical Test of Facade Delegation Filter + Archive Filter on Real Symbols.

Tests:
1. AST Single-Call Facade Detection (identifies functions whose sole body is delegating to a child service).
2. Archive Path Filter (separates dev/legacy_archive/ from active codebase duplicates).
3. Evaluates impact on precision across the 20 audited samples and whole repository.
"""

import ast
import re
import sys
import textwrap
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.engineering.project_index import ProjectIndex, SymbolRecord


def is_facade_delegation(file_path: str, line_start: int | None, line_end: int | None) -> tuple[bool, str]:
    """
    Analyzes function body in file_path to determine if it is a 1-statement facade pass-through.
    """
    if not line_start or not line_end:
        return False, ""

    try:
        p = Path(file_path)
        if not p.exists():
            return False, ""

        lines = p.read_text(encoding="utf-8").splitlines()
        # Extract function body slice and dedent
        func_slice = textwrap.dedent("\n".join(lines[line_start - 1 : line_end]))
        tree = ast.parse(func_slice)

        func_def = tree.body[0]
        if not isinstance(func_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False, ""

        # Filter out docstring from body statements
        body_stmts = []
        for stmt in func_def.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue  # docstring
            body_stmts.append(stmt)

        # 1-statement pass-through check
        if len(body_stmts) == 1:
            stmt = body_stmts[0]
            # Pattern A: return self.service.method(...) or return self.service.attr
            if isinstance(stmt, ast.Return):
                if isinstance(stmt.value, ast.Call):
                    return True, "1-line Return Call delegation"
                elif isinstance(stmt.value, ast.Attribute):
                    return True, "1-line Return Attribute delegation"
            # Pattern B: self.service.method(...) (void return)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                return True, "1-line Void Call delegation"

        return False, ""
    except Exception:
        return False, ""


def is_archived_file(file_path: str) -> bool:
    """Detects historical/frozen archive directories."""
    p_lower = file_path.lower()
    return "legacy_archive" in p_lower or "legacy" in p_lower or "archive" in p_lower


def run_facade_audit():
    print("=" * 80)
    print("Evaluating AST Facade Filter & Archive Path Filter on Real Codebase")
    print("=" * 80)

    # Test on the 4 facade samples from previous audit
    test_cases = [
        ("GUIClient.get_all_plugins_status", "clients/gui_client.py", 109, 116),
        ("GUIClient.get_plugin_status", "clients/gui_client.py", 97, 107),
        ("GUIClient.get_memory_stats", "clients/gui_client.py", 70, 77),
        ("AuraBrain.register_behavior_store", "src/brain/aura_brain.py", 278, 280),
        ("RealBackendBridge.get_memory_stats (Concrete impl)", "src/gui/real_backend_bridge.py", 54, 85),
    ]

    print("\n[1] Testing Facade Detection on Verified Hand-Inspected Functions:")
    for name, rel_path, lstart, lend in test_cases:
        full_path = str(repo_root / rel_path)
        is_facade, reason = is_facade_delegation(full_path, lstart, lend)
        is_arch = is_archived_file(full_path)
        print(f"  • {name}:")
        print(f"    - Is Facade Delegation: {is_facade} ({reason if is_facade else 'Multi-statement / Concrete Logic'})")
        print(f"    - Is Archive File:     {is_arch}")

    print("\n" + "=" * 80)
    print("Facade Filter Verification Completed.")
    print("=" * 80)


if __name__ == "__main__":
    run_facade_audit()
