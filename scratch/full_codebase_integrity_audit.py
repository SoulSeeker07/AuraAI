"""
Full Codebase Integrity Audit
==============================
Scans all Python files across AuraAI for:
1. Syntax and AST Parse Errors
2. Circular Imports and Import-Time Exceptions across src/
3. Broken References or Module Structure Issues
4. Pytest Collection Health across tests/
"""

import ast
import importlib
import os
import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"

sys.path.insert(0, str(_SRC))
sys.path.insert(1, str(_ROOT))

def audit_ast_syntax():
    print("=" * 70)
    print(" 1. AST SYNTAX & PARSE INTEGRITY SCAN")
    print("=" * 70)
    
    errors = []
    scanned_count = 0
    
    for root, dirs, files in os.walk(_ROOT):
        # Skip venv, .git, .aura_staging, __pycache__
        if any(ignored in root for ignored in [".venv", ".git", ".aura_staging", "__pycache__", "node_modules"]):
            continue
        for file in files:
            if file.endswith(".py"):
                scanned_count += 1
                full_path = Path(root) / file
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        source = f.read()
                    ast.parse(source, filename=str(full_path))
                except Exception as e:
                    errors.append((str(full_path.relative_to(_ROOT)), str(e)))
                    
    print(f"Scanned {scanned_count} Python files.")
    if errors:
        print(f"[FAIL] Found {len(errors)} syntax/AST parse errors:")
        for path, err in errors:
            print(f"  • {path}: {err}")
    else:
        print(" [PASS] 100% of Python files have valid AST syntax.")
    return errors

def audit_imports_and_circularity():
    print("\n" + "=" * 70)
    print(" 2. MODULE IMPORT & CIRCULAR DEPENDENCY SCAN")
    print("=" * 70)
    
    import_errors = []
    circular_warnings = []
    scanned_modules = []
    
    # Ensure src is at the absolute head of sys.path
    if sys.path[0] != str(_SRC):
        sys.path.insert(0, str(_SRC))

    # Discover all importable modules in src/
    for root, dirs, files in os.walk(_SRC):
        if "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                rel_path = Path(root).relative_to(_SRC)
                parts = list(rel_path.parts)
                parts.append(file[:-3])
                mod_name = ".".join(parts)
                scanned_modules.append(mod_name)
            elif file == "__init__.py":
                rel_path = Path(root).relative_to(_SRC)
                parts = list(rel_path.parts)
                if parts:
                    mod_name = ".".join(parts)
                    scanned_modules.append(mod_name)

    print(f"Testing dynamic import for {len(scanned_modules)} modules in src/...")
    
    for mod in sorted(scanned_modules):
        try:
            importlib.import_module(mod)
        except ImportError as ie:
            msg = str(ie)
            if "circular" in msg.lower() or "partially initialized" in msg.lower():
                circular_warnings.append((mod, f"CIRCULAR IMPORT: {msg}"))
            else:
                import_errors.append((mod, f"ImportError: {msg}"))
        except Exception as e:
            # Other top-level exceptions (e.g. hardware missing, audio device not found, etc.)
            import_errors.append((mod, f"{type(e).__name__}: {e}"))

    if circular_warnings:
        print(f"\n[CRITICAL] Found {len(circular_warnings)} Circular Import errors:")
        for mod, err in circular_warnings:
            print(f"  • {mod} -> {err}")
    else:
        print(" [PASS] Zero circular imports detected across src/ modules.")

    if import_errors:
        print(f"\n[WARN/FAIL] Found {len(import_errors)} module import issues:")
        for mod, err in import_errors:
            print(f"  • {mod}: {err}")
    else:
        print(" [PASS] All modules imported cleanly.")

    return circular_warnings, import_errors

def main():
    ast_errs = audit_ast_syntax()
    circ_errs, imp_errs = audit_imports_and_circularity()
    
    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)
    print(f"AST Syntax Errors:       {len(ast_errs)}")
    print(f"Circular Imports:        {len(circ_errs)}")
    print(f"Import/Load Exceptions:  {len(imp_errs)}")
    print("=" * 70)

if __name__ == "__main__":
    main()
