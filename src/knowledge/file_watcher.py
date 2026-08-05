"""
Knowledge File Watcher

Monitors directories for file changes and triggers re-indexing.
"""

import logging
import threading
from pathlib import Path
from typing import Any

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from .indexer import Indexer

logger = logging.getLogger(__name__)


class FileEventHandler(FileSystemEventHandler):
    """File system event handler for knowledge indexing."""

    def __init__(self, indexer: Indexer):
        """
        Initialize file event handler.

        Args:
            indexer: Indexer instance
        """
        self.indexer = indexer

    def on_created(self, event: FileCreatedEvent):
        """Handle file creation."""
        if not event.is_directory:
            file_path = event.src_path
            logger.info(f"File created: {file_path}")
            self.indexer.queue_indexing(file_path)

    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification."""
        if not event.is_directory:
            file_path = event.src_path
            logger.info(f"File modified: {file_path}")
            self.indexer.queue_indexing(file_path)

    def on_deleted(self, event: FileDeletedEvent):
        """Handle file deletion."""
        if not event.is_directory:
            file_path = event.src_path
            logger.info(f"File deleted: {file_path}")
            # Optionally, we could delete from knowledge store
            # self._remove_from_knowledge_store(file_path)


class KnowledgeFileWatcher:
    """
    Watches directories for file changes and triggers re-indexing.
    """

    def __init__(
        self, indexer: Indexer, directories: list[str], recursive: bool = True
    ):
        """
        Initialize file watcher.

        Args:
            indexer: Indexer instance
            directories: List of directories to watch
            recursive: Whether to recurse into subdirectories
        """
        self.indexer = indexer
        self.directories = [Path(d) for d in directories]
        self.recursive = recursive
        self.watched_files: set[Path] = set()
        self.exclude_patterns: list[str] = []
        self.file_hashes: dict[str, str] = {}

        self.observer: Observer | None = None
        self.is_running = False
        self.lock = threading.Lock()

        logger.info(
            f"Knowledge file watcher initialized for {len(directories)} directories"
        )

    def start(self):
        """Start watching directories."""
        if self.is_running:
            logger.warning("File watcher is already running")
            return

        # Clear watched files
        self.watched_files.clear()

        # Find files to watch
        for directory in self.directories:
            if directory.exists() and directory.is_dir():
                self._discover_files(directory)

        # Create and start observer
        self.observer = Observer()
        event_handler = FileEventHandler(self.indexer)
        self.observer.schedule(
            event_handler, str(directory.parent), recursive=self.recursive
        )

        self.observer.start()
        self.is_running = True

        logger.info(f"Started watching {len(self.watched_files)} files")

    def stop(self):
        """Stop watching directories."""
        if not self.is_running:
            return

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

        self.is_running = False
        logger.info("File watcher stopped")

    def add_directory(self, directory: str, recursive: bool = True):
        """
        Add a directory to watch.

        Args:
            directory: Directory path
            recursive: Whether to recurse into subdirectories
        """
        directory_path = Path(directory)

        if not directory_path.exists():
            logger.error(f"Directory does not exist: {directory}")
            return

        self.directories.append(directory_path)
        self._discover_files(directory_path, recursive=recursive)

        # Update observer schedule
        if self.observer and self.is_running:
            event_handler = FileEventHandler(self.indexer)
            self.observer.schedule(
                event_handler, str(directory_path.parent), recursive=recursive
            )

        logger.info(f"Added directory to watch: {directory}")

    def remove_directory(self, directory: str):
        """
        Remove a directory from watch.

        Args:
            directory: Directory path
        """
        directory_path = Path(directory)

        if directory_path in self.directories:
            self.directories.remove(directory_path)

            # Remove files from watch
            self.watched_files = {
                f
                for f in self.watched_files
                if not str(f).startswith(str(directory_path))
            }

            logger.info(f"Removed directory from watch: {directory}")

    def scan_and_queue_changes(self):
        """
        Scan directories for changes and queue re-indexing.

        This method compares current file states with tracked states.
        """
        logger.info("Scanning directories for changes...")

        current_files = set()

        for directory in self.directories:
            if directory.exists() and directory.is_dir():
                current_files.update(self._get_files_in_directory(directory))

        # Check for new files
        new_files = current_files - self.watched_files

        for file_path in new_files:
            try:
                self.indexer.queue_indexing(str(file_path))
            except Exception as e:
                logger.error(f"Error queuing new file {file_path}: {e}")

        # Check for modified files
        for file_path in self.watched_files:
            if file_path in current_files:
                # Check if file was modified (by comparing hashes)
                if self._is_file_modified(file_path):
                    try:
                        self.indexer.queue_indexing(str(file_path))
                    except Exception as e:
                        logger.error(f"Error queuing modified file {file_path}: {e}")

        # Update watched files
        self.watched_files = current_files

        logger.info(f"Scan complete. New/modified files: {len(new_files)}")

    def set_exclude_patterns(self, patterns: list[str]):
        """
        Set file exclusion patterns.

        Args:
            patterns: List of glob patterns to exclude
        """
        self.exclude_patterns = patterns
        logger.info(f"Set exclude patterns: {patterns}")

    def add_exclude_pattern(self, pattern: str):
        """
        Add a file exclusion pattern.

        Args:
            pattern: Glob pattern to exclude
        """
        if pattern not in self.exclude_patterns:
            self.exclude_patterns.append(pattern)
            logger.info(f"Added exclude pattern: {pattern}")

    def remove_exclude_pattern(self, pattern: str):
        """
        Remove a file exclusion pattern.

        Args:
            pattern: Glob pattern to remove
        """
        if pattern in self.exclude_patterns:
            self.exclude_patterns.remove(pattern)
            logger.info(f"Removed exclude pattern: {pattern}")

    def get_watched_files(self) -> list[str]:
        """
        Get list of watched files.

        Returns:
            List of file paths
        """
        with self.lock:
            return [str(f) for f in self.watched_files]

    def get_statistics(self) -> dict[str, Any]:
        """
        Get watcher statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "directories_watched": len(self.directories),
            "files_watched": len(self.watched_files),
            "is_running": self.is_running,
            "exclude_patterns": self.exclude_patterns,
        }

    def _discover_files(self, directory: Path, recursive: bool = True):
        """
        Discover files in directory.

        Args:
            directory: Directory path
            recursive: Whether to recurse into subdirectories
        """
        # Get files
        files = []

        if recursive:
            for ext in [".py", ".md", ".txt", ".json", ".yaml", ".yml", ".csv"]:
                files.extend(directory.rglob(f"*{ext}"))
        else:
            files.extend(directory.glob("*"))

        # Apply exclude patterns
        filtered_files = []

        for file_path in files:
            if file_path.is_file():
                # Check exclude patterns
                excluded = False
                for pattern in self.exclude_patterns:
                    if file_path.match(pattern):
                        excluded = True
                        break

                if not excluded:
                    filtered_files.append(file_path)

        # Update watched files
        self.watched_files.update(filtered_files)

    def _get_files_in_directory(self, directory: Path) -> set[Path]:
        """
        Get all files in directory.

        Args:
            directory: Directory path

        Returns:
            Set of file paths
        """
        files = set()

        if recursive:
            for ext in [".py", ".md", ".txt", ".json", ".yaml", ".yml", ".csv"]:
                files.update(directory.rglob(f"*{ext}"))
        else:
            files.update(directory.glob("*"))

        return files

    def _is_file_modified(self, file_path: Path) -> bool:
        """
        Check if file was modified by comparing hashes.

        Args:
            file_path: File path

        Returns:
            True if file was modified
        """
        try:
            file_hash = self._calculate_file_hash(file_path)

            if file_path not in self.file_hashes:
                self.file_hashes[str(file_path)] = file_hash
                return False

            if file_hash != self.file_hashes[str(file_path)]:
                self.file_hashes[str(file_path)] = file_hash
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking file modification {file_path}: {e}")
            return False

    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate file hash.

        Args:
            file_path: File path

        Returns:
            File hash
        """
        import hashlib

        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        return hasher.hexdigest()
