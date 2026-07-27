from dataclasses import dataclass

from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class AuraPalette:
    background: str = "#0f1217"
    surface: str = "#151a21"
    elevated: str = "#1a2028"
    sidebar: str = "#171b22"
    border: str = "rgba(255, 255, 255, 28)"
    text: str = "#f7f8fb"
    muted: str = "rgba(247, 248, 251, 145)"
    faint: str = "rgba(247, 248, 251, 95)"
    accent: str = "#74d7c4"
    accent_hover: str = "#8ee2d2"
    danger: str = "#ff6b7a"


PALETTE = AuraPalette()


def app_stylesheet() -> str:
    p = PALETTE
    return f"""
    QMainWindow {{
        background: transparent;
    }}
    QWidget {{
        background: {p.background};
        color: {p.text};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }}
    #windowShadowHost {{
        background: transparent;
    }}
    #windowFrame {{
        background: {p.background};
        border: 1px solid {p.border};
        border-radius: 16px;
    }}
    #titleBar {{
        background: {p.background};
        border-top-left-radius: 16px;
        border-top-right-radius: 16px;
    }}
    #titleLabel {{
        font-size: 14px;
        font-weight: 750;
    }}
    #titleButton {{
        background: transparent;
        border: none;
        border-radius: 8px;
        color: {p.muted};
        font-size: 15px;
        font-weight: 700;
        min-height: 30px;
        min-width: 34px;
        padding: 0;
    }}
    #titleButton:hover {{
        background: rgba(255, 255, 255, 18);
        color: {p.text};
    }}
    #closeButton {{
        background: transparent;
        border: none;
        border-radius: 8px;
        color: {p.muted};
        font-size: 16px;
        font-weight: 700;
        min-height: 30px;
        min-width: 34px;
        padding: 0;
    }}
    #closeButton:hover {{
        background: {p.danger};
        color: #ffffff;
    }}
    #sidebar {{
        background: {p.sidebar};
        border-bottom-left-radius: 16px;
        border-right: 1px solid {p.border};
    }}
    #brand {{
        font-size: 28px;
        font-weight: 800;
    }}
    #pageTitle {{
        font-size: 28px;
        font-weight: 750;
    }}
    #sectionTitle {{
        font-size: 16px;
        font-weight: 700;
        margin-top: 10px;
    }}
    #status {{
        color: rgba(247, 248, 251, 185);
        font-size: 14px;
    }}
    #muted, #hint {{
        color: {p.muted};
        font-size: 13px;
    }}
    #hint {{
        line-height: 1.35;
    }}
    #navItem {{
        color: rgba(247, 248, 251, 185);
        padding: 9px 10px;
        border-radius: 8px;
    }}
    #navItem:hover {{
        background: rgba(255, 255, 255, 16);
    }}
    QPushButton {{
        background: {p.accent};
        border: none;
        border-radius: 8px;
        color: #08110f;
        font-weight: 700;
        padding: 11px 14px;
    }}
    QPushButton:hover {{
        background: {p.accent_hover};
    }}
    #secondaryButton {{
        background: rgba(255, 255, 255, 14);
        border: 1px solid rgba(255, 255, 255, 30);
        color: {p.text};
    }}
    #secondaryButton:hover {{
        background: rgba(255, 255, 255, 22);
    }}
    #secondaryButton:checked {{
        background: {p.accent};
        color: #08110f;
    }}
    #metricCard {{
        background: {p.elevated};
        border: 1px solid {p.border};
        border-radius: 8px;
    }}
    #cardTitle {{
        color: rgba(247, 248, 251, 150);
        font-size: 12px;
        font-weight: 650;
        text-transform: uppercase;
    }}
    #cardValue {{
        font-size: 21px;
        font-weight: 760;
    }}
    QListWidget {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 8px;
        outline: none;
    }}
    QListWidget::item {{
        border-radius: 6px;
        padding: 10px;
        margin: 2px;
    }}
    QListWidget::item:alternate {{
        background: rgba(255, 255, 255, 10);
    }}
    QListWidget::item:selected {{
        background: rgba(116, 215, 196, 55);
    }}
    #overlayPanel {{
        background: rgba(20, 24, 32, 240);
        border: 1px solid rgba(255, 255, 255, 42);
        border-radius: 18px;
    }}
    #overlayTitle {{
        font-size: 24px;
        font-weight: 760;
    }}
    #overlaySubtitle, #overlayTools {{
        color: {p.muted};
        font-size: 13px;
    }}
    QLineEdit {{
        background: rgba(255, 255, 255, 16);
        border: 1px solid rgba(255, 255, 255, 38);
        border-radius: 10px;
        color: #ffffff;
        font-size: 17px;
        padding: 13px 15px;
        selection-background-color: {p.accent};
    }}
    QLineEdit:focus {{
        border-color: {p.accent};
    }}
    #overlayResponse {{
        background: rgba(255, 255, 255, 10);
        border: 1px solid rgba(255, 255, 255, 24);
        border-radius: 10px;
        color: rgba(247, 248, 251, 210);
        font-size: 13px;
        padding: 10px 12px;
    }}
    """


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(app_stylesheet())
