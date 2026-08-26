"""
AuraAI GUI Theme System
========================
Glassmorphism dark-mode design tokens, color palette, and QSS stylesheet builder.
Inspired by Raycast, Arc, and Linear App.
"""

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget

# =============================================================================
# COLOR PALETTE
# =============================================================================


class Colors:
    """Centralized color definitions for AuraAI Cyber-HUD."""

    # Backgrounds
    BG_DEEP = "#0d1117"
    BG_SLATE = "#121722"
    BG_SURFACE = "#161c28"
    BG_CARD = "rgba(22, 28, 40, 0.85)"
    BG_CARD_HOVER = "rgba(32, 42, 60, 0.95)"
    BG_INPUT = "rgba(18, 23, 34, 0.9)"
    BG_TOOLBAR = "#0e131d"
    BG_OVERLAY = "rgba(16, 20, 28, 0.92)"
    BG_SIDEBAR = "#0c1017"

    # Accents (Cyber Neon)
    CYAN = "#00e5ff"
    CYAN_GLOW = "#33eeff"
    CYAN_DIM = "rgba(0, 229, 255, 0.15)"
    BLUE = "#50aaff"
    BLUE_GLOW = "#80c4ff"
    PURPLE = "#818cf8"
    PURPLE_GLOW = "#a5b4fc"
    EMERALD = "#10b981"
    AMBER = "#fbbf24"
    CRIMSON = "#f43f5e"

    # Gradients
    BORDER_GRADIENT = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00e5ff, stop:1 #818cf8)"
    )
    GLOW_GRADIENT = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33eeff, stop:1 #a5b4fc)"
    )

    # Status
    SUCCESS = "#10b981"
    WARNING = "#fbbf24"
    ERROR = "#f43f5e"
    INFO = "#50aaff"

    # Text
    TEXT_PRIMARY = "#f3f6fc"
    TEXT_SECONDARY = "#a5b4cb"
    TEXT_MUTED = "#627289"
    TEXT_DISABLED = "#3e4c60"

    # Borders
    BORDER_SUBTLE = "rgba(255, 255, 255, 0.08)"
    BORDER_ACTIVE = "rgba(0, 229, 255, 0.4)"
    BORDER_ACCENT = "rgba(0, 229, 255, 0.85)"

    # Overlay-specific
    OVERLAY_BG = "rgba(16, 20, 28, 0.92)"
    OVERLAY_BORDER = "rgba(0, 229, 255, 0.45)"


# =============================================================================
# TYPOGRAPHY
# =============================================================================


class Typography:
    """Font configurations."""

    FAMILY = "Inter, Segoe UI, -apple-system, sans-serif"

    @classmethod
    def font(
        cls, size: int, weight: int = QFont.Weight.Normal, bold: bool = False
    ) -> QFont:
        f = QFont(cls.FAMILY.split(",")[0].strip(), size)
        f.setWeight(QFont.Weight.Bold if bold else weight)
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return f

    @classmethod
    def H1(cls) -> QFont:
        return cls.font(24, bold=True)

    @classmethod
    def H2(cls) -> QFont:
        return cls.font(18, bold=True)

    @classmethod
    def H3(cls) -> QFont:
        return cls.font(14, bold=True)

    @classmethod
    def BODY(cls) -> QFont:
        return cls.font(13)

    @classmethod
    def CAPTION(cls) -> QFont:
        return cls.font(11)

    @classmethod
    def MONO(cls) -> QFont:
        return cls.font(12, weight=QFont.Weight.Medium)


# =============================================================================
# SPACING & SIZING
# =============================================================================


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Radius:
    SM = "6px"
    MD = "10px"
    LG = "14px"
    XL = "20px"
    PILL = "9999px"


# =============================================================================
# QSS STYLESHEET BUILDER
# =============================================================================


