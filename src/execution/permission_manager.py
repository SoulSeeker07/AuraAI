"""
Tool Execution Engine - Permission Management

This module manages permissions for tool executions, implementing a risk-based
access control system with four permission levels: Safe, Medium, High, and Critical.
"""


from typing import Dict, Set, Optional, List, Any
from enum import Enum
from .exceptions import PermissionDeniedError


class PermissionLevel(Enum):
    """Permission level enumeration."""
    SAFE = "safe"       # Read-only operations
    MEDIUM = "medium"   # Non-destructive operations
    HIGH = "high"       # Destructive operations
    CRITICAL = "critical"  # System-level operations


class PermissionAction(Enum):
    """Types of permissions."""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    DELETE_FILE = "delete_file"
    RENAME_FILE = "rename_file"
    EXECUTE_COMMAND = "execute_command"
    SHUTDOWN_SYSTEM = "shutdown_system"
    FORMAT_DISK = "format_disk"
    MODIFY_REGISTRY = "modify_registry"
    DELETE_SYSTEM32 = "delete_system32"
    OPEN_APPLICATION = "open_application"
    CLOSE_APPLICATION = "close_application"
    ACCESS_CLIPBOARD = "access_clipboard"
    NETWORK_ACCESS = "network_access"
    MAIL_SEND = "mail_send"
    CALENDAR_MODIFY = "calendar_modify"


# Permission mappings: what permission level is required for each action
REQUIRED_PERMISSIONS = {
    PermissionAction.READ_FILE: PermissionLevel.SAFE,
    PermissionAction.WRITE_FILE: PermissionLevel.MEDIUM,
    PermissionAction.DELETE_FILE: PermissionLevel.HIGH,
    PermissionAction.RENAME_FILE: PermissionLevel.MEDIUM,
    PermissionAction.EXECUTE_COMMAND: PermissionLevel.MEDIUM,
    PermissionAction.SHUTDOWN_SYSTEM: PermissionLevel.CRITICAL,
    PermissionAction.FORMAT_DISK: PermissionLevel.CRITICAL,
    PermissionAction.MODIFY_REGISTRY: PermissionLevel.HIGH,
    PermissionAction.DELETE_SYSTEM32: PermissionLevel.CRITICAL,
    PermissionAction.OPEN_APPLICATION: PermissionLevel.MEDIUM,
    PermissionAction.CLOSE_APPLICATION: PermissionLevel.MEDIUM,
    PermissionAction.ACCESS_CLIPBOARD: PermissionLevel.SAFE,
    PermissionAction.NETWORK_ACCESS: PermissionLevel.HIGH,
    PermissionAction.MAIL_SEND: PermissionLevel.MEDIUM,
    PermissionAction.CALENDAR_MODIFY: PermissionLevel.MEDIUM,
}


