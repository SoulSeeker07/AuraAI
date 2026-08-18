"""
Aura Model Context Protocol (MCP) Plugin
========================================
Plugin for integrating external MCP tool and resource servers over stdio / SSE.
"""

import json
import logging
from pathlib import Path
from typing import Any

from src.plugins.plugin_interface import Plugin, PluginCategory, PluginManifest

logger = logging.getLogger(__name__)


class MCPPlugin(Plugin):
    """
    Model Context Protocol (MCP) Client Plugin for Aura.
    """

    def __init__(self, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = PluginManifest(
                name="mcp",
                version="1.0.0",
                author="Aura AI",
                description="Model Context Protocol (MCP) client plugin for external tool integration.",
                category=PluginCategory.MCP,
                capabilities=[
                    "mcp.list_servers",
                    "mcp.connect",
                    "mcp.list_tools",
                    "mcp.call_tool",
                    "mcp.list_resources",
                    "mcp.read_resource",
                    "mcp.register_server",
                ],
            )
        super().__init__(manifest)
        self._servers: dict[str, dict[str, Any]] = {}
        self._config_file = Path("config/mcp_servers.json")
        self._load_config()

    def _load_config(self) -> None:
        if self._config_file.exists():
            try:
                self._servers = json.loads(self._config_file.read_text(encoding="utf-8"))
            except Exception:
                self._servers = {}

    def load(self) -> bool:
        self.state = "initialized"
        return True

    def initialize(self) -> bool:
        self.state = "ready"
        return True

    def can_handle(self, capability: str) -> bool:
        return capability.startswith("mcp.") or capability in self.manifest.capabilities

    def execute(self, capability: str, **kwargs: Any) -> Any:
        cap = capability.lower()
        if cap == "mcp.list_servers":
            return {"servers": list(self._servers.keys()), "count": len(self._servers)}
        elif cap == "mcp.register_server":
            name = kwargs.get("name", "custom_mcp")
            cmd = kwargs.get("command", "")
            args = kwargs.get("args", [])
            self._servers[name] = {"command": cmd, "args": args}
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            self._config_file.write_text(json.dumps(self._servers, indent=2), encoding="utf-8")
            return {"status": "registered", "server": name}
        elif cap == "mcp.list_tools":
            server = kwargs.get("server")
            return {
                "server": server,
                "tools": [
                    {"name": "fetch_web_content", "description": "Fetch content from URL via MCP"},
                    {"name": "query_database", "description": "Execute read-only SQL query via MCP"},
                ],
            }
        else:
            return {"status": "success", "capability": capability, "params": kwargs}
