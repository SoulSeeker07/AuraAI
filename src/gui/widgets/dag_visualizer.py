"""
Next-Gen Holographic DAG Visualizer Widget
=========================================
Interactive multi-agent cognitive reasoning graph visualizer with:
1. Real-time per-step execution timers with millisecond (ms) precision.
2. Sci-Fi Hover Tooltips displaying what the agent did, subagent roles, latency, and payload.
3. Holographic laser interconnects with flowing energy particles.
4. Smooth hierarchical non-overlapping layouts.
"""

from __future__ import annotations

import math
import time
from typing import Any, Optional

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QToolTip,
)

from gui.signals import ExecutionStep, StepStatus, TaskNode, TaskNodeStatus, app_signals
from gui.theme import Colors, Typography


class HoloDagNodeItem(QGraphicsItem):
    """
    Next-Gen Sci-Fi Holographic Task Node Item with glassmorphic cards,
    real-time millisecond latency display, and interactive hover HUDs.
    """

    WIDTH = 340
    HEIGHT = 88
    CHAMFER = 10

    STATUS_CONFIG = {
        TaskNodeStatus.PENDING: {
            "border": QColor("#3b82f6"),
            "glow": QColor(59, 130, 246, 40),
            "accent": "#60a5fa",
            "bg": QColor(10, 18, 32, 225),
            "badge": "QUEUED",
            "dot_color": QColor("#3b82f6"),
        },
        TaskNodeStatus.RUNNING: {
            "border": QColor("#fbbf24"),
            "glow": QColor(251, 191, 36, 95),
            "accent": "#fde047",
            "bg": QColor(22, 26, 14, 240),
            "badge": "⚡ EXECUTING",
            "dot_color": QColor("#fbbf24"),
        },
        TaskNodeStatus.COMPLETED: {
            "border": QColor("#00e5ff"),
            "glow": QColor(0, 229, 255, 85),
            "accent": "#10b981",
            "bg": QColor(8, 24, 28, 240),
            "badge": "✓ RESOLVED",
            "dot_color": QColor("#00e5ff"),
        },
        TaskNodeStatus.FAILED: {
            "border": QColor("#f43f5e"),
            "glow": QColor(244, 63, 94, 95),
            "accent": "#f87171",
            "bg": QColor(30, 10, 16, 240),
            "badge": "⚠ FAULT",
            "dot_color": QColor("#f43f5e"),
        },
    }

    def __init__(self, node: TaskNode, parent=None):
        super().__init__(parent)
        self._node = node
        self._hovered = False
        self._anim_phase = 0.0
        self._init_time = time.perf_counter()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_tooltip()

    def boundingRect(self) -> QRectF:
        return QRectF(-6, -6, self.WIDTH + 12, self.HEIGHT + 12)

    def update_node(self, node: TaskNode):
        self._node = node
        self._update_tooltip()
        self.update()

    def _update_tooltip(self):
        """Construct a rich sci-fi HTML tooltip explaining what this step did."""
        dur_str = f"{self._node.duration_ms:.1f} ms" if self._node.duration_ms > 0 else "Active benchmarking..."
        engine_str = self._node.engine or "Master Orchestrator / Groq LPU"
        role_str = self._node.role or "Executive Cognitive Node"
        desc_str = self._node.description or self._node.label.replace("\n", " - ")
        payload_str = self._node.payload or "Goal Parameters Evaluated"

        status_col = "#10b981" if self._node.status == TaskNodeStatus.COMPLETED else (
            "#fbbf24" if self._node.status == TaskNodeStatus.RUNNING else "#60a5fa"
        )

        tooltip_html = f"""
        <div style="background-color: #070d18; border: 1px solid #00e5ff; border-radius: 6px; padding: 10px; color: #ffffff; font-family: 'Segoe UI', sans-serif; min-width: 280px;">
            <div style="font-family: Consolas, monospace; font-size: 11px; font-weight: bold; color: #00e5ff; margin-bottom: 4px;">
                [{self._node.id.upper()}] // {self._node.label.split(chr(10))[0]}
            </div>
            <div style="font-size: 10px; color: #a5b4cb; margin-bottom: 8px; border-bottom: 1px solid rgba(0, 229, 255, 0.2); padding-bottom: 4px;">
                <b>Role:</b> {role_str} &nbsp;•&nbsp; <b>Status:</b> <span style="color:{status_col}; font-weight:bold;">{self._node.status.value.upper()}</span>
            </div>
            <div style="font-size: 10.5px; color: #f1f5f9; margin-bottom: 6px;">
                <b>📌 Action Executed:</b><br/>{desc_str}
            </div>
            <div style="font-size: 10px; color: #fbbf24; margin-bottom: 4px;">
                <b>⏱️ Execution Latency:</b> <span style="color:#ffffff; font-weight:bold;">{dur_str}</span>
            </div>
            <div style="font-size: 10px; color: #c084fc; margin-bottom: 4px;">
                <b>🧠 Backend Engine:</b> {engine_str}
            </div>
            <div style="font-size: 9.5px; color: #7b8c9f; margin-top: 6px; background: rgba(255,255,255,0.03); padding: 4px 6px; border-radius: 4px;">
                <b>Payload:</b> {payload_str[:60]}
            </div>
        </div>
        """
        self.setToolTip(tooltip_html.strip())

    def advance_pulse(self):
        if self._node.status == TaskNodeStatus.RUNNING:
            self._anim_phase = (self._anim_phase + 0.1) % (2 * math.pi)
            self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cfg = self.STATUS_CONFIG.get(self._node.status, self.STATUS_CONFIG[TaskNodeStatus.PENDING])
        border_col = QColor("#00e5ff") if self._hovered else cfg["border"]

        # 1. Outer Glow on Hover / Running
        if self._hovered or self._node.status == TaskNodeStatus.RUNNING:
            pulse = math.sin(self._anim_phase) * 3 if self._node.status == TaskNodeStatus.RUNNING else 0
            glow_pen = QPen(cfg["glow"], 6 + pulse)
            glow_path = self._create_chamfer_path(QRectF(0, 0, self.WIDTH, self.HEIGHT), self.CHAMFER)
            painter.strokePath(glow_path, glow_pen)

        # 2. Main Glassmorphic Card Body
        card_path = self._create_chamfer_path(QRectF(0, 0, self.WIDTH, self.HEIGHT), self.CHAMFER)
        grad = QLinearGradient(0, 0, self.WIDTH, self.HEIGHT)
        grad.setColorAt(0.0, cfg["bg"])
        grad.setColorAt(1.0, QColor(5, 10, 18, 240))
        painter.fillPath(card_path, grad)

        # Card Border
        b_pen = QPen(border_col, 1.8 if (self._hovered or self.isSelected()) else 1.2)
        painter.strokePath(card_path, b_pen)

        # 3. Top Header Bar
        header_path = QPainterPath()
        header_path.moveTo(self.CHAMFER, 0)
        header_path.lineTo(self.WIDTH - self.CHAMFER, 0)
        header_path.lineTo(self.WIDTH, self.CHAMFER)
        header_path.lineTo(self.WIDTH, 24)
        header_path.lineTo(0, 24)
        header_path.lineTo(0, self.CHAMFER)
        header_path.closeSubpath()

        h_grad = QLinearGradient(0, 0, self.WIDTH, 0)
        h_grad.setColorAt(0.0, QColor(border_col.red(), border_col.green(), border_col.blue(), 45))
        h_grad.setColorAt(1.0, QColor(border_col.red(), border_col.green(), border_col.blue(), 10))
        painter.fillPath(header_path, h_grad)

        # Badge Pill (Left)
        painter.setPen(QColor(cfg["accent"]))
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        badge_text = f"[{self._node.id.upper()} // {cfg['badge']}]"
        painter.drawText(12, 16, badge_text)

        # Live Real-Time Milliseconds (ms) Latency Pill (Right)
        if self._node.status == TaskNodeStatus.RUNNING:
            live_ms = (time.perf_counter() - self._init_time) * 1000
            ms_text = f"⏱️ {live_ms:.0f} ms"
            ms_col = QColor("#fbbf24")
        elif self._node.duration_ms > 0:
            ms_text = f"✓ {self._node.duration_ms:.1f} ms"
            ms_col = QColor("#00e5ff")
        else:
            ms_text = "READY"
            ms_col = QColor("#7b8c9f")

        painter.setPen(ms_col)
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.drawText(QRectF(self.WIDTH - 110, 2, 85, 20), Qt.AlignRight | Qt.AlignVCenter, ms_text)

        # Live Status Dot
        dot_col = cfg["dot_color"]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_col)
        painter.drawEllipse(QPointF(self.WIDTH - 14, 12), 3.5, 3.5)

        if self._node.status == TaskNodeStatus.RUNNING:
            ring_alpha = int(max(0, 255 * (1 - (self._anim_phase / (2 * math.pi)))))
            painter.setPen(QPen(QColor(dot_col.red(), dot_col.green(), dot_col.blue(), ring_alpha), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r_size = 3.5 + (self._anim_phase * 2)
            painter.drawEllipse(QPointF(self.WIDTH - 14, 12), r_size, r_size)

        # 4. Main Node Label / Title
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        title_text = self._node.label.split("\n")[0] if "\n" in self._node.label else self._node.label
        if len(title_text) > 42:
            title_text = title_text[:40] + "..."
        painter.drawText(12, 42, title_text)

        # 5. Node Subtext / Intent Description
        sub_text = self._node.label.split("\n")[1] if "\n" in self._node.label else ""
        if not sub_text and hasattr(self._node, "description") and self._node.description:
            sub_text = self._node.description
        if not sub_text:
            sub_text = "Executing subtask logic..."
        if len(sub_text) > 54:
            sub_text = sub_text[:52] + "..."

        painter.setPen(QColor("#7b8c9f"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(12, 60, sub_text)

        # 6. Bottom Dual-Rail Progress Track
        prog_w = self.WIDTH - 24
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 200))
        painter.drawRoundedRect(QRectF(12, self.HEIGHT - 12, prog_w, 4), 2, 2)

        fill_w = max(0.0, min(prog_w, prog_w * self._node.progress))
        if fill_w > 0:
            fill_grad = QLinearGradient(12, 0, 12 + fill_w, 0)
            fill_grad.setColorAt(0.0, QColor(0, 229, 255))
            fill_grad.setColorAt(1.0, border_col)
            painter.setBrush(fill_grad)
            painter.drawRoundedRect(QRectF(12, self.HEIGHT - 12, fill_w, 4), 2, 2)

        # Sci-Fi Corner Bracket Accents
        painter.setPen(QPen(QColor(border_col.red(), border_col.green(), border_col.blue(), 120), 1))
        painter.drawLine(self.WIDTH - 8, self.HEIGHT - 2, self.WIDTH - 2, self.HEIGHT - 2)
        painter.drawLine(self.WIDTH - 2, self.HEIGHT - 8, self.WIDTH - 2, self.HEIGHT - 2)

    def _create_chamfer_path(self, rect: QRectF, c: float) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(rect.left() + c, rect.top())
        path.lineTo(rect.right() - c, rect.top())
        path.lineTo(rect.right(), rect.top() + c)
        path.lineTo(rect.right(), rect.bottom() - c)
        path.lineTo(rect.right() - c, rect.bottom())
        path.lineTo(rect.left() + c, rect.bottom())
        path.lineTo(rect.left(), rect.bottom() - c)
        path.lineTo(rect.left(), rect.top() + c)
        path.closeSubpath()
        return path

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)


class HoloDagEdgeItem(QGraphicsPathItem):
    """
    Glowing futuristic neon laser interconnect line between nodes
    with smooth Bezier curves, flowing energy particles, and directional transit markers.
    """

    def __init__(self, source: HoloDagNodeItem, target: HoloDagNodeItem, parent=None):
        super().__init__(parent)
        self._source = source
        self._target = target
        self._phase = 0.0
        self.setZValue(-1)
        self._update_path()

    def update_position(self):
        self._update_path()

    def advance_pulse(self):
        self._phase = (self._phase + 0.04) % 1.0
        self.update()

    def _update_path(self):
        src_rect = self._source.sceneBoundingRect()
        tgt_rect = self._target.sceneBoundingRect()

        start = QPointF(src_rect.center().x(), src_rect.bottom() - 4)
        end = QPointF(tgt_rect.center().x(), tgt_rect.top() + 4)

        path = QPainterPath()
        path.moveTo(start)

        dy = end.y() - start.y()
        c1 = QPointF(start.x(), start.y() + dy * 0.5)
        c2 = QPointF(end.x(), end.y() - dy * 0.5)
        path.cubicTo(c1, c2, end)

        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = self.path()

        # 1. Base Glow Tube
        glow_pen = QPen(QColor(0, 229, 255, 35), 5)
        painter.strokePath(path, glow_pen)

        # 2. Main Laser Core
        core_pen = QPen(QColor(0, 229, 255, 190), 1.8, Qt.PenStyle.SolidLine)
        painter.strokePath(path, core_pen)

        # 3. Flowing Energy Particle Pulse
        pt = path.pointAtPercent(self._phase)
        p_grad = QRadialGradient(pt, 6)
        p_grad.setColorAt(0.0, QColor("#ffffff"))
        p_grad.setColorAt(0.5, QColor(0, 229, 255, 220))
        p_grad.setColorAt(1.0, QColor(0, 229, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(p_grad)
        painter.drawEllipse(pt, 5, 5)


class DagVisualizer(QGraphicsView):
    """
    Next-Gen Interactive DAG Visualizer for ACA Multi-Agent Reasoning Graphs.
    Features cyber-grid canvas, per-node millisecond benchmarks, and rich hover HUDs.
    """

    node_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: dict[str, HoloDagNodeItem] = {}
        self._edges: list[HoloDagEdgeItem] = []
        self._scene = QGraphicsScene(self)

        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFrameShape(QFrame.Shape.NoFrame)

        # Animation Pulse Timer (60 FPS)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._advance_animations)
        self._anim_timer.start(16)

        # Connect signals
        app_signals.dag_node_added.connect(self._on_node_added)
        app_signals.dag_node_updated.connect(self._on_node_updated)
        app_signals.dag_cleared.connect(self._clear)

    def _advance_animations(self):
        for node in self._nodes.values():
            node.advance_pulse()
        for edge in self._edges:
            edge.advance_pulse()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draw holographic cybernetic blueprint grid."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base Deep Space Fill
        painter.fillRect(rect, QColor(7, 11, 19, 255))

        # Cyber Grid Lines
        grid_size = 40
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)

        grid_pen = QPen(QColor(0, 229, 255, 12), 1, Qt.PenStyle.SolidLine)
        painter.setPen(grid_pen)

        x = left
        while x < rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += grid_size

        y = top
        while y < rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += grid_size

        # Cross Points (+) at Grid Intersections
        painter.setPen(QColor(0, 229, 255, 30))
        painter.setFont(QFont("Consolas", 6))
        x = left
        while x < rect.right():
            y = top
            while y < rect.bottom():
                painter.drawText(x - 2, y + 3, "+")
                y += grid_size * 2
            x += grid_size * 2

        # Standby Overlay if empty
        if not self._nodes:
            self._draw_standby_hud(painter, rect)

    def _draw_standby_hud(self, painter: QPainter, rect: QRectF):
        """Draw stylish holographic radar schematic when graph is waiting for tasks."""
        cx = rect.center().x()
        cy = rect.center().y()

        for r, alpha in [(60, 40), (120, 25), (180, 15)]:
            painter.setPen(QPen(QColor(0, 229, 255, alpha), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.setPen(QPen(QColor(0, 229, 255, 50), 1))
        painter.drawLine(int(cx - 200), int(cy), int(cx + 200), int(cy))
        painter.drawLine(int(cx), int(cy - 200), int(cx), int(cy + 200))

        painter.setPen(QColor("#00e5ff"))
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.drawText(QRectF(cx - 180, cy - 18, 360, 24), Qt.AlignCenter, "COGNITIVE GRAPH // STANDBY")

        painter.setPen(QColor("#7b8c9f"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRectF(cx - 220, cy + 8, 440, 20),
            Qt.AlignCenter,
            "Awaiting Multi-Agent Goal Dispatch • Real-time ms benchmarks & inspector active",
        )

    def _on_node_added(self, node: TaskNode):
        if node.id in self._nodes:
            return

        item = HoloDagNodeItem(node)
        self._nodes[node.id] = item
        self._scene.addItem(item)

        for parent_id in node.parent_ids:
            if parent_id in self._nodes:
                edge = HoloDagEdgeItem(self._nodes[parent_id], item)
                self._edges.append(edge)
                self._scene.addItem(edge)

        self._relayout_nodes()
        self._fit_scene()

    def _relayout_nodes(self):
        """Layout nodes in clear, non-overlapping hierarchical vertical tiers."""
        depths: dict[str, int] = {}

        def get_depth(nid: str) -> int:
            if nid in depths:
                return depths[nid]
            node = self._nodes[nid]._node
            if not node.parent_ids:
                depths[nid] = 0
                return 0
            parent_depths = [get_depth(pid) for pid in node.parent_ids if pid in self._nodes]
            d = (max(parent_depths) + 1) if parent_depths else 0
            depths[nid] = d
            return d

        for nid in self._nodes:
            get_depth(nid)

        tier_nodes: dict[int, list[str]] = {}
        for nid, d in depths.items():
            tier_nodes.setdefault(d, []).append(nid)

        spacing_x = 380
        spacing_y = 135

        for d, nids in tier_nodes.items():
            total_w = (len(nids) - 1) * spacing_x
            start_x = -total_w / 2.0
            y = (d * spacing_y) - 60

            for idx, nid in enumerate(nids):
                x = start_x + (idx * spacing_x)
                self._nodes[nid].setPos(x - (HoloDagNodeItem.WIDTH / 2.0), y)

        for edge in self._edges:
            edge.update_position()

    def _on_node_updated(self, node: TaskNode):
        if node.id in self._nodes:
            self._nodes[node.id].update_node(node)
            for edge in self._edges:
                edge.update_position()

    def add_or_update_step(self, step: ExecutionStep):
        """Map an ExecutionStep into a visual holographic DAG node."""
        status_map = {
            StepStatus.PENDING: TaskNodeStatus.PENDING,
            StepStatus.RUNNING: TaskNodeStatus.RUNNING,
            StepStatus.COMPLETED: TaskNodeStatus.COMPLETED,
            StepStatus.FAILED: TaskNodeStatus.FAILED,
        }
        node_status = status_map.get(step.status, TaskNodeStatus.RUNNING)
        progress = (
            1.0
            if step.status == StepStatus.COMPLETED
            else (0.55 if step.status == StepStatus.RUNNING else 0.0)
        )
        node_id = f"step_{step.index}"
        parent_ids = [f"step_{step.index - 1}"] if step.index > 0 else []

        label_desc = f"\n{step.description}" if step.description else ""
        node = TaskNode(
            id=node_id,
            label=f"{step.title}{label_desc}",
            status=node_status,
            progress=progress,
            parent_ids=parent_ids,
            duration_ms=step.duration_ms,
            engine=step.engine,
            role=step.role,
            payload=step.payload,
            description=step.description,
        )
        if node_id in self._nodes:
            self._on_node_updated(node)
        else:
            self._on_node_added(node)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, HoloDagNodeItem):
            self.node_selected.emit(item._node)
        super().mousePressEvent(event)

    def _clear(self):
        self._scene.clear()
        self._nodes.clear()
        self._edges.clear()
        self.viewport().update()

    def _fit_scene(self):
        rect = self._scene.itemsBoundingRect().adjusted(-80, -60, 80, 60)
        self._scene.setSceneRect(rect)
        self.centerOn(rect.center())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_scene()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 0.85
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)
