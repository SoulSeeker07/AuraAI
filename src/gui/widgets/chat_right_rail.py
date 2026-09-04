"""
ChatRightRail Widget
====================
Right telemetry and operations rail for AuraAI Neural Chat HUD.
Hosts collapsible accordion sections:
1. Scheduled Tasks (Live triggers and cron routines from SchedulerManager / PersonalOSStateStore)
2. Background Tasks & Agents (Mini agent status grid + ExpandableTaskRow queue)
3. Artifacts [Phase 2 Stub] (Referenced & generated files)
4. Terminal [Phase 3 Stub] (Interactive HMAC-gated CLI console)
"""

import logging
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QGridLayout,
    QLayout,
)

from gui.real_backend_bridge import RealBackendBridge
from gui.signals import app_signals, ExecutionStep

logger = logging.getLogger(__name__)

TEXT_AND_CODE_EXTENSIONS = frozenset({
    ".md", ".markdown", ".txt", ".log",
    ".json", ".csv", ".tsv", ".yaml", ".yml", ".xml", ".toml", ".ini", ".cfg",
    ".html", ".css", ".js", ".ts", ".py", ".svg",
})

IMAGE_AND_DOC_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".pdf",
})

SAFE_ARTIFACT_EXTENSIONS = TEXT_AND_CODE_EXTENSIONS | IMAGE_AND_DOC_EXTENSIONS

PROHIBITED_EXEC_EXTENSIONS = frozenset({
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".jse",
    ".wsf", ".wsh", ".msc", ".msi", ".msp", ".scr", ".pif", ".reg",
    ".com", ".hta", ".cpl", ".jar", ".dll", ".sys",
})


