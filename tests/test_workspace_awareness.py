"""
Comprehensive tests for Workspace Awareness module.

Tests all workspace sensors and the WorkspaceManager.
"""

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from workspace import (
    ActiveWindow,
    ClipboardContext,
    CurrentProject,
    GitRepository,
    OpenFile,
    PlatformType,
    ProjectType,
    RunningApplication,
    TerminalContext,
    TerminalType,
    WorkspaceManager,
    WorkspaceState,
)
from workspace.active_window import ActiveWindowMonitor
from workspace.clipboard_monitor import ClipboardMonitor
from workspace.git_context import GitContext
from workspace.project_detector import ProjectDetector
from workspace.running_apps import RunningAppsMonitor


@pytest.fixture
def workspace_manager(tmp_path):
    """Create a temporary WorkspaceManager for testing"""
    return WorkspaceManager(
        data_path=tmp_path / "test_workspace.json",
        enabled_features={
            "active_window": False,  # Disable for faster tests
            "project_detection": False,
            "git": False,
            "clipboard": False,
            "running_apps": False,
            "terminal": False,
        },
    )


@pytest.fixture
def analyzer():
    """Create a project detector for testing"""
    return ProjectDetector()


@pytest.mark.asyncio
class TestWorkspaceStateModels:
    """Test workspace state models"""

    def test_active_window_creation(self):
        """Test ActiveWindow model creation"""
        window = ActiveWindow(
            title="Test Window", app_name="TestApp", process_name="testapp.exe"
        )

        assert window.title == "Test Window"
        assert window.app_name == "TestApp"
        assert window.process_name == "testapp.exe"
        assert window.is_in_workspace is True

    def test_active_window_with_rect(self):
        """Test ActiveWindow with window rectangle"""
        window = ActiveWindow(
            title="Test Window",
            app_name="TestApp",
            process_name="testapp.exe",
            rect={"x": 100, "y": 200, "width": 800, "height": 600},
        )

        assert window.is_in_workspace is True
        assert window.rect == {"x": 100, "y": 200, "width": 800, "height": 600}

    def test_active_window_out_of_bounds(self):
        """Test ActiveWindow outside workspace bounds"""
        window = ActiveWindow(
            title="Test Window",
            app_name="TestApp",
            process_name="testapp.exe",
            rect={"x": -100, "y": -200, "width": 800, "height": 600},
        )

        assert window.is_in_workspace is False

    def test_current_project_creation(self):
        """Test CurrentProject model creation"""
        project = CurrentProject(
            path="/test/project", name="TestProject", type=ProjectType.PYTHON
        )

        assert project.path == "/test/project"
        assert project.name == "TestProject"
        assert project.type == ProjectType.PYTHON
        assert project.has_git is False
        assert project.is_dirty is False

    def test_current_project_with_git(self):
        """Test CurrentProject with git repository"""
        git_repo = GitRepository(
            path="/test/project", branch="main", commit_hash="abc123"
        )

        project = CurrentProject(
            path="/test/project",
            name="TestProject",
            type=ProjectType.PYTHON,
            git_repo=git_repo,
        )

        assert project.has_git is True
        assert project.git_repo is not None
        assert project.git_repo.branch == "main"

    def test_workspace_state_initialization(self):
        """Test WorkspaceState initialization"""
        state = WorkspaceState(platform=PlatformType.WINDOWS)

        assert state.platform == PlatformType.WINDOWS
        assert state.active_window is None
        assert state.current_project is None
        assert state.open_files == []
        assert len(state.running_apps) == 0

    def test_workspace_state_properties(self):
        """Test WorkspaceState properties"""
        state = WorkspaceState()

        # Create test data
        window = ActiveWindow(
            title="Test Window", app_name="TestApp", process_name="testapp.exe"
        )
        project = CurrentProject(path="/test", name="Test", type=ProjectType.PYTHON)

        state.active_window = window
        state.current_project = project

        assert state.has_active_window is True
        assert state.has_active_project is True

    def test_git_repository_creation(self):
        """Test GitRepository model creation"""
        repo = GitRepository(
            path="/test",
            branch="main",
            modified_files=["file1.py", "file2.py"],
            is_dirty=True,
        )

        assert repo.path == "/test"
        assert repo.branch == "main"
        assert len(repo.modified_files) == 2
        assert repo.is_dirty is True

    def test_git_repository_repo_name(self):
        """Test GitRepository repo_name property"""
        repo = GitRepository(path="/test/project", branch="main")

        assert repo.repo_name == "project"


