# -*- coding: utf-8 -*-
"""
disk_cleaner.py
----------------
A cross‑platform temporary‑file and junk‑disk analyzer with a PySide6 GUI.
Features
~~~~~~~~
* Scans common temporary directories (system & user) and reports total size.
* Shows each discovered file/folder in a tree view with check‑boxes.
* Allows selective or full cleanup.
* Runs the scan in a background thread to keep the UI responsive.
* Provides progress feedback and robust error handling.

Author: Aura Autonomous Engineering Platform
"""

from __future__ import annotations

import os
import sys
import shutil
import traceback
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    QObject,
    QCoreApplication,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeView,
    QMessageBox,
    QProgressBar,
    QLabel,
    QCheckBox,
    QFileIconProvider,
)


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def human_readable_size(num_bytes: int) -> str:
    """Convert a byte count into a human‑readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def get_temp_paths() -> List[Path]:
    """
    Return a list of platform‑specific temporary directories to analyse.
    The list is deduplicated and filtered for existence.
    """
    candidates: List[Path] = []

    # Environment variables (Windows, Linux, macOS)
    for var in ("TMP", "TEMP", "TMPDIR"):
        val = os.getenv(var)
        if val:
            candidates.append(Path(val).expanduser())

    # Common user temp locations
    home = Path.home()
    if sys.platform.startswith("win"):
        candidates.append(home / "AppData" / "Local" / "Temp")
        candidates.append(Path(os.getenv("SystemRoot", "C:\\Windows")) / "Temp")
    else:
        candidates.append(Path("/tmp"))
        candidates.append(Path("/var/tmp"))

    # Remove duplicates and non‑existent paths
    unique_paths = []
    for p in candidates:
        try:
            p = p.resolve(strict=True)
        except FileNotFoundError:
            continue
        if p not in unique_paths:
            unique_paths.append(p)

    return unique_paths


def calculate_directory_size(root: Path) -> int:
    """Recursively calculate the total size of a directory (in bytes)."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        for f in filenames:
            try:
                fp = Path(dirpath) / f
                total += fp.stat().st_size
            except (OSError, PermissionError):
                continue
    return total


# --------------------------------------------------------------------------- #
# Worker thread for scanning
# --------------------------------------------------------------------------- #
class ScanWorker(QObject):
    """
    Worker object that runs in a separate QThread to avoid blocking the UI.
    Emits progress updates and a final result list.
    """
    progress = Signal(int)               # percent (0‑100)
    finished = Signal(list)              # List[Tuple[Path, int]]
    error = Signal(str)                  # error message

    def __init__(self, paths: List[Path]) -> None:
        super().__init__()
        self._paths = paths
        self._is_interrupted = False

    def interrupt(self) -> None:
        """Request early termination of the scan."""
        self._is_interrupted = True

    def run(self) -> None:
        """Perform the scan."""
        try:
            results: List[Tuple[Path, int]] = []
            total_paths = len(self._paths)
            for idx, p in enumerate(self._paths, start=1):
                if self._is_interrupted:
                    break
                size = calculate_directory_size(p)
                results.append((p, size))
                percent = int((idx / total_paths) * 100)
                self.progress.emit(percent)
            self.finished.emit(results)
        except Exception as exc:
            tb = traceback.format_exc()
            self.error.emit(f"{exc}\n{tb}")