class ElidedLabel(QLabel):
    """QLabel that elides overflowing text with '…' instead of letting
    the layout hard-clip it mid-word at the container boundary."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setToolTip(text)
        QLabel.setText(self, text)

    def setFullText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._apply_elision()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elision()

    def _apply_elision(self) -> None:
        if self.width() <= 0:
            return
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self._full_text, Qt.ElideRight, max(self.width(), 0))
        QLabel.setText(self, elided)

    def minimumSizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance("…"), fm.height())


class AccordionHeader(QFrame):
    """Clickable header bar for accordion sections with animated chevron and count badge."""
    toggled = Signal(bool)

    def __init__(self, title: str, count_badge: str = "", is_expanded: bool = True, is_dimmed: bool = False, parent=None):
        super().__init__(parent)
        self.is_expanded = is_expanded
        self.is_dimmed = is_dimmed
        self.setCursor(Qt.PointingHandCursor if not is_dimmed else Qt.ForbiddenCursor)
        self._setup_ui(title, count_badge)

    def _setup_ui(self, title: str, count_badge: str):
        self.setStyleSheet(f"""
            AccordionHeader {{
                background: rgba(15, 23, 42, { '0.4' if self.is_dimmed else '0.85' });
                border: 1px solid rgba(56, 189, 248, { '0.08' if self.is_dimmed else '0.2' });
                border-radius: 8px;
            }}
            AccordionHeader:hover {{
                background: rgba(30, 41, 59, { '0.4' if self.is_dimmed else '0.95' });
                border-color: rgba(56, 189, 248, { '0.15' if self.is_dimmed else '0.45' });
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Chevron
        self._chevron = QLabel("▼" if self.is_expanded else "▶")
        self._chevron.setFont(QFont("Consolas", 8, QFont.Bold))
        self._chevron.setStyleSheet("color: #64748b;" if self.is_dimmed else ("color: #00e5ff;" if self.is_expanded else "color: #94a3b8;"))
        layout.addWidget(self._chevron)

        # Title (elides gracefully with '…', taking remaining stretch)
        t_lbl = ElidedLabel(title)
        t_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        t_lbl.setStyleSheet("color: #64748b;" if self.is_dimmed else "color: #e2e8f0; letter-spacing: 0.5px;")
        t_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(t_lbl, 1)

        # Count Badge (always fixed size and fully intact)
        if count_badge:
            self._badge = QLabel(count_badge)
            self._badge.setFont(QFont("Consolas", 7, QFont.Bold))
            self._badge.setStyleSheet("""
                color: #38bdf8;
                background: rgba(56, 189, 248, 0.15);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 4px;
                padding: 1px 6px;
            """)
            layout.addWidget(self._badge)

    def set_badge(self, text: str):
        if hasattr(self, "_badge"):
            self._badge.setText(text)

    def mousePressEvent(self, event):
        if self.is_dimmed:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_expanded = not self.is_expanded
            self._chevron.setText("▼" if self.is_expanded else "▶")
            self._chevron.setStyleSheet("color: #00e5ff;" if self.is_expanded else "color: #94a3b8;")
            self.toggled.emit(self.is_expanded)
            event.accept()
        else:
            super().mousePressEvent(event)


class ScheduledJobCard(QFrame):
    """Card displaying a single scheduled routine or cron trigger."""

    def __init__(self, job_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.job_data = job_data
        self._setup_ui(job_data)

    def _setup_ui(self, job: Dict[str, Any]):
        self.setStyleSheet("""
            ScheduledJobCard {
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(56, 189, 248, 0.15);
                border-radius: 6px;
            }
            ScheduledJobCard:hover {
                background: rgba(30, 41, 59, 0.7);
                border-color: rgba(56, 189, 248, 0.35);
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header Row
        head = QHBoxLayout()
        head.setSpacing(6)

        dot = QLabel("●" if job.get("enabled", True) else "○")
        dot.setFont(QFont("Consolas", 8, QFont.Bold))
        dot.setStyleSheet("color: #10b981;" if job.get("enabled", True) else "color: #64748b;")
        head.addWidget(dot)

        name_lbl = QLabel(job.get("name", "Scheduled Task"))
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        name_lbl.setStyleSheet("color: #f1f5f9;")
        head.addWidget(name_lbl, 1)

        sched_lbl = QLabel(job.get("schedule", "interval"))
        sched_lbl.setFont(QFont("Consolas", 7))
        sched_lbl.setStyleSheet("""
            color: #fbbf24;
            background: rgba(251, 191, 36, 0.12);
            border: 1px solid rgba(251, 191, 36, 0.3);
            border-radius: 3px;
            padding: 1px 5px;
        """)
        head.addWidget(sched_lbl)
        layout.addLayout(head)

        # Target Goal
        target = job.get("target", "")
        if target:
            t_lbl = QLabel(target)
            t_lbl.setFont(QFont("Segoe UI", 8))
            t_lbl.setWordWrap(True)
            t_lbl.setStyleSheet("color: #94a3b8; padding-left: 14px;")
            layout.addWidget(t_lbl)


class RailTaskCard(QFrame):
    """
    Compact Expandable Task Card specifically tailored for ChatRightRail (330px width).
    Ensures word-wrap and zero horizontal layout blowout.
    """

    def __init__(self, task_data: Dict[str, Any], is_expanded: bool = False, on_toggle_callback=None, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self.is_expanded = is_expanded
        self.on_toggle_callback = on_toggle_callback
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            RailTaskCard {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(56, 189, 248, 0.15);
                border-radius: 6px;
            }
            RailTaskCard:hover {
                background: rgba(30, 41, 59, 0.85);
                border-color: rgba(56, 189, 248, 0.35);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Row 1: Chevron + Task ID + Agent • Status Badge
        r1 = QHBoxLayout()
        r1.setSpacing(6)

        self._chevron_lbl = QLabel("▼" if self.is_expanded else "▶")
        self._chevron_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        self._chevron_lbl.setStyleSheet("color: #00e5ff;" if self.is_expanded else "color: #64748b;")
        r1.addWidget(self._chevron_lbl)

        t_id = self.task_data.get("id", "T-0000")
        id_lbl = QLabel(t_id)
        id_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        id_lbl.setStyleSheet("color: #e2e8f0;")
        r1.addWidget(id_lbl)

        agent_txt = self.task_data.get("agent", "Executive Brain")
        agent_lbl = ElidedLabel(f"• {agent_txt}")
        agent_lbl.setFont(QFont("Segoe UI", 8))
        agent_lbl.setStyleSheet("color: #6496ff;")
        agent_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        r1.addWidget(agent_lbl, 1)

        status_txt = self.task_data.get("status", "● Completed")
        status_col = "#10b981"
        if "failed" in status_txt.lower() or "error" in status_txt.lower():
            status_col = "#f43f5e"
        elif "running" in status_txt.lower() or "executing" in status_txt.lower():
            status_col = "#fbbf24"

        s_lbl = QLabel(status_txt)
        s_lbl.setFont(QFont("Consolas", 7, QFont.Bold))
        s_lbl.setStyleSheet(f"""
            color: {status_col};
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid {status_col}44;
            border-radius: 3px;
            padding: 1px 5px;
        """)
        r1.addWidget(s_lbl)
        layout.addLayout(r1)

        # Row 2: Description (Word Wrapped, No Layout Blowout)
        desc_txt = self.task_data.get("desc", "No description")
        if desc_txt:
            d_lbl = QLabel(desc_txt)
            d_lbl.setFont(QFont("Segoe UI", 8))
            d_lbl.setWordWrap(True)
            d_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            d_lbl.setStyleSheet("color: #94a3b8; padding-left: 14px;")
            layout.addWidget(d_lbl)

        # Row 3: Expanded Detail Container
        self._details = QFrame()
        self._details.setVisible(self.is_expanded)
        self._details.setStyleSheet("""
            QFrame {
                background: rgba(8, 12, 22, 0.95);
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 6px;
                margin-top: 4px;
            }
        """)
        d_layout = QVBoxLayout(self._details)
        d_layout.setContentsMargins(8, 6, 8, 6)
        d_layout.setSpacing(6)

        resp_text = self.task_data.get("response", "")
        if not resp_text:
            resp_text = "Action completed through cognitive pipeline."
        resp_box = QLabel(resp_text)
        resp_box.setFont(QFont("Segoe UI", 8))
        resp_box.setWordWrap(True)
        resp_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        resp_box.setStyleSheet("color: #f1f5f9; background: transparent;")
        d_layout.addWidget(resp_box)

        # Error report if any
        err_msg = self.task_data.get("error", "")
        if err_msg:
            err_lbl = QLabel(f"⚠️ {err_msg}")
            err_lbl.setFont(QFont("Segoe UI", 8))
            err_lbl.setWordWrap(True)
            err_lbl.setStyleSheet("color: #fca5a5; background: rgba(244, 63, 94, 0.15); padding: 4px; border-radius: 4px;")
            d_layout.addWidget(err_lbl)

        # Copy Action
        btn_copy = QPushButton("📋 Copy Summary")
        btn_copy.setFont(QFont("Segoe UI", 7, QFont.Bold))
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(100, 150, 255, 0.12);
                border: 1px solid rgba(100, 150, 255, 0.25);
                border-radius: 3px;
                color: #6496ff;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: rgba(100, 150, 255, 0.25);
            }
        """)
        def _do_copy():
            from PySide6.QtGui import QGuiApplication
            summary = f"Task {t_id} [{status_txt}]: {desc_txt}\n{resp_text}"
            QGuiApplication.clipboard().setText(summary)
            btn_copy.setText("✓ Copied!")
            QTimer.singleShot(1500, lambda: btn_copy.setText("📋 Copy Summary"))
        btn_copy.clicked.connect(_do_copy)
        d_layout.addWidget(btn_copy, 0, Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self._details)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_expanded = not self.is_expanded
            self._chevron_lbl.setText("▼" if self.is_expanded else "▶")
            self._chevron_lbl.setStyleSheet("color: #00e5ff;" if self.is_expanded else "color: #64748b;")
            self._details.setVisible(self.is_expanded)
            if self.on_toggle_callback:
                self.on_toggle_callback(self.task_data.get("id", ""), self.is_expanded)
            event.accept()
        else:
            super().mousePressEvent(event)


class ArtifactCard(QFrame):
    """
    Card displaying a session-generated artifact (document, code file, plot, or output).
    Includes safe launch in default OS handler and Copy Path.
    """

    def __init__(self, artifact_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.artifact_data = artifact_data
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            ArtifactCard {
                background: rgba(15, 23, 42, 0.65);
                border: 1px solid rgba(56, 189, 248, 0.15);
                border-radius: 6px;
            }
            ArtifactCard:hover {
                background: rgba(30, 41, 59, 0.8);
                border-color: rgba(56, 189, 248, 0.35);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Row 1: Icon + Name + Size Badge
        r1 = QHBoxLayout()
        r1.setSpacing(6)

        icon_lbl = QLabel(self.artifact_data.get("icon", "📄"))
        icon_lbl.setFont(QFont("Segoe UI Emoji", 9))
        r1.addWidget(icon_lbl)

        name_txt = self.artifact_data.get("name", "artifact")
        name_lbl = ElidedLabel(name_txt)
        name_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        name_lbl.setStyleSheet("color: #f1f5f9;")
        name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        r1.addWidget(name_lbl, 1)

        size_txt = self.artifact_data.get("size_str", "")
        if size_txt:
            size_lbl = QLabel(size_txt)
            size_lbl.setFont(QFont("Consolas", 7))
            size_lbl.setStyleSheet("""
                color: #38bdf8;
                background: rgba(56, 189, 248, 0.1);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 3px;
                padding: 1px 4px;
            """)
            r1.addWidget(size_lbl)
        layout.addLayout(r1)

        # Row 2: Path (Muted Grey)
        path_txt = self.artifact_data.get("path", "")
        if path_txt:
            path_lbl = ElidedLabel(path_txt)
            path_lbl.setFont(QFont("Segoe UI", 7))
            path_lbl.setStyleSheet("color: #64748b; padding-left: 18px;")
            path_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            layout.addWidget(path_lbl)

        # Row 3: Action Buttons (Open, Copy Path)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.setContentsMargins(18, 2, 0, 0)

        btn_open = QPushButton("↗ Open")
        btn_open.setFont(QFont("Segoe UI", 7, QFont.Bold))
        btn_open.setStyleSheet("""
            QPushButton {
                background: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 3px;
                color: #38bdf8;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.25);
            }
        """)

        def _do_open():
            import os
            import subprocess
            from pathlib import Path
            from desktop.native.sandbox.workspace_jail import WorkspaceJail
            from core.config import PROJECT_ROOT

            target_path = self.artifact_data.get("path", "")
            if not target_path:
                return

            try:
                candidate = Path(target_path).resolve()
            except Exception as exc:
                logger.warning(f"[ArtifactCard] Invalid path '{target_path}': {exc}")
                return

            if not candidate.exists() or not candidate.is_file():
                logger.warning(f"[ArtifactCard] Target artifact does not exist on disk: '{candidate}'")
                return

            # 1. Enforce WorkspaceJail containment strictly against PROJECT_ROOT
            terminal_jail = WorkspaceJail(workspace_root=str(PROJECT_ROOT))
            if not terminal_jail.is_path_inside_workspace(candidate):
                logger.error(f"[Security Violation] Blocked opening artifact outside workspace jail: '{candidate}'")
                return

            ext = candidate.suffix.lower()

            # 2. Strict prohibition on executable extensions
            if ext in PROHIBITED_EXEC_EXTENSIONS or ext not in SAFE_ARTIFACT_EXTENSIONS:
                logger.error(f"[Security Violation] Blocked opening prohibited or unverified artifact extension '{ext}': '{candidate}'")
                return

            # 3. Explicit safe dispatch: no arbitrary fallthrough
            try:
                if ext in TEXT_AND_CODE_EXTENSIONS:
                    # Open strictly with safe system text editor (notepad.exe) to prevent execution
                    subprocess.Popen(["notepad.exe", str(candidate)])
                elif ext in IMAGE_AND_DOC_EXTENSIONS:
                    # Images and non-executable documents (.png, .jpg, .pdf)
                    os.startfile(str(candidate))
                else:
                    logger.error(f"[Security Violation] Unhandled or unverified extension '{ext}': '{candidate}'")
                    return
            except Exception as exc:
                logger.warning(f"[ArtifactCard] Failed to open artifact '{candidate}': {exc}")

        btn_open.clicked.connect(_do_open)
        actions.addWidget(btn_open)

        btn_copy = QPushButton("📋 Copy Path")
        btn_copy.setFont(QFont("Segoe UI", 7))
        btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(148, 163, 184, 0.1);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 3px;
                color: #94a3b8;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: rgba(148, 163, 184, 0.2);
                color: #e2e8f0;
            }
        """)

        def _do_copy():
            from PySide6.QtGui import QGuiApplication, QClipboard
            target_path = self.artifact_data.get("path", "")
            if target_path:
                cb = QGuiApplication.clipboard()
                if cb is not None:
                    cb.setText(target_path, QClipboard.Mode.Clipboard)
                btn_copy.setText("✓ Copied!")
                QTimer.singleShot(1500, lambda: btn_copy.setText("📋 Copy Path"))

        btn_copy.clicked.connect(_do_copy)
        actions.addWidget(btn_copy)
        actions.addStretch()
        layout.addLayout(actions)


class HMACApprovalCard(QFrame):
    """
    Interactive approval card for pending cryptographic HMAC tickets.
    Provides single-source redemption execution and operator denial.
    """

    def __init__(self, ticket_data: Dict[str, Any], on_action_callback=None, parent=None):
        super().__init__(parent)
        self.ticket_data = ticket_data
        self.on_action_callback = on_action_callback
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            HMACApprovalCard {
                background: rgba(30, 27, 75, 0.75);
                border: 1px solid rgba(244, 63, 94, 0.35);
                border-radius: 6px;
            }
            HMACApprovalCard:hover {
                background: rgba(49, 46, 129, 0.85);
                border-color: rgba(244, 63, 94, 0.6);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Row 1: Action Badge + Ticket ID + Expiry
        r1 = QHBoxLayout()
        r1.setSpacing(6)

        action_type = self.ticket_data.get("action_type", "HIGH RISK").upper()
        type_lbl = QLabel(action_type)
        type_lbl.setFont(QFont("Consolas", 7, QFont.Bold))
        type_lbl.setStyleSheet("""
            color: #f43f5e;
            background: rgba(244, 63, 94, 0.15);
            border: 1px solid rgba(244, 63, 94, 0.3);
            border-radius: 3px;
            padding: 1px 4px;
        """)
        r1.addWidget(type_lbl)

        t_id = self.ticket_data.get("ticket_id", "")
        id_lbl = QLabel(t_id)
        id_lbl.setFont(QFont("Consolas", 7))
        id_lbl.setStyleSheet("color: #38bdf8;")
        r1.addWidget(id_lbl)

        r1.addStretch()

        exp_sec = self.ticket_data.get("expires_in_secs", 300)
        exp_lbl = QLabel(f"Expires in {exp_sec}s")
        exp_lbl.setFont(QFont("Segoe UI", 7))
        exp_lbl.setStyleSheet("color: #fbbf24;")
        r1.addWidget(exp_lbl)
        layout.addLayout(r1)

        # Row 2: Target / Command Box
        target_txt = self.ticket_data.get("target", "")
        target_lbl = ElidedLabel(target_txt)
        target_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        target_lbl.setStyleSheet("""
            color: #f1f5f9;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 3px;
            padding: 2px 4px;
        """)
        target_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        layout.addWidget(target_lbl)

        # Row 3: HMAC Hash preview
        h_txt = self.ticket_data.get("action_hash", "")[:16] + "…" if self.ticket_data.get("action_hash") else ""
        if h_txt:
            h_lbl = QLabel(f"HMAC: {h_txt}")
            h_lbl.setFont(QFont("Consolas", 7))
            h_lbl.setStyleSheet("color: #94a3b8;")
            layout.addWidget(h_lbl)

        # Row 4: Approve & Deny Buttons
        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.setContentsMargins(0, 2, 0, 0)

        btn_approve = QPushButton("✓ Approve & Execute")
        btn_approve.setFont(QFont("Segoe UI", 7, QFont.Bold))
        btn_approve.setStyleSheet("""
            QPushButton {
                background: rgba(16, 185, 129, 0.2);
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 3px;
                color: #10b981;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background: rgba(16, 185, 129, 0.35);
                color: #34d399;
            }
        """)

        def _do_approve():
            bridge = RealBackendBridge.get_instance()
            bridge.approve_and_execute_ticket(t_id)
            if self.on_action_callback:
                self.on_action_callback()

        btn_approve.clicked.connect(_do_approve)
        actions.addWidget(btn_approve)

        btn_deny = QPushButton("✗ Deny")
        btn_deny.setFont(QFont("Segoe UI", 7))
        btn_deny.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 3px;
                color: #ef4444;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
                color: #fca5a5;
            }
        """)

        def _do_deny():
            bridge = RealBackendBridge.get_instance()
            bridge.deny_ticket(t_id)
            if self.on_action_callback:
                self.on_action_callback()

        btn_deny.clicked.connect(_do_deny)
        actions.addWidget(btn_deny)
        actions.addStretch()
        layout.addLayout(actions)


class TerminalStreamWidget(QFrame):
    """
    Monospace terminal log console displaying stdout/stderr traces and execution results.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            TerminalStreamWidget {
                background: #050811;
                border: 1px solid rgba(56, 189, 248, 0.18);
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(4)

        # Header bar: Title + Clear + Copy
        hbar = QHBoxLayout()
        hbar.setSpacing(6)

        title = QLabel("💻 STREAM LOG")
        title.setFont(QFont("Consolas", 7, QFont.Bold))
        title.setStyleSheet("color: #38bdf8;")
        hbar.addWidget(title)
        hbar.addStretch()

        btn_copy = QPushButton("Copy")
        btn_copy.setFont(QFont("Segoe UI", 6))
        btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(148, 163, 184, 0.1);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 2px;
                color: #94a3b8;
                padding: 1px 4px;
            }
            QPushButton:hover { background: rgba(148, 163, 184, 0.2); color: #f1f5f9; }
        """)

        def _do_copy():
            from PySide6.QtGui import QGuiApplication
            logs = RealBackendBridge.get_instance().get_terminal_logs()
            full_txt = "\n".join(f"[{l['timestamp']}] {l['text']}" for l in logs)
            if full_txt:
                QGuiApplication.clipboard().setText(full_txt)
                btn_copy.setText("Copied!")
                QTimer.singleShot(1500, lambda: btn_copy.setText("Copy"))

        btn_copy.clicked.connect(_do_copy)
        hbar.addWidget(btn_copy)

        btn_clear = QPushButton("Clear")
        btn_clear.setFont(QFont("Segoe UI", 6))
        btn_clear.setStyleSheet("""
            QPushButton {
                background: rgba(148, 163, 184, 0.1);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 2px;
                color: #94a3b8;
                padding: 1px 4px;
            }
            QPushButton:hover { background: rgba(148, 163, 184, 0.2); color: #f1f5f9; }
        """)

        def _do_clear():
            RealBackendBridge.get_instance().clear_terminal_logs()
            self.set_logs([])

        btn_clear.clicked.connect(_do_clear)
        hbar.addWidget(btn_clear)
        layout.addLayout(hbar)

        # Log content container
        self._log_container = QFrame()
        self._log_layout = QVBoxLayout(self._log_container)
        self._log_layout.setContentsMargins(0, 0, 0, 0)
        self._log_layout.setSpacing(2)
        layout.addWidget(self._log_container)

    def set_logs(self, logs: List[Dict[str, str]]):
        while self._log_layout.count():
            item = self._log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not logs:
            empty = QLabel("Console idle. Ready for command execution.")
            empty.setFont(QFont("Consolas", 7))
            empty.setStyleSheet("color: #475569; padding: 4px;")
            self._log_layout.addWidget(empty)
            return

        for log in logs[-8:]:
            txt = log.get("text", "")
            lvl = log.get("level", "info")
            if lvl == "command":
                col = "#38bdf8"
            elif lvl == "success":
                col = "#4ade80"
            elif lvl == "error":
                col = "#f87171"
            elif lvl == "warn":
                col = "#fbbf24"
            else:
                col = "#94a3b8"

            lbl = ElidedLabel(f"[{log.get('timestamp', '')}] {txt}")
            lbl.setFont(QFont("Consolas", 7))
            lbl.setStyleSheet(f"color: {col}; padding: 1px 2px;")
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            self._log_layout.addWidget(lbl)


class ChatRightRail(QWidget):
    """
    Collapsible right sidebar for ChatWindowOverlay.
    Contains real-time scheduled tasks, background tasks, and agent telemetry.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatRightRail")
        self._bridge = RealBackendBridge.get_instance()
        self._expanded_task_ids = set()

        self._setup_ui()
        self._connect_signals()

        # Low-frequency 3s timer for countdowns and idle status checks
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_data)
        self._timer.start(3000)

        # Initial render
        QTimer.singleShot(100, self.refresh_data)

    def _setup_ui(self):
        self.setMinimumWidth(330)
        self.setMaximumWidth(390)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            #ChatRightRail {
                background: #0b1120;
                border: 1px solid rgba(56, 189, 248, 0.16);
                border-radius: 12px;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # Header Title + Status tightly grouped
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(6, 4, 6, 4)
        top_bar.setSpacing(8)

        title = QLabel("OPERATIONS & TELEMETRY")
        title.setFont(QFont("Consolas", 8, QFont.Bold))
        title.setStyleSheet("color: #38bdf8; letter-spacing: 1px;")
        top_bar.addWidget(title)

        self._live_indicator = QLabel("● IDLE")
        self._live_indicator.setFont(QFont("Consolas", 7, QFont.Bold))
        self._live_indicator.setStyleSheet("""
            color: #10b981;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.25);
            border-radius: 4px;
            padding: 1px 6px;
        """)
        top_bar.addWidget(self._live_indicator)
        top_bar.addStretch()
        root_layout.addLayout(top_bar)

        # Main Scrollable Area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 0.4);
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(56, 189, 248, 0.25);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 229, 255, 0.5);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 4, 0)
        self._layout.setSpacing(10)

        # ── 1. Scheduled Tasks Section ──
        self._sched_header = AccordionHeader("⏱ SCHEDULED TASKS", count_badge="0 Active", is_expanded=True)
        self._sched_header.toggled.connect(self._toggle_sched_body)
        self._layout.addWidget(self._sched_header)

        self._sched_body = QWidget()
        self._sched_body_layout = QVBoxLayout(self._sched_body)
        self._sched_body_layout.setContentsMargins(10, 4, 6, 6)
        self._sched_body_layout.setSpacing(6)
        self._layout.addWidget(self._sched_body)

        # ── 2. Background Tasks & Agents Section ──
        self._bg_header = AccordionHeader("⚡ BACKGROUND TASKS & AGENTS", count_badge="6 Agents", is_expanded=True)
        self._bg_header.toggled.connect(self._toggle_bg_body)
        self._layout.addWidget(self._bg_header)

        self._bg_body = QWidget()
        self._bg_body_layout = QVBoxLayout(self._bg_body)
        self._bg_body_layout.setContentsMargins(10, 4, 6, 6)
        self._bg_body_layout.setSpacing(8)

        # Single-column Agent Status List (avoids 2-column clipping)
        self._agent_list_layout = QVBoxLayout()
        self._agent_list_layout.setSpacing(5)
        self._bg_body_layout.addLayout(self._agent_list_layout)

        # Task Queue Container
        self._tasks_list_layout = QVBoxLayout()
        self._tasks_list_layout.setSpacing(6)
        self._bg_body_layout.addLayout(self._tasks_list_layout)

        self._layout.addWidget(self._bg_body)

        # ── 3. Artifacts Section ──
        self._art_header = AccordionHeader("📦 ARTIFACTS", count_badge="0 Items", is_expanded=False, is_dimmed=False)
        self._art_header.toggled.connect(self._toggle_art_body)
        self._layout.addWidget(self._art_header)

        self._art_body = QFrame()
        self._art_body.setVisible(False)
        self._art_body_layout = QVBoxLayout(self._art_body)
        self._art_body_layout.setContentsMargins(10, 4, 6, 6)
        self._art_body_layout.setSpacing(6)
        self._layout.addWidget(self._art_body)

        # ── 4. Terminal Console Section ──
        self._term_header = AccordionHeader("💻 TERMINAL CONSOLE", count_badge="Console Ready", is_expanded=False, is_dimmed=False)
        self._term_header.toggled.connect(self._toggle_term_body)
        self._layout.addWidget(self._term_header)

        self._term_body = QFrame()
        self._term_body.setVisible(False)
        self._term_body_layout = QVBoxLayout(self._term_body)
        self._term_body_layout.setContentsMargins(10, 4, 6, 6)
        self._term_body_layout.setSpacing(6)

        # HMAC Queue Layout
        self._hmac_queue_layout = QVBoxLayout()
        self._hmac_queue_layout.setSpacing(4)
        self._term_body_layout.addLayout(self._hmac_queue_layout)

        # Terminal Stream Widget
        self._term_stream_widget = TerminalStreamWidget(parent=self)
        self._term_body_layout.addWidget(self._term_stream_widget)

        self._layout.addWidget(self._term_body)

        self._layout.addStretch()
        self._scroll.setWidget(self._container)
        root_layout.addWidget(self._scroll)

    def _toggle_sched_body(self, expanded: bool):
        self._sched_body.setVisible(expanded)

    def _toggle_bg_body(self, expanded: bool):
        self._bg_body.setVisible(expanded)

    def _toggle_art_body(self, expanded: bool):
        self._art_body.setVisible(expanded)

    def _toggle_term_body(self, expanded: bool):
        self._term_body.setVisible(expanded)

    def _connect_signals(self):
        """Pure observer listener: triggers local redraw on execution events without mutating bridge."""
        app_signals.execution_started.connect(self._on_execution_signal)
        app_signals.execution_finished.connect(self._on_execution_signal)
        app_signals.step_updated.connect(self._on_step_signal)

    def _on_execution_signal(self, *args):
        self.refresh_data()

    def _on_step_signal(self, step: ExecutionStep):
        # Update live indicator briefly
        self._live_indicator.setText("◐ EXECUTING")
        self._live_indicator.setStyleSheet("color: #fbbf24; background: transparent;")
        self.refresh_data()

    def refresh_data(self):
        """Coalesce same-tick refresh calls into one rebuild."""
        if getattr(self, "_refresh_pending", False):
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._do_refresh)

    @staticmethod
    def _clear_layout(layout: Optional[QLayout]) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                try:
                    w.setParent(None)
                    w.deleteLater()
                except Exception:
                    pass
            elif item.layout() is not None:
                ChatRightRail._clear_layout(item.layout())

    def _do_refresh(self):
        self._refresh_pending = False

        # 1. Scheduled Tasks
        jobs = self._bridge.get_scheduled_jobs()
        active_jobs = [j for j in jobs if j.get("enabled", True)]
        self._sched_header.set_badge(f"{len(active_jobs)} Active")

        # Clear and repopulate scheduled jobs (immediately unparenting to prevent ghosting)
        self._clear_layout(self._sched_body_layout)

        if jobs:
            for job in jobs[:5]:
                card = ScheduledJobCard(job, parent=self)
                self._sched_body_layout.addWidget(card)
        else:
            no_jobs = QLabel("No active schedules or timers.")
            no_jobs.setFont(QFont("Segoe UI", 8))
            no_jobs.setStyleSheet("color: #64748b; padding: 4px 8px;")
            self._sched_body_layout.addWidget(no_jobs)

        # 2. Agent Data & Tasks
        agent_data = self._bridge.get_agent_task_data()
        agents = agent_data.get("agents", [])

        # Update Agent List (Single-column layout, no clipping)
        self._clear_layout(self._agent_list_layout)

        for a in agents[:6]:
            pill = self._create_agent_pill(a)
            self._agent_list_layout.addWidget(pill)

        # Update Task Queue
        tasks = agent_data.get("tasks", [])
        active_tasks = [t for t in tasks if "executing" in str(t.get("status", "")).lower()]
        self._bg_header.set_badge(f"{len(active_tasks)} Running • {len(agents)} Agents" if active_tasks else f"{len(agents)} Agents Ready")

        self._clear_layout(self._tasks_list_layout)

        if tasks:
            for t in tasks[:6]:
                t_id = t.get("id", "")
                is_expanded = t_id in self._expanded_task_ids
                row = RailTaskCard(
                    task_data=t,
                    is_expanded=is_expanded,
                    on_toggle_callback=self._on_task_toggle,
                    parent=self,
                )
                self._tasks_list_layout.addWidget(row)
        else:
            no_tasks = QLabel("No active tasks in queue.")
            no_tasks.setFont(QFont("Segoe UI", 8))
            no_tasks.setStyleSheet("color: #64748b; padding: 4px 8px;")
            self._tasks_list_layout.addWidget(no_tasks)

        # 3. Session Artifacts
        artifacts = self._bridge.get_session_artifacts()
        self._art_header.set_badge(f"{len(artifacts)} Items")

        self._clear_layout(self._art_body_layout)
        if artifacts:
            for art in artifacts[:8]:
                card = ArtifactCard(art, parent=self)
                self._art_body_layout.addWidget(card)
        else:
            no_art = QLabel("No session artifacts generated yet.")
            no_art.setFont(QFont("Segoe UI", 8))
            no_art.setStyleSheet("color: #64748b; padding: 4px 8px;")
            self._art_body_layout.addWidget(no_art)

        # 4. Terminal Console & HMAC Gate
        pending_tickets = self._bridge.get_pending_approval_tickets()
        if pending_tickets:
            self._term_header.set_badge(f"{len(pending_tickets)} Pending")
        else:
            self._term_header.set_badge("Console Ready")

        self._clear_layout(self._hmac_queue_layout)
        for t in pending_tickets[:5]:
            card = HMACApprovalCard(t, on_action_callback=self.refresh_data, parent=self)
            self._hmac_queue_layout.addWidget(card)

        terminal_logs = self._bridge.get_terminal_logs()
        self._term_stream_widget.set_logs(terminal_logs)

        # Reset indicator if no active execution
        if not active_tasks:
            self._live_indicator.setText("● IDLE")
            self._live_indicator.setStyleSheet("""
                color: #10b981;
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.25);
                border-radius: 4px;
                padding: 1px 6px;
            """)

        # Lock horizontal scroll offset to zero to prevent any left-edge clipping
        if hasattr(self, "_scroll"):
            QTimer.singleShot(10, lambda: self._scroll.horizontalScrollBar().setValue(0))

    def _create_agent_pill(self, a: Dict[str, Any]) -> QFrame:
        pill = QFrame()
        col = a.get("color", "#6496ff")
        pill.setStyleSheet(f"""
            QFrame {{
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba({int(col[1:3], 16)}, {int(col[3:5], 16)}, {int(col[5:7], 16)}, 0.25);
                border-radius: 6px;
            }}
            QFrame:hover {{
                background: rgba(30, 41, 59, 0.85);
                border-color: rgba({int(col[1:3], 16)}, {int(col[3:5], 16)}, {int(col[5:7], 16)}, 0.5);
            }}
        """)
        pill.setMinimumHeight(44)
        pill.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        outer = QVBoxLayout(pill)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(8)

        dot = QLabel("●")
        dot.setFont(QFont("Consolas", 8, QFont.Bold))
        dot.setStyleSheet(f"color: {col}; background: transparent;")
        top.addWidget(dot)

        name = ElidedLabel(a.get("name", "Agent"))
        name.setFont(QFont("Segoe UI", 8, QFont.Bold))
        name.setStyleSheet("color: #e2e8f0;")
        name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top.addWidget(name, 1)

        status = QLabel(a.get("status", "Ready"))
        status.setFont(QFont("Consolas", 7, QFont.Bold))
        status.setStyleSheet(f"""
            color: {col};
            background: rgba({int(col[1:3], 16)}, {int(col[3:5], 16)}, {int(col[5:7], 16)}, 0.12);
            border-radius: 3px;
            padding: 2px 6px;
        """)
        top.addWidget(status)
        outer.addLayout(top)

        task_desc = a.get("task", "")
        if task_desc:
            desc_lbl = ElidedLabel(task_desc)
            desc_lbl.setFont(QFont("Segoe UI", 7))
            desc_lbl.setStyleSheet("color: #7b8c9f;")
            desc_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            outer.addWidget(desc_lbl)

        return pill

    def _on_task_toggle(self, task_id: str, expanded: bool):
        if expanded:
            self._expanded_task_ids.add(task_id)
        else:
            self._expanded_task_ids.discard(task_id)
