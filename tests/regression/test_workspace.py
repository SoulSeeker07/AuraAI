"""
Regression tests for Workspace subsystem.

These tests ensure that Workspace behavior doesn't break during refactors.
Run this suite before any major refactors to prevent regressions.
"""

import pytest


class TestWorkspaceRegression:
    """Test suite for Workspace subsystem regression prevention."""

    def test_workspace_detection(self):
        """Verify workspace detection works."""
        from core.aura_core import AuraCore

        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()

        # Check workspace
        workspace = core.workspace
        assert workspace is not None
        assert isinstance(workspace, str)

    def test_workspace_info_access(self):
        """Verify workspace info can be accessed."""
        from core.aura_core import AuraCore

        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()

        # Check workspace info
        workspace_info = core.workspace_info
        assert isinstance(workspace_info, dict)

    def test_plugin_management(self):
        """Verify plugin management works."""
        from core.aura_core import AuraCore

        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()

        # Check plugin count
        plugin_count = core.plugin_count
        assert isinstance(plugin_count, int)

    def test_plugins_list(self):
        """Verify plugins list is accessible."""
        from core.aura_core import AuraCore

        # Note: Singleton issue may prevent proper initialization
        core = AuraCore()

        # Check plugins list
        plugins = core.plugins
        assert isinstance(plugins, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
