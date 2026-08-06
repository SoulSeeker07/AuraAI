"""
AST-based Code Parser
======================

Parses Python code using the ast module to extract:
- Imports (absolute, relative, aliased)
- Classes and their methods
- Functions and their decorators
- Inheritance relationships
- Module structure
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ImportInfo:
    """Represents an import statement."""
    module: str
    alias: Optional[str] = None
    is_relative: bool = False
    line_number: int = 0


@dataclass
class ClassInfo:
    """Represents a Python class."""
    name: str
    bases: List[str]
    methods: List[str]
    line_number: int
    decorators: List[str]


@dataclass
class FunctionInfo:
    """Represents a Python function or method."""
    name: str
    decorators: List[str]
    line_number: int
    is_async: bool = False


@dataclass
class ModuleInfo:
    """Represents a Python module."""
    path: str
    imports: List[ImportInfo]
    classes: Dict[str, ClassInfo]
    functions: Dict[str, FunctionInfo]
    decorators: List[str]
    
    def __post_init__(self):
        """Create sets for faster lookups."""
        self.import_modules = {imp.module for imp in self.imports}
        self.class_names = set(self.classes.keys())
        self.function_names = set(self.functions.keys())


class ASTParser:
    """Parses Python code using AST to extract structure and dependencies."""
    
    def __init__(self, root_path: str):
        """
        Initialize the parser with a root directory.
        
        Args:
            root_path: Path to the root directory to scan
        """
        self.root_path = Path(root_path)
        self.all_modules: Dict[str, ModuleInfo] = {}
    
    def parse_file(self, file_path: Path) -> Optional[ModuleInfo]:
        """
        Parse a single Python file.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            ModuleInfo if parsing succeeds, None otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            module_name = file_path.stem
            module_info = self._parse_tree(tree, file_path)
            
            self.all_modules[module_name] = module_info
            return module_info
            
        except SyntaxError as e:
            print(f"Warning: Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            print(f"Warning: Error parsing {file_path}: {e}")
            return None
    
    def _parse_tree(self, tree: ast.AST, file_path: Path) -> ModuleInfo:
        """
        Parse an AST tree and extract module information.
        
        Args:
            tree: AST tree to parse
            file_path: File path for reference
            
        Returns:
            ModuleInfo with parsed structure
        """
        imports = []
        classes = {}
        functions = {}
        decorators = []
        
        for node in ast.walk(tree):
            # Collect decorators from the module level
            if isinstance(node, ast.Module):
                decorators = []
            
            # Handle imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        is_relative=False,
                        line_number=node.lineno
                    ))
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=f"{module}.{alias.name}",
                        alias=alias.asname,
                        is_relative=node.level > 0,
                        line_number=node.lineno
                    ))
            
            # Handle class definitions
            elif isinstance(node, ast.ClassDef):
                bases = [self._get_base_name(base) for base in node.bases]
                methods = []
                
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)
                    elif isinstance(item, ast.AsyncFunctionDef):
                        methods.append(item.name)
                
                classes[node.name] = ClassInfo(
                    name=node.name,
                    bases=bases,
                    methods=methods,
                    line_number=node.lineno,
                    decorators=[
                        ast.unparse(dec) for dec in node.decorator_list
                    ]
                )
            
            # Handle function definitions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_name = node.name
                decorators = [
                    ast.unparse(dec) for dec in node.decorator_list
                ]
                
                functions[func_name] = FunctionInfo(
                    name=func_name,
                    decorators=decorators,
                    line_number=node.lineno,
                    is_async=isinstance(node, ast.AsyncFunctionDef)
                )
        
        return ModuleInfo(
            path=str(file_path),
            imports=imports,
            classes=classes,
            functions=functions,
            decorators=decorators
        )
    
    def _get_base_name(self, base: ast.expr) -> str:
        """
        Get the base class name from an AST expression.
        
        Args:
            base: AST expression for the base class
            
        Returns:
            Base class name as string
        """
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return base.attr
        return "Unknown"
    
    def parse_directory(self, directory: Path, recursive: bool = True) -> Dict[str, ModuleInfo]:
        """
        Parse all Python files in a directory.
        
        Args:
            directory: Directory to parse
            recursive: Whether to recursively parse subdirectories
            
        Returns:
            Dictionary of module name to ModuleInfo
        """
        extensions = {'.py', '.pyi'}
        
        for root, dirs, files in os.walk(directory):
            # Filter out common directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
                '__pycache__', 'venv', 'env', '.venv', '.git', 
                'node_modules', 'dist', 'build', 'generated_code'
            ]]
            
            for file in files:
                if file.endswith(('.py', '.pyi')):
                    file_path = Path(root) / file
                    
                    if recursive or file_path.parent == directory:
                        self.parse_file(file_path)
        
        return self.all_modules
    
    def get_all_imports(self) -> Dict[str, Set[str]]:
        """
        Get all imports for all modules.
        
        Returns:
            Dictionary mapping module names to sets of imported modules
        """
        return {
            module_name: module.import_modules
            for module_name, module in self.all_modules.items()
        }
    
    def get_all_classes(self) -> Dict[str, List[str]]:
        """
        Get all classes across all modules.
        
        Returns:
            Dictionary mapping module names to lists of class names
        """
        return {
            module_name: list(module.class_names)
            for module_name, module in self.all_modules.items()
        }
    
    def get_all_functions(self) -> Dict[str, List[str]]:
        """
        Get all functions across all modules.
        
        Returns:
            Dictionary mapping module names to lists of function names
        """
        return {
            module_name: list(module.function_names)
            for module_name, module in self.all_modules.items()
        }
    
    def get_all_modules(self) -> Dict[str, ModuleInfo]:
        """
        Get all parsed modules.
        
        Returns:
            Dictionary of module names to ModuleInfo
        """
        return self.all_modules
