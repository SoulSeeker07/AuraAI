"""
Domain Runtime Sessions (Browser, Desktop, Research)
Location: src/core/orchestration/domain_sessions.py

Specialized session classes for Browser, Desktop, and Research domains,
all inheriting from the unified RuntimeSession base class.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from .runtime_session import RuntimeSession


@dataclass
class BrowserSession(RuntimeSession):
    """Long-running browser automation session."""

    domain: str = "browser"
    target_url: str = ""
    open_tabs: list[str] = field(default_factory=list)
    active_tab: str = ""

    def __post_init__(self):
        if not self.session_id.startswith("browser_"):
            self.session_id = f"browser_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "target_url": self.target_url,
                "open_tabs": self.open_tabs,
                "active_tab": self.active_tab,
            }
        )
        return data


@dataclass
class DesktopSession(RuntimeSession):
    """Long-running desktop window / process manipulation session."""

    domain: str = "desktop"
    target_app: str = ""
    active_hwnd: int = 0
    window_state: str = "NORMAL"  # "NORMAL", "MINIMIZED", "MAXIMIZED", "CLOSED"

    def __post_init__(self):
        if not self.session_id.startswith("desktop_"):
            self.session_id = f"desktop_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "target_app": self.target_app,
                "active_hwnd": self.active_hwnd,
                "window_state": self.window_state,
            }
        )
        return data


@dataclass
class ResearchSession(RuntimeSession):
    """Long-running research investigation session."""

    domain: str = "research"
    sources_crawled: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.session_id.startswith("research_"):
            self.session_id = f"research_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "sources_crawled": self.sources_crawled,
                "findings": self.findings,
            }
        )
        return data
