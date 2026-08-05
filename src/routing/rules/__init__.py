"""
Routing Rules

Individual rule sets for different capabilities.
"""

from .browser_rules import BrowserRules
from .desktop_rules import DesktopRules
from .filesystem_rules import FilesystemRules
from .knowledge_rules import KnowledgeRules
from .memory_rules import MemoryRules
from .vision_rules import VisionRules

__all__ = [
    "DesktopRules",
    "FilesystemRules",
    "BrowserRules",
    "VisionRules",
    "MemoryRules",
    "KnowledgeRules",
]
