"""
Project Index — Persistent Structural Memory

Provides durable, incremental structural indexing of code repositories.
Stores symbols, signatures, imports, and static call edges in SQLite (WAL mode).
Invalidates only modified files based on sha256 content hashes.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


@dataclass
class SymbolRecord:
    """Represents a symbol stored in the persistent project index."""

    id: int | None
    file_path: str
    symbol_type: str  # 'function' | 'async_function' | 'class' | 'method'
    name: str
    qualified_name: str
    signature: str | None = None
    docstring: str | None = None
    line_start: int | None = None
    line_end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProjectIndex:
    """
    Manages SQLite-backed structural memory for a repository.

    Location: <repo_root>/.aura/memory/project_index.sqlite3
    """

    def __init__(self, repo_root: Path | str, db_path: Path | str | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        if db_path is not None:
            self.db_path = Path(db_path).resolve()
        else:
            self.db_path = self.repo_root / ".aura" / "memory" / "project_index.sqlite3"

        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    last_scanned_at TEXT NOT NULL,
                    mtime REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
                    symbol_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    qualified_name TEXT NOT NULL,
                    signature TEXT,
                    docstring TEXT,
                    line_start INTEGER,
                    line_end INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
                CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
                CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);

                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
                    imported_module TEXT NOT NULL,
                    imported_names TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_imports_module ON imports(imported_module);
                CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file_path);

                CREATE TABLE IF NOT EXISTS call_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    caller_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
                    callee_qualified_name TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_callee_name ON call_edges(callee_qualified_name);
                """
            )
            conn.commit()

    @staticmethod
    def _compute_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _format_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Reconstruct raw signature string from AST arguments."""
        try:
            args = node.args
            parts = []

            # Positional only args
            for a in getattr(args, "posonlyargs", []):
                ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
                parts.append(f"{a.arg}{ann}")
            if getattr(args, "posonlyargs", []):
                parts.append("/")

            # Regular args with defaults
            defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
            for a, d in zip(args.args, defaults):
                ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
                default_str = f" = {ast.unparse(d)}" if d is not None else ""
                parts.append(f"{a.arg}{ann}{default_str}")

            # Vararg (*args)
            if args.vararg:
                ann = f": {ast.unparse(args.vararg.annotation)}" if args.vararg.annotation else ""
                parts.append(f"*{args.vararg.arg}{ann}")
            elif args.kwonlyargs:
                parts.append("*")

            # Keyword-only args
            kw_defaults = args.kw_defaults
            for a, d in zip(args.kwonlyargs, kw_defaults):
                ann = f": {ast.unparse(a.annotation)}" if a.annotation else ""
                default_str = f" = {ast.unparse(d)}" if d is not None else ""
                parts.append(f"{a.arg}{ann}{default_str}")

            # Kwarg (**kwargs)
            if args.kwarg:
                ann = f": {ast.unparse(args.kwarg.annotation)}" if args.kwarg.annotation else ""
                parts.append(f"**{args.kwarg.arg}{ann}")

            returns_str = ""
            if node.returns:
                returns_str = f" -> {ast.unparse(node.returns)}"

            prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
            return f"{prefix}{node.name}({', '.join(parts)}){returns_str}"
        except Exception:
            return f"def {node.name}(...)"

    def _extract_file_data(
        self, file_path_str: str, source: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[int, str]]]:
        """
        Parses source and extracts:
        - symbols: list of symbol dicts
        - imports: list of import dicts
        - call_edges: list of (symbol_index_in_list, callee_name)
        """
        ext = Path(file_path_str).suffix.lower()
        if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            try:
                from .language_providers.typescript import TypeScriptLanguageProvider
                ts_provider = TypeScriptLanguageProvider()
                return ts_provider.get_index_records(file_path_str, source)
            except Exception as e:
                logger.warning(f"ProjectIndex: Tree-sitter JS/TS parse error for {file_path_str}: {e}")

        tree = ast.parse(source, filename=file_path_str)

        # Derive module path relative to repo_root
        try:
            rel_path = Path(file_path_str).relative_to(self.repo_root)
            parts = list(rel_path.with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts.pop()
            module_name = ".".join(parts) if parts else Path(file_path_str).stem
        except ValueError:
            module_name = Path(file_path_str).stem

        symbols: list[dict[str, Any]] = []
        imports: list[dict[str, Any]] = []
        call_edges_unresolved: list[tuple[int, str]] = []

        # 1. Extract Imports
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "file_path": file_path_str,
                        "imported_module": alias.name,
                        "imported_names": json.dumps([alias.asname or alias.name]),
                    })
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append({
                    "file_path": file_path_str,
                    "imported_module": mod,
                    "imported_names": json.dumps(names),
                })

        # 2. Extract Symbols & Calls
        def _resolve_call_name(call_node: ast.Call) -> str | None:
            func = call_node.func
            if isinstance(func, ast.Name):
                return func.id
            elif isinstance(func, ast.Attribute):
                try:
                    return ast.unparse(func)
                except Exception:
                    return func.attr
            return None

        def _traverse_symbols(parent_node: ast.AST, scope_prefix: str) -> None:
            for child in getattr(parent_node, "body", []):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sym_type = "method" if scope_prefix else ("async_function" if isinstance(child, ast.AsyncFunctionDef) else "function")
                    qual_name = f"{scope_prefix}.{child.name}" if scope_prefix else f"{module_name}.{child.name}"
                    sig = self._format_signature(child)
                    doc = ast.get_docstring(child)
                    line_start = getattr(child, "lineno", None)
                    line_end = getattr(child, "end_lineno", line_start)

                    sym_idx = len(symbols)
                    symbols.append({
                        "file_path": file_path_str,
                        "symbol_type": sym_type,
                        "name": child.name,
                        "qualified_name": qual_name,
                        "signature": sig,
                        "docstring": doc,
                        "line_start": line_start,
                        "line_end": line_end,
                    })

                    # Traverse calls inside function body
                    for inner in ast.walk(child):
                        if isinstance(inner, ast.Call):
                            callee = _resolve_call_name(inner)
                            if callee:
                                call_edges_unresolved.append((sym_idx, callee))

                    # Nested functions
                    _traverse_symbols(child, qual_name)

                elif isinstance(child, ast.ClassDef):
                    qual_name = f"{scope_prefix}.{child.name}" if scope_prefix else f"{module_name}.{child.name}"
                    doc = ast.get_docstring(child)
                    line_start = getattr(child, "lineno", None)
                    line_end = getattr(child, "end_lineno", line_start)

                    symbols.append({
                        "file_path": file_path_str,
                        "symbol_type": "class",
                        "name": child.name,
                        "qualified_name": qual_name,
                        "signature": f"class {child.name}",
                        "docstring": doc,
                        "line_start": line_start,
                        "line_end": line_end,
                    })

                    # Methods and nested classes
                    _traverse_symbols(child, qual_name)

        _traverse_symbols(tree, "")

        return symbols, imports, call_edges_unresolved

    def _parse_and_upsert(
        self,
        conn: sqlite3.Connection,
        file_path: Path,
        content: bytes,
        mtime: float,
        content_hash: str,
    ) -> bool:
        """Parses a single file and upserts all tables atomically in the given connection."""
        file_path_str = str(file_path.resolve())
        now_str = datetime.now(timezone.utc).isoformat()

        try:
            source = content.decode("utf-8")
            symbols, imports, call_edges = self._extract_file_data(file_path_str, source)
        except Exception as e:
            logger.warning(f"ProjectIndex: Failed to parse {file_path_str}: {e}")
            return False

        # Clear existing file records (foreign keys cascade)
        conn.execute("DELETE FROM files WHERE path = ?", (file_path_str,))

        conn.execute(
            """
            INSERT INTO files (path, content_hash, last_scanned_at, mtime)
            VALUES (?, ?, ?, ?)
            """,
            (file_path_str, content_hash, now_str, mtime),
        )

        inserted_symbol_ids: list[int] = []
        for sym in symbols:
            cursor = conn.execute(
                """
                INSERT INTO symbols (file_path, symbol_type, name, qualified_name, signature, docstring, line_start, line_end)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sym["file_path"],
                    sym["symbol_type"],
                    sym["name"],
                    sym["qualified_name"],
                    sym["signature"],
                    sym["docstring"],
                    sym["line_start"],
                    sym["line_end"],
                ),
            )
            inserted_symbol_ids.append(cursor.lastrowid)

        for imp in imports:
            conn.execute(
                """
                INSERT INTO imports (file_path, imported_module, imported_names)
                VALUES (?, ?, ?)
                """,
                (imp["file_path"], imp["imported_module"], imp["imported_names"]),
            )

        for sym_idx, callee in call_edges:
            if sym_idx < len(inserted_symbol_ids):
                sym_id = inserted_symbol_ids[sym_idx]
                conn.execute(
                    """
                    INSERT INTO call_edges (caller_symbol_id, callee_qualified_name)
                    VALUES (?, ?)
                    """,
                    (sym_id, callee),
                )

        return True

    def scan(
        self,
        repo_root: Path | str | None = None,
        file_paths: list[Path] | None = None,
    ) -> dict[str, int]:
        """
        Incrementally re-scans the repository or supplied file list.
        Compares content hashes against the index.

        Returns statistics: {'unchanged': X, 'updated': Y, 'deleted': Z}
        """
        root = Path(repo_root or self.repo_root).resolve()

        IGNORED_DIRS = {
            ".venv",
            "venv",
            "env",
            ".git",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "node_modules",
            "build",
            "dist",
            ".aura_backups",
            ".staging",
            "artifacts",
        }

        SUPPORTED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
        disk_files: dict[str, Path] = {}
        if file_paths is None:
            import os

            for dirpath, dirnames, filenames in os.walk(str(root)):
                # In-place directory pruning prevents descending into large folders
                dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
                for fname in filenames:
                    ext = Path(fname).suffix.lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        p = Path(dirpath) / fname
                        disk_files[str(p.resolve())] = p
        else:
            for f in file_paths:
                if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.is_file():
                    disk_files[str(f.resolve())] = f

        stats = {"unchanged": 0, "updated": 0, "deleted": 0}

        with self._get_connection() as conn:
            # 1. Fetch current index cache (path -> (content_hash, mtime))
            cached_rows = conn.execute("SELECT path, content_hash, mtime FROM files").fetchall()
            cached_db_map = {row["path"]: (row["content_hash"], row["mtime"]) for row in cached_rows}

            # 2. Check for deleted files (in DB but not on disk within this scan scope)
            if file_paths is None:
                # Full scan: any cached path under repo_root not on disk is deleted
                for cached_path in list(cached_db_map.keys()):
                    if cached_path not in disk_files and cached_path.startswith(str(root)):
                        conn.execute("DELETE FROM files WHERE path = ?", (cached_path,))
                        stats["deleted"] += 1

            now_str = datetime.now(timezone.utc).isoformat()

            # 3. Check disk files for unchanged vs modified with mtime fast-path
            for path_str, path_obj in disk_files.items():
                try:
                    mtime = path_obj.stat().st_mtime

                    # Fast path: mtime identical -> 0 disk read, 0 hashing
                    if path_str in cached_db_map:
                        cached_hash, cached_mtime = cached_db_map[path_str]
                        if abs(cached_mtime - mtime) < 1e-4:
                            stats["unchanged"] += 1
                            continue

                        # mtime changed: read & hash to check if content actually changed
                        content = path_obj.read_bytes()
                        chash = self._compute_hash(content)
                        if chash == cached_hash:
                            # Touched without content change: update mtime only
                            conn.execute(
                                "UPDATE files SET mtime = ?, last_scanned_at = ? WHERE path = ?",
                                (mtime, now_str, path_str),
                            )
                            stats["unchanged"] += 1
                            continue

                        # Content actually changed: re-parse and upsert
                        success = self._parse_and_upsert(conn, path_obj, content, mtime, chash)
                        if success:
                            stats["updated"] += 1
                    else:
                        # New file
                        content = path_obj.read_bytes()
                        chash = self._compute_hash(content)
                        success = self._parse_and_upsert(conn, path_obj, content, mtime, chash)
                        if success:
                            stats["updated"] += 1
                except Exception as e:
                    logger.warning(f"Error scanning {path_str}: {e}")

            conn.commit()

        logger.info(
            f"ProjectIndex scan complete: {stats['unchanged']} unchanged, {stats['updated']} updated, {stats['deleted']} deleted"
        )
        return stats

    def invalidate_file(self, file_path: Path | str) -> bool:
        """
        Immediately re-scans a single file after a live write/edit operation.
        """
        p = Path(file_path).resolve()
        path_str = str(p)

        with self._get_connection() as conn:
            if not p.exists() or not p.is_file():
                conn.execute("DELETE FROM files WHERE path = ?", (path_str,))
                conn.commit()
                return True

            try:
                content = p.read_bytes()
                mtime = p.stat().st_mtime
                chash = self._compute_hash(content)
                success = self._parse_and_upsert(conn, p, content, mtime, chash)
                conn.commit()
                return success
            except Exception as e:
                logger.error(f"ProjectIndex invalidation failed for {path_str}: {e}")
                return False

    # ── Query API ─────────────────────────────────────────────────────────────

    def find_symbol(self, name: str) -> list[SymbolRecord]:
        """Find symbols matching a simple or qualified name."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, file_path, symbol_type, name, qualified_name, signature, docstring, line_start, line_end
                FROM symbols
                WHERE name = ? OR qualified_name = ? OR qualified_name LIKE ?
                ORDER BY name ASC
                """,
                (name, name, f"%.{name}"),
            ).fetchall()

            return [
                SymbolRecord(
                    id=row["id"],
                    file_path=row["file_path"],
                    symbol_type=row["symbol_type"],
                    name=row["name"],
                    qualified_name=row["qualified_name"],
                    signature=row["signature"],
                    docstring=row["docstring"],
                    line_start=row["line_start"],
                    line_end=row["line_end"],
                )
                for row in rows
            ]

    def get_file_symbols(self, path: str | Path) -> list[SymbolRecord]:
        """Get all symbols defined in a given file."""
        path_str = str(Path(path).resolve())
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, file_path, symbol_type, name, qualified_name, signature, docstring, line_start, line_end
                FROM symbols
                WHERE file_path = ?
                ORDER BY line_start ASC
                """,
                (path_str,),
            ).fetchall()

            return [
                SymbolRecord(
                    id=row["id"],
                    file_path=row["file_path"],
                    symbol_type=row["symbol_type"],
                    name=row["name"],
                    qualified_name=row["qualified_name"],
                    signature=row["signature"],
                    docstring=row["docstring"],
                    line_start=row["line_start"],
                    line_end=row["line_end"],
                )
                for row in rows
            ]

    def get_importers_of(self, module: str) -> list[str]:
        """
        Finds all file paths that import the given module name or sub-module.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT file_path
                FROM imports
                WHERE imported_module = ? OR imported_module LIKE ?
                """,
                (module, f"{module}.%"),
            ).fetchall()

            return [row["file_path"] for row in rows]

    def get_callers_of(self, qualified_name: str) -> list[SymbolRecord]:
        """
        Finds all caller symbols that make a call to the specified callee name.
        """
        # Search either exact callee_qualified_name or suffix match for unqualified calls
        simple_name = qualified_name.split(".")[-1]
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT s.id, s.file_path, s.symbol_type, s.name, s.qualified_name, s.signature, s.docstring, s.line_start, s.line_end
                FROM symbols s
                JOIN call_edges c ON s.id = c.caller_symbol_id
                WHERE c.callee_qualified_name = ? 
                   OR c.callee_qualified_name = ?
                   OR c.callee_qualified_name LIKE ?
                """,
                (qualified_name, simple_name, f"%.{simple_name}"),
            ).fetchall()

            return [
                SymbolRecord(
                    id=row["id"],
                    file_path=row["file_path"],
                    symbol_type=row["symbol_type"],
                    name=row["name"],
                    qualified_name=row["qualified_name"],
                    signature=row["signature"],
                    docstring=row["docstring"],
                    line_start=row["line_start"],
                    line_end=row["line_end"],
                )
                for row in rows
            ]

    def close(self) -> None:
        """Close hook (stateless per-call connections, no-op)."""
        pass
