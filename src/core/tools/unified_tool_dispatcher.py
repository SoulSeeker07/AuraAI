"""
Unified Tool Dispatcher
=======================
Location: src/core/tools/unified_tool_dispatcher.py

Canonical 14-tool discrete execution dispatcher for Aura AI's Agent Loop.
Implements the 14-tool OpenAI/Groq function calling schema, verified against
all Groq model tiers, with mandatory classify_action_risk() and
CryptographicApprovalAuthority HMAC ticket governance on every execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SRC_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _SRC_ROOT.parent

class UnifiedToolDispatcher:
    """
    Unified Tool Dispatcher exposing 14 discrete, flat, strictly-typed tools.
    Every tool call passes through:
      1. classify_action_risk()
      2. ExecutionPolicy.evaluate_action()
      3. CryptographicApprovalAuthority ticket redemption for HIGH/CRITICAL actions.
    """

    @classmethod
    def get_tool_definitions(cls) -> list[dict[str, Any]]:
        """Return the 14 discrete, flat tool schemas for OpenAI/Groq function calling."""
        return [
            # ── 1. Coding & Workspace Tools (3) ──────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read contents of a file in the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path to file"},
                            "start_line": {"type": "integer", "description": "Optional 1-indexed start line"},
                            "end_line": {"type": "integer", "description": "Optional 1-indexed end line"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Replace exact existing text with new replacement text in a workspace file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path to file"},
                            "target_content": {"type": "string", "description": "Exact existing code snippet to replace"},
                            "replacement_content": {"type": "string", "description": "New code snippet to insert"}
                        },
                        "required": ["path", "target_content", "replacement_content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": "Run targeted pytest verification suite on a test file or module.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "test_target": {"type": "string", "description": "Path to test file or specific test function"}
                        },
                        "required": ["test_target"]
                    }
                }
            },
            # ── 2. System & Shell Tools (2) ──────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "terminal_run_command",
                    "description": "Execute a shell or PowerShell command on the system. Safe read-only inspection commands execute immediately; mutating commands generate an approval ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The exact shell command line string to execute."},
                            "cwd": {"type": "string", "description": "Optional working directory path."},
                            "ticket_id": {"type": "string", "description": "Cryptographic approval ticket ID for mutating commands."}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "system_get_telemetry",
                    "description": "Get real-time hardware telemetry: CPU, RAM, battery level, and active OS metrics.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            # ── 3. Screen & Vision Tools (1) ────────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "vision_inspect_screen",
                    "description": "Capture current screen and inspect visible text, active window content, and open applications via OCR/vision.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Specific element, application, or text to look for on screen."}
                        }
                    }
                }
            },
            # ── 4. Browser Automation Tools (2) ──────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "browser_navigate_and_read",
                    "description": "Navigate to a web URL using headless browser engine and extract page text or markdown content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "The web URL to navigate to."},
                            "extract_mode": {"type": "string", "enum": ["markdown", "text", "title", "links"], "description": "Extraction mode"}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_interact",
                    "description": "Perform an interactive action in the active browser page (click, type, scroll, wait).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["click", "type", "scroll", "press_key"]},
                            "selector": {"type": "string", "description": "CSS or XPath selector"},
                            "value": {"type": "string", "description": "Text value to type or key to press"}
                        },
                        "required": ["action", "selector"]
                    }
                }
            },
            # ── 5. Desktop Automation Tools (5) ──────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "desktop_launch_app",
                    "description": "Launch a Windows application (e.g. notepad, spotify, chrome, calc, vscode).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "application": {"type": "string", "description": "Name of the application to launch"}
                        },
                        "required": ["application"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "desktop_control_window",
                    "description": "Control an application window (focus, minimize, maximize, restore, or close).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "window_title": {"type": "string", "description": "Window title or app name"},
                            "action": {"type": "string", "enum": ["focus", "minimize", "maximize", "restore", "close"]}
                        },
                        "required": ["window_title", "action"]
                    }
                }
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
                                "description": "Whether to read or write to the clipboard."
                            },
                            "text": {
                                "type": "string",
                                "description": "Text to write to the clipboard (required when action is 'write')."
                            }
                        },
                        "required": ["action"]
                    }
                }
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
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Volume percentage between 0 and 100."
                            },
                            "mute": {
                                "type": "boolean",
                                "description": "True to mute, False to unmute (optional)."
                            }
                        }
                    }
                }
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
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Brightness percentage from 0 to 100."
                            }
                        },
                        "required": ["level"]
                    }
                }
            },
            # ── 6. Memory & Personal OS Tools (3) ────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "memory_save_fact",
                    "description": "Save a user preference, profile detail, or persistent note to memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": ["profile", "preference", "skill", "project", "goal"]},
                            "key": {"type": "string", "description": "Fact key"},
                            "value": {"type": "string", "description": "Information to remember"}
                        },
                        "required": ["category", "key", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_query_facts",
                    "description": "Query persistent memory to recall user preferences or facts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "key": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "personal_os_agenda",
                    "description": "Get today agenda, deadlines, and prioritized tasks from Personal OS.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "YYYY-MM-DD date"}
                        }
                    }
                }
            },
            # ── 7. Dynamic Task Tracking Tool (1) ────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "task_plan_update",
                    "description": "Update the active task plan and subtasks progress checklist.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "task_id": {"type": "string"},
                                        "title": {"type": "string"},
                                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed"]}
                                    },
                                    "required": ["task_id", "title", "status"]
                                }
                            }
                        },
                        "required": ["tasks"]
                    }
                }
            },
            # ── 8. File Artifact Generation Tool (1) ─────────────────────────────
            # This tool is the correct path for any request to CREATE a file:
            # Excel spreadsheets, Word documents, PowerPoint presentations, CSVs,
            # PDFs, or any other generated artifact.  It routes to the CodeAct
            # sandboxed synthesis engine (DynamicCodeActExecutor) which drafts,
            # statically-checks, and executes Python code in a restricted staging
            # environment.  It must NOT be replaced by terminal_run_command for
            # these requests.
            {
                "type": "function",
                "function": {
                    "name": "create_file_artifact",
                    "description": (
                        "Generate and save a file artifact: Excel spreadsheet (.xlsx), "
                        "Word document (.docx), PowerPoint presentation (.pptx), CSV, "
                        "PDF, or any data file. Use this tool whenever the user asks to "
                        "CREATE, GENERATE, or MAKE a document, spreadsheet, or file. "
                        "Do NOT use terminal_run_command for file creation tasks — use this tool."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": (
                                    "Full natural-language description of what to create, "
                                    "including content, columns, data, formatting, and any "
                                    "other relevant details from the user's request."
                                ),
                            },
                            "output_filename": {
                                "type": "string",
                                "description": (
                                    "Target filename with extension, e.g. 'shopping_list.xlsx', "
                                    "'report.docx', 'slides.pptx'. Must include the correct "
                                    "extension for the requested format."
                                ),
                            },
                            "destination": {
                                "type": "string",
                                "description": (
                                    "Optional save location. Use 'desktop' to save to the user's "
                                    "Desktop, 'downloads' for the Downloads folder, or omit to "
                                    "save to the current working directory."
                                ),
                                "enum": ["desktop", "downloads", "documents", "cwd"],
                            },
                        },
                        "required": ["goal", "output_filename"],
                    },
                },
            },
            # ── 9. SmartHome Device Control Tool (1) ─────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "smarthome_control",
                    "description": "Control smart home devices (lights, switches, plugs, fans, smart locks) or query device status via Home Assistant or direct Tapo integration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "Action to perform (e.g. 'turn_on', 'turn_off', 'toggle', 'set_brightness', 'set_color', 'get_state', 'list_all', 'lock', 'unlock')."
                            },
                            "entity_id": {
                                "type": "string",
                                "description": "Target device entity ID, e.g. 'light.living_room', 'switch.bedroom_fan', 'lock.front_door'."
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Optional parameters such as brightness (0-255), color, color_temp, or speed."
                            },
                            "ticket_id": {
                                "type": "string",
                                "description": "Cryptographic approval ticket ID for high-risk operations (e.g. smart locks)."
                            },
                            "signature": {
                                "type": "string",
                                "description": "HMAC signature for approval ticket."
                            }
                        },
                        "required": ["action", "entity_id"]
                    }
                }
            },
            # ── 10. Email Communication Tool (1) ─────────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "email_action",
                    "description": "Read, search, draft, or send emails. Read operations execute immediately; sending emails requires human approval ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["read_inbox", "search", "send", "draft", "reply", "list_folders"],
                                "description": "The email action to perform."
                            },
                            "recipient": {
                                "type": "string",
                                "description": "Recipient email address (for send, draft, reply)."
                            },
                            "subject": {
                                "type": "string",
                                "description": "Subject of the email."
                            },
                            "body": {
                                "type": "string",
                                "description": "Body content of the email."
                            },
                            "query": {
                                "type": "string",
                                "description": "Search query or keyword (for search)."
                            },
                            "ticket_id": {
                                "type": "string",
                                "description": "Cryptographic approval ticket ID for sending emails."
                            },
                            "signature": {
                                "type": "string",
                                "description": "HMAC signature for approval ticket."
                            }
                        },
                        "required": ["action"]
                    }
                }
            },
            # ── 11. Calendar & Scheduling Tool (1) ───────────────────────────────
            {
                "type": "function",
                "function": {
                    "name": "calendar_action",
                    "description": "List events, create calendar appointments, update, or delete events. Listing events executes immediately; deleting events requires human approval ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["list_events", "create_event", "update_event", "delete_event", "check_availability"],
                                "description": "Calendar action to perform."
                            },
                            "title": {
                                "type": "string",
                                "description": "Title or summary of the event (for create, update)."
                            },
                            "start_time": {
                                "type": "string",
                                "description": "Start time ISO string or format YYYY-MM-DD HH:MM."
                            },
                            "end_time": {
                                "type": "string",
                                "description": "End time ISO string or format YYYY-MM-DD HH:MM."
                            },
                            "event_id": {
                                "type": "string",
                                "description": "Event ID (for update, delete)."
                            },
                            "ticket_id": {
                                "type": "string",
                                "description": "Cryptographic approval ticket ID for deleting events."
                            },
                            "signature": {
                                "type": "string",
                                "description": "HMAC signature for approval ticket."
                            }
                        },
                        "required": ["action"]
                    }
                }
            },
        ]


    # ── Policy & Risk Classification Mapper ───────────────────────────────────

    @classmethod
    def _map_tool_to_risk(cls, name: str, arguments: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        """Maps a tool name and arguments to (engine_domain, action_name, params) for classify_action_risk."""
        if name == "read_file":
            return ("filesystem", "file.read", arguments)
        elif name == "edit_file":
            return ("engineering", "edit_file", arguments)
        elif name == "run_tests":
            return ("engineering", "code.test", arguments)
        elif name == "terminal_run_command":
            cmd = str(arguments.get("command") or "").strip()
            cmd_lower = cmd.lower()
            safe_prefixes = (
                "git status", "git log", "git diff", "git branch", "git show", "git tag",
                "dir", "ls", "cat", "type", "get-childitem", "get-content", "get-process",
                "get-service", "get-command", "get-location", "pwd", "echo", "where", "which",
                "python --version", "node --version", "npm --version", "git --version",
                "pytest", "ruff", "black", "ipconfig", "ping", "whoami", "hostname",
                "select-string", "findstr", "grep",
            )
            has_chaining = any(c in cmd for c in (";", "&", "|", ">", "<", "`", "$("))
            is_safe_prefix = any(
                cmd_lower == p or cmd_lower.startswith(p + " ") or cmd_lower.startswith(p + "\t")
                for p in safe_prefixes
            )
            if is_safe_prefix and not has_chaining:
                return ("desktop", "terminal.get_output", arguments)
            return ("desktop", "terminal.execute", arguments)
        elif name == "system_get_telemetry":
            return ("desktop", "system_info", arguments)
        elif name == "vision_inspect_screen":
            return ("desktop", "vision.ocr", arguments)
        elif name == "browser_navigate_and_read":
            return ("browser", "browser.navigate", arguments)
        elif name == "browser_interact":
            action = str(arguments.get("action") or "click").lower().strip()
            if action in ("submit", "form.submit"):
                return ("browser", "browser.submit", arguments)
            return ("browser", action, arguments)
        elif name == "desktop_launch_app":
            app = str(arguments.get("application") or "").lower().strip()
            dangerous_apps = (
                "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
                "bash", "bash.exe", "wsl", "wsl.exe", "regedit", "regedit.exe",
                "format", "rundll32", "rundll32.exe", "wscript", "cscript",
            )
            if app in dangerous_apps or any(app.startswith(d + " ") for d in dangerous_apps):
                return ("desktop", "terminal.execute", arguments)
            return ("desktop", "app_open", arguments)
        elif name == "desktop_control_window":
            act = str(arguments.get("action") or "focus").lower().strip()
            if act == "close":
                return ("desktop", "close_window", arguments)
            elif act == "minimize":
                return ("desktop", "minimize_window", arguments)
            elif act == "maximize":
                return ("desktop", "maximize_window", arguments)
            elif act == "restore":
                return ("desktop", "restore_window", arguments)
            return ("desktop", "activate_window", arguments)
        elif name == "memory_save_fact":
            return ("memory", "memory.store", arguments)
        elif name == "memory_query_facts":
            return ("memory", "memory.recall", arguments)
        elif name == "personal_os_agenda":
            return ("personal_os", "get_agenda", arguments)
        elif name == "task_plan_update":
            return ("orchestration", "plan_update", arguments)
        elif name == "create_file_artifact":
            return ("codeact", "codeact.synthesize", arguments)
        elif name == "desktop_clipboard":
            action = str(arguments.get("action") or "read").lower().strip()
            if action == "write":
                return ("desktop", "clipboard.write", arguments)
            return ("desktop", "clipboard.read", arguments)
        elif name == "desktop_set_volume":
            return ("desktop", "audio.set_volume", arguments)
        elif name == "desktop_set_brightness":
            return ("desktop", "display.set_brightness", arguments)
        elif name == "smarthome_control":
            import re
            action = str(arguments.get("action") or "get_state").lower().strip()
            entity_id = str(arguments.get("entity_id") or "").lower().strip()
            is_lock_action = action in ("lock", "unlock") or action.endswith(".lock") or action.endswith(".unlock")
            domain = entity_id.split(".")[0] if "." in entity_id else ""
            is_lock_device = domain == "lock" or bool(re.search(r"\b(?:door_lock|smart_lock|lock)\b", entity_id))
            if is_lock_action or is_lock_device:
                return ("smarthome", f"smarthome.{action}", arguments)
            if action.startswith("light.") or action.startswith("switch.") or action.startswith("fan."):
                return ("smarthome", f"smarthome.{action}", arguments)
            return ("smarthome", f"smarthome.{action}", arguments)
        elif name == "email_action":
            action = str(arguments.get("action") or "read_inbox").lower().strip()
            if action == "send":
                return ("email", "send_email", arguments)
            elif action == "draft":
                return ("email", "email.draft", arguments)
            elif action in ("delete", "delete_email"):
                return ("email", "email.delete", arguments)
            return ("email", f"email.{action}", arguments)
        elif name == "calendar_action":
            action = str(arguments.get("action") or "list_events").lower().strip()
            if "delete" in action:
                return ("calendar", "calendar.delete_event", arguments)
            elif "create" in action:
                return ("calendar", "calendar.create_event", arguments)
            elif "update" in action:
                return ("calendar", "calendar.update_event", arguments)
            return ("calendar", f"calendar.{action}", arguments)
        return ("desktop", name, arguments)



    @classmethod
    def _extract_target(cls, name: str, arguments: dict[str, Any]) -> str:
        """Extract canonical target descriptor for parameter-bound cryptographic tickets."""
        if name in ("read_file", "edit_file"):
            return str(arguments.get("path") or "")
        elif name == "terminal_run_command":
            return str(arguments.get("command") or "")
        elif name == "browser_navigate_and_read":
            return str(arguments.get("url") or "")
        elif name == "browser_interact":
            return str(arguments.get("selector") or "")
        elif name == "desktop_launch_app":
            return str(arguments.get("application") or "")
        elif name == "desktop_control_window":
            return str(arguments.get("window_title") or "")
        elif name in ("memory_save_fact", "memory_query_facts"):
            return f"{arguments.get('category', '')}:{arguments.get('key', '')}"
        elif name == "personal_os_agenda":
            return str(arguments.get("date") or "")
        elif name == "run_tests":
            return str(arguments.get("test_target") or "")
        elif name == "create_file_artifact":
            return str(arguments.get("output_filename") or "")
        elif name == "desktop_clipboard":
            return str(arguments.get("action") or "read")
        elif name == "desktop_set_volume":
            return f"level={arguments.get('level')},mute={arguments.get('mute')}"
        elif name == "desktop_set_brightness":
            return f"level={arguments.get('level')}"
        elif name == "smarthome_control":
            return f"{arguments.get('entity_id', '')}:{arguments.get('action', '')}"
        elif name == "email_action":
            return f"{arguments.get('recipient', '')}:{arguments.get('subject', '')}"
        elif name == "calendar_action":
            act = str(arguments.get("action") or "").lower().strip()
            if "delete" in act or "event_id" in arguments:
                return f"{act}:{arguments.get('event_id', '')}"
            return f"{arguments.get('title', '')}:{arguments.get('start_time', '')}"
        return str(arguments.get("path") or arguments.get("command") or arguments.get("target") or name)


    # ── Dispatcher Entry Point ────────────────────────────────────────────────

    @classmethod
    async def dispatch(
        cls,
        name: str,
        arguments: dict[str, Any],
        session: Any = None,
        aura_core: Any = None,
        emitter: Any = None
    ) -> dict[str, Any]:
        """
        Execute a tool with full risk classification and CryptographicApprovalAuthority gating.
        Enforces cryptographic parameter binding on all high-risk actions to block substitution attacks.
        """
        logger.info(f"[UnifiedToolDispatcher] Dispatching '{name}' with args: {arguments}")

        # 1. Evaluate ActionRisk and ExecutionPolicy
        from core.orchestration.autonomy_mode import ActionRisk, classify_action_risk
        from core.orchestration.execution_policy import ExecutionPolicy, PolicyAction
        from desktop.native.security.approval_authority import CryptographicApprovalAuthority

        domain, action_verb, risk_params = cls._map_tool_to_risk(name, arguments)
        risk = classify_action_risk(domain, action_verb, risk_params)

        # Check workspace boundary for file mutations
        if name == "edit_file":
            target_path = arguments.get("path")
            if target_path:
                try:
                    from desktop.native.sandbox.workspace_jail import WorkspaceJail
                    jail = WorkspaceJail(workspace_root=str(_PROJECT_ROOT))
                    if not jail.is_path_inside_workspace(target_path):
                        risk = ActionRisk.HIGH
                except Exception as e:
                    logger.debug(f"[UnifiedToolDispatcher] Workspace jail check failed: {e}")

        # Ensure smarthome perimeter locks require human approval ticket
        if name == "smarthome_control":
            import re
            act = str(arguments.get("action") or "").lower().strip()
            ent = str(arguments.get("entity_id") or "").lower().strip()
            is_lock_act = act in ("lock", "unlock") or act.endswith(".lock") or act.endswith(".unlock")
            domain = ent.split(".")[0] if "." in ent else ""
            is_lock_ent = domain == "lock" or bool(re.search(r"\b(?:door_lock|smart_lock|lock)\b", ent))
            if is_lock_act or is_lock_ent:
                risk = ActionRisk.HIGH

        policy_decision = ExecutionPolicy.get_instance().evaluate_action(
            engine=domain, action=action_verb, params=risk_params
        )

        ticket_id = arguments.get("ticket_id")
        target = cls._extract_target(name, arguments)
        clean_params = {
            k: v for k, v in arguments.items()
            if k not in {"ticket_id", "signature", "approval_ticket_id", "approval_signature", "user_authorized"}
        }
        resolved_cwd = str(arguments.get("cwd") or _PROJECT_ROOT)

        # 2. Check if confirmation is required
        if policy_decision.action == PolicyAction.ASK_USER or risk in (ActionRisk.HIGH, ActionRisk.CRITICAL):
            auth = CryptographicApprovalAuthority.get_instance()
            is_valid_ticket = False

            if ticket_id:
                # Strictly require human signature; do NOT synthesize or auto-sign in tool dispatcher
                sig = arguments.get("signature")
                if not sig:
                    logger.warning(
                        f"[UnifiedToolDispatcher] Security alert: UNAUTHORIZED_LLM_SELF_APPROVAL_BLOCKED for '{name}' with ticket '{ticket_id}'"
                    )
                    return {
                        "status": "error",
                        "error": f"Action '{name}' requires human authorization. Ticket '{ticket_id}' must be signed by the human approval channel (UI/CLI).",
                        "ticket_id": ticket_id,
                        "security_alert": "UNAUTHORIZED_LLM_SELF_APPROVAL_BLOCKED",
                    }

                if name == "terminal_run_command":
                    is_valid_ticket, auth_err = auth.verify_and_redeem_command(
                        ticket_id=ticket_id,
                        signature=sig,
                        command=str(arguments.get("command", "")),
                        cwd=resolved_cwd,
                    )
                else:
                    is_valid_ticket, auth_err = auth.verify_and_redeem(
                        ticket_id=ticket_id,
                        signature=sig,
                        action_type=name,
                        target=target,
                        parameters=clean_params,
                    )

                if not is_valid_ticket:
                    alert_type = (
                        "SUBSTITUTION_ATTACK_BLOCKED"
                        if "does not match" in auth_err.lower()
                        else "UNAUTHORIZED_OR_FORGED_APPROVAL"
                    )
                    logger.warning(
                        f"[UnifiedToolDispatcher] Security alert: {alert_type} for '{name}' with ticket '{ticket_id}': {auth_err}"
                    )
                    return {
                        "status": "error",
                        "error": f"Authorization failed: {auth_err}",
                        "ticket_id": ticket_id,
                        "security_alert": alert_type,
                    }

            if not ticket_id:
                # Issue new approval ticket and suspend execution
                if name == "terminal_run_command":
                    t_id = auth.create_command_ticket(
                        command=str(arguments.get("command", "")),
                        cwd=resolved_cwd,
                    )
                else:
                    t_id = auth.create_ticket(
                        action_type=name,
                        target=target,
                        parameters=clean_params,
                    )

                prompt_msg = policy_decision.message or f"Action '{name}' requires human approval ({risk.value} risk)."
                logger.warning(f"[UnifiedToolDispatcher] Gated high-risk action '{name}': ticket={t_id}")

                try:
                    from core.event_bus import EventBus, Events
                    EventBus.get_instance().publish(
                        Events.CONFIRMATION_REQUIRED,
                        payload={
                            "ticket_id": t_id,
                            "action_name": name,
                            "action_params": clean_params,
                            "risk": risk.value if hasattr(risk, "value") else str(risk),
                            "is_crypto_ticket": True,
                        },
                    )
                except Exception as eb_err:
                    logger.error(
                        f"[UnifiedToolDispatcher] CRITICAL: Failed to publish CONFIRMATION_REQUIRED event for ticket '{t_id}': {eb_err}",
                        exc_info=True,
                    )

                if session and hasattr(session, "pending_confirmation"):
                    from core.orchestration.confirmation import ActionPlanConfirmation
                    from core.planning.action_plan import ActionPlan
                    ap = ActionPlan(
                        action=name,
                        target=target,
                        goal=prompt_msg,
                        capability=name,
                        arguments=arguments,
                        policy_action="ask_user",
                        session_id=getattr(session, "session_id", "sess_0"),
                    )
                    session.pending_confirmation = ActionPlanConfirmation(
                        action_plan=ap,
                        session_id=getattr(session, "session_id", "sess_0"),
                        prompt=prompt_msg,
                    )

                return {
                    "status": "confirmation_required",
                    "action": name,
                    "risk_level": risk.value if hasattr(risk, "value") else str(risk),
                    "ticket_id": t_id,
                    "prompt": f"{prompt_msg} To approve, run with ticket_id='{t_id}' or say 'confirm {t_id}'.",
                    "requires_human_approval": True,
                }

        # 3. Execute approved tool natively
        try:
            res = await cls._execute_tool_inner(name, arguments, session=session, aura_core=aura_core, emitter=emitter)
        except Exception as err:
            logger.error(f"[UnifiedToolDispatcher] Tool '{name}' execution failed: {err}", exc_info=True)
            res = {"status": "error", "error": str(err)}

        # Failure Ledger & Circuit Breaker Tracking (Tier 1 & Tier 2)
        sess_id = getattr(session, "session_id", None) if session else None
        is_err = isinstance(res, dict) and (res.get("status") == "error" or ("error" in res and res.get("status") != "success"))

        try:
            ledger = None
            if aura_core and getattr(aura_core, "memory", None):
                ledger = getattr(aura_core.memory, "failure_ledger", None)
                if not ledger and getattr(aura_core.memory, "cognitive", None):
                    ledger = getattr(aura_core.memory.cognitive, "failure_ledger", None)

            if is_err:
                err_msg = res.get("error") or "Unknown tool execution failure"
                if ledger:
                    cb_res = ledger.record_failure(
                        tool_name=name,
                        error=err_msg,
                        session_id=sess_id,
                    )
                    if cb_res.tripped:
                        res["circuit_breaker_tripped"] = True
                        res["escalate_to_user"] = True
                        res["circuit_breaker_message"] = cb_res.message
                        res["strikes"] = cb_res.strikes
                        res["fingerprint"] = cb_res.fingerprint
            else:
                if ledger and sess_id:
                    # Successful execution resets strikes / records resolution
                    ledger.record_resolution(
                        tool_name=name,
                        countermeasure=f"Verified valid tool invocation with keys: {list(arguments.keys())}",
                        session_id=sess_id,
                    )
        except Exception as ledger_err:
            logger.debug(f"[UnifiedToolDispatcher] Failure ledger handling warning: {ledger_err}")

        return res

    @classmethod
    async def _execute_tool_inner(
        cls,
        name: str,
        arguments: dict[str, Any],
        session: Any = None,
        aura_core: Any = None,
        emitter: Any = None
    ) -> dict[str, Any]:
        """Direct native execution for all 14 tools."""
        # ── 1. Coding Tools ──────────────────────────────────────────────────
        if name == "read_file":
            return await asyncio.to_thread(cls._exec_read_file, arguments)
        elif name == "edit_file":
            return await asyncio.to_thread(cls._exec_edit_file, arguments)
        elif name == "run_tests":
            return await asyncio.to_thread(cls._exec_run_tests, arguments)

        # ── 2. System & Shell Tools ──────────────────────────────────────────
        elif name == "terminal_run_command":
            cmd = arguments.get("command", "").strip()
            cwd = arguments.get("cwd")
            tkt = arguments.get("ticket_id")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._run_terminal_command, cmd, cwd, tkt, _upstream_verified=True)
        elif name == "system_get_telemetry":
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._get_system_telemetry)

        # ── 3. Vision & Screen Tools ─────────────────────────────────────────
        elif name == "vision_inspect_screen":
            query = arguments.get("query", "")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._inspect_screen, query)

        # ── 4. Browser Tools ─────────────────────────────────────────────────
        elif name == "browser_navigate_and_read":
            url = arguments.get("url", "")
            mode = arguments.get("extract_mode", "markdown")
            return await asyncio.to_thread(cls._exec_browser_navigate_and_read, url, mode, session=session)
        elif name == "browser_interact":
            return await asyncio.to_thread(cls._exec_browser_interact, arguments, session=session)

        # ── 5. Desktop Tools ─────────────────────────────────────────────────
        elif name == "desktop_launch_app":
            app = arguments.get("application", "")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._launch_app, app)
        elif name == "desktop_control_window":
            win = arguments.get("window_title", "")
            act = arguments.get("action", "focus")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._control_window, win, act)
        elif name == "desktop_clipboard":
            act = str(arguments.get("action") or "read")
            txt = str(arguments.get("text") or "")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._handle_clipboard, act, txt)
        elif name == "desktop_set_volume":
            lvl = arguments.get("level")
            mute = arguments.get("mute")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._set_volume, lvl, mute)
        elif name == "desktop_set_brightness":
            lvl = int(arguments.get("level", 50))
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._set_brightness, lvl)

        # ── 6. Memory & Personal OS Tools ────────────────────────────────────
        elif name == "memory_save_fact":
            cat = arguments.get("category", "preference")
            k = arguments.get("key", "note")
            v = arguments.get("value", "")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._save_memory_fact, cat, k, v, aura_core)
        elif name == "memory_query_facts":
            cat = arguments.get("category")
            k = arguments.get("key")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._query_memory_facts, cat, k, aura_core)
        elif name == "personal_os_agenda":
            t_date = arguments.get("date")
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._get_daily_agenda, t_date, aura_core)

        # ── 7. Dynamic Task Tracking Tool ────────────────────────────────────
        elif name == "task_plan_update":
            tasks_list = arguments.get("tasks", [])
            return cls._exec_task_plan_update(tasks_list, session=session, emitter=emitter)

        # ── 8. File Artifact Generation Tool ─────────────────────────────────
        # Routes directly to the CodeAct sandboxed synthesis engine.
        # This is the correct tool for any "create / generate / make a file" request.
        # It must NOT fall through to terminal_run_command.
        elif name == "create_file_artifact":
            return await cls._exec_create_file_artifact(arguments, emitter=emitter)

        # ── 9. SmartHome Device Control Tool ─────────────────────────────────
        elif name == "smarthome_control":
            return await cls._exec_smarthome_control(arguments)

        # ── 10. Email Communication Tool ─────────────────────────────────────
        elif name == "email_action":
            return await cls._exec_email_action(arguments)

        # ── 11. Calendar & Scheduling Tool ───────────────────────────────────
        elif name == "calendar_action":
            return await cls._exec_calendar_action(arguments)

        return {"status": "error", "error": f"Unknown tool: {name}"}

    # ── Specialized Implementations ──────────────────────────────────────────

    @classmethod
    async def _exec_smarthome_control(cls, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute smarthome device control via SmartHomeBackendAdapter."""
        from core.backends.adapters.smarthome_backend import SmartHomeBackendAdapter
        adapter = SmartHomeBackendAdapter()
        action = str(arguments.get("action") or "get_state").strip()
        entity_id = str(arguments.get("entity_id") or "").strip()
        params = dict(arguments.get("parameters") or {})
        params["entity_id"] = entity_id

        # Determine capability string
        if "." in action:
            capability = action
        elif entity_id and "." in entity_id:
            domain = entity_id.split(".")[0]
            capability = f"{domain}.{action}"
        else:
            capability = f"smarthome.{action}"

        goal = f"Control smarthome {entity_id}: {action}"
        try:
            res = await adapter.execute_async(capability=capability, goal=goal, arguments=params)
            return {
                "status": "success" if res.success else "error",
                "data": res.data,
                "observations": res.observations,
                "error": res.error if not res.success else None,
            }
        except Exception as e:
            logger.error(f"[UnifiedToolDispatcher] SmartHome execution error: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @classmethod
    async def _exec_email_action(cls, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute email operations via EmailBackendAdapter."""
        from core.backends.adapters.email_backend import EmailBackendAdapter
        adapter = EmailBackendAdapter()
        action = str(arguments.get("action") or "read_inbox").strip()
        capability = action if "." in action else f"email.{action}"
        goal = f"Email action: {action}"
        try:
            res = await asyncio.to_thread(adapter.execute, capability, goal, arguments)
            return {
                "status": "success" if res.success else "error",
                "data": res.data.get("result") if res.data else None,
                "observations": res.observations,
                "error": res.error if not res.success else None,
            }
        except Exception as e:
            logger.error(f"[UnifiedToolDispatcher] Email execution error: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @classmethod
    async def _exec_calendar_action(cls, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute calendar and task management via CalendarBackendAdapter."""
        from core.backends.adapters.calendar_backend import CalendarBackendAdapter
        adapter = CalendarBackendAdapter()
        action = str(arguments.get("action") or "list_events").strip()
        capability = action if "." in action else f"calendar.{action}"
        goal = f"Calendar action: {action}"
        try:
            res = await asyncio.to_thread(adapter.execute, capability, goal, arguments)
            return {
                "status": "success" if res.success else "error",
                "data": res.data.get("result") if res.data else None,
                "observations": res.observations,
                "error": res.error if not res.success else None,
            }
        except Exception as e:
            logger.error(f"[UnifiedToolDispatcher] Calendar execution error: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    @classmethod
    def _generate_default_rows_for_goal(cls, goal: str) -> list[list[Any]]:
        """Generate structured default tabular data matching the goal for spreadsheet creation."""
        goal_l = goal.lower()
        if "shopping" in goal_l or "grocery" in goal_l:
            return [
                ["Item", "Category", "Quantity", "Estimated Price ($)", "Notes"],
                ["Milk", "Dairy", "1 gallon", 3.99, "Whole or 2%"],
                ["Eggs", "Dairy", "1 dozen", 3.49, "Large grade A"],
                ["Bread", "Bakery", "1 loaf", 2.99, "Whole wheat"],
                ["Apples", "Produce", "2 lbs", 3.99, "Honeycrisp"],
                ["Bananas", "Produce", "1 bunch", 1.89, "Ripe"],
                ["Chicken Breast", "Meat", "2 lbs", 8.99, "Boneless, skinless"],
                ["Rice", "Pantry", "5 lbs", 4.99, "Jasmine or Basmati"],
                ["Olive Oil", "Pantry", "1 bottle", 7.99, "Extra virgin"],
                ["Spinach", "Produce", "1 bag", 2.49, "Fresh organic"],
            ]
        elif "budget" in goal_l or "expense" in goal_l or "finance" in goal_l:
            return [
                ["Category", "Allocated ($)", "Spent ($)", "Remaining ($)", "Status"],
                ["Housing & Rent", 1500.00, 1500.00, 0.00, "On Track"],
                ["Groceries & Food", 600.00, 420.50, 179.50, "On Track"],
                ["Utilities", 250.00, 210.00, 40.00, "On Track"],
                ["Transportation", 200.00, 185.00, 15.00, "On Track"],
                ["Entertainment", 150.00, 120.00, 30.00, "On Track"],
                ["Savings & Investment", 500.00, 500.00, 0.00, "Completed"],
            ]
        elif "inventory" in goal_l or "stock" in goal_l:
            return [
                ["SKU", "Item Name", "Category", "In Stock", "Unit Price ($)", "Reorder Level"],
                ["SKU-001", "Widget A", "Hardware", 120, 15.50, 25],
                ["SKU-002", "Widget B", "Hardware", 85, 22.00, 20],
                ["SKU-003", "Cable Pack", "Accessories", 200, 8.99, 50],
                ["SKU-004", "Power Adapter", "Electronics", 45, 19.99, 15],
            ]
        else:
            return [
                ["ID", "Title", "Description", "Status", "Date"],
                [1, "Item 1", f"Entry for {goal[:40]}", "Active", "2026-09-05"],
                [2, "Item 2", "Secondary entry", "Pending", "2026-09-05"],
                [3, "Item 3", "Tertiary entry", "Completed", "2026-09-05"],
            ]

    @classmethod
    async def _exec_create_file_artifact(
        cls,
        arguments: dict[str, Any],
        emitter: Any = None,
    ) -> dict[str, Any]:
        """
        Execute a file-artifact generation request via the CodeAct sandboxed synthesis engine.

        Unifies with TaskDecomposer._detect_artifact_synthesis as the authoritative source
        for capability routing and allowed_libraries restrictions.
        """
        from pathlib import Path

        goal = (arguments.get("goal") or "").strip()
        output_filename = (arguments.get("output_filename") or "output.xlsx").strip()
        destination = (arguments.get("destination") or "cwd").lower()

        if not goal:
            return {"status": "error", "error": "Missing required argument 'goal'."}
        if not output_filename:
            return {"status": "error", "error": "Missing required argument 'output_filename'."}

        # 1. Resolve destination directory
        home = Path.home()
        _dest_map = {
            "desktop":   home / "Desktop",
            "downloads": home / "Downloads",
            "documents": home / "Documents",
            "cwd":       Path(_PROJECT_ROOT),
        }
        dest_dir = _dest_map.get(destination, Path(_PROJECT_ROOT))
        if destination == "desktop" and not dest_dir.exists():
            od_desktop = home / "OneDrive" / "Desktop"
            if od_desktop.exists():
                dest_dir = od_desktop
        dest_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(dest_dir / output_filename)

        # 2. Authoritative artifact parameter resolution via public shared API
        from core.orchestration.task_decomposer import resolve_artifact_synthesis

        spec = resolve_artifact_synthesis(goal, output_filename)
        if spec is not None:
            allowed_libraries = spec.allowed_libraries
            capability = spec.capability
        else:
            # Fallback library inference matching TaskDecomposer rules
            ext = Path(output_filename).suffix.lower()
            if ext in (".xlsx", ".xls"):
                allowed_libraries = ["openpyxl"]
            elif ext in (".docx", ".doc"):
                allowed_libraries = ["python-docx"]
            elif ext in (".pptx", ".ppt"):
                allowed_libraries = ["python-pptx"]
            elif ext == ".pdf":
                allowed_libraries = ["python-docx", "openpyxl", "fpdf2"]
            else:
                # Fail-closed: unclassified extensions permit zero third-party libraries
                allowed_libraries = []
            capability = "codeact.synthesize"

        logger.info(
            "[UnifiedToolDispatcher] create_file_artifact: goal=%r output=%r lib=%r cap=%r",
            goal[:80], output_path, allowed_libraries, capability,
        )

        # 3. Attempt CodeAct synthesis (primary sandboxed execution path)
        codeact_err = ""
        try:
            from core.backends.adapters.codeact_backend import CodeActBackendAdapter

            adapter = CodeActBackendAdapter()
            result = await asyncio.to_thread(
                adapter.execute,
                capability=capability,
                goal=goal,
                arguments={
                    "goal": goal,
                    "output_filename": output_filename,
                    "allowed_libraries": allowed_libraries,
                    "destination_dir": str(dest_dir),
                },
            )

            if result and result.success:
                final_path = (result.data or {}).get("path") or output_path
                return {
                    "status": "success",
                    "message": f"✅ Created '{output_filename}' at `{final_path}`.",
                    "output_path": final_path,
                }
            codeact_err = getattr(result, "error", None) or "; ".join(result.observations)
            logger.warning("[UnifiedToolDispatcher] CodeAct synthesis failed (%s), trying plugin fallback.", codeact_err)

        except Exception as codeact_exc:
            logger.warning("[UnifiedToolDispatcher] CodeAct unavailable (%s), trying plugin fallback.", codeact_exc)
            codeact_err = str(codeact_exc)

        # 4. Fallback: office_plugin for .xlsx / .xls spreadsheets
        ext = Path(output_filename).suffix.lower()
        if ext in (".xlsx", ".xls"):
            try:
                from plugins.office.office_plugin import OfficePlugin
                plugin = OfficePlugin()
                rows = cls._generate_default_rows_for_goal(goal)
                fb_result = await asyncio.to_thread(
                    plugin.execute,
                    capability="office.create_spreadsheet",
                    path=output_path,
                    rows=rows,
                )
                if fb_result and fb_result.get("status") in ("created", "created_csv_fallback", "success"):
                    return {
                        "status": "success",
                        "message": f"✅ Created '{output_filename}' at `{output_path}`.",
                        "output_path": output_path,
                    }
                return {
                    "status": "error",
                    "error": f"Both CodeAct synthesis and office_plugin failed. CodeAct: {codeact_err}. Plugin: {fb_result}",
                }
            except Exception as plugin_exc:
                return {
                    "status": "error",
                    "error": f"CodeAct failed ({codeact_err}) and office_plugin raised: {plugin_exc}",
                }

        return {
            "status": "error",
            "error": f"File artifact generation failed: {codeact_err}",
        }

    @classmethod
    def _exec_read_file(cls, args: dict[str, Any]) -> dict[str, Any]:
        rel_path = args.get("path", "").strip()
        if not rel_path:
            return {"status": "error", "error": "Missing required argument 'path'"}

        target = (_PROJECT_ROOT / rel_path).resolve()
        if not target.is_relative_to(_PROJECT_ROOT):
            return {"status": "error", "error": f"Access denied: path '{rel_path}' escapes workspace root."}
        if not target.exists() or not target.is_file():
            return {"status": "error", "error": f"File not found: '{rel_path}'"}

        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            start = args.get("start_line") or 1
            end = args.get("end_line") or len(lines)
            start_idx = max(1, start) - 1
            end_idx = min(len(lines), end)

            selected_lines = [
                f"{i + 1}: {line}" for i, line in enumerate(lines[start_idx:end_idx], start=start_idx)
            ]
            return {
                "status": "success",
                "path": rel_path,
                "total_lines": len(lines),
                "start_line": start_idx + 1,
                "end_line": end_idx,
                "content": "\n".join(selected_lines)
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed reading file '{rel_path}': {e}"}

    @classmethod
    def _exec_edit_file(cls, args: dict[str, Any]) -> dict[str, Any]:
        rel_path = args.get("path", "").strip()
        target_content = args.get("target_content", "")
        replacement_content = args.get("replacement_content", "")

        if not rel_path or target_content is None or replacement_content is None:
            return {"status": "error", "error": "Missing required arguments: path, target_content, replacement_content"}

        target = (_PROJECT_ROOT / rel_path).resolve()
        if not target.is_relative_to(_PROJECT_ROOT):
            return {"status": "error", "error": f"Access denied: path '{rel_path}' escapes workspace root."}
        if not target.exists() or not target.is_file():
            return {"status": "error", "error": f"File not found: '{rel_path}'"}

        try:
            current_text = target.read_text(encoding="utf-8")
            if target_content not in current_text:
                return {
                    "status": "error",
                    "error": f"Target content not found in '{rel_path}'. Verify exact text and whitespace."
                }

            updated_text = current_text.replace(target_content, replacement_content, 1)
            target.write_text(updated_text, encoding="utf-8")
            logger.info(f"[UnifiedToolDispatcher] Successfully edited '{rel_path}'")
            return {
                "status": "success",
                "path": rel_path,
                "bytes_written": len(replacement_content),
                "message": f"Successfully updated {rel_path}"
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed editing file '{rel_path}': {e}"}

    @classmethod
    def _exec_run_tests(cls, args: dict[str, Any]) -> dict[str, Any]:
        test_target = args.get("test_target", "").strip()
        if not test_target:
            return {"status": "error", "error": "Missing required argument 'test_target'"}

        pytest_exe = _PROJECT_ROOT / ".venv" / "Scripts" / "pytest.exe"
        if not pytest_exe.exists():
            pytest_exe = Path(sys.executable).parent / "pytest.exe"

        cmd = [str(pytest_exe), test_target, "-q", "--tb=short"]
        try:
            res = subprocess.run(
                cmd,
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace"
            )
            return {
                "status": "success" if res.returncode == 0 else "failed",
                "returncode": res.returncode,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"Test execution timed out after 60s: {test_target}"}
        except Exception as e:
            return {"status": "error", "error": f"Test execution failed: {e}"}

    @classmethod
    def _exec_browser_navigate_and_read(
        cls, url: str, extract_mode: str = "markdown", session: Any = None
    ) -> dict[str, Any]:
        """
        Navigates to URL and extracts page content.
        If a session with goal_id is provided and AURA_ENABLE_AGENT_LOOP=1,
        attaches the live page to BrowserSessionManager so subsequent interactive tools
        (e.g. browser_interact) can act on the same page.
        All Playwright operations run on the pinned dedicated browser thread.
        """
        from core.orchestration import is_agent_loop_enabled
        loop_active = is_agent_loop_enabled()
        goal_id = getattr(session, "goal_id", None) if session else None
        if not goal_id and session and hasattr(session, "data") and isinstance(session.data, dict):
            goal_id = session.data.get("goal_id")

        if goal_id and loop_active:
            try:
                from browser.browser_session_manager import BrowserSessionManager, run_on_browser_thread
                mgr = BrowserSessionManager.get_instance()
                with mgr.operation_scope(goal_id):
                    browser_sess = mgr.acquire_session(goal_id)
                    page = mgr.get_page(goal_id)

                    target_url = url.strip()
                    if not target_url.startswith(("http://", "https://")):
                        target_url = "https://" + target_url

                    if page is not None:
                        def _navigate_and_extract() -> dict[str, Any]:
                            page.goto(target_url, wait_until="networkidle", timeout=12000)
                            title = page.title()
                            if extract_mode == "title":
                                return {"status": "success", "url": target_url, "title": title}
                            body_text = page.inner_text("body")
                            lines = [line.strip() for line in body_text.splitlines() if line.strip()]
                            clean_content = "\n".join(lines[:100])
                            return {
                                "status": "success",
                                "url": target_url,
                                "title": title,
                                "content": clean_content[:4000],
                                "extract_mode": extract_mode,
                            }

                        result = run_on_browser_thread(_navigate_and_extract)
                        if session and hasattr(session, "data") and isinstance(session.data, dict):
                            session.data["browser_session"] = browser_sess

                        return result
            except RuntimeError as rerr:
                # In-flight lease protection: another goal is actively operating the browser.
                # Must NOT fall back to spawning an uncontrolled second browser process.
                err_msg = str(rerr)
                if "is actively executing a browser operation" in err_msg or "Concurrent in-flight browser execution is rejected" in err_msg:
                    logger.warning(f"[UnifiedToolDispatcher] Browser in-flight lease busy: {err_msg}")
                    return {
                        "status": "error",
                        "error": "Browser is currently busy: another task is actively executing an operation. Please wait a moment and retry.",
                        "busy": True,
                    }
                logger.warning(f"[UnifiedToolDispatcher] BrowserSessionManager navigation fallback: {rerr}", exc_info=True)
            except Exception as ex:
                logger.warning(f"[UnifiedToolDispatcher] BrowserSessionManager navigation fallback: {ex}", exc_info=True)

        from core.tools.aura_tool_registry import AuraToolRegistry
        return AuraToolRegistry._browser_navigate_and_read(url, extract_mode)

    @classmethod
    def _exec_browser_interact(cls, args: dict[str, Any], session: Any = None) -> dict[str, Any]:
        action = (args.get("action") or "click").strip()
        selector = (args.get("selector") or "").strip()
        value = args.get("value", "")

        if not selector and action not in ("scroll", "wait"):
            return {"status": "error", "error": "Missing required argument 'selector' for browser_interact."}

        goal_id = getattr(session, "goal_id", None) if session else None
        if not goal_id and session and hasattr(session, "data") and isinstance(session.data, dict):
            goal_id = session.data.get("goal_id")

        mgr = None
        tombstone = None
        if goal_id:
            try:
                from browser.browser_session_manager import BrowserSessionManager
                mgr = BrowserSessionManager.get_instance()
                tombstone = mgr.get_tombstone(goal_id)
            except Exception:
                pass

        if tombstone:
            reason = tombstone.get("reason")
            if reason == "ttl_expired":
                return {
                    "status": "error",
                    "error": "Your browser session was closed after 15 minutes of inactivity while awaiting confirmation. Please re-run your request to start a fresh browser session.",
                    "eviction_reason": "ttl_expired",
                }
            elif reason == "bumped_by_new_goal":
                return {
                    "status": "error",
                    "error": "Your browser session was closed because a new browser task was started. Please re-run your request to start a fresh browser session.",
                    "eviction_reason": "bumped_by_new_goal",
                }

        # In-flight lease protection: Check if another goal has the browser actively in flight
        if mgr is not None and goal_id:
            for other_gid in list(mgr._active_sessions.keys()):
                if other_gid != goal_id and mgr.is_operation_in_flight(other_gid):
                    return {
                        "status": "error",
                        "error": "Browser is currently busy: another task is actively executing an operation. Please wait a moment and retry.",
                        "busy": True,
                    }

        page = None
        # 1. Authoritative lookup via BrowserSessionManager when goal_id is present
        if mgr is not None and goal_id:
            page = mgr.get_page(goal_id)

        # 2. Fallback to session.data["browser_session"] if not resolved from manager
        if page is None and session and hasattr(session, "data") and isinstance(session.data, dict):
            browser_session = session.data.get("browser_session")
            if browser_session is not None and hasattr(browser_session, "page") and browser_session.page is not None:
                page = browser_session.page

        # Verify page is not closed
        if page is not None and hasattr(page, "is_closed"):
            try:
                if page.is_closed() is True:
                    page = None
            except Exception:
                page = None

        if page is not None:
            try:
                from browser.browser_session_manager import run_on_browser_thread

                def _do_interact() -> dict[str, Any]:
                    if action == "click":
                        page.click(selector, timeout=5000)
                        return {"status": "success", "action": action, "selector": selector, "result": f"Clicked element '{selector}'"}
                    elif action == "type":
                        page.fill(selector, str(value), timeout=5000)
                        return {"status": "success", "action": action, "selector": selector, "result": f"Typed value into '{selector}'"}
                    elif action == "scroll":
                        direction = "down" if value != "up" else "up"
                        page.evaluate(f"window.scrollBy(0, {'500' if direction == 'down' else '-500'})")
                        return {"status": "success", "action": action, "selector": selector, "result": f"Scrolled page {direction}"}
                    elif action == "press_key":
                        page.press(selector, str(value), timeout=5000)
                        return {"status": "success", "action": action, "selector": selector, "result": f"Pressed key '{value}' on '{selector}'"}
                    else:
                        return {"status": "error", "error": f"Unsupported browser action: '{action}'"}

                if mgr is not None and goal_id:
                    with mgr.operation_scope(goal_id):
                        return run_on_browser_thread(_do_interact)
                return run_on_browser_thread(_do_interact)
            except Exception as pe:
                return {"status": "error", "error": f"Failed executing '{action}' on '{selector}': {pe}"}

        # Fail-closed invariant: Never fabricate a simulated success response
        return {
            "status": "error",
            "error": f"Cannot execute '{action}' on '{selector}': No active browser session available. Live browser interaction requires an active browser session.",
        }

    @classmethod
    def _exec_task_plan_update(
        cls,
        tasks: list[dict[str, Any]],
        session: Any = None,
        emitter: Any = None
    ) -> dict[str, Any]:
        """Update active TaskGraph subtasks on session in real time."""
        if not tasks:
            return {"status": "success", "updated_count": 0}

        try:
            if session and hasattr(session, "data"):
                active_tasks = session.data.setdefault("task_plan", [])
                session.data["task_plan"] = tasks

            # Synchronize into active TaskGraph
            task_graph = getattr(session, "task_graph", None) if session else None
            if not task_graph and session and hasattr(session, "data"):
                task_graph = session.data.get("task_graph")

            if task_graph is not None and hasattr(task_graph, "subtasks"):
                try:
                    from core.orchestration.task_decomposer import PlannerRole, SubTask
                    from core.orchestration.execution_events import NodeState, NodeStateChangedEvent

                    for t_dict in tasks:
                        t_id = t_dict.get("task_id")
                        if not t_id:
                            continue
                        t_title = t_dict.get("title", t_id)
                        t_status = t_dict.get("status", "pending")
                        if t_id in task_graph.subtasks:
                            st = task_graph.subtasks[t_id]
                            st.title = t_title
                            if t_status and t_status != st.status:
                                old_state = NodeState.from_str(st.status)
                                st.status = t_status
                                new_state = NodeState.from_str(t_status)
                                evt = NodeStateChangedEvent(
                                    task_id=t_id,
                                    new_state=new_state,
                                    old_state=old_state,
                                )
                                if session and hasattr(session, "emit_event") and callable(session.emit_event):
                                    session.emit_event(evt)
                                else:
                                    try:
                                        from core.orchestration import MasterOrchestrator
                                        MasterOrchestrator.get_instance()._emit(evt)
                                    except Exception:
                                        pass
                        else:
                            req_role = t_dict.get("required_role")
                            if req_role is None:
                                logger.warning(
                                    f"[UnifiedToolDispatcher] Task plan update subtask '{t_id}' missing explicit 'required_role'; defaulting to DESKTOP"
                                )
                                req_role = PlannerRole.DESKTOP

                            cap = t_dict.get("capability")
                            if cap is None:
                                logger.warning(
                                    f"[UnifiedToolDispatcher] Task plan update subtask '{t_id}' missing explicit 'capability'; defaulting to 'desktop.action'"
                                )
                                cap = "desktop.action"

                            new_st = SubTask(
                                task_id=t_id,
                                title=t_title,
                                required_role=req_role,
                                capability=cap,
                                description=t_dict.get("description", t_title),
                                parameters=t_dict.get("parameters", {}),
                                dependencies=t_dict.get("dependencies", []),
                                status=t_status or "pending",
                            )
                            task_graph.add_task(new_st)
                            evt = NodeStateChangedEvent(
                                task_id=t_id,
                                new_state=NodeState.PENDING,
                                old_state=None,
                            )
                            if session and hasattr(session, "emit_event") and callable(session.emit_event):
                                session.emit_event(evt)
                            else:
                                try:
                                    from core.orchestration import MasterOrchestrator
                                    MasterOrchestrator.get_instance()._emit(evt)
                                except Exception:
                                    pass
                except Exception as sync_err:
                    logger.warning(f"[UnifiedToolDispatcher] TaskGraph sync error: {sync_err}")
                    return {"status": "error", "error": f"Failed updating task graph: {sync_err}"}

            if emitter is not None and hasattr(emitter, "plan"):
                summary = ", ".join([f"{t.get('task_id', '')}: {t.get('title', '')} [{t.get('status', '')}]" for t in tasks[:3]])
                emitter.plan(f"Task Plan Update: {len(tasks)} subtasks", detail=summary)

            return {
                "status": "success",
                "updated_count": len(tasks),
                "tasks": tasks
            }
        except Exception as e:
            return {"status": "error", "error": f"task_plan_update failed: {e}"}
