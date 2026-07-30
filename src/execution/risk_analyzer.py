"""
Tool Execution Engine - Risk Analysis

This module analyzes the risk level of tool operations to determine
what level of permission and confirmation is required.
"""


from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from .permission_manager import PermissionLevel, REQUIRED_PERMISSIONS


class RiskLevel(Enum):
    """Risk level enumeration."""
    LOW = "low"           # Safe operations, no confirmation needed
    MEDIUM = "medium"     # Moderate risk, confirmation recommended
    HIGH = "high"         # High risk, confirmation required
    CRITICAL = "critical" # Critical risk, explicit confirmation required


# Risk mappings: what risk level for each operation
OPERATION_RISK = {
    "read_file": RiskLevel.LOW,
    "write_file": RiskLevel.MEDIUM,
    "delete_file": RiskLevel.HIGH,
    "rename_file": RiskLevel.MEDIUM,
    "create_file": RiskLevel.MEDIUM,
    "search_files": RiskLevel.LOW,
    "execute_command": RiskLevel.MEDIUM,
    "browser_open": RiskLevel.LOW,
    "git_commit": RiskLevel.MEDIUM,
    "git_push": RiskLevel.HIGH,
    "git_force_push": RiskLevel.CRITICAL,
    "git_reset": RiskLevel.HIGH,
    "git_revert": RiskLevel.MEDIUM,
    "shutdown_system": RiskLevel.CRITICAL,
    "restart_system": RiskLevel.HIGH,
    "format_disk": RiskLevel.CRITICAL,
    "delete_system32": RiskLevel.CRITICAL,
    "modify_registry": RiskLevel.HIGH,
    "delete_registry_key": RiskLevel.HIGH,
    "modify_registry_key": RiskLevel.HIGH,
    "open_application": RiskLevel.MEDIUM,
    "close_application": RiskLevel.MEDIUM,
    "access_clipboard": RiskLevel.LOW,
    "network_access": RiskLevel.MEDIUM,
    "network_send_email": RiskLevel.MEDIUM,
    "calendar_modify": RiskLevel.MEDIUM,
    "delete_calendar_event": RiskLevel.MEDIUM,
    "docker_build": RiskLevel.MEDIUM,
    "docker_run": RiskLevel.HIGH,
    "docker_remove": RiskLevel.MEDIUM,
    "docker_kill": RiskLevel.HIGH,
    "docker-compose_up": RiskLevel.MEDIUM,
    "docker-compose_down": RiskLevel.HIGH,
    "mcp_execute": RiskLevel.MEDIUM,
}


