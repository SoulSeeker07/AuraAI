"""
Base Manager Contract for Native Windows Layer

Defines the strict contract that all native managers must implement.
This makes managers interchangeable and enables plugin architectures.

Every manager follows the same lifecycle:
1. register_capabilities() - Define what the manager can do
2. execute() - Execute the native operation (Windows-specific)
3. verify() - Verify the action completed successfully (optional, automated)
4. rollback() - Rollback the action if needed (optional, automated)

Architecture:
- Aura Brain → Desktop Planner → NativeManager → Capability Router → NativePipeline
- NativePipeline handles: permissions, logging, metrics, context, verification, rollback, diagnostics
- Managers only handle: Windows-specific execution logic
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..native_execution_context import NativeExecutionContext
from ..native_result import NativeResult
from ..native_exceptions import NativeError
from ..verification_layer import VerificationLayer
from ..rollback_framework import RollbackFunctions


class BaseNativeManager(ABC):
    """
    Abstract base class for all native desktop managers.

    All managers must implement this contract to be interchangeable in the
    execution pipeline. The pipeline handles all cross-cutting concerns
    (permissions, logging, metrics, verification, rollback, diagnostics).
    """

    def __init__(self):
        """Initialize the manager with capability registry and verification layer."""
        self._capabilities: List[str] = []
        self._verification_layer: Optional[VerificationLayer] = None
        self._rollback_functions: Optional[RollbackFunctions] = None

    @property
    def capabilities(self) -> List[str]:
        """
        Get list of capabilities this manager can handle.

        Returns:
            List of capability names this manager supports.

        Example:
            >>> manager = WindowManager()
            >>> manager.capabilities
            ['window.activate', 'window.close', 'window.resize']
        """
        return self._capabilities.copy()

    @property
    def verification_layer(self) -> VerificationLayer:
        """
        Get the verification layer for this manager.

        Returns:
            VerificationLayer instance with registered handlers.

        Raises:
            NativeError: If verification layer not initialized.
        """
        if self._verification_layer is None:
            raise NativeError(
                "Verification layer not initialized. Call register_capabilities() first."
            )
        return self._verification_layer

    @property
    def rollback_functions(self) -> RollbackFunctions:
        """
        Get rollback functions for this manager.

        Returns:
            RollbackFunctions instance with registered rollback handlers.

        Raises:
            NativeError: If rollback functions not initialized.
        """
        if self._rollback_functions is None:
            raise NativeError(
                "Rollback functions not initialized. Call register_capabilities() first."
            )
        return self._rollback_functions

    def register_capabilities(
        self,
        capabilities: List[str],
        verification_handlers: Optional[Dict[str, callable]] = None,
        rollback_handlers: Optional[Dict[str, callable]] = None,
    ) -> None:
        """
        Register capabilities with verification and rollback handlers.

        Args:
            capabilities: List of capability names this manager supports.
            verification_handlers: Optional dict mapping capability to verify function.
            rollback_handlers: Optional dict mapping capability to rollback function.

        Raises:
            NativeError: If capability name is invalid or duplicates already registered.

        Example:
            >>> handlers = {
            ...     'window.activate': lambda ctx: ctx.verification_layer.verify_window_activated(),
            ...     'window.close': lambda ctx: ctx.verification_layer.verify_window_closed(),
            ... }
            >>> rollback_handlers = {
            ...     'window.activate': lambda ctx: ctx.rollback_functions.rollback_window_activated(),
            ... }
            >>> manager.register_capabilities(['window.activate', 'window.close'], handlers, rollback_handlers)
        """
        # Validate capability names
        for capability in capabilities:
            if not capability or not isinstance(capability, str):
                raise NativeError(
                    f"Invalid capability name: {capability}. Must be non-empty string."
                )

            # Check for duplicates
            if capability in self._capabilities:
                raise NativeError(
                    f"Capability '{capability}' already registered. "
                    "Each capability must be unique."
                )

        # Register capabilities
        self._capabilities.extend(capabilities)

        # Register verification handlers
        if verification_handlers:
            for capability, handler in verification_handlers.items():
                if capability not in self._capabilities:
                    raise NativeError(
                        f"Cannot register verification handler for unknown capability '{capability}'. "
                        "Must be registered in capabilities list first."
                    )

                if not callable(handler):
                    raise NativeError(
                        f"Verification handler for '{capability}' must be callable."
                    )

                self._verification_layer.register_handler(capability, handler)

        # Register rollback handlers
        if rollback_handlers:
            for capability, handler in rollback_handlers.items():
                if capability not in self._capabilities:
                    raise NativeError(
                        f"Cannot register rollback handler for unknown capability '{capability}'. "
                        "Must be registered in capabilities list first."
                    )

                if not callable(handler):
                    raise NativeError(
                        f"Rollback handler for '{capability}' must be callable."
                    )

                self._rollback_functions.register_handler(capability, handler)

    @abstractmethod
    def execute(
        self,
        capability: str,
        context: NativeExecutionContext,
    ) -> NativeResult:
        """
        Execute the native operation for the given capability.

        This is the ONLY method that contains Windows-specific code.
        All other concerns are handled by the pipeline.

        Args:
            capability: Name of capability to execute.
            context: NativeExecutionContext with permission, metrics, and verification state.

        Returns:
            NativeResult with execution status and result data.

        Raises:
            NativeError: If capability not supported or execution fails.

        Example:
            >>> context = ExecutionContextFactory.create()
            >>> result = window_manager.execute('window.activate', context)
            >>> if result.success:
            ...     print("Window activated successfully")
            ... else:
            ...     print(f"Failed: {result.error}")
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute() method."
        )

    def can_handle(self, capability: str) -> bool:
        """
        Check if this manager can handle the given capability.

        Args:
            capability: Capability name to check.

        Returns:
            True if this manager can handle the capability.

        Example:
            >>> manager = WindowManager()
            >>> manager.can_handle('window.activate')
            True
            >>> manager.can_handle('clipboard.copy')
            False
        """
        return capability in self._capabilities

    def verify(self, result: NativeResult) -> bool:
        """
        Verify that the action completed successfully.

        This is an optional method for managers that need custom verification.
        Most managers will rely on the automatic verification layer.

        Args:
            result: NativeResult from execute().

        Returns:
            True if verification passed, False otherwise.

        Example:
            >>> result = manager.execute('window.activate', context)
            >>> if manager.verify(result):
            ...     print("Verification passed")
        """
        return result.success

    def rollback(self, result: NativeResult, context: NativeExecutionContext) -> bool:
        """
        Rollback the action if it was successful.

        This is an optional method for managers that need custom rollback logic.
        Most managers will rely on the automatic rollback framework.

        Args:
            result: NativeResult from execute().
            context: NativeExecutionContext for rollback context.

        Returns:
            True if rollback succeeded, False otherwise.

        Example:
            >>> result = manager.execute('window.activate', context)
            >>> if result.success and manager.rollback(result, context):
            ...     print("Rollback successful")
        """
        return True

    def get_capability_details(self, capability: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a capability.

        Args:
            capability: Capability name.

        Returns:
            Dict with capability details or None if capability not found.
        """
        return {
            "name": capability,
            "manager": self.__class__.__name__,
            "supported": self.can_handle(capability),
        }

    def list_all_capabilities(self) -> List[Dict[str, Any]]:
        """
        Get details for all capabilities this manager supports.

        Returns:
            List of dicts with capability details.
        """
        return [
            self.get_capability_details(capability)
            for capability in self._capabilities
        ]

    def __repr__(self) -> str:
        """String representation of the manager."""
        return f"{self.__class__.__name__}(capabilities={len(self._capabilities)})"
