"""
Registry Manager
Manages Windows registry operations.
"""
from typing import List, Optional, Any
import logging

from .native_manager import NativeManager
from .native_models import RegistryKey
from .native_exceptions import RegistryKeyNotFoundError, RegistryValueNotFoundError


logger = logging.getLogger(__name__)


class RegistryManager:
    """Manages registry operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the registry manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("RegistryManager initialized")

    def read_key(self, key_path: str, key_name: Optional[str] = None) -> List[RegistryKey]:
        """
        Read registry key or value.

        Args:
            key_path: Registry key path (e.g., "HKEY_LOCAL_MACHINE\\Software")
            key_name: Registry value name (optional, for single value)

        Returns:
            List of RegistryKey objects

        Raises:
            RegistryKeyNotFoundError: If key not found
        """
        logger.debug(f"Reading registry key: {key_path}, value: {key_name}")
        return self.native_manager._registry_manager.read_key(key_path, key_name)

    def read_value(self, key_path: str, value_name: str) -> Any:
        """
        Read specific registry value.

        Args:
            key_path: Registry key path
            value_name: Value name

        Returns:
            Value

        Raises:
            RegistryKeyNotFoundError: If key not found
            RegistryValueNotFoundError: If value not found
        """
        logger.debug(f"Reading registry value: {key_path}\\{value_name}")
        return self.native_manager._registry_manager.read_value(key_path, value_name)

    def write_value(
        self,
        key_path: str,
        value_name: str,
        value: Any,
        value_type: str = "REG_SZ"
    ) -> bool:
        """
        Write registry value.

        Args:
            key_path: Registry key path
            value_name: Value name
            value: Value to write
            value_type: Value type (REG_SZ, REG_DWORD, REG_BINARY, etc.)

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Writing registry value: {key_path}\\{value_name}")
        return self.native_manager._registry_manager.write_value(
            key_path, value_name, value, value_type
        )

    def delete_value(self, key_path: str, value_name: str) -> bool:
        """
        Delete registry value.

        Args:
            key_path: Registry key path
            value_name: Value name

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Deleting registry value: {key_path}\\{value_name}")
        return self.native_manager._registry_manager.delete_value(key_path, value_name)

    def delete_key(self, key_path: str) -> bool:
        """
        Delete registry key and all subkeys.

        Args:
            key_path: Registry key path

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Deleting registry key: {key_path}")
        return self.native_manager._registry_manager.delete_key(key_path)

    def key_exists(self, key_path: str) -> bool:
        """
        Check if registry key exists.

        Args:
            key_path: Registry key path

        Returns:
            True if key exists, False otherwise
        """
        logger.debug(f"Checking if registry key exists: {key_path}")
        return self.native_manager._registry_manager.key_exists(key_path)

    def value_exists(self, key_path: str, value_name: str) -> bool:
        """
        Check if registry value exists.

        Args:
            key_path: Registry key path
            value_name: Value name

        Returns:
            True if value exists, False otherwise
        """
        logger.debug(f"Checking if registry value exists: {key_path}\\{value_name}")
        return self.native_manager._registry_manager.value_exists(key_path, value_name)

    def list_subkeys(self, key_path: str) -> List[str]:
        """
        List subkeys of a registry key.

        Args:
            key_path: Registry key path

        Returns:
            List of subkey names
        """
        logger.debug(f"Listing subkeys for: {key_path}")
        return self.native_manager._registry_manager.list_subkeys(key_path)
