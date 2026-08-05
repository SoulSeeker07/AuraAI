"""
Tool Router

Routes requests to appropriate tools and plugins.
This replaces direct tool calls with a centralized routing system.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ToolResult:
    """Result of executing a tool."""

    def __init__(
        self,
        tool_name: str,
        success: bool,
        output: str = "",
        error: str | None = None,
        metadata: dict[str, Any] = None,
    ):
        """
        Initialize tool result.

        Args:
            tool_name: Name of tool executed
            success: Whether tool succeeded
            output: Tool output
            error: Error message if failed
            metadata: Additional metadata
        """
        self.tool_name = tool_name
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}

    def __bool__(self) -> bool:
        """Tool result is truthy if successful."""
        return self.success

    def __repr__(self) -> str:
        """String representation."""
        status = "SUCCESS" if self.success else "FAILED"
        return f"ToolResult({self.tool_name}: {status})"


class ToolRouter:
    """
    Routes requests to appropriate tools.

    The Tool Router is responsible for:
    - Discovering available tools and plugins
    - Routing requests to the correct tool
    - Executing tools and capturing results
    - Handling tool errors gracefully

    Architecture:
        AuraBrain → Tool Router → Tools/Plugins

    Tools supported:
        - Filesystem tools
        - Browser automation
        - Desktop automation
        - Git operations
        - Plugin tools
        - Custom tools
    """

    def __init__(
        self,
        plugin_registry=None,
        desktop_agent=None,
        filesystem=None,
        workspace_root: Path = None,
    ):
        """
        Initialize Tool Router.

        Args:
            plugin_registry: Plugin registry for plugin tools
            desktop_agent: Desktop agent for desktop automation
            filesystem: Filesystem handler
            workspace_root: Root directory of the project/workspace
        """
        self.plugins = plugin_registry
        self.desktop = desktop_agent
        self.filesystem = filesystem
        self.workspace_root = workspace_root or Path.cwd()

        # Initialize code executor if available
        self.code_executor = None
        if workspace_root:
            try:
                from core.tools.code_execution.code_execution_tool import (
                    CodeExecutionTool,
                )

                self.code_executor = CodeExecutionTool(workspace_root=workspace_root)
                logger.info("Code execution tool initialized")
            except ImportError:
                logger.warning("Code execution tool not available")

        # Register known tools
        self.registered_tools = self._discover_tools()

        logger.info(f"Tool Router initialized with {len(self.registered_tools)} tools")

    def _discover_tools(self) -> dict[str, Any]:
        """
        Discover available tools.

        Returns:
            Dictionary of available tools
        """
        tools = {}

        # Register code execution tool if available
        if hasattr(self, "code_executor") and self.code_executor is not None:
            tools["execute_python"] = {
                "name": "execute_python",
                "description": "Save and execute Python code",
                "async": False,
                "handler": lambda params: self.code_executor.save_and_execute(
                    code=params.get("code", ""),
                    filename=params.get("filename"),
                    timeout=params.get("timeout", 30),
                ),
            }
        else:
            logger.warning(
                "Code executor not available, skipping 'execute_python' tool registration"
            )

        # Register core tools
        tools["read_file"] = {
            "name": "read_file",
            "description": "Read content from a file",
            "async": False,
            "handler": self._read_file,
        }

        tools["write_file"] = {
            "name": "write_file",
            "description": "Write content to a file",
            "async": False,
            "handler": self._write_file,
        }

        tools["search_files"] = {
            "name": "search_files",
            "description": "Search for files by name",
            "async": False,
            "handler": self._search_files,
        }

        tools["execute_command"] = {
            "name": "execute_command",
            "description": "Execute a shell command",
            "async": False,
            "handler": self._execute_command,
        }

        tools["browser"] = {
            "name": "browser",
            "description": "Open a URL in browser",
            "async": False,
            "handler": self._open_browser,
        }

        tools["git"] = {
            "name": "git",
            "description": "Execute git commands",
            "async": False,
            "handler": self._execute_git,
        }

        # Register plugin tools if available
        if self.plugins:
            plugin_tools = self.plugins.get_available_tools()
            for plugin_name, plugin_tool in plugin_tools.items():
                tools[plugin_name] = plugin_tool
                logger.info(f"Registered plugin tool: {plugin_name}")

        return tools

    def route(self, tool_name: str, params: dict[str, Any] = None) -> ToolResult:
        """
        Route a request to the appropriate tool.

        Args:
            tool_name: Name of the tool to execute
            params: Parameters for the tool

        Returns:
            ToolResult with success status and output/error
        """
        params = params or {}

        logger.debug(f"Routing request to tool: {tool_name}")

        # Check if tool exists
        if tool_name not in self.registered_tools:
            error_msg = f"Unknown tool: {tool_name}. Available tools: {list(self.registered_tools.keys())}"
            logger.error(error_msg)
            return ToolResult(
                tool_name=tool_name, success=False, output="", error=error_msg
            )

        # Get tool definition
        tool = self.registered_tools[tool_name]

        # Execute tool
        try:
            handler = tool["handler"]
            output = handler(params)
            logger.info(f"Tool {tool_name} executed successfully")

            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=str(output),
                metadata=tool.get("metadata", {}),
            )

        except Exception as e:
            error_msg = f"Tool execution failed: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)

            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=error_msg,
                metadata=tool.get("metadata", {}),
            )

    def register_tool(self, tool_name: str, tool_handler, metadata: dict = None):
        """
        Register a custom tool.

        Args:
            tool_name: Name of the tool
            tool_handler: Function to handle the tool
            metadata: Additional metadata
        """
        self.registered_tools[tool_name] = {
            "name": tool_name,
            "description": "Custom tool",
            "async": False,
            "handler": tool_handler,
            "metadata": metadata or {},
        }
        logger.info(f"Registered custom tool: {tool_name}")

    # Tool handlers

    def _read_file(self, params: dict) -> str:
        """Read file content."""
        file_path = params.get("path", "")
        if not file_path:
            raise ValueError("Path parameter is required")

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            return content
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {file_path}")
        except Exception as e:
            raise Exception(f"Failed to read file: {e}")

    def _write_file(self, params: dict) -> str:
        """Write content to file."""
        file_path = params.get("path", "")
        content = params.get("content", "")

        if not file_path:
            raise ValueError("Path parameter is required")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            raise Exception(f"Failed to write file: {e}")

    def _search_files(self, params: dict) -> str:
        """Search for files."""
        search_term = params.get("term", "")
        directory = params.get("directory", ".")

        if not search_term:
            raise ValueError("Search term is required")

        import os

        matches = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if search_term.lower() in file.lower():
                    matches.append(os.path.join(root, file))

        return "\n".join(matches[:10])  # Return top 10 matches

    def _execute_command(self, params: dict) -> str:
        """Execute shell command."""
        command = params.get("command", "")

        if not command:
            raise ValueError("Command parameter is required")

        import subprocess

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=30
            )

            output = result.stdout + result.stderr
            return output

        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds"
        except Exception as e:
            return f"Command execution failed: {e}"

    def _open_browser(self, params: dict) -> str:
        """Open URL in browser."""
        url = params.get("url", "")

        if not url:
            raise ValueError("URL parameter is required")

        import webbrowser

        webbrowser.open(url)
        return f"Opened {url} in browser"

    def _execute_git(self, params: dict) -> str:
        """Execute git command."""
        command = params.get("command", "")

        if not command:
            raise ValueError("Command parameter is required")

        import subprocess

        try:
            result = subprocess.run(
                ["git"] + command.split(), capture_output=True, text=True, timeout=30
            )

            output = result.stdout + result.stderr
            return output

        except subprocess.TimeoutExpired:
            return "Git command timed out after 30 seconds"
        except Exception as e:
            return f"Git command failed: {e}"
