"""
Service Manager
Manages Windows service operations.
"""
from typing import List, Optional
import logging

from .native_manager import NativeManager
from .native_models import ServiceInfo
from .native_exceptions import ServiceNotFoundError

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages service operations"""

    def __init__(self, native_manager: NativeManager):
        """
        Initialize the service manager.

        Args:
            native_manager: The NativeManager instance
        """
        self.native_manager = native_manager
        logger.debug("ServiceManager initialized")

    def list_services(self) -> List[ServiceInfo]:
        """
        List all services.

        Returns:
            List of ServiceInfo objects
        """
        logger.debug("Listing all services")
        return self.native_manager._service_manager.list_services()

    def get_service_by_name(self, service_name: str) -> ServiceInfo:
        """
        Get service by name.

        Args:
            service_name: Service name

        Returns:
            ServiceInfo object

        Raises:
            ServiceNotFoundError: If service not found
        """
        logger.debug(f"Getting service by name: {service_name}")
        return self.native_manager._service_manager.get_service_by_name(service_name)

    def get_service_by_display_name(self, display_name: str) -> ServiceInfo:
        """
        Get service by display name.

        Args:
            display_name: Service display name

        Returns:
            ServiceInfo object

        Raises:
            ServiceNotFoundError: If service not found
        """
        logger.debug(f"Getting service by display name: {display_name}")
        return self.native_manager._service_manager.get_service_by_display_name(display_name)

    def start_service(self, service_name: str) -> bool:
        """
        Start a service.

        Args:
            service_name: Service name

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Starting service: {service_name}")
        return self.native_manager._service_manager.start_service(service_name)

    def stop_service(self, service_name: str) -> bool:
        """
        Stop a service.

        Args:
            service_name: Service name

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Stopping service: {service_name}")
        return self.native_manager._service_manager.stop_service(service_name)

    def restart_service(self, service_name: str) -> bool:
        """
        Restart a service.

        Args:
            service_name: Service name

        Returns:
            True if successful, False otherwise
        """
        logger.debug(f"Restarting service: {service_name}")
        return self.native_manager._service_manager.restart_service(service_name)

    def get_service_status(self, service_name: str) -> Optional[str]:
        """
        Get service status.

        Args:
            service_name: Service name

        Returns:
            Service status string, or None if service not found
        """
        logger.debug(f"Getting status for service: {service_name}")
        return self.native_manager._service_manager.get_service_status(service_name)

    def get_service_description(self, service_name: str) -> Optional[str]:
        """
        Get service description.

        Args:
            service_name: Service name

        Returns:
            Service description, or None if not found
        """
        logger.debug(f"Getting description for service: {service_name}")
        return self.native_manager._service_manager.get_service_description(service_name)

    def get_service_start_type(self, service_name: str) -> Optional[str]:
        """
        Get service start type.

        Args:
            service_name: Service name

        Returns:
            Start type string, or None if service not found
        """
        logger.debug(f"Getting start type for service: {service_name}")
        return self.native_manager._service_manager.get_service_start_type(service_name)

    def get_service_process_id(self, service_name: str) -> Optional[int]:
        """
        Get service process ID.

        Args:
            service_name: Service name

        Returns:
            Process ID, or None if service not found
        """
        logger.debug(f"Getting process ID for service: {service_name}")
        return self.native_manager._service_manager.get_service_process_id(service_name)

    def can_start(self, service_name: str) -> bool:
        """
        Check if service can be started.

        Args:
            service_name: Service name

        Returns:
            True if can be started, False otherwise
        """
        logger.debug(f"Checking if service can start: {service_name}")
        return self.native_manager._service_manager.can_start(service_name)

    def can_stop(self, service_name: str) -> bool:
        """
        Check if service can be stopped.

        Args:
            service_name: Service name

        Returns:
            True if can be stopped, False otherwise
        """
        logger.debug(f"Checking if service can stop: {service_name}")
        return self.native_manager._service_manager.can_stop(service_name)

    def is_running(self, service_name: str) -> bool:
        """
        Check if service is running.

        Args:
            service_name: Service name

        Returns:
            True if running, False otherwise
        """
        logger.debug(f"Checking if service is running: {service_name}")
        return self.native_manager._service_manager.is_running(service_name)
