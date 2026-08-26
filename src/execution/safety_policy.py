"""
Configurable Safety Policy Engine
Location: src/execution/safety_policy.py

Enforces system-wide safety constraints across OS operations, protecting critical
applications (e.g. Code.exe, explorer.exe, System) from accidental termination or modification.
"""

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SafetyPolicy:
    """
    Central Safety Policy Engine.
    Configurable via config/safety_policy.yaml or runtime settings.
    """

    _instance: Optional["SafetyPolicy"] = None

    DEFAULT_PROTECTED_APPS = [
        "code.exe",
        "vscode",
        "vs code",
        "visual studio code",
        "explorer.exe",
        "system",
        "python.exe",
        "cmd.exe",
        "command prompt",
        "powershell.exe",
        "powershell",
        "windowsterminal.exe",
        "terminal",
        "conhost.exe",
        "bash.exe",
    ]

    @classmethod
    def get_instance(cls) -> "SafetyPolicy":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, config_path: Path | None = None):
        self.protected_applications: list[str] = list(self.DEFAULT_PROTECTED_APPS)
        self.protected_directories: list[str] = ["c:\\windows", "c:\\system32"]
        self._load_config(config_path)

    def _load_config(self, config_path: Path | None = None) -> None:
        if config_path is None:
            root = Path(__file__).resolve().parent.parent.parent
            config_path = root / "config" / "safety_policy.yaml"

        if config_path and config_path.exists():
            try:
                import yaml

                data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if data and isinstance(data, dict):
                    apps = data.get("protected_applications", [])
                    for app in apps:
                        clean = str(app).lower()
                        if clean not in self.protected_applications:
                            self.protected_applications.append(clean)
                    dirs = data.get("protected_directories", [])
                    for d in dirs:
                        clean = str(d).lower()
                        if clean not in self.protected_directories:
                            self.protected_directories.append(clean)
                logger.info(f"SafetyPolicy loaded from {config_path.name}")
            except Exception as e:
                logger.warning(f"SafetyPolicy config load fallback: {e}")

    def is_protected_app(self, app_name_or_title: str) -> bool:
        """Check if an application name or window title is protected from close/terminate operations."""
        if not app_name_or_title:
            return False
        clean = app_name_or_title.strip().lower()
        clean_base = clean.replace(".exe", "")
        for protected in self.protected_applications:
            p_clean = protected.lower()
            p_base = p_clean.replace(".exe", "")
            if (
                p_clean in clean
                or clean == p_clean
                or clean_base == p_base
                or (clean.endswith(".exe") and clean == p_clean)
            ):
                return True
        return False

    def check_close_permission(self, app_name_or_title: str) -> bool:
        """
        Validate permission to close an application window.

        Raises PermissionError if app is protected.
        """
        if self.is_protected_app(app_name_or_title):
            raise PermissionError(
                f"Safety Policy Exception: Application '{app_name_or_title}' is protected by SafetyPolicy and cannot be closed."
            )
        return True
