#!/usr/bin/env python3
"""
AuraAI Codebase AST Integrity & Method Shadowing Scanner
========================================================
Scans all Python source files in the repository using Python's AST parser
to ensure no class contains duplicate method definitions that silently shadow
earlier implementations.

Exit codes:
  0: Clean (No duplicates found)
  1: Duplicate method definitions detected
"""

import ast
import os
import sys
from collections import Counter
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_duplicate_class_methods(target_dir: Path) -> List[Tuple[Path, str, str, int]]:
    """
    Parses all .py files in target_dir and returns a list of:
      (file_path, class_name, method_name, duplicate_count)
    """
    duplicates = []

    for root, _, files in os.walk(target_dir):
        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = Path(root) / file
            # Skip virtual environments and caches
            if any(part in file_path.parts for part in (".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist")):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content, filename=str(file_path))
            except Exception as e:
                print(f"[WARN] Failed to parse AST for {file_path}: {e}", file=sys.stderr)
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Collect method names and their decorators
                    methods = []
                    properties = set()

                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            # Check if it's a property setter/deleter
                            is_property_accessor = False
                            for dec in item.decorator_list:
                                if isinstance(dec, ast.Attribute) and dec.attr in ("setter", "deleter"):
                                    is_property_accessor = True
                                elif isinstance(dec, ast.Name) and dec.id == "property":
                                    properties.add(item.name)

                            if not is_property_accessor:
                                methods.append(item.name)

                    counts = Counter(methods)
                    for name, count in counts.items():
                        if count > 1:
                            duplicates.append((file_path, node.name, name, count))

    return duplicates


def find_duplicate_class_methods_in_files(file_paths: List[Path]) -> List[Tuple[Path, str, str, int]]:
    """
    Parses a specific list of .py files and returns duplicate method definitions.
    """
    duplicates = []

    for file_path in file_paths:
        if not file_path.suffix == ".py" or not file_path.exists():
            continue

        # Skip virtual environments and caches
        if any(part in file_path.parts for part in (".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist")):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            print(f"[WARN] Failed to parse AST for {file_path}: {e}", file=sys.stderr)
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                properties = set()

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        is_property_accessor = False
                        for dec in item.decorator_list:
                            if isinstance(dec, ast.Attribute) and dec.attr in ("setter", "deleter"):
                                is_property_accessor = True
                            elif isinstance(dec, ast.Name) and dec.id == "property":
                                properties.add(item.name)

                        if not is_property_accessor:
                            methods.append(item.name)

                counts = Counter(methods)
                for name, count in counts.items():
                    if count > 1:
                        duplicates.append((file_path, node.name, name, count))

    return duplicates


def main() -> int:
    # If specific files passed as arguments, scan only those files
    if len(sys.argv) > 1:
        raw_paths = [Path(p).resolve() for p in sys.argv[1:] if p.endswith(".py")]
        if not raw_paths:
            print("[INFO] No Python files specified to check.")
            return 0
        print(f"Scanning {len(raw_paths)} specified Python file(s) for duplicate class methods...")
        duplicates = find_duplicate_class_methods_in_files(raw_paths)
    else:
        src_dir = PROJECT_ROOT / "src"
        print(f"Scanning codebase for duplicate class methods in {src_dir}...")
        duplicates = find_duplicate_class_methods(src_dir)

    if duplicates:
        print("\n[FAIL] AST INTEGRITY CHECK FAILED:")
        print(f"Found {len(duplicates)} duplicate method definition(s) that cause silent shadowing:\n")
        for file_path, class_name, method_name, count in duplicates:
            try:
                rel_path = file_path.relative_to(PROJECT_ROOT)
            except ValueError:
                rel_path = file_path
            print(f"  * {rel_path} -> Class '{class_name}': method '{method_name}' defined {count} times")
        print("\nPlease remove or rename duplicate method definitions so they don't silently overwrite each other.\n")
        return 1

    print("\n[PASS] AST INTEGRITY CHECK PASSED: 0 duplicate method definitions across the codebase.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
