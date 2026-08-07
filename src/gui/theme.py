"""
AuraAI GUI Theme System
========================
Glassmorphism dark-mode design tokens, color palette, and QSS stylesheet builder.
Inspired by Raycast, Arc, and Linear App.
"""


from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase

# =============================================================================
# COLOR PALETTE
# =============================================================================

class Colors:
    """Centralized color definitions."""
    
    # Backgrounds
    BG_DEEP          = "#0B0F17"
    BG_SLATE         = "#0F172A"
    BG_CARD          = "#1E293B"
    BG_CARD_HOVER    = "#334155"
    BG_INPUT         = "#1E293B"
    BG_TOOLBAR       = "#0F172A"
    BG_OVERLAY       = "rgba(11, 15, 23, 0.85)"
    BG_SIDEBAR       = "#0F172A"
    
    # Accents
    CYAN             = "#06B6D4"
    CYAN_GLOW        = "#22D3EE"
    PURPLE           = "#6366F1"
    PURPLE_GLOW      = "#818CF8"
    
    # Gradients (for borders / glows)
    BORDER_GRADIENT  = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #06B6D4, stop:1 #6366F1)"
    GLOW_GRADIENT    = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22D3EE, stop:1 #818CF8)"
    
    # Status
    SUCCESS          = "#10B981"
    WARNING          = "#F59E0B"
    ERROR            = "#F43F5E"
    INFO             = "#3B82F6"
    
    # Text
    TEXT_PRIMARY     = "#F8FAFC"
    TEXT_SECONDARY   = "#94A3B8"
    TEXT_MUTED       = "#64748B"
    TEXT_DISABLED    = "#475569"
    
    # Borders
    BORDER_SUBTLE    = "#1E293B"
    BORDER_ACTIVE    = "#334155"
    
    # Overlay-specific
    OVERLAY_BG       = "rgba(15, 23, 42, 0.88)"
    OVERLAY_BORDER   = "rgba(34, 211, 238, 0.25)"


# =============================================================================
# TYPOGRAPHY
# =============================================================================

class Typography:
    """Font configurations."""
    
    FAMILY = "Inter, Segoe UI, -apple-system, sans-serif"
    
    @classmethod
    def font(cls, size: int, weight: int = QFont.Weight.Normal, bold: bool = False) -> QFont:
        f = QFont(cls.FAMILY.split(",")[0].strip(), size)
        f.setWeight(QFont.Weight.Bold if bold else weight)
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return f
    
    H1       = lambda: Typography.font(24, bold=True)
    H2       = lambda: Typography.font(18, bold=True)
    H3       = lambda: Typography.font(14, bold=True)
    BODY     = lambda: Typography.font(13)
    CAPTION  = lambda: Typography.font(11)
    MONO     = lambda: Typography.font(12, weight=QFont.Weight.Medium)


# =============================================================================
# SPACING & SIZING
# =============================================================================

class Spacing:
    XS  = 4
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 24
    XXL = 32

class Radius:
    SM  = "6px"
    MD  = "10px"
    LG  = "14px"
    XL  = "20px"
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

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QSize
from PySide6.QtWidgets import QWidget

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
    def slide_up(widget: QWidget, distance: int = 20, duration: int = 300) -> QPropertyAnimation:
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

