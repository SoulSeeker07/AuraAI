"""
Aura Plugin Template

This is a template for creating Aura plugins.
Follow this pattern to create new plugins.
"""


import logging
from typing import Any, Dict, Optional
from src.plugins.plugin_interface import Plugin, PluginManifest, PluginCategory


logger = logging.getLogger(__name__)


class ExamplePlugin(Plugin):
    """
    Example Aura Plugin.

    Replace this with your plugin's functionality.
    """

    def __init__(self, manifest: PluginManifest):
        """
        Initialize the plugin.

        Args:
            manifest: Plugin manifest with metadata
        """
        super().__init__(manifest)

    def load(self) -> bool:
        """
        Load the plugin.

        This is called when the plugin is first discovered.
        Use this to load external resources, initialize variables, etc.

        Returns:
            True if loaded successfully
        """
        try:
            logger.info(f"Loading plugin: {self.manifest.name}")

            # Initialize plugin state here
            self.state = "initialized"

            # Register capabilities
            for capability in self.manifest.capabilities:
                self.register_capability(capability, self._handle_capability)

            logger.info(f"Plugin loaded successfully: {self.manifest.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {self.manifest.name}: {e}")
            self.set_error(e)
            return False

    def initialize(self) -> bool:
        """
        Initialize the plugin.

        This is called after load() is successful.
        Use this to set up more complex state.

        Returns:
            True if initialized successfully
        """
        try:
            logger.info(f"Initializing plugin: {self.manifest.name}")

            # Perform initialization logic here

            self.state = "ready"

            logger.info(f"Plugin initialized successfully: {self.manifest.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize plugin {self.manifest.name}: {e}")
            self.set_error(e)
            return False

    def can_handle(self, capability: str) -> bool:
        """
        Check if this plugin can handle the given capability.

        Args:
            capability: Capability to check

        Returns:
            True if plugin can handle it
        """
        return capability in self.manifest.capabilities

    def execute(self, capability: str, **kwargs) -> Any:
        """
        Execute a capability.

        Args:
            capability: Capability to execute
            **kwargs: Execution parameters

        Returns:
            Execution result

        Raises:
            PluginExecutionError: If execution fails
        """
        try:
            # Get the capability handler
            handler = self.get_capability_handler(capability)

            if not handler:
                raise Exception(f"Capability '{capability}' not found in plugin")

            # Execute the capability
            return handler(**kwargs)

        except Exception as e:
            logger.error(f"Error executing capability '{capability}' in plugin {self.manifest.name}: {e}")
            self.set_error(e)
            raise

    def _handle_capability(self, **kwargs) -> Any:
        """
        Internal method to handle capabilities.

        This is called when a capability is executed.
        Implement the specific logic for each capability here.

        Args:
            **kwargs: Capability parameters

        Returns:
            Result of the capability execution
        """
        # Implement your capability logic here
        logger.info(f"Handling capability: {kwargs.get('capability_name', 'unknown')}")

        # Return the result
        return {
            "status": "success",
            "message": f"Capability executed successfully"
        }

    def shutdown(self) -> bool:
        """
        Shutdown the plugin.

        This is called when the plugin is being unloaded.
        Clean up resources here.

        Returns:
            True if shutdown successfully
        """
        try:
            logger.info(f"Shutting down plugin: {self.manifest.name}")

            # Perform cleanup here

            return True

        except Exception as e:
            logger.error(f"Error shutting down plugin {self.manifest.name}: {e}")
            return False
