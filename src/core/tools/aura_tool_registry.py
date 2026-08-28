"""
Aura Tool Registry
==================
Defines OpenAI/Groq-compatible JSON schemas for Aura's native capabilities
and provides an autonomous execution dispatcher for LLM tool calling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import webbrowser
from typing import Any

logger = logging.getLogger(__name__)


class AuraToolRegistry:
    """
    Registry for all tools callable by Aura's LLM reasoning engine.
    Formats tool definitions according to standard OpenAI/Groq Function Calling JSON schema.
    """

    @classmethod
    def get_tool_definitions(cls) -> list[dict[str, Any]]:
        """
        Return the list of OpenAI/Groq function calling tool definitions.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "desktop_launch_app",
                    "description": "Launch a Windows application (e.g., 'notepad', 'spotify', 'chrome', 'calc', 'vscode', 'msedge', or any app name).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "application": {
                                "type": "string",
                                "description": "The name or command of the application to launch (e.g. 'spotify', 'notepad', 'calc', 'chrome').",
                            }
                        },
                        "required": ["application"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_control_window",
                    "description": "Control an application window (focus, minimize, maximize, restore, or close).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "window_title": {
                                "type": "string",
                                "description": "Window title or application name to target.",
                            },
                            "action": {
                                "type": "string",
                                "enum": ["focus", "minimize", "maximize", "restore", "close"],
                                "description": "The action to perform on the window.",
                            },
                        },
                        "required": ["window_title", "action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_set_volume",
                    "description": "Adjust Windows system audio volume (0 to 100) or toggle mute.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "integer",
                                "description": "Volume percentage between 0 and 100.",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "mute": {
                                "type": "boolean",
                                "description": "True to mute, False to unmute (optional).",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_set_brightness",
                    "description": "Set primary display screen brightness level from 0 to 100.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "integer",
                                "description": "Brightness percentage from 0 to 100.",
                                "minimum": 0,
                                "maximum": 100,
                            }
                        },
                        "required": ["level"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_clipboard",
                    "description": "Read from or write to the Windows clipboard.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["read", "write"],
                                "description": "Whether to read or write to the clipboard.",
                            },
                            "text": {
                                "type": "string",
                                "description": "Text to write to the clipboard (required when action is 'write').",
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vision_inspect_screen",
                    "description": "Capture the current screen and perform OCR to inspect visible text, active window content, and open applications.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Optional specific question or element to look for on screen.",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "system_get_telemetry",
                    "description": "Get real-time hardware telemetry: CPU usage, RAM usage, Battery level/charging status, and active OS metrics.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_save_fact",
                    "description": "Save a user profile fact, preference, project note, or skill to Aura's persistent SQLite memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["profile", "preference", "skill", "project", "goal", "important"],
                                "description": "Category for the memory fact.",
                            },
                            "key": {
                                "type": "string",
                                "description": "The fact identifier key (e.g., 'favorite_language', 'project_status', 'theme').",
                            },
                            "value": {
                                "type": "string",
                                "description": "The information to remember.",
                            },
                        },
                        "required": ["category", "key", "value"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_query_facts",
                    "description": "Query Aura's persistent memory to recall user preferences, profile details, or saved facts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Optional category filter (e.g. 'preference', 'profile').",
                            },
                            "key": {
                                "type": "string",
                                "description": "Optional specific key name.",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_open_url",
                    "description": "Open a website or URL in the default web browser.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The full URL to open (e.g., 'https://github.com').",
                            }
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "personal_os_get_daily_agenda",
                    "description": "Get today's agenda, prioritized tasks, deadlines, and schedule from Personal OS.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Optional date string in YYYY-MM-DD format (defaults to today).",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "personal_os_add_task",
                    "description": "Add a new task or todo item to Personal OS.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Task title or description.",
                            },
                            "due_date": {
                                "type": "string",
                                "description": "Optional due date (YYYY-MM-DD).",
                            },
                            "priority": {
                                "type": "integer",
                                "description": "Priority 1 (high), 2 (medium), 3 (low). Default is 2.",
                            },
                        },
                        "required": ["title"],
                    },
                },
            },
        ]

    @classmethod
    async def execute_tool(
        cls, name: str, arguments: dict[str, Any], aura_core: Any = None
    ) -> dict[str, Any]:
        """
        Execute the tool by name with provided arguments.
        """
        logger.info(f"[AuraToolRegistry] Executing tool '{name}' with args: {arguments}")

        try:
            if name == "desktop_launch_app":
                app = arguments.get("application", "").strip()
                return await asyncio.to_thread(cls._launch_app, app)

            elif name == "desktop_control_window":
                title = arguments.get("window_title", "")
                action = arguments.get("action", "focus")
                return await asyncio.to_thread(cls._control_window, title, action)

            elif name == "desktop_set_volume":
                level = arguments.get("level")
                mute = arguments.get("mute")
                return await asyncio.to_thread(cls._set_volume, level, mute)

            elif name == "desktop_set_brightness":
                level = int(arguments.get("level", 50))
                return await asyncio.to_thread(cls._set_brightness, level)

            elif name == "desktop_clipboard":
                action = arguments.get("action", "read")
                text = arguments.get("text", "")
                return await asyncio.to_thread(cls._handle_clipboard, action, text)

            elif name == "vision_inspect_screen":
                query = arguments.get("query", "")
                return await asyncio.to_thread(cls._inspect_screen, query)

            elif name == "system_get_telemetry":
                return await asyncio.to_thread(cls._get_system_telemetry)

            elif name == "memory_save_fact":
                category = arguments.get("category", "important")
                key = arguments.get("key", "note")
                val = arguments.get("value", "")
                return await asyncio.to_thread(cls._save_memory_fact, category, key, val, aura_core)

            elif name == "memory_query_facts":
                category = arguments.get("category")
                key = arguments.get("key")
                return await asyncio.to_thread(cls._query_memory_facts, category, key, aura_core)

            elif name == "browser_open_url":
                url = arguments.get("url", "")
                return await asyncio.to_thread(cls._open_url, url)

            elif name == "personal_os_get_daily_agenda":
                target_date = arguments.get("date")
                return await asyncio.to_thread(cls._get_daily_agenda, target_date, aura_core)

            elif name == "personal_os_add_task":
                title = arguments.get("title", "")
                due_date = arguments.get("due_date")
                priority = int(arguments.get("priority", 2))
                return await asyncio.to_thread(cls._add_personal_task, title, due_date, priority, aura_core)

            else:
                return {"status": "error", "error": f"Unknown tool: {name}"}

        except Exception as e:
            logger.error(f"[AuraToolRegistry] Tool execution failed for {name}: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    # ── Tool Implementations ──────────────────────────────────────────────

    @staticmethod
    def _launch_app(application: str) -> dict[str, Any]:
        app_clean = application.lower().strip()
        common_apps = {
            "spotify": "spotify:",
            "calculator": "calc",
            "calc": "calc",
            "notepad": "notepad",
            "paint": "mspaint",
            "mspaint": "mspaint",
            "vscode": "code",
            "vs code": "code",
            "visual studio code": "code",
            "chrome": "chrome",
            "edge": "msedge",
            "msedge": "msedge",
            "file explorer": "explorer",
            "explorer": "explorer",
            "task manager": "taskmgr",
            "cmd": "cmd",
            "terminal": "wt",
        }

        target = common_apps.get(app_clean, application)
        try:
            if target.endswith(":"):
                os.startfile(target)
            else:
                subprocess.Popen(target, shell=True)
            return {"status": "success", "message": f"Launched '{application}' successfully."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to launch '{application}': {e}"}

    @staticmethod
    def _control_window(window_title: str, action: str) -> dict[str, Any]:
        try:
            import win32gui
            import win32con

            matched_hwnd = None
            found_title = ""

            def enum_cb(hwnd, _):
                nonlocal matched_hwnd, found_title
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if window_title.lower() in t.lower() and t.strip():
                        matched_hwnd = hwnd
                        found_title = t

            win32gui.EnumWindows(enum_cb, None)

            if not matched_hwnd:
                return {"status": "error", "message": f"No active window found matching '{window_title}'."}

            if action == "focus":
                win32gui.ShowWindow(matched_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(matched_hwnd)
                return {"status": "success", "message": f"Brought window '{found_title}' to the foreground."}
            elif action == "minimize":
                win32gui.ShowWindow(matched_hwnd, win32con.SW_MINIMIZE)
                return {"status": "success", "message": f"Minimized window '{found_title}'."}
            elif action == "maximize":
                win32gui.ShowWindow(matched_hwnd, win32con.SW_MAXIMIZE)
                return {"status": "success", "message": f"Maximized window '{found_title}'."}
            elif action == "restore":
                win32gui.ShowWindow(matched_hwnd, win32con.SW_RESTORE)
                return {"status": "success", "message": f"Restored window '{found_title}'."}
            elif action == "close":
                win32gui.PostMessage(matched_hwnd, win32con.WM_CLOSE, 0, 0)
                return {"status": "success", "message": f"Closed window '{found_title}'."}
            else:
                return {"status": "error", "message": f"Unknown window action: {action}"}
        except Exception as e:
            return {"status": "error", "message": f"Window control failed: {e}"}

    @staticmethod
    def _set_volume(level: int | None, mute: bool | None) -> dict[str, Any]:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            msg_parts = []
            if mute is not None:
                volume.SetMute(1 if mute else 0, None)
                msg_parts.append("muted" if mute else "unmuted")

            if level is not None:
                scalar = max(0.0, min(1.0, float(level) / 100.0))
                volume.SetMasterVolumeLevelScalar(scalar, None)
                msg_parts.append(f"volume set to {level}%")

            return {"status": "success", "message": "Audio " + ", ".join(msg_parts)}
        except Exception as e:
            # Fallback to windows nircmd or powershell if pycaw fails
            return {"status": "error", "message": f"Volume adjustment failed: {e}"}

    @staticmethod
    def _set_brightness(level: int) -> dict[str, Any]:
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(level)
            return {"status": "success", "message": f"Display brightness set to {level}%."}
        except Exception as e:
            return {"status": "error", "message": f"Brightness adjustment failed: {e}"}

    _clipboard_cache: str = ""

    @classmethod
    def _handle_clipboard(cls, action: str, text: str = "") -> dict[str, Any]:
        import time
        # Retry up to 3 times for physical Windows clipboard
        for _ in range(3):
            try:
                import win32clipboard
                import win32con

                if action == "read":
                    win32clipboard.OpenClipboard()
                    try:
                        data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                        cls._clipboard_cache = str(data)
                        return {"status": "success", "content": str(data)}
                    finally:
                        win32clipboard.CloseClipboard()
                elif action == "write":
                    win32clipboard.OpenClipboard()
                    try:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                        cls._clipboard_cache = text
                        return {"status": "success", "message": "Copied text to clipboard."}
                    finally:
                        win32clipboard.CloseClipboard()
            except Exception:
                time.sleep(0.02)

        # Fallback to pyperclip
        try:
            import pyperclip
            if action == "read":
                content = pyperclip.paste()
                if content:
                    cls._clipboard_cache = content
                    return {"status": "success", "content": content}
            elif action == "write":
                pyperclip.copy(text)
                cls._clipboard_cache = text
                return {"status": "success", "message": "Copied text to clipboard."}
        except Exception:
            pass

        # In-process clipboard cache fallback (when OS session isolates background token)
        if action == "read":
            return {"status": "success", "content": cls._clipboard_cache, "source": "in_process_cache"}
        elif action == "write":
            cls._clipboard_cache = text
            return {"status": "success", "message": "Copied text to clipboard (session cache)."}

        return {"status": "error", "message": f"Invalid clipboard action: {action}"}

    @classmethod
    def _inspect_screen(cls, query: str = "") -> dict[str, Any]:
        active_window = "Desktop"
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                t = win32gui.GetWindowText(hwnd)
                if t.strip():
                    active_window = t.strip()
        except Exception:
            pass

        # Attempt full OCR screenshot analysis via VisionManager
        try:
            from vision.vision_manager import VisionManager
            import numpy as np
            from PIL import Image

            vm = VisionManager()
            vis_ctx = vm.capture_and_analyze()
            screen_text = (vis_ctx.extracted_text or "").strip()
            detected_window = vis_ctx.metadata.get("active_window")
            if detected_window and detected_window != "Desktop":
                active_window = detected_window

            # Validate frame integrity against blank / unrendered DWM composition captures
            frame_integrity = "OK"
            if vis_ctx.image_path:
                try:
                    with Image.open(vis_ctx.image_path) as img:
                        arr = np.asarray(img.convert("L"), dtype=np.uint8)
                        # Check for true uniform blankness (less than 4 distinct luminance levels)
                        unique_levels = len(np.unique(arr[::4, ::4]))
                        
                        # Compute Laplacian variance for structural edge detection
                        try:
                            import cv2
                            laplacian_var = float(cv2.Laplacian(arr, cv2.CV_64F).var())
                        except Exception:
                            gy, gx = np.gradient(arr.astype(np.float32))
                            laplacian_var = float(np.var(gx) + np.var(gy))

                        # Only flag if both pixel diversity is near-zero AND edge variance is near-zero (genuine unrendered rectangle)
                        # Dark theme IDEs with text have hundreds of unique levels and laplacian_var > 10.0
                        if unique_levels <= 3 and laplacian_var < 0.5:
                            frame_integrity = "BLANK_OR_OCCLUDED"
                            logger.warning(
                                f"[Vision] Capture produced unrendered/blank frame (unique_levels={unique_levels}, laplacian_var={laplacian_var:.3f}). DWM hardware composition may be occluding."
                            )
                except Exception as e:
                    logger.debug(f"[Vision] Frame integrity validation note: {e}")

            if frame_integrity == "BLANK_OR_OCCLUDED":
                # Augment blank OCR with window enumeration
                return cls._get_window_hierarchy_fallback(active_window, query, reason="DWM_GPU_OCCLUDED")

            return {
                "status": "success",
                "active_window": active_window,
                "visible_text": screen_text[:2000] if screen_text else "No visible text detected on screen.",
                "query": query,
                "frame_integrity": frame_integrity,
            }
        except Exception as ocr_err:
            logger.info(f"[AuraToolRegistry] Full screen OCR fallback to Win32 active window inspection: {ocr_err}")
            return cls._get_window_hierarchy_fallback(active_window, query, reason=str(ocr_err))

    @staticmethod
    def _get_window_hierarchy_fallback(active_window: str, query: str = "", reason: str = "") -> dict[str, Any]:
        try:
            import win32gui
            visible_windows = []

            def _enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    txt = win32gui.GetWindowText(hwnd)
                    if txt.strip() and len(txt.strip()) > 1:
                        visible_windows.append(txt.strip())

            win32gui.EnumWindows(_enum_cb, None)
            summary_text = "Active Visible Windows on Desktop:\n" + "\n".join(f"- {w}" for w in visible_windows[:15])

            return {
                "status": "success",
                "active_window": active_window,
                "visible_text": summary_text,
                "query": query,
                "source": "win32_window_hierarchy",
                "fallback_reason": reason,
            }
        except Exception as e:
            return {
                "status": "success",
                "active_window": active_window,
                "visible_text": f"Active focused window is '{active_window}'.",
                "query": query,
                "fallback_reason": str(e),
            }

    @staticmethod
    def _get_system_telemetry() -> dict[str, Any]:
        try:
            import psutil
            import platform

            cpu_pct = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            battery = psutil.sensors_battery()

            battery_info = "N/A"
            if battery:
                battery_info = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'Battery'})"

            return {
                "status": "success",
                "cpu_usage": f"{cpu_pct}%",
                "ram_usage": f"{mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)",
                "battery": battery_info,
                "os": f"{platform.system()} {platform.release()}",
            }
        except Exception as e:
            return {"status": "error", "message": f"Telemetry retrieval failed: {e}"}

    @staticmethod
    def _save_memory_fact(category: str, key: str, value: str, aura_core: Any) -> dict[str, Any]:
        try:
            if aura_core and hasattr(aura_core, "memory") and aura_core.memory:
                aura_core.memory.add_fact(category, key, value)
                return {"status": "success", "message": f"Saved fact [{category}] {key} = '{value}' to persistent memory."}
            return {"status": "error", "message": "Memory store not accessible."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to save fact: {e}"}

    @staticmethod
    def _query_memory_facts(category: str | None, key: str | None, aura_core: Any) -> dict[str, Any]:
        try:
            if aura_core and hasattr(aura_core, "memory") and aura_core.memory:
                if category and key:
                    val = aura_core.memory.fact_value(category, key)
                    return {"status": "success", "facts": [{category: {key: val}}]} if val else {"status": "success", "facts": []}
                elif category:
                    facts = aura_core.memory.all_facts(category)
                    return {"status": "success", "facts": [{f.category: {f.key: f.value}} for f in facts]}
                else:
                    facts = aura_core.memory.all_facts()
                    return {"status": "success", "facts": [{f.category: {f.key: f.value}} for f in facts[:20]]}
            return {"status": "error", "message": "Memory store not accessible."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to query facts: {e}"}

    @staticmethod
    def _open_url(url: str) -> dict[str, Any]:
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)
            return {"status": "success", "message": f"Opened {url} in web browser."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to open URL: {e}"}

    @staticmethod
    def _get_daily_agenda(target_date: str | None, aura_core: Any) -> dict[str, Any]:
        try:
            from personal_os.daily_context import DailyContextEngine
            engine = DailyContextEngine()
            ctx = engine.get_daily_context(target_date=target_date)
            return {
                "status": "success",
                "date": ctx.date,
                "summary": ctx.summary,
                "tasks_count": len(ctx.tasks),
                "meetings_count": len(ctx.meetings),
                "deadlines_count": len(ctx.deadlines),
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to fetch daily agenda: {e}"}

    @staticmethod
    def _add_personal_task(title: str, due_date: str | None, priority: int, aura_core: Any) -> dict[str, Any]:
        try:
            from personal_os.state_store import PersonalOSStateStore
            import uuid
            from datetime import datetime

            store = PersonalOSStateStore.get_instance()
            tasks = store.get_preference("tasks_list", [])
            if not isinstance(tasks, list):
                tasks = []

            priority_label = "HIGH" if priority == 1 else ("LOW" if priority == 3 else "NORMAL")
            new_task = {
                "task_id": f"task_{uuid.uuid4().hex[:8]}",
                "title": title,
                "status": "PENDING",
                "priority": priority_label,
                "due_date": due_date,
                "created_at": datetime.utcnow().isoformat(),
            }
            tasks.append(new_task)
            store.set_preference("tasks_list", tasks)

            return {"status": "success", "message": f"Added task '{title}' with priority {priority_label}."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to add task: {e}"}

