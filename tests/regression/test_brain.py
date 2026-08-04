"""
Regression tests for AuraBrain subsystem.

These tests ensure that AuraBrain behavior doesn't break during refactors.
Run this suite before any major refactors to prevent regressions.
"""

import pytest


class TestBrainRegression:
    """Test suite for AuraBrain subsystem regression prevention."""

    def test_brain_initialization(self):
        """Verify AuraBrain initializes correctly."""
        from core.aura_core import AuraCore

        # This test verifies AuraBrain can be instantiated
        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()
        assert core is not None
        assert core.current_task is None

    def test_brain_components_initialized(self):
        """Verify AuraBrain components are initialized."""
        from core.aura_core import AuraCore

        # This test verifies AuraBrain components can be accessed
        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()

        # Check that core has expected attributes
        assert hasattr(core, 'memory')
        assert hasattr(core, 'conversation_engine')
        assert hasattr(core, 'components')
        assert hasattr(core, 'get_status')

    def test_brain_status_reporting(self):
        """Verify AuraBrain status reporting works."""
        from core.aura_core import AuraCore

        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()
        status = core.get_status()

        # Verify status structure
        assert 'components' in status
        assert 'memory' in status
        assert 'plugins' in status

    def test_brain_add_to_conversation(self):
        """Verify adding to conversation works."""
        from core.aura_core import AuraCore

        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()

        # Add to conversation
        core.add_to_conversation('user', 'Hello world')

        # Verify
        history = core.get_conversation_history()
        assert len(history) == 1
        assert history[0]['role'] == 'user'
        assert history[0]['content'] == 'Hello world'

    def test_brain_clear_conversation(self):
        """Verify clearing conversation works."""
        from core.aura_core import AuraCore

        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()

        # Add messages
        core.add_to_conversation('user', 'Hello')
        core.add_to_conversation('assistant', 'Hi there')

        # Clear
        core.clear_conversation_history()

        # Verify
        history = core.get_conversation_history()
        assert len(history) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
