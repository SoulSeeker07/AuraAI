"""
ChatBubble & ChatStreamWidget
===============================
Rich chat message components for the MainWindow execution feed.
Supports markdown rendering, streaming text, and code blocks.
"""

import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.signals import app_signals
from gui.theme import Radius, Spacing


class ChatBubble(QWidget):
    """
    A styled chat bubble for user or agent messages using QLabel for high-visibility text.

    Args:
        sender: "user" or "agent"
        content: Message text (supports basic markdown)
        parent: Parent widget
    """

    def __init__(self, sender: str, content: str, parent=None):
        super().__init__(parent)
        self._sender = sender
        self._content = content

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._setup_ui()
        self._render_content()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)

        is_user = self._sender == "user"

        if is_user:
            layout.addStretch()

        self._bubble = QLabel()
        self._bubble.setWordWrap(True)
        self._bubble.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._bubble.setMinimumWidth(180)
        self._bubble.setMaximumWidth(700)

        if is_user:
            self._bubble.setStyleSheet(f"""
                QLabel {{
                    background-color: #1E293B;
                    border: 1px solid #334155;
                    border-radius: {Radius.MD};
                    border-bottom-right-radius: 2px;
                    padding: 12px 16px;
                    font-size: 13px;
                    color: #FFFFFF;
                }}
            """)
        else:
            self._bubble.setStyleSheet(f"""
                QLabel {{
                    background-color: #0F172A;
                    border: 1px solid rgba(6, 182, 212, 0.35);
                    border-radius: {Radius.MD};
                    border-bottom-left-radius: 2px;
                    padding: 12px 16px;
                    font-size: 13px;
                    color: #F8FAFC;
                }}
            """)

        layout.addWidget(self._bubble)

        if not is_user:
            layout.addStretch()

    def _render_content(self):
        html = self._markdown_to_html(self._content)
        self._bubble.setText(html)

    def _markdown_to_html(self, text: str) -> str:
        if not text:
            return ""
        is_user = self._sender == "user"
        text_color = "#FFFFFF" if is_user else "#F8FAFC"

        # Escape HTML
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Bold & Italic
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)

        # Inline code
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background:#020617;padding:2px 6px;border-radius:4px;color:#22D3EE;font-family:Consolas,monospace;font-size:12px;">\1</code>',
            text,
        )

        # Code blocks
        text = re.sub(
            r"```(\w+)?\n(.*?)```",
            r'<pre style="background:#020617;padding:10px;border-radius:6px;border:1px solid #1E293B;margin:6px 0;"><code style="color:#CBD5E1;font-family:Consolas,monospace;font-size:12px;">\2</code></pre>',
            text,
            flags=re.DOTALL,
        )

        # Newlines
        text = text.replace("\n", "<br>")

        return f"<div style=\"font-family:'Segoe UI', sans-serif; font-size:13px; color:{text_color}; line-height:1.5;\">{text}</div>"

    def append_text(self, text: str):
        self._content += text
        self._render_content()


class ChatStreamWidget(QFrame):
    """
    Scrollable chat feed that auto-connects to app_signals.
    Handles both complete messages and streaming tokens.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bubbles: list[ChatBubble] = []
        self._current_stream_bubble: ChatBubble | None = None

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch()

        # Connect signals
        app_signals.message_received.connect(self._on_message_received)
        app_signals.message_stream.connect(self._on_message_stream)

    def _on_message_received(self, sender: str, content: str, is_user: bool):
        self._current_stream_bubble = None
        bubble = ChatBubble("user" if is_user else "agent", content)
        self._bubbles.append(bubble)

        layout = self.layout()
        layout.insertWidget(layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _on_message_stream(self, token: str):
        if self._current_stream_bubble is None:
            self._current_stream_bubble = ChatBubble("agent", "")
            self._bubbles.append(self._current_stream_bubble)
            layout = self.layout()
            layout.insertWidget(layout.count() - 1, self._current_stream_bubble)

        self._current_stream_bubble.append_text(token)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        scroll_area = self.parentWidget()
        while scroll_area and not isinstance(scroll_area, QScrollArea):
            scroll_area = scroll_area.parentWidget()
        if scroll_area:
            QTimer.singleShot(
                50,
                lambda: scroll_area.verticalScrollBar().setValue(
                    scroll_area.verticalScrollBar().maximum()
                ),
            )

    def clear(self):
        while self.layout().count() > 1:
            widget = self.layout().takeAt(0).widget()
            if widget:
                widget.deleteLater()
        self._bubbles.clear()
        self._current_stream_bubble = None
