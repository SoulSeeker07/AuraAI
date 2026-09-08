"""
Unit & Integration Tests for SpeechManager
Location: tests/desktop/test_speech_manager.py

Validates:
1. Class metadata (NAME, VERSION, PRIORITY, DEPENDENCIES, capabilities).
2. Lifecycle operations (initialize, health_check, shutdown).
3. Auto-discovery and resolution by NativeManagerRegistry.
4. All 6 speech capabilities:
   - speech.say
   - speech.list_voices
   - speech.set_voice
   - speech.set_rate
   - speech.set_volume
   - speech.stop
5. Error handling and edge cases (unsupported capability, invalid arguments).
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from desktop.native.desktop_result import DesktopResult, DesktopStatus
from desktop.native.managers.base_manager import HealthCheckResult, HealthStatus
from desktop.native.managers.native_manager_registry import NativeManagerRegistry
from desktop.native.managers.speech_manager import SpeechManager


def setup_function():
    """Reset registry singleton before each test."""
    NativeManagerRegistry.reset_instance()


def teardown_function():
    """Reset registry singleton after each test."""
    NativeManagerRegistry.reset_instance()


def test_speech_manager_metadata():
    """Validate SpeechManager class metadata and property contracts."""
    mgr = SpeechManager()
    assert mgr.name == "speech"
    assert mgr.NAME == "speech"
    assert mgr.VERSION == "1.0"
    assert mgr.PRIORITY == 30
    assert mgr.DEPENDENCIES == []

    expected_caps = [
        "speech.say",
        "speech.list_voices",
        "speech.set_voice",
        "speech.set_rate",
        "speech.set_volume",
        "speech.stop",
    ]
    assert len(mgr.capabilities) == 6
    for cap in expected_caps:
        assert cap in mgr.capabilities


def test_speech_manager_lifecycle():
    """Validate initialize, health check, and shutdown lifecycle."""
    mgr = SpeechManager()
    assert mgr._initialized is False

    init_ok = mgr.initialize()
    assert init_ok is True
    assert mgr._initialized is True

    health = mgr.health_check()
    assert isinstance(health, HealthCheckResult)
    assert health.manager_name == "speech"
    assert health.status == HealthStatus.HEALTHY
    assert health.total_capabilities == 6
    assert health.available_capabilities == 6
    assert health.details.get("initialized") is True
    assert "active_backend" in health.details

    mgr.shutdown()
    assert mgr._initialized is False


def test_auto_discovery_and_resolution():
    """Validate that NativeManagerRegistry discovers and resolves SpeechManager."""
    registry = NativeManagerRegistry.get_instance()
    discovered = registry.discover("desktop.native.managers")

    assert "speech" in discovered
    resolved = registry.resolve("speech.say")
    assert resolved is not None
    assert resolved.name == "speech"

    resolved_voices = registry.resolve("speech.list_voices")
    assert resolved_voices is not None
    assert resolved_voices.name == "speech"


def test_speech_list_voices():
    """Validate speech.list_voices capability execution and return format."""
    mgr = SpeechManager()
    result = mgr.execute("speech.list_voices")

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert "voices" in result.data
    assert "count" in result.data
    assert "backend" in result.data
    assert isinstance(result.data["voices"], list)
    assert result.data["count"] >= 0


def test_speech_set_voice():
    """Validate speech.set_voice capability."""
    mgr = SpeechManager()
    result = mgr.execute("speech.set_voice", arguments={"voice_id": "Microsoft David Desktop"})

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.data["voice"] == "Microsoft David Desktop"
    assert "voice_changed" in result.events

    # Missing argument failure
    fail_res = mgr.execute("speech.set_voice", arguments={})
    assert fail_res.success is False
    assert "Missing required argument" in fail_res.error


def test_speech_set_rate():
    """Validate speech.set_rate capability and clamping."""
    mgr = SpeechManager()
    result = mgr.execute("speech.set_rate", arguments={"rate": 220})

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.data["rate"] == 220
    assert "rate_changed" in result.events

    # Invalid rate
    fail_res = mgr.execute("speech.set_rate", arguments={"rate": "invalid"})
    assert fail_res.success is False
    assert "Invalid rate value" in fail_res.error


def test_speech_set_volume():
    """Validate speech.set_volume capability and clamping."""
    mgr = SpeechManager()
    result = mgr.execute("speech.set_volume", arguments={"volume": 0.8})

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.data["volume"] == 0.8
    assert "volume_changed" in result.events

    # Percentage input (80 -> 0.8)
    pct_res = mgr.execute("speech.set_volume", arguments={"volume": 80})
    assert pct_res.success is True
    assert pct_res.data["volume"] == 0.8

    # Missing volume
    fail_res = mgr.execute("speech.set_volume", arguments={})
    assert fail_res.success is False
    assert "Missing required argument" in fail_res.error


def test_speech_say_async_and_stop():
    """Validate speech.say (async daemon thread) and speech.stop."""
    mgr = SpeechManager()
    result = mgr.execute("speech.say", arguments={"text": "Test speech", "wait": False})

    assert isinstance(result, DesktopResult)
    assert result.success is True
    assert result.data["text"] == "Test speech"
    assert result.data["async"] is True
    assert "speech_started" in result.events

    # Stop active speech
    stop_res = mgr.execute("speech.stop")
    assert isinstance(stop_res, DesktopResult)
    assert stop_res.success is True
    assert stop_res.data["stopped"] is True
    assert "speech_stopped" in stop_res.events


def test_speech_say_validation():
    """Validate speech.say missing text validation."""
    mgr = SpeechManager()
    fail_res = mgr.execute("speech.say", arguments={"text": ""})

    assert fail_res.success is False
    assert "No text provided" in fail_res.error


def test_unsupported_capability():
    """Validate handling of unsupported capability."""
    mgr = SpeechManager()
    result = mgr.execute("speech.non_existent")

    assert result.success is False
    assert "Unsupported capability" in result.error
