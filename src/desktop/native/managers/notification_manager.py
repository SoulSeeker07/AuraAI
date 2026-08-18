"""
Notification Manager — Windows System Notifications & Alerts
Location: src/desktop/native/managers/notification_manager.py

Provides Windows toast notifications, message box alerts, audio cues,
and scheduled notification queues.
"""

import ctypes
import logging
import subprocess
import threading
import time
import uuid
import winsound
from typing import Any

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)


class NotificationManager(BaseNativeManager):
    """
    Manages desktop notifications, toast popups, message boxes, and audio alerts.
    """

    NAME = "notification"
    VERSION = "1.0"
    PRIORITY = 30
    DEPENDENCIES: list[str] = []

    def __init__(self):
        super().__init__()
        self._scheduled_notifications: dict[str, dict[str, Any]] = {}
        self._initialized = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        return [
            "notify.toast",
            "notify.alert",
            "notify.schedule",
            "notify.clear",
            "notify.list",
            "notify.sound",
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
                "pending_scheduled": len(self._scheduled_notifications),
            },
        )

    def shutdown(self) -> None:
        self._scheduled_notifications.clear()
        self._initialized = False

    def _show_toast_ps(self, title: str, message: str) -> None:
        """Show toast using PowerShell Windows.UI.Notifications or NotifyIcon fallback."""
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $template = @"
        <toast>
            <visual>
                <binding template="ToastGeneric">
                    <text>{title}</text>
                    <text>{message}</text>
                </binding>
            </visual>
        </toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Aura AI").Show($toast)
        """
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                timeout=5.0,
            )
        except Exception:
            # Fallback to NotifyIcon balloon tip
            fallback = f"""
            Add-Type -AssemblyName System.Windows.Forms
            $global:balloon = New-Object System.Windows.Forms.NotifyIcon
            $path = (Get-Process -id $pid).Path
            $balloon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon($path)
            $balloon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
            $balloon.BalloonTipText = '{message}'
            $balloon.BalloonTipTitle = '{title}'
            $balloon.Visible = $true
            $balloon.ShowBalloonTip(5000)
            """
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", fallback],
                capture_output=True,
                timeout=5.0,
            )

    def _show_alert_dialog(self, title: str, message: str, alert_type: str = "ok") -> int:
        """Show native Win32 MessageBox modal."""
        MB_OK = 0x00000000
        MB_OKCANCEL = 0x00000001
        MB_YESNO = 0x00000004
        MB_ICONINFORMATION = 0x00000040

        flags = MB_ICONINFORMATION
        if alert_type.lower() == "yesno":
            flags |= MB_YESNO
        elif alert_type.lower() == "okcancel":
            flags |= MB_OKCANCEL
        else:
            flags |= MB_OK

        return ctypes.windll.user32.MessageBoxW(0, message, title, flags)

    def _play_sound(self, sound_type: str = "asterisk") -> None:
        """Play Windows standard sound."""
        sound_map = {
            "asterisk": winsound.MB_ICONASTERISK,
            "exclamation": winsound.MB_ICONEXCLAMATION,
            "hand": winsound.MB_ICONHAND,
            "question": winsound.MB_ICONQUESTION,
            "ok": winsound.MB_OK,
        }
        winsound.MessageBeep(sound_map.get(sound_type.lower(), winsound.MB_OK))

    def _schedule_worker(self, notif_id: str, title: str, message: str, delay_seconds: float) -> None:
        time.sleep(delay_seconds)
        if notif_id in self._scheduled_notifications:
            self._show_toast_ps(title, message)
            self._play_sound("asterisk")
            self._scheduled_notifications.pop(notif_id, None)

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
            if cap == "notify.toast":
                title = args.get("title") or "Aura AI"
                msg = args.get("message") or args.get("text") or goal
                self._show_toast_ps(title, msg)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"title": title, "message": msg},
                    events=["toast_displayed"],
                )

            elif cap == "notify.alert":
                title = args.get("title") or "Aura AI Alert"
                msg = args.get("message") or args.get("text") or goal
                alert_type = args.get("type", "ok")
                res_code = self._show_alert_dialog(title, msg, alert_type)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"title": title, "message": msg, "response_code": res_code},
                    events=["alert_displayed"],
                )

            elif cap == "notify.sound":
                sound_type = args.get("sound_type", "asterisk")
                self._play_sound(sound_type)
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"sound_type": sound_type},
                    events=["sound_played"],
                )

            elif cap == "notify.schedule":
                title = args.get("title") or "Aura AI Reminder"
                msg = args.get("message") or args.get("text") or goal
                delay = float(args.get("delay_seconds", 60.0))
                notif_id = f"notif_{uuid.uuid4().hex[:8]}"

                self._scheduled_notifications[notif_id] = {
                    "id": notif_id,
                    "title": title,
                    "message": msg,
                    "scheduled_at": time.time(),
                    "deliver_at": time.time() + delay,
                }

                t = threading.Thread(
                    target=self._schedule_worker,
                    args=(notif_id, title, msg, delay),
                    daemon=True,
                )
                t.start()

                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"id": notif_id, "title": title, "delay_seconds": delay},
                    events=["notification_scheduled"],
                )

            elif cap == "notify.list":
                items = list(self._scheduled_notifications.values())
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"scheduled_notifications": items},
                )

            elif cap == "notify.clear":
                count = len(self._scheduled_notifications)
                self._scheduled_notifications.clear()
                return DesktopResult.create_success(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    data={"cleared_count": count},
                    events=["notifications_cleared"],
                )

            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unsupported notification capability: {capability}",
                )

        except Exception as exc:
            logger.error(f"NotificationManager.{cap} failed: {exc}")
            return DesktopResult.create_failure(
                goal=goal,
                capability=capability,
                manager=self.name,
                error=f"Notification failed: {exc}",
            )
