"""
Routing Module

Main entry point for the routing system.

Provides capability routing, workflow orchestration, and plugin discovery.
"""

from core.backends import BackendRegistry
from core.orchestration import (
    PlannerRegistry,
    PlannerRole,
    SubTask,
    TaskDecomposer,
    TaskGraph,
)

from .capability_router import CapabilityRouter
from .capability_types import CapabilityCategory, CapabilityPriority, CapabilityType
from .plugin_registry import PluginCapability, PluginRegistry
from .routing_result import RoutingResult
from .workflow_orchestrator import WorkflowOrchestrator, WorkflowStep

__all__ = [
    "CapabilityType",
    "CapabilityPriority",
    "CapabilityCategory",
    "RoutingResult",
    "CapabilityRouter",
    "WorkflowOrchestrator",
    "WorkflowStep",
    "PluginRegistry",
    "PluginCapability",
    "TaskDecomposer",
    "TaskGraph",
    "SubTask",
    "PlannerRole",
    "PlannerRegistry",
    "BackendRegistry",
]
