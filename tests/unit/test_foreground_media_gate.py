import pytest
from unittest.mock import MagicMock, patch
from brain.conversation_engine import ConversationEngine, _extract_media_target
from brain.models import Intent, ConversationResult
from routing.app_context_router import AppContext
from vision.grounding_engine import GroundedTarget


def test_extract_media_target_helper():
    assert _extract_media_target("play GTA 6 on youtube") == "GTA 6"
    assert _extract_media_target("watch GTA 6 trailer in chrome") == "GTA 6 trailer"
    assert _extract_media_target("listen to lo-fi beats on spotify") == "lo-fi beats"
    assert _extract_media_target("play that video") == "that video"
    assert _extract_media_target("open video funny cats") == "funny cats"


@pytest.fixture
def mock_engine(tmp_path):
    memory = MagicMock()
    provider_mgr = MagicMock()
    engine = ConversationEngine(memory=memory, provider_manager=provider_mgr)
    mock_aura = MagicMock()
    engine.aura_core = mock_aura
    return engine, mock_aura


@pytest.mark.asyncio
async def test_foreground_media_gate_browser_match_success(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="chrome.exe",
        window_title="YouTube - GTA 6 Trailer - Google Chrome",
        window_handle=23451,
        is_browser=True,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    # Mock DOM grounded target
    mock_dom_element = MagicMock()
    grounded_target = GroundedTarget(
        label="GTA 6 Trailer",
        center=(400, 300),
        element_handle=mock_dom_element,
        source_tier="tier1_dom",
        app_name="chrome.exe",
    )
    mock_aura.grounding_engine.resolve.return_value = grounded_target
    
    with patch("browser.run_browser_goal.run_browser_goal") as mock_run_browser_goal:
        res = await engine.process("play GTA 6 on youtube")
        
        # run_browser_goal MUST NOT be called when resolved in foreground
        assert mock_run_browser_goal.call_count == 0
        assert mock_dom_element.click.call_count == 1
        assert "Found 'GTA 6 Trailer' already open in chrome.exe" in res.text


@pytest.mark.asyncio
async def test_foreground_media_gate_target_not_found_falls_back_to_run_browser_goal(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="chrome.exe",
        window_title="Google Chrome",
        window_handle=23452,
        is_browser=True,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    mock_aura.grounding_engine.resolve.return_value = None
    
    with patch("browser.run_browser_goal.run_browser_goal") as mock_run_browser_goal:
        mock_run_browser_goal.return_value = {
            "status": "SUCCESS",
            "summary": "Searched and played GTA 6 trailer in new browser session",
            "url": "https://youtube.com/results",
            "steps": [],
        }
        res = await engine.process("play GTA 6 on youtube")
        
        assert mock_run_browser_goal.call_count == 1
        assert "Searched and played GTA 6 trailer" in res.text


@pytest.mark.asyncio
async def test_non_browser_foreground_short_circuits_grounding_resolve(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="code.exe",
        window_title="Visual Studio Code",
        window_handle=23453,
        is_browser=False,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    with patch("browser.run_browser_goal.run_browser_goal") as mock_run_browser_goal:
        mock_run_browser_goal.return_value = {
            "status": "SUCCESS",
            "summary": "Searched and played GTA 6",
            "url": "https://youtube.com",
            "steps": [],
        }
        res = await engine.process("play GTA 6 on youtube")
        
        # grounding_engine.resolve MUST NOT be invoked when foreground app is not a browser
        assert mock_aura.grounding_engine.resolve.call_count == 0
        assert mock_run_browser_goal.call_count == 1


@pytest.mark.asyncio
async def test_media_click_failure_returns_none_and_falls_back_to_run_browser_goal(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="chrome.exe",
        window_title="YouTube - Google Chrome",
        window_handle=23454,
        is_browser=True,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    # Mock DOM element handle whose click raises an Exception
    mock_dom_element = MagicMock()
    mock_dom_element.click.side_effect = RuntimeError("DOM element detached")
    grounded_target = GroundedTarget(
        label="GTA 6",
        center=(400, 300),
        element_handle=mock_dom_element,
        source_tier="tier1_dom",
        app_name="chrome.exe",
    )
    mock_aura.grounding_engine.resolve.return_value = grounded_target
    
    with patch("browser.run_browser_goal.run_browser_goal") as mock_run_browser_goal:
        mock_run_browser_goal.return_value = {
            "status": "SUCCESS",
            "summary": "Played GTA 6 via fallback browser session",
            "url": "https://youtube.com",
            "steps": [],
        }
        
        match = engine._try_resolve_media_in_foreground("play GTA 6 on youtube", "GTA 6")
        assert match is None
        
        res = await engine.process("play GTA 6 on youtube")
        assert mock_run_browser_goal.call_count == 1
        assert "Played GTA 6 via fallback browser session" in res.text


@pytest.mark.asyncio
async def test_non_media_autonomous_browser_goal_bypasses_media_gate(mock_engine):
    engine, mock_aura = mock_engine
    
    app_ctx = AppContext(
        app_name="chrome.exe",
        window_title="Amazon.in - Google Chrome",
        window_handle=23455,
        is_browser=True,
    )
    mock_aura.app_context_router.detect_current_app.return_value = app_ctx
    
    with patch("browser.run_browser_goal.run_browser_goal") as mock_run_browser_goal:
        mock_run_browser_goal.return_value = {
            "status": "SUCCESS",
            "summary": "Added running shoes to cart",
            "url": "https://amazon.in",
            "steps": [],
        }
        res = await engine.process("add running shoes to cart on amazon")
        
        # grounding_engine.resolve MUST NOT be invoked for non-media goals
        assert mock_aura.grounding_engine.resolve.call_count == 0
        assert mock_run_browser_goal.call_count == 1
