"""
Sci-Fi Styled Code Block Widget for AuraAI
==========================================
Location: src/gui/widgets/code_block_widget.py

Renders code blocks with syntax styling, language badges, and one-click copy buttons.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CodeBlockWidget(QFrame):
    """Sleek syntax-styled code block with copy button."""

    def __init__(self, code: str, language: str = "code", parent: QWidget | None = None):
        super().__init__(parent)
        self.code = code.strip()
        self.language = language or "code"
        self._setup_ui()

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet("""
            CodeBlockWidget {
                background: #070c18;
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header ribbon
        ribbon = QFrame()
        ribbon.setFixedHeight(30)
        ribbon.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.85);
                border-bottom: 1px solid rgba(56, 189, 248, 0.15);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)
        r_layout = QHBoxLayout(ribbon)
        r_layout.setContentsMargins(10, 2, 10, 2)
        r_layout.setSpacing(6)

        lang_lbl = QLabel(self.language.upper())
        lang_lbl.setFont(QFont("Consolas", 8, QFont.Bold))
        lang_lbl.setStyleSheet("color: #38bdf8; background: transparent;")
        r_layout.addWidget(lang_lbl)

        r_layout.addStretch()

        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setFont(QFont("Segoe UI", 8))
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                color: #94a3b8;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background: rgba(56, 189, 248, 0.2);
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)
        self.copy_btn.clicked.connect(self._copy_code)
        r_layout.addWidget(self.copy_btn)

        layout.addWidget(ribbon)

        # Code display
        self.edit = QPlainTextEdit(self.code)
        self.edit.setReadOnly(True)
        self.edit.setFont(QFont("Consolas", 9))
        self.edit.setStyleSheet("""
            QPlainTextEdit {
                background: transparent;
                color: #e2e8f0;
                border: none;
                padding: 10px;
                font-family: Consolas, monospace;
            }
        """)
        # Dynamic height calculation
        line_count = len(self.code.splitlines())
        height = min(max(line_count * 19 + 25, 60), 380)
        self.edit.setFixedHeight(height)

        layout.addWidget(self.edit)

    def _copy_code(self):
        QGuiApplication.clipboard().setText(self.code)
        self.copy_btn.setText("✓ Copied!")
        QTimer.singleShot(1800, lambda: self.copy_btn.setText("📋 Copy"))
