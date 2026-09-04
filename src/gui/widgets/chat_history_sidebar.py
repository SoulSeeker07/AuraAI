"""
ChatHistorySidebar Widget
=========================
Collapsible left sidebar for ChatWindowOverlay.
Provides session history navigation, search filtering, and quick 'New Chat' action.
Loads past turns from Data/ChatLog.json.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
)

from gui.widgets.chat_right_rail import ElidedLabel

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHAT_LOG_PATH = PROJECT_ROOT / "Data" / "ChatLog.json"


class HistorySessionItem(QFrame):
    """Clickable session card in the history sidebar."""
    clicked = Signal(str, str)  # prompt, response

    def __init__(self, prompt: str, response: str, timestamp: str = "", topic: str = "General", parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.response = response
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui(prompt, timestamp, topic)

    def _setup_ui(self, prompt: str, timestamp: str, topic: str):
        self.setStyleSheet("""
            HistorySessionItem {
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(56, 189, 248, 0.12);
                border-radius: 6px;
            }
            HistorySessionItem:hover {
                background: rgba(30, 41, 59, 0.8);
                border-color: rgba(56, 189, 248, 0.4);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Title / Prompt Preview
        disp_title = prompt.strip() or "Untitled Session"
        title_lbl = ElidedLabel(disp_title)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_lbl.setStyleSheet("color: #f1f5f9; background: transparent; border: none;")
        title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(title_lbl)

        # Footer: Topic Pill + Timestamp
        foot = QHBoxLayout()
        foot.setSpacing(6)

        topic_pill = ElidedLabel(topic.upper())
        topic_pill.setFont(QFont("Consolas", 7, QFont.Bold))
        topic_pill.setMaximumWidth(80)
        topic_pill.setStyleSheet("""
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 3px;
            padding: 1px 4px;
        """)
        foot.addWidget(topic_pill)

        foot.addStretch()

        if timestamp:
            time_part = timestamp.split("T")[-1][:5] if "T" in timestamp else timestamp[-8:-3]
            time_lbl = QLabel(time_part)
            time_lbl.setFont(QFont("Consolas", 7))
            time_lbl.setStyleSheet("color: #64748b; background: transparent; border: none;")
            foot.addWidget(time_lbl)

        layout.addLayout(foot)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.prompt, self.response)
            event.accept()
        else:
            super().mousePressEvent(event)


class ChatHistorySidebar(QWidget):
    """
    Collapsible conversation history sidebar.
    Lists past user commands and dialogue sessions with search filtering.
    """
    new_chat_requested = Signal()
    history_item_selected = Signal(str, str)  # prompt, response

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatHistorySidebar")
        self._raw_sessions: List[Dict[str, Any]] = []
        self._setup_ui()
        self.reload_history()

    def _setup_ui(self):
        self.setMinimumWidth(220)
        self.setMaximumWidth(280)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            #ChatHistorySidebar {
                background: #0b1120;
                border: 1px solid rgba(56, 189, 248, 0.16);
                border-radius: 12px;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        # Top Header Bar: Title + New Chat
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(6, 4, 6, 4)

        title = QLabel("CONVERSATIONS")
        title.setFont(QFont("Consolas", 8, QFont.Bold))
        title.setStyleSheet("color: #38bdf8; letter-spacing: 1px;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        btn_new = QPushButton("+ New")
        btn_new.setFont(QFont("Consolas", 8, QFont.Bold))
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setStyleSheet("""
            QPushButton {
                background: rgba(56, 189, 248, 0.15);
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 4px;
                color: #38bdf8;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.35);
                color: #ffffff;
            }
        """)
        btn_new.clicked.connect(self.new_chat_requested.emit)
        top_bar.addWidget(btn_new)
        root_layout.addLayout(top_bar)

        # Search / Filter Bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search history...")
        self._search_input.setFont(QFont("Segoe UI", 8))
        self._search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 6px;
                color: #e2e8f0;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
        """)
        self._search_input.textChanged.connect(self._filter_sessions)
        root_layout.addWidget(self._search_input)

        # Scrollable Sessions Feed
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
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
        self._items_layout = QVBoxLayout(self._container)
        self._items_layout.setContentsMargins(0, 0, 4, 0)
        self._items_layout.setSpacing(6)
        self._items_layout.addStretch()

        scroll.setWidget(self._container)
        root_layout.addWidget(scroll)

    def reload_history(self):
        """Read Data/ChatLog.json and parse paired turns."""
        self._raw_sessions = []
        if CHAT_LOG_PATH.exists():
            try:
                with open(CHAT_LOG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    i = 0
                    while i < len(data):
                        entry = data[i]
                        if entry.get("role") == "user":
                            prompt = str(entry.get("content", "")).strip()
                            timestamp = entry.get("timestamp", "")
                            topic = entry.get("topic", "General")
                            resp = ""
                            if i + 1 < len(data) and data[i + 1].get("role") == "assistant":
                                resp = str(data[i + 1].get("content", "")).strip()
                                i += 1
                            if prompt:
                                self._raw_sessions.append({
                                    "prompt": prompt,
                                    "response": resp,
                                    "timestamp": timestamp,
                                    "topic": topic,
                                })
                        i += 1
            except Exception as e:
                logger.debug(f"[ChatHistorySidebar] Error parsing ChatLog: {e}")

        self._render_items(self._raw_sessions)

    def _render_items(self, sessions: List[Dict[str, Any]]):
        # Clear existing
        while self._items_layout.count() > 1:
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Display reversed (newest first) up to 25 items
        for s in reversed(sessions[-25:]):
            card = HistorySessionItem(
                prompt=s["prompt"],
                response=s["response"],
                timestamp=s.get("timestamp", ""),
                topic=s.get("topic", "General"),
                parent=self,
            )
            card.clicked.connect(self.history_item_selected.emit)
            self._items_layout.insertWidget(self._items_layout.count() - 1, card)

    def _filter_sessions(self, query: str):
        query = query.strip().lower()
        if not query:
            self._render_items(self._raw_sessions)
            return

        filtered = [
            s for s in self._raw_sessions
            if query in s["prompt"].lower() or query in s["response"].lower() or query in s.get("topic", "").lower()
        ]
        self._render_items(filtered)
