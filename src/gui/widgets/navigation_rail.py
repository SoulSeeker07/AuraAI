"""
NavigationRail Widget
=====================
Left sidebar icon rail for switching between MainWindow tabs.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy, QSpacerItem, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from src.gui.theme import Colors, Radius, Typography, Spacing


class NavButton(QPushButton):
    """Custom checkable nav button with icon and label."""
    
    def __init__(self, icon_text: str, label: str, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(64, 64)
        self.setText(f"{icon_text}\n{label}")
        self.setFont(Typography.CAPTION())
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: {Radius.MD};
                color: {Colors.TEXT_MUTED};
                padding: 8px;
            }}
            QPushButton:hover {{
                background: {Colors.BG_CARD};
                color: {Colors.TEXT_SECONDARY};
            }}
            QPushButton:checked {{
                background: {Colors.BG_CARD};
                color: {Colors.CYAN_GLOW};
                border-left: 2px solid {Colors.CYAN};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class NavigationRail(QWidget):
    """Left navigation rail emitting tab change signals."""
    
    tab_changed = Signal(int)
    
    TABS = [
        ("💬", "Chat"),
        ("🧠", "DAG"),
        ("👁️", "Observer"),
        ("📚", "Memory"),
        ("⚙️", "Settings"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NavRail")
        self.setFixedWidth(72)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {Colors.BG_SIDEBAR}; border-right: 1px solid {Colors.BORDER_SUBTLE};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, Spacing.LG, 4, Spacing.LG)
        layout.setSpacing(4)
        
        # Logo / Top spacer
        logo = QLabel("✦")
        logo.setStyleSheet(f"color: {Colors.CYAN}; font-size: 24px; background: transparent; border: none;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(48)
        layout.addWidget(logo)
        layout.addSpacing(Spacing.XL)
        
        self._buttons: list[NavButton] = []
        for idx, (icon, label) in enumerate(self.TABS):
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda checked, i=idx: self._on_tab_clicked(i))
            self._buttons.append(btn)
            layout.addWidget(btn)
        
        self._buttons[0].setChecked(True)
        layout.addStretch()
    
    def _on_tab_clicked(self, index: int):
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
        self.tab_changed.emit(index)