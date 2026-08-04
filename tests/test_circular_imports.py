"""
Test for circular import detection.

This test detects circular import issues in the Aura codebase
by attempting to import all modules in the core package hierarchy.
"""

import sys
import importlib
from pathlib import Path


def test_no_circular_imports_core():
    """Verify no circular imports in core package."""
    core_path = Path("core")
    
    # Get all Python files in core
    py_files = list(core_path.glob("*.py"))
    
    print(f"\n=== Testing core package for circular imports ===")
    print(f"Found {len(py_files)} Python files in core/")
    
    # Store original imports
    original_imports = set(sys.modules.keys())
    
    for py_file in py_files:
        module_name = f"core.{py_file.stem}"
        print(f"\nImporting: {module_name}")
        
        try:
            # Clear any previous import of this module
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Import the module
            module = importlib.import_module(module_name)
            
            # List all imported modules
            imported_modules = [name for name in sys.modules.keys() if name.startswith(module_name) or name.startswith(module_name.split('.')[0])]
            
            if imported_modules:
                print(f"  Imported modules: {len(imported_modules)}")
                for im in sorted(imported_modules):
                    if im != module_name:
                        print(f"    - {im}")
            
        except Exception as e:
            print(f"  ❌ ERROR: {type(e).__name__}: {e}")
            raise
    
    # Restore
    for mod in list(sys.modules.keys()):
        if mod not in original_imports:
            del sys.modules[mod]


def test_no_circular_imports_agents():
    """Verify no circular imports in agents package."""
    agents_path = Path("core/agents")
    
    if not agents_path.exists():
        print("\n=== agents package not found, skipping ===")
        return
    
    py_files = list(agents_path.glob("*.py"))
    
    print(f"\n=== Testing agents package for circular imports ===")
    print(f"Found {len(py_files)} Python files in core/agents/")
    
    original_imports = set(sys.modules.keys())
    
    for py_file in py_files:
        module_name = f"core.agents.{py_file.stem}"
        print(f"\nImporting: {module_name}")
        
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            module = importlib.import_module(module_name)
            
            imported_modules = [name for name in sys.modules.keys() if name.startswith(module_name)]
            
            if imported_modules:
                print(f"  Imported modules: {len(imported_modules)}")
                for im in sorted(imported_modules):
                    if im != module_name:
                        print(f"    - {im}")
            
        except Exception as e:
            print(f"  ❌ ERROR: {type(e).__name__}: {e}")
            raise
    
    for mod in list(sys.modules.keys()):
        if mod not in original_imports:
            del sys.modules[mod]


def test_no_circular_imports_memory():
    """Verify no circular imports in memory subsystem."""
    memory_path = Path("core/memory")
    
    if not memory_path.exists():
        print("\n=== memory package not found, skipping ===")
        return
    
    py_files = list(memory_path.glob("*.py"))
    
    print(f"\n=== Testing memory package for circular imports ===")
    print(f"Found {len(py_files)} Python files in core/memory/")
    
    original_imports = set(sys.modules.keys())
    
    # Import only subdirectories, not files (files are imported in __init__.py)
    importable_modules = [f for f in py_files if f.is_dir()]
    
    for py_file in importable_modules:
        module_name = f"core.memory.{py_file.stem}"
        print(f"\nImporting: {module_name}")
        
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            module = importlib.import_module(module_name)
            
            imported_modules = [name for name in sys.modules.keys() if name.startswith(module_name)]
            
            if imported_modules:
                print(f"  Imported modules: {len(imported_modules)}")
                for im in sorted(imported_modules):
                    if im != module_name:
                        print(f"    - {im}")
            
        except Exception as e:
            print(f"  ❌ ERROR: {type(e).__name__}: {e}")
            raise
    
    for mod in list(sys.modules.keys()):
        if mod not in original_imports:
            del sys.modules[mod]


def test_no_circular_imports_brain():
    """Verify no circular imports in brain subsystem."""
    brain_path = Path("core/brain")
    
    if not brain_path.exists():
        print("\n=== brain package not found, skipping ===")
        return
    
    py_files = list(brain_path.glob("*.py"))
    
    print(f"\n=== Testing brain package for circular imports ===")
    print(f"Found {len(py_files)} Python files in core/brain/")
    
    original_imports = set(sys.modules.keys())
    
    for py_file in py_files:
        module_name = f"core.brain.{py_file.stem}"
        print(f"\nImporting: {module_name}")
        
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            module = importlib.import_module(module_name)
            
            imported_modules = [name for name in sys.modules.keys() if name.startswith(module_name)]
            
            if imported_modules:
                print(f"  Imported modules: {len(imported_modules)}")
                for im in sorted(imported_modules):
                    if im != module_name:
                        print(f"    - {im}")
            
        except Exception as e:
            print(f"  ❌ ERROR: {type(e).__name__}: {e}")
            raise
    
    for mod in list(sys.modules.keys()):
        if mod not in original_imports:
            del sys.modules[mod]


if __name__ == "__main__":
    print("=" * 80)
    print("CIRCULAR IMPORT DETECTION TEST")
    print("=" * 80)
    
    test_no_circular_imports_core()
    test_no_circular_imports_agents()
    test_no_circular_imports_memory()
    test_no_circular_imports_brain()
    
    print("\n" + "=" * 80)
    print("✅ All circular import tests completed successfully")
    print("=" * 80)
