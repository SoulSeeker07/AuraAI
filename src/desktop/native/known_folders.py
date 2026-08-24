"""
Windows Known-Folder Resolution Module
Location: src/desktop/native/known_folders.py

Resolves standard Windows user folders (Documents, Downloads, Desktop, Pictures,
Music, Videos) honoring OneDrive Known Folder Move (KFM) redirection, with
graceful cross-platform and home directory fallbacks.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Standard known folder GUID mapping
_FOLDERID_NAMES: dict[str, str] = {
    "documents": "FOLDERID_Documents",
    "downloads": "FOLDERID_Downloads",
    "desktop": "FOLDERID_Desktop",
    "pictures": "FOLDERID_Pictures",
    "music": "FOLDERID_Music",
    "videos": "FOLDERID_Videos",
}

_FALLBACK_SUBDIRS: dict[str, str] = {
    "documents": "Documents",
    "downloads": "Downloads",
    "desktop": "Desktop",
    "pictures": "Pictures",
    "music": "Music",
    "videos": "Videos",
}


def resolve_known_folder(name: str) -> Path:
    """
    Resolve a standard user folder name to its canonical Path.
    
    Prefers Windows shell API (SHGetKnownFolderPath via win32com.shell) to properly
    honor OneDrive KFM redirection, falling back to Path.home() / subdir if unavailable.
    """
    clean_name = name.lower().strip()
    if clean_name.endswith(" folder"):
        clean_name = clean_name[:-7].strip()
    elif clean_name.endswith(" directory"):
        clean_name = clean_name[:-10].strip()

    if clean_name not in _FOLDERID_NAMES and clean_name.rstrip("s") in _FOLDERID_NAMES:
        clean_name = clean_name.rstrip("s")

    if clean_name not in _FOLDERID_NAMES:
        raise ValueError(
            f"Unknown known folder name '{name}'. Valid names: {list(_FOLDERID_NAMES.keys())}"
        )

    # 1. Try Windows shell API via win32com.shell
    if os.name == "nt":
        try:
            from win32com.shell import shell

            attr_name = _FOLDERID_NAMES[clean_name]
            folder_id = getattr(shell, attr_name, None)
            if folder_id is not None:
                path_str = shell.SHGetKnownFolderPath(folder_id, 0, None)
                if path_str and Path(path_str).exists():
                    return Path(path_str).resolve()
        except Exception as exc:
            logger.debug(f"win32com.shell SHGetKnownFolderPath failed for '{clean_name}': {exc}")

    # 2. Fallback to standard user home directory subfolder
    sub_dir = _FALLBACK_SUBDIRS[clean_name]
    fallback_path = (Path.home() / sub_dir).resolve()
    if fallback_path.exists():
        return fallback_path

    # Check OneDrive under user profile if standard home subfolder didn't exist
    onedrive_dir = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive_dir:
        onedrive_candidate = (Path(onedrive_dir) / sub_dir).resolve()
        if onedrive_candidate.exists():
            return onedrive_candidate

    return fallback_path
