import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from brain.conversation_engine import ConversationEngine, ForegroundMatch, FILE_CONTAINER_APPS
from brain.models import Intent
from routing.app_context_router import AppContext
from vision.grounding_engine import GroundedTarget
from Memory import Memory
from ai.provider_manager import ProviderManager


@pytest.fixture
def mock_engine(tmp_path):
    memory = Memory(db_path=tmp_path / "Memory.db", chat_log_path=tmp_path / "ChatLog.json")
    pm = ProviderManager()
    
    mock_aura_core = MagicMock()
    engine = ConversationEngine(
        memory=memory,
        provider_manager=pm,
        aura_core=mock_aura_core,
    )
    return engine, mock_aura_core


@pytest.mark.asyncio
async def test_foreground_file_gate_window_title_match(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="antigravity.exe",
        window_title="agent.md - AuraAI - Antigravity IDE",
        window_handle=12345,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    with patch("core.backends.adapters.desktop_backend._force_foreground") as mock_force_fg, \
         patch("tools.file_service.FileService.find_and_open") as mock_find_and_open:
        res = await engine.process("open agent.md")
        
        # FileService.find_and_open must NOT be called
        assert mock_find_and_open.call_count == 0
        # Canonical _force_foreground MUST be called with window_handle
        assert mock_force_fg.call_count == 1
        mock_force_fg.assert_called_once_with(12345)
        assert "already open in antigravity.exe" in res.text
        assert "switched to it" in res.text


@pytest.mark.asyncio
async def test_foreground_file_gate_grounded_tier1_dom_match(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="chrome.exe",
        window_title="Google Chrome",
        window_handle=12346,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    # Mock Playwright DOM element handle
    mock_dom_element = MagicMock()
    grounded_target = GroundedTarget(
        label="agent.md",
        center=(100, 200),
        element_handle=mock_dom_element,
        source_tier="tier1_dom",
        app_name="chrome.exe",
    )
    mock_aura.grounding_engine.resolve_foreground_only.return_value = grounded_target
    
    with patch("tools.file_service.FileService.find_and_open") as mock_find_and_open:
        res = await engine.process("open agent.md")
        
        assert mock_find_and_open.call_count == 0
        # Playwright DOM click MUST be fired directly on element handle
        assert mock_dom_element.click.call_count == 1
        assert "Found 'agent.md' already open in chrome.exe" in res.text


@pytest.mark.asyncio
async def test_foreground_file_gate_grounded_tier1_a11y_match(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="code.exe",
        window_title="Visual Studio Code",
        window_handle=12347,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    # Mock UIA element handle with click_input
    mock_uia_element = MagicMock()
    grounded_target = GroundedTarget(
        label="agent.md",
        center=(100, 200),
        element_handle=mock_uia_element,
        source_tier="tier1_a11y",
        app_name="code.exe",
    )
    mock_aura.grounding_engine.resolve_foreground_only.return_value = grounded_target
    
    with patch("tools.file_service.FileService.find_and_open") as mock_find_and_open:
        res = await engine.process("open agent.md")
        
        assert mock_find_and_open.call_count == 0
        # UIA element click_input MUST be fired
        assert mock_uia_element.click_input.call_count == 1
        assert "Found 'agent.md' already open in code.exe" in res.text


@pytest.mark.asyncio
async def test_no_container_app_focused_falls_back_to_file_service(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="cmd.exe",
        window_title="Command Prompt",
        window_handle=12348,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    with patch("tools.file_service.FileService.get_instance") as mock_fs_instance:
        mock_fs = MagicMock()
        mock_fs.find_and_open.return_value = (True, "Opened notes.txt", "/path/to/notes.txt")
        mock_fs_instance.return_value = mock_fs
        
        res = await engine.process("open notes.txt")
        
        assert mock_fs.find_and_open.call_count == 1
        assert "Opened notes.txt" in res.text


@pytest.mark.asyncio
async def test_focus_failure_returns_none_and_falls_back_to_file_service(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="antigravity.exe",
        window_title="agent.md - AuraAI - Antigravity IDE",
        window_handle=12349,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    # Simulate _force_foreground raising an OS error / returning False
    with patch("core.backends.adapters.desktop_backend._force_foreground", side_effect=RuntimeError("AttachThreadInput denied")), \
         patch("tools.file_service.FileService.get_instance") as mock_fs_instance:
        mock_fs = MagicMock()
        mock_fs.find_and_open.return_value = (True, "Opened agent.md via fallback", "/path/to/agent.md")
        mock_fs_instance.return_value = mock_fs
        
        # Method _try_resolve_in_foreground must return None on failure
        match = engine._try_resolve_in_foreground("agent.md")
        assert match is None
        
        # Engine process must fall back to FileService.find_and_open
        res = await engine.process("open agent.md")
        assert mock_fs.find_and_open.call_count == 1
        assert "Opened agent.md via fallback" in res.text


@pytest.mark.asyncio
async def test_click_failure_returns_none_and_falls_back_to_file_service(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="chrome.exe",
        window_title="Google Chrome",
        window_handle=12350,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    # Mock DOM element handle whose click raises an Exception
    mock_dom_element = MagicMock()
    mock_dom_element.click.side_effect = RuntimeError("DOM element detached")
    grounded_target = GroundedTarget(
        label="agent.md",
        center=(100, 200),
        element_handle=mock_dom_element,
        source_tier="tier1_dom",
        app_name="chrome.exe",
    )
    mock_aura.grounding_engine.resolve_foreground_only.return_value = grounded_target
    
    with patch("tools.file_service.FileService.get_instance") as mock_fs_instance:
        mock_fs = MagicMock()
        mock_fs.find_and_open.return_value = (True, "Opened agent.md via fallback", "/path/to/agent.md")
        mock_fs_instance.return_value = mock_fs
        
        match = engine._try_resolve_in_foreground("agent.md")
        assert match is None
        
        res = await engine.process("open agent.md")
        assert mock_fs.find_and_open.call_count == 1
        assert "Opened agent.md via fallback" in res.text


@pytest.mark.asyncio
async def test_uia_stale_click_failure_falls_back_to_file_service(mock_engine):
    """
    Ensure that if a grounded UIA element is stale/destroyed and click_input raises,
    ConversationEngine catches the error, marks action_ok=False, and safely falls
    back to FileService.find_and_open().
    """
    engine, mock_aura = mock_engine

    app_ctx = AppContext(
        app_name="code.exe",
        window_title="Visual Studio Code",
        window_handle=12351,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx

    mock_uia_element = MagicMock()
    mock_uia_element.click_input.side_effect = RuntimeError("Element handle is stale / Window closed")
    grounded_target = GroundedTarget(
        label="agent.md",
        center=(100, 200),
        element_handle=mock_uia_element,
        source_tier="tier1_a11y",
        app_name="code.exe",
    )
    mock_aura.grounding_engine.resolve_foreground_only.return_value = grounded_target

    with patch("tools.file_service.FileService.get_instance") as mock_fs_instance:
        mock_fs = MagicMock()
        mock_fs.find_and_open.return_value = (True, "Opened agent.md via fallback", "/path/to/agent.md")
        mock_fs_instance.return_value = mock_fs

        match = engine._try_resolve_in_foreground("agent.md")
        assert match is None

        res = await engine.process("open agent.md")
        assert mock_fs.find_and_open.call_count == 1
        assert "Opened agent.md via fallback" in res.text