class RiskAnalyzer:
    """Analyzes the risk level of tool operations."""
    
    def __init__(self, require_confirmation: bool = True):
        """
        Initialize the risk analyzer.
        
        Args:
            require_confirmation: If True, high/critical risks require confirmation
        """
        self.require_confirmation = require_confirmation
        self._risk_cache: Dict[str, Tuple[RiskLevel, List[str]]] = {}
    
    def analyze_operation(
        self,
        tool_name: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Tuple[RiskLevel, List[str]]:
        """
        Analyze the risk level of a specific operation.
        
        Args:
            tool_name: Name of the tool
            operation: Name of the operation
            parameters: Operation parameters
            
        Returns:
            Tuple of (risk_level, risk_factors)
        """
        # Create cache key
        cache_key = f"{tool_name}:{operation}:{str(parameters)}"
        
        # Check cache
        if cache_key in self._risk_cache:
            return self._risk_cache[cache_key]
        
        # Determine base risk from operation
        base_operation = operation.lower()
        base_risk = self._get_base_risk(base_operation)
        
        # Analyze parameters for additional risk factors
        risk_factors = self._analyze_parameters(tool_name, operation, parameters)
        
        # Determine final risk level
        final_risk = self._determine_final_risk(base_risk, risk_factors)
        
        # Cache the result
        self._risk_cache[cache_key] = (final_risk, risk_factors)
        
        return final_risk, risk_factors
    
    def _get_base_risk(self, operation: str) -> RiskLevel:
        """Get the base risk level for an operation."""
        return OPERATION_RISK.get(operation, RiskLevel.MEDIUM)
    
    def _analyze_parameters(
        self,
        tool_name: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> List[str]:
        """Analyze parameters for additional risk factors."""
        risk_factors = []
        
        # Check for destructive operations
        if operation in ["delete_file", "delete_registry_key"]:
            if "force" in parameters:
                risk_factors.append("Force delete flag present")
            if "recursive" in parameters:
                risk_factors.append("Recursive deletion")
        
        # Check for system-level operations
        if operation in ["shutdown_system", "restart_system", "format_disk"]:
            risk_factors.append("System-level operation")
            if "force" in parameters:
                risk_factors.append("Force operation flag present")
        
        # Check for multiple file operations
        if operation in ["delete_file", "write_file"]:
            file_count = parameters.get("files", [])
            if isinstance(file_count, list):
                risk_factors.append(f"Multiple files affected: {len(file_count)}")
            elif isinstance(file_count, str):
                risk_factors.append("Single file affected")
            elif file_count is not None:
                risk_factors.append(f"{file_count} files affected")
        
        # Check for network operations
        if operation in ["network_access", "network_send_email"]:
            if "remote" in parameters or "remote_host" in parameters:
                risk_factors.append("Remote operation")
            if "force" in parameters:
                risk_factors.append("Force network operation")
        
        # Check for admin operations
        if operation in ["execute_command"]:
            command = parameters.get("command", "")
            if "sudo" in command.lower() or "rm -rf" in command.lower():
                risk_factors.append("Potentially destructive command")
            if "delete" in command.lower() or "remove" in command.lower():
                risk_factors.append("File deletion in command")
        
        return risk_factors
    
    def _determine_final_risk(
        self,
        base_risk: RiskLevel,
        risk_factors: List[str]
    ) -> RiskLevel:
        """
        Determine the final risk level based on base risk and additional factors.
        
        Args:
            base_risk: Base risk level from operation
            risk_factors: List of risk factors
            
        Returns:
            Final risk level
        """
        if not risk_factors:
            return base_risk
        
        # Add factors to base risk
        additional_risk = RiskLevel.LOW
        
        for factor in risk_factors:
            if "force" in factor.lower():
                if base_risk == RiskLevel.MEDIUM:
                    additional_risk = RiskLevel.HIGH
                elif base_risk == RiskLevel.LOW:
                    additional_risk = RiskLevel.MEDIUM
            elif "multiple" in factor.lower() or "recursive" in factor.lower():
                if base_risk == RiskLevel.MEDIUM:
                    additional_risk = RiskLevel.HIGH
            elif "system-level" in factor.lower() or "remote" in factor.lower():
                if base_risk == RiskLevel.MEDIUM:
                    additional_risk = RiskLevel.HIGH
                elif base_risk == RiskLevel.LOW:
                    additional_risk = RiskLevel.MEDIUM
        
        # Combine risks (higher level wins)
        return max(base_risk, additional_risk)
    
    def check_if_confirmation_required(
        self,
        tool_name: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, RiskLevel, List[str]]:
        """
        Check if confirmation is required for an operation.
        
        Args:
            tool_name: Name of the tool
            operation: Name of the operation
            parameters: Operation parameters
            
        Returns:
            Tuple of (requires_confirmation, risk_level, risk_factors)
        """
        risk_level, risk_factors = self.analyze_operation(tool_name, operation, parameters)
        
        # Determine if confirmation is required
        requires_confirmation = False
        
        if self.require_confirmation:
            if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                requires_confirmation = True
            elif risk_level == RiskLevel.MEDIUM and self._has_destructive_factors(risk_factors):
                requires_confirmation = True
        
        return requires_confirmation, risk_level, risk_factors
    
    def _has_destructive_factors(self, risk_factors: List[str]) -> bool:
        """Check if risk factors indicate destructive behavior."""
        destructive_keywords = ["delete", "remove", "force", "recursive", "system-level"]
        return any(keyword in factor.lower() for factor in risk_factors for keyword in destructive_keywords)
    
    def get_risk_level_name(self, risk_level: RiskLevel) -> str:
        """Get the human-readable name of a risk level."""
        return risk_level.name
    
    def get_risk_description(self, risk_level: RiskLevel) -> str:
        """Get a description of what each risk level means."""
        descriptions = {
            RiskLevel.LOW: "Low risk: Safe operations with no data loss expected",
            RiskLevel.MEDIUM: "Medium risk: Operations that could affect data or system state",
            RiskLevel.HIGH: "High risk: Operations that could cause data loss or system instability",
            RiskLevel.CRITICAL: "Critical risk: Operations that could damage system or cause data loss"
        }
        return descriptions.get(risk_level, "Unknown risk level")
    
    def get_risk_recommendations(
        self,
        tool_name: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> List[str]:
        """
        Get safety recommendations for an operation.
        
        Args:
            tool_name: Name of the tool
            operation: Name of the operation
            parameters: Operation parameters
            
        Returns:
            List of safety recommendations
        """
        _, risk_factors = self.analyze_operation(tool_name, operation, parameters)
        
        recommendations = []
        
        for factor in risk_factors:
            if "force" in factor.lower():
                recommendations.append("⚠️  Consider using force flag only if absolutely necessary")
            if "multiple" in factor.lower() or "recursive" in factor.lower():
                recommendations.append("⚠️  Review affected files carefully before proceeding")
            if "system-level" in factor.lower():
                recommendations.append("⚠️  System-level operations should be reviewed with care")
            if "remote" in factor.lower():
                recommendations.append("⚠️  Verify remote host before proceeding")
            if "potentially destructive" in factor.lower():
                recommendations.append("⚠️  Consider using backup before executing")
        
        return recommendations
    
    def clear_cache(self) -> None:
        """Clear the risk analysis cache."""
        self._risk_cache.clear()
    
    def reset_to_defaults(self) -> None:
        """Reset analyzer to default settings."""
        self._risk_cache.clear()
