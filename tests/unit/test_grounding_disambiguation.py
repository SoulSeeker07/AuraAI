"""
Unit tests covering candidate disambiguation & ratio-gap ambiguity detection for Items 28 & 29.
"""

from unittest.mock import MagicMock, patch
import pytest

from vision.grounding_engine import GroundedTarget, GroundingEngine


def test_grounding_engine_detects_candidate_ambiguity_when_ratio_gap_small():
    engine = GroundingEngine()

    bb1 = MagicMock()
    bb1.left = 100
    bb1.top = 100
    bb1.width = 200
    bb1.height = 50
    bb1.right = 300
    bb1.bottom = 150

    bb2 = MagicMock()
    bb2.left = 100
    bb2.top = 200
    bb2.width = 200
    bb2.height = 50
    bb2.right = 300
    bb2.bottom = 250

    node1 = MagicMock()
    node1.name = "GTA 6 Trailer Part 1"
    node1.bounding_box = bb1
    node1.children = []

    node2 = MagicMock()
    node2.name = "GTA 6 Trailer Part 2"
    node2.bounding_box = bb2
    node2.children = []

    tree = MagicMock()
    tree.name = "Root"
    tree.children = [node1, node2]

    mock_adapter = MagicMock()
    mock_adapter.is_available.return_value = True
    mock_adapter.find_elements.return_value = []
    mock_adapter.get_tree.return_value = tree

    mock_uia_mgr = MagicMock()
    mock_uia_mgr.adapter = mock_adapter

    mock_registry = MagicMock()
    mock_registry.get_manager.return_value = mock_uia_mgr

    app_ctx = MagicMock(spec=["app_name"])
    app_ctx.app_name = "code.exe"

    with patch("desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance", return_value=mock_registry):
        target = engine.resolve("GTA 6 Trailer Part", app_context=app_ctx)
        assert target is not None
        assert target.is_ambiguous is True
        assert target.confidence_gap < 0.05
        assert len(target.candidate_options) >= 2


def test_grounding_engine_single_match_when_ratio_gap_large():
    engine = GroundingEngine()

    bb1 = MagicMock()
    bb1.left = 100
    bb1.top = 100
    bb1.width = 200
    bb1.height = 50
    bb1.right = 300
    bb1.bottom = 150

    bb2 = MagicMock()
    bb2.left = 100
    bb2.top = 200
    bb2.width = 200
    bb2.height = 50
    bb2.right = 300
    bb2.bottom = 250

    node1 = MagicMock()
    node1.name = "GTA 6 Trailer (Official)"
    node1.bounding_box = bb1
    node1.children = []

    node2 = MagicMock()
    node2.name = "Unrelated Video Tutorial"
    node2.bounding_box = bb2
    node2.children = []

    tree = MagicMock()
    tree.name = "Root"
    tree.children = [node1, node2]

    mock_adapter = MagicMock()
    mock_adapter.is_available.return_value = True
    mock_adapter.find_elements.return_value = []
    mock_adapter.get_tree.return_value = tree

    mock_uia_mgr = MagicMock()
    mock_uia_mgr.adapter = mock_adapter

    mock_registry = MagicMock()
    mock_registry.get_instance.return_value = mock_registry
    mock_registry.get_manager.return_value = mock_uia_mgr

    app_ctx = MagicMock(spec=["app_name"])
    app_ctx.app_name = "code.exe"

    with patch("desktop.native.managers.native_manager_registry.NativeManagerRegistry.get_instance", return_value=mock_registry):
        target = engine.resolve("GTA 6 Trailer (Official)", app_context=app_ctx)
        assert target is not None
        assert target.is_ambiguous is False
        assert target.confidence_gap >= 0.05


def test_foreground_media_gate_ambiguous_candidate_prompts_user_clarification():
    from brain.conversation_engine import ConversationEngine

    mock_core = MagicMock()
    mock_app_context = MagicMock(is_browser=True, app_name="chrome.exe")
    mock_core.app_context_router.detect_current_app.return_value = mock_app_context

    ambiguous_target = GroundedTarget(
        label="GTA 6 Official Trailer",
        center=(200, 200),
        is_ambiguous=True,
        confidence_gap=0.02,
        candidate_options=[
            GroundedTarget(label="GTA 6 Official Trailer", center=(200, 200)),
            GroundedTarget(label="GTA 6 Trailer Reaction", center=(200, 300)),
        ],
    )
    mock_core.grounding_engine.resolve.return_value = ambiguous_target

    engine = ConversationEngine(aura_core=mock_core, memory=MagicMock(), provider_manager=MagicMock())
    match = engine._try_resolve_media_in_foreground("play GTA 6 trailer", "GTA 6 trailer")
    assert match is not None
    assert match.resolution_path == "ambiguous_clarification"
    assert "multiple matching media items" in match.message
    assert "1st or 2nd" in match.message


def test_foreground_file_gate_ambiguous_candidate_prompts_user_clarification():
    from brain.conversation_engine import ConversationEngine

    mock_core = MagicMock()
    mock_app_context = MagicMock(app_name="code.exe", window_handle=12345, window_title="Workspace")
    mock_core.app_context_router.detect_current_app.return_value = mock_app_context

    ambiguous_target = GroundedTarget(
        label="main.py",
        center=(200, 200),
        is_ambiguous=True,
        confidence_gap=0.01,
        candidate_options=[
            GroundedTarget(label="main.py", center=(200, 200)),
            GroundedTarget(label="main_test.py", center=(200, 300)),
        ],
    )
    mock_core.grounding_engine.resolve_foreground_only.return_value = ambiguous_target

    engine = ConversationEngine(aura_core=mock_core, memory=MagicMock(), provider_manager=MagicMock())
    match = engine._try_resolve_in_foreground("main.py")
    assert match is not None
    assert match.resolution_path == "ambiguous_clarification"
    assert "multiple matching items open" in match.message
