"""
AuraAI Process Lifecycle & Graceful State Preservation Manager
==============================================================
Location: src/tools/restart_manager.py

Handles restarting AuraAI gracefully upon user voice or text command without
losing active tasks, scheduled routines, or session memory.
"""

import os
import sys
import json
import time
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
STATE_FILE = STORAGE_DIR / "restart_state.json"


class RestartManager:
    """Manages snapshotting active state and gracefully respawning AuraAI."""

    @classmethod
    def snapshot_state(cls, extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Snapshots current active tasks, triggers, and session metadata.

        Args:
            extra_data: Optional additional state dict to include.

        Returns:
            Dict representing the serialized state.
        """
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        state = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
            "argv": sys.argv,
            "executable": sys.executable,
            "cwd": str(PROJECT_ROOT),
            "running_tasks": [],
            "active_routines": [],
            "extra": extra_data or {},
        }

        # Try to pull active tasks from AuraCore if loaded
        try:
            from core.aura_core import AuraCore
            if hasattr(AuraCore, "_instance") and AuraCore._instance:
                core = AuraCore._instance
                if hasattr(core, "current_task") and core.current_task:
                    state["running_tasks"].append({"task": core.current_task, "status": str(core.current_task_status)})
                if hasattr(core, "conversation_history"):
                    state["recent_history"] = core.conversation_history[-5:]
        except Exception as e:
            logger.debug(f"[RestartManager] AuraCore snapshot note: {e}")

        # Try to pull active Personal OS triggers
        try:
            from personal_os.state_store import PersonalOSStateStore
            store = PersonalOSStateStore.get_instance(db_path=STORAGE_DIR / "personal_os.db")
            triggers = store.list_triggers(enabled_only=True)
            state["active_routines"] = [
                {"id": t.trigger_id, "goal": t.goal_text, "schedule": t.schedule}
                for t in triggers
            ]
        except Exception as e:
            logger.debug(f"[RestartManager] PersonalOS snapshot note: {e}")

        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            logger.info(f"[RestartManager] State successfully saved to {STATE_FILE}")
        except Exception as e:
            logger.error(f"[RestartManager] Failed to save restart state: {e}")

        return state

    @classmethod
    def load_and_restore_state(cls) -> Optional[Dict[str, Any]]:
        """
        Checks for previous restart recovery state and re-arms restored tasks.

        Returns:
            Dict containing restored state or None if no recovery file was present.
        """
        if not STATE_FILE.exists():
            return None

        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            logger.info(
                f"[RestartManager] Found recovery state from {state.get('iso_time')} "
                f"(Recovered {len(state.get('running_tasks', []))} active task(s), "
                f"{len(state.get('active_routines', []))} routine(s))."
            )

            # Clean up after reading
            try:
                STATE_FILE.unlink()
            except Exception:
                pass

            return state
        except Exception as e:
            logger.warning(f"[RestartManager] Failed to load recovery state: {e}")
            return None

    @classmethod
    def restart_aura(
        cls,
        delay_seconds: float = 1.0,
        extra_data: Optional[Dict[str, Any]] = None,
        target_cmd: Optional[list[str]] = None,
    ) -> str:
        """
        Initiates a graceful restart by saving state and respawning AuraAI.

        Args:
            delay_seconds: Seconds to wait before exiting (allows chat UI to send confirmation).
            extra_data: Optional extra state metadata.
            target_cmd: Optional explicit command list to launch.

        Returns:
            Confirmation message string.
        """
        logger.info("[RestartManager] Initiating AuraAI graceful restart sequence...")
        cls.snapshot_state(extra_data)

        def _do_spawn_and_exit():
            time.sleep(delay_seconds)
            try:
                # Spawn detached process on Windows
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200

                # Determine target command cleanly
                if target_cmd:
                    cmd = target_cmd
                else:
                    argv_str = " ".join(sys.argv)
                    if "run_voice_notch.py" in argv_str or "--notch" in argv_str or "notch" in sys.argv:
                        cmd = [sys.executable, str(PROJECT_ROOT / "run_voice_notch.py")]
                    elif "run_chat_window.py" in argv_str:
                        cmd = [sys.executable, str(PROJECT_ROOT / "run_chat_window.py")]
                    elif "run_gui.py" in argv_str:
                        cmd = [sys.executable, str(PROJECT_ROOT / "run_gui.py")]
                    elif "--gui" in sys.argv:
                        cmd = [sys.executable, str(PROJECT_ROOT / "main.py"), "--gui"]
                    elif "--cli" in sys.argv and "restart" not in sys.argv:
                        cmd = [sys.executable, str(PROJECT_ROOT / "main.py"), "--cli"]
                    elif "main.py" in argv_str:
                        cmd = [sys.executable, str(PROJECT_ROOT / "main.py")]
                    else:
                        cmd = [sys.executable, str(PROJECT_ROOT / "run_voice_notch.py")]

                logger.info(f"[RestartManager] Launching new instance: {' '.join(cmd)}")
                subprocess.Popen(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                    close_fds=True,
                )
            except Exception as e:
                logger.critical(f"[RestartManager] Process respawn failed: {e}", exc_info=True)
            finally:
                # Force clean exit of previous process
                logger.info("[RestartManager] Exiting old process.")
                os._exit(0)

        # Launch restart thread in background
        t = threading.Thread(target=_do_spawn_and_exit, daemon=True, name="AuraGracefulRestart")
        t.start()

        return (
            "🔄 **AuraAI Graceful Restart Initiated**\n\n"
            "• **State & Memory:** Saved to disk\n"
            "• **Active Tasks & Routines:** Preserved and scheduled for automatic recovery\n"
            "• **Respawning System:** Relaunching in 1 second..."
        )
