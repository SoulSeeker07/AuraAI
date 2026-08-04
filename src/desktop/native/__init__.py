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

from .native_manager import NativeManager, NativeCapability
from .capability_registry import (
    CapabilityRegistry,
    CapabilityDescriptor,
    PermissionRequired,
    RiskLevel,
)
from .native_result import NativeResult, ResultStatus, ActionCategory
from .metrics import (
    MetricsRecorder,
    NativeOperationMetrics,
    MetricsLevel,
    get_metrics_recorder,
    reset_metrics_recorder,
)
from .desktop_context import (
    DesktopContext,
    ContextScope,
    get_desktop_context,
    reset_desktop_context,
)
from .capability_router import (
    CapabilityRouter,
    RoutingStrategy,
    get_capability_router,
    reset_capability_router,
    get_native_manager,
    get_capability_registry,
)
from .native_events import (
    EventType,
    NativeEventBus,
    EventListener,
)
from .native_execution_context import (
    NativeExecutionContext,
    ExecutionStage,
    ExecutionStatus,
    ExecutionContextFactory,
)
from .verification_layer import (
    VerificationLayer,
    VerificationResult,
    VerificationMode,
)
from .middleware import (
    NativeMiddleware,
    MiddlewareType,
    MiddlewareResult,
    ExecutionResult,
    PermissionMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
    ContextMiddleware,
    DiagnosticsMiddleware,
    NativePipeline,
)
from .rollback_framework import (
    RollbackManager,
    RollbackFunctions,
    RollbackContext,
    RollbackAction,
    create_rollback_context,
)
from .capability_discovery import (
    CapabilityDiscovery,
    GoalIntent,
    CapabilityMatchScore,
)
from .native_diagnostics import (
    NativeDiagnostics,
    DiagnosticsStage,
    StageTiming,
    DiagnosticsReporter,
    get_diagnostics,
    reset_diagnostics,
)

# Export managers
from .window_manager import WindowManager
from .clipboard_manager import ClipboardManager
from .display_manager import DisplayManager
from .power_manager import PowerManager
from .audio_manager import AudioManager
from .network_manager import NetworkManager
from .registry_manager import RegistryManager
from .service_manager import ServiceManager

# Export models
from .native_models import (
    WindowInfo,
    ProcessInfo,
    ClipboardData,
    DisplayInfo,
    AudioDevice,
    NetworkInterface,
    RegistryKey,
    ServiceInfo,
    Rect,
)

# Export exceptions
from .native_exceptions import (
    NativeError,
    WindowError,
    ProcessError,
    ClipboardError,
    DisplayError,
    PowerError,
    AudioError,
    NetworkError,
    RegistryError,
    ServiceError,
    CapabilityNotFoundError,
    PermissionDeniedError,
    OperationTimeoutError,
    OperationCancelledError,
)

__version__ = "1.0.0"

__all__ = [
    # Main facade
    "NativeManager",
    "NativeCapability",
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
]
