from __future__ import annotations

from qt.preview_widget_base import QtCore, QtGui, QtWidgets, load_target, gate_project_for_target, PreviewWidget

class MatrixPreviewWidget(QtWidgets.QWidget):
    """Matrix preview surface (MVP).

    : Replaces the  placeholder with a real matrix renderer.

    - Draws a logical top-left-origin grid (row 0 at top, col 0 at left).
    - Uses serpentine (zig-zag) index mapping by default:
        row 0: left->right
        row 1: right->left
        row 2: left->right
        ...
    - Colors are taken from the preview engine if available; otherwise a dim placeholder.
    """

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core
        self.setMinimumSize(260, 220)

        # : matrix viewport (zoom/pan)
        # Matrix cannot grow vertically (controls must remain visible), so we add
        # a proper viewport here rather than resizing the strip header.
        self._base_cell = 20
        self._zoom = 1.0
        self._zoom_min = 0.25
        self._zoom_max = 10.0
        # FIT673: auto-fit mode for matrix preview
        self._fit_mode = True
        self._in_fit = False
        self._last_fit_key = None  # (mw,mh,w,h)
        self._pan = QtCore.QPointF(0.0, 0.0)  # screen-space pixels, applied after centering
        self._panning = False
        self._pan_start = None
        self._pan_start_pan = None

        # Update at ~30fps for parity with strip preview.
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

        self._pad = 12

        # Selection / drag state (parity with strip)
        self._dragging = False
        self._drag_start = None  # (x,y)
        self._drag_rect = None   # (x0,y0,x1,y1)
        self._last_anchor = None

        # Cache of last grid metrics for hit testing
        self._grid_metrics = None  # (ox, oy, cell, mw, mh)

        self.setMouseTracking(True)
