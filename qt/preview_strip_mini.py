
from __future__ import annotations

import time

from qt.preview_shared import QtCore, QtGui, QtWidgets, get_surface_spec

class StripMiniPreview(QtWidgets.QWidget):
    """Compact 1D strip preview used in the top strip bar."""

    def __init__(self, app_core, parent=None):
        super().__init__(parent)
        self.app_core = app_core
        self.setMinimumHeight(20)
        # Qt enum compat: PyQt6 moved QSizePolicy enums under QSizePolicy.Policy.
        _pol = getattr(QtWidgets.QSizePolicy, 'Policy', QtWidgets.QSizePolicy)
        self.setSizePolicy(_pol.Expanding, _pol.Fixed)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def paintEvent(self, event):  # noqa: N802
        p = QtGui.QPainter(self)
        # Blend into the pane background (avoid looking like an extra "black bar").
        p.fillRect(self.rect(), self.palette().window())

        # Prefer the main live preview engine (used by MatrixPreviewWidget) so the strip line
        # always reflects the active simulation. Fall back to the full preview engine.
        pe = getattr(self.app_core, "preview_engine", None) or getattr(self.app_core, "_full_preview_engine", None)
        if pe is None:
            p.end()
            return

        # Ensure the preview engine keeps producing frames even when the main PreviewWidget is hidden.
        # Otherwise the mini preview can appear blank/stale in Matrix mode (placement is fine; the buffer just stops updating).
        try:
            import time as _time
            now = _time.time()
            last = getattr(self, '_last_render_t', 0.0)
            if (now - float(last)) > 0.050:  # ~20Hz
                setattr(self, '_last_render_t', now)
                # If CoreBridge flagged preview as dirty (project dict changed),
                # resync the PreviewEngine Project model before rendering.
                # This avoids the common "always red" masking where the widgets
                # keep rendering a stale project model.
                try:
                    if bool(getattr(self.app_core, '_preview_dirty', False)) and hasattr(self.app_core, 'sync_preview_engine_from_project_data'):
                        self.app_core.sync_preview_engine_from_project_data()
                except Exception:
                    pass
                # Bind latest project + registry each tick (avoid stale layers).
                try:
                    pd = getattr(self.app_core, 'project', None)
                    if callable(pd):
                        pd = pd()
                    if isinstance(pd, dict):
                        setattr(pe, 'project_data', pd)
                except Exception:
                    pass
                try:
                    reg = getattr(self.app_core, 'effect_registry', None)
                    if reg is not None:
                        setattr(pe, 'effect_registry', reg)
                except Exception:
                    pass
                try:
                    tm = getattr(self.app_core, 'target_mask', None)
                    setattr(pe, 'target_mask', tm)
                except Exception:
                    pass
                try:
                    # Playlist tick (preview-time) before rendering.
                    fn = getattr(self.app_core, 'playlist_tick', None)
                    if callable(fn):
                        fn(now)
                except Exception:
                    pass
                try:
                    pe.render_frame(now)
                except Exception:
                    pass
        except Exception:
            pass

        # PreviewEngine doesn't expose a stable public "get_pixels" API.
        # Use the most recent rendered frame buffer if present.
        pixels = getattr(pe, "_prev_frame_rgb", None)
        if pixels is None:
            pixels = getattr(pe, "prev_frame_rgb", None)
        if pixels is None:
            pixels = []
        # Prefer current strip LED count if available.
        # If the UI temporarily reports 0 while the engine still has a valid frame,
        # fall back to the rendered frame length so the mini preview never disappears.
        try:
            n = int(self.app_core.get_led_count())
        except Exception:
            n = 0
        if n <= 0:
            n = len(pixels)

        if n <= 0:
            p.end()
            return

        if len(pixels) < n:
            pixels = list(pixels) + [(0, 0, 0)] * (n - len(pixels))
        else:
            pixels = list(pixels[:n])

        w = self.width()
        h = self.height()
        cell_w = max(1.0, w / float(n))

        for i, rgb in enumerate(pixels):
            try:
                r, g, b = rgb
            except Exception:
                r = g = b = 0
            x0 = int(i * cell_w)
            x1 = int((i + 1) * cell_w)
            if x1 <= x0:
                x1 = x0 + 1
            p.fillRect(QtCore.QRect(x0, 0, x1 - x0, h), QtGui.QColor(int(r), int(g), int(b)))

        p.end()
