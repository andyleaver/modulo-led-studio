from __future__ import annotations

import time
from typing import Any, Dict

from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore

QColor = QtGui.QColor
QPainter = QtGui.QPainter
QPen = QtGui.QPen
QSizePolicy = QtWidgets.QSizePolicy
QTimer = QtCore.QTimer
QWidget = QtWidgets.QWidget


class _WorkbenchPreview(QWidget):
    """Small preview for era workbench.

    - indicator: single dot
    - strip: row of N pixels with an active index
    - cells: WxH grid with a cursor
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state: Dict[str, Any] = {}
        self.setMinimumHeight(90)
        policy = getattr(QSizePolicy, "Policy", QSizePolicy)
        self.setSizePolicy(policy.Expanding, policy.Fixed)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def set_state(self, state: Dict[str, Any]):
        self.state = dict(state or {})
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        try:
            antialias = getattr(QPainter, "RenderHint", QPainter).Antialiasing
            painter.setRenderHint(antialias, True)
        except Exception:
            pass

        width = self.width()
        height = self.height()

        surface_kind = str(self.state.get("kind") or "indicator").strip().lower()
        power = bool(self.state.get("power", False))
        mode = str(self.state.get("mode", "steady")).strip().lower()
        pulse_rate = str(self.state.get("pulse_rate", "slow")).strip().lower()
        brightness = int(self.state.get("brightness", 100) or 100)
        brightness = max(0, min(100, brightness))

        lit = power
        if power and mode == "pulse":
            hz = 2.0 if pulse_rate == "fast" else 1.0
            lit = (int(time.monotonic() * hz * 2.0) % 2) == 0

        color = self.state.get("color", (255, 0, 0))
        r, g, b = color if isinstance(color, (tuple, list)) and len(color) == 3 else (255, 0, 0)
        scale = brightness / 100.0
        on_col = QColor(int(r * scale), int(g * scale), int(b * scale))
        off_col = QColor(20, 20, 20)

        painter.fillRect(0, 0, width, height, QColor(14, 14, 16))
        painter.setPen(QPen(QColor(60, 60, 60)))

        if surface_kind == "strip":
            n = max(1, min(60, int(self.state.get("count", 30) or 30)))
            active = max(0, min(n - 1, int(self.state.get("active_index", 0) or 0)))
            pad = 8
            gap = 2
            cell_w = max(4.0, (width - pad * 2 - gap * (n - 1)) / float(n))
            cell_h = min(18.0, height - 24.0)
            y = (height - cell_h) / 2.0
            x = float(pad)
            for i in range(n):
                painter.setBrush(on_col if lit and i == active else off_col)
                painter.drawRoundedRect(int(x), int(y), int(cell_w), int(cell_h), 3, 3)
                x += cell_w + gap
            return

        if surface_kind == "cells":
            cols = max(1, min(16, int(self.state.get("width", 8) or 8)))
            rows = max(1, min(16, int(self.state.get("height", 8) or 8)))
            active_x = max(0, min(cols - 1, int(self.state.get("active_x", 0) or 0)))
            active_y = max(0, min(rows - 1, int(self.state.get("active_y", 0) or 0)))
            pad = 8
            gap = 2
            cell = max(6.0, min((width - pad * 2 - gap * (cols - 1)) / float(cols), (height - pad * 2 - gap * (rows - 1)) / float(rows)))
            origin_x = (width - (cols * cell + (cols - 1) * gap)) / 2.0
            origin_y = (height - (rows * cell + (rows - 1) * gap)) / 2.0
            for y in range(rows):
                for x in range(cols):
                    painter.setBrush(on_col if lit and x == active_x and y == active_y else off_col)
                    rx = origin_x + x * (cell + gap)
                    ry = origin_y + y * (cell + gap)
                    painter.drawRoundedRect(int(rx), int(ry), int(cell), int(cell), 2, 2)
            return

        radius = max(10, min(width, height) // 6)
        painter.setBrush(on_col if lit else off_col)
        painter.drawEllipse((width // 2) - radius, (height // 2) - radius, radius * 2, radius * 2)