class PermissionManager:
    """Manages permissions for tool executions."""
    
    def __init__(self, allow_all: bool = False):
        """
        Initialize the permission manager.
        
        Args:
            allow_all: If True, all permissions are granted without checking.
                      This is for testing or trusted environments.
        """
        self.allow_all = allow_all
        self._user_permissions: Dict[str, Dict[str, PermissionLevel]] = {}
        self._current_level: PermissionLevel = PermissionLevel.MEDIUM
        self._global_permissions: Dict[PermissionLevel, Set[str]] = {
            level: set() for level in PermissionLevel
        }
    
    def set_global_permission(
        self,
        permission_level: PermissionLevel,
        action: PermissionAction,
        granted: bool = True
    ) -> None:
        """
        Set a global permission for a specific level.
        
        Args:
            permission_level: The permission level
            action: The permission action
            granted: Whether permission is granted
        """
        if granted:
            self._global_permissions[permission_level].add(action.value)
        else:
            self._global_permissions[permission_level].discard(action.value)
    
    def set_user_permission(
        self,
        user_id: str,
        permission_level: PermissionLevel,
        action: PermissionAction,
        granted: bool = True
    ) -> None:
        """
        Set a permission for a specific user.
        
        Args:
            user_id: User identifier
            permission_level: The permission level
            action: The permission action
            granted: Whether permission is granted
        """
        if user_id not in self._user_permissions:
            self._user_permissions[user_id] = {}
        
        if granted:
            self._user_permissions[user_id][action.value] = permission_level
        else:
            if action.value in self._user_permissions[user_id]:
                del self._user_permissions[user_id][action.value]
    
    def set_current_level(self, level: PermissionLevel) -> None:
        """
        Set the current permission level for all users.
        
        Args:
            level: The permission level
        """
        self._current_level = level
    
    def get_required_permission(self, action: PermissionAction) -> PermissionLevel:
        """
        Get the required permission level for an action.
        
        Args:
            action: The permission action
            
        Returns:
            The required permission level
        """
        return REQUIRED_PERMISSIONS.get(action, PermissionLevel.MEDIUM)
    
    def has_permission(
        self,
        user_id: str,
        action: PermissionAction,
        resource: str = None
    ) -> bool:
        """
        Check if a user has permission to execute an action.
        
        Args:
            user_id: User identifier
            action: The permission action
            resource: Optional resource being accessed
            
        Returns:
            True if permission is granted, False otherwise
        """
        if self.allow_all:
            return True
        
        # Check global permissions for the required level
        required_level = self.get_required_permission(action)
        required_permissions = self._global_permissions.get(required_level, set())
        
        # Check if the action is globally allowed
        if action.value not in required_permissions:
            return False
        
        # Check user-specific permissions
        if user_id in self._user_permissions:
            user_permissions = self._user_permissions[user_id]
            if action.value in user_permissions:
                user_granted_level = user_permissions[action.value]
                return user_granted_level == required_level
        
        # Check current level
        if action.value in self._global_permissions.get(self._current_level, set()):
            return True
        
        return False
    
    def request_permission(
        self,
        user_id: str,
        action: PermissionAction,
        resource: str = None,
        message: str = None
    ) -> bool:
        """
        Request permission from user for an action.
        
        Args:
            user_id: User identifier
            action: The permission action
            resource: Optional resource being accessed
            message: Optional message to display to user
            
        Returns:
            True if permission granted, False otherwise
        """
        if self.allow_all:
            return True
        
        if self.has_permission(user_id, action, resource):
            return True
        
        # For now, deny by default - in a real implementation, this would prompt the user
        return False
    
    def check_permission(
        self,
        user_id: str,
        action: PermissionAction,
        execution_id: str = None,
        resource: str = None,
        allow_confirmation: bool = True
    ) -> bool:
        """
        Check permission and optionally request confirmation.
        
        Args:
            user_id: User identifier
            action: The permission action
            execution_id: Execution ID for error messages
            resource: Optional resource being accessed
            allow_confirmation: Whether to request confirmation
            
        Returns:
            True if permission granted
            
        Raises:
            PermissionDeniedError: If permission is denied
        """
        if self.allow_all:
            return True
        
        if not self.has_permission(user_id, action, resource):
            required_level = self.get_required_permission(action)
            
            if allow_confirmation:
                # For now, we'll use a simple override mechanism
                # In production, this would prompt the user via the UI
                pass
            
            raise PermissionDeniedError(
                f"Permission denied: {action.value}",
                execution_id=execution_id,
                required_permission=action.value,
                permission_level=required_level.value,
                resource=resource
            )
        
        return True
    
    def get_permission_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current permission settings.
        
        Returns:
            Dictionary with permission summary
        """
        return {
            "allow_all": self.allow_all,
            "current_level": self._current_level.value,
            "global_permissions": {
                level.value: list(perms)
                for level, perms in self._global_permissions.items()
            },
            "user_permissions_count": len(self._user_permissions)
        }
    
    def list_actions_for_level(self, level: PermissionLevel) -> List[str]:
        """
        List all actions that require a specific permission level.
        
        Args:
            level: The permission level
            
        Returns:
            List of action names
        """
        required_permissions = {}
        for action, req_level in REQUIRED_PERMISSIONS.items():
            if req_level == level:
                required_permissions[action.value] = action.value
        
        return list(required_permissions.keys())


class PermissionContext:
    """Context for permission checking during execution."""
    
    def __init__(
        self,
        user_id: str,
        execution_id: str,
        permission_manager: PermissionManager
    ):
        self.user_id = user_id
        self.execution_id = execution_id
        self.permission_manager = permission_manager
    
    def check_permission(self, action: PermissionAction, resource: str = None) -> bool:
        """Check if permission is granted."""
        return self.permission_manager.check_permission(
            self.user_id, action, self.execution_id, resource
        )
    
    def request_permission(self, action: PermissionAction, resource: str = None) -> bool:
        """Request permission from user."""
        return self.permission_manager.request_permission(
            self.user_id, action, resource
        )
    
    def set_permission_level(self, level: PermissionLevel) -> None:
        """Set the current permission level."""
        self.permission_manager.set_current_level(level)
