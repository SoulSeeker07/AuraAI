"""
AST-Based Static Import and Safety Checker
Location: src/codeact/static_checker.py

Inspects generated Python code prior to execution to enforce library allowlists,
prevent network egress, and detect sandbox escape tricks (eval/exec/__import__/ctypes).
"""

from __future__ import annotations

import ast
import logging
from typing import Sequence

from .models import StaticCheckResult

logger = logging.getLogger(__name__)

# Modules that are permanently forbidden under all circumstances
BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        # Network access
        "socket",
        "http",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "ftplib",
        "smtplib",
        "imaplib",
        "poplib",
        "asyncio.streams",
        # Subprocess and shell execution
        "subprocess",
        "multiprocessing",
        # Native interop / binary escape
        "ctypes",
        "cffi",
        "win32api",
        "win32con",
        "win32com",
        "win32process",
        "win32security",
        "win32gui",
        # Dynamic code import / introspection
        "importlib",
        "imp",
        # Serialization injection
        "pickle",
        "shelve",
        "marshal",
        # System-level power / shutdown
        "winreg",
    }
)

# Standard library modules that are inherently safe for computation/formatting
DEFAULT_ALLOWED_STDLIB: frozenset[str] = frozenset(
    {
        "math",
        "datetime",
        "dateutil",
        "time",
        "json",
        "csv",
        "pathlib",
        "re",
        "collections",
        "itertools",
        "functools",
        "typing",
        "io",
        "sys",
        "os.path",
        "textwrap",
        "uuid",
        "random",
        "string",
        "decimal",
        "fractions",
        "statistics",
        "hashlib",
        "base64",
        "copy",
        "dataclasses",
        "enum",
    }
)

# Package name aliases to root import module names
PACKAGE_ALIASES: dict[str, str] = {
    "python-pptx": "pptx",
    "python-docx": "docx",
    "pillow": "PIL",
    "fpdf2": "fpdf",
}

# Forbidden function and attribute identifiers
BLOCKED_CALLS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "globals",
        "locals",
        "getattr",
        "setattr",
        "delattr",
        "system",
        "popen",
        "spawn",
        "execv",
        "execl",
        "kill",
        "rmdir",
        "rmtree",
    }
)

# Dangerous function/method names prohibited from ImportFrom symbols and direct calls
DANGEROUS_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "system",
        "popen",
        "spawn",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "execv",
        "execve",
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execvp",
        "execvpe",
        "kill",
        "killpg",
        "fork",
        "forkpty",
        "unlink",
        "rmdir",
        "rmtree",
        "move",
        "copytree",
        "chown",
        "chmod",
    }
)


def _canonicalize_module(name: str) -> str:
    """Resolve package aliases to actual import module root."""
    name_clean = name.strip().lower()
    return PACKAGE_ALIASES.get(name_clean, name_clean)


