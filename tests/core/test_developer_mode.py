"""
Unit Tests for Developer Mode Explicit Trigger & Telemetry
Location: tests/core/test_developer_mode.py
"""

from unittest.mock import MagicMock

import pytest

from brain.aura_brain import AuraBrain

import pytest

@pytest.mark.skip(reason="Developer mode was removed from AuraBrain in M20.5 refactor")
def test_developer_mode_explicit_triggers():
    mock_memory = MagicMock()
    mock_provider = MagicMock()
    mock_tool_router = MagicMock()
    mock_workspace = MagicMock()
    mock_response = MagicMock()
    brain = AuraBrain(
        workspace_manager=mock_workspace,
        tool_router=mock_tool_router,
        response_coordinator=mock_response,
        enable_routing=False,
    )

    assert brain.developer_mode is False

    # Off-query while OFF informs user Developer Mode is disabled
    res_off = brain._handle_worker_control_command("why", 0.0, "conv_1")
    assert res_off is not None
    assert "Developer Mode is disabled" in res_off.text

    # Enable Developer Mode
    res_start = brain._handle_worker_control_command(
        "start Developer Mode", 0.0, "conv_1"
    )
    assert res_start is not None
    assert "Developer Mode Enabled" in res_start.text
    assert brain.developer_mode is True

    # "why" command
    res_why = brain._handle_worker_control_command("why", 0.0, "conv_1")
    assert res_why is not None
    assert "Decision Trace" in res_why.text

    # "inspect" command
    res_inspect = brain._handle_worker_control_command("inspect", 0.0, "conv_1")
    assert res_inspect is not None
    assert "Current Runtime" in res_inspect.text

    # "watch" command
    res_watch = brain._handle_worker_control_command("watch workers", 0.0, "conv_1")
    assert res_watch is not None
    assert "[Watch Workers]" in res_watch.text

    # Disable Developer Mode
    res_stop = brain._handle_worker_control_command(
        "stop Developer Mode", 0.0, "conv_1"
    )
    assert res_stop is not None
    assert "Developer Mode Disabled" in res_stop.text
    assert brain.developer_mode is False

    # Query after stopping returns disabled notification
    res_off_again = brain._handle_worker_control_command("why", 0.0, "conv_1")
    assert res_off_again is not None
    assert "Developer Mode is disabled" in res_off_again.text
