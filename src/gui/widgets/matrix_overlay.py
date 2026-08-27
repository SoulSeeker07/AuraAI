"""
src/gui/widgets/matrix_overlay.py

A PySide6 widget that renders a futuristic “cyber‑punk Matrix” falling‑code
overlay.  The widget is completely self‑contained, production‑ready and
does not depend on any external assets.

Features
--------
* Fully transparent background – can be placed on top of any other widget.
* Adjustable density, speed and colour palette.
* Uses a QTimer for smooth animation (default 30 fps).
* Handles high‑DPI displays correctly.
* Thread‑safe – all GUI work stays on the main thread.

Usage
-----
    from src.gui.widgets.matrix_overlay import MatrixOverlay

    overlay = MatrixOverlay(parent=some_window)
    overlay.show()
"""

from __future__ import annotations

import random
import string
from typing import List, Tuple

from PySide6.QtCore import (
    QTimer,
    Qt,
    QRect,
    QSize,
    QPointF,
    QEvent,
)
from PySide6.QtGui import (
    QPainter,
    QFont,
    QColor,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import QWidget


class _Column:
    """
    Internal helper representing a single vertical stream of characters.
    """

    def __init__(self, x: int, height: int, char_set: List[str],
                 speed_range: Tuple[int, int],
                 max_length: int) -> None:
        self.x = x
        self.height = height
        self.char_set = char_set
        self.speed = random.randint(*speed_range)          # pixels per frame
        self.max_length = max_length

        # y is the position of the *head* of the column (topmost visible char)
        self.y = random.randint(-height, 0)

        # The list of characters currently displayed in this column.
        self.chars: List[str] = []

    def step(self) -> None:
        """Advance the column by one frame."""
        self.y += self.speed
        # Add a new character at the head.
        self.chars.insert(0, random.choice(self.char_set))

        # Trim the list to the maximum visible length.
        if len(self.chars) > self.max_length:
            self.chars.pop()

        # Reset when the column has completely scrolled out of view.
        if self.y - self.max_length * self.speed > self.height:
            self.reset()

    def reset(self) -> None:
        """Re‑initialise the column to start falling from the top again."""
        self.y = random.randint(-self.height, 0)
        self.speed = random.randint(2, 8)
        self.chars.clear()


class MatrixOverlay(QWidget):
    """
    A QWidget that draws a Matrix‑style falling‑code effect.

    The widget is transparent and ignores mouse events, making it ideal as an
    overlay on top of other UI elements.
    """

    # --------------------------------------------------------------------- #
    # Construction / configuration
    # --------------------------------------------------------------------- #
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        density: int = 120,               # Approx. number of columns
        font_family: str = "Consolas",
        font_size: int = 12,
        palette: Tuple[QColor, QColor] = (QColor(0, 255, 70), QColor(0, 180, 50)),
        char_set: List[str] | None = None,
        speed_range: Tuple[int, int] = (2, 8),
        max_column_length: int = 20,
        fps: int = 30,
    ) -> None:
        """
        Parameters
        ----------
        parent : QWidget | None
            Parent widget.
        density : int
            Approximate number of columns.  The actual count depends on widget
            width and the chosen font metrics.
        font_family : str
            Font used for the characters.
        font_size : int
            Font size in points.
        palette : Tuple[QColor, QColor]
            (head_colour, tail_colour).  The head is brighter.
        char_set : List[str] | None
            Characters to use.  If ``None`` a default cyber‑punk set is used.
        speed_range : Tuple[int, int]
            Minimum and maximum pixel speed per frame.
        max_column_length : int
            Maximum number of characters visible per column.
        fps : int
            Target frames‑per‑second.
        """
        super().__init__(parent)

        # -----------------------------------------------------------------
        # Widget appearance
        # -----------------------------------------------------------------
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool  # prevents task‑bar entry on Windows
        )
        self.setAutoFillBackground(False)

        # -----------------------------------------------------------------
        # Core parameters
        # -----------------------------------------------------------------
        self._density = max(1, density)
        self._font = QFont(font_family, font_size)
        self._head_colour, self._tail_colour = palette
        self._speed_range = speed_range
        self._max_column_length = max_column_length

        # Character set – a mix of Katakana, ASCII symbols and digits gives a
        # cyber‑punk feel.
        if char_set is None:
            katakana = [chr(cp) for cp in range(0x30A0, 0x30FF)]
            ascii_symbols = list("!@#$%^&*()-_=+[]{}|;:'\",.<>/?")
            digits = list(string.digits)
            self._char_set = katakana + ascii_symbols + digits
        else:
            self._char_set = char_set

        # -----------------------------------------------------------------
        # Animation state
        # -----------------------------------------------------------------
        self._columns: List[_Column] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000 // max(1, fps))

        # Initialise columns after we know the widget size.
        self._needs_initialisation = True

    # --------------------------------------------------------------------- #
    # Event handling
    # --------------------------------------------------------------------- #
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Re‑create columns when the widget size changes."""
        super().resizeEvent(event)
        self._needs_initialisation = True

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw all columns."""
        if self._needs_initialisation:
            self._initialize_columns()
            self._needs_initialisation = False

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setFont(self._font)

        # Paint each column.
        for col in self._columns:
            self._paint_column(painter, col)

        painter.end()

    def _initialize_columns(self) -> None:
        """Create column objects based on current widget dimensions."""
        self._columns.clear()
        if self.width() == 0 or self.height() == 0:
            return

        # Approximate column width using the font's average character width.
        metrics = self.fontMetrics()
        col_width = metrics.horizontalAdvance('M') + 2  # small spacing

        # Determine how many columns fit horizontally.
        possible_cols = max(1, self.width() // col_width)
        actual_cols = min(self._density, possible_cols)

        # Randomly choose x positions for the columns.
        x_positions = random.sample(
            range(0, self.width(), col_width), actual_cols
        )

        for x in x_positions:
            column = _Column(
                x=x,
                height=self.height(),
                char_set=self._char_set,
                speed_range=self._speed_range,
                max_length=self._max_column_length,
            )
            self._columns.append(column)

    # --------------------------------------------------------------------- #
    # Animation tick
    # --------------------------------------------------------------------- #
    def _on_tick(self) -> None:
        """Advance animation state and schedule a repaint."""
        for col in self._columns:
            col.step()
        self.update()  # triggers paintEvent

    # --------------------------------------------------------------------- #
    # Rendering helpers
    # --------------------------------------------------------------------- #
    def _paint_column(self, painter: QPainter, column: _Column) -> None:
        """Render a single column of characters."""
        metrics = painter.fontMetrics()
        char_h = metrics.height()
        x = column.x

        # Determine the y coordinate for each character in the column.
        for idx, char in enumerate(column.chars):
            y = column.y - idx * char_h

            # Skip characters that are outside the visible area.
            if y < -char_h or y > self.height():
                continue

            # Fade effect: head is brightest, tail fades out.
            if idx == 0:
                colour = self._head_colour
            else:
                # Linear interpolation between head and tail colour.
                ratio = idx / max(1, len(column.chars) - 1)
                r = self._head_colour.red() * (1 - ratio) + self._tail_colour.red() * ratio
                g = self._head_colour.green() * (1 - ratio) + self._tail_colour.green() * ratio
                b = self._head_colour.blue() * (1 - ratio) + self._tail_colour.blue() * ratio
                a = 255 * (1 - ratio * 0.7)  # slight transparency for older chars
                colour = QColor(int(r), int(g), int(b), int(a))

            painter.setPen(colour)
            painter.drawText(QPointF(x, y), char)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def start(self) -> None:
        """Start the animation (no‑op if already running)."""
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        """Stop the animation."""
        self._timer.stop()

    def is_running(self) -> bool:
        """Return ``True`` if the animation timer is active."""
        return self._timer.isActive()

    # --------------------------------------------------------------------- #
    # Size hints – useful when the widget is used as a standalone window.
    # --------------------------------------------------------------------- #
    def sizeHint(self) -> QSize:
        return QSize(400, 300)

    def minimumSizeHint(self) -> QSize:
        return QSize(200, 150)
