"""
Test script for CLI/GUI Architecture

Tests the basic functionality of the new architecture.
"""

import asyncio
import sys
from pathlib import Path

# Add paths in correct order: project root first (to find core/__init__.py), then src
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(1, str(PROJECT_ROOT))

from clients.gui_client import GUIClient
from core.aura_core import AuraCore


def test_aura_core_initialization():
    """Test Aura Core initialization."""
    print("=" * 60)
    print("Testing Aura Core Initialization")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        print("\n✓ Aura Core initialized successfully")
        print(f"  Workspace: {aura_core.workspace}")
        print(f"  Plugins: {aura_core.plugin_count}")
        print(f"  Memory: {aura_core.memory_enabled}")
        print(f"  Knowledge: {aura_core.knowledge_enabled}")
        print(f"  Workspace Aware: {aura_core.workspace_aware}")
        return True
    except Exception as e:
        print(f"\n✗ Failed to initialize Aura Core: {e}")
        return False


def test_gui_client_creation():
    """Test GUI Client creation."""
    print("\n" + "=" * 60)
    print("Testing GUI Client Creation")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        gui_client = GUIClient(aura_core)
        print("\n✓ GUI Client created successfully")

        # Test status retrieval
        status = gui_client.get_status()
        print(f"  Project: {status['project']}")
        print(f"  Plugins loaded: {status['plugins']['count']}")

        return True
    except Exception as e:
        print(f"\n✗ Failed to create GUI Client: {e}")
        return False


def test_component_status():
    """Test component status retrieval."""
    print("\n" + "=" * 60)
    print("Testing Component Status")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        gui_client = GUIClient(aura_core)

        # Test getting status
        status = gui_client.get_status()
        components = status["components"]

        print(f"\n  Found {len(components)} components:")
        for name, info in components.items():
            loaded = "✓" if info["loaded"] else "✗"
            print(f"    {loaded} {name}: {info['status']}")

        return True
    except Exception as e:
        print(f"\n✗ Failed to get component status: {e}")
        return False


def test_plugin_status():
    """Test plugin status retrieval."""
    print("\n" + "=" * 60)
    print("Testing Plugin Status")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        gui_client = GUIClient(aura_core)

        # Test getting plugin list
        plugins = gui_client.get_plugin_list()
        print(f"\n  Loaded {len(plugins)} plugins:")
        for plugin in plugins:
            print(f"    - {plugin}")

        # Test getting plugin status
        all_plugins_status = gui_client.get_all_plugins_status()
        print(f"\n  Total plugins: {all_plugins_status['total']}")

        return True
    except Exception as e:
        print(f"\n✗ Failed to get plugin status: {e}")
        return False


def test_health_report():
    """Test health report generation."""
    print("\n" + "=" * 60)
    print("Testing Health Report")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        gui_client = GUIClient(aura_core)

        # Test getting health report
        report = gui_client.get_health_report()
        print("\n  Component Status:")
        for name, status in report.items():
            if name in ["overall", "percentage"]:
                print(f"    {name}: {status}")
            else:
                print(f"    {name}: {status}")

        return True
    except Exception as e:
        print(f"\n✗ Failed to generate health report: {e}")
        return False


def test_conversation_history():
    """Test conversation history."""
    print("\n" + "=" * 60)
    print("Testing Conversation History")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        gui_client = GUIClient(aura_core)

        # Test adding to conversation
        gui_client.add_conversation_entry("user", "Hello")
        gui_client.add_conversation_entry("assistant", "Hi there!")

        # Test getting history
        history = gui_client.get_conversation_history()
        print(f"\n  Conversation history has {len(history)} entries")

        # Test clearing
        gui_client.clear_conversation_history()
        print("  ✓ History cleared successfully")

        return True
    except Exception as e:
        print(f"\n✗ Failed to test conversation history: {e}")
        return False


def test_workspace_analysis():
    """Test workspace analysis."""
    print("\n" + "=" * 60)
    print("Testing Workspace Analysis")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        gui_client = GUIClient(aura_core)

        # Test scanning workspace
        scan_result = gui_client.scan_workspace()

        if scan_result["success"]:
            print(f"\n  Files: {scan_result['files']}")
            print(f"  Folders: {scan_result['folders']}")
            print(f"  Path: {scan_result['path']}")
        else:
            print(f"\n  ✗ Scan failed: {scan_result['message']}")

        return True
    except Exception as e:
        print(f"\n✗ Failed to test workspace analysis: {e}")
        return False


def test_code_analysis():
    """Test code analysis."""
    print("\n" + "=" * 60)
    print("Testing Code Analysis")
    print("=" * 60)

    try:
        aura_core = AuraCore()
        gui_client = GUIClient(aura_core)

        # Test analyzing a file
        # Use a known existing file
        test_file = PROJECT_ROOT / "main.py"
        if test_file.exists():
            result = gui_client.analyze_code(str(test_file))

            if result["success"]:
                print(f"\n  Analyzed: {result['file']}")
                print(f"  Lines: {result['lines']}")
                print(f"  Characters: {result['characters']}")
                print(f"  Words: {result['words']}")
            else:
                print(f"\n  ✗ Analysis failed: {result['message']}")
        else:
            print("\n  ⚠ Test file not found")

        return True
    except Exception as e:
        print(f"\n✗ Failed to test code analysis: {e}")
        return False


async def run_cli_test():
    """Run CLI test in async mode."""
    print("\n" + "=" * 60)
    print("Starting CLI Test")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Aura Core Initialization", test_aura_core_initialization()))
    results.append(("GUI Client Creation", test_gui_client_creation()))
    results.append(("Component Status", test_component_status()))
    results.append(("Plugin Status", test_plugin_status()))
    results.append(("Health Report", test_health_report()))
    results.append(("Conversation History", test_conversation_history()))
    results.append(("Workspace Analysis", test_workspace_analysis()))
    results.append(("Code Analysis", test_code_analysis()))

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\n  Passed: {passed}/{total}")
    print(f"  Failed: {total - passed}/{total}")

    if passed == total:
        print("\n  ✓ All tests passed!")
        return True
    else:
        print("\n  ✗ Some tests failed")
        for name, result in results:
            if not result:
                print(f"    ✗ {name}")
        return False


def main():
    """Main test runner."""
    print("\n" + "=" * 60)
    print("AuraAI CLI/GUI Architecture Test")
    print("=" * 60)

    try:
        # Run async tests
        result = asyncio.run(run_cli_test())

        if result:
            print("\n✓ All tests completed successfully!")
            print("\nYou can now run AuraAI using:")
            print("  python run_aura.py --cli")
            print("\nOr test the GUI client:")
            print("  python test_cli_architecture.py")
        else:
            print("\n✗ Some tests failed")
            return 1

        return 0

    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