@pytest.mark.asyncio
class TestWorkspaceManager:
    """Test WorkspaceManager class"""

    async def test_workspace_manager_initialization(self, workspace_manager):
        """Test WorkspaceManager initialization"""
        assert workspace_manager is not None
        assert workspace_manager.state is not None
        assert workspace_manager.enabled_features is not None

    async def test_workspace_manager_enable_disable_feature(self, workspace_manager):
        """Test enabling/disabling features"""
        assert workspace_manager.is_feature_enabled("active_window") is False
        workspace_manager.enable_feature("active_window", True)
        assert workspace_manager.is_feature_enabled("active_window") is True

    async def test_workspace_manager_force_update(self, workspace_manager):
        """Test force update method"""
        await workspace_manager.force_update()
        assert workspace_manager.state.last_updated is not None

    async def test_workspace_manager_update_timestamp(self, workspace_manager):
        """Test timestamp update"""
        state = workspace_manager.state
        state.last_updated = datetime.now()

        state.update_timestamp()

        assert state.last_updated > datetime.now() - asyncio.sleep(1)

    async def test_workspace_manager_add_open_file(self, workspace_manager):
        """Test adding an open file"""
        await workspace_manager.add_open_file("test.py", modified=True)

        assert len(workspace_manager.state.open_files) == 1
        assert workspace_manager.state.open_files[0].name == "test.py"
        assert workspace_manager.state.open_files[0].modified is True

    async def test_workspace_manager_remove_open_file(self, workspace_manager):
        """Test removing an open file"""
        await workspace_manager.add_open_file("test.py")
        await workspace_manager.remove_open_file("test.py")

        assert len(workspace_manager.state.open_files) == 0

    async def test_workspace_manager_context_summary(self, workspace_manager):
        """Test context summary generation"""
        await workspace_manager.add_open_file("test.py")

        summary = workspace_manager.get_context_summary()
        assert summary is not None
        assert "test.py" in summary


@pytest.mark.asyncio
class TestProjectDetector:
    """Test ProjectDetector class"""

    async def test_project_detector_initialization(self, analyzer):
        """Test ProjectDetector initialization"""
        assert analyzer is not None

    async def test_project_detector_no_project_in_aura_ai(self, analyzer):
        """Test detecting project in AuraAI directory"""
        result = await analyzer.detect_current_project(
            str(Path(__file__).parent.parent)
        )

        assert result is not None
        assert result.project is not None
        assert "AuraAI" in result.project.name
        assert result.project.type == ProjectType.PYTHON

    async def test_project_detector_at_root(self, analyzer):
        """Test detecting project at root directory"""
        result = await analyzer.detect_current_project()

        # Should detect some project (either AuraAI or parent)
        assert result is not None


@pytest.mark.asyncio
class TestGitContext:
    """Test GitContext class"""

    async def test_git_context_no_repo(self, tmp_path):
        """Test git context with no repository"""
        git_context = GitContext()

        result = await git_context.get_git_repo(str(tmp_path))
        assert result is None

    async def test_git_context_get_current_branch(self, analyzer):
        """Test getting current branch"""
        git_context = GitContext()

        # Check if AuraAI has git repo
        branch = await git_context.get_current_branch()

        # This will pass if AuraAI is in a git repo
        if branch:
            assert isinstance(branch, str)
            assert len(branch) > 0

    async def test_git_context_get_recent_commits(self, analyzer):
        """Test getting recent commits"""
        git_context = GitContext()

        commits = await git_context.get_recent_commits(count=3)

        if commits:
            assert isinstance(commits, list)
            for commit in commits:
                assert "hash" in commit
                assert "message" in commit

    async def test_git_context_get_modified_files(self, analyzer):
        """Test getting modified files"""
        git_context = GitContext()

        modified = await git_context.get_modified_files()

        if modified:
            assert isinstance(modified, list)


@pytest.mark.asyncio
class TestClipboardMonitor:
    """Test ClipboardMonitor class"""

    async def test_clipboard_monitor_initialization(self):
        """Test ClipboardMonitor initialization"""
        monitor = ClipboardMonitor(poll_interval=1)
        assert monitor.poll_interval == 1

    async def test_clipboard_monitor_get_clipboard(self, monitor):
        """Test getting clipboard content"""
        content = await monitor.get_clipboard()
        assert content is None or isinstance(content, ClipboardContext)

    async def test_clipboard_monitor_set_clipboard(self, monitor):
        """Test setting clipboard content"""
        await monitor.set_clipboard("Test content", is_code=True)
        content = await monitor.get_clipboard()

        assert content is not None
        assert content.text == "Test content"
        assert content.is_code is True

    async def test_clipboard_monitor_clear_clipboard(self, monitor):
        """Test clearing clipboard"""
        await monitor.set_clipboard("Test")
        await monitor.clear_clipboard()

        content = await monitor.get_clipboard()
        assert content is None


