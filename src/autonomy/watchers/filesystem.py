"""
FilesystemWatcher Dumb Telemetry Producer (M24 Phase 5)
Location: src/autonomy/watchers/filesystem.py

Native OS filesystem monitor emitting raw AuraEvent telemetry into the EventRuntime.

Architectural Invariants:
1. Pure Dumb Sensor: Observes file changes and emits raw AuraEvent facts.
   NEVER evaluates importance, NEVER applies business rules, NEVER executes capabilities.
2. Robust & Isolated: Handles permission errors, rapid editor write bursts, and directory
   deletion without crashing the runtime or leaking background observer threads.
3. Clean Lifecycle: Clean start/stop/pause without duplicate event loops.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import threading
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..events import AuraEvent, EventSource, EventType
from ..event_runtime import EventRuntime

logger = logging.getLogger(__name__)


class _AuraFileSystemHandler(FileSystemEventHandler):
    """
    Internal Watchdog handler that converts raw OS filesystem events
    into standardized, immutable AuraEvent instances and feeds them to EventRuntime.
    """

    def __init__(self, runtime: EventRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        self._listeners: list[Any] = []
        self._listener_lock = threading.Lock()

    def register_listener(self, callback: Any) -> None:
        with self._listener_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def unregister_listener(self, callback: Any) -> None:
        with self._listener_lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _notify_listeners(self, event_type: str, path_str: str) -> None:
        with self._listener_lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(event_type, path_str)
            except Exception as e:
                logger.warning(f"[FilesystemWatcher] Listener callback warning: {e}")

    def _normalize_path(self, path_str: str) -> str:
        try:
            return os.path.normpath(str(path_str))
        except Exception:
            return str(path_str)

    def on_created(self, event: FileSystemEvent) -> None:
        try:
            norm_path = self._normalize_path(event.src_path)
            size_bytes = 0
            if not event.is_directory:
                try:
                    size_bytes = os.path.getsize(norm_path)
                except Exception:
                    size_bytes = 0

            aura_event = AuraEvent.create(
                event_type=EventType.FILESYSTEM_CREATED,
                source=EventSource.FILESYSTEM,
                payload={
                    "path": norm_path,
                    "is_directory": event.is_directory,
                    "size_bytes": size_bytes,
                    "operation": "created",
                },
            )
            self.runtime.ingest(aura_event)
            self._notify_listeners("created", norm_path)
        except Exception as e:
            logger.debug(f"[FilesystemWatcher] Error processing creation event for {event.src_path}: {e}")

    def on_modified(self, event: FileSystemEvent) -> None:
        try:
            norm_path = self._normalize_path(event.src_path)
            size_bytes = 0
            if not event.is_directory:
                try:
                    size_bytes = os.path.getsize(norm_path)
                except Exception:
                    size_bytes = 0

            aura_event = AuraEvent.create(
                event_type=EventType.FILESYSTEM_MODIFIED,
                source=EventSource.FILESYSTEM,
                payload={
                    "path": norm_path,
                    "is_directory": event.is_directory,
                    "size_bytes": size_bytes,
                    "operation": "modified",
                },
            )
            self.runtime.ingest(aura_event)
            self._notify_listeners("modified", norm_path)
        except Exception as e:
            logger.debug(f"[FilesystemWatcher] Error processing modification event for {event.src_path}: {e}")

    def on_deleted(self, event: FileSystemEvent) -> None:
        try:
            norm_path = self._normalize_path(event.src_path)
            aura_event = AuraEvent.create(
                event_type=EventType.FILESYSTEM_DELETED,
                source=EventSource.FILESYSTEM,
                payload={
                    "path": norm_path,
                    "is_directory": event.is_directory,
                    "operation": "deleted",
                },
            )
            self.runtime.ingest(aura_event)
            self._notify_listeners("deleted", norm_path)
        except Exception as e:
            logger.debug(f"[FilesystemWatcher] Error processing deletion event for {event.src_path}: {e}")

    def on_moved(self, event: FileSystemEvent) -> None:
        try:
            src_norm = self._normalize_path(event.src_path)
            dest_norm = self._normalize_path(getattr(event, "dest_path", event.src_path))
            aura_event = AuraEvent.create(
                event_type=EventType.FILESYSTEM_MOVED,
                source=EventSource.FILESYSTEM,
                payload={
                    "src_path": src_norm,
                    "dest_path": dest_norm,
                    "path": dest_norm,
                    "is_directory": event.is_directory,
                    "operation": "moved",
                },
            )
            self.runtime.ingest(aura_event)
            self._notify_listeners("moved", dest_norm)
        except Exception as e:
            logger.debug(f"[FilesystemWatcher] Error processing move event for {event.src_path}: {e}")


class FilesystemWatcher:
    """
    Physical Filesystem Telemetry Producer.
    Maintains native OS directory watchers and emits raw AuraEvents into EventRuntime.
    """

    def __init__(
        self,
        runtime: EventRuntime,
        watch_paths: list[str | Path] | None = None,
        recursive: bool = True,
    ) -> None:
        self.runtime = runtime
        self.recursive = recursive
        self._handler = _AuraFileSystemHandler(runtime)
        self._observer: Observer | None = None
        self._watched_paths: dict[str, Any] = {}  # norm_path -> ObservedWatch
        self._lock = threading.Lock()
        self._is_running = False

        if watch_paths:
            for p in watch_paths:
                self.add_watch(p, recursive=recursive)

    def register_listener(self, callback: Any) -> None:
        """Register a direct callback receiving (event_type: str, path: str)."""
        self._handler.register_listener(callback)

    def unregister_listener(self, callback: Any) -> None:
        """Unregister a direct callback."""
        self._handler.unregister_listener(callback)

    def add_watch(self, path: str | Path, recursive: bool | None = None) -> bool:
        """
        Adds a target directory or file to the active filesystem monitor.
        Returns True if watch was successfully scheduled, False otherwise.
        """
        norm_path = os.path.normpath(str(path))
        is_rec = recursive if recursive is not None else self.recursive

        if not os.path.exists(norm_path):
            logger.warning(f"[FilesystemWatcher] Cannot watch non-existent path: '{norm_path}'")
            return False

        with self._lock:
            if norm_path in self._watched_paths:
                return True

            if self._observer and self._is_running:
                try:
                    watch = self._observer.schedule(self._handler, norm_path, recursive=is_rec)
                    self._watched_paths[norm_path] = watch
                    logger.info(f"[FilesystemWatcher] Scheduled active watch on '{norm_path}' (recursive={is_rec})")
                    return True
                except Exception as e:
                    logger.error(f"[FilesystemWatcher] Failed to schedule watch on '{norm_path}': {e}")
                    return False
            else:
                # Store path for scheduling upon start()
                self._watched_paths[norm_path] = None
                return True

    def remove_watch(self, path: str | Path) -> bool:
        """Removes a path from active monitoring."""
        norm_path = os.path.normpath(str(path))
        with self._lock:
            if norm_path not in self._watched_paths:
                return False

            watch = self._watched_paths.pop(norm_path, None)
            if watch and self._observer and self._is_running:
                try:
                    self._observer.unschedule(watch)
                    logger.info(f"[FilesystemWatcher] Unscheduled watch on '{norm_path}'")
                except Exception as e:
                    logger.debug(f"[FilesystemWatcher] Unschedule error for '{norm_path}': {e}")
            return True

    def list_watches(self) -> list[str]:
        """Returns list of currently watched normalized paths."""
        with self._lock:
            return list(self._watched_paths.keys())

    def start(self) -> None:
        """Starts the background native OS observer thread."""
        with self._lock:
            if self._is_running:
                return

            self._observer = Observer()
            for path_str in list(self._watched_paths.keys()):
                if os.path.exists(path_str):
                    try:
                        watch = self._observer.schedule(self._handler, path_str, recursive=self.recursive)
                        self._watched_paths[path_str] = watch
                    except Exception as e:
                        logger.error(f"[FilesystemWatcher] Error scheduling watch on {path_str}: {e}")

            self._observer.start()
            self._is_running = True
            logger.info("[FilesystemWatcher] Started physical native filesystem observer.")

    def stop(self, timeout: float = 2.0) -> None:
        """Stops the native filesystem observer cleanly."""
        with self._lock:
            if not self._is_running or self._observer is None:
                return

            self._observer.stop()
            self._observer.join(timeout=timeout)
            self._observer = None
            self._is_running = False
            logger.info("[FilesystemWatcher] Stopped physical native filesystem observer.")

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running and self._observer is not None and self._observer.is_alive()