def build_global_stylesheet() -> str:
    """Returns the global QSS stylesheet for AuraAI."""
    return f"""
    /* ── Global ── */
    QWidget {{
        font-family: {Typography.FAMILY};
        color: {Colors.TEXT_PRIMARY};
        background: {Colors.BG_DEEP};
        outline: none;
        border: none;
    }}
    
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical {{
        background: {Colors.BORDER_ACTIVE};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {Colors.TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 0px;
        border-radius: 3px;
    }}
    QScrollBar::handle:horizontal {{
        background: {Colors.BORDER_ACTIVE};
        border-radius: 3px;
        min-width: 30px;
    }}
    
    /* ── Glass Card ── */
    .GlassCard {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
    }}
    .GlassCard:hover {{
        border: 1px solid {Colors.BORDER_ACTIVE};
    }}
    
    /* ── Input Fields ── */
    QLineEdit {{
        background: {Colors.BG_INPUT};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        padding: 10px 14px;
        font-size: 14px;
        color: {Colors.TEXT_PRIMARY};
        selection-background-color: {Colors.CYAN};
    }}
    QLineEdit:focus {{
        border: 1px solid {Colors.CYAN};
    }}
    QLineEdit::placeholder {{
        color: {Colors.TEXT_MUTED};
    }}
    
    /* ── Buttons ── */
    QPushButton {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        padding: 8px 16px;
        font-size: 13px;
        color: {Colors.TEXT_PRIMARY};
    }}
    QPushButton:hover {{
        background: {Colors.BG_CARD_HOVER};
        border: 1px solid {Colors.BORDER_ACTIVE};
    }}
    QPushButton:pressed {{
        background: {Colors.BG_INPUT};
    }}
    
    QPushButton.Primary {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {Colors.CYAN}, stop:1 {Colors.PURPLE});
        color: {Colors.BG_DEEP};
        border: none;
        font-weight: bold;
    }}
    QPushButton.Primary:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {Colors.CYAN_GLOW}, stop:1 {Colors.PURPLE_GLOW});
    }}
    
    QPushButton.Danger {{
        background: {Colors.ERROR};
        color: white;
        border: none;
    }}
    
    /* ── Text Edit / Markdown ── */
    QTextEdit {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        padding: 12px;
        font-size: 13px;
        color: {Colors.TEXT_PRIMARY};
        line-height: 1.6;
    }}
    QTextEdit:focus {{
        border: 1px solid {Colors.CYAN};
    }}
    
    /* ── List / Tree ── */
    QListWidget {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget::item {{
        background: transparent;
        border-radius: {Radius.SM};
        padding: 8px 12px;
        margin: 2px 4px;
    }}
    QListWidget::item:selected {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_ACTIVE};
    }}
    QListWidget::item:hover {{
        background: {Colors.BG_CARD};
    }}
    
    /* ── Combo Box ── */
    QComboBox {{
        background: {Colors.BG_INPUT};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        padding: 6px 12px;
        min-width: 120px;
    }}
    QComboBox:hover {{
        border: 1px solid {Colors.BORDER_ACTIVE};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        selection-background-color: {Colors.BG_CARD_HOVER};
        padding: 4px;
    }}
    
    /* ── Progress Bar ── */
    QProgressBar {{
        background: {Colors.BG_INPUT};
        border: none;
        border-radius: {Radius.PILL};
        height: 6px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {Colors.CYAN}, stop:1 {Colors.PURPLE});
        border-radius: {Radius.PILL};
    }}
    
    /* ── Tooltips ── */
    QToolTip {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_ACTIVE};
        border-radius: {Radius.SM};
        color: {Colors.TEXT_PRIMARY};
        padding: 6px 10px;
        font-size: 12px;
    }}
    
    /* ── Splitter ── */
    QSplitter::handle {{
        background: {Colors.BORDER_SUBTLE};
    }}
    QSplitter::handle:horizontal {{
        width: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 2px;
    }}
    QSplitter::handle:hover {{
        background: {Colors.CYAN};
    }}
    """


def apply_theme(app) -> None:
    """Applies the global stylesheet to the QApplication instance."""
    if hasattr(app, "setStyleSheet"):
        app.setStyleSheet(build_global_stylesheet())


