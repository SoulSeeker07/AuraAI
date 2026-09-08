"""
Capability Dashboard Widget
===========================
Location: src/gui/widgets/capability_dashboard_widget.py

Live capability usage dashboard panel.
Shows coverage %, least-used capabilities, and most recently used capabilities.
Polls CapabilityUsageTracker every 3s via QTimer.

Embed in ChatRightRail by adding:
    from gui.widgets.capability_dashboard_widget import CapabilityDashboardWidget
    self._cap_dashboard = CapabilityDashboardWidget()
    layout.addWidget(self._cap_dashboard)
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy,
        QScrollArea,
    )
    from PySide6.QtGui import QColor, QPainter, QPen
    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False
    logger.debug("[CapabilityDashboard] PySide6 not available -- widget disabled")


_STYLE_CARD = """
    QFrame {
        background: #0d0d12;
        border: 1px solid rgba(124, 58, 237, 0.18);
        border-radius: 8px;
    }
"""
_STYLE_HEADER = "color: #c8c8d4; font-size: 13px; font-weight: 600; margin: 0;"
_STYLE_SUBTEXT = "color: #6b6b8a; font-size: 11px;"
_STYLE_COV_PCT = "color: #7c3aed; font-size: 28px; font-weight: 700;"
_STYLE_TABLE_LABEL = "color: #9090b0; font-size: 11px; font-weight: 600; margin-top: 8px;"
_STYLE_ROW_NAME = "color: #c0c0d8; font-size: 11px; padding: 2px 0;"
_STYLE_ROW_VAL = "color: #7c3aed; font-size: 11px; padding: 2px 0; text-align: right;"
_STYLE_NEVER = "color: #ef4444; font-size: 11px; padding: 2px 0;"
_STYLE_BAR_BG = "background: #1a1a2e; border-radius: 3px; min-height: 6px; max-height: 6px;"
_STYLE_BAR_FILL = "background: #7c3aed; border-radius: 3px; min-height: 6px; max-height: 6px;"


def _time_ago(ts: Optional[float]) -> str:
    if ts is None:
        return "never"
    diff = time.time() - ts
    if diff < 60:
        return f"{int(diff)}s ago"
    if diff < 3600:
        return f"{int(diff / 60)}m ago"
    if diff < 86400:
        return f"{int(diff / 3600)}h ago"
    return f"{int(diff / 86400)}d ago"


def _fmt_cap_id(cap_id: str) -> str:
    """Make capability IDs readable: 'power.battery' -> 'power > battery'"""
    return cap_id.replace(".", " > ")


if _PYSIDE6_AVAILABLE:

    class CapabilityDashboardWidget(QWidget):
        """
        Live capability usage dashboard.
        Polls CapabilityUsageTracker every POLL_MS milliseconds.
        """

        POLL_MS = 3000

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._tracker = None
            self._registry_ids: list[str] = []
            self._last_data: Optional[dict] = None
            self._setup_ui()
            self._setup_tracker()
            self._setup_timer()

        def _setup_ui(self) -> None:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(6)

            # Card frame
            card = QFrame()
            card.setStyleSheet(_STYLE_CARD)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(4)

            # Header row
            hdr_row = QHBoxLayout()
            hdr_row.setSpacing(0)
            self._header_label = QLabel("Capability Coverage")
            self._header_label.setStyleSheet(_STYLE_HEADER)
            self._pct_label = QLabel("--%")
            self._pct_label.setStyleSheet(_STYLE_COV_PCT)
            self._pct_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            hdr_row.addWidget(self._header_label)
            hdr_row.addStretch()
            hdr_row.addWidget(self._pct_label)
            card_layout.addLayout(hdr_row)

            # Sub-text
            self._sub_label = QLabel("Loading...")
            self._sub_label.setStyleSheet(_STYLE_SUBTEXT)
            card_layout.addWidget(self._sub_label)

            # Progress bar (two nested frames)
            bar_bg = QFrame()
            bar_bg.setStyleSheet(_STYLE_BAR_BG)
            bar_bg.setFixedHeight(6)
            bar_layout = QHBoxLayout(bar_bg)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(0)
            self._bar_fill = QFrame()
            self._bar_fill.setStyleSheet(_STYLE_BAR_FILL)
            self._bar_fill.setFixedHeight(6)
            self._bar_fill.setFixedWidth(0)
            self._bar_spacer = QWidget()
            self._bar_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            bar_layout.addWidget(self._bar_fill)
            bar_layout.addWidget(self._bar_spacer)
            card_layout.addWidget(bar_bg)
            self._bar_bg = bar_bg

            # Divider
            div = QFrame()
            div.setFrameShape(QFrame.HLine)
            div.setStyleSheet("color: rgba(124,58,237,0.12);")
            card_layout.addWidget(div)

            # Two-column table area
            tables_row = QHBoxLayout()
            tables_row.setSpacing(16)

            # Least used column
            least_col = QVBoxLayout()
            least_col.setSpacing(2)
            least_hdr = QLabel("Least Used")
            least_hdr.setStyleSheet(_STYLE_TABLE_LABEL)
            least_col.addWidget(least_hdr)
            self._least_layout = QVBoxLayout()
            self._least_layout.setSpacing(1)
            least_col.addLayout(self._least_layout)
            least_col.addStretch()
            tables_row.addLayout(least_col)

            # Most recent column
            recent_col = QVBoxLayout()
            recent_col.setSpacing(2)
            recent_hdr = QLabel("Last Used")
            recent_hdr.setStyleSheet(_STYLE_TABLE_LABEL)
            recent_col.addWidget(recent_hdr)
            self._recent_layout = QVBoxLayout()
            self._recent_layout.setSpacing(1)
            recent_col.addLayout(self._recent_layout)
            recent_col.addStretch()
            tables_row.addLayout(recent_col)

            card_layout.addLayout(tables_row)
            root.addWidget(card)

        def _setup_tracker(self) -> None:
            try:
                from core.capabilities.capability_usage_tracker import get_tracker
                self._tracker = get_tracker()
            except Exception as exc:
                logger.debug(f"[CapabilityDashboard] Tracker unavailable: {exc}")

            try:
                from core.capabilities.capability_registry import CapabilityRegistry
                reg = CapabilityRegistry.get_instance()
                self._registry_ids = [c.name for c in reg.list()]
            except Exception as exc:
                logger.debug(f"[CapabilityDashboard] Registry unavailable: {exc}")

        def _setup_timer(self) -> None:
            self._timer = QTimer(self)
            self._timer.setInterval(self.POLL_MS)
            self._timer.timeout.connect(self.refresh)
            self._timer.start()
            # Immediate first refresh
            QTimer.singleShot(100, self.refresh)

        def refresh(self) -> None:
            """Poll the tracker and update all UI elements."""
            if self._tracker is None:
                return
            try:
                # Re-fetch registry IDs in case new capabilities were registered
                try:
                    from core.capabilities.capability_registry import CapabilityRegistry
                    self._registry_ids = [c.name for c in CapabilityRegistry.get_instance().list()]
                except Exception:
                    pass

                data = self._tracker.export_dashboard_json(self._registry_ids)
                self._last_data = data
                self._render(data)

                # Export to storage/dashboard/dashboard.json for HTML view
                try:
                    from pathlib import Path
                    dash_file = Path(__file__).resolve().parents[3] / "storage" / "dashboard" / "dashboard.json"
                    self._tracker.export_dashboard_file(self._registry_ids, dash_file)
                except Exception as dash_err:
                    logger.debug(f"[CapabilityDashboard] dashboard.json export failed: {dash_err}")
            except Exception as exc:
                logger.debug(f"[CapabilityDashboard] refresh failed: {exc}")

        def _render(self, data: dict) -> None:
            cov = data.get("coverage", {})
            pct = cov.get("coverage_pct", 0.0)
            used = cov.get("used_at_least_once", 0)
            total = cov.get("total_registered", 0)
            never = cov.get("never_used", 0)

            self._pct_label.setText(f"{pct}%")
            self._sub_label.setText(
                f"{used} / {total} capabilities used - {never} never touched"
            )

            # Update progress bar width
            bar_w = self._bar_bg.width()
            fill_w = max(0, min(bar_w, int(bar_w * pct / 100.0)))
            self._bar_fill.setFixedWidth(fill_w)

            # Least used
            self._clear_layout(self._least_layout)
            for stat in data.get("least_used", [])[:10]:
                row = QHBoxLayout()
                row.setSpacing(4)
                name_lbl = QLabel(_fmt_cap_id(stat.get("capability_id", "")))
                style = _STYLE_NEVER if stat.get("usage_count", 0) == 0 else _STYLE_ROW_NAME
                name_lbl.setStyleSheet(style)
                name_lbl.setMaximumWidth(130)
                cnt_lbl = QLabel(f"{stat.get('usage_count', 0)}x")
                cnt_lbl.setStyleSheet(_STYLE_ROW_VAL)
                cnt_lbl.setAlignment(Qt.AlignRight)
                row.addWidget(name_lbl)
                row.addStretch()
                row.addWidget(cnt_lbl)
                container = QWidget()
                container.setLayout(row)
                self._least_layout.addWidget(container)

            # Most recent
            self._clear_layout(self._recent_layout)
            for stat in data.get("most_recent", [])[:10]:
                row = QHBoxLayout()
                row.setSpacing(4)
                name_lbl = QLabel(_fmt_cap_id(stat.get("capability_id", "")))
                name_lbl.setStyleSheet(_STYLE_ROW_NAME)
                name_lbl.setMaximumWidth(120)
                time_lbl = QLabel(_time_ago(stat.get("last_used_at")))
                time_lbl.setStyleSheet(_STYLE_SUBTEXT)
                time_lbl.setAlignment(Qt.AlignRight)
                row.addWidget(name_lbl)
                row.addStretch()
                row.addWidget(time_lbl)
                container = QWidget()
                container.setLayout(row)
                self._recent_layout.addWidget(container)

        @staticmethod
        def _clear_layout(layout: "QVBoxLayout") -> None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

else:
    # No-op stub when PySide6 is not available
    class CapabilityDashboardWidget:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            pass
        def refresh(self) -> None:
            pass
        def set_visible(self, visible: bool) -> None:
            pass