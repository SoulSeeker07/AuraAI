"""Test all CLI non-interactive commands."""
import asyncio
import sys
from pathlib import Path

# Add paths
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(1, str(SRC_DIR))

from clients.cli_client import CLIClient
from core.aura_core import AuraCore

async def test_commands():
    """Test all non-interactive CLI commands."""
    print("=" * 80)
    print("TESTING CLI NON-INTERACTIVE COMMANDS")
    print("=" * 80)

    # Initialize AuraCore
    aura_core = AuraCore()
    client = CLIClient(aura_core)

    # Test 1: Status
    print("\n1. Testing 'status' command...")
    await client.process_command('status')

    # Test 2: Knowledge stats
    print("\n2. Testing 'knowledge' command...")
    await client.process_command('knowledge')

    # Test 3: Workspace stats
    print("\n3. Testing 'workspace' command...")
    await client.process_command('workspace')

    # Test 4: Plugins status
    print("\n4. Testing 'plugins' command...")
    await client.process_command('plugins')

    # Test 5: Tasks status
    print("\n5. Testing 'tasks' command...")
    await client.process_command('tasks')

    # Test 6: History
    print("\n6. Testing 'history' command...")
    await client.process_command('history')

    # Test 7: Workflow
    print("\n7. Testing 'workflow' command...")
    await client.process_command('workflow')

    # Test 8: Agents
    print("\n8. Testing 'agents' command...")
    await client.process_command('agents')

    # Test 9: Engineering
    print("\n9. Testing 'engineering' command...")
    await client.process_command('engineering')

    # Test 10: Doctor
    print("\n10. Testing 'doctor' command...")
    await client.process_command('doctor')

    # Test 11: Graph
    print("\n11. Testing 'graph' command...")
    await client.process_command('graph')

    # Test 12: Help
    print("\n12. Testing 'help' command...")
    await client.process_command('help')

    # Test 13: Memory subcommands
    print("\n13. Testing 'memory:clear' command...")
    await client.process_command('memory:clear')

    # Test 14: Knowledge subcommands
    print("\n14. Testing 'knowledge:clear' command...")
    await client.process_command('knowledge:clear')

    # Test 15: Workspace subcommands
    print("\n15. Testing 'workspace:scan' command...")
    await client.process_command('workspace:scan')

    # Test 16: Plugins subcommands
    print("\n16. Testing 'plugins:load' command...")
    await client.process_command('plugins:load desktop')

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)

    # Shutdown
    await aura_core.shutdown()

if __name__ == "__main__":
    asyncio.run(test_commands())
