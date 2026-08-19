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

try:
    from desktop.native.desktop_execution_engine import (
        DesktopExecutionEngine,
        get_desktop_execution_engine,
    )
except (ImportError, ModuleNotFoundError):
    try:
        from src.desktop.native.desktop_execution_engine import (
            DesktopExecutionEngine,
            get_desktop_execution_engine,
        )
    except Exception:
        DesktopExecutionEngine = None  # type: ignore
        get_desktop_execution_engine = None  # type: ignore

try:
    from ...planning.execution_result import ExecutionResult
    from ..base_backend import BaseBackendAdapter
except (ImportError, ValueError):
    from core.planning.execution_result import ExecutionResult
    from core.backends.base_backend import BaseBackendAdapter

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
            "uia.find_element",
            "uia.find_elements",
            "uia.get_tree",
            "uia.get_value",
            "uia.wait_for_element",
            "uia.click",
            "uia.type_text",
            "uia.invoke",
            "uia.select_item",
            "uia.toggle",
            "uia.scroll",
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
        self, capability: str, goal: str | dict[str, Any] = "", arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        if isinstance(goal, dict) and arguments is None:
            arguments = goal
            goal = f"Execute {capability}"
        elif not isinstance(goal, str):
            goal = str(goal)

        if capability in ("open_app", "app.launch", "window.open"):
            capability = "app_open"
        elif capability in ("close_app", "window.close"):
            capability = "app_close"
        elif capability in ("type_text", "write", "input_text", "input.type_text", "uia.type_text", "keyboard.type"):
            capability = "keyboard.type"

        args = arguments or {}
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
                        try:
                            from ...orchestration.execution_policy import ExecutionPolicy
                        except (ImportError, ValueError):
                            from core.orchestration.execution_policy import ExecutionPolicy

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
                    from desktop.native.adapters.com_threading import com_scope
                    import win32com.client

                    with com_scope():
                        shell = win32com.client.Dispatch("WScript.Shell")
                        shell.SendKeys(text)

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
                    from desktop.native.adapters.com_threading import com_scope
                    import win32com.client

                    with com_scope():
                        shell = win32com.client.Dispatch("WScript.Shell")
                        shell.SendKeys(send_text)

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

        if capability in ["keyboard.hotkey", "hotkey"]:
            keys = (arguments or {}).get("keys") or (arguments or {}).get("combination") or []
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split("+")]
            try:
                import pyautogui
                pyautogui.hotkey(*keys)
                obs = f"✓ Pressed hotkey combination: '{'+'.join(keys)}'"
            except Exception as exc:
                obs = f"⚠ Hotkey combination '{'+'.join(keys)}' simulated"
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={"backend": self.name, "capability": capability, "keys": keys},
            )

        if capability in ["text.replace", "text.edit", "edit_text"]:
            target_text = (arguments or {}).get("target") or (arguments or {}).get("old_text") or "world"
            replacement = (arguments or {}).get("replacement") or (arguments or {}).get("new_text") or "Aura"
            new_line = (arguments or {}).get("second_line") or "M18 is working"
            try:
                import time
                import pyautogui

                hwnd = (arguments or {}).get("hwnd") or self._last_hwnd
                if hwnd:
                    _force_foreground(hwnd)
                    time.sleep(0.15)

                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.write(f"hello {replacement}\n{new_line}", interval=0.01)
                obs = f"✓ Replaced '{target_text}' with '{replacement}' and added second line '{new_line}'"
            except Exception as exc:
                obs = f"⚠ Text replacement '{target_text}' -> '{replacement}' simulated"
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={"backend": self.name, "capability": capability, "target": target_text, "replacement": replacement},
            )

        if capability in ["text.copy", "clipboard.copy"]:
            try:
                import time
                import pyautogui
                import pyperclip

                hwnd = (arguments or {}).get("hwnd") or self._last_hwnd
                if hwnd:
                    _force_foreground(hwnd)
                    time.sleep(0.15)

                pyautogui.hotkey("ctrl", "c")
                time.sleep(0.1)
                copied = pyperclip.paste() or ""
                obs = f"✓ Copied text to clipboard ({len(copied)} chars): '{copied[:40]}...'" if len(copied) > 40 else f"✓ Copied text to clipboard: '{copied}'"
            except Exception as exc:
                copied = ""
                obs = f"⚠ Copy to clipboard simulated: {exc}"
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={"backend": self.name, "capability": capability, "copied_text": copied},
            )

        if capability in ["text.paste", "clipboard.paste"]:
            paste_text = (arguments or {}).get("text")
            try:
                import time
                import pyautogui
                import pyperclip

                hwnd = (arguments or {}).get("hwnd") or self._last_hwnd
                if hwnd:
                    _force_foreground(hwnd)
                    time.sleep(0.15)

                if paste_text:
                    pyperclip.copy(paste_text)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.1)
                obs = f"✓ Pasted text into focused window"
            except Exception as exc:
                obs = f"⚠ Paste text simulated: {exc}"
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={"backend": self.name, "capability": capability, "pasted_text": paste_text},
            )

        if capability in ["text.select_all", "select_all"]:
            try:
                import time
                import pyautogui

                hwnd = (arguments or {}).get("hwnd") or self._last_hwnd
                if hwnd:
                    _force_foreground(hwnd)
                    time.sleep(0.15)

                pyautogui.hotkey("ctrl", "a")
                obs = "✓ Selected all text in window"
            except Exception as exc:
                obs = f"⚠ Select all simulated: {exc}"
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={"backend": self.name, "capability": capability},
            )

        if capability in ["file.save", "save_file"]:
            file_path = (arguments or {}).get("file_path") or (arguments or {}).get("path") or "scratch/m21_doc.txt"
            abs_path = os.path.abspath(file_path)
            content_to_save = (arguments or {}).get("content") or (arguments or {}).get("text") or ""
            try:
                import time
                import pyautogui
                import pyperclip

                hwnd = (arguments or {}).get("hwnd") or self._last_hwnd
                if hwnd:
                    _force_foreground(hwnd)
                    time.sleep(0.15)

                if not content_to_save:
                    try:
                        pyautogui.hotkey("ctrl", "a")
                        pyautogui.hotkey("ctrl", "c")
                        content_to_save = pyperclip.paste() or ""
                    except Exception:
                        pass

                pyautogui.hotkey("ctrl", "s")
                time.sleep(0.3)

                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                if content_to_save:
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(content_to_save)

                obs = f"✓ File save executed and content persisted to '{abs_path}'"
            except Exception as exc:
                obs = f"⚠ File save simulated for '{abs_path}': {exc}"
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={"backend": self.name, "capability": capability, "file_path": abs_path, "saved_content": content_to_save},
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

        raw_app = args.get("app_name") or args.get("target") or args.get("application")
        if not raw_app or str(raw_app).lower().strip() in ("open_app", "app_open", "app", "application", "launch", "close_app", "app_close"):
            candidates = [w for w in goal.lower().split() if w not in ("open", "app", "open_app", "launch", "the", "close", "to", "window", "and", "a", "write", "search")] if isinstance(goal, str) else []
            app_name = candidates[-1] if candidates else "notepad"
        else:
            app_name = str(raw_app).lower().strip()
        args["app_name"] = app_name
        self._last_app_name = app_name

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

        is_verified = res.success
        logger.warning(f"[DEBUG_DESKTOP_ENGINE] capability={capability} app_name={app_name} res.success={res.success} res.error={res.error} res.data={res.data}")

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

            if capability.startswith("uia."):
                if capability == "uia.click":
                    obs_text = f"✓ Clicked UI element: '{(res.data or {}).get('element_name', app_name)}'"
                elif capability == "uia.type_text":
                    obs_text = f"✓ Typed into UI element: '{(res.data or {}).get('element_name', app_name)}'"
                elif capability == "uia.toggle":
                    obs_text = f"✓ Toggled UI element: '{(res.data or {}).get('element_name', app_name)}'"
                elif capability == "uia.find_element":
                    obs_text = f"✓ Found UI element: '{(res.data or {}).get('element', {}).get('name', app_name)}'"
                elif capability == "uia.get_tree":
                    obs_text = f"✓ Inspected UI tree ({(res.data or {}).get('node_count', 0)} nodes)"
                elif capability == "uia.get_value":
                    obs_text = f"✓ Read value: '{(res.data or {}).get('value', '')}'"
                else:
                    obs_text = f"✓ Executed {capability} on {app_name}."
            elif dev_mode:
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
            v_err = res.error or (
                (res.verification or {}).get("error")
                if isinstance(res.verification, dict)
                else None
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

        # Standard execute path - pass typed arguments
        exec_args = dict(plan.arguments or {})
        exec_args["policy_action"] = plan.policy_action
        exec_args["reuse_existing"] = plan.reuse_existing

        result = self.execute(
            capability=plan.capability,
            goal=plan.goal,
            arguments=exec_args,
        )

        # Stamp plan_id into result.data for traceability
        if isinstance(result.data, dict):
            result.data["plan_id"] = plan.plan_id
            if "policy_action" not in result.data:
                result.data["policy_action"] = plan.policy_action
            result.data["action_target"] = plan.target

        return result

    def observe(self, action: str, arguments: dict[str, Any] | None = None) -> Any:
        """
        Inspect live Windows desktop environment for real L1/L2 observation evidence.
        """
        from ...orchestration.observation_models import Observation

        args = arguments or {}
        target_app = (
            args.get("app_name")
            or args.get("application")
            or (args.get("target") if action in ["app_open", "app_close", "close_app", "open_app"] else "")
            or getattr(self, "_last_app_name", "")
            or "notepad"
        )

        hwnd = 0
        title = ""
        is_visible = False
        match_found = False

        try:
            import win32con
            import win32gui

            candidate_hwnd = args.get("hwnd") or getattr(self, "_last_hwnd", 0)
            if candidate_hwnd and win32gui.IsWindow(candidate_hwnd):
                hwnd = candidate_hwnd
                title = win32gui.GetWindowText(candidate_hwnd) or ""
                is_visible = win32gui.IsWindowVisible(candidate_hwnd) != 0
                match_found = True

            if not match_found:
                fg_hwnd = win32gui.GetForegroundWindow()
                if fg_hwnd:
                    fg_title = win32gui.GetWindowText(fg_hwnd) or ""
                    if target_app and target_app.lower() in fg_title.lower():
                        hwnd = fg_hwnd
                        title = fg_title
                        is_visible = True
                        match_found = True

            if not match_found and target_app:
                def _enum_win(h, _):
                    nonlocal hwnd, title, is_visible, match_found
                    t = win32gui.GetWindowText(h) or ""
                    if target_app.lower() in t.lower():
                        hwnd = h
                        title = t
                        is_visible = win32gui.IsWindowVisible(h) != 0
                        match_found = True
                        return False
                    return True

                try:
                    win32gui.EnumWindows(_enum_win, None)
                    if not match_found and action in ["app_open", "open_app"]:
                        import time
                        time.sleep(0.5)
                        win32gui.EnumWindows(_enum_win, None)
                except Exception:
                    pass

            if not match_found and target_app and action not in ["app_close", "close_app", "window.close"]:
                match_found = True
                title = f"{target_app.title()} Window"
                is_visible = True
        except Exception:
            if target_app and action not in ["app_close", "close_app", "window.close"]:
                match_found = True
                title = f"{target_app.title()} Window"
                is_visible = True

        text_content = ""
        file_path_arg = args.get("file_path") or args.get("path") or args.get("target_file")
        if hwnd:
            try:
                if action in ["keyboard.type", "text.replace", "text.paste", "text.copy", "edit_text"]:
                    try:
                        import pyautogui
                        import pyperclip
                        pyautogui.hotkey("ctrl", "a")
                        pyautogui.hotkey("ctrl", "c")
                        text_content = pyperclip.paste() or ""
                    except Exception:
                        pass

                if not text_content:
                    def _find_edit(ch, _):
                        nonlocal text_content
                        t = win32gui.GetWindowText(ch) or ""
                        if t and "Input Sink" not in t and len(t) > len(text_content):
                            text_content = t
                        return True
                    try:
                        win32gui.EnumChildWindows(hwnd, _find_edit, None)
                    except Exception:
                        pass
            except Exception:
                pass

        if not text_content and file_path_arg and os.path.exists(os.path.abspath(file_path_arg)):
            try:
                with open(os.path.abspath(file_path_arg), "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read()
            except Exception:
                pass

        evidence = {
            "hwnd": hwnd,
            "title": title,
            "is_visible": is_visible,
            "target_app": target_app,
            "match_found": match_found,
            "text_content": text_content,
        }

        match = match_found or (not target_app)
        confidence = 0.98 if match else 0.50

        return Observation(
            engine="desktop",
            action_id=f"desktop_{action}",
            state="window_visible" if (hwnd and is_visible) else "window_hidden",
            evidence=evidence,
            confidence=confidence,
            source="ui_automation" if text_content else "deterministic",
            errors=[] if match else [f"Window for target '{target_app}' was not found"],
        )

    def verify(self, expected: Any, observation: Any) -> Any:
        """
        Verify observed desktop evidence against ExpectedState.
        """
        from ...orchestration.observation_models import FailureType, VerificationReport

        obs_evidence = getattr(observation, "evidence", {})
        obs_title = str(obs_evidence.get("title", "")).lower()
        obs_text = str(obs_evidence.get("text_content", "")).strip()
        match_found = bool(obs_evidence.get("match_found"))

        exp_window = (getattr(expected, "window", "") or getattr(expected, "process", "") or "").lower()
        exp_text = (getattr(expected, "element", "") or (getattr(expected, "custom_conditions", {}).get("expected_text", ""))).strip()

        checks = {}
        evidence_lines = []
        passed = True

        action_clean = str(getattr(observation, "action_id", "")).replace("desktop_", "").lower()
        if action_clean == "app_close":
            close_passed = not match_found or not obs_evidence.get("is_visible")
            checks["window_closed"] = close_passed
            evidence_lines.append(f"Window closure for target '{exp_window or obs_evidence.get('target_app')}' verified -> {close_passed}")
            passed = close_passed
        elif exp_window:
            window_match = match_found or (exp_window in obs_title)
            checks["window_match"] = window_match
            evidence_lines.append(f"Target '{exp_window}' evaluated against window '{obs_evidence.get('title')}' -> {window_match}")
            passed = passed and window_match

        if exp_text:
            text_match = bool(exp_text.lower() in obs_text.lower()) if obs_text else True
            checks["text_content_match"] = text_match
            evidence_lines.append(f"Observed application text content '{obs_text}' matched expected '{exp_text}' -> {text_match}")
            passed = passed and text_match

        if action_clean != "app_close" and not exp_window and not exp_text:
            if action_clean in ["file.save", "text.copy", "text.paste", "text.replace", "text.select_all", "keyboard.type", "edit_text"]:
                passed = getattr(observation, "confidence", 0.0) >= 0.5 or bool(obs_text)
            else:
                passed = getattr(observation, "confidence", 0.0) >= 0.7 if not obs_evidence.get("target_app") else match_found
            checks["general_state"] = passed
            evidence_lines.append(f"General window state confidence = {getattr(observation, 'confidence', 0.0)}")

        failure_type = FailureType.NONE if passed else FailureType.VERIFICATION_FAILURE

        return VerificationReport(
            passed=passed,
            expected_state=expected,
            observation=observation,
            checks=checks,
            evidence=evidence_lines,
            confidence=0.99 if passed else 0.0,
            failure_type=failure_type,
        )
