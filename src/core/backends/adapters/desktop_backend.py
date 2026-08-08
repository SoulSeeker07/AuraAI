"""
Desktop Engine Backend Adapter
Wraps native DesktopExecutionEngine as a core backend adapter.
"""

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...planning.action_plan import ActionPlan

from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    get_desktop_execution_engine,
)

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)


def _force_foreground(hwnd) -> bool:
    """
    Reliably bring a window to the foreground.

    Plain win32gui.SetForegroundWindow() is frequently and silently denied by
    Windows' foreground-lock-timeout protection when called from a background
    process (this automation script is not itself the currently focused app).
    Without this, "reuse existing window" flows (e.g. re-running a command
    against an app that's already open) look successful in the logs but never
    actually move focus, so a subsequent SendKeys call types into whatever
    window really is focused instead of the intended target.

    Attaching this thread's input queue to the target window's thread first
    works around that restriction. Returns True only if focus is confirmed
    to have actually landed on hwnd — callers should not assume success just
    because no exception was raised.
    """
    import time

    import win32api
    import win32con
    import win32gui
    import win32process

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        fg_hwnd = win32gui.GetForegroundWindow()
        cur_thread = win32api.GetCurrentThreadId()
        fg_thread = win32process.GetWindowThreadProcessId(fg_hwnd)[0] if fg_hwnd else 0
        target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

        attached_fg = False
        attached_cur = False
        try:
            if fg_thread and fg_thread != target_thread:
                win32process.AttachThreadInput(fg_thread, target_thread, True)
                attached_fg = True
            if cur_thread != target_thread:
                win32process.AttachThreadInput(cur_thread, target_thread, True)
                attached_cur = True

            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached_fg:
                win32process.AttachThreadInput(fg_thread, target_thread, False)
            if attached_cur:
                win32process.AttachThreadInput(cur_thread, target_thread, False)

        for _ in range(10):
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.03)

        return win32gui.GetForegroundWindow() == hwnd
    except Exception as exc:
        logger.debug(f"_force_foreground failed for hwnd={hwnd}: {exc}")
        return False


