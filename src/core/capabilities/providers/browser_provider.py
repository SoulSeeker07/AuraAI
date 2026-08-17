"""
Browser Capability Provider
===========================
Location: src/core/capabilities/providers/browser_provider.py

Provides capability descriptors for the Browser automation subsystem (Playwright).
Marked as scaffolded contracts (is_live=False) until M22 operational wiring is complete.
"""

from __future__ import annotations

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


class BrowserCapabilityProvider(ICapabilityProvider):
    """Provider for browser automation and web interaction capabilities."""

    DOMAIN = "browser"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = self._build_capabilities()

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def _build_capabilities(self) -> dict[str, Capability]:
        caps = [
            Capability(
                name="browser.open",
                domain=self.DOMAIN,
                description="Launch or connect to a Playwright browser session.",
                category="session",
                input_schema={
                    "type": "object",
                    "properties": {"headless": {"type": "boolean", "default": True}},
                },
                output_schema={
                    "type": "object",
                    "properties": {"session_id": {"type": "string"}},
                },
                risk_level=ActionRisk.LOW,
                permissions=["browser:session"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=[],
                verifies=["browser.observe"],
                tags=["browser", "session", "live"],
            ),
            Capability(
                name="browser.navigate",
                domain=self.DOMAIN,
                description="Navigate current browser page to a target URL.",
                category="navigation",
                input_schema={
                    "type": "object",
                    "required": ["url"],
                    "properties": {"url": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "url": {"type": "string"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["network:http"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=["browser.open"],
                verifies=["browser.observe"],
                tags=["browser", "navigation", "live"],
            ),
            Capability(
                name="browser.find_element",
                domain=self.DOMAIN,
                description="Find and resolve a unique DOM element matching a CSS or text selector.",
                category="inspection",
                input_schema={
                    "type": "object",
                    "required": ["selector"],
                    "properties": {"selector": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                        "element": {"type": "object"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["browser:read"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=["browser.navigate"],
                verifies=[],
                tags=["browser", "find", "live"],
            ),
            Capability(
                name="browser.click",
                domain=self.DOMAIN,
                description="Click a DOM element identified by CSS selector or XPath, requiring confirmation for destructive actions.",
                category="interaction",
                input_schema={
                    "type": "object",
                    "required": ["selector"],
                    "properties": {"selector": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {"clicked": {"type": "boolean"}},
                },
                risk_level=ActionRisk.HIGH,
                is_destructive=True,
                requires_confirmation=True,
                permissions=["browser:interact"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=["browser.navigate"],
                verifies=["browser.observe"],
                tags=["browser", "click", "mutation", "live"],
            ),
            Capability(
                name="browser.type",
                domain=self.DOMAIN,
                description="Fill or type text into a web input field, requiring confirmation for destructive input.",
                category="interaction",
                input_schema={
                    "type": "object",
                    "required": ["selector", "text"],
                    "properties": {
                        "selector": {"type": "string"},
                        "text": {"type": "string"},
                        "clear": {"type": "boolean", "default": True},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {"success": {"type": "boolean"}},
                },
                risk_level=ActionRisk.HIGH,
                is_destructive=True,
                requires_confirmation=True,
                permissions=["browser:interact"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=["browser.navigate"],
                verifies=["browser.observe"],
                tags=["browser", "type", "mutation", "live"],
            ),
            Capability(
                name="browser.submit",
                domain=self.DOMAIN,
                description="Submit a web form or press Enter on targeted element, requiring confirmation.",
                category="interaction",
                input_schema={
                    "type": "object",
                    "properties": {"selector": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {"submitted": {"type": "boolean"}},
                },
                risk_level=ActionRisk.HIGH,
                is_destructive=True,
                requires_confirmation=True,
                permissions=["browser:interact"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=["browser.navigate"],
                verifies=["browser.observe"],
                tags=["browser", "submit", "mutation", "live"],
            ),
            Capability(
                name="browser.extract",
                domain=self.DOMAIN,
                description="Extract structured text, markdown, or table data from the active page.",
                category="extraction",
                input_schema={
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "format": {"type": "string", "default": "markdown"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                },
                risk_level=ActionRisk.LOW,
                permissions=["browser:read"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=["browser.navigate"],
                verifies=[],
                tags=["browser", "extract", "live"],
            ),
            Capability(
                name="browser.observe",
                domain=self.DOMAIN,
                description="Capture current page DOM accessibility tree, snapshot, or title.",
                category="observation",
                input_schema={"type": "object", "properties": {}},
                output_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["browser:read"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=["browser.open"],
                verifies=[],
                tags=["browser", "observe", "live"],
            ),
            Capability(
                name="browser.close",
                domain=self.DOMAIN,
                description="Close active browser session and cleanup page instances.",
                category="session",
                input_schema={"type": "object", "properties": {}},
                output_schema={
                    "type": "object",
                    "properties": {"closed": {"type": "boolean"}},
                },
                risk_level=ActionRisk.LOW,
                permissions=["browser:session"],
                execution_backend="browser",
                is_live=True,
                availability="available",
                requires=[],
                verifies=[],
                tags=["browser", "close", "live"],
            ),
        ]
        return {cap.name: cap for cap in caps}

    def list_capabilities(self) -> list[Capability]:
        return list(self._capabilities.values())

    def get_capability(self, name: str) -> Capability | None:
        return self._capabilities.get(name)