@pytest.mark.asyncio
class TestActiveWindowMonitor:
    """Test ActiveWindowMonitor class"""

    async def test_active_window_monitor_initialization(self):
        """Test ActiveWindowMonitor initialization"""
        monitor = ActiveWindowMonitor()
        assert monitor is not None

    async def test_active_window_monitor_get_active_window(self, monitor):
        """Test getting active window"""
        window = await monitor.get_active_window()

        # Will work on Windows
        if window:
            assert window.title is not None
            assert window.app_name is not None
            assert window.process_name is not None


@pytest.mark.asyncio
class TestRunningAppsMonitor:
    """Test RunningAppsMonitor class"""

    async def test_running_apps_monitor_initialization(self):
        """Test RunningAppsMonitor initialization"""
        monitor = RunningAppsMonitor()
        assert monitor is not None

    async def test_running_apps_monitor_get_running_apps(self, monitor):
        """Test getting running apps"""
        apps = await monitor.get_running_apps()

        assert isinstance(apps, list)
        for app in apps:
            assert isinstance(app, RunningApplication)

    async def test_running_apps_monitor_get_editor_apps(self, monitor):
        """Test getting editor apps"""
        apps = await monitor.get_editor_apps()

        assert isinstance(apps, list)

    async def test_running_apps_monitor_get_browser_apps(self, monitor):
        """Test getting browser apps"""
        apps = await monitor.get_browser_apps()

        assert isinstance(apps, list)

    async def test_running_apps_monitor_is_editor(self):
        """Test is_editor property"""
        app = RunningApplication(
            name="VS Code", process_name="code.exe", is_foreground=False
        )

        assert app.is_editor is True

    async def test_running_apps_monitor_is_browser(self):
        """Test is_browser property"""
        app = RunningApplication(
            name="Chrome", process_name="chrome.exe", is_foreground=False
        )

        assert app.is_browser is True


@pytest.mark.asyncio
class TestTerminalContext:
    """Test TerminalContext class"""

    async def test_terminal_context_monitor_initialization(self):
        """Test TerminalContextMonitor initialization"""
        monitor = get_terminal_monitor()
        assert monitor is not None

    async def test_terminal_context_monitor_get_terminal_context(self, monitor):
        """Test getting terminal context"""
        context = await monitor.get_terminal_context()

        # Will get context if running in terminal
        if context:
            assert isinstance(context, TerminalContext)
            assert context.working_directory is not None

    async def test_terminal_context_monitor_set_current_command(self, monitor):
        """Test setting current command"""
        await monitor.set_current_command("npm install")
        assert monitor._current_command == "npm install"

    async def test_terminal_context_monitor_add_running_command(self, monitor):
        """Test adding running command"""
        await monitor.add_running_command("npm install")
        await monitor.add_running_command("npm test")

        assert len(monitor._running_commands) == 2

    async def test_terminal_context_monitor_clear_commands(self, monitor):
        """Test clearing commands"""
        await monitor.add_running_command("npm install")
        await monitor.clear_running_commands()

        assert len(monitor._running_commands) == 0

    async def test_terminal_context_monitor_is_wsl(self, monitor):
        """Test is_wsl check"""
        await monitor.set_current_command("wsl --exec bash")
        await monitor.get_terminal_context()

        # May or may not be WSL depending on context
        is_wsl_result = monitor.is_wsl()
        # This is a reasonable check that returns False unless in WSL
        assert isinstance(is_wsl_result, bool)


def test_git_repository_clone_with_additional_fields():
    """Test GitRepository with additional fields"""
    import dataclasses

    # Create a GitRepository with all fields
    repo = GitRepository(
        path="/test/project",
        branch="main",
        remote_url="https://github.com/user/repo.git",
        commit_hash="abc123def456",
        modified_files=["file1.py"],
        uncommitted_changes=1,
        is_dirty=True,
    )

    assert repo.repo_name == "project"
    assert repo.uncommitted_changes == 1
    assert repo.is_dirty is True
    assert repo.remote_url == "https://github.com/user/repo.git"


def test_open_file_creation():
    """Test OpenFile model creation"""
    file = OpenFile(
        path="/test/project/test.py",
        name="test.py",
        modified=True,
        line_number=10,
        cursor_position=50,
    )

    assert file.path == "/test/project/test.py"
    assert file.name == "test.py"
    assert file.modified is True
    assert file.line_number == 10
    assert file.cursor_position == 50

    # Test hash
    assert hash(file) == hash(file.path)


def test_clipboard_context_with_code():
    """Test ClipboardContext with code"""
    context = ClipboardContext(
        text="def hello():\n    print('hello')",
        code="def hello():\n    print('hello')",
        is_code=True,
        is_text=True,
    )

    assert context.text == "def hello():\n    print('hello')"
    assert context.code == "def hello():\n    print('hello')"
    assert context.is_code is True
    assert context.has_content is True
