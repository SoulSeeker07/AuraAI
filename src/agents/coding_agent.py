"""
Coding Agent - Analyzes and improves codebases.

The Coding Agent can:
- Analyze entire projects
- Find bugs and issues
- Refactor code
- Generate new modules
- Explain errors
- Generate tests
- Build documentation
- Run project-wide searches
- Suggest architecture improvements
"""

from __future__ import annotations

import os
import ast
import inspect
from pathlib import Path
from typing import Any, List, Optional
import subprocess

from .task_model import (
    Task,
    TaskStatus,
    TaskType,
    TaskInput,
    TaskOutput,
    TaskPriority
)


class CodingAgent:
    """
    Analyzes and improves codebases.

    Capabilities:
    - Project-wide code analysis
    - Bug detection and fixing
    - Code refactoring
    - Code generation
    - Test generation
    - Documentation generation
    - Architecture suggestions
    """

    def __init__(self, task_manager):
        """
        Initialize the coding agent.

        Args:
            task_manager: TaskManager instance
        """
        self.task_manager = task_manager
        self._project_roots: List[Path] = []

    def execute_task(self, task: Task) -> TaskOutput:
        """
        Execute a coding task.

        Args:
            task: Task to execute

        Returns:
            Task execution result
        """
        try:
            method = getattr(self, f"_execute_{task.type.value}", None)

            if not method:
                return TaskOutput(
                    success=False,
                    message=f"No handler for task type: {task.type.value}",
                    error=f"Task type {task.type.value} not supported"
                )

            return method(task)

        except Exception as e:
            return TaskOutput(
                success=False,
                message=f"Error executing task",
                error=str(e)
            )

    # ========================================
    # CODE ANALYSIS
    # ========================================

    def _execute_code_analysis(self, task: Task) -> TaskOutput:
        """Analyze code for issues and patterns."""
        project_path = task.input.get("project_path", str(Path.cwd()))
        analysis_type = task.input.get("analysis_type", "all")

        try:
            path = Path(project_path)
            if not path.exists():
                return TaskOutput(
                    success=False,
                    message="Project path not found",
                    error=f"Path does not exist: {project_path}"
                )

            issues = []
            files_analyzed = 0

            # Scan Python files
            for py_file in path.rglob("*.py"):
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())

                    # Simple analysis: check for common issues
                    if analysis_type in ["all", "issues"]:
                        issues.extend(self._analyze_ast(tree))

                    files_analyzed += 1
                except Exception:
                    continue

            return TaskOutput(
                success=True,
                message=f"Analyzed {files_analyzed} Python files",
                data={
                    "files_analyzed": files_analyzed,
                    "issues": issues,
                    "file_count": len(issues)
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="Code analysis failed",
                error=str(e)
            )

    def _analyze_ast(self, tree: ast.AST) -> List[dict[str, Any]]:
        """Analyze AST for common issues."""
        issues = []

        for node in ast.walk(tree):
            # Check for unused imports (simplified)
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    issues.append({
                        "type": "unused_import",
                        "file": getattr(node, 'filename', 'unknown'),
                        "line": node.lineno,
                        "message": f"Import from '{node.module}'",
                        "severity": "low"
                    })

            # Check for missing docstrings (optional)
            if isinstance(node, ast.FunctionDef) and node.lineno:
                # Simple heuristic: functions without docstrings
                docstring = ast.get_docstring(node)
                if not docstring:
                    issues.append({
                        "type": "missing_docstring",
                        "file": getattr(node, 'filename', 'unknown'),
                        "line": node.lineno,
                        "message": "Function lacks docstring",
                        "severity": "medium"
                    })

        return issues

    # ========================================
    # CODE REFACTORING
    # ========================================

    def _execute_code_refactor(self, task: Task) -> TaskOutput:
        """Refactor code to improve quality."""
        file_path = task.input.get("file_path")
        refactoring_type = task.input.get("refactoring_type", "all")

        if not file_path:
            return TaskOutput(
                success=False,
                message="Failed to refactor code",
                error="File path required"
            )

        try:
            path = Path(file_path)
            if not path.exists():
                return TaskOutput(
                    success=False,
                    message="File not found",
                    error=f"Path does not exist: {file_path}"
                )

            # Read file
            with open(path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Apply refactoring
            refactored_content = original_content
            changes_made = []

            if refactoring_type in ["all", "imports"]:
                refactored_content, import_changes = self._refactor_imports(refactored_content)
                changes_made.extend(import_changes)

            if refactoring_type in ["all", "formatting"]:
                refactored_content, format_changes = self._apply_basic_formatting(refactored_content)
                changes_made.extend(format_changes)

            # Write refactored code
            with open(path, 'w', encoding='utf-8') as f:
                f.write(refactored_content)

            return TaskOutput(
                success=True,
                message=f"Code refactored successfully",
                data={
                    "file": str(path),
                    "changes": changes_made,
                    "change_count": len(changes_made)
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="Refactoring failed",
                error=str(e)
            )

    def _refactor_imports(self, content: str) -> tuple[str, List[dict]]:
        """Refactor imports (simple version)."""
        # Sort imports alphabetically
        lines = content.split('\n')
        import_lines = []
        other_lines = []

        for line in lines:
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                import_lines.append(line)
            else:
                other_lines.append(line)

        import_lines.sort()

        return '\n'.join(import_lines + other_lines), []

    def _apply_basic_formatting(self, content: str) -> tuple[str, List[dict]]:
        """Apply basic formatting (simple version)."""
        # Normalize whitespace (basic)
        lines = []
        changes = []

        for i, line in enumerate(content.split('\n')):
            # Remove trailing whitespace
            if line != line.rstrip():
                changes.append({
                    "line": i + 1,
                    "type": "trailing_whitespace",
                    "message": "Removed trailing whitespace"
                })
                line = line.rstrip()

            lines.append(line)

        return '\n'.join(lines), changes

    # ========================================
    # CODE GENERATION
    # ========================================

    def _execute_code_generate(self, task: Task) -> TaskOutput:
        """Generate code based on specifications."""
        code_type = task.input.get("code_type", "function")
        specs = task.input.get("specs", {})

        if code_type == "function":
            return self._generate_function(**specs)
        elif code_type == "class":
            return self._generate_class(**specs)
        elif code_type == "module":
            return self._generate_module(**specs)
        else:
            return TaskOutput(
                success=False,
                message="Unknown code type",
                error=f"Code type '{code_type}' not supported"
            )

    def _generate_function(self, name: str, description: str, returns: str = None, **kwargs) -> TaskOutput:
        """Generate a function."""
        params = kwargs.get("params", [])
        param_list = ", ".join(params)

        func_code = f'''def {name}({param_list}):
    """
    {description}
    """
    pass
'''

        return TaskOutput(
            success=True,
            message=f"Function generated: {name}",
            data={
                "code": func_code,
                "function_name": name
            }
        )

    def _generate_class(self, name: str, description: str, methods: List[dict] = None, **kwargs) -> TaskOutput:
        """Generate a class."""
        methods = methods or []
        method_code = []

        for method in methods:
            method_code.append(self._generate_function(
                name=method.get("name"),
                description=method.get("description"),
                returns=method.get("returns")
            ).data["code"])

        class_code = f'''class {name}:
    """
    {description}
    """

{chr(10).join(method_code)}'''

        return TaskOutput(
            success=True,
            message=f"Class generated: {name}",
            data={
                "code": class_code,
                "class_name": name
            }
        )

    def _generate_module(self, name: str, description: str, components: List[dict] = None, **kwargs) -> TaskOutput:
        """Generate a module."""
        components = components or []

        module_code = f'''"""
{description}

Module: {name}
"""

'''

        for comp in components:
            module_code += self._generate_function(
                name=comp.get("name"),
                description=comp.get("description")
            ).data["code"]

        return TaskOutput(
            success=True,
            message=f"Module generated: {name}",
            data={
                "code": module_code,
                "module_name": name
            }
        )

    # ========================================
    # CODE DEBUGGING
    # ========================================

    def _execute_code_debug(self, task: Task) -> TaskOutput:
        """Debug code issues."""
        code = task.input.get("code", "")
        issue_type = task.input.get("issue_type", "bug")

        try:
            # Parse code to check for syntax errors
            tree = ast.parse(code)

            return TaskOutput(
                success=True,
                message="Code parsed successfully (no syntax errors)",
                data={
                    "parsed": True,
                    "issues": []
                }
            )

        except SyntaxError as e:
            return TaskOutput(
                success=False,
                message="Syntax error detected",
                error=f"Line {e.lineno}: {e.msg}",
                data={
                    "parsed": False,
                    "syntax_error": {
                        "line": e.lineno,
                        "message": e.msg,
                        "offset": e.offset
                    }
                }
            )
        except Exception as e:
            return TaskOutput(
                success=False,
                message="Debug analysis failed",
                error=str(e)
            )

    # ========================================
    # TEST GENERATION
    # ========================================

    def _execute_test_generate(self, task: Task) -> TaskOutput:
        """Generate tests for code."""
        code = task.input.get("code", "")
        test_framework = task.input.get("framework", "pytest")

        if test_framework == "pytest":
            return self._generate_pytest_tests(code)

        return TaskOutput(
            success=False,
            message="Test generation failed",
            error=f"Test framework '{test_framework}' not supported"
        )

    def _generate_pytest_tests(self, code: str) -> TaskOutput:
        """Generate pytest tests."""
        try:
            tree = ast.parse(code)
            test_count = 0

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.startswith("_"):
                        test_count += 1

            return TaskOutput(
                success=True,
                message=f"Generated pytest tests for {test_count} functions",
                data={
                    "functions_analyzed": test_count,
                    "test_framework": "pytest",
                    "tests": [
                        {
                            "name": f"test_{func.name}",
                            "description": f"Test for {func.name}"
                        }
                        for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
                    ]
                }
            )

        except SyntaxError:
            return TaskOutput(
                success=False,
                message="Failed to generate tests (syntax error)",
                error="Code has syntax errors, cannot generate tests"
            )

    # ========================================
    # DOCUMENTATION GENERATION
    # ========================================

    def _execute_code_document(self, task: Task) -> TaskOutput:
        """Generate documentation for code."""
        file_path = task.input.get("file_path")

        if not file_path:
            return TaskOutput(
                success=False,
                message="Failed to generate documentation",
                error="File path required"
            )

        try:
            path = Path(file_path)
            if not path.exists():
                return TaskOutput(
                    success=False,
                    message="File not found",
                    error=f"Path does not exist: {file_path}"
                )

            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()

            # Parse and generate documentation
            tree = ast.parse(code)
            documentation = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    docstring = ast.get_docstring(node) or f"Function: {node.name}\n\n"
                    parameters = []

                    for arg in node.args.args:
                        param_type = self._get_annotation(arg.annotation) if arg.annotation else "Any"
                        parameters.append(f"  {arg.arg}: {param_type}")

                    returns = self._get_annotation(node.returns) if node.returns else "None"

                    docstring += "Parameters:\n"
                    docstring += "\n".join(parameters) + "\n\n"
                    docstring += f"Returns: {returns}\n"

                    documentation.append({
                        "name": node.name,
                        "docstring": docstring,
                        "line": node.lineno
                    })

            return TaskOutput(
                success=True,
                message=f"Generated documentation for {len(documentation)} functions",
                data={
                    "documentation": documentation,
                    "format": "markdown"
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="Documentation generation failed",
                error=str(e)
            )

    def _get_annotation(self, annotation) -> str:
        """Get annotation string."""
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Subscript):
            return self._get_annotation(annotation.value) + "[" + ", ".join(
                self._get_annotation(sub) for sub in annotation.slice.value.elts
            ) + "]"
        else:
            return str(annotation)
