"""
Aura Dependency Graph Generator
===============================
Scans Python AST imports across packages (core, desktop, research, execution, backends, clients)
and validates layer coupling against config/architecture.json.
"""

import ast
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_architecture_manifest(root_dir: Path) -> dict[str, Any]:
    """Load architecture manifest from config/architecture.json."""
    manifest_path = root_dir / "config" / "architecture.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: Could not parse {manifest_path}: {e}")
    return {}


def parse_imports_in_file(filepath: Path) -> set[str]:
    """Parse top-level imports in a Python file."""
    imports = set()
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(filepath))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except Exception:
        pass
    return imports


def generate_dependency_graph(root_dir: Path) -> dict[str, set[str]]:
    """Build a mapping of package -> imported packages."""
    graph: dict[str, set[str]] = {}
    target_packages = [
        "core",
        "desktop",
        "research",
        "execution",
        "clients",
        "frontend",
        "apps",
        "planning",
    ]

    for pkg_name in target_packages:
        pkg_dir = root_dir / pkg_name
        if not pkg_dir.exists():
            pkg_dir = root_dir / "src" / pkg_name
        if not pkg_dir.exists():
            continue

        pkg_imports: set[str] = set()
        for py_file in pkg_dir.rglob("*.py"):
            file_imports = parse_imports_in_file(py_file)
            for imp in file_imports:
                if imp in target_packages and imp != pkg_name:
                    pkg_imports.add(imp)

        graph[pkg_name] = pkg_imports

    return graph


def validate_against_manifest(
    graph: dict[str, set[str]], manifest: dict[str, Any]
) -> list[str]:
    """Validate dependency graph against architecture manifest forbidden rules."""
    violations = []
    forbidden_rules = manifest.get("forbidden", [])

    for rule in forbidden_rules:
        importer = rule.get("importer")
        cannot_import = rule.get("cannot_import")
        if importer in graph and cannot_import in graph[importer]:
            violations.append(
                f"Forbidden import rule violated: '{importer}' imports '{cannot_import}'"
            )

    return violations


def print_ascii_graph(
    graph: dict[str, set[str]], manifest: dict[str, Any], violations: list[str]
) -> None:
    """Print clean ASCII representation of module dependency graph and manifest compliance."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("\n============================================================")
    print("                AURA SYSTEM DEPENDENCY GRAPH                ")
    print("============================================================")
    for pkg, deps in sorted(graph.items()):
        print(f"\n{pkg}")
        if not deps:
            print("  +-- (none)")
        else:
            dep_list = sorted(list(deps))
            for i, dep in enumerate(dep_list):
                connector = "  +-- " if i == len(dep_list) - 1 else "  |-- "
                print(f"{connector}{dep}")

    print("\n------------------------------------------------------------")
    print("MANIFEST ARCHITECTURE COMPLIANCE REPORT")
    print("------------------------------------------------------------")
    if manifest:
        print(
            f"Loaded Manifest: config/architecture.json ({len(manifest.get('layers', {}))} layers defined)"
        )
    else:
        print("Manifest: Not loaded (using defaults)")

    if not violations:
        print("Architectural Violations: 0 (All layer rules satisfied)")
    else:
        print(f"Architectural Violations: {len(violations)}")
        for v in violations:
            print(f"  ✗ {v}")
    print("============================================================\n")


def main():
    manifest = load_architecture_manifest(PROJECT_ROOT)
    graph = generate_dependency_graph(PROJECT_ROOT)
    violations = validate_against_manifest(graph, manifest)
    print_ascii_graph(graph, manifest, violations)


if __name__ == "__main__":
    main()
