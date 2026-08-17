"""
Active Editor Tracker
Location: src/workspace/editor_tracker.py

Tracks active code editor windows (Antigravity IDE, VS Code, Cursor, PyCharm, etc.),
extracts the active open document with fail-closed validation against the repository root,
and filters out cross-project windows.
"""

from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VALID_CODE_EXTENSIONS = frozenset({
    ".py", ".ts", ".js", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".md", ".rs", ".go", ".c", ".cpp", ".h", ".hpp",
    ".sql", ".sh", ".ps1", ".html", ".css", ".scss", ".xml", ".ini",
})

KNOWN_NON_CODE_VIEWS = frozenset({
    "implementation plan",
    "walkthrough",
    "settings",
    "welcome",
    "release notes",
    "extensions",
    "search",
    "source control",
    "run and debug",
    "git history",
    "output",
    "terminal",
    "problems",
})

EDITOR_BRAND_IDENTIFIERS = frozenset({
    "antigravity ide",
    "visual studio code",
    "visual studio",
    "code",
    "cursor",
    "pycharm",
    "sublime text",
    "intellij idea",
    "idea",
})

# Windows Win32 definitions
_DESKTOP_ENUMERATE = 0x0040
_DESKTOP_READOBJECTS = 0x0001
_DESKTOPENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


class EditorTracker:
    """
    Perception sensor that tracks open code editors and extracts the active document
    with fail-closed validation against workspace ground truth.
    """

    def __init__(self, root: Path | str | None = None):
        self.root: Path = Path(root).resolve() if root else Path.cwd().resolve()

    def parse_window_title(
        self,
        title: str,
        expected_workspace: str | None = None,
        repo_path: Path | None = None,
    ) -> dict[str, Any] | None:
        """
        Fail-closed parser for VS Code / Antigravity / Cursor window titles.

        Returns:
            dict with keys {"filename", "relative_path", "workspace", "is_dirty"} if valid,
            or None if the title is malformed, from a different project, or not a real file.
        """
        if not title or not isinstance(title, str):
            return None

        clean_title = title.strip()

        # Check for dirty/modified marker
        is_dirty = False
        if clean_title.startswith("● ") or clean_title.startswith("* "):
            is_dirty = True
            clean_title = clean_title[2:].strip()

        # Split by standard title separator
        parts = [p.strip() for p in clean_title.split(" - ") if p.strip()]
        if len(parts) < 2:
            return None

        # Locate editor brand component
        editor_idx = -1
        for idx, p in enumerate(parts):
            if p.lower() in EDITOR_BRAND_IDENTIFIERS:
                editor_idx = idx
                break

        if editor_idx == -1:
            return None

        candidate_file: str | None = None
        candidate_workspace: str | None = None

        if editor_idx == 2 and len(parts) >= 3:
            # Format A: file - workspace - editor
            candidate_file = parts[0]
            candidate_workspace = parts[1]
        elif editor_idx == 1 and len(parts) >= 3:
            # Format B: workspace - editor - view_or_file
            candidate_workspace = parts[0]
            candidate_file = parts[2]
        elif editor_idx == 1 and len(parts) == 2:
            # Format C: file - editor
            candidate_file = parts[0]
            candidate_workspace = None
        else:
            return None

        # 1. Strict workspace name filter
        target_ws = expected_workspace or self.root.name
        if target_ws and candidate_workspace:
            if candidate_workspace.lower() != target_ws.lower():
                # Cross-project editor window — ignore
                return None

        # Explicitly reject bare workspace window titles (e.g. 'AuraAI - Antigravity IDE' with no file)
        if target_ws and candidate_file.lower() == target_ws.lower():
            return None

        # 2. Filter out non-code UI tabs (e.g. Implementation Plan, Settings)
        candidate_lower = candidate_file.lower()
        if candidate_lower in KNOWN_NON_CODE_VIEWS:
            return None
        if any(candidate_lower.startswith(prefix) for prefix in ("extension:", "output:", "terminal:")):
            return None

        # 3. Check for recognized code extension
        file_path = Path(candidate_file)
        ext = file_path.suffix.lower()
        if not ext or ext not in VALID_CODE_EXTENSIONS:
            return None

        # 4. Filesystem ground-truth verification
        target_repo = repo_path or self.root
        resolved_rel_path: str = candidate_file
        if target_repo and target_repo.exists():
            direct = target_repo / candidate_file
            if direct.exists() and direct.is_file():
                try:
                    resolved_rel_path = direct.relative_to(target_repo).as_posix()
                except ValueError:
                    resolved_rel_path = direct.name
            else:
                # Search workspace for matching file basename
                matches = list(target_repo.glob(f"**/{file_path.name}"))
                valid_matches = [
                    m for m in matches
                    if not any(skip in m.parts for skip in (".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"))
                ]
                if valid_matches:
                    resolved_rel_path = valid_matches[0].relative_to(target_repo).as_posix()
                else:
                    # File does not exist within target repository — fail closed
                    return None

        return {
            "filename": file_path.name,
            "relative_path": resolved_rel_path,
            "workspace": candidate_workspace or (target_ws or ""),
            "is_dirty": is_dirty,
        }

    def get_active_editor_file_sync(
        self,
        expected_workspace: str | None = None,
        repo_path: Path | None = None,
    ) -> dict[str, Any] | None:
        """
        Synchronously enumerate visible desktop windows to locate the active or topmost editor
        and return its verified open file.

        Returns:
            Parsed file dict or None if no matching editor window with a valid file is found.
        """
        user32 = ctypes.windll.user32
        target_ws = expected_workspace or self.root.name
        target_repo = repo_path or self.root

        # 1. Fast check: is the foreground window an editor?
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd:
            length = user32.GetWindowTextLengthW(fg_hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(fg_hwnd, buff, length + 1)
                parsed = self.parse_window_title(buff.value, expected_workspace=target_ws, repo_path=target_repo)
                if parsed is not None:
                    return parsed

        # 2. Fallback check: enumerate all visible desktop windows (e.g. if user is looking at browser/voice)
        try:
            h_desk = user32.OpenInputDesktop(0, False, _DESKTOP_ENUMERATE | _DESKTOP_READOBJECTS)
        except Exception:
            h_desk = None

        if not h_desk:
            try:
                kernel32 = ctypes.windll.kernel32
                h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
            except Exception:
                h_desk = None

        if not h_desk:
            return None

        editor_candidates: list[dict[str, Any]] = []

        def _enum_cb(hwnd: int, lparam: int) -> bool:
            try:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    parsed = self.parse_window_title(
                        buff.value, expected_workspace=target_ws, repo_path=target_repo
                    )
                    if parsed is not None:
                        editor_candidates.append(parsed)
            except Exception:
                pass
            return True

        cb = _DESKTOPENUMPROC(_enum_cb)
        try:
            user32.EnumDesktopWindows(h_desk, cb, 0)
        except Exception as e:
            logger.debug(f"[EditorTracker] EnumDesktopWindows failed: {e}")
            return None

        if editor_candidates:
            # Return topmost matched candidate
            return editor_candidates[0]

        return None

    async def get_active_editor_file(
        self,
        expected_workspace: str | None = None,
        repo_path: Path | None = None,
    ) -> dict[str, Any] | None:
        """Asynchronously query active editor file on dedicated worker."""
        return await asyncio.to_thread(
            self.get_active_editor_file_sync, expected_workspace, repo_path
        )


__all__ = ["EditorTracker", "VALID_CODE_EXTENSIONS", "KNOWN_NON_CODE_VIEWS"]
