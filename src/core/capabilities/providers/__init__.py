"""
Domain Capability Providers Package
===================================
Location: src/core/capabilities/providers/
"""

from core.capabilities.providers.browser_provider import BrowserCapabilityProvider
from core.capabilities.providers.coding_provider import CodingCapabilityProvider
from core.capabilities.providers.desktop_provider import DesktopCapabilityProvider
from core.capabilities.providers.memory_provider import MemoryCapabilityProvider
from core.capabilities.providers.research_provider import ResearchCapabilityProvider

__all__ = [
    "DesktopCapabilityProvider",
    "CodingCapabilityProvider",
    "BrowserCapabilityProvider",
    "MemoryCapabilityProvider",
    "ResearchCapabilityProvider",
]
