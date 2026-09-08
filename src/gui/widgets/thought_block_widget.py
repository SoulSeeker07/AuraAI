"""
ThoughtBlockWidget
==================
Location: src/gui/widgets/thought_block_widget.py

A sleek, collapsible cyber-HUD card for chain-of-thought and reasoning segments
(<think> / <thinking> blocks).
- Collapsed by default (takes only a compact ~30px header bar).
- Click to expand and inspect the model's internal reasoning.
- Dark glassmorphism card styling with cyan accent border.
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ThoughtBlockWidget(QFrame):
    """
    Collapsible thought/reasoning card inspired by Claude and DeepSeek R1 UI patterns.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        content: str,
        title: str = "Thought Process",
        is_expanded: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._raw_content = (content or "").strip()
        self._title = title or "Thought Process"
        self.is_expanded = is_expanded

        self._setup_ui()

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet("""
            ThoughtBlockWidget {
                background: rgba(10, 15, 26, 0.65);
                border: 1px solid rgba(56, 189, 248, 0.18);
                border-left: 3px solid rgba(0, 229, 255, 0.55);
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ── Header Bar (Always visible & clickable) ──
        self._header = QFrame()
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(8)

        # Chevron
        self._chevron = QLabel("▼" if self.is_expanded else "▶")
        self._chevron.setFont(QFont("Consolas", 8, QFont.Bold))
        self._chevron.setStyleSheet("color: #00e5ff; background: transparent;")
        header_layout.addWidget(self._chevron)

        # Brain / Thought Icon & Title
        title_lbl = QLabel(f"💭 {self._title}")
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #94a3b8; letter-spacing: 0.3px; background: transparent;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        # Token / Line Count Badge
        line_count = len(self._raw_content.splitlines())
        word_count = len(self._raw_content.split())
        badge_text = f"{word_count} words" if word_count < 100 else f"{line_count} lines"
        self._badge = QLabel(badge_text)
        self._badge.setFont(QFont("Consolas", 8))
        self._badge.setStyleSheet("""
            QLabel {
                color: #38bdf8;
                background: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 4px;
                padding: 1px 6px;
            }
        """)
        header_layout.addWidget(self._badge)

        layout.addWidget(self._header)

        # ── Body Container (Collapsible) ──
        self._body_container = QWidget()
        body_layout = QVBoxLayout(self._body_container)
        body_layout.setContentsMargins(8, 4, 8, 6)
        body_layout.setSpacing(4)

        self._body_lbl = QLabel()
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._body_lbl.setFont(QFont("Segoe UI", 9))
        self._body_lbl.setText(self._format_thought_html(self._raw_content))
        self._body_lbl.setStyleSheet("background: transparent; border: none;")
        body_layout.addWidget(self._body_lbl)

        layout.addWidget(self._body_container)

        # Sync initial visibility
        self._body_container.setVisible(self.is_expanded)

    def _format_thought_html(self, text: str) -> str:
        if not text:
            return ""
        # Escape HTML
        formatted = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Bold & Italic
        formatted = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", formatted)
        formatted = re.sub(r"\*(.+?)\*", r"<i>\1</i>", formatted)
        # Inline code
        formatted = re.sub(
            r"`([^`]+)`",
            r'<code style="color:#00e5ff; background:rgba(0,229,255,0.08); padding:1px 4px; border-radius:3px; font-family:Consolas,monospace;">\1</code>',
            formatted,
        )
        formatted = formatted.replace("\n", "<br>")
        return f'<div style="color: #94a3b8; line-height: 1.5; font-style: normal;">{formatted}</div>'

    def mousePressEvent(self, event):
        pos = event.pos()
        # Toggle if clicking inside the header or anywhere when collapsed
        if not self.is_expanded or self._header.geometry().contains(pos):
            self.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self._chevron.setText("▼" if self.is_expanded else "▶")
        self._body_container.setVisible(self.is_expanded)
        self.toggled.emit(self.is_expanded)
