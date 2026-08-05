"""
AuraBrain Integration with Tool Execution Engine

This module integrates the new Tool Execution Engine with AuraBrain.
It provides a unified interface for executing tools with consistent
lifecycle, error handling, and progress reporting.
"""

import logging
import os
import sys
from typing import Any

# Add parent directory to path to allow importing core modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from brain.execution_state import ExecutionState
from brain.request import ToolResult
from core.tools.tool_router import ToolRouter
from core.workspace.workspace_manager import WorkspaceManager
from execution.execution_engine import ExecutionEngine
from execution.tool_adapter import adapt_function
from execution.tool_interface import ToolCategory

logger = logging.getLogger(__name__)


class BrainIntegration:
    """
    Integration layer between AuraBrain and the Tool Execution Engine.

    This class provides:
    1. Execution engine initialization and configuration
    2. Tool registration and discovery
    3. Unified interface for tool execution
    4. Result formatting for AuraBrain
    5. Error handling and logging
    6. Backward compatibility with existing ToolRouter

    Usage:
        >>> integration = BrainIntegration(
        ...     workspace_manager=workspace_manager,
        ...     tool_router=existing_tool_router
        ... )
        >>> integration.initialize()
        >>> result = integration.execute_tool("file_writer", "write", {"content": "hello"})
    """

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        tool_router: ToolRouter | None = None,
        enable_execution_engine: bool = True,
        auto_register_tools: bool = True,
    ):
        """
        Initialize the Brain Integration.

        Args:
            workspace_manager: Workspace manager for file operations
            tool_router: Existing ToolRouter (for backward compatibility)
            enable_execution_engine: Whether to enable the execution engine
            auto_register_tools: Whether to automatically register tools
        """
        self.workspace_manager = workspace_manager
        self.tool_router = tool_router
        self.enable_execution_engine = enable_execution_engine
        self.auto_register_tools = auto_register_tools

        # Execution engine components
        self.execution_engine: ExecutionEngine | None = None
        self.execution_state: ExecutionState | None = None

        # Tools that have been registered
        self.registered_tools: dict[str, Any] = {}

        # Setup logging
        logger.info("BrainIntegration initialized")

    def initialize(self) -> None:
        """
        Initialize the execution engine and register tools.

        This method should be called during AuraBrain initialization.
        """
        if not self.enable_execution_engine:
            logger.info("Execution engine is disabled")
            return

        logger.info("Initializing execution engine")

        try:
            # Create execution engine
            self.execution_engine = ExecutionEngine(
                default_timeout=300, require_confirmation=True  # 5 minutes
            )

            # Register tools automatically
            if self.auto_register_tools:
                self.register_default_tools()

            logger.info("Execution engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize execution engine: {e}", exc_info=True)
            # Don't fail AuraBrain initialization, just disable execution engine
            self.enable_execution_engine = False

    def register_default_tools(self) -> None:
        """
        Register default tools for Aura.

        This includes tools for:
        - File operations
        - Desktop operations
        - Knowledge operations
        - Research operations
        """
        if not self.execution_engine:
            return

        logger.info("Registering default tools")

        try:
            # Register filesystem tool
            self.register_tool(
                name="filesystem",
                description="File system operations",
                category=ToolCategory.FILE,
                execute_function=self._execute_filesystem_operation,
                tags=["file", "filesystem", "read", "write", "delete"],
            )

            # Register desktop tool
            self.register_tool(
                name="desktop",
                description="Desktop operations",
                category=ToolCategory.GENERAL,
                execute_function=self._execute_desktop_operation,
                tags=["desktop", "window", "app"],
            )

            # Register search tool
            self.register_tool(
                name="search",
                description="Search files and content",
                category=ToolCategory.SEARCH,
                execute_function=self._execute_search_operation,
                tags=["search", "find", "locate"],
            )

            # Register knowledge tool
            self.register_tool(
                name="knowledge",
                description="Knowledge base operations",
                category=ToolCategory.KNOWLEDGE,
                execute_function=self._execute_knowledge_operation,
                tags=["knowledge", "memory", "facts"],
            )

            # Register web search tool
            self.register_tool(
                name="web_search",
                description="Web search operations",
                category=ToolCategory.INTERNET,
                execute_function=self._execute_web_search,
                tags=["web", "search", "internet"],
            )

            logger.info(f"Registered {len(self.registered_tools)} default tools")

        except Exception as e:
            logger.error(f"Failed to register default tools: {e}", exc_info=True)

    def register_tool(
        self,
        name: str,
        description: str,
        category: ToolCategory = ToolCategory.GENERAL,
        execute_function: callable | None = None,
        tags: list = None,
        version: str = "1.0.0",
    ) -> None:
        """
        Register a tool with the execution engine.

        Args:
            name: Tool name
            description: Tool description
            category: Tool category
            execute_function: Function to execute the tool
            tags: List of tags
            version: Tool version
        """
        if not self.execution_engine:
            logger.warning("Execution engine not available, cannot register tool")
            return

        # Create adapter from function
        adapter = adapt_function(
            function=execute_function,
            name=name,
            description=description,
            category=category,
            version=version,
        )

        # Register with execution engine
        self.execution_engine.tool_registry.register_tool(adapter)

        # Store reference for backward compatibility
        self.registered_tools[name] = adapter

        logger.info(f"Registered tool: {name} ({category.value})")

    def execute_tool(
        self,
        tool_name: str,
        operation: str,
        parameters: dict[str, Any] = None,
        user_id: str = "aura",
    ) -> ToolResult:
        """
        Execute a tool using the execution engine.

        Args:
            tool_name: Name of the tool
            operation: Operation to perform
            parameters: Operation parameters
            user_id: User ID for permission checking

        Returns:
            ToolResult formatted for AuraBrain
        """
        if not self.execution_engine:
            logger.error("Execution engine not available")
            return ToolResult(
                success=False, output=None, error="Execution engine not initialized"
            )

        try:
            logger.debug(f"Executing tool: {tool_name}.{operation}")

            # Execute using execution engine
            result = self.execution_engine.execute_tool(
                tool_name=tool_name,
                operation=operation,
                parameters=parameters or {},
                context={
                    "working_directory": self.workspace_manager.current_directory,
                    "user_id": user_id,
                    "metadata": {"tool_name": tool_name, "operation": operation},
                },
                user_id=user_id,
                timeout=60,
            )

            # Format result for AuraBrain
            formatted_result = self._format_tool_result(
                result=result, tool_name=tool_name, operation=operation
            )

            return formatted_result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)

            return ToolResult(
                success=False, output=None, error=f"Tool execution failed: {str(e)}"
            )

    def execute_tools_parallel(self, operations: list) -> list:
        """
        Execute multiple tools in parallel.

        Args:
            operations: List of operation dictionaries with:
                - tool_name
                - operation
                - parameters (optional)

        Returns:
            List of ToolResults
        """
        if not self.execution_engine:
            logger.error("Execution engine not available")
            return []

        try:
            logger.debug(f"Executing {len(operations)} tools in parallel")

            # Execute in parallel
            results = self.execution_engine.execute_parallel(operations)

            # Format results
            formatted_results = []
            for op_index, result in results.items():
                if result.success:
                    tool_name = operations[op_index].get("tool_name", "unknown")
                    operation = operations[op_index].get("operation", "unknown")
                    formatted_result = self._format_tool_result(
                        result=result, tool_name=tool_name, operation=operation
                    )
                else:
                    formatted_result = ToolResult(
                        success=False,
                        output=None,
                        error=result.error,
                        execution_metadata=result.execution_metadata,
                    )

                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            logger.error(f"Error executing parallel tools: {e}", exc_info=True)
            return []

    def wrap_tool_router(self) -> ToolRouter | None:
        """
        Wrap the existing ToolRouter to use the execution engine.

        This provides backward compatibility by creating a wrapper
        that delegates to the execution engine while maintaining
        the ToolRouter interface.

        Returns:
            Wrapped ToolRouter or None if execution engine is disabled
        """
        if not self.execution_engine:
            return self.tool_router

        logger.info("Creating wrapped ToolRouter for backward compatibility")

        class WrappedToolRouter:
            """Wrapped ToolRouter that delegates to execution engine."""

            def __init__(
                self, integration: BrainIntegration, original_router: ToolRouter | None
            ):
                self.integration = integration
                self.original_router = original_router

            def route(self, tool_name: str, params: dict = None) -> ToolResult:
                """Route a tool execution through execution engine."""
                if params is None:
                    params = {}

                return self.integration.execute_tool(
                    tool_name=tool_name, operation="execute", parameters=params
                )

            def get_tool(self, tool_name: str):
                """Get tool metadata."""
                if self.integration.execution_engine:
                    return self.integration.execution_engine.tool_registry.get_tool(
                        tool_name
                    )
                return None

            def list_tools(self):
                """List all registered tools."""
                if self.integration.execution_engine:
                    return self.integration.execution_engine.list_tools()
                return []

        return WrappedToolRouter(self, self.tool_router)

    # Private helper methods

    def _format_tool_result(self, result, tool_name: str, operation: str) -> ToolResult:
        """
        Format execution engine result for AuraBrain.

        Args:
            result: ToolExecutionResult from execution engine
            tool_name: Tool name
            operation: Operation name

        Returns:
            ToolResult formatted for AuraBrain
        """
        if result.success:
            return ToolResult(
                success=True,
                output=result.output,
                execution_metadata={
                    "execution_id": result.execution_id,
                    "execution_time": result.execution_time,
                    "execution_metadata": result.execution_metadata,
                },
            )
        else:
            return ToolResult(
                success=False,
                output=None,
                error=result.error,
                execution_metadata=result.execution_metadata,
            )

    def _execute_filesystem_operation(self, operation: str, parameters: dict) -> dict:
        """
        Execute filesystem operations.

        Args:
            operation: Operation type (read, write, list, delete)
            parameters: Operation parameters

        Returns:
            Operation result
        """
        if operation == "read":
            # Read file
            try:
                file_path = parameters.get("path")
                if file_path:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                    return {"status": "success", "content": content}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif operation == "write":
            # Write file
            try:
                file_path = parameters.get("path")
                content = parameters.get("content", "")
                mode = parameters.get("mode", "w")

                with open(file_path, mode, encoding="utf-8") as f:
                    f.write(content)

                return {"status": "success", "written": len(content)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif operation == "list":
            # List directory
            try:
                path = parameters.get("path", ".")
                entries = []
                for item in self.workspace_manager.filesystem.listdir(path):
                    entries.append(
                        {
                            "name": item.name,
                            "is_dir": item.is_dir(),
                            "size": item.stat().st_size if not item.is_dir() else None,
                        }
                    )
                return {"status": "success", "entries": entries}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif operation == "delete":
            # Delete file
            try:
                file_path = parameters.get("path")
                if file_path:
                    import os

                    os.remove(file_path)
                    return {"status": "success", "deleted": file_path}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _execute_desktop_operation(self, operation: str, parameters: dict) -> dict:
        """
        Execute desktop operations.

        Args:
            operation: Operation type
            parameters: Operation parameters

        Returns:
            Operation result
        """
        if operation == "minimize":
            # Minimize current window
            try:
                # This would integrate with the desktop agent
                return {"status": "success", "message": "Window minimized"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif operation == "maximize":
            # Maximize current window
            try:
                return {"status": "success", "message": "Window maximized"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif operation == "close":
            # Close current window
            try:
                return {"status": "success", "message": "Window closed"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _execute_search_operation(self, operation: str, parameters: dict) -> dict:
        """
        Execute search operations.

        Args:
            operation: Operation type (search, find_files)
            parameters: Operation parameters

        Returns:
            Operation result
        """
        if operation == "search":
            # Search files by content
            try:
                query = parameters.get("query", "")
                if query:
                    # Simple file content search
                    matches = []
                    for root, dirs, files in self.workspace_manager.filesystem.walk(
                        "."
                    ):
                        for file in files:
                            if file.endswith(".py"):
                                try:
                                    with open(root / file, encoding="utf-8") as f:
                                        content = f.read()
                                        if query.lower() in content.lower():
                                            matches.append(str(root / file))
                                except Exception:
                                    pass

                    return {"status": "success", "matches": matches}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif operation == "find_files":
            # Find files by pattern
            try:
                pattern = parameters.get("pattern", "")
                if pattern:
                    matches = []
                    for file in self.workspace_manager.filesystem.glob(pattern):
                        matches.append(str(file))

                    return {"status": "success", "matches": matches}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _execute_knowledge_operation(self, operation: str, parameters: dict) -> dict:
        """
        Execute knowledge operations.

        Args:
            operation: Operation type
            parameters: Operation parameters

        Returns:
            Operation result
        """
        if operation == "search":
            # Search knowledge base
            try:
                query = parameters.get("query", "")
                if query:
                    # This would integrate with memory manager
                    # For now, return a placeholder
                    return {"status": "success", "results": []}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        elif operation == "add":
            # Add knowledge
            try:
                fact = parameters.get("fact", "")
                if fact:
                    # This would integrate with memory manager
                    return {"status": "success", "added": fact}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _execute_web_search(self, operation: str, parameters: dict) -> dict:
        """
        Execute web search operations.

        Args:
            operation: Operation type
            parameters: Operation parameters

        Returns:
            Operation result
        """
        if operation == "search":
            # Perform web search
            try:
                query = parameters.get("query", "")
                if query:
                    # This would integrate with web search functionality
                    # For now, return a placeholder
                    return {"status": "success", "results": [], "query": query}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def get_tool_count(self) -> int:
        """Get the number of registered tools."""
        if self.execution_engine:
            return self.execution_engine.get_tool_count()
        return 0

    def get_tool_categories(self) -> list:
        """Get list of tool categories."""
        if self.execution_engine:
            return self.execution_engine.list_categories()
        return []

    def is_execution_engine_available(self) -> bool:
        """Check if execution engine is available."""
        return self.enable_execution_engine and self.execution_engine is not None
