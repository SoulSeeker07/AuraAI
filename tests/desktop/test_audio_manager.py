"""
Test AudioManager & AudioAdapter Hierarchy

Validates:
1. AudioAdapter hierarchy and fallback chain (PyCAWAudioAdapter -> WinMMAudioAdapter -> DummyAudioAdapter).
2. AudioManager pure native structure (zero cross-cutting concerns).
3. Auto-discovery by NativeManagerRegistry.
4. Health check reporting.
5. Capability execution through DesktopExecutionEngine.
"""

import inspect
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

import src.desktop.native.managers.audio_manager as am_module
from src.desktop.native.adapters.audio_adapter import (
    AudioAdapter,
    AudioAdapterFactory,
    DummyAudioAdapter,
    PyCAWAudioAdapter,
    WinMMAudioAdapter,
)
from src.desktop.native.desktop_execution_engine import DesktopExecutionEngine
from src.desktop.native.managers.audio_manager import AudioManager
from src.desktop.native.managers.base_manager import HealthStatus
from src.desktop.native.managers.native_manager_registry import NativeManagerRegistry


def setup_function():
    """Reset registry singleton before test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singleton after test."""
    NativeManagerRegistry.reset_instance()


def test_audio_adapter_hierarchy():
    """Test AudioAdapter hierarchy and fallback selection."""
    dummy = DummyAudioAdapter()
    assert dummy.is_available() is True
    assert len(dummy.list_devices()) >= 2
    assert dummy.set_volume(75.0) is True
    assert dummy.get_volume()["level"] == 75.0
    assert dummy.set_mute(True) is True
    assert dummy.get_mute() is True

    winmm = WinMMAudioAdapter()
    assert isinstance(winmm, AudioAdapter)

    pycaw = PyCAWAudioAdapter()
    assert isinstance(pycaw, AudioAdapter)

    # Factory selection
    active_adapter = AudioAdapterFactory.get_adapter()
    assert isinstance(active_adapter, AudioAdapter)
    assert active_adapter.is_available() is True

    print(f"[OK] AudioAdapter hierarchy verified (active: {active_adapter.name})")


def test_audio_manager_native_structure():
    """Test that AudioManager follows pure native manager structure."""
    manager = AudioManager(adapter=DummyAudioAdapter())
    assert manager.name == "audio"
    assert manager.NAME == "audio"
    assert manager.VERSION == "1.0"
    assert manager.PRIORITY == 20
    assert "pycaw" in manager.DEPENDENCIES
    assert len(manager.capabilities) >= 8

    # Verify no cross-cutting concerns in code body
    source = inspect.getsource(am_module)
    forbidden_symbols = [
        "PermissionMiddleware",
        "MetricsRecorder",
        "DiagnosticsStage",
        "get_desktop_context",
        "NativeEventBus",
    ]
    for symbol in forbidden_symbols:
        assert (
            symbol not in source
        ), f"AudioManager code body contains forbidden symbol: {symbol}"

    print("[OK] AudioManager native structure verified")


def test_audio_manager_auto_discovery_and_health():
    """Test AudioManager auto-discovery and health checks."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("src.desktop.native.managers")

    assert "audio" in discovered
    audio_manager = registry.get("audio")
    assert audio_manager is not None
    assert audio_manager.name == "audio"

    health_res = audio_manager.health_check()
    assert health_res.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    print(
        f"[OK] AudioManager auto-discovery and health check verified (status: {health_res.status.value})"
    )


def test_audio_capabilities_execution():
    """Test executing audio capabilities through DesktopExecutionEngine."""
    registry = NativeManagerRegistry.get_instance()
    registry.discover("src.desktop.native.managers")

    engine = DesktopExecutionEngine(manager_registry=registry)

    # Test list_audio_devices
    res_list = engine.execute(
        goal="list audio devices", capability="list_audio_devices"
    )
    assert res_list.success is True
    assert "devices" in res_list.data

    # Test audio.list_devices
    res_list_dot = engine.execute(
        goal="list audio endpoints", capability="audio.list_devices"
    )
    assert res_list_dot.success is True

    # Test get_volume
    res_vol = engine.execute(goal="get volume level", capability="get_volume")
    assert res_vol.success is True
    assert "level" in res_vol.data

    # Test set_volume
    res_set_vol = engine.execute(
        goal="set volume to 80%", capability="set_volume", level=80.0
    )
    assert res_set_vol.success is True
    assert res_set_vol.data["level"] == 80.0

    # Test toggle_mute
    res_mute = engine.execute(goal="toggle mute", capability="toggle_mute", mute=True)
    assert res_mute.success is True
    assert res_mute.data["muted"] is True

    # Test is_muted
    res_is_muted = engine.execute(goal="check if muted", capability="is_muted")
    assert res_is_muted.success is True

    print("[OK] AudioManager capability execution through engine verified")
