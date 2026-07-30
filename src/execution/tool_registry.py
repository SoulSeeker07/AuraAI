"""
Tool Execution Engine - Tool Registry

This module manages tool registration, discovery, and lifecycle.
It provides a unified interface for discovering and using tools.
"""


from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import importlib
import inspect
from .tool_interface import ToolInterface, ToolMetadata, ToolCategory


class ToolRegistry:
    """Registry for managing tool instances and their metadata."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, ToolInterface] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._categories: Dict[str, List[str]] = {}
        self._loaders: List[Callable] = []
        self._initialized = False
    
    def register_tool(self, tool: ToolInterface) -> None:
        """
        Register a tool instance.
        
        Args:
            tool: Tool instance to register
            
        Raises:
            ValueError: If tool is None or metadata is missing
        """
        if tool is None:
            raise ValueError("Tool cannot be None")
        
        metadata = tool.get_metadata()
        if not metadata or not metadata.name:
            raise ValueError("Tool must have metadata with a name")
        
        tool_name = metadata.name
        
        # Check if tool is already registered
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")
        
        # Initialize the tool
        try:
            tool.initialize()
        except Exception as e:
            raise ValueError(f"Failed to initialize tool '{tool_name}': {e}")
        
        # Register the tool
        self._tools[tool_name] = tool
        self._metadata[tool_name] = metadata
        
        # Update categories
        category = metadata.category
        if category not in self._categories:
            self._categories[category] = []
        if tool_name not in self._categories[category]:
            self._categories[category].append(tool_name)
        
        self._initialized = True
    
    def unregister_tool(self, tool_name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            True if tool was unregistered, False if not found
        """
        if tool_name in self._tools:
            # Try to cleanup the tool
            tool = self._tools[tool_name]
            try:
                # Check if tool has a cleanup method
                if hasattr(tool, 'cleanup'):
                    try:
                        # Create empty context for cleanup
                        tool.cleanup("unregister", {})
                    except Exception:
                        pass  # Log error but don't fail
            except Exception:
                pass  # Log error but don't fail
            
            # Remove from registry
            metadata = self._metadata.pop(tool_name, None)
            if metadata:
                category = metadata.category
                if category in self._categories and tool_name in self._categories[category]:
                    self._categories[category].remove(tool_name)
            
            del self._tools[tool_name]
            return True
        return False
    
    def get_tool(self, tool_name: str) -> Optional[ToolInterface]:
        """
        Get a tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance, or None if not found
        """
        return self._tools.get(tool_name)
    
    def get_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """Get metadata for a tool."""
        return self._metadata.get(tool_name)
    
    def list_tools(self) -> List[ToolMetadata]:
        """
        List all registered tools.
        
        Returns:
            List of tool metadata
        """
        return list(self._metadata.values())
    
    def list_tools_by_category(self, category: str) -> List[ToolMetadata]:
        """
        List tools by category.
        
        Args:
            category: Category name
            
        Returns:
            List of tool metadata
        """
        tool_names = self._categories.get(category, [])
        return [self._metadata[name] for name in tool_names]
    
    def list_categories(self) -> List[str]:
        """List all registered categories."""
        return list(self._categories.keys())
    
    def search_tools(self, query: str) -> List[ToolMetadata]:
        """
        Search for tools by name, description, or tags.
        
        Args:
            query: Search query
            
        Returns:
            List of matching tool metadata
        """
        query = query.lower()
        results = []
        
        for tool_name, metadata in self._metadata.items():
            if (query in tool_name.lower() or
                query in metadata.description.lower() or
                any(query in tag.lower() for tag in metadata.tags)):
                results.append(metadata)
        
        return results
    
    def get_supported_operations(self, tool_name: str) -> List[str]:
        """
        Get operations supported by a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of operation names
        """
        tool = self.get_tool(tool_name)
        if tool:
            return tool.get_supported_operations()
        return []
    
    def get_all_supported_operations(self) -> Dict[str, List[str]]:
        """
        Get all supported operations across all tools.
        
        Returns:
            Dictionary mapping tool names to lists of operations
        """
        return {
            tool_name: tool.get_supported_operations()
            for tool_name, tool in self._tools.items()
        }
    
    def add_loader(self, loader: Callable) -> None:
        """
        Add a tool loader function.
        
        Args:
            loader: Loader function that discovers and loads tools
        """
        self._loaders.append(loader)
    
    def load_tools_from_directory(self, directory: str) -> int:
        """
        Load tools from a directory.
        
        Args:
            directory: Path to directory containing tools
            
        Returns:
            Number of tools loaded
        """
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return 0
        
        loaded_count = 0
        
        # Look for Python files
        for file_path in dir_path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            
            try:
                # Import the module
                module_name = f"tools.{file_path.stem}"
                importlib.import_module(module_name)
                
                # Look for ToolInterface subclasses
                for name, obj in inspect.getmembers(
                    importlib.import_module(module_name),
                    inspect.isclass
                ):
                    if (issubclass(obj, ToolInterface) and 
                        obj is not ToolInterface and
                        obj.__module__ == module_name):
                        try:
                            tool = obj()
                            self.register_tool(tool)
                            loaded_count += 1
                        except Exception as e:
                            # Log error but continue
                            pass
            except Exception as e:
                # Log error but continue
                pass
        
        return loaded_count
    
    def clear(self) -> None:
        """Clear all registered tools."""
        # Unregister all tools
        while self._tools:
            tool_name = next(iter(self._tools.keys()))
            self.unregister_tool(tool_name)
        
        # Clear categories
        self._categories.clear()
    
    def get_tool_count(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)
    
    def get_tool_count_by_category(self, category: str) -> int:
        """Get the number of tools in a category."""
        return len(self._categories.get(category, []))


class ToolManager:
    """Manager for discovering and loading tools."""
    
    def __init__(self, registry: ToolRegistry = None):
        """
        Initialize the tool manager.
        
        Args:
            registry: Optional registry instance
        """
        self.registry = registry or ToolRegistry()
        self._discovered_tools: Dict[str, str] = {}
    
    def discover_tools(self, search_paths: List[str] = None) -> int:
        """
        Discover and register tools.
        
        Args:
            search_paths: Optional list of directories to search
            
        Returns:
            Number of tools discovered and registered
        """
        discovered_count = 0
        
        # Search in default locations
        default_paths = [
            "plugins",
            "tools",
            "src/tools"
        ]
        
        # Add custom search paths if provided
        search_paths = search_paths or []
        all_paths = default_paths + search_paths
        
        for path in all_paths:
            if Path(path).exists():
                try:
                    loaded = self.registry.load_tools_from_directory(path)
                    discovered_count += loaded
                except Exception as e:
                    # Log error but continue
                    pass
        
        return discovered_count
    
    def auto_load(self, search_paths: List[str] = None) -> int:
        """
        Auto-discover and register all available tools.
        
        Args:
            search_paths: Optional list of directories to search
            
        Returns:
            Number of tools loaded
        """
        return self.discover_tools(search_paths)
