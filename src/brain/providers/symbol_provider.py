"""
Symbol Graph World Model Provider
Location: src/brain/providers/symbol_provider.py

Provides code intelligence perception: AST-indexed classes, functions, calls, and imports.
Features dynamic per-file mtime cache invalidation (same pattern as WorkspaceWalker).
"""

from __future__ import annotations

import ast
import asyncio
import logging
from concurrent.futures import Executor
from pathlib import Path
from typing import Any

from workspace.workspace_walker import WorkspaceWalker
from .base import IWorldProvider, ProviderFact

logger = logging.getLogger(__name__)


class SymbolGraphProvider(IWorldProvider):
    """
    World model provider for AST symbol graph perception with mtime caching.
    """

    def __init__(
        self,
        root: Path | str | None = None,
        walker: WorkspaceWalker | None = None,
        executor: Executor | None = None,
    ):
        self.root: Path = Path(root).resolve() if root else Path.cwd().resolve()
        self.walker = walker or WorkspaceWalker(root=self.root, respect_gitignore=True, max_files=500)
        self._executor = executor
        
        # Cache mapping: file_path -> (mtime, parsed_symbols_dict)
        self._file_cache: dict[Path, tuple[float, dict[str, Any]]] = {}

    @property
    def domain(self) -> str:
        return "symbol"

    def _parse_file_symbols(self, file_path: Path) -> dict[str, Any]:
        """
        Parse AST symbols from a single Python file, cached against st_mtime.
        """
        try:
            current_mtime = file_path.stat().st_mtime
        except OSError:
            return {"classes": [], "functions": [], "imports": []}

        if file_path in self._file_cache:
            cached_mtime, cached_data = self._file_cache[file_path]
            if cached_mtime == current_mtime:
                return cached_data

        classes: list[str] = []
        functions: list[str] = []
        imports: list[str] = []

        try:
            code = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            data = {
                "classes": sorted(list(set(classes))),
                "functions": sorted(list(set(functions))),
                "imports": sorted(list(set(imports))),
            }
            self._file_cache[file_path] = (current_mtime, data)
            return data

        except Exception as e:
            logger.debug(f"[SymbolGraphProvider] Error parsing {file_path}: {e}")
            return {"classes": [], "functions": [], "imports": []}

    def _index_all_files_sync(self) -> dict[str, Any]:
        """Index all Python files in the workspace with mtime caching."""
        py_files = self.walker.walk_files(pattern="*.py", raise_on_limit=False)
        all_classes: dict[str, str] = {}    # class_name -> file_path
        all_functions: dict[str, str] = {}  # func_name -> file_path
        all_imports: set[str] = set()

        for f in py_files:
            symbols = self._parse_file_symbols(f)
            rel_path = f.relative_to(self.root).as_posix()

            for c in symbols["classes"]:
                all_classes[c] = rel_path
            for fn in symbols["functions"]:
                all_functions[fn] = rel_path
            all_imports.update(symbols["imports"])

        return {
            "classes": all_classes,
            "functions": all_functions,
            "imports": sorted(list(all_imports)),
            "indexed_files_count": len(py_files),
        }

    async def get_state(self) -> dict[str, Any]:
        """Fetch full symbol graph summary dictionary."""
        loop = asyncio.get_running_loop()
        if self._executor:
            return await loop.run_in_executor(self._executor, self._index_all_files_sync)
        return self._index_all_files_sync()

    async def query(self, entity: str) -> list[ProviderFact]:
        """
        Query symbol graph for classes, functions, or specific symbols.
        
        Supported entity queries:
          - "class:<name>" -> finds file location of class
          - "function:<name>" -> finds file location of function
          - "classes" -> lists all indexed classes
          - "functions" -> lists all indexed functions
          - "symbols" / "all" -> complete symbol summary
        """
        facts: list[ProviderFact] = []
        entity_norm = entity.strip()
        state = await self.get_state()

        if entity_norm.lower().startswith("class:"):
            target = entity_norm.split(":", 1)[1].strip()
            loc = state["classes"].get(target)
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity=f"class:{target}",
                    value=loc if loc else "not_found",
                )
            )
            return facts

        if entity_norm.lower().startswith("function:"):
            target = entity_norm.split(":", 1)[1].strip()
            loc = state["functions"].get(target)
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity=f"function:{target}",
                    value=loc if loc else "not_found",
                )
            )
            return facts

        if entity_norm.lower() in ("classes", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="classes",
                    value=list(state["classes"].keys())[:50],
                )
            )

        if entity_norm.lower() in ("functions", "all"):
            facts.append(
                ProviderFact(
                    domain=self.domain,
                    entity="functions",
                    value=list(state["functions"].keys())[:50],
                )
            )

        return facts
