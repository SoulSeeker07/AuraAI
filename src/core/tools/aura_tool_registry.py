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
                    "name": "desktop_create_note",
                    "description": "Create a text note or file on the user's desktop with the specified filename and content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "Filename (e.g. 'spacex_summary.txt' or 'SpaceX_Launch_Note.txt').",
                            },
                            "content": {
                                "type": "string",
                                "description": "The text content or summary to save to the desktop file.",
                            },
                        },
                        "required": ["filename", "content"],
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
            {
                "type": "function",
                "function": {
                    "name": "terminal_run_command",
                    "description": "Execute a shell or PowerShell command on the system. Safe read-only inspection commands execute immediately; mutating commands generate an approval ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The exact shell command line string to execute.",
                            },
                            "cwd": {
                                "type": "string",
                                "description": "Optional working directory path.",
                            },
                            "ticket_id": {
                                "type": "string",
                                "description": "Cryptographic approval ticket ID for executing confirmed mutating commands.",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docker_container_action",
                    "description": "Manage or query Docker containers. Read-only actions (list, logs, inspect) execute immediately; mutating actions (stop, restart, remove, prune) require an approval ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list", "logs", "inspect", "ps", "stop", "restart", "remove", "prune"],
                                "description": "Action to perform on Docker.",
                            },
                            "container_id": {
                                "type": "string",
                                "description": "Target container ID or name (for logs, inspect, stop, restart, remove).",
                            },
                            "ticket_id": {
                                "type": "string",
                                "description": "Cryptographic approval ticket ID for mutating container actions.",
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_navigate_and_read",
                    "description": "Navigate to a web URL using headless browser engine and extract page text or markdown content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The web URL to navigate to.",
                            },
                            "extract_mode": {
                                "type": "string",
                                "enum": ["markdown", "text", "title", "links"],
                                "description": "Format of extracted web content (default: 'markdown').",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_discover_and_call",
                    "description": "Discover and execute tools from connected Model Context Protocol (MCP) tool servers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list_servers", "list_tools", "call_tool"],
                                "description": "Action to perform on MCP ecosystem.",
                            },
                            "server_name": {
                                "type": "string",
                                "description": "Target MCP server name (optional for list_servers).",
                            },
                            "tool_name": {
                                "type": "string",
                                "description": "Tool name on the MCP server (for call_tool).",
                            },
                            "arguments": {
                                "type": "object",
                                "description": "Arguments to pass to the MCP tool.",
                            },
                        },
                        "required": ["action"],
                    },
                },
            },
        ]

    @classmethod
    async def execute_tool(
        cls, name: str, arguments: dict[str, Any], aura_core: Any = None, emitter: Any = None
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

            elif name == "desktop_create_note":
                filename = arguments.get("filename", "note.txt").strip()
                content = arguments.get("content", "")
                return await asyncio.to_thread(cls._create_desktop_note, filename, content)

            elif name == "personal_os_get_daily_agenda":
                target_date = arguments.get("date")
                return await asyncio.to_thread(cls._get_daily_agenda, target_date, aura_core)

            elif name == "personal_os_add_task":
                title = arguments.get("title", "")
                due_date = arguments.get("due_date")
                priority = int(arguments.get("priority", 2))
                return await asyncio.to_thread(cls._add_personal_task, title, due_date, priority, aura_core)

            elif name == "terminal_run_command":
                cmd = arguments.get("command", "").strip()
                cwd = arguments.get("cwd")
                tkt_id = arguments.get("ticket_id")
                return await asyncio.to_thread(cls._run_terminal_command, cmd, cwd, tkt_id)

            elif name == "docker_container_action":
                act = arguments.get("action", "list")
                c_id = arguments.get("container_id")
                tkt_id = arguments.get("ticket_id")
                return await asyncio.to_thread(cls._docker_action, act, c_id, tkt_id)

            elif name == "browser_navigate_and_read":
                target_url = arguments.get("url", "")
                mode = arguments.get("extract_mode", "markdown")
                return await asyncio.to_thread(cls._browser_navigate_and_read, target_url, mode)

            elif name == "mcp_discover_and_call":
                act = arguments.get("action", "list_tools")
                srv = arguments.get("server_name")
                tool = arguments.get("tool_name")
                args = arguments.get("arguments")
                return await asyncio.to_thread(cls._mcp_discover_and_call, act, srv, tool, args)

            else:
                return {"status": "error", "error": f"Unknown tool: {name}"}

        except Exception as e:
            logger.error(f"[AuraToolRegistry] Tool execution failed for {name}: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    # ── Tool Implementations ──────────────────────────────────────────────

    @staticmethod
    def _create_desktop_note(filename: str, content: str) -> dict[str, Any]:
        """Create a note on the user's Desktop directory."""
        from pathlib import Path
        try:
            desktop_dir = Path.home() / "Desktop"
            if not desktop_dir.exists():
                onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
                if onedrive_desktop.exists():
                    desktop_dir = onedrive_desktop

            if not filename.endswith((".txt", ".md")):
                filename += ".txt"

            file_path = desktop_dir / filename
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"[AuraToolRegistry] Created note on desktop: {file_path}")
            return {
                "status": "success",
                "message": f"Successfully created summary note '{filename}' on your Desktop.",
                "path": str(file_path),
            }
        except Exception as e:
            logger.error(f"[AuraToolRegistry] Failed to create desktop note: {e}")
            return {"status": "error", "error": f"Failed to save note on Desktop: {e}"}

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
            "chrome": "start chrome",
            "google chrome": "start chrome",
            "edge": "start msedge",
            "msedge": "start msedge",
            "file explorer": "explorer",
            "explorer": "explorer",
            "task manager": "taskmgr",
            "cmd": "cmd",
            "terminal": "wt",
        }

        # Check WindowManager resolver for known apps and web URLs (e.g. instagram, youtube, whatsapp)
        try:
            from desktop.native.managers.window_manager import WindowManager
            res_type, resolved_target = WindowManager()._resolve_app_executable(app_clean)
            if res_type == "url" and resolved_target:
                webbrowser.open(resolved_target)
                return {"status": "success", "message": f"Opened '{application}' in web browser."}
            elif res_type == "protocol" and resolved_target:
                if os.name == "nt":
                    os.system(f"start {resolved_target}")
                else:
                    webbrowser.open(resolved_target)
                return {"status": "success", "message": f"Launched '{application}' successfully."}
            elif res_type == "exe" and resolved_target and os.path.isabs(resolved_target):
                subprocess.Popen(f'start "" "{resolved_target}"', shell=True)
                return {"status": "success", "message": f"Launched '{application}' successfully."}
        except Exception as res_err:
            logger.debug(f"[AuraToolRegistry] WindowManager lookup fallback: {res_err}")

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
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL

            devices = AudioUtilities.GetSpeakers()
            if hasattr(devices, "EndpointVolume"):
                volume = devices.EndpointVolume
            else:
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

    @staticmethod
    def _run_terminal_command(command: str, cwd: str | None = None, ticket_id: str | None = None) -> dict[str, Any]:
        """
        Executes a shell command with strict CryptographicApprovalAuthority risk gating.
        Safe inspection commands auto-execute; state-mutating commands require ticket approval.
        """
        import re
        import subprocess
        from pathlib import Path

        cmd_clean = command.strip()
        if not cmd_clean:
            return {"status": "error", "error": "Empty command provided."}

        # 1. Tier 3: Prohibited destructive blocklist (fail-closed)
        prohibited_patterns = [
            r"\bformat\s+[a-z]:",
            r"\bdel\s+/[fqs]\s+[a-z]:\\",
            r"\brmdir\s+/[sq]\s+[a-z]:\\",
            r"\brm\s+-rf\s+[/~\\]",
            r"\bremove-item\s+.*-recurse.*[a-z]:\\",
            r"\b(set-mppreference|add-mppreference)\b",
            r"(\.ssh[/\\]id_|id_rsa|id_ed25519|credentials\.json|\.aws[/\\]credentials)",
            r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
            r"%\s*0\s*\|\s*%\s*0",
        ]
        for pat in prohibited_patterns:
            if re.search(pat, cmd_clean, re.IGNORECASE):
                logger.error(f"[AuraToolRegistry] Command blocked by safety policy: {cmd_clean}")
                return {"status": "blocked", "error": "Command blocked fail-closed by security policy."}

        # 2. Check for shell command chaining, pipeline, or redirection metacharacters.
        # Any command containing chaining operators cannot auto-execute via safe-prefixes.
        chaining_pattern = re.compile(r"[;&|`$><\n]")
        has_chaining = bool(chaining_pattern.search(cmd_clean))

        # 3. Tier 1: Safe read-only inspection prefixes with strict word boundary check
        safe_prefixes = (
            "git status", "git log", "git diff", "git branch", "git show", "git tag",
            "dir", "ls", "cat", "type", "get-childitem", "get-content", "get-process",
            "get-service", "get-command", "get-location", "pwd", "echo", "where", "which",
            "python --version", "node --version", "npm --version", "git --version",
            "pytest", "ruff", "black", "ipconfig", "ping", "whoami", "hostname",
            "select-string", "findstr", "grep",
        )

        cmd_lower = cmd_clean.lower()
        is_safe_prefix = any(
            cmd_lower == p or cmd_lower.startswith(p + " ") or cmd_lower.startswith(p + "\t")
            for p in safe_prefixes
        )

        # A command is only Tier 1 (safe auto-execute) if it matches a safe prefix AND has NO chaining/redirection
        is_safe = is_safe_prefix and not has_chaining

        # 4. Tier 2: State-mutating or unlisted commands require CryptographicApprovalAuthority ticket
        if not is_safe:
            from desktop.native.security.approval_authority import CryptographicApprovalAuthority
            auth = CryptographicApprovalAuthority.get_instance()

            if ticket_id:
                # User provided ticket_id for confirmation
                sig = auth.generate_human_signature(ticket_id)
                if not sig:
                    return {
                        "status": "error",
                        "error": f"Invalid, unverified, or expired approval ticket '{ticket_id}'.",
                    }
                from core.config import PROJECT_ROOT
                resolved_cwd = str(Path(cwd).resolve()) if cwd else str(PROJECT_ROOT)

                ok, err_msg = auth.verify_and_redeem(
                    ticket_id=ticket_id,
                    signature=sig,
                    action_type="terminal_execution",
                    target=cmd_clean,
                    parameters={"cwd": resolved_cwd},
                )
                if not ok:
                    return {
                        "status": "error",
                        "error": f"Ticket verification failed: {err_msg}",
                    }
                logger.info(f"[AuraToolRegistry] Redeemed approval ticket '{ticket_id}' for command: {cmd_clean}")
            else:
                from core.config import PROJECT_ROOT
                resolved_cwd = str(Path(cwd).resolve()) if cwd else str(PROJECT_ROOT)

                # Generate new approval ticket and request user confirmation
                new_ticket_id = auth.create_ticket(
                    action_type="terminal_execution",
                    target=cmd_clean,
                    parameters={"cwd": resolved_cwd},
                    description=f"Execute shell command: {cmd_clean} in {resolved_cwd}",
                )
                logger.info(f"[AuraToolRegistry] Generated approval ticket '{new_ticket_id}' for command: {cmd_clean}")
                return {
                    "status": "confirmation_required",
                    "ticket_id": new_ticket_id,
                    "action": "terminal_execution",
                    "command": cmd_clean,
                    "message": (
                        f"This command modifies system/file state. "
                        f"Approval ticket '{new_ticket_id}' generated. Please confirm execution."
                    ),
                }

        # Execute command
        try:
            target_cwd = cwd or str(Path.cwd())
            res = subprocess.run(
                cmd_clean,
                shell=True,
                capture_output=True,
                text=True,
                cwd=target_cwd,
                timeout=30,
            )
            return {
                "status": "success",
                "command": cmd_clean,
                "exit_code": res.returncode,
                "stdout": res.stdout[:4000] if res.stdout else "",
                "stderr": res.stderr[:2000] if res.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Command timed out after 30 seconds."}
        except Exception as e:
            return {"status": "error", "error": f"Execution failed: {e}"}

    @staticmethod
    def _docker_action(action: str, container_id: str | None = None, ticket_id: str | None = None) -> dict[str, Any]:
        """
        Executes Docker container queries and actions with ticket gating for mutating operations.
        """
        import subprocess

        action_clean = action.lower().strip()
        read_only_actions = {"list", "ps", "logs", "inspect"}

        if action_clean not in read_only_actions:
            from desktop.native.security.approval_authority import CryptographicApprovalAuthority
            auth = CryptographicApprovalAuthority.get_instance()

            if ticket_id:
                sig = auth.generate_human_signature(ticket_id)
                if not sig:
                    return {"status": "error", "error": f"Invalid or expired approval ticket '{ticket_id}'."}
                ok, err_msg = auth.verify_and_redeem(
                    ticket_id=ticket_id,
                    signature=sig,
                    action_type="docker_action",
                    target=f"{action_clean}:{container_id or 'all'}",
                    parameters={"action": action_clean, "container_id": container_id},
                )
                if not ok:
                    return {"status": "error", "error": f"Ticket verification failed: {err_msg}"}
            else:
                new_ticket_id = auth.create_ticket(
                    action_type="docker_action",
                    target=f"{action_clean}:{container_id or 'all'}",
                    parameters={"action": action_clean, "container_id": container_id},
                    description=f"Docker {action_clean} on container '{container_id}'",
                )
                return {
                    "status": "confirmation_required",
                    "ticket_id": new_ticket_id,
                    "action": "docker_action",
                    "operation": f"docker {action_clean} {container_id or ''}".strip(),
                    "message": f"Docker {action_clean} requires approval. Ticket '{new_ticket_id}' generated.",
                }

        # Build CLI command
        if action_clean in ("list", "ps"):
            cmd = "docker ps -a --format \"table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Names}}\""
        elif action_clean == "logs":
            if not container_id:
                return {"status": "error", "error": "container_id required for docker logs."}
            cmd = f"docker logs --tail 50 {container_id}"
        elif action_clean == "inspect":
            if not container_id:
                return {"status": "error", "error": "container_id required for docker inspect."}
            cmd = f"docker inspect {container_id}"
        elif action_clean in ("stop", "restart", "remove"):
            if not container_id:
                return {"status": "error", "error": f"container_id required for docker {action_clean}."}
            subcmd = "rm -f" if action_clean == "remove" else action_clean
            cmd = f"docker {subcmd} {container_id}"
        elif action_clean == "prune":
            cmd = "docker system prune -f"
        else:
            return {"status": "error", "error": f"Unsupported docker action: {action}"}

        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
            return {
                "status": "success",
                "action": action_clean,
                "exit_code": res.returncode,
                "stdout": res.stdout[:4000] if res.stdout else "",
                "stderr": res.stderr[:1000] if res.stderr else "",
            }
        except Exception as e:
            return {"status": "error", "error": f"Docker operation failed: {e}"}

    @staticmethod
    def _browser_navigate_and_read(url: str, extract_mode: str = "markdown") -> dict[str, Any]:
        """
        Navigates to URL using headless browser engine and extracts page content.
        """
        import urllib.request
        import re

        target_url = url.strip()
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
                page = browser.new_page()
                page.goto(target_url, wait_until="networkidle", timeout=12000)

                title = page.title()
                if extract_mode == "title":
                    browser.close()
                    return {"status": "success", "url": target_url, "title": title}

                body_text = page.inner_text("body")
                browser.close()

                # Clean whitespace
                lines = [line.strip() for line in body_text.splitlines() if line.strip()]
                clean_content = "\n".join(lines[:100])  # Top 100 meaningful lines

                return {
                    "status": "success",
                    "url": target_url,
                    "title": title,
                    "content": clean_content[:4000],
                    "extract_mode": extract_mode,
                }
        except Exception as pw_err:
            logger.warning(f"[AuraToolRegistry] Playwright read fallback to HTTP request: {pw_err}")
            # Fallback to standard HTTP GET
            try:
                req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AuraAI/1.0"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                    # Simple tag stripper
                    text = re.sub(r"<[^>]+>", " ", html)
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    return {
                        "status": "success",
                        "url": target_url,
                        "content": "\n".join(lines[:80])[:3000],
                        "source": "http_fallback",
                    }
            except Exception as http_err:
                return {"status": "error", "error": f"Failed to navigate and read {target_url}: {http_err}"}

    @staticmethod
    def _mcp_discover_and_call(
        action: str,
        server_name: str | None = None,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Discovers and executes tools across Model Context Protocol servers.
        """
        try:
            try:
                from plugins.mcp.mcp_plugin import MCPPlugin
                plugin = MCPPlugin()
                plugin.load()
                plugin.initialize()
            except (ImportError, ModuleNotFoundError):
                plugin = None

            if action == "list_servers":
                servers = getattr(plugin, "get_servers", lambda: ["filesystem", "memory", "sqlite"])() if plugin else ["filesystem", "memory", "sqlite"]
                return {"status": "success", "servers": servers}

            elif action == "list_tools":
                if plugin:
                    res = plugin.execute(capability="mcp.list_tools", server_name=server_name)
                    return {"status": "success", "tools": getattr(res, "data", {})}
                return {"status": "success", "tools": []}

            elif action == "call_tool":
                if not tool_name:
                    return {"status": "error", "error": "tool_name is required for call_tool."}
                if plugin:
                    res = plugin.execute(
                        capability="mcp.call_tool",
                        server_name=server_name,
                        tool_name=tool_name,
                        arguments=arguments or {},
                    )
                    return {
                        "status": "success" if res.success else "error",
                        "result": getattr(res, "data", getattr(res, "observation", str(res))),
                    }
                return {"status": "error", "error": f"MCP server '{server_name}' not connected."}
            else:
                return {"status": "error", "error": f"Unknown MCP action: {action}"}
        except Exception as e:
            return {"status": "error", "error": f"MCP operation failed: {e}"}


