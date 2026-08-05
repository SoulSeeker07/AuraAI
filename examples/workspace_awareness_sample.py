"""
Sample usage for Workspace Awareness.

This file demonstrates how to use Aura's workspace awareness features.
Run this file to see workspace context in action.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.workspace import PlatformType, WorkspaceManager, WorkspaceState


async def demo_basic_workspace_state():
    """Demonstrate basic workspace state usage"""
    print("=" * 60)
    print("DEMO 1: Basic Workspace State")
    print("=" * 60)

    # Create a workspace state
    state = WorkspaceState(platform=PlatformType.WINDOWS)

    print(f"Platform: {state.platform}")
    print(f"Has active window: {state.has_active_window}")
    print(f"Has active project: {state.has_active_project}")
    print(f"Open files: {len(state.open_files)}")
    print(f"Running apps: {len(state.running_apps)}")


async def demo_workspace_manager():
    """Demonstrate WorkspaceManager usage"""
    print("\n" + "=" * 60)
    print("DEMO 2: Workspace Manager")
    print("=" * 60)

    # Create workspace manager
    manager = WorkspaceManager(
        enabled_features={
            "active_window": False,
            "project_detection": False,
            "git": False,
            "clipboard": False,
            "running_apps": False,
            "terminal": False,
        }
    )

    print(f"Workspace manager created: {manager is not None}")
    print(f"State initialized: {manager.state is not None}")

    # Add an open file
    await manager.add_open_file("src/workspace/models.py", modified=True)
    print(f"Added open file: {manager.state.open_files[0].name}")

    # Remove a file
    await manager.remove_open_file("src/workspace/models.py")
    print(f"Files remaining: {len(manager.state.open_files)}")

    # Get context summary
    summary = manager.get_context_summary()
    print(f"Context summary length: {len(summary)} chars")


async def demo_running_apps():
    """Demonstrate running applications monitoring"""
    print("\n" + "=" * 60)
    print("DEMO 3: Running Applications")
    print("=" * 60)

    from src.workspace.running_apps import RunningAppsMonitor

    monitor = RunningAppsMonitor()
    apps = await monitor.get_running_apps()

    print(f"Total running apps: {len(apps)}")

    # Filter for editors
    editors = await monitor.get_editor_apps()
    print(f"Editor apps: {len(editors)}")
    for app in editors[:5]:  # Show first 5
        print(f"  - {app.name} ({app.process_name})")

    # Filter for browsers
    browsers = await monitor.get_browser_apps()
    print(f"Browser apps: {len(browsers)}")
    for app in browsers[:5]:
        print(f"  - {app.name} ({app.process_name})")

    # Find foreground app
    foreground = await monitor.get_foreground_app()
    if foreground:
        print(f"Foreground app: {foreground.name} ({foreground.process_name})")


async def demo_clipboard():
    """Demonstrate clipboard monitoring"""
    print("\n" + "=" * 60)
    print("DEMO 4: Clipboard")
    print("=" * 60)

    from src.workspace.clipboard_monitor import ClipboardMonitor

    monitor = ClipboardMonitor(poll_interval=0.5)

    # Get current clipboard
    context = await monitor.get_clipboard()
    if context:
        print(f"Clipboard content: {context.text[:50]}...")
        print(f"Is code: {context.is_code}")
        print(f"Is text: {context.is_text}")
    else:
        print("Clipboard is empty")

    # Set some test content
    await monitor.set_clipboard("Hello, World!", is_code=False)
    print("Set clipboard: 'Hello, World!'")

    # Try with code
    test_code = """def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)"""
    await monitor.set_clipboard(test_code, is_code=True)
    print("Set clipboard (code snippet)")

    # Check again
    context = await monitor.get_clipboard()
    if context and context.is_code:
        print(f"Detected code type: {context.code_type}")


async def demo_terminal_context():
    """Demonstrate terminal context monitoring"""
    print("\n" + "=" * 60)
    print("DEMO 5: Terminal Context")
    print("=" * 60)

    from src.workspace.terminal_context import get_terminal_monitor

    monitor = get_terminal_monitor()

    # Get terminal context
    context = await monitor.get_terminal_context()

    if context:
        print(f"Terminal type: {context.type}")
        print(f"Working directory: {context.working_directory}")
        print(f"Has current command: {monitor._current_command is not None}")
        print(f"Running commands: {len(monitor._running_commands)}")

        if monitor._current_command:
            print(f"Current command: {monitor._current_command}")

        if monitor._last_command_output:
            print(f"Command output length: {len(monitor._last_command_output)} chars")

    else:
        print("No terminal context available (not running in terminal)")

    # Test command tracking
    print("\nTesting command tracking...")
    await monitor.set_current_command("npm install")
    await monitor.add_running_command("npm install")
    await monitor.add_running_command("npm test")
    await monitor.add_running_command("python --version")

    print(f"Current command: {monitor._current_command}")
    print(f"Running commands: {monitor._running_commands}")


async def demo_active_window():
    """Demonstrate active window monitoring"""
    print("\n" + "=" * 60)
    print("DEMO 6: Active Window")
    print("=" * 60)

    from src.workspace.active_window import ActiveWindowMonitor

    monitor = ActiveWindowMonitor()
    window = await monitor.get_active_window()

    if window:
        print(f"Window title: {window.title}")
        print(f"Application: {window.app_name}")
        print(f"Process: {window.process_name}")
        print(f"Is in workspace: {window.is_in_workspace}")

        if window.rect:
            print(f"Rectangle: {window.rect}")
    else:
        print("No active window found (script may be running in background)")


async def demo_project_detection():
    """Demonstrate project auto-detection"""
    print("\n" + "=" * 60)
    print("DEMO 7: Project Detection")
    print("=" * 60)

    from src.workspace.project_detector import ProjectDetector

    detector = ProjectDetector()

    # Detect project in AuraAI directory
    result = await detector.detect_current_project()

    if result and result.project:
        project = result.project
        print(f"Project name: {project.name}")
        print(f"Project path: {project.path}")
        print(f"Project type: {project.type}")

        if project.has_git:
            print(f"Git repository: {project.git_repo.repo_name}")
            print(f"Git branch: {project.git_repo.branch}")
            print(f"Is dirty: {project.git_repo.is_dirty}")

            if project.git_repo.modified_files:
                print(f"Modified files: {len(project.git_repo.modified_files)}")
                for file in project.git_repo.modified_files[:5]:
                    print(f"  - {file}")
    else:
        print("No project detected")


async def demo_git_context():
    """Demonstrate git context"""
    print("\n" + "=" * 60)
    print("DEMO 8: Git Context")
    print("=" * 60)

    from src.workspace.git_context import GitContext

    git = GitContext()

    # Get git repository
    repo = await git.get_git_repo()
    if repo:
        print(f"Repository path: {repo.path}")
        print(f"Repository name: {repo.repo_name}")
        print(f"Branch: {repo.branch}")

        if repo.remote_url:
            print(f"Remote URL: {repo.remote_url}")

        print(f"Is dirty: {repo.is_dirty}")

        if repo.modified_files:
            print(f"Modified files: {len(repo.modified_files)}")
            for file in repo.modified_files[:5]:
                print(f"  - {file}")

        # Get recent commits
        commits = await git.get_recent_commits(count=3)
        print("\nRecent commits:")
        for commit in commits:
            print(f"  {commit['hash'][:8]}: {commit['message'][:50]}...")

    else:
        print("Not in a git repository")


async def demo_context_summary():
    """Demonstrate context summary generation"""
    print("\n" + "=" * 60)
    print("DEMO 9: Context Summary")
    print("=" * 60)

    # Create workspace manager
    manager = WorkspaceManager()

    # Add some test data
    await manager.add_open_file(
        "src/workspace/models.py", modified=True, line_number=10
    )
    await manager.add_open_file("src/workspace/workspace_manager.py", modified=False)
    await manager.add_open_file("README.md", modified=True)

    # Get context summary
    summary = manager.get_context_summary()

    print("Context Summary:")
    print("-" * 60)
    print(summary)
    print("-" * 60)

    print(f"\nSummary length: {len(summary)} characters")


async def main():
    """Run all demonstrations"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Aura Workspace Awareness Demo" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        await demo_basic_workspace_state()
        await demo_workspace_manager()
        await demo_running_apps()
        await demo_clipboard()
        await demo_terminal_context()
        await demo_active_window()
        await demo_project_detection()
        await demo_git_context()
        await demo_context_summary()

        print("\n" + "=" * 60)
        print("All demonstrations completed!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nError running demo: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
