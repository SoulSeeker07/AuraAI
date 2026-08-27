"""
src/browser/profile_sync.py

Synchronizes the user's primary Google Chrome profile (cookies, preferences, history, sessions)
into Aura's persistent profile directory (~/.aura/browser_profile) so Aura browser automations
run directly with the user's logged-in identity without file-lock collisions with the active Chrome process.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def get_default_chrome_user_data_path() -> Path:
    """Return the system default Chrome User Data directory on Windows."""
    return Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))


def discover_target_profile_dir(profile_name_query: str = "sreekanta") -> str:
    """
    Inspect Chrome's Local State to find the profile folder directory name (e.g. 'Default', 'Profile 1')
    matching the target user name or email.
    """
    user_data = get_default_chrome_user_data_path()
    local_state_file = user_data / "Local State"

    if not local_state_file.exists():
        return "Default"

    try:
        with open(local_state_file, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
            profiles = data.get("profile", {}).get("info_cache", {})
            q = profile_name_query.lower()
            for prof_dir, info in profiles.items():
                name = (info.get("name") or "").lower()
                gaia = (info.get("gaia_name") or "").lower()
                user_name = (info.get("user_name") or "").lower()
                if q in name or q in gaia or q in user_name:
                    logger.info(f"[ProfileSync] Found target profile '{prof_dir}' matching query '{profile_name_query}' ({info.get('name')})")
                    return prof_dir
    except Exception as e:
        logger.debug(f"[ProfileSync] Error reading Chrome Local State: {e}")

    return "Default"


def sync_chrome_profile(
    target_profile_dir: str = "Default",
    aura_user_data_dir: Path | None = None,
) -> Path:
    """
    Copy user preferences, cookies, local storage, and session state from system Chrome
    into Aura's isolated persistent profile dir (~/.aura/browser_profile).
    """
    src_root = get_default_chrome_user_data_path()
    dst_root = aura_user_data_dir or (Path.home() / ".aura" / "browser_profile")
    dst_root.mkdir(parents=True, exist_ok=True)

    if not src_root.exists():
        return dst_root

    # 1. Copy Local State (contains encryption keys for DPAPI cookie/password decrypt)
    src_local_state = src_root / "Local State"
    dst_local_state = dst_root / "Local State"
    if src_local_state.exists():
        try:
            shutil.copy2(src_local_state, dst_local_state)
        except Exception:
            pass

    # 2. Copy Profile-Specific Files & WAL logs
    src_prof = src_root / target_profile_dir
    dst_prof = dst_root / target_profile_dir
    dst_prof.mkdir(parents=True, exist_ok=True)

    if src_prof.exists():
        files_to_sync = [
            "Preferences", "Secure Preferences", "Web Data", "Web Data-journal", "Web Data-wal",
            "Favicons", "History", "History-journal", "History-wal",
            "Bookmarks", "Login Data", "Login Data-journal", "Login Data-wal"
        ]
        for fname in files_to_sync:
            sf = src_prof / fname
            df = dst_prof / fname
            if sf.exists():
                try:
                    shutil.copy2(sf, df)
                except Exception:
                    pass

        # 3. Copy Network directory (all Cookies, Trust Tokens, Device Bound Sessions)
        src_net = src_prof / "Network"
        dst_net = dst_prof / "Network"
        if src_net.exists():
            dst_net.mkdir(parents=True, exist_ok=True)
            for item in src_net.iterdir():
                if item.is_file() and not item.name.endswith(".tmp"):
                    try:
                        shutil.copy2(item, dst_net / item.name)
                    except Exception:
                        pass

        # 4. Copy Local Storage, Session Storage & IndexedDB for modern web sessions & auth tokens
        for storage_dir_name in ["Local Storage", "Session Storage", "IndexedDB"]:
            src_storage = src_prof / storage_dir_name
            dst_storage = dst_prof / storage_dir_name
            if src_storage.exists():
                try:
                    shutil.copytree(src_storage, dst_storage, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.lock", "*.tmp", "*LOCK*"))
                except Exception as ex:
                    logger.debug(f"[ProfileSync] Storage sync notice for {storage_dir_name}: {ex}")

    logger.info(f"[ProfileSync] Profile '{target_profile_dir}' synced to {dst_root}")
    return dst_root
