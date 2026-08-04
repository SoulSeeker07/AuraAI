"""
Network Manager
Manages network interface operations.
"""
from typing import List, Optional
import logging

from .native_manager import NativeManager
from .native_models import NetworkInterface
from .native_exceptions import NetworkInterfaceNotFoundError

logger = logging.getLogger(__name__)


class NetworkManager:
    """Manages network interface operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the network manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("NetworkManager initialized")

    def list_interfaces(self) -> List[NetworkInterface]:
        """
        List all network interfaces.

        Returns:
            List of NetworkInterface objects
        """
        logger.debug("Listing all network interfaces")
        return self.native_manager._network_manager.list_interfaces()

    def get_default_interface(self) -> NetworkInterface:
        """
        Get default network interface.

        Returns:
            NetworkInterface object
        """
        logger.debug("Getting default network interface")
        return self.native_manager._network_manager.get_default_interface()

    def get_interface_by_index(self, index: int) -> NetworkInterface:
        """
        Get network interface by index.

        Args:
            index: Interface index

        Returns:
            NetworkInterface object

        Raises:
            NetworkInterfaceNotFoundError: If interface not found
        """
        logger.debug(f"Getting network interface at index: {index}")
        return self.native_manager._network_manager.get_interface_by_index(index)

    def get_interface_by_name(self, name: str) -> NetworkInterface:
        """
        Get network interface by name.

        Args:
            name: Interface name

        Returns:
            NetworkInterface object

        Raises:
            NetworkInterfaceNotFoundError: If interface not found
        """
        interfaces = self.list_interfaces()
        for interface in interfaces:
            if interface.name.lower() == name.lower():
                return interface
        raise NetworkInterfaceNotFoundError(
            f"Network interface not found with name: {name}",
            "get_interface_by_name",
            details={"name": name}
        )

    def get_ip_address(self, interface_index: int) -> Optional[str]:
        """
        Get IP address for network interface.

        Args:
            interface_index: Interface index

        Returns:
            IP address or None if not available
        """
        logger.debug(f"Getting IP address for interface {interface_index}")
        return self.native_manager._network_manager.get_ip_address(interface_index)

    def get_mac_address(self, interface_index: int) -> Optional[str]:
        """
        Get MAC address for network interface.

        Args:
            interface_index: Interface index

        Returns:
            MAC address or None if not available
        """
        logger.debug(f"Getting MAC address for interface {interface_index}")
        return self.native_manager._network_manager.get_mac_address(interface_index)

    def is_interface_connected(self, interface_index: int) -> bool:
        """
        Check if network interface is connected.

        Args:
            interface_index: Interface index

        Returns:
            True if connected, False otherwise
        """
        logger.debug(f"Checking if interface {interface_index} is connected")
        return self.native_manager._network_manager.is_interface_connected(interface_index)

    def ping(self, host: str, count: int = 4, timeout: int = 2) -> dict:
        """
        Ping a host.

        Args:
            host: Host to ping
            count: Number of pings to send
            timeout: Timeout in seconds

        Returns:
            Dictionary with ping results
        """
        logger.debug(f"Pinging host: {host}")
        return self.native_manager._network_manager.ping(host, count, timeout)

    def get_dns_servers(self, interface_index: int) -> List[str]:
        """
        Get DNS servers for network interface.

        Args:
            interface_index: Interface index

        Returns:
            List of DNS server addresses
        """
        logger.debug(f"Getting DNS servers for interface {interface_index}")
        return self.native_manager._network_manager.get_dns_servers(interface_index)
