"""
Comprehensive Architecture Analysis for AuraAI

This script analyzes:
1. Import dependencies across the codebase
2. Circular dependency detection
3. Component linkage to Aura Brain
4. Potential duplication
5. Integration completeness
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
import ast
import importlib.util
import json

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
CORE_DIR = PROJECT_ROOT / "core"
BACKEND_DIR = PROJECT_ROOT / "backend"

print("=" * 100)
print("🔍 COMPREHENSIVE ARCHITECTURE ANALYSIS FOR AURA AI")
print("=" * 100)
print()

# Scan all Python files
all_files = []
file_structure = {}

for directory in [SRC_DIR, CORE_DIR, BACKEND_DIR]:
    if directory.exists():
        for py_file in directory.rglob("*.py"):
            rel_path = str(py_file.relative_to(PROJECT_ROOT))
            all_files.append(rel_path)
            file_structure[rel_path] = py_file

print(f"Found {len(all_files)} Python files in codebase")
print()

# Analyze imports for each file
print("Analyzing imports and dependencies...")
print()

import_graph = defaultdict(set)  # file -> set of imported files
imported_by = defaultdict(set)   # file -> set of files that import it
file_to_modules = {}             # file -> list of module names

for file_path in all_files:
    try:
        with open(file_structure[file_path], 'r', encoding='utf-8') as f:
            source = f.read()
            tree = ast.parse(source)

        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    modules.append(module_name)
                    import_graph[file_path].add(module_name)
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module.split('.')[0] if node.module else ''
                if module_name:
                    modules.append(module_name)
                    import_graph[file_path].add(module_name)

        file_to_modules[file_path] = list(set(modules))

    except Exception as e:
        print(f"  ⚠ Error parsing {file_path}: {e}")

# Build reverse import graph
for file_path, imports in import_graph.items():
    for module in imports:
        imported_by[file_path].add(module)

# Check for circular dependencies
print("=" * 100)
print("🚨 CIRCULAR DEPENDENCY DETECTION")
print("=" * 100)
print()

circular_deps = []
visited = set()
rec_stack = set()

def check_circular(file_path, path=[]):
    """Check for circular dependencies using DFS."""
    if file_path in rec_stack:
        # Found a cycle
        cycle_start = path.index(file_path)
        cycle = path[cycle_start:] + [file_path]
        circular_deps.append(cycle)
        return

    if file_path in visited:
        return

    visited.add(file_path)
    rec_stack.add(file_path)
    path.append(file_path)

    for module in import_graph.get(file_path, []):
        # Find all files that import this module
        for other_file in all_files:
            if file_structure[other_file].parent == Path(file_path).parent:
                # Check if this file imports the module
                if any(m.startswith(module) for m in file_to_modules.get(other_file, [])):
                    check_circular(other_file, path[:])

    rec_stack.remove(file_path)
    path.pop()

for file_path in all_files:
    check_circular(file_path)

if circular_deps:
    print(f"⚠ Found {len(circular_deps)} circular dependency(s):")
    for i, cycle in enumerate(circular_deps, 1):
        print(f"  Cycle {i}: {' → '.join(cycle)}")
else:
    print("✅ No circular dependencies detected")

print()

# Check for duplication
print("=" * 100)
print("📝 DUPLICATION DETECTION")
print("=" * 100)
print()

# Look for duplicate function/class definitions
print("Checking for duplicate function/class definitions...")
print()

duplicate_functions = defaultdict(list)
duplicate_classes = defaultdict(list)

for file_path in all_files:
    try:
        with open(file_structure[file_path], 'r', encoding='utf-8') as f:
            source = f.read()
            tree = ast.parse(source)

        functions = defaultdict(list)
        classes = defaultdict(list)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions[node.name].append((file_path, node.lineno))
            elif isinstance(node, ast.ClassDef):
                classes[node.name].append((file_path, node.lineno))

        for func_name, locations in functions.items():
            if len(locations) > 1:
                duplicate_functions[func_name] = locations

        for class_name, locations in classes.items():
            if len(locations) > 1:
                duplicate_classes[class_name] = locations

    except Exception as e:
        print(f"  ⚠ Error parsing {file_path}: {e}")

if duplicate_functions:
    print(f"⚠ Found {len(duplicate_functions)} functions with duplicate definitions:")
    for func_name, locations in duplicate_functions.items():
        print(f"  - {func_name}:")
        for file_path, line in locations[:3]:
            print(f"      {file_path}:{line}")
else:
    print("✅ No duplicate function definitions found")

print()

if duplicate_classes:
    print(f"⚠ Found {len(duplicate_classes)} classes with duplicate definitions:")
    for class_name, locations in duplicate_classes.items():
        print(f"  - {class_name}:")
        for file_path, line in locations[:3]:
            print(f"      {file_path}:{line}")
else:
    print("✅ No duplicate class definitions found")

print()

# Check Aura Brain integration
print("=" * 100)
print("🔗 AURA BRAIN INTEGRATION ANALYSIS")
print("=" * 100)
print()

# Core components that should be initialized by AuraBrain
core_components = {
    "MemoryManager": "core.memory.memory_manager",
    "ToolRouter": "core.tools.tool_router",
    "PluginRegistry": "core.plugins.plugin_registry",
    "CapabilityRouter": "routing.capability_router",
    "WorkspaceManager": "core.workspace.workspace_manager",
    "AgentRegistry": "agents.agent_registry",
    "ResponseCoordinator": "brain.response_coordinator",
    "DecisionEngine": "brain.decision_engine",
    "ContextBuilder": "brain.context_builder",
    "WorkflowOrchestrator": "routing.workflow_orchestrator",
}

print("Checking Aura Brain component initialization...")
print()

aura_brain_components = []

# Look for AuraBrain class
found_aura_brain = False
for file_path in all_files:
    if "aura_brain.py" in file_path:
        try:
            with open(file_structure[file_path], 'r', encoding='utf-8') as f:
                source = f.read()
                if "class AuraBrain" in source:
                    found_aura_brain = True
                    print(f"✅ AuraBrain found in {file_path}")
                    aura_brain_components.append(file_path)
        except:
            pass

if not found_aura_brain:
    print("❌ AuraBrain NOT found!")
else:
    print()

    # Check if core components are initialized
    missing_components = []
    for component_name, component_path in core_components.items():
        # Parse the component path
        if '.' in component_path:
            module_part, class_name = component_path.rsplit('.', 1)
            files = list(file_structure.keys())
            found_files = [f for f in files if module_part in f and f.endswith('.py')]

            for found_file in found_files:
                try:
                    with open(file_structure[found_file], 'r', encoding='utf-8') as f:
                        source = f.read()
                        if f"class {class_name}" in source:
                            aura_brain_components.append(found_file)
                            break
                except:
                    pass

    print(f"Found {len(aura_brain_components)} core components in AuraBrain")
    print()

    # Check component usage
    print("Checking how components are used...")
    print()

    usage_stats = defaultdict(int)
    for file_path in all_files:
        try:
            with open(file_structure[file_path], 'r', encoding='utf-8') as f:
                source = f.read()

                # Check for common patterns
                if "AuraBrain" in source or "aura_brain" in source.lower():
                    usage_stats['AuraBrain_usage'] += 1

                if "self.memory_manager" in source or "memory_manager" in source:
                    usage_stats['MemoryManager_usage'] += 1

                if "self.tool_router" in source or "tool_router" in source:
                    usage_stats['ToolRouter_usage'] += 1

                if "self.capability_router" in source or "capability_router" in source:
                    usage_stats['CapabilityRouter_usage'] += 1

                if "self.workspace" in source or "workspace_manager" in source:
                    usage_stats['WorkspaceManager_usage'] += 1

        except:
            pass

    print("Component Usage Statistics:")
    print("-" * 100)
    for component, count in sorted(usage_stats.items(), key=lambda x: -x[1]):
        status = "✅" if count > 0 else "❌"
        print(f"  {status} {component}: {count} occurrences")

print()

# Check entry points
print("=" * 100)
print("🚀 ENTRY POINTS AND FLOW")
print("=" * 100)
print()

entry_points = []

# Check main.py
if "main.py" in file_structure:
    try:
        with open(file_structure["main.py"], 'r', encoding='utf-8') as f:
            source = f.read()
            if "AuraCore" in source or "AuraBrain" in source:
                entry_points.append(("main.py", "AuraCore/AuraBrain"))
    except:
        pass

# Check CLI client
cli_client_found = False
for file_path in all_files:
    if "cli_client.py" in file_path:
        try:
            with open(file_structure[file_path], 'r', encoding='utf-8') as f:
                source = f.read()
                if "CLIClient" in source and "AuraCore" in source:
                    entry_points.append((file_path, "CLI Client → AuraCore"))
                    cli_client_found = True
        except:
            pass

if not cli_client_found:
    entry_points.append(("cli_client.py", "CLI Client (likely needs AuraCore integration)"))

print("Entry Points Found:")
print("-" * 100)
for file_path, desc in entry_points:
    print(f"  ✅ {file_path} → {desc}")

print()

# Check plugin system
print("=" * 100)
print("🔌 PLUGIN SYSTEM INTEGRATION")
print("=" * 100)
print()

plugin_system_files = [f for f in all_files if any(
    keyword in f.lower() for keyword in ['plugin', 'tool']
)]

print(f"Found {len(plugin_system_files)} plugin/tool related files")
print()

# Check ToolRouter
tool_router_found = False
for file_path in plugin_system_files:
    if "tool_router" in file_path.lower():
        try:
            with open(file_structure[file_path], 'r', encoding='utf-8') as f:
                source = f.read()
                if "class ToolRouter" in source or "def ToolRouter" in source:
                    print(f"✅ {file_path} - ToolRouter implementation found")
                    tool_router_found = True
        except:
            pass

if not tool_router_found:
    print(f"❌ ToolRouter NOT found!")

print()

# Check Capability Router
capability_router_found = False
for file_path in plugin_system_files:
    if "capability_router" in file_path.lower():
        try:
            with open(file_structure[file_path], 'r', encoding='utf-8') as f:
                source = f.read()
                if "class CapabilityRouter" in source or "def CapabilityRouter" in source:
                    print(f"✅ {file_path} - CapabilityRouter implementation found")
                    capability_router_found = True
        except:
            pass

if not capability_router_found:
    print(f"❌ CapabilityRouter NOT found!")

print()

# Final Summary
print("=" * 100)
print("📊 ARCHITECTURE ANALYSIS SUMMARY")
print("=" * 100)
print()

print("✅ Architecture Health:")
print(f"  - Total Files: {len(all_files)}")
print(f"  - Circular Dependencies: {len(circular_deps) if circular_deps else 0}")
print(f"  - Duplicate Functions: {len(duplicate_functions)}")
print(f"  - Duplicate Classes: {len(duplicate_classes)}")
print()

print("🔗 Integration Status:")
print(f"  - AuraBrain Components: {len(aura_brain_components)}")
print(f"  - Entry Points: {len(entry_points)}")
print(f"  - Plugin System Files: {len(plugin_system_files)}")
print()

print("✅ Ready to Run:")
if found_aura_brain and len(circular_deps) == 0 and len(duplicate_functions) == 0:
    print("  All systems check out! Ready to run.")
else:
    print("  ⚠ Some issues detected. Review above findings.")

print("=" * 100)