class _SafetyVisitor(ast.NodeVisitor):
    def __init__(self, allowed_roots: set[str]):
        self.allowed_roots = allowed_roots
        self.blocked_imports: list[str] = []
        self.disallowed_imports: list[str] = []
        self.violations: list[str] = []
        self._imported_aliases: dict[str, str] = {}

    def _check_module_name(self, full_name: str, node: ast.AST) -> None:
        root_name = full_name.split(".")[0].lower()
        canonical_root = _canonicalize_module(root_name)

        # 1. Hard blocked modules
        if root_name in BLOCKED_MODULES or full_name.lower() in BLOCKED_MODULES:
            self.blocked_imports.append(full_name)
            return

        # 2. Check against allowed roots
        if canonical_root not in self.allowed_roots and root_name not in self.allowed_roots:
            self.disallowed_imports.append(full_name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module_name(alias.name, node)
            as_name = alias.asname or alias.name
            self._imported_aliases[as_name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self._check_module_name(node.module, node)
            # Inspect imported symbols (e.g. from os import system, from shutil import rmtree)
            for alias in node.names:
                full_sym = f"{node.module}.{alias.name}"
                if alias.name.lower() in DANGEROUS_ATTRIBUTES or full_sym.lower() in BLOCKED_MODULES:
                    self.violations.append(f"Import of dangerous function/symbol '{full_sym}'")
                as_name = alias.asname or alias.name
                self._imported_aliases[as_name] = full_sym
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            if node.id in BLOCKED_CALLS:
                self.violations.append(f"Forbidden identifier referenced: '{node.id}'")
            elif node.id in DANGEROUS_ATTRIBUTES:
                self.violations.append(f"Dangerous OS identifier referenced: '{node.id}'")
            orig_sym = self._imported_aliases.get(node.id)
            if orig_sym and (orig_sym in BLOCKED_CALLS or orig_sym.split(".")[-1] in DANGEROUS_ATTRIBUTES):
                self.violations.append(f"Forbidden aliased identifier referenced: '{node.id}' ({orig_sym})")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            attr_name = node.attr
            base_name = node.value.id if isinstance(node.value, ast.Name) else ""
            canonical_base = self._imported_aliases.get(base_name, base_name)
            if attr_name in BLOCKED_CALLS:
                self.violations.append(f"Forbidden attribute access: '{base_name + '.' if base_name else ''}{attr_name}'")
            elif attr_name == "unlink":
                # Unconditional: .unlink() is always a filesystem deletion operation (Path.unlink, p.unlink, os.unlink)
                self.violations.append(f"Dangerous file deletion attribute access: '{base_name + '.' if base_name else ''}unlink'")
            elif attr_name == "remove":
                # Flag .remove() when called on os/shutil/pathlib (including aliased imports like 'import os as o') or Path constructor
                is_path_call = False
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name) and node.value.func.id in ("Path", "pathlib"):
                        is_path_call = True
                    elif isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "Path":
                        is_path_call = True
                if canonical_base in ("os", "shutil", "pathlib", "Path") or is_path_call:
                    self.violations.append(f"Dangerous file deletion attribute access: '{base_name + '.' if base_name else ''}remove'")
            elif attr_name in DANGEROUS_ATTRIBUTES:
                self.violations.append(f"Dangerous OS attribute access: '{base_name + '.' if base_name else ''}{attr_name}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # 1. Direct calls to blocked builtins / dangerous names (eval, exec, system, popen, getattr, etc.)
        if isinstance(node.func, ast.Name):
            func_id = node.func.id
            if func_id in BLOCKED_CALLS or func_id in DANGEROUS_ATTRIBUTES:
                self.violations.append(f"Direct call to forbidden identifier '{func_id}'")
            orig_sym = self._imported_aliases.get(func_id)
            if orig_sym and (orig_sym in BLOCKED_CALLS or orig_sym.split(".")[-1] in DANGEROUS_ATTRIBUTES):
                self.violations.append(f"Call to aliased dangerous symbol '{func_id}' ({orig_sym})")

        # 2. Attribute calls (e.g. os.system, shutil.rmtree, sys.exit, etc.)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            base_name = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
            if attr_name in DANGEROUS_ATTRIBUTES or attr_name in BLOCKED_CALLS:
                self.violations.append(
                    f"Call to dangerous method '{base_name + '.' if base_name else ''}{attr_name}'"
                )

        # 3. Dynamic reflection calls: getattr(os, "system")("...")
        elif isinstance(node.func, ast.Call):
            if isinstance(node.func.func, ast.Name) and node.func.func.id == "getattr":
                self.violations.append("Dynamic function invocation via getattr(...) call")

        self.generic_visit(node)


def check_imports(code: str, allowed_libraries: Sequence[str] | None = None) -> StaticCheckResult:
    """
    Parse code AST and verify that all imports and calls conform to safety policies.

    Args:
        code: Python source code string
        allowed_libraries: External package names requested for this task (e.g. ['python-pptx'])

    Returns:
        StaticCheckResult indicating pass/fail with structured violation details.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as syn_err:
        return StaticCheckResult(
            passed=False,
            violations=[f"SyntaxError: {syn_err}"],
            reason=f"Code fails Python syntax validation: {syn_err}",
        )

    # Build full allowed root set
    allowed_roots: set[str] = set(DEFAULT_ALLOWED_STDLIB)
    # Also allow basic 'os' as long as dangerous methods are caught by call inspection
    allowed_roots.add("os")

    if allowed_libraries:
        for lib in allowed_libraries:
            canonical = _canonicalize_module(lib)
            allowed_roots.add(canonical)
            allowed_roots.add(lib.lower())

    visitor = _SafetyVisitor(allowed_roots)
    visitor.visit(tree)

    has_blocked = bool(visitor.blocked_imports)
    has_disallowed = bool(visitor.disallowed_imports)
    has_violations = bool(visitor.violations)

    passed = not (has_blocked or has_disallowed or has_violations)

    reason = None
    if not passed:
        parts = []
        if visitor.blocked_imports:
            parts.append(f"Blocked security modules imported: {visitor.blocked_imports}")
        if visitor.disallowed_imports:
            parts.append(f"Modules not in allowed library list: {visitor.disallowed_imports}")
        if visitor.violations:
            parts.append(f"Security violations detected: {visitor.violations}")
        reason = " | ".join(parts)

    return StaticCheckResult(
        passed=passed,
        blocked_imports=visitor.blocked_imports,
        disallowed_imports=visitor.disallowed_imports,
        violations=visitor.violations,
        reason=reason,
    )
