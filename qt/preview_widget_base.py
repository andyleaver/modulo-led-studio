from __future__ import annotations

from qt.preview_shared import QtCore, QtWidgets, Viewport
from qt.preview_strip_widgets import StripPreviewBar
from qt.preview_widget_interaction import PreviewWidgetInteractionMixin
from qt.preview_widget_paint import PreviewWidgetPaintMixin


class PreviewWidget(PreviewWidgetPaintMixin, PreviewWidgetInteractionMixin, QtWidgets.QWidget):
    def __init__(self, app_core, bar: StripPreviewBar):
        super().__init__()
        self._last_paint_info = {}
        self._last_mode_used = None
        self.app_core = app_core
        self.bar = bar
        self.vp = Viewport()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect((self.update if hasattr(self, 'update') else (lambda *a, **k: None)))
        self._timer.start(33)

        self._layout_timer = QtCore.QTimer(self)
        self._layout_timer.timeout.connect(self._check_layout)
        self._layout_timer.start(500)

        self._dragging = False
        self._drag_start = None
        self._drag_rect = None

        self.setMouseTracking(True)
        self._ever_painted = False
        self.setAutoFillBackground(False)
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass
