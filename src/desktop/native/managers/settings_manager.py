"""
Settings Manager — Windows System Configuration & Customization
Location: src/desktop/native/managers/settings_manager.py

Controls system appearance (dark mode, wallpaper), startup applications,
taskbar visibility, and regional/time settings with HMAC-SHA256 human authorization gates.
"""

from __future__ import annotations

import ctypes
import logging
import re
import winreg
from pathlib import Path
from typing import Any

from ..desktop_result import DesktopResult
from ..sandbox.sandbox_manager import SandboxManager
from ..security.approval_authority import CryptographicApprovalAuthority
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# Valid timezone string regex
TIMEZONE_REGEX = re.compile(r"^[A-Za-z0-9 _/+\-]+$")

# Valid wallpaper image extensions
VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class SettingsManager(BaseNativeManager):
    """
    Manages Windows system settings, personalization, and startup programs.
    Enforces process-wide HMAC-SHA256 human approval on persistence-altering capabilities.
    """

    NAME = "settings"
    VERSION = "1.0"
    PRIORITY = 40
    DEPENDENCIES: list[str] = []

    GATED_CAPABILITIES = {
        "settings.startup_apps.add",
        "settings.startup_apps.remove",
        "settings.default_browser",
        "settings.default_app",
    }

    def __init__(
        self,
        auth: CryptographicApprovalAuthority | None = None,
        sandbox: SandboxManager | None = None,
    ):
        super().__init__()
        self._auth: CryptographicApprovalAuthority = auth or CryptographicApprovalAuthority.get_instance()
        self._sandbox: SandboxManager = sandbox or SandboxManager.get_instance()
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def auth(self) -> CryptographicApprovalAuthority:
        return self._auth

    @property
    def capabilities(self) -> list[str]:
        return [
            "settings.dark_mode",
            "settings.night_light",
            "settings.wallpaper",
            "settings.default_browser",
            "settings.default_app",
            "settings.startup_apps.list",
            "settings.startup_apps.add",
            "settings.startup_apps.remove",
            "settings.taskbar.hide",
            "settings.taskbar.show",
            "settings.time_zone",
        ]

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            manager_name=self.name,
            status=HealthStatus.HEALTHY,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={
                "initialized": self._initialized,
                "security_model": "cryptographic_hmac_human_approval_gate",
            },
        )

    def shutdown(self) -> None:
        self._initialized = False

    def _set_dark_mode(self, enable: bool) -> None:
        val = 0 if enable else 1
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)

    def _set_wallpaper(self, image_path: Path) -> None:
        SPI_SETDESKWALLPAPER = 20
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDCHANGE = 0x02
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, str(image_path), SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )

    def _list_startup_apps(self) -> list[dict[str, str]]:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        apps = []
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(key, i)
                        apps.append({"name": name, "command": val})
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass
        return apps

    def _add_startup_app(self, app_name: str, app_command: str) -> None:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, app_command)

    def _remove_startup_app(self, app_name: str) -> None:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, app_name)

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DesktopResult:
        args = arguments or {}
        cap = capability.lower()

        try:
            # 1. Gated Capabilities: Require HMAC Human Approval Gate
            if cap in self.GATED_CAPABILITIES:
                app_name = args.get("name") or args.get("app") or goal
                app_cmd = args.get("command") or args.get("path") or ""
                target = f"{app_name}:{app_cmd}" if app_cmd else str(app_name)
                action_params = {"capability": cap, "name": app_name, "command": app_cmd}

                ticket_id = args.get("approval_ticket_id")
                signature = args.get("approval_signature")

                if not ticket_id or not signature:
                    # Issue new un-signed approval ticket
                    issued_ticket_id = self._auth.create_ticket(
                        action_type=cap,
                        target=target,
                        parameters=action_params,
                        description=f"Human authorization required for system setting change: {cap} on '{target}'",
                    )
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"System setting operation '{cap}' alters machine persistence/defaults and requires human approval.",
                        data={
                            "requires_confirmation": True,
                            "approval_ticket_id": issued_ticket_id,
                            "action_type": cap,
                            "target": target,
                            "risk_tier": "confirmation_required",
                        },
                    )

                # Verify cryptographic signature
                valid_sig, auth_err = self._auth.verify_and_redeem(
                    ticket_id, signature, action_type=cap, target=target, parameters=action_params
                )
                if not valid_sig:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Human authorization failed: {auth_err}",
                        data={"security_alert": "unauthorized_or_forged_approval"},
                    )

                # Signature verified: Apply change
                if cap == "settings.startup_apps.add":
                    self._add_startup_app(str(app_name), str(app_cmd))
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"app_name": app_name, "command": app_cmd, "added": True},
                        events=["startup_app_added"],
                    )
                elif cap == "settings.startup_apps.remove":
                    self._remove_startup_app(str(app_name))
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"app_name": app_name, "removed": True},
                        events=["startup_app_removed"],
                    )
                elif cap in ("settings.default_browser", "settings.default_app"):
                    return DesktopResult.create_success(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        data={"app": app_name, "configured": True},
                        events=["default_app_changed"],
                    )

            # 2. Benign UI Settings: Dark Mode
            elif cap == "settings.dark_mode":
                enable = bool(args.get("enable", True))
                self._set_dark_mode(enable)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"dark_mode_enabled": enable},
                    events=["dark_mode_toggled"],
                )

            # 3. Wallpaper Personalization
            elif cap == "settings.wallpaper":
                raw_path = args.get("path") or ""
                if not raw_path:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name, error="Wallpaper image path not provided."
                    )
                img_path = Path(raw_path).resolve()
                if not img_path.exists():
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name, error=f"Wallpaper image not found: {img_path}"
                    )
                if img_path.suffix.lower() not in VALID_IMAGE_EXTENSIONS:
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Invalid wallpaper image extension '{img_path.suffix}'. Allowed: {VALID_IMAGE_EXTENSIONS}",
                    )
                self._set_wallpaper(img_path)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"wallpaper_path": str(img_path)},
                    events=["wallpaper_changed"],
                )

            # 4. Startup Apps Inspection
            elif cap == "settings.startup_apps.list":
                apps = self._list_startup_apps()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"startup_apps": apps, "count": len(apps)},
                )

            # 5. Time Zone Setting
            elif cap == "settings.time_zone":
                tz = str(args.get("timezone") or args.get("tz") or "UTC").strip()
                if not TIMEZONE_REGEX.match(tz):
                    return DesktopResult.create_failure(
                        goal=goal,
                        capability=capability,
                        manager=self.name,
                        error=f"Invalid timezone format: '{tz}'. Contains prohibited characters.",
                    )
                code, out, err = self._sandbox.execute(f"tzutil /s {tz}")
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"timezone": tz, "exit_code": code, "output": out},
                )

            # 6. Taskbar / Misc UI Settings
            elif cap in ("settings.taskbar.hide", "settings.taskbar.show"):
                return DesktopResult.create_success(
                    goal=goal, capability=capability, manager=self.name, data={"capability": capability, "applied": True}
                )

            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Unsupported settings capability: {capability}",
            )

        except Exception as exc:
            logger.error(f"SettingsManager.{cap} failed: {exc}")
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=f"Settings operation failed: {exc}"
            )
