"""
Code Execution Tool

This tool allows Aura to automatically save and execute generated Python code.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from core import logger


class CodeExecutionTool:
    """Tool for saving and executing Python code."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.code_dir = workspace_root / "generated_code"
        self.code_dir.mkdir(exist_ok=True)
        logger.info(f"Code execution tool initialized in {self.code_dir}")

    def save_and_execute(
        self, code: str, filename: str = None, timeout: int = 30
    ) -> dict[str, Any]:
        """
        Save code to a file and execute it.

        Args:
            code: Python code to execute
            filename: Optional filename (default: timestamp-based)
            timeout: Execution timeout in seconds

        Returns:
            Dictionary with execution results:
            {
                'success': bool,
                'output': str | None,
                'error': str | None,
                'filename': str,
                'execution_time': float
            }
        """
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_{timestamp}.py"

        filepath = self.code_dir / filename

        # Save code to file
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
            logger.info(f"Saved code to {filepath}")
        except Exception as e:
            error_msg = f"Failed to save code: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "output": None,
                "error": error_msg,
                "filename": filename,
                "execution_time": 0.0,
            }

        # Execute the code
        return self._execute_code(filepath, timeout)

    def _execute_code(self, filepath: Path, timeout: int) -> dict[str, Any]:
        """
        Execute a Python file.

        Args:
            filepath: Path to the Python file
            timeout: Execution timeout in seconds

        Returns:
            Dictionary with execution results
        """
        import time

        start_time = time.time()

        try:
            # Run the Python file using subprocess
            result = subprocess.run(
                [sys.executable, str(filepath)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace_root),
            )

            execution_time = time.time() - start_time

            if result.returncode == 0:
                logger.info(f"Successfully executed {filepath}")
                return {
                    "success": True,
                    "output": result.stdout,
                    "error": None,
                    "filename": filepath.name,
                    "execution_time": execution_time,
                }
            else:
                logger.error(
                    f"Failed to execute {filepath} (return code: {result.returncode})"
                )
                return {
                    "success": False,
                    "output": result.stdout,
                    "error": result.stderr,
                    "filename": filepath.name,
                    "execution_time": execution_time,
                }

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.error(f"Code execution timed out after {timeout}s")
            return {
                "success": False,
                "output": None,
                "error": f"Execution timed out after {timeout} seconds",
                "filename": filepath.name,
                "execution_time": execution_time,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error executing code: {e}", exc_info=True)
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "filename": filepath.name,
                "execution_time": execution_time,
            }

    def list_executions(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        List previously executed codes.

        Args:
            limit: Maximum number of recent executions to return

        Returns:
            List of execution results
        """
        executions = []

        for filepath in sorted(self.code_dir.glob("*.py"), reverse=True)[:limit]:
            try:
                stat = filepath.stat()
                executions.append(
                    {
                        "filename": filepath.name,
                        "path": str(filepath),
                        "timestamp": datetime.fromtimestamp(stat.st_mtime),
                        "size": stat.st_size,
                    }
                )
            except Exception as e:
                logger.error(f"Error reading {filepath}: {e}")

        return executions
