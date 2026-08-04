"""
Unit tests for AuraCore Singleton pattern.

These tests verify that only one instance of AuraCore can be created
and that get_instance() returns the same instance across calls.
"""

import pytest

from core.aura_core import AuraCore


class TestAuraCoreSingleton:
    """Test suite for AuraCore singleton pattern."""

    def test_singleton_instance_created(self):
        """Verify that creating AuraCore creates an instance."""
        from core.aura_core import AuraCore

        core = AuraCore()
        assert core is not None
        assert isinstance(core, AuraCore)

    def test_singleton_multiple_instances_return_same_object(self):
        """Verify that multiple calls to get_instance() return the same instance."""
        from core.aura_core import AuraCore

        # Create instances using get_instance()
        core1 = AuraCore.get_instance()
        core2 = AuraCore.get_instance()
        core3 = AuraCore.get_instance()

        # Verify they are the same object
        assert core1 is core2
        assert core2 is core3
        assert core1 is core3

    def test_singleton_manual_instantiation_returns_single_instance(self):
        """Verify that manual instantiation returns the same singleton instance."""
        from core.aura_core import AuraCore

        # Create instance manually
        core1 = AuraCore()
        # Create another instance
        core2 = AuraCore()

        # Verify they are the same object
        assert core1 is core2

    def test_singleton_instance_has_correct_config(self):
        """Verify that singleton instance has correct configuration."""
        from core.aura_core import AuraCore

        config = {
            'project_root': '/test/path',
            'workspace': 'test_workspace',
            'groq_model': 'custom-model'
        }

        core = AuraCore.get_instance(config)

        assert core.config == config

    def test_singleton_initialized_flag(self):
        """Verify that _initialized flag works correctly."""
        from core.aura_core import AuraCore

        # Should start as False
        assert AuraCore._initialized is False

        # Create instance using get_instance (recommended method)
        core = AuraCore.get_instance()

        # Should now be True
        assert AuraCore._initialized is True

        # Create another instance
        core2 = AuraCore.get_instance()

        # Should still be True
        assert AuraCore._initialized is True

    def test_singleton_instance_is_unique(self):
        """Verify that only one instance can exist at a time."""
        from core.aura_core import AuraCore

        # Use get_instance (recommended method)
        core1 = AuraCore.get_instance()
        assert AuraCore._instance is not None

        # Create another instance using get_instance
        core2 = AuraCore.get_instance()

        # Verify they are the same
        assert core1 is core2

    def test_singleton_get_instance_with_none_config(self):
        """Verify get_instance() works with None config."""
        from core.aura_core import AuraCore

        # Reset singleton
        AuraCore._instance = None
        AuraCore._initialized = False

        # Get instance with None config
        core = AuraCore.get_instance(None)

        assert core is not None
        assert AuraCore._instance is core

    def test_singleton_no_multiple_initializations(self):
        """Verify that components are not re-initialized on subsequent calls."""
        from core.aura_core import AuraCore

        # Create first instance
        core1 = AuraCore.get_instance()

        # Create second instance (should not reinitialize)
        core2 = AuraCore.get_instance()

        # The _initialized flag should still be True
        assert AuraCore._initialized is True

        # Verify they are the same instance
        assert core1 is core2


    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset AuraCore singleton state before and after each test."""
        AuraCore._instance = None
        AuraCore._initialized = False
        yield
        AuraCore._instance = None
        AuraCore._initialized = False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
