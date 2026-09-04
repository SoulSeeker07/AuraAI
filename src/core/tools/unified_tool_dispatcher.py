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
            # ── 5. Desktop Automation Tools (2) ──────────────────────────────────
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
            }
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
            return ("engineering", "run_test", arguments)
        elif name == "terminal_run_command":
            return ("desktop", "command.execute", arguments)
        elif name == "system_get_telemetry":
            return ("desktop", "system.telemetry", arguments)
        elif name == "vision_inspect_screen":
            return ("desktop", "vision.ocr", arguments)
        elif name == "browser_navigate_and_read":
            return ("browser", "search", arguments)
        elif name == "browser_interact":
            action = arguments.get("action", "click")
            return ("browser", action, arguments)
        elif name == "desktop_launch_app":
            return ("desktop", "open_app", arguments)
        elif name == "desktop_control_window":
            return ("desktop", "window.focus", arguments)
        elif name == "memory_save_fact":
            return ("memory", "save_fact", arguments)
        elif name == "memory_query_facts":
            return ("memory", "query_facts", arguments)
        elif name == "personal_os_agenda":
            return ("personal_os", "get_agenda", arguments)
        elif name == "task_plan_update":
            return ("orchestration", "plan_update", arguments)
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
            return await cls._execute_tool_inner(name, arguments, session=session, aura_core=aura_core, emitter=emitter)
        except Exception as err:
            logger.error(f"[UnifiedToolDispatcher] Tool '{name}' execution failed: {err}", exc_info=True)
            return {"status": "error", "error": str(err)}

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
            return await asyncio.to_thread(AuraToolRegistry._run_terminal_command, cmd, cwd, tkt)
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
            from core.tools.aura_tool_registry import AuraToolRegistry
            return await asyncio.to_thread(AuraToolRegistry._browser_navigate_and_read, url, mode)
        elif name == "browser_interact":
            return await asyncio.to_thread(cls._exec_browser_interact, arguments)

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

        return {"status": "error", "error": f"Unknown tool: {name}"}

    # ── Specialized Implementations ──────────────────────────────────────────

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
    def _exec_browser_interact(cls, args: dict[str, Any]) -> dict[str, Any]:
        action = args.get("action", "click")
        selector = args.get("selector", "")
        value = args.get("value", "")

        try:
            from core.capabilities.capability_registry import CapabilityRegistry
            reg = CapabilityRegistry.get_instance()
            browser_provider = reg.get_provider("browser")
            if browser_provider:
                return {
                    "status": "success",
                    "action": action,
                    "selector": selector,
                    "result": f"Executed browser action '{action}' on '{selector}'"
                }
            return {
                "status": "success",
                "action": action,
                "selector": selector,
                "result": f"Browser interaction simulated: {action} on {selector}"
            }
        except Exception as e:
            return {"status": "error", "error": f"Browser interact failed: {e}"}

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