def overlay_stylesheet() -> str:
    """QSS specific to the Overlay (Spotlight HUD)."""
    return f"""
    #OverlayWindow {{
        background: {Colors.OVERLAY_BG};
        border: 1.5px solid {Colors.OVERLAY_BORDER};
        border-radius: {Radius.LG};
    }}
    
    #OmniInput {{
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.LG};
        padding: 14px 18px;
        font-size: 16px;
        color: {Colors.TEXT_PRIMARY};
        selection-background-color: {Colors.CYAN};
    }}
    #OmniInput:focus {{
        border: 1.5px solid {Colors.CYAN};
    }}
    
    #StepCard {{
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        padding: 10px 14px;
    }}
    
    #StatusPill {{
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.PILL};
        padding: 4px 12px;
        font-size: 11px;
        color: {Colors.TEXT_SECONDARY};
    }}
    #StatusPill.Active {{
        border: 1px solid {Colors.CYAN};
        color: {Colors.CYAN_GLOW};
        background: rgba(6, 182, 212, 0.1);
    }}
    """


def main_window_stylesheet() -> str:
    """QSS specific to the Main Control Center."""
    return f"""
    #MainWindow {{
        background: {Colors.BG_DEEP};
    }}
    
    #NavRail {{
        background: {Colors.BG_SIDEBAR};
        border-right: 1px solid {Colors.BORDER_SUBTLE};
    }}
    
    #NavButton {{
        background: transparent;
        border: none;
        border-radius: {Radius.MD};
        padding: 12px;
        color: {Colors.TEXT_MUTED};
        font-size: 11px;
    }}
    #NavButton:hover {{
        background: {Colors.BG_CARD};
        color: {Colors.TEXT_SECONDARY};
    }}
    #NavButton:checked {{
        background: {Colors.BG_CARD};
        color: {Colors.CYAN_GLOW};
        border-left: 2px solid {Colors.CYAN};
    }}
    
    #CenterStage {{
        background: {Colors.BG_DEEP};
    }}
    
    #InspectorDrawer {{
        background: {Colors.BG_SLATE};
        border-left: 1px solid {Colors.BORDER_SUBTLE};
    }}
    
    #ChatBubbleUser {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.MD};
        border-bottom-right-radius: 2px;
        padding: 12px 16px;
    }}
    #ChatBubbleAgent {{
        background: rgba(6, 182, 212, 0.08);
        border: 1px solid rgba(6, 182, 212, 0.2);
        border-radius: {Radius.MD};
        border-bottom-left-radius: 2px;
        padding: 12px 16px;
    }}
    
    #TaskNode {{
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_SUBTLE};
        border-radius: {Radius.SM};
        padding: 8px 12px;
        min-width: 140px;
    }}
    #TaskNode.Running {{
        border: 1px solid {Colors.WARNING};
        background: rgba(245, 158, 11, 0.08);
    }}
    #TaskNode.Completed {{
        border: 1px solid {Colors.SUCCESS};
        background: rgba(16, 185, 129, 0.08);
    }}
    #TaskNode.Failed {{
        border: 1px solid {Colors.ERROR};
        background: rgba(244, 63, 94, 0.08);
    }}
    """


# =============================================================================
# ANIMATION HELPERS
# =============================================================================


class Animations:
    """Reusable animation presets."""

    @staticmethod
    def fade_in(widget: QWidget, duration: int = 250) -> QPropertyAnimation:
        anim = QPropertyAnimation(widget, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        return anim

    @staticmethod
    def slide_up(
        widget: QWidget, distance: int = 20, duration: int = 300
    ) -> QPropertyAnimation:
        anim = QPropertyAnimation(widget, b"pos")
        anim.setDuration(duration)
        start_pos = widget.pos() + QPoint(0, distance)
        anim.setStartValue(start_pos)
        anim.setEndValue(widget.pos())
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    @staticmethod
    def pulse_glow(widget: QWidget, property_name: bytes, duration: int = 1500):
        """Creates a pulsing opacity animation for glow effects."""
        anim = QPropertyAnimation(widget, property_name)
        anim.setDuration(duration)
        anim.setStartValue(0.4)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)  # Infinite
        return anim