# --------------------------------------------------------------------------- #
# Main GUI widget
# --------------------------------------------------------------------------- #
class DiskCleaner(QWidget):
    """Main application window for the disk‑cleanup tool."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aura Disk Cleaner")
        self.setMinimumSize(720, 480)
        self._setup_ui()
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None

    # ------------------------------------------------------------------- #
    # UI construction
    # ------------------------------------------------------------------- #
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header / status
        self.status_label = QLabel("Press **Scan** to analyse temporary files.")
        layout.addWidget(self.status_label)

        # Tree view for results
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Location", "Size"])
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(self.tree.SelectionMode.ExtendedSelection)
        self.tree.setEditTriggers(self.tree.EditTrigger.NoEditTriggers)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeMode.ResizeToContents)
        layout.addWidget(self.tree)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Buttons
        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self.start_scan)
        btn_layout.addWidget(self.scan_btn)

        self.clean_selected_btn = QPushButton("Clean Selected")
        self.clean_selected_btn.clicked.connect(self.clean_selected)
        self.clean_selected_btn.setEnabled(False)
        btn_layout.addWidget(self.clean_selected_btn)

        self.clean_all_btn = QPushButton("Clean All")
        self.clean_all_btn.clicked.connect(self.clean_all)
        self.clean_all_btn.setEnabled(False)
        btn_layout.addWidget(self.clean_all_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh_btn.setEnabled(False)
        btn_layout.addWidget(self.refresh_btn)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------- #
    # Scan handling
    # ------------------------------------------------------------------- #
    def start_scan(self) -> None:
        """Kick off a background scan of temporary directories."""
        self.scan_btn.setEnabled(False)
        self.status_label.setText("Scanning temporary locations...")
        self.model.removeRows(0, self.model.rowCount())
        self.progress.setValue(0)

        temp_paths = get_temp_paths()
        if not temp_paths:
            QMessageBox.warning(self, "No Temp Paths", "No temporary directories were found on this system.")
            self.scan_btn.setEnabled(True)
            self.status_label.setText("Ready.")
            return

        # Set up worker thread
        self._thread = QThread()
        self._worker = ScanWorker(temp_paths)
        self._worker.moveToThread(self._thread)

        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_scan_finished(self, results: List[Tuple[Path, int]]) -> None:
        """Populate the tree view with scan results."""
        icon_provider = QFileIconProvider()
        total_size = 0

        for path, size in results:
            total_size += size
            folder_item = QStandardItem(icon_provider.icon(QFileIconProvider.Folder), str(path))
            folder_item.setCheckable(True)
            folder_item.setCheckState(Qt.Checked)

            size_item = QStandardItem(human_readable_size(size))
            size_item.setEditable(False)

            self.model.appendRow([folder_item, size_item])

        self.status_label.setText(
            f"Scan complete – {len(results)} locations found, total size {human_readable_size(total_size)}."
        )
        self.scan_btn.setEnabled(True)
        self.clean_selected_btn.setEnabled(True)
        self.clean_all_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)

    def _on_scan_error(self, message: str) -> None:
        QMessageBox.critical(self, "Scan Error", f"An error occurred while scanning:\n{message}")
        self.scan_btn.setEnabled(True)
        self.status_label.setText("Ready.")

    # ------------------------------------------------------------------- #
    # Cleanup handling
    # ------------------------------------------------------------------- #
    def _delete_path(self, path: Path) -> Tuple[bool, str]:
        """Attempt to delete a file or directory. Returns (success, message)."""
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def clean_selected(self) -> None:
        """Delete only the items that are checked."""
        checked_items = self._gather_checked_items()
        if not checked_items:
            QMessageBox.information(self, "Nothing Selected", "No locations are selected for cleanup.")
            return

        self._perform_cleanup(checked_items, "selected items")

    def clean_all(self) -> None:
        """Delete every scanned temporary location."""
        all_items = self._gather_all_items()
        if not all_items:
            QMessageBox.information(self, "No Items", "There are no items to clean.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Full Cleanup",
            "Are you sure you want to delete **all** temporary files listed?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._perform_cleanup(all_items, "all items")

    def _gather_checked_items(self) -> List[Path]:
        """Return a list of Paths whose top‑level rows are checked."""
        paths: List[Path] = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            if item.checkState() == Qt.Checked:
                paths.append(Path(item.text()))
        return paths

    def _gather_all_items(self) -> List[Path]:
        """Return a list of all Paths displayed in the model."""
        return [Path(self.model.item(row, 0).text()) for row in range(self.model.rowCount())]

    def _perform_cleanup(self, paths: List[Path], description: str) -> None:
        """Delete the supplied paths, showing progress and handling errors."""
        total = len(paths)
        successes = 0
        failures: List[Tuple[Path, str]] = []

        self.progress.setValue(0)
        self.status_label.setText(f"Cleaning {description}...")

        for idx, p in enumerate(paths, start=1):
            ok, msg = self._delete_path(p)
            if ok:
                successes += 1
            else:
                failures.append((p, msg))
            self.progress.setValue(int((idx / total) * 100))
            QCoreApplication.processEvents()  # keep UI responsive

        # Refresh view after cleanup
        self.refresh()

        # Summary dialog
        if failures:
            fail_msg = "\n".join(f"{str(p)} – {msg}" for p, msg in failures)
            QMessageBox.warning(
                self,
                "Cleanup Completed with Errors",
                f"Deleted {successes} items successfully.\n"
                f"{len(failures)} items could not be removed:\n{fail_msg}",
            )
        else:
            QMessageBox.information(
                self,
                "Cleanup Successful",
                f"All {successes} selected items were removed successfully.",
            )
        self.status_label.setText("Ready.")

    # ------------------------------------------------------------------- #
    # Refresh handling
    # ------------------------------------------------------------------- #
    def refresh(self) -> None:
        """Re‑run the scan to reflect the current state of temporary directories."""
        self.start_scan()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    """Launch the Disk Cleaner application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Aura Disk Cleaner")
    window = DiskCleaner()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
