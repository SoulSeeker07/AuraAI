"""
Test: AuraCore brain_init wiring — identity check runs under CI.

Verifies that ContextBuilder.memory_manager and ExecutionCoordinator.memory_manager
are the exact same MemoryManager instance directly owned by AuraCore (zero split-brain).
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def reset_aura_core_singleton():
    """Each test gets a clean AuraCore singleton."""
    from core.aura_core import AuraCore

    # Reset singletons before the test
    AuraCore._instance = None
    AuraCore._initialized = False

    yield

    # Tear down after
    AuraCore._instance = None
    AuraCore._initialized = False


def test_brain_init_wiring_identity_check(tmp_path):
    """
    brain_init must complete successfully (brain_enabled=True) and
    ContextBuilder.memory_manager and ExecutionCoordinator.memory_manager
    must be the exact same object as core.memory_manager.
    """
    from core.aura_core import AuraCore
    AuraCore.reset_instance()

    # Use a real temp file so Path(db_path) resolves correctly
    db_path = tmp_path / "test_memory.db"

    # ── Mock the things that need an API key or network ──────────────────────
    mock_groq_provider = MagicMock()
    mock_provider_manager = MagicMock()
    mock_memory_instance = MagicMock()

    with patch("src.ai.groq_provider.GroqProvider", return_value=mock_groq_provider), \
         patch("ai.provider_manager.ProviderManager", return_value=mock_provider_manager), \
         patch("core.aura_core.Memory", return_value=mock_memory_instance):

        config = {
            "groq_model": "mock-model",
            "voice_enabled": False,
            "memory_db_path": str(db_path),
        }
        core = AuraCore(config)

    # ── Assert brain_init completed ──────────────────────────────────────────
    assert core.brain_enabled, (
        f"brain_init failed — brain_enabled is False. "
        f"Error: {getattr(core, '_brain_init_error', 'unknown')}"
    )
    assert hasattr(core, "conversation_engine"), (
        "brain_init completed but conversation_engine was not set"
    )
    assert hasattr(core, "memory_manager"), (
        "AuraCore must directly own its memory_manager"
    )

    # ── Assert the identity check actually passed ────────────────────────────
    assert core.conversation_engine.context_builder.memory_manager is core.memory_manager, (
        "ContextBuilder.memory_manager is NOT the same object as "
        "AuraCore.memory_manager — split-brain regression!"
    )
    assert core.coordinator.memory_manager is core.memory_manager, (
        "ExecutionCoordinator.memory_manager is NOT the same object as "
        "AuraCore.memory_manager — split-brain regression!"
    )


def test_brain_init_failure_is_loud():
    """
    If brain_init fails, brain_enabled must be False AND _brain_init_error
    must be set (so health checks and tests can inspect the cause), not silently
    swallowed.
    """
    from core.aura_core import AuraCore
    AuraCore.reset_instance()

    # Force GroqProvider to blow up
    with patch("src.ai.groq_provider.GroqProvider", side_effect=RuntimeError("no key")):
        config = {"groq_model": "mock", "voice_enabled": False}
        core = AuraCore(config)

    assert not core.brain_enabled, "brain_enabled should be False when init fails"
    assert hasattr(core, "_brain_init_error"), (
        "_brain_init_error not set — silent failure, impossible to diagnose"
    )
    assert isinstance(core._brain_init_error, Exception)
