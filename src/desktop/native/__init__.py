"""
Native Windows Layer for Aura AI

Provides a unified, permission-based API for Windows desktop operations.
Aura never calls Win32, psutil, or pyautogui directly - all operations go through
this layer.

Architecture:
- Aura Brain → Desktop Planner → Capability Router → Capability Discovery → Native Pipeline ⭐
- NativePipeline: Unified execution pipeline with middleware chain
- NativeExecutionContext: Shared execution context for all layers
- Verification Layer: Verifies actions completed successfully
- Middleware: Permission, logging, metrics, execution, verification, context
- Rollback Framework: Executable rollback functions for state changes
- Capability Discovery: Search capabilities based on goals (not hardcoded names)
- Native Diagnostics: Detailed timing breakdown for each stage

Layer 1: NativePipeline ⭐ (New)
- Unified execution path for all operations
- Middleware chain orchestration
- Permission and verification checking

Layer 2: Managers
- Specialized managers for each domain (Window, Clipboard, Display, etc.)
- Individual Windows API wrappers

Layer 3: Infrastructure
- CapabilityRegistry: Metadata and descriptions for all capabilities
- NativeResult: Structured result objects with undo support and metrics
- MetricsRecorder: Performance tracking for operations
- DesktopContext: Synchronized state management (source of truth)
- CapabilityRouter: Intermediate routing between Planner and NativeManager
"""

from .capability_discovery import (
    CapabilityDiscovery,
    CapabilityMatchScore,
    GoalIntent,
)
from .capability_registry import (
    CapabilityDescriptor,
    CapabilityRegistry,
    PermissionRequired,
    RiskLevel,
)
from .capability_router import (
    CapabilityRouter,
    RoutingStrategy,
    get_capability_registry,
    get_capability_router,
    get_native_manager,
    reset_capability_router,
)
from .desktop_context import (
    ContextScope,
    DesktopContext,
    get_desktop_context,
    reset_desktop_context,
)
from .desktop_execution_engine import (
    DesktopExecutionEngine,
    get_desktop_execution_engine,
)
from .managers import (
    BaseNativeManager,
    ClipboardManager,
    WindowManager,
)
from .metrics import (
    MetricsLevel,
    MetricsRecorder,
    NativeOperationMetrics,
    get_metrics_recorder,
    reset_metrics_recorder,
)
from .middleware import (
    ContextMiddleware,
    DiagnosticsMiddleware,
    ExecutionResult,
    LoggingMiddleware,
    MetricsMiddleware,
    MiddlewareAction,
    MiddlewareResult,
    MiddlewareType,
    NativeMiddleware,
    NativePipeline,
    PermissionMiddleware,
)
from .native_diagnostics import (
    DiagnosticsReporter,
    DiagnosticsStage,
    NativeDiagnostics,
    StageTiming,
    get_diagnostics,
    reset_diagnostics,
)
from .native_events import (
    EventListener,
    EventType,
    NativeEventBus,
)

# Export exceptions
from .native_exceptions import (
    AudioError,
    CapabilityNotFoundError,
    ClipboardError,
    DisplayError,
    NativeError,
    NetworkError,
    OperationCancelledError,
    OperationTimeoutError,
    PermissionDeniedError,
    PowerError,
    ProcessError,
    RegistryError,
    RollbackError,
    ServiceError,
    VerificationError,
    WindowError,
)
from .native_execution_context import (
    ExecutionContextFactory,
    ExecutionStage,
    ExecutionStatus,
    NativeExecutionContext,
)
from .native_manager import NativeCapability, NativeManager

# Export models
from .native_models import (
    AudioDevice,
    ClipboardData,
    DisplayInfo,
    NetworkInterface,
    ProcessInfo,
    Rect,
    RegistryKey,
    ServiceInfo,
    WindowInfo,
)
from .native_result import ActionCategory, NativeResult, ResultStatus
from .rollback_framework import (
    RollbackAction,
    RollbackContext,
    RollbackFunctions,
    RollbackManager,
    create_rollback_context,
)
from .verification_layer import (
    VerificationLayer,
    VerificationMode,
    VerificationResult,
)

__version__ = "1.0.0"

__all__ = [
    # Main facade
    "NativeManager",
    "NativeCapability",
    # Desktop Execution Engine
    "DesktopExecutionEngine",
    "get_desktop_execution_engine",
    # Pipeline and Execution ⭐ NEW
    "NativePipeline",
    "NativeExecutionContext",
    "ExecutionStage",
    "ExecutionStatus",
    "ExecutionContextFactory",
    # Verification ⭐ NEW
    "VerificationLayer",
    "VerificationResult",
    "VerificationMode",
    # Middleware ⭐ NEW
    "NativeMiddleware",
    "MiddlewareType",
    "MiddlewareResult",
    "MiddlewareAction",
    "ExecutionResult",
    "PermissionMiddleware",
    "LoggingMiddleware",
    "MetricsMiddleware",
    "ContextMiddleware",
    "DiagnosticsMiddleware",
    # Rollback Framework ⭐ NEW
    "RollbackManager",
    "RollbackFunctions",
    "RollbackContext",
    "RollbackAction",
    "create_rollback_context",
    # Capability Discovery ⭐ NEW
    "CapabilityDiscovery",
    "GoalIntent",
    "CapabilityMatchScore",
    # Diagnostics ⭐ NEW
    "NativeDiagnostics",
    "DiagnosticsStage",
    "StageTiming",
    "DiagnosticsReporter",
    "get_diagnostics",
    "reset_diagnostics",
    # Registry
    "CapabilityRegistry",
    "CapabilityDescriptor",
    "PermissionRequired",
    "RiskLevel",
    # Results
    "NativeResult",
    "ResultStatus",
    "ActionCategory",
    # Metrics
    "MetricsRecorder",
    "NativeOperationMetrics",
    "MetricsLevel",
    "get_metrics_recorder",
    "reset_metrics_recorder",
    # Desktop Context
    "DesktopContext",
    "ContextScope",
    "get_desktop_context",
    "reset_desktop_context",
    # Router
    "CapabilityRouter",
    "RoutingStrategy",
    "get_capability_router",
    "reset_capability_router",
    "get_native_manager",
    "get_capability_registry",
    # Events
    "EventType",
    "NativeEventBus",
    "EventListener",
    # Managers
    "WindowManager",
    "ClipboardManager",
    "DisplayManager",
    "PowerManager",
    "AudioManager",
    "NetworkManager",
    "RegistryManager",
    "ServiceManager",
    # Models
    "WindowInfo",
    "ProcessInfo",
    "ClipboardData",
    "DisplayInfo",
    "AudioDevice",
    "NetworkInterface",
    "RegistryKey",
    "ServiceInfo",
    "Rect",
    # Exceptions
    "NativeError",
    "WindowError",
    "ProcessError",
    "ClipboardError",
    "DisplayError",
    "PowerError",
    "AudioError",
    "NetworkError",
    "RegistryError",
    "ServiceError",
    "CapabilityNotFoundError",
    "PermissionDeniedError",
    "OperationTimeoutError",
    "OperationCancelledError",
    "VerificationError",
    "RollbackError",
    # Managers
    "BaseNativeManager",
    "WindowManager",
    "ClipboardManager",
    "DisplayManager",
    "AudioManager",
    "PowerManager",
    "NetworkManager",
    "ServiceManager",
    "RegistryManager",
]
