"""
Main Control Center Window
==========================
Full multi-panel interface for deep tasks, DAG visualization,
memory management, and system monitoring.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStackedWidget, QLineEdit, QPushButton, QSplitter, QFrame,
    QSizePolicy, QApplication, QScrollArea
)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QFont, QColor, QPalette

from src.gui.theme import (
    Colors, Radius, Typography, Spacing, 
    build_global_stylesheet, main_window_stylesheet
)
from src.gui.signals import app_signals
from src.gui.widgets import (
    NavigationRail, ChatStreamWidget, DagVisualizer,
    InspectorDrawer, StatusPill
)


class MainWindow(QMainWindow):
    """
    Mode B: Full Control Center.
    Layout: Nav Rail | Center Stage | Inspector Drawer
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.setWindowTitle("AuraAI Control Center")
        self.setMinimumSize(1200, 800)
        
        # Frameless with custom titlebar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Apply stylesheets
        self.setStyleSheet(build_global_stylesheet() + main_window_stylesheet())
        
        self._setup_ui()
        self._setup_titlebar()
        self._connect_signals()
        self._center_window()
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ── Left Navigation Rail ──
        self._nav = NavigationRail()
        self._nav.tab_changed.connect(self._on_tab_changed)
        layout.addWidget(self._nav)
        
        # ── Center Stage ──
        self._center_stack = QStackedWidget()
        self._center_stack.setObjectName("CenterStage")
        
        # Tab 0: Chat / Execution Feed
        self._chat_tab = self._build_chat_tab()
        self._center_stack.addWidget(self._chat_tab)
        
        # Tab 1: DAG Visualizer
        self._dag_tab = DagVisualizer()
        self._center_stack.addWidget(self._dag_tab)
        
        # Tab 2: World Observer
        self._observer_tab = self._build_observer_tab()
        self._center_stack.addWidget(self._observer_tab)
        
        # Tab 3: Memory Base
        self._memory_tab = self._build_memory_tab()
        self._center_stack.addWidget(self._memory_tab)
        
        # Tab 4: Settings
        self._settings_tab = self._build_settings_tab()
        self._center_stack.addWidget(self._settings_tab)
        
        layout.addWidget(self._center_stack, 1)
        
        # ── Right Inspector Drawer ──
        self._inspector = InspectorDrawer()
        layout.addWidget(self._inspector)
    
    def _setup_titlebar(self):
        """Custom draggable titlebar overlay."""
        self._titlebar = QFrame(self)
        self._titlebar.setFixedHeight(40)
        self._titlebar.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SLATE};
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }}
        """)
        
        tb_layout = QHBoxLayout(self._titlebar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        tb_layout.setSpacing(12)
        
        title = QLabel("AuraAI Control Center")
        title.setFont(Typography.BODY())
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none; font-weight: 600;")
        tb_layout.addWidget(title)
        
        tb_layout.addStretch()
        
        # Window controls
        for sym, color, action in [("−", Colors.TEXT_MUTED, self.showMinimized),
                                   ("□", Colors.TEXT_MUTED, self._toggle_maximize),
                                   ("✕", Colors.ERROR, self.close)]:
            btn = QPushButton(sym)
            btn.setFixedSize(32, 32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: {Radius.SM};
                    color: {color};
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background: {Colors.BG_CARD};
                }}
            """)
            btn.clicked.connect(action)
            tb_layout.addWidget(btn)
        
        # Position titlebar at top
        self._titlebar.setGeometry(0, 0, self.width(), 40)
    
    def _build_chat_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(Spacing.LG, 52, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)
        
        # Header
        header = QHBoxLayout()
        header_title = QLabel("💬 Live Assistant")
        header_title.setFont(Typography.H2())
        header_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        header.addWidget(header_title)
        
        self._status_indicator = StatusPill("●", "Idle", active=False)
        header.addWidget(self._status_indicator)
        header.addStretch()
        layout.addLayout(header)
        
        # Chat stream
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        self._chat_stream = ChatStreamWidget()
        scroll.setWidget(self._chat_stream)
        layout.addWidget(scroll, 1)
        
        # Input
        input_layout = QHBoxLayout()
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Type a message or command...")
        self._chat_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: {Radius.MD};
                padding: 10px 14px;
                font-size: 13px;
                color: #FFFFFF;
            }}
            QLineEdit:focus {{
                border: 1px solid #06B6D4;
            }}
            QLineEdit::placeholder {{
                color: #94A3B8;
            }}
        """)
        self._chat_input.returnPressed.connect(self._on_chat_submit)
        input_layout.addWidget(self._chat_input)
        
        send_btn = QPushButton("➤")
        send_btn.setObjectName("Primary")
        send_btn.setFixedSize(40, 40)
        send_btn.clicked.connect(self._on_chat_submit)
        input_layout.addWidget(send_btn)
        
        layout.addLayout(input_layout)
        return tab
    
    def _build_observer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(Spacing.LG, 52, Spacing.LG, Spacing.LG)
        
        title = QLabel("👁️ World Observer")
        title.setFont(Typography.H2())
        layout.addWidget(title)
        
        self._observer_feed = QLabel("Waiting for WorldStateObserver data...")
        self._observer_feed.setWordWrap(True)
        self._observer_feed.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(self._observer_feed)
        layout.addStretch()
        return tab
    
    def _build_memory_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(Spacing.LG, 52, Spacing.LG, Spacing.LG)
        
        title = QLabel("📚 Memory & Knowledge Base")
        title.setFont(Typography.H2())
        layout.addWidget(title)
        
        search = QLineEdit()
        search.setPlaceholderText("Search memories...")
        layout.addWidget(search)
        
        self._memory_grid = QLabel("Memory entries will appear here as cards.")
        self._memory_grid.setWordWrap(True)
        self._memory_grid.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(self._memory_grid)
        layout.addStretch()
        return tab
    
    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(Spacing.LG, 52, Spacing.LG, Spacing.LG)
        
        title = QLabel("⚙️ Settings & Backends")
        title.setFont(Typography.H2())
        layout.addWidget(title)
        
        # Provider selector
        layout.addWidget(QLabel("AI Provider"))
        self._provider_combo = QPushButton("Groq (Active)")
        self._provider_combo.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD};
                padding: 10px 14px;
                text-align: left;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(self._provider_combo)
        layout.addStretch()
        return tab
    
    def _connect_signals(self):
        app_signals.execution_started.connect(
            lambda _: self._status_indicator.set_active(True) or self._status_indicator.set_label("Running")
        )
        app_signals.execution_finished.connect(
            lambda _, __: self._status_indicator.set_active(False) or self._status_indicator.set_label("Idle")
        )
        app_signals.world_state_changed.connect(self._on_world_state)
        app_signals.toggle_inspector.connect(self._inspector.toggle)
    
    def _on_tab_changed(self, index: int):
        self._center_stack.setCurrentIndex(index)
    
    def _on_chat_submit(self):
        text = self._chat_input.text().strip()
        if text:
            app_signals.message_received.emit("user", text, True)
            self._chat_input.clear()
    
    def _on_world_state(self, snapshot):
        text = f"Window: {snapshot.focused_window}\nURL: {snapshot.active_url}\nMouse: {snapshot.mouse_position}"
        self._observer_feed.setText(text)
    
    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
    
    def _center_window(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_titlebar'):
            self._titlebar.setGeometry(0, 0, self.width(), 40)
    
    def mousePressEvent(self, event):
        if event.position().y() <= 40:
            self._drag_pos = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_pos') and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint()