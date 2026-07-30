"""
Routing Rules

Individual rule sets for different capabilities.
"""

from .desktop_rules import DesktopRules
from .filesystem_rules import FilesystemRules
from .browser_rules import BrowserRules
from .vision_rules import VisionRules
from .memory_rules import MemoryRules
from .knowledge_rules import KnowledgeRules

__all__ = [
    "DesktopRules",
    "FilesystemRules",
    "BrowserRules",
    "VisionRules",
    "MemoryRules",
    "KnowledgeRules",
]
