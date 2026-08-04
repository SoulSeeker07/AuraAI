"""
Trigger Manager

Manages workflow triggers: manual, scheduled, event, workspace, voice, plugin.
"""


import logging
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING
from datetime import datetime, timedelta
import threading
import json
import os

from .models import WorkflowTriggerType

# Avoid circular import - use TYPE_CHECKING for type hints only
if TYPE_CHECKING:
    from .workflow_engine import WorkflowEngine


logger = logging.getLogger(__name__)


class TriggerManager:
    """
    Manages workflow triggers and schedules.
    """

    def __init__(
        self,
        on_trigger_fire: Callable[[str, Dict[str, Any]], None],
        agent_runtime=None
    ):
        """
        Initialize trigger manager.

        Args:
            on_trigger_fire: Callback when trigger fires
            agent_runtime: Agent Runtime instance
        """
        self.on_trigger_fire = on_trigger_fire
        self.agent_runtime = agent_runtime

        # Schedules: workflow_id -> (schedule, last_run)
        self.schedules: Dict[str, Dict[str, Any]] = {}

        # Event handlers: event_name -> [workflow_ids]
        self.event_handlers: Dict[str, List[str]] = {}

        # Workspace watchers: [workflow_ids]
        self.workspace_watchers: List[str] = []

        # Voice trigger listener (placeholder)
        self.voice_listener_active = False

        # Plugin triggers (placeholder)
        self.plugin_triggers: Dict[str, List[str]] = {}  # plugin_id -> [workflow_ids]

        # Scheduler thread
        self.scheduler_running = False
        self.scheduler_thread: Optional[threading.Thread] = None

        # Load saved schedules
        self._load_schedules()

        logger.info("Trigger Manager initialized")

    def add_schedule(
        self,
        workflow_id: str,
        schedule: str,
        timezone: str = "UTC"
    ) -> bool:
        """
        Add scheduled trigger for workflow.

        Args:
            workflow_id: Workflow ID
            schedule: Cron-style schedule
            timezone: Timezone

        Returns:
            Success
        """
        if workflow_id not in self.schedules:
            self.schedules[workflow_id] = {
                'schedule': schedule,
                'timezone': timezone,
                'last_run': None,
                'next_run': self._calculate_next_run(schedule, timezone)
            }
            logger.info(f"Added schedule for workflow {workflow_id[:8]}: {schedule}")
            return True
        return False

    def remove_schedule(self, workflow_id: str) -> bool:
        """
        Remove schedule for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id in self.schedules:
            del self.schedules[workflow_id]
            logger.info(f"Removed schedule for workflow {workflow_id[:8]}")
            return True
        return False

    def add_event_handler(self, event_name: str, workflow_id: str) -> bool:
        """
        Add event handler for workflow.

        Args:
            event_name: Event name
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []

        if workflow_id not in self.event_handlers[event_name]:
            self.event_handlers[event_name].append(workflow_id)

        logger.info(f"Added event handler for {event_name} in workflow {workflow_id[:8]}")
        return True

    def remove_event_handler(self, event_name: str, workflow_id: str) -> bool:
        """
        Remove event handler for workflow.

        Args:
            event_name: Event name
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if event_name in self.event_handlers and workflow_id in self.event_handlers[event_name]:
            self.event_handlers[event_name].remove(workflow_id)

            if not self.event_handlers[event_name]:
                del self.event_handlers[event_name]

            logger.info(f"Removed event handler for {event_name} in workflow {workflow_id[:8]}")
            return True
        return False

    def add_workspace_watcher(self, workflow_id: str) -> bool:
        """
        Add workspace watcher for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.workspace_watchers:
            self.workspace_watchers.append(workflow_id)
            logger.info(f"Added workspace watcher for workflow {workflow_id[:8]}")

            # Start workspace watcher if not already running
            self._start_workspace_watcher()
            return True
        return False

    def remove_workspace_watcher(self, workflow_id: str) -> bool:
        """
        Remove workspace watcher for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id in self.workspace_watchers:
            self.workspace_watchers.remove(workflow_id)
            logger.info(f"Removed workspace watcher for workflow {workflow_id[:8]}")
            return True
        return False

    def start(self):
        """Start trigger manager."""
        if not self.scheduler_running:
            self.scheduler_running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()

            # Start workspace watcher
            self._start_workspace_watcher()

            # Start voice listener
            self._start_voice_listener()

            logger.info("Trigger Manager started")

    def stop(self):
        """Stop trigger manager."""
        self.scheduler_running = False

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)

        logger.info("Trigger Manager stopped")

    def fire_event(self, event_name: str, data: Optional[Dict[str, Any]] = None):
        """
        Fire an event.

        Args:
            event_name: Event name
            data: Event data
        """
        logger.info(f"Event fired: {event_name}")

        # Fire for event handlers
        if event_name in self.event_handlers:
            for workflow_id in self.event_handlers[event_name]:
                self._on_trigger_fire(workflow_id, data or {})

        # Fire for plugin triggers
        for plugin_id in self.plugin_triggers.get(event_name, []):
            self._on_trigger_fire(plugin_id, data or {})

    def enable_voice_trigger(self, workflow_id: str) -> bool:
        """
        Enable voice trigger for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id not in self.schedules:
            self.schedules[workflow_id] = {
                'schedule': 'voice',
                'timezone': 'user',
                'last_run': None,
                'next_run': None
            }

        self.voice_listener_active = True
        logger.info(f"Enabled voice trigger for workflow {workflow_id[:8]}")
        return True

    def disable_voice_trigger(self, workflow_id: str) -> bool:
        """
        Disable voice trigger for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if workflow_id in self.schedules:
            del self.schedules[workflow_id]

        logger.info(f"Disabled voice trigger for workflow {workflow_id[:8]}")
        return True

    def enable_plugin_trigger(self, plugin_id: str, workflow_id: str) -> bool:
        """
        Enable plugin trigger for workflow.

        Args:
            plugin_id: Plugin ID
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if plugin_id not in self.plugin_triggers:
            self.plugin_triggers[plugin_id] = []

        if workflow_id not in self.plugin_triggers[plugin_id]:
            self.plugin_triggers[plugin_id].append(workflow_id)

        logger.info(f"Enabled plugin trigger {plugin_id} for workflow {workflow_id[:8]}")
        return True

    def disable_plugin_trigger(self, plugin_id: str, workflow_id: str) -> bool:
        """
        Disable plugin trigger for workflow.

        Args:
            plugin_id: Plugin ID
            workflow_id: Workflow ID

        Returns:
            Success
        """
        if plugin_id in self.plugin_triggers and workflow_id in self.plugin_triggers[plugin_id]:
            self.plugin_triggers[plugin_id].remove(workflow_id)

            if not self.plugin_triggers[plugin_id]:
                del self.plugin_triggers[plugin_id]

            logger.info(f"Disabled plugin trigger {plugin_id} for workflow {workflow_id[:8]}")
            return True
        return False

    def _scheduler_loop(self):
        """Main scheduler loop."""
        logger.info("Scheduler loop started")

        while self.scheduler_running:
            now = datetime.now()

            for workflow_id, schedule_data in self.schedules.items():
                schedule = schedule_data['schedule']

                # Check if it's time to run
                if self._is_time_to_run(schedule, now, schedule_data):
                    # Check if enabled
                    if not schedule_data.get('enabled', True):
                        continue

                    # Update last run
                    schedule_data['last_run'] = now.isoformat()

                    # Fire trigger
                    self._on_trigger_fire(workflow_id, {
                        'trigger': 'scheduled',
                        'schedule': schedule
                    })

                    # Save schedule
                    self._save_schedules()

            # Sleep for 1 second
            time.sleep(1)

    def _start_workspace_watcher(self):
        """Start workspace watcher thread."""
        if hasattr(self, '_workspace_watcher_thread') and self._workspace_watcher_thread and self._workspace_watcher_thread.is_alive():
            return

        self._workspace_watcher_thread = threading.Thread(target=self._workspace_watcher_loop, daemon=True)
        self._workspace_watcher_thread.start()
        logger.info("Workspace watcher started")

    def _workspace_watcher_loop(self):
        """Main workspace watcher loop."""
        import os
        import time

        watched_dirs = set()
        last_modified = {}

        while self.scheduler_running:
            try:
                # Watch each workflow's workspace
                for workflow_id in self.workspace_watchers:
                    workspace = self.schedules.get(workflow_id, {}).get('workspace_path', '')

                    if workspace and os.path.exists(workspace):
                        for dirpath, dirnames, filenames in os.walk(workspace):
                            for filename in filenames:
                                filepath = os.path.join(dirpath, filename)
                                mtime = os.path.getmtime(filepath)

                                key = f"{workflow_id}:{filepath}"

                                if key not in last_modified:
                                    last_modified[key] = mtime
                                elif last_modified[key] < mtime:
                                    # File was modified
                                    logger.info(f"File modified: {filepath}")

                                    self._on_trigger_fire(workflow_id, {
                                        'trigger': 'workspace',
                                        'event': 'file_modified',
                                        'filepath': filepath
                                    })

                                    last_modified[key] = mtime

            except Exception as e:
                logger.error(f"Workspace watcher error: {e}")

            time.sleep(5)

    def _start_voice_listener(self):
        """Start voice listener (placeholder)."""
        logger.info("Voice listener started")

    def _on_trigger_fire(self, workflow_id: str, trigger_data: Dict[str, Any]):
        """
        Callback when trigger fires.

        Args:
            workflow_id: Workflow ID
            trigger_data: Trigger data
        """
        if self.on_trigger_fire:
            self.on_trigger_fire(workflow_id, trigger_data)

    def _is_time_to_run(self, schedule: str, now: datetime, schedule_data: Dict[str, Any]) -> bool:
        """
        Check if it's time to run.

        Args:
            schedule: Schedule string
            now: Current datetime
            schedule_data: Schedule data

        Returns:
            True if time to run
        """
        last_run = schedule_data.get('last_run')

        if not last_run:
            return True

        # Simple check for daily schedules
        if 'daily' in schedule:
            return now.time() >= self._parse_time(schedule)
        elif 'hourly' in schedule:
            return now.minute == 0

        return False

    def _calculate_next_run(self, schedule: str, timezone: str) -> datetime:
        """
        Calculate next run time.

        Args:
            schedule: Schedule string
            timezone: Timezone

        Returns:
            Next run datetime
        """
        now = datetime.now()

        if 'daily' in schedule:
            time = self._parse_time(schedule)
            return now.replace(hour=time.hour, minute=time.minute, second=0, microsecond=0)
        elif 'hourly' in schedule:
            return now.replace(minute=0, second=0, microsecond=0)

        return now

    def _parse_time(self, schedule: str) -> datetime:
        """
        Parse time from schedule.

        Args:
            schedule: Schedule string

        Returns:
            Time datetime
        """
        # Simple format: "HH:MM"
        parts = schedule.split(':')
        hour = int(parts[0])
        minute = int(parts[1])

        return datetime.now().replace(hour=hour, minute=minute)

    def _save_schedules(self):
        """Save schedules to file."""
        try:
            schedule_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'schedules.json')
            os.makedirs(os.path.dirname(schedule_file), exist_ok=True)

            data = {
                'schedules': self.schedules,
                'event_handlers': self.event_handlers,
                'workspace_watchers': self.workspace_watchers,
                'plugin_triggers': self.plugin_triggers
            }

            with open(schedule_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")

    def _load_schedules(self):
        """Load schedules from file."""
        try:
            schedule_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'schedules.json')

            if os.path.exists(schedule_file):
                with open(schedule_file, 'r') as f:
                    data = json.load(f)

                self.schedules = data.get('schedules', {})
                self.event_handlers = data.get('event_handlers', {})
                self.workspace_watchers = data.get('workspace_watchers', [])
                self.plugin_triggers = data.get('plugin_triggers', {})

                logger.info(f"Loaded {len(self.schedules)} schedules from file")
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")

    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all schedules.

        Returns:
            Schedules dictionary
        """
        return self.schedules.copy()
