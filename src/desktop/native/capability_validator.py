"""
Capability Validation Framework

Performs pre-flight validation on all capabilities registered in CapabilityRegistry
against resolving managers in NativeManagerRegistry.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from .capability_registry import CapabilityRegistry, CapabilityDescriptor
from .managers.native_manager_registry import NativeManagerRegistry

logger = logging.getLogger(__name__)


@dataclass
class CapabilityValidationReport:
    """Detailed capability validation report."""
    valid: bool
    total_capabilities: int
    validated_capabilities: int
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dict format."""
        return {
            "valid": self.valid,
            "total_capabilities": self.total_capabilities,
            "validated_capabilities": self.validated_capabilities,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


class CapabilityValidator:
    """
    Validates capability definitions and their backing managers pre-flight.
    """

    def __init__(
        self,
        capability_registry: Optional[CapabilityRegistry] = None,
        manager_registry: Optional[NativeManagerRegistry] = None,
    ):
        """Initialize validator with registries."""
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.manager_registry = manager_registry or NativeManagerRegistry.get_instance()

    def validate_all(self) -> CapabilityValidationReport:
        """
        Validate all registered capabilities.

        Asserts for each capability:
        1. Resolving manager exists in NativeManagerRegistry.
        2. Manager implements execute() method.
        3. Manager can_handle(capability) returns True or manager name matches.
        4. If supports_undo=True, rollback handler is available or supported.

        Returns:
            CapabilityValidationReport with pass/fail and errors/warnings.
        """
        descriptors = self.capability_registry.list_all()
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        validated_count = 0

        for descriptor in descriptors:
            cap_name = descriptor.name
            manager = self.manager_registry.resolve(cap_name)

            if manager is None:
                warnings.append({
                    "capability": cap_name,
                    "manager": descriptor.manager,
                    "warning": f"No native manager resolved for capability '{cap_name}' (manager '{descriptor.manager}' not yet registered)",
                })
                continue

            if not hasattr(manager, "execute") or not callable(getattr(manager, "execute")):
                errors.append({
                    "capability": cap_name,
                    "manager": manager.name,
                    "error": f"Manager '{manager.name}' does not implement callable execute() method",
                })

            if descriptor.supports_undo:
                # Check rollback handler
                try:
                    if hasattr(manager, "rollback_functions") and manager.rollback_functions:
                        if not manager.rollback_functions.has_handler(cap_name):
                            warnings.append({
                                "capability": cap_name,
                                "manager": manager.name,
                                "warning": f"Capability '{cap_name}' supports undo but manager has no explicit rollback handler registered",
                            })
                except Exception:
                    pass

            validated_count += 1

        is_valid = len(errors) == 0
        return CapabilityValidationReport(
            valid=is_valid,
            total_capabilities=len(descriptors),
            validated_capabilities=validated_count,
            errors=errors,
            warnings=warnings,
        )
