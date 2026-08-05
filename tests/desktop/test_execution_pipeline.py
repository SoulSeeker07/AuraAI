"""
Desktop Execution Pipeline - End-to-End Integration Test

Tests the full flow:
    Goal → Discovery → Registry → Pipeline → Verification → Diagnostics → DesktopResult

This test proves that the Phase 2A.6 architecture works end-to-end
with a MockManager. When Phase 2B begins, only the manager changes
(MockManager → real Win32 managers). The pipeline stays the same.

Run:
    python -m pytest tests/desktop/test_execution_pipeline.py -v
"""

import sys
import os
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest
from unittest.mock import MagicMock

from desktop.native.desktop_result import DesktopResult, DesktopStatus
from desktop.native.mock_manager import MockManager, MockWindowState
from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    ExecutionConfig,
    ExecutionStage,
)
from desktop.native.capability_registry import (
    CapabilityRegistry,
    CapabilityDescriptor,
    PermissionRequired,
    RiskLevel,
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_manager():
    """Create a fresh MockManager for each test."""
    return MockManager()


@pytest.fixture
def registry():
    """Create a fresh CapabilityRegistry for each test."""
    return CapabilityRegistry()


@pytest.fixture
def engine(mock_manager, registry):
    """Create a DesktopExecutionEngine with mock manager."""
    return DesktopExecutionEngine(
        manager=mock_manager,
        registry=registry,
        config=ExecutionConfig(enable_verification=True, enable_context_updates=True),
    )


# ==================== DesktopResult Tests ====================

class TestDesktopResult:
    """Test the DesktopResult model."""

    def test_create_success(self):
        """Test creating a successful result."""
        result = DesktopResult.create_success(
            goal="Activate VS Code",
            capability="activate_window",
            manager="mock",
            data={"window": "VS Code", "activated": True},
            events=["window_activated"],
        )
        assert result.success is True
        assert result.goal == "Activate VS Code"
        assert result.capability == "activate_window"
        assert result.manager == "mock"
        assert result.data == {"window": "VS Code", "activated": True}
        assert result.events == ["window_activated"]
        assert result.status == DesktopStatus.SUCCESS

    def test_create_failure(self):
        """Test creating a failure result."""
        result = DesktopResult.create_failure(
            goal="Close nonexistent window",
            capability="close_window",
            manager="mock",
            error="Window not found: Nonexistent",
        )
        assert result.success is False
        assert result.error == "Window not found: Nonexistent"
        assert result.status == DesktopStatus.FAILURE

    def test_create_partial(self):
        """Test creating a partial result."""
        result = DesktopResult.create_partial(
            goal="List windows",
            capability="list_windows",
            manager="mock",
            data=[],
            warnings=["No windows found"],
        )
        assert result.success is True
        assert result.status == DesktopStatus.PARTIAL
        assert len(result.warnings) == 1

    def test_create_cancelled(self):
        """Test creating a cancelled result."""
        result = DesktopResult.create_cancelled(
            goal="Shutdown",
            capability="shutdown",
            manager="mock",
            reason="User cancelled",
        )
        assert result.success is False
        assert result.status == DesktopStatus.CANCELLED

    def test_rollback_execution(self):
        """Test rollback execution."""
        rollback_called = [False]

        def rollback():
            rollback_called[0] = True
            return True

        result = DesktopResult.create_success(
            goal="Test", capability="test", manager="mock",
            rollback=rollback,
        )
        assert result.rollback_available is True
        assert result.execute_rollback() is True
        assert rollback_called[0] is True

    def test_rollback_not_available(self):
        """Test rollback when not available."""
        result = DesktopResult.create_success(
            goal="Test", capability="test", manager="mock",
        )
        assert result.rollback_available is False
        assert result.execute_rollback() is False

    def test_add_warning(self):
        """Test adding warnings."""
        result = DesktopResult.create_success(
            goal="Test", capability="test", manager="mock",
        )
        result.add_warning("Warning 1")
        result.add_warning("Warning 2")
        assert len(result.warnings) == 2

    def test_add_event(self):
        """Test adding events (no duplicates)."""
        result = DesktopResult.create_success(
            goal="Test", capability="test", manager="mock",
        )
        result.add_event("window_activated")
        result.add_event("window_activated")  # Should not duplicate
        assert len(result.events) == 1

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = DesktopResult.create_success(
            goal="Test", capability="test", manager="mock",
            data={"key": "value"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["goal"] == "Test"
        assert d["capability"] == "test"
        assert d["data"] == {"key": "value"}
        assert d["status"] == "success"

    def test_duration_ms(self):
        """Test duration calculation."""
        result = DesktopResult(
            success=True, goal="Test", capability="test", manager="mock",
            started_at=1000.0, completed_at=1001.5,
        )
        assert result.duration_ms == 1500.0

    def test_repr(self):
        """Test string representation."""
        result = DesktopResult.create_success(
            goal="Test", capability="activate_window", manager="mock",
        )
        repr_str = repr(result)
        assert "DesktopResult" in repr_str
        assert "activate_window" in repr_str


# ==================== MockManager Tests ====================

class TestMockManager:
    """Test the MockManager."""

    def test_initialization(self, mock_manager):
        """Test mock manager initialization."""
        assert mock_manager.name == "mock"
        assert mock_manager.get_call_count() == 0

    def test_execute_activate_window(self, mock_manager):
        """Test activating a window."""
        result = mock_manager.execute(
            capability="activate_window",
            goal="Activate VS Code",
            arguments={"window_title": "VS Code"},
        )
        assert result.success is True
        assert result.capability == "activate_window"
        assert result.data["window"] == "VS Code"
        assert result.data["activated"] is True
        assert "window_activated" in result.events
        assert result.rollback_available is True
        assert result.verification["passed"] is True

    def test_execute_list_windows(self, mock_manager):
        """Test listing windows."""
        result = mock_manager.execute(
            capability="list_windows",
            goal="List all windows",
            arguments={},
        )
        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) == 3  # Calculator, VS Code, Chrome

    def test_execute_close_window(self, mock_manager):
        """Test closing a window."""
        result = mock_manager.execute(
            capability="close_window",
            goal="Close Calculator",
            arguments={"window_title": "Calculator"},
        )
        assert result.success is True
        assert result.data["closed"] is True
        assert result.rollback_available is True

    def test_execute_unknown_capability(self, mock_manager):
        """Test executing an unknown capability."""
        result = mock_manager.execute(
            capability="unknown_capability",
            goal="Do something unknown",
            arguments={},
        )
        assert result.success is False
        assert "Unknown capability" in result.error

    def test_execute_window_not_found(self, mock_manager):
        """Test activating a nonexistent window."""
        result = mock_manager.execute(
            capability="activate_window",
            goal="Activate Nonexistent",
            arguments={"window_title": "Nonexistent"},
        )
        assert result.success is False
        assert "Window not found" in result.error

    def test_rollback_activate_window(self, mock_manager):
        """Test rollback after activating a window."""
        result = mock_manager.execute(
            capability="activate_window",
            goal="Activate Chrome",
            arguments={"window_title": "Chrome"},
        )
        assert result.success is True
        assert result.rollback_available is True

        # Execute rollback
        rollback_result = result.execute_rollback()
        assert rollback_result is True

    def test_clipboard_operations(self, mock_manager):
        """Test clipboard write and read."""
        # Write to clipboard
        write_result = mock_manager.execute(
            capability="write_clipboard",
            goal="Copy text to clipboard",
            arguments={"text": "Hello World"},
        )
        assert write_result.success is True
        assert write_result.data["text"] == "Hello World"

        # Read from clipboard
        read_result = mock_manager.execute(
            capability="read_clipboard",
            goal="Read clipboard",
            arguments={},
        )
        assert read_result.success is True
        assert read_result.data["text"] == "Hello World"

    def test_audio_operations(self, mock_manager):
        """Test audio operations."""
        # Set volume
        result = mock_manager.execute(
            capability="set_volume",
            goal="Set volume to 80%",
            arguments={"volume": 0.8},
        )
        assert result.success is True
        assert result.data["volume"] == 0.8
        assert result.rollback_available is True

    def test_call_log(self, mock_manager):
        """Test call logging."""
        mock_manager.execute(
            capability="list_windows", goal="List windows", arguments={},
        )
        mock_manager.execute(
            capability="list_displays", goal="List displays", arguments={},
        )
        assert mock_manager.get_call_count() == 2
        assert mock_manager.was_called("list_windows") is True
        assert mock_manager.was_called("list_displays") is True

    def test_reset(self, mock_manager):
        """Test resetting the mock manager."""
        mock_manager.execute(
            capability="list_windows", goal="List", arguments={},
        )
        assert mock_manager.get_call_count() == 1
        mock_manager.reset()
        assert mock_manager.get_call_count() == 0


# ==================== DesktopExecutionEngine Tests ====================

class TestDesktopExecutionEngine:
    """Test the DesktopExecutionEngine - the main orchestrator."""

    def test_initialization(self, engine):
        """Test engine initialization."""
        assert engine.manager.name == "mock"
        assert engine.config.enabled is True
        assert engine.get_execution_count() == 0

    def test_execute_with_discovery(self, engine):
        """Test executing with capability discovery from natural language."""
        result = engine.execute(goal="Activate VS Code")

        assert result.success is True
        assert result.goal == "Activate VS Code"
        assert result.capability == "activate_window"
        assert result.manager == "window"
        assert "window_activated" in result.events
        assert result.verification["passed"] is True
        assert result.rollback_available is True

    def test_execute_with_explicit_capability(self, engine):
        """Test executing with an explicit capability name."""
        result = engine.execute(
            goal="List all windows",
            capability="list_windows",
        )

        assert result.success is True
        assert result.capability == "list_windows"
        assert result.manager == "window"
        assert isinstance(result.data, list)
        assert len(result.data) == 3

    def test_execute_with_arguments(self, engine):
        """Test executing with arguments."""
        result = engine.execute(
            goal="Activate Chrome",
            capability="activate_window",
            arguments={"window_title": "Chrome"},
        )

        assert result.success is True
        assert result.data["window"] == "Chrome"

    def test_execute_with_kwargs(self, engine):
        """Test executing with keyword arguments."""
        result = engine.execute(
            goal="Write to clipboard",
            capability="clipboard.write_text",
            text="Hello from kwargs",
        )

        assert result.success is True
        assert result.data["text"] == "Hello from kwargs"

    def test_capability_discovery_list_windows(self, engine):
        """Test capability discovery for 'list windows' goal."""
        result = engine.execute(goal="list windows")
        assert result.capability == "list_windows"
        assert result.success is True

    def test_capability_discovery_close_window(self, engine):
        """Test capability discovery for 'close' goal."""
        result = engine.execute(goal="Close Calculator")
        assert result.capability == "close_window"
        assert result.success is True

    def test_capability_discovery_clipboard(self, engine):
        """Test capability discovery for clipboard operations."""
        result = engine.execute(goal="write clipboard")
        assert result.capability == "clipboard.write_text"
        assert result.success is True

    def test_capability_discovery_volume(self, engine):
        """Test capability discovery for volume operations."""
        result = engine.execute(
            goal="set volume", arguments={"volume": 0.7}
        )
        assert result.capability == "set_volume"
        assert result.success is True

    def test_capability_discovery_no_match(self, engine):
        """Test capability discovery when no match is found."""
        result = engine.execute(goal="do something completely unknown xyz123")
        assert result.success is False
        assert "No capability found" in result.error

    def test_unknown_capability_in_registry(self, engine):
        """Test executing a capability not in the registry."""
        result = engine.execute(
            goal="Test",
            capability="nonexistent_capability",
        )
        assert result.success is False
        assert "Capability not in registry" in result.error

    def test_verification(self, engine):
        """Test that verification runs and passes."""
        result = engine.execute(goal="list windows")
        assert result.verification["passed"] is True
        assert "checks" in result.verification

    def test_rollback_support(self, engine):
        """Test that rollback is available for undoable operations."""
        result = engine.execute(goal="Activate VS Code")
        assert result.rollback_available is True
        assert result.rollback is not None

        # Execute rollback
        rollback_result = result.execute_rollback()
        assert rollback_result is True

    def test_events_published(self, engine):
        """Test that events are published during execution."""
        result = engine.execute(goal="Activate Chrome")
        assert len(result.events) > 0
        assert "window_activated" in result.events

    def test_context_changes(self, engine):
        """Test that context changes are recorded."""
        result = engine.execute(goal="Activate VS Code")
        assert len(result.context_changes) > 0
        assert "active_window" in result.context_changes

    def test_metrics_recorded(self, engine):
        """Test that metrics are recorded."""
        result = engine.execute(goal="list windows")
        assert "total_duration_ms" in result.metrics
        assert "diagnostics" in result.metrics
        assert result.metrics["total_duration_ms"] > 0

    def test_diagnostics_report(self, engine):
        """Test that diagnostics are available."""
        engine.execute(goal="list windows")
        report = engine.get_diagnostics_report()
        assert "NATIVE OPERATION DIAGNOSTICS" in report

    def test_execution_history(self, engine):
        """Test that execution history is tracked."""
        engine.execute(goal="list windows")
        engine.execute(goal="list displays")

        assert engine.get_execution_count() == 2
        history = engine.get_execution_history()
        assert len(history) == 2

    def test_last_result(self, engine):
        """Test getting the last result."""
        engine.execute(goal="list windows")
        last = engine.get_last_result()
        assert last is not None
        assert last.capability == "list_windows"

    def test_success_rate(self, engine):
        """Test success rate calculation."""
        engine.execute(goal="list windows")  # Success
        engine.execute(goal="Activate VS Code")  # Success
        engine.execute(goal="unknown xyz123")  # Failure

        rate = engine.get_success_rate()
        assert rate == 2/3

    def test_reset(self, engine):
        """Test resetting the engine."""
        engine.execute(goal="list windows")
        assert engine.get_execution_count() == 1
        engine.reset()
        assert engine.get_execution_count() == 0

    def test_disabled_engine(self, mock_manager, registry):
        """Test that a disabled engine returns failure."""
        engine = DesktopExecutionEngine(
            manager=mock_manager, registry=registry,
            config=ExecutionConfig(enabled=False),
        )
        result = engine.execute(goal="list windows")
        assert result.success is False
        assert "disabled" in result.error.lower()


# ==================== Full Pipeline Integration Tests ====================

class TestFullPipeline:
    """Test the full pipeline end-to-end."""

    def test_full_pipeline_window_activation(self, engine):
        """Test the full pipeline for window activation."""
        result = engine.execute(goal="Activate VS Code")

        # Discovery
        assert result.capability == "activate_window"

        # Registry lookup
        assert result.manager == "window"

        # Permission check passed (result succeeded)
        assert result.success is True

        # Pipeline executed
        assert result.data is not None
        assert result.data["activated"] is True

        # Verification
        assert result.verification["passed"] is True

        # Events
        assert "window_activated" in result.events

        # Rollback
        assert result.rollback_available is True

        # Context changes
        assert "active_window" in result.context_changes

        # Metrics
        assert result.metrics["total_duration_ms"] > 0

    def test_full_pipeline_clipboard_write(self, engine):
        """Test the full pipeline for clipboard write."""
        result = engine.execute(
            goal="write clipboard",
            text="Test text",
        )

        assert result.success is True
        assert result.capability == "clipboard.write_text"
        assert result.data["text"] == "Test text"
        assert "clipboard_changed" in result.events
        assert result.rollback_available is True

    def test_full_pipeline_multiple_operations(self, engine):
        """Test multiple operations in sequence."""
        # Op 1: List windows
        r1 = engine.execute(goal="list windows")
        assert r1.success is True
        assert r1.capability == "list_windows"

        # Op 2: Activate a window
        r2 = engine.execute(goal="Activate Chrome")
        assert r2.success is True
        assert r2.capability == "activate_window"

        # Op 3: Write clipboard
        r3 = engine.execute(goal="write clipboard", text="Hello")
        assert r3.success is True
        assert r3.capability == "clipboard.write_text"

        # Op 4: List displays
        r4 = engine.execute(goal="list displays")
        assert r4.success is True
        assert r4.capability == "list_displays"

        # Check history
        assert engine.get_execution_count() == 4
        assert engine.get_success_rate() == 1.0

    def test_full_pipeline_with_rollback(self, engine):
        """Test the full pipeline including rollback."""
        # Execute an operation
        result = engine.execute(goal="Activate VS Code")
        assert result.success is True
        assert result.rollback_available is True

        # Execute rollback
        rollback_success = result.execute_rollback()
        assert rollback_success is True

    def test_full_pipeline_failure_handling(self, engine):
        """Test failure handling in the pipeline."""
        # Try to activate a nonexistent window
        result = engine.execute(
            goal="Activate Nonexistent Window",
            capability="activate_window",
            arguments={"window_title": "Nonexistent"},
        )
        assert result.success is False
        assert result.error is not None
        assert "Window not found" in result.error

    def test_full_pipeline_power_operations(self, engine):
        """Test power operations through the pipeline."""
        result = engine.execute(goal="lock")
        assert result.success is True
        assert result.capability == "lock"
        assert result.manager == "power"
        assert "system_lock" in result.events
        assert len(result.warnings) > 0  # Mock warning

    def test_full_pipeline_audio_operations(self, engine):
        """Test audio operations through the pipeline."""
        result = engine.execute(
            goal="set volume",
            arguments={"volume": 0.9},
        )
        assert result.success is True
        assert result.capability == "set_volume"
        assert result.data["volume"] == 0.9
        assert "audio_volume_changed" in result.events
        assert result.rollback_available is True

    def test_full_pipeline_service_operations(self, engine):
        """Test service operations through the pipeline."""
        result = engine.execute(goal="list services")
        assert result.success is True
        assert result.capability == "list_services"
        assert result.manager == "service"
        assert isinstance(result.data, list)

    def test_full_pipeline_network_operations(self, engine):
        """Test network operations through the pipeline."""
        result = engine.execute(goal="list network")
        assert result.success is True
        assert result.capability == "list_network_interfaces"
        assert result.manager == "network"
        assert isinstance(result.data, list)

    def test_full_pipeline_display_operations(self, engine):
        """Test display operations through the pipeline."""
        result = engine.execute(goal="list displays")
        assert result.success is True
        assert result.capability == "list_displays"
        assert result.manager == "display"
        assert isinstance(result.data, list)
        assert len(result.data) == 2  # Main + Secondary


# ==================== Architecture Validation Tests ====================

class TestArchitectureValidation:
    """Validate that the architecture mirrors ResearchEngine correctly."""

    def test_engine_is_single_entry_point(self, engine):
        """Verify that engine.execute() is the single entry point."""
        # All operations should go through execute()
        result = engine.execute(goal="list windows")
        assert result is not None
        assert isinstance(result, DesktopResult)

    def test_result_contains_all_future_proof_fields(self, engine):
        """Verify DesktopResult has all future-proof fields."""
        result = engine.execute(goal="Activate VS Code")

        # Core fields
        assert hasattr(result, 'success')
        assert hasattr(result, 'goal')
        assert hasattr(result, 'capability')
        assert hasattr(result, 'manager')
        assert hasattr(result, 'data')
        assert hasattr(result, 'error')

        # Execution metadata
        assert hasattr(result, 'status')

        # Events
        assert hasattr(result, 'events')

        # Rollback
        assert hasattr(result, 'rollback')
        assert hasattr(result, 'rollback_available')

        # Verification
        assert hasattr(result, 'verification')

        # Metrics
        assert hasattr(result, 'metrics')

        # Context changes
        assert hasattr(result, 'context_changes')

        # Warnings
        assert hasattr(result, 'warnings')

    def test_pipeline_stages_all_executed(self, engine):
        """Verify all pipeline stages are executed."""
        result = engine.execute(goal="Activate VS Code")

        # Discovery happened (capability was found)
        assert result.capability == "activate_window"

        # Registry lookup happened (manager is set from descriptor)
        assert result.manager == "window"

        # Permission check happened (result succeeded)
        assert result.success is True

        # Pipeline execute happened (data is present)
        assert result.data is not None

        # Verification happened
        assert "passed" in result.verification

        # Context update happened
        assert len(result.context_changes) > 0

        # Events published
        assert len(result.events) > 0

        # Diagnostics recorded
        assert "diagnostics" in result.metrics
        assert "total_duration_ms" in result.metrics

    def test_mock_manager_swappable(self, mock_manager, registry):
        """Verify that the manager is swappable (DI pattern)."""
        # Create engine with mock manager
        engine1 = DesktopExecutionEngine(manager=mock_manager, registry=registry)
        assert engine1.manager.name == "mock"

        # Create a different mock manager
        mock_manager2 = MockManager()
        mock_manager2.name = "mock_v2"

        # Create engine with different manager
        engine2 = DesktopExecutionEngine(manager=mock_manager2, registry=registry)
        assert engine2.manager.name == "mock_v2"

        # Both should work the same way
        r1 = engine1.execute(goal="list windows")
        r2 = engine2.execute(goal="list windows")
        assert r1.success is True
        assert r2.success is True

    def test_registry_lookup_works(self, engine, registry):
        """Verify registry lookup returns correct descriptors."""
        # Get descriptor for activate_window
        descriptor = registry.get("activate_window")
        assert descriptor is not None
        assert descriptor.name == "activate_window"
        assert descriptor.manager == "window"
        assert descriptor.permission == PermissionRequired.CONTROL
        assert descriptor.supports_undo is True

    def test_capability_discovery_covers_all_categories(self, engine):
        """Verify discovery works for all capability categories."""
        test_cases = [
            ("list windows", "list_windows", "window"),
            ("write clipboard", "clipboard.write_text", "clipboard"),
            ("list displays", "list_displays", "display"),
            ("set volume", "set_volume", "audio"),
            ("list network", "list_network_interfaces", "network"),
            ("list services", "list_services", "service"),
            ("lock", "lock", "power"),
        ]

        for goal, expected_cap, expected_manager in test_cases:
            result = engine.execute(goal=goal)
            assert result.capability == expected_cap, \
                f"Goal '{goal}' → expected '{expected_cap}', got '{result.capability}'"
            assert result.manager == expected_manager, \
                f"Goal '{goal}' → expected manager '{expected_manager}', got '{result.manager}'"
            assert result.success is True, \
                f"Goal '{goal}' failed: {result.error}"


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    """Run tests directly: python tests/desktop/test_execution_pipeline.py"""
    pytest.main([__file__, "-v", "--tb=short"])