from __future__ import annotations

# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass
from qt.qt_compat import QtCore, QtGui, QtWidgets
from core.surface_compat import normalize_surface_kind, normalize_surface_mapping
import time
import traceback

# : apply canonical matrix mapping (serpentine/flip/rotate) when painting
try:
    from preview.mapping import MatrixMapping, xy_index
except Exception:
    MatrixMapping = None  # type: ignore
    xy_index = None  # type: ignore

try:
    from app.project_model import (
        get_surface_spec,
        get_surface_snapshot,
        get_surface_kind,
        get_surface_count,
        get_surface_dimensions,
        get_surface_mapping,
        get_surface_geometry_values,
    )
    from core.surface_compat import get_surface_mapping_values
except Exception:
    get_surface_spec = None  # type: ignore
    get_surface_snapshot = None  # type: ignore
    get_surface_kind = None  # type: ignore
    get_surface_count = None  # type: ignore
    get_surface_dimensions = None  # type: ignore
    get_surface_mapping = None  # type: ignore
    get_surface_geometry_values = None  # type: ignore
    get_surface_mapping_values = None  # type: ignore

class SurfacePreviewWidget(QtWidgets.QWidget):
    """Surface-truthful preview widget.

    This build adds **on-screen error reporting**:
      - Any exception during frame fetch or paint is captured
      - The traceback is rendered directly on the preview surface
      - No more silent blank previews

    Design rules:
      - Dark background exists ONLY under the pixel area.
      - Off LEDs are still visible via faint cell outlines.
      - Aspect ratio is preserved; surface is centered.
    """

    def set_fit(self, on: bool):
        self._fit = bool(on)

    def set_zoom(self, cell_px: int):
        try:
            self._cell_px = max(1, int(cell_px))
        except Exception:
            self._cell_px = 8

    def debug_state(self):
        return {'fit': getattr(self, '_fit', None), 'cell_px': getattr(self, '_cell_px', None)}

    def __init__(self, app_core, parent=None, *, min_height: int = 220, force_shape: str | None = None, force_kind: str | None = None):
        super().__init__(parent)
        self._fit = True
        self._cell_px = 8

        self.app_core = app_core
        _forced = str(force_kind or force_shape or '').strip().lower()
        _forced = normalize_surface_kind(_forced, default='') if _forced else ''
        self.force_kind = _forced if _forced in ('strip', 'cells') else None  # None | 'strip' | 'cells'
        self.force_shape = self.force_kind  # compatibility mirror only

        self.setMinimumHeight(int(min_height))
        self.setAutoFillBackground(False)

        # last error (rendered on-screen if present)
        self._last_error: str | None = None
        self._last_error_ts: float = 0.0

        # Simple refresh loop (keeps this independent from legacy widget signals).
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self.update)
        self._timer.start()

    # ----------------------------
    # Error overlay
    # ----------------------------

    def _set_error(self, exc_text: str):
        self._last_error = exc_text
        self._last_error_ts = time.time()

    def _clear_error(self):
        self._last_error = None

    def _draw_error_overlay(self, painter: QtGui.QPainter, exc_text: str):
        # dark overlay over full widget (not just pixel rect)
        painter.fillRect(self.rect(), QtGui.QColor(10, 10, 10))
        painter.setPen(QtGui.QColor(255, 80, 80))
        font = painter.font()
        font.setPointSize(max(8, font.pointSize()))
        painter.setFont(font)

        lines = (exc_text or "").splitlines()
        if not lines:
            lines = ["(unknown preview error)"]

        y = 22
        painter.drawText(10, y, "PREVIEW ERROR (traceback):")
        y += 18
        # limit lines so we don't freeze drawing
        for line in lines[:40]:
            painter.drawText(10, y, line[:180])
            y += 14

    # ----------------------------
    # Frame + geometry helpers
    # ----------------------------

    def _get_current_frame(self):
        """Return a frame dict for painting.

        The engine API we rely on: PreviewEngine.get_pixels.
        Dimensions come from SurfaceSpec or canonical surface snapshot only.
        """
        try:
            engine = getattr(self.app_core, "preview_engine", None)
            if engine is None or not hasattr(engine, "get_pixels"):
                return None

            proj = getattr(self.app_core, "project", None)
            spec = get_surface_spec(proj) if callable(get_surface_spec) else None

            kind = get_surface_kind(proj) if callable(get_surface_kind) else 'strip'
            if callable(get_surface_geometry_values):
                _gkind, leds, w, h = get_surface_geometry_values(
                    get_surface_snapshot(proj) if callable(get_surface_snapshot) else {},
                    default_kind='strip',
                    default_count=get_surface_count(proj) if callable(get_surface_count) else 1,
                )
            else:
                leds = get_surface_count(proj) if callable(get_surface_count) else 0
                w, h = get_surface_dimensions(proj) if callable(get_surface_dimensions) else (0, 0)

            if spec is not None:
                leds = int(getattr(spec, "count", leds) or leds or 0)
                w = int(getattr(spec, "width", w) or w or 0)
                h = int(getattr(spec, "height", h) or h or 0)
            elif not callable(get_surface_geometry_values):
                snap = get_surface_snapshot(proj) if callable(get_surface_snapshot) else {}
                leds = int(snap.get('count', leds) or leds or 0)
                w = int(snap.get('width', w) or w or 0)
                h = int(snap.get('height', h) or h or 0)

            if self.force_kind in ('strip', 'cells'):
                kind = self.force_kind

            if kind != 'cells' or (w <= 1 and h <= 1 and leds > 0):
                w = max(1, leds if leds > 0 else (w if w > 0 else 1))
                h = 1
                expected = w
            else:
                if w <= 0 or h <= 0:
                    # fallback to strip
                    w = max(1, leds if leds > 0 else 1)
                    h = 1
                    expected = w
                else:
                    expected = w * h

            # Ensure the preview engine actually renders frames (not just reads the last buffer).
            if hasattr(engine, 'render_frame'):
                try:
                    engine.render_frame(time.time())
                except Exception:
                    # keep going; get_pixels may still return last buffer
                    pass

            px = engine.get_pixels() if callable(getattr(engine, "get_pixels", None)) else (getattr(engine, "get_pixels", None) or [])
            if len(px) < expected:
                px = list(px) + [(0, 0, 0)] * (expected - len(px))
            elif len(px) > expected:
                px = list(px)[:expected]

            mapping = None
            try:
                mapping = get_surface_mapping(proj) if callable(get_surface_mapping) else None
            except Exception:
                mapping = None
            if mapping is None and spec is not None:
                try:
                    mapping = get_surface_mapping_values(spec) if callable(get_surface_mapping_values) else normalize_surface_mapping(getattr(spec, "mapping", None), fallback={
                        "serpentine": getattr(spec, "serpentine", False),
                        "flip_x": getattr(spec, "flip_x", False),
                        "flip_y": getattr(spec, "flip_y", False),
                        "rotate": getattr(spec, "rotate", 0),
                        "origin": getattr(spec, "origin", 'top_left'),
                    })
                except Exception:
                    mapping = None
            return {"width": w, "height": h, "pixels": px, "mapping": mapping}
        except Exception:
            self._set_error(traceback.format_exc())
            return None

    def _infer_surface_dims(self, frame: dict):
        pixels = frame.get("pixels")
        w = int(frame.get("width") or 0)
        h = int(frame.get("height") or 0)

        if not isinstance(pixels, (list, tuple)):
            pixels = []

        if w <= 0 and h <= 0 and len(pixels) > 0:
            w = len(pixels)
            h = 1

        if h <= 0:
            h = 1

        return w, h, pixels

    def _compute_pixel_rect(self, w: int, h: int) -> QtCore.QRect:
        widget_w = max(1, self.width())
        widget_h = max(1, self.height())

        aspect = (w / h) if (w > 0 and h > 0) else 1.0
        widget_aspect = widget_w / widget_h

        if widget_aspect > aspect:
            render_h = widget_h
            render_w = int(render_h * aspect)
        else:
            render_w = widget_w
            render_h = int(render_w / aspect) if aspect != 0 else widget_h

        x = int((widget_w - render_w) / 2)
        y = int((widget_h - render_h) / 2)

        return QtCore.QRect(x, y, int(render_w), int(render_h))

    # ----------------------------
    # Paint
    # ----------------------------

    def paintEvent(self, ev):  # noqa: N802
        painter = QtGui.QPainter(self)
        try:
            # Qt6-safe render hint enum
            try:
                RH = QtGui.QPainter.RenderHint
                painter.setRenderHint(RH.Antialiasing, False)
            except Exception as e:
                _diag_exc(e, "qt/surface_preview_widget.py")

            # Fill with the window background so the area outside pixels blends with UI.
            painter.fillRect(self.rect(), self.palette().window())

            frame = self._get_current_frame()
            if frame is None:
                if self._last_error:
                    self._draw_error_overlay(painter, self._last_error)
                else:
                    self._draw_center_text(painter, "No preview")
                return

            # clear old error once we successfully got a frame
            self._clear_error()

            w, h, pixels = self._infer_surface_dims(frame)
            if w <= 0 or h <= 0:
                self._draw_center_text(painter, "No surface")
                return

            pixel_rect = self._compute_pixel_rect(w, h)
            _fit = bool(getattr(self, '_fit', True))
            _cell_px = int(getattr(self, '_cell_px', 8) or 8)
            _cell_px = max(1, _cell_px)
            if not _fit:
                total_w = _cell_px * w
                total_h = _cell_px * h
                # center fixed-size surface inside available rect
                r = self.rect().adjusted(6, 6, -6, -6)
                left = r.left() + max(0, int((r.width() - total_w) / 2))
                top = r.top() + max(0, int((r.height() - total_h) / 2))
                pixel_rect = QtCore.QRect(left, top, int(total_w), int(total_h))

            # Dark background only under the pixel area.
            painter.fillRect(pixel_rect, QtGui.QColor(0, 0, 0))
            # : overlay moved to end
            cell_w = (pixel_rect.width() / w) if _fit else float(_cell_px)
            cell_h = (pixel_rect.height() / h) if _fit else float(_cell_px)
            if cell_w <= 0 or cell_h <= 0:
                return

            outline = QtGui.QPen(QtGui.QColor(255, 255, 255, 18))
            outline.setCosmetic(True)
            outline.setWidth(1)
            painter.setPen(outline)

            # : choose pixel index via MatrixMapping when available (matches export XY)
            use_map = False
            mm = None
            try:
                raw_mapping = frame.get("mapping") or {}
                mp = normalize_surface_mapping(raw_mapping, fallback=frame)
                # Apply canonical mapping for both matrix and strip (strip treated as 1-row surface).
                if MatrixMapping is not None and xy_index is not None and w > 1:
                    mm = MatrixMapping(w=w, h=h,
                                       serpentine=mp.get("serpentine", False),
                                       flip_x=mp.get("flip_x", False),
                                       flip_y=mp.get("flip_y", False),
                                       rotate=mp.get("rotate", 0),
                                       origin=mp.get("origin", 'top_left'))
                    use_map = True
            except Exception:
                use_map = False
                mm = None
            
            for y in range(h):
                y0 = pixel_rect.top() + int(y * cell_h)
                for x in range(w):
                    x0 = pixel_rect.left() + int(x * cell_w)
            
                    if use_map and mm is not None:
                        try:
                            idx = int(xy_index(mm, x, y))
                        except Exception:
                            idx = y * w + x
                    else:
                        idx = y * w + x
            
                    c = pixels[idx] if idx < len(pixels) else (0, 0, 0)
            
                    if isinstance(c, (tuple, list)) and len(c) >= 3:
                        r, g, b = int(c[0]), int(c[1]), int(c[2])
                    else:
                        r, g, b = 0, 0, 0
            
                    rect = QtCore.QRect(x0, y0, int(cell_w), int(cell_h))
                    painter.fillRect(rect, QtGui.QColor(r, g, b))
                    painter.drawRect(rect)

        except Exception:
            self._set_error(traceback.format_exc())
            self._draw_error_overlay(painter, self._last_error or "(unknown preview error)")

        painter.end()

    def _draw_center_text(self, painter: QtGui.QPainter, text: str):
        painter.setPen(QtGui.QColor(200, 200, 200))
        painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, text)
