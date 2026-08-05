"""
Capability Types

Defines all possible capabilities Aura can handle.
Each request maps to one or more capabilities.
"""

from enum import Enum


class CapabilityType(str, Enum):
    """
    All possible capabilities Aura can handle.

    Each capability represents a distinct domain of functionality.
    Requests are routed to the most appropriate capability based on
    the request's intent and context.
    """

    # Local OS capabilities
    DESKTOP = "desktop"
    FILESYSTEM = "filesystem"
    TERMINAL = "terminal"
    BROWSER = "browser"
    NETWORK = "network"

    # Input/Output capabilities
    VISION = "vision"
    VOICE = "voice"
    CLIPBOARD = "clipboard"

    # Knowledge and Memory
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    DATABASE = "database"

    # AI and Processing
    PROVIDER = "provider"  # LLM provider
    AGENT = "agent"  # Agent-based tasks
    WORKFLOW = "workflow"

    # Plugin-based capabilities
    PLUGIN = "plugin"
    PLUGIN_SEARCH = "plugin_search"

    # System capabilities
    SYSTEM = "system"
    SETTINGS = "settings"


class CapabilityPriority(str, Enum):
    """
    Priority levels for capabilities.

    Higher priority capabilities are attempted first.
    This ensures fast responses and avoids unnecessary LLM calls.
    """

    HIGHEST = "highest"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    LOWEST = "lowest"


class CapabilityCategory(str, Enum):
    """
    High-level categories for grouping capabilities.
    """

    LOCAL = "local"  # OS-level operations
    PLUGIN = "plugin"  # Plugin-based operations
    KNOWLEDGE = "knowledge"  # Knowledge retrieval and storage
    PROCESSING = "processing"  # AI processing
    SYSTEM = "system"  # System operations
