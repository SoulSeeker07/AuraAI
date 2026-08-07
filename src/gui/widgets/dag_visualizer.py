"""
DagVisualizer Widget
======================
Interactive Task DAG (Directed Acyclic Graph) visualizer.
Shows SubTask nodes with connections and real-time status updates.
Used in MainWindow's Task Graph tab.
"""


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, 
    QGraphicsScene, QGraphicsItem, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsTextItem, QGraphicsEllipseItem, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPainterPath

from src.gui.theme import Colors, Radius, Typography
from src.gui.signals import TaskNode, TaskNodeStatus, app_signals
from typing import Dict, List
import math


class DagNodeItem(QGraphicsRectItem):
    """Visual representation of a task node in the DAG."""
    
    STATUS_COLORS = {
        TaskNodeStatus.PENDING:   QColor(Colors.TEXT_MUTED),
        TaskNodeStatus.RUNNING:   QColor(Colors.WARNING),
        TaskNodeStatus.COMPLETED: QColor(Colors.SUCCESS),
        TaskNodeStatus.FAILED:    QColor(Colors.ERROR),
    }
    
    STATUS_BG = {
        TaskNodeStatus.PENDING:   QColor("#1E293B"),
        TaskNodeStatus.RUNNING:   QColor("#F59E0B"),
        TaskNodeStatus.COMPLETED: QColor("#10B981"),
        TaskNodeStatus.FAILED:    QColor("#F43F5E"),
    }
    
    NODE_WIDTH = 160
    NODE_HEIGHT = 48
    
    def __init__(self, node: TaskNode, parent=None):
        super().__init__(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT, parent)
        self._node = node
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Progress bar background
        self._progress_bg = QGraphicsRectItem(0, self.NODE_HEIGHT - 4, self.NODE_WIDTH, 4, self)
        self._progress_bg.setBrush(QBrush(QColor("#0F172A")))
        self._progress_bg.setPen(QPen(Qt.PenStyle.NoPen))
        
        # Progress fill
        self._progress_fill = QGraphicsRectItem(0, self.NODE_HEIGHT - 4, 0, 4, self)
        self._progress_fill.setBrush(QBrush(QColor(Colors.CYAN)))
        self._progress_fill.setPen(QPen(Qt.PenStyle.NoPen))
        
        # Label
        self._label = QGraphicsTextItem(self._node.label, self)
        self._label.setDefaultTextColor(QColor(Colors.TEXT_PRIMARY))
        self._label.setFont(Typography.BODY())
        self._label.setTextWidth(self.NODE_WIDTH - 20)
        self._label.setPos(10, 10)
        
        # Status dot
        self._status_dot = QGraphicsEllipseItem(self.NODE_WIDTH - 16, 18, 8, 8, self)
        
        self._update_appearance()
    
    def _update_appearance(self):
        status = self._node.status
        color = self.STATUS_COLORS[status]
        bg_color = self.STATUS_BG[status]
        
        # Main rect
        self.setBrush(QBrush(QColor(Colors.BG_CARD)))
        self.setPen(QPen(color, 2))
        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)
        
        # Rounded corners via path (simplified)
        
        # Status dot
        self._status_dot.setBrush(QBrush(color))
        self._status_dot.setPen(QPen(Qt.PenStyle.NoPen))
        
        # Progress
        progress_width = self.NODE_WIDTH * self._node.progress
        self._progress_fill.setRect(0, self.NODE_HEIGHT - 4, progress_width, 4)
        
        if status == TaskNodeStatus.RUNNING:
            self._progress_fill.setBrush(QBrush(QColor(Colors.WARNING)))
        elif status == TaskNodeStatus.COMPLETED:
            self._progress_fill.setBrush(QBrush(QColor(Colors.SUCCESS)))
        elif status == TaskNodeStatus.FAILED:
            self._progress_fill.setBrush(QBrush(QColor(Colors.ERROR)))
        else:
            self._progress_fill.setBrush(QBrush(QColor(Colors.CYAN)))
    
    def update_node(self, node: TaskNode):
        self._node = node
        self._label.setPlainText(node.label)
        self._update_appearance()
    
    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 8, 8)
        painter.fillPath(path, self.brush())
        painter.strokePath(path, self.pen())
    
    def hoverEnterEvent(self, event):
        self.setPen(QPen(QColor(Colors.CYAN_GLOW), 2))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self._update_appearance()
        super().hoverLeaveEvent(event)


class DagEdgeItem(QGraphicsLineItem):
    """Connection line between two DAG nodes."""
    
    def __init__(self, source: DagNodeItem, target: DagNodeItem, parent=None):
        super().__init__(parent)
        self._source = source
        self._target = target
        self.setPen(QPen(QColor(Colors.BORDER_ACTIVE), 1.5))
        self.setZValue(-1)
        self._update_line()
    
    def _update_line(self):
        src_rect = self._source.sceneBoundingRect()
        tgt_rect = self._target.sceneBoundingRect()
        
        start = QPointF(src_rect.center().x(), src_rect.bottom())
        end = QPointF(tgt_rect.center().x(), tgt_rect.top())
        
        self.setLine(start.x(), start.y(), end.x(), end.y())
    
    def update_position(self):
        self._update_line()


class DagVisualizer(QGraphicsView):
    """
    Interactive DAG visualizer for task execution graphs.
    Auto-updates when TaskNode signals are emitted.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: Dict[str, DagNodeItem] = {}
        self._edges: List[DagEdgeItem] = []
        self._scene = QGraphicsScene(self)
        
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("background: transparent; border: none;")
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # Connect signals
        app_signals.dag_node_added.connect(self._on_node_added)
        app_signals.dag_node_updated.connect(self._on_node_updated)
        app_signals.dag_cleared.connect(self._clear)
    
    def _on_node_added(self, node: TaskNode):
        if node.id in self._nodes:
            return
        
        item = DagNodeItem(node)
        self._nodes[node.id] = item
        self._scene.addItem(item)
        
        # Position node (simple tree layout)
        level = len(node.parent_ids)
        siblings = [n for n in self._nodes.values() if len(n._node.parent_ids) == level]
        index = len(siblings) - 1
        
        x = index * 200 - (len(siblings) - 1) * 100
        y = level * 100
        item.setPos(x + 400, y + 50)
        
        # Create edges to parents
        for parent_id in node.parent_ids:
            if parent_id in self._nodes:
                edge = DagEdgeItem(self._nodes[parent_id], item)
                self._edges.append(edge)
                self._scene.addItem(edge)
        
        self._fit_scene()
    
    def _on_node_updated(self, node: TaskNode):
        if node.id in self._nodes:
            self._nodes[node.id].update_node(node)
            # Update edges
            for edge in self._edges:
                edge.update_position()
    
    def _clear(self):
        self._scene.clear()
        self._nodes.clear()
        self._edges.clear()
    
    def _fit_scene(self):
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_scene()
    
    def wheelEvent(self, event):
        # Zoom with Ctrl+wheel
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            factor = 1.1 if event.angleDelta().y() > 0 else 0.9
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