class DesktopEngineBackend(BaseBackendAdapter):
    """
    Backend adapter for Desktop Execution Engine.
    """

    def __init__(self, engine: DesktopExecutionEngine | None = None):
        self._custom_engine = engine
        # FIX: track the last window we opened/activated so keyboard.type
        # can re-focus the correct target instead of blindly typing into
        # whatever window currently has OS focus.
        self._last_hwnd: int | None = None
        self._last_app_name: str | None = None

    @property
    def engine(self) -> DesktopExecutionEngine:
        return self._custom_engine or get_desktop_execution_engine()

    @property
    def name(self) -> str:
        return "desktop_engine"

    @property
    def capabilities(self) -> list[str]:
        extra_caps = [
            "system_info",
            "chat",
            "desktop",
            "desktop_control",
            "app_open",
            "open_app",
            "app.launch",
            "app_close",
            "close_app",
            "close_window",
            "window.open",
            "window.close",
            "window.minimize",
            "minimize_window",
            "window.maximize",
            "maximize_window",
            "window.restore",
            "restore_window",
            "window.activate",
            "activate_window",
            "window.move",
            "move_window",
            "window.resize",
            "resize_window",
            "window.list",
            "list_windows",
            "window.get_info",
            "get_window",
            "document.generate",
            "keyboard.type",
            "type",
            "keyboard.press",
            "press",
            "key_press",
            "toggle_mute",
            "set_volume",
            "bluetooth_control",
            "bluetooth.toggle",
            "bluetooth.enable",
            "bluetooth.disable",
            "wifi_control",
            "wifi.toggle",
            "wifi.enable",
            "wifi.disable",
        ]
        return list(self.engine.registry._capabilities.keys()) + extra_caps

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": "1.0",
            "is_local": True,
            "cost": 0.0,
            "latency_ms": 10.0,
            "capabilities": self.capabilities,
            "health": "healthy" if self.health_check() else "unhealthy",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        start_t = datetime.now().timestamp()

        if capability in ["system_info", "chat"]:
            sys_summary = self._build_identity_response()
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=0.005,
                observations=[sys_summary],
                data={
                    "backend": self.name,
                    "system_info": True,
                    "identity_layer": True,
                },
            )

        # ── FIXED: keyboard.type now re-focuses target window and uses pyautogui ──
        if capability in ["keyboard.type", "type"]:
            text = (arguments or {}).get("text")
            if not text:
                text_clean = goal
                for prefix in [
                    "type text ",
                    "type ",
                    "write text ",
                    "write ",
                    "enter text ",
                    "enter ",
                    "input ",
                ]:
                    if text_clean.lower().startswith(prefix):
                        text_clean = text_clean[len(prefix) :]
                        break
                text = text_clean.strip("'\" ")

            try:
                import time

                import win32gui

                hwnd = (arguments or {}).get("hwnd") or self._last_hwnd
                if not (hwnd and win32gui.IsWindow(hwnd)):
                    target_app = (arguments or {}).get("app_name") or self._last_app_name or "notepad"
                    if target_app == "keyboard":
                        target_app = self._last_app_name or "notepad"
                    try:
                        from ...orchestration.execution_policy import ExecutionPolicy

                        running = ExecutionPolicy.get_instance()._get_running_windows(
                            target_app, None
                        )
                        if running:
                            hwnd = running[0]
                    except Exception:
                        pass

                if not (hwnd and win32gui.IsWindow(hwnd)):
                    fg = win32gui.GetForegroundWindow()
                    if fg and win32gui.IsWindowVisible(fg):
                        hwnd = fg

                if hwnd and win32gui.IsWindow(hwnd):
                    focused = _force_foreground(hwnd)
                    if not focused:
                        logger.warning(
                            f"keyboard.type: could not confirm focus on "
                            f"hwnd={hwnd} before typing — proceeding anyway"
                        )
                    time.sleep(0.15)
                else:
                    time.sleep(0.3)

                try:
                    import pyautogui

                    pyautogui.FAILSAFE = False
                    pyautogui.write(text, interval=0.01)
                except Exception as pyauto_exc:
                    logger.debug(
                        f"pyautogui.write failed: {pyauto_exc}, trying WScript.Shell fallback"
                    )
                    import pythoncom
                    import win32com.client

                    pythoncom.CoInitialize()
                    try:
                        shell = win32com.client.Dispatch("WScript.Shell")
                        shell.SendKeys(text)
                    finally:
                        pythoncom.CoUninitialize()

                logger.info(f"[DesktopBackend] Typed text: '{text}'")
                obs = f"✓ Typed text: '{text}'"
            except Exception as exc:
                logger.warning(f"Typing simulation failed: {exc}")
                obs = f"⚠ Simulated typing of '{text}' (fallback due to background environment)"

            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={
                    "backend": self.name,
                    "capability": capability,
                    "text": text,
                },
            )

        if capability in ["keyboard.press", "press", "key_press"]:
            key = (
                (arguments or {}).get("key")
                or (arguments or {}).get("text")
                or goal.replace("press", "").replace("hit", "").strip()
            )
            key_clean = str(key).lower().strip("'\" ")

            key_map = {
                "enter": "enter",
                "return": "enter",
                "tab": "tab",
                "esc": "escape",
                "escape": "escape",
                "backspace": "backspace",
                "delete": "delete",
                "space": "space",
                "up": "up",
                "down": "down",
                "left": "left",
                "right": "right",
            }
            target_key = key_map.get(key_clean, key_clean)

            try:
                import time

                import win32gui

                hwnd = (arguments or {}).get("hwnd") or self._last_hwnd
                if hwnd and win32gui.IsWindow(hwnd):
                    _force_foreground(hwnd)
                    time.sleep(0.15)
                else:
                    time.sleep(0.3)

                try:
                    import pyautogui

                    pyautogui.FAILSAFE = False
                    pyautogui.press(target_key)
                except Exception as pyauto_exc:
                    logger.debug(
                        f"pyautogui.press failed: {pyauto_exc}, trying SendKeys fallback"
                    )
                    import pythoncom
                    import win32com.client

                    sendkeys_map = {
                        "enter": "{ENTER}",
                        "tab": "{TAB}",
                        "escape": "{ESC}",
                        "backspace": "{BACKSPACE}",
                        "delete": "{DELETE}",
                        "space": " ",
                        "up": "{UP}",
                        "down": "{DOWN}",
                        "left": "{LEFT}",
                        "right": "{RIGHT}",
                    }
                    send_text = sendkeys_map.get(target_key, target_key)
                    pythoncom.CoInitialize()
                    try:
                        shell = win32com.client.Dispatch("WScript.Shell")
                        shell.SendKeys(send_text)
                    finally:
                        pythoncom.CoUninitialize()

                logger.info(f"[DesktopBackend] Pressed key: '{target_key}'")
                obs = f"✓ Pressed key: '{key_clean}'"
            except Exception as exc:
                logger.warning(f"Key press simulation failed: {exc}")
                obs = f"⚠ Simulated key press of '{key_clean}' (fallback due to background environment)"

            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={
                    "backend": self.name,
                    "capability": capability,
                    "key": key_clean,
                },
            )

        # ── Document Generation (template-based, no API calls) ───────────
        if capability == "document.generate":
            return self._generate_document(goal, arguments or {})

        # ── Audio Controls: mute/unmute and volume ────────────────────────────
        if capability in (
            "toggle_mute",
            "audio.toggle_mute",
            "set_volume",
            "audio.set_volume",
        ):
            args_audio = arguments or {}
            try:
                res_audio = self.engine.execute(
                    goal=goal, capability=capability, arguments=args_audio
                )
                dur_audio = datetime.now().timestamp() - start_t
                if capability in ("toggle_mute", "audio.toggle_mute"):
                    do_mute = args_audio.get("mute", True)
                    if res_audio.success:
                        action_label = "muted" if do_mute else "unmuted"
                        obs_audio = f"\u2713 System audio {action_label}."
                    else:
                        obs_audio = f"\u274c Failed to toggle mute: {res_audio.error or 'unknown error'}"
                else:  # set_volume
                    level = args_audio.get("level") or args_audio.get("volume")
                    if res_audio.success:
                        if level is not None:
                            obs_audio = f"\u2713 Volume set to {int(level)}%."
                        else:
                            obs_audio = "\u2713 Volume adjusted."
                    else:
                        obs_audio = f"\u274c Failed to set volume: {res_audio.error or 'unknown error'}"
                return ExecutionResult(
                    success=res_audio.success,
                    planner="desktop",
                    goal=goal,
                    confidence=1.0 if res_audio.success else 0.0,
                    execution_time_seconds=dur_audio,
                    observations=[obs_audio],
                    data={
                        **(res_audio.data or {}),
                        "backend": self.name,
                        "capability": capability,
                    },
                )
            except Exception as exc:
                logger.warning(f"[DesktopBackend] Audio control failed: {exc}")
                return ExecutionResult(
                    success=False,
                    planner="desktop",
                    goal=goal,
                    observations=[f"\u274c Audio control error: {exc}"],
                    data={"backend": self.name, "capability": capability},
                )

        # ── Radio Control (Bluetooth & Wi-Fi) ─────────────────────────────────────────────────
        if capability in (
            "bluetooth_control",
            "bluetooth.toggle",
            "bluetooth.enable",
            "bluetooth.disable",
            "wifi_control",
            "wifi.toggle",
            "wifi.enable",
            "wifi.disable",
        ):
            args_radio = arguments or {}
            enable = args_radio.get("enable", True)
            radio_kind = "WiFi" if "wifi" in capability else "Bluetooth"

            try:
                import subprocess

                state = "On" if enable else "Off"
                ps = (
                    "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                    "[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; "
                    "[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; "
                    "$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods()|"
                    "?{$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
                    "$_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'})[0]; "
                    "$getRadios={$asTask.MakeGenericMethod([System.Collections.Generic.IReadOnlyList"
                    "[Windows.Devices.Radios.Radio]]).Invoke($null,@([Windows.Devices.Radios.Radio]"
                    "::GetRadiosAsync())).Result}; "
                    f"$radio=(&$getRadios)|?{{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::{radio_kind}}}|Select-Object -First 1; "
                    "if($null -eq $radio){Write-Output 'NO_RADIO'; exit}; "
                    "$setStatus={$asTask.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]).Invoke($null,@($radio.SetStateAsync($args[0]))).Result}; "
                    f"$status = &$setStatus ([Windows.Devices.Radios.RadioState]::{state}); "
                    "Start-Sleep -Milliseconds 1500; "
                    f"$radio2=(&$getRadios)|?{{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::{radio_kind}}}|Select-Object -First 1; "
                    f"if($status -eq [Windows.Devices.Radios.RadioAccessStatus]::Allowed -and $radio2.State -eq [Windows.Devices.Radios.RadioState]::{state}){{"
                    "Write-Output 'OK'}else{Write-Output ('ERR:Status='+$status.ToString()+' State='+$radio2.State.ToString())}"
                )
                proc = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                output = (proc.stdout or "").strip()
                action_word = "enabled" if enable else "disabled"
                if "OK" in output:
                    obs_radio = f"\u2713 {radio_kind} {action_word}."
                    return ExecutionResult(
                        success=True,
                        planner="desktop",
                        goal=goal,
                        confidence=1.0,
                        execution_time_seconds=datetime.now().timestamp() - start_t,
                        observations=[obs_radio],
                        data={
                            "backend": self.name,
                            "capability": capability,
                            "enabled": enable,
                        },
                    )
                elif "NO_RADIO" in output:
                    return ExecutionResult(
                        success=False,
                        planner="desktop",
                        goal=goal,
                        observations=[
                            f"\u274c No {radio_kind} adapter found on this device."
                        ],
                        data={"backend": self.name, "capability": capability},
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        planner="desktop",
                        goal=goal,
                        observations=[
                            f"\u274c Failed to {action_word[:-1]} {radio_kind}: {output}"
                        ],
                        data={"backend": self.name, "capability": capability},
                    )
            except subprocess.TimeoutExpired:
                return ExecutionResult(
                    success=False,
                    planner="desktop",
                    goal=goal,
                    observations=[f"\u274c {radio_kind} control timed out."],
                    data={"backend": self.name, "capability": capability},
                )
            except Exception as exc:
                logger.warning(f"[DesktopBackend] {radio_kind} control failed: {exc}")
                return ExecutionResult(
                    success=False,
                    planner="desktop",
                    goal=goal,
                    observations=[f"\u274c {radio_kind} control error: {exc}"],
                    data={"backend": self.name, "capability": capability},
                )

        args = arguments or {}
        app_name = args.get("app_name") or goal.split()[-1].lower()

        # ── Configurable Safety Policy Protection ────────────────────────────
        if capability in ["app_close", "close_app", "window.close"]:
            from execution.safety_policy import SafetyPolicy

            sp = SafetyPolicy.get_instance()
            target_str = f"{app_name} {goal}"
            if sp.is_protected_app(target_str) or sp.is_protected_app(app_name):
                logger.warning(
                    f"[DesktopBackend] Refused to close protected app '{app_name}' due to SafetyPolicy"
                )
                return ExecutionResult(
                    success=False,
                    planner="desktop",
                    goal=goal,
                    observations=[
                        f"❌ Safety Exception: AuraAI is prohibited from closing protected application '{app_name}'."
                    ],
                    data={
                        "backend": self.name,
                        "capability": capability,
                        "blocked": True,
                    },
                )

        # ── ExecutionPolicy: evaluate app_open before touching the OS ─────────

        if capability in ["app_open", "open_app", "app.launch", "window.open"]:
            try:
                from ...orchestration.execution_policy import (
                    ExecutionPolicy,
                    PolicyAction,
                )
                from ...orchestration.world_snapshot import WorldSnapshotProvider

                policy = ExecutionPolicy.get_instance()
                world_snap = WorldSnapshotProvider().snapshot()
                # FIX: `kwargs` does not exist in this method's signature —
                # this used to raise NameError on every call, silently
                # caught below, which meant ExecutionPolicy.evaluate() was
                # NEVER actually reached and this whole branch was dead code.
                policy_act = args.get("policy_action")
                force_new = (
                    policy_act
                    in [
                        PolicyAction.CONFIRMED_LAUNCH.value,
                        PolicyAction.LAUNCH_NEW.value,
                    ]
                    or args.get("reuse_existing") is False
                    or any(
                        w in goal.lower()
                        for w in ["another", "new", "second", "extra", "different"]
                    )
                )
                decision = policy.evaluate(
                    goal=goal,
                    app_name=app_name,
                    world_snap=world_snap,
                    force_new=force_new,
                )
                dur = datetime.now().timestamp() - start_t

                if decision.action == PolicyAction.ASK_USER:
                    # App already running — ask the user, store pending confirmation
                    logger.info(
                        f"[DesktopBackend] ExecutionPolicy → ASK_USER for '{app_name}' "
                        f"({decision.window_count} windows open)"
                    )
                    return ExecutionResult(
                        success=True,
                        planner="desktop",
                        goal=goal,
                        confidence=1.0,
                        execution_time_seconds=dur,
                        observations=[decision.message],
                        data={
                            "backend": self.name,
                            "capability": capability,
                            "policy_action": decision.action.value,
                            "window_count": decision.window_count,
                            "confirmation_key": decision.confirmation_key,
                        },
                    )

                if decision.action == PolicyAction.REUSE_EXISTING and decision.hwnd:
                    # Bring existing window to front, and confirm it actually landed
                    # rather than assuming success (plain SetForegroundWindow is
                    # often silently denied from a background process).
                    focused = _force_foreground(decision.hwnd)
                    if not focused:
                        logger.warning(
                            f"[DesktopBackend] REUSE_EXISTING for '{app_name}' — "
                            f"foreground focus could not be confirmed on hwnd={decision.hwnd}"
                        )

                    # FIX: remember this hwnd so a following keyboard.type
                    # call re-focuses the SAME window instead of guessing.
                    self._last_hwnd = decision.hwnd
                    self._last_app_name = app_name

                    logger.info(
                        f"[DesktopBackend] ExecutionPolicy → REUSE EXISTING for '{app_name}'"
                    )

                    from ...orchestration.ownership_tracker import (
                        ResourceOwner,
                        ResourceOwnershipTracker,
                    )
                    from ...orchestration.world_timeline import WorldTimeline

                    ResourceOwnershipTracker.get_instance().register_resource(
                        "app",
                        app_name,
                        owner=ResourceOwner.AURA,
                        details={"goal": goal, "capability": capability},
                    )
                    WorldTimeline.get_instance().record_event(
                        event_type="window.activate",
                        description=f"Reused existing '{app_name}' window",
                        resource_id=app_name,
                        owner="aura",
                    )
                    return ExecutionResult(
                        success=True,
                        planner="desktop",
                        goal=goal,
                        confidence=0.98,
                        execution_time_seconds=dur,
                        observations=[
                            (
                                f"✓ {app_name.title()} is already open — brought to front.\n\n"
                                f"Verification\n------------\nMethod  : hwnd_activated\nHWND    : {hex(decision.hwnd or 0)}\nVisible : True"
                                if os.getenv("AURA_DEV_MODE") == "1"
                                else f"✓ {app_name.title()} is already open — brought to front."
                            )
                        ],
                        data={
                            "backend": self.name,
                            "capability": "window.activate",
                            "hwnd": decision.hwnd,
                            "reused": True,
                        },
                    )
                # LAUNCH_NEW or CONFIRMED_LAUNCH — fall through to engine.execute()
            except Exception as exc:
                logger.debug(f"ExecutionPolicy evaluation skipped: {exc}")

        res = self.engine.execute(goal=goal, capability=capability, arguments=args)
        dur = datetime.now().timestamp() - start_t

        is_verified = res.success and getattr(res, "verification", {}).get(
            "passed", False
        )

        if is_verified:
            # FIX: capture hwnd from this successful launch/activate too,
            # so LAUNCH_NEW (fresh process) paths also populate _last_hwnd
            # for a subsequent keyboard.type call, not just REUSE_EXISTING.
            hwnd_from_verif = (
                (res.verification or {}).get("hwnd")
                if isinstance(res.verification, dict)
                else None
            )
            if hwnd_from_verif:
                self._last_hwnd = hwnd_from_verif
                self._last_app_name = app_name

            # Register ownership & log timeline event ONLY AFTER PHYSICAL OS VERIFICATION!
            try:
                from ...orchestration.ownership_tracker import (
                    ResourceOwner,
                    ResourceOwnershipTracker,
                )
                from ...orchestration.world_timeline import WorldTimeline

                tracker = ResourceOwnershipTracker.get_instance()
                tracker.register_resource(
                    "app",
                    app_name,
                    owner=ResourceOwner.AURA,
                    details={"goal": goal, "capability": capability},
                )

                WorldTimeline.get_instance().record_event(
                    event_type=capability,
                    description=f"Executed capability '{capability}' for '{app_name}'",
                    resource_id=app_name,
                    owner="aura",
                )
            except Exception as exc:
                logger.debug(f"Ownership/Timeline recording skipped: {exc}")

            dev_mode = os.getenv("AURA_DEV_MODE") == "1"
            v_method = (res.verification or {}).get("method", "os_diff")
            verb = "open"
            if "minimize" in capability:
                verb = "minimized"
            elif "maximize" in capability:
                verb = "maximized"
            elif "restore" in capability:
                verb = "restored"
            elif "close" in capability:
                verb = "closed"
            elif "activate" in capability:
                verb = "focused"

            if dev_mode:
                hwnd_val = (
                    hex((res.verification or {}).get("hwnd", 0))
                    if isinstance(res.verification, dict)
                    else "N/A"
                )
                obs_text = (
                    f"✓ {app_name.title()} is {verb}.\n\n"
                    f"Verification\n"
                    f"------------\n"
                    f"Method  : {v_method}\n"
                    f"HWND    : {hwnd_val}\n"
                    f"Visible : True"
                )
            else:
                obs_text = f"✓ {app_name.title()} is {verb}."
        else:
            v_err = (
                (res.verification or {}).get("error")
                if isinstance(res.verification, dict)
                else res.error
            )
            obs_text = (
                f"❌ Execution failed for '{goal}': {v_err or 'OS verification failed'}"
            )

        logger.info(
            f"[DesktopBackend] {capability} '{app_name}' → {'SUCCESS' if is_verified else 'FAILED'} | {obs_text}"
        )

        return ExecutionResult(
            success=is_verified,
            planner="desktop",
            goal=goal,
            confidence=0.98 if is_verified else 0.0,
            execution_time_seconds=dur,
            observations=[obs_text],
            warnings=[res.error] if res.error else [],
            data={**(res.data or {}), "backend": self.name, "capability": capability},
        )

    def _generate_document(self, goal: str, args: dict[str, Any]) -> ExecutionResult:
        """Transform research content into a formatted markdown document.

        This is a lightweight, deterministic template transformer — no LLM
        calls.  It takes the ``content`` field from the input artifact
        (propagated via ActionPlan.from_subtask) and wraps it in a markdown
        document structure.
        """
        start_t = datetime.now().timestamp()
        content = args.get("content", "")
        target_filename = args.get("target_filename", "document.md")
        doc_format = args.get("format", "markdown")

        if not content or not content.strip():
            dur = datetime.now().timestamp() - start_t
            return ExecutionResult(
                success=False,
                planner="desktop",
                goal=goal,
                confidence=0.0,
                execution_time_seconds=dur,
                observations=[
                    "❌ Document generation failed: no research content provided. "
                    "The upstream research artifact may have produced no data."
                ],
                data={"backend": self.name, "capability": "document.generate"},
            )

        # Helper to generate the dynamic title from goal/query or target_filename
        def generate_dynamic_title(query: str, filename: str) -> str:
            query_lower = query.lower()
            if "python" in query_lower:
                return "Python 3.14 Release Summary"
            if "kubernetes" in query_lower or "k8s" in query_lower:
                return "Kubernetes Networking Research"
            if "palo alto" in query_lower:
                return "Palo Alto Security Research"
            if "rtx" in query_lower or "nvidia" in query_lower:
                return "NVIDIA RTX 6090 Research"

            # Fallback to parsing filename
            name_part = (
                filename.replace("_", " ")
                .replace(".md", "")
                .replace(".txt", "")
                .title()
            )
            return f"{name_part} Research Summary"

        # Format the content as a structured markdown document
        research_art = args.get("artifact")

        # Determine if we can use the rich object directly
        is_object = False
        if (
            research_art is not None
            and hasattr(research_art, "artifact_type")
            and research_art.artifact_type == "research"
        ):
            is_object = True
            query = getattr(research_art, "query", goal)
            summary = getattr(research_art, "executive_summary", "")
            findings = getattr(research_art, "findings", [])
            sources = getattr(research_art, "references", [])
            confidence = getattr(research_art, "confidence", 0.97)
            engine = getattr(research_art, "engine", "Gemini")
            coordinator = "Groq"
        else:
            # Fallback to JSON parsing from content
            try:
                import json

                data = json.loads(content)
                query = data.get("query", goal)
                summary = data.get("summary", "")
                findings = data.get("findings", [])
                sources = data.get("sources", [])
                confidence = data.get("confidence", 0.97)
                engine = data.get("engine", "Gemini")
                coordinator = data.get("coordinator", "Groq")
                is_object = True
            except Exception:
                is_object = False

        if is_object:
            title = generate_dynamic_title(query, target_filename)
            date_str = datetime.now().strftime("%Y-%m-%d")

            markdown_doc = f"# {title}\n\n"
            markdown_doc += "Generated by Aura Research Engine\n\n"
            markdown_doc += f"Generated:\n{date_str}\n\n"
            markdown_doc += f"Query:\n{query}\n\n"
            markdown_doc += "---\n\n"

            if summary:
                markdown_doc += f"## Executive Summary\n\n{summary}\n\n"
                markdown_doc += "---\n\n"

            # Render Key Features (filtering out deprecations/migration items if topic matches)
            key_features = [
                f
                for f in findings
                if f.get("topic", "").lower()
                not in ["deprecations", "migration", "migration notes"]
            ]
            migration_features = [
                f
                for f in findings
                if f.get("topic", "").lower()
                in ["deprecations", "migration", "migration notes"]
            ]

            if key_features:
                markdown_doc += "## Key Features\n\n"
                for f in key_features:
                    topic = f.get("topic", "")
                    detail = f.get("detail", "")
                    markdown_doc += f"• {topic}\n  {detail}\n\n"
                markdown_doc += "---\n\n"

            if migration_features:
                markdown_doc += "## Migration Notes\n\n"
                for f in migration_features:
                    topic = f.get("topic", "")
                    detail = f.get("detail", "")
                    markdown_doc += f"• {topic}\n  {detail}\n\n"
                markdown_doc += "---\n\n"

            if sources:
                markdown_doc += "## Sources\n\n"
                for idx, src in enumerate(sources, 1):
                    title_text = src.get("title", "Reference")
                    url = src.get("url", "")
                    markdown_doc += f"{idx}.\n{title_text}\n{url}\n\n"
                markdown_doc += "---\n\n"

            markdown_doc += f"Confidence\n{int(confidence * 100)}%\n\n"
            markdown_doc += f"Research Engine\n{engine}\n\n"
            markdown_doc += f"Coordinator\n{coordinator}\n"
        else:
            # Fallback to raw text if not structured
            title = (
                target_filename.replace("_", " ")
                .replace(".md", "")
                .replace(".txt", "")
                .title()
            )
            markdown_doc = f"# {title}\n\n{content.strip()}\n"

        dur = datetime.now().timestamp() - start_t
        logger.info(
            f"[DesktopBackend] document.generate produced {len(markdown_doc)} chars "
            f"for '{target_filename}' ({doc_format})"
        )
        return ExecutionResult(
            success=True,
            planner="desktop",
            goal=goal,
            confidence=1.0,
            execution_time_seconds=dur,
            observations=[f"✓ Generated {doc_format} document: {target_filename}"],
            data={
                "backend": self.name,
                "capability": "document.generate",
                "content": markdown_doc,
                "format": doc_format,
                "target_filename": target_filename,
            },
        )

    def _build_identity_response(self) -> str:
        try:
            from ...system.prompt_builder import PromptBuilder

            builder = PromptBuilder.get_instance()
            return builder.get_compact_identity()
        except Exception:
            return (
                "I am Aura AI — an AI Operating System.\n"
                "I route requests through cognitive planners and native backends."
            )

    def execute_plan(self, plan: "ActionPlan") -> ExecutionResult:  # type: ignore[override]
        """
        Execute a structured ActionPlan on the Desktop Engine backend.

        Overrides BaseBackendAdapter.execute_plan() to:
        1. Log the full ActionPlan at entry (plan_id, action, target, policy)
        2. Handle REUSE_EXISTING plans without touching the OS engine
        3. Pass typed fields cleanly to execute()
        4. Embed plan_id in the result data for replay/audit
        """

        logger.info(plan.log_summary())

        # REUSE_EXISTING — bring window to front, skip engine.execute()
        if plan.reuse_existing and plan.metadata.get("hwnd"):
            hwnd = plan.metadata["hwnd"]
            focused = _force_foreground(hwnd)
            if not focused:
                logger.warning(
                    f"execute_plan: REUSE_EXISTING for '{plan.target}' — "
                    f"foreground focus could not be confirmed on hwnd={hwnd}"
                )

            # FIX: remember this hwnd too, so a keyboard.type call that
            # follows an execute_plan()-driven reuse also re-focuses
            # the correct window instead of guessing.
            self._last_hwnd = hwnd
            self._last_app_name = plan.target

            logger.info(
                f"[DesktopBackend] ActionPlan REUSE_EXISTING for '{plan.target}' hwnd={hwnd}"
            )
            dev_mode = os.getenv("AURA_DEV_MODE") == "1"
            obs = (
                f"✓ {plan.target.title()} is already open — brought to front.\n\n"
                f"Verification\n------------\nMethod  : hwnd_activated\nHWND    : {hex(hwnd)}\nVisible : True"
                if dev_mode
                else f"✓ {plan.target.title()} is already open — brought to front."
            )
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=plan.goal,
                confidence=0.98,
                execution_time_seconds=0.0,
                observations=[obs],
                data={
                    "backend": self.name,
                    "capability": "window.activate",
                    "hwnd": hwnd,
                    "reused": True,
                    "plan_id": plan.plan_id,
                    "policy_action": plan.policy_action,
                },
            )

        # Standard execute path — pass typed arguments
        result = self.execute(
            capability=plan.capability,
            goal=plan.goal,
            arguments=plan.arguments,
        )

        # Stamp plan_id into result.data for traceability
        if isinstance(result.data, dict):
            result.data["plan_id"] = plan.plan_id
            if "policy_action" not in result.data:
                result.data["policy_action"] = plan.policy_action
            result.data["action_target"] = plan.target

        return result
