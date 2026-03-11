from __future__ import annotations

import time

from qt.qt_compat import QtCore, QtGui, QtWidgets
from qt.wiretap_support import _diag_exc, _log_line


class WiretapOverlay(QtWidgets.QWidget):
    """Small passive overlay inside the main window for wiretap feedback."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._msg = ""
        self._ts = 0.0
        self._ttl = 2.5

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def show_msg(self, msg: str, *, ttl: float = 2.5) -> None:
        self._msg = str(msg or "")
        self._ts = time.time()
        self._ttl = float(ttl)
        _log_line(self._msg)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if not self._msg:
            return
        if (time.time() - self._ts) > self._ttl:
            self._msg = ""
            return

        painter = QtGui.QPainter(self)
        try:
            try:
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            except Exception:
                pass
            metrics = QtGui.QFontMetrics(painter.font())
            lines = self._msg.splitlines()[:10] or [self._msg]
            width = min(max(metrics.horizontalAdvance(line) for line in lines) + 16, max(40, self.width() - 20))
            height = min((metrics.height() * len(lines)) + 14, max(30, self.height() - 20))
            rect = QtCore.QRect(10, 10, width, height)
            painter.fillRect(rect, QtGui.QColor(0, 0, 0, 180))
            painter.setPen(QtGui.QColor(255, 255, 255, 220))
            y = rect.top() + 18
            for line in lines:
                painter.drawText(rect.left() + 8, y, line[:200])
                y += metrics.height()
        except Exception as exc:
            _diag_exc(exc, "wiretap_overlay.paint")
        finally:
            painter.end()
