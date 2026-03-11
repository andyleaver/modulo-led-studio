from __future__ import annotations

import time

from core.surface_compat import normalize_surface_mapping

from qt.preview_shared import (
    QtCore,
    QtGui,
    QtWidgets,
    Viewport,
    MatrixMapping,
    xy_index,
    logical_dims,
    gate_project_for_target,
    get_surface_snapshot,
    get_surface_spec,
    get_surface_kind,
    get_surface_geometry_values,
    load_target,
    pick_debug_color,
)


class PreviewWidgetPaintMixin:

    def paintEvent(self, e):  # noqa: N802
        p = QtGui.QPainter(self)
        if not getattr(self, '_ever_painted', False):
            p.fillRect(self.rect(), QtGui.QColor(0, 0, 0))

        self.vp.set_size(self.width(), self.height())
        self.bar.set_preview_width(self.width())

        geom = getattr(self.app_core, "_full_preview_geom", None)
        eng = getattr(self.app_core, "preview_engine", None) or getattr(self.app_core, "_full_preview_engine", None)
        if geom is None or eng is None or not getattr(geom, "coords", None):
            try:
                self.app_core._rebuild_full_preview_engine()
                geom = getattr(self.app_core, "_full_preview_geom", None)
                eng = getattr(self.app_core, "preview_engine", None) or getattr(self.app_core, "_full_preview_engine", None)
            except Exception:
                geom = None
                eng = None

        if geom is None or eng is None or not getattr(geom, "coords", None):
            p.setPen(QtGui.QColor(255, 255, 255))
            p.drawText(10, 20, "Qt preview: waiting for geometry…")
            return

        coords = geom.coords
        # Apply global target_mask from app_core to preview engine (Phase A1)
        try:
            tm = getattr(self.app_core, 'target_mask', None)
            setattr(eng, 'target_mask', tm)
        except Exception:
            pass
        # Keep preview engine bound to latest project data / registry (avoid stale layer-enabled state).
        try:
            # Bind engine.project_data to the live project dict (CoreBridge exposes `project`).
            pd = getattr(self.app_core, 'project', None)
            if pd is None:
                pd = getattr(self.app_core, 'project_data', None)
            if pd is not None:
                setattr(eng, 'project_data', pd)
        except Exception:
            pass
        try:
            reg = getattr(self.app_core, 'effect_registry', None)
            if reg is not None:
                setattr(eng, 'effect_registry', reg)
        except Exception:
            pass
            pass
        tnow = time.time()
        try:
            fn = getattr(self.app_core, 'playlist_tick', None)
            if callable(fn):
                fn(tnow)
        except Exception:
            pass
        leds = eng.render_frame(tnow)
        # --- diagnostics: paint telemetry ---
        try:
            _nz = 0
            for _px in (leds or []):
                if _px[0] or _px[1] or _px[2]:
                    _nz += 1
            self._last_paint_info = {
                'ts': tnow,
                'coords_len': len(coords) if coords is not None else None,
                'leds_len': len(leds) if leds is not None else None,
                'nonzero': _nz,
                'visible_count': int(self.bar.visible_count()) if hasattr(self, 'bar') else None,
            }
        except Exception:
            pass

        # Phase 6.1: update signal bus from stepped preview audio
        try:
            if hasattr(self.app_core, '_update_signals_from_preview'):
                self.app_core._update_signals_from_preview(tnow)
        except Exception:
            pass
        total = min(len(coords), len(leds))
        if total <= 0:
            return

        self.bar._update_ui()

        vis = self.bar.visible_count()
        try:
            surface_kind = get_surface_kind(getattr(self.app_core, 'project', None)) if callable(get_surface_kind) else 'strip'
        except Exception:
            surface_kind = 'strip'

        # For strip layouts we keep the scrollable window (view_start/visible_count).
        # For matrix/cells layouts we render the full buffer and auto-fit to the widget.
        if surface_kind == 'strip':
            vis = self.bar.visible_count()
            start = max(0, min(int(self.bar.view_start), max(0, total - 1)))
            end = min(total, start + vis)
        else:
            start = 0
            end = total
            try:
                self.bar.view_start = 0
            except Exception:
                pass

        # Compute viewport transform from the chosen range
        x0, y0, x1, y1 = coords[start]
        cell_world_w = max(1e-6, float(x1 - x0))

        pad_x = 6.0
        pad_y = 10.0

        if surface_kind == 'strip':
            self.vp.scale = float(self.bar.led_px) / cell_world_w
            self.vp.ox = pad_x - (x0 * self.vp.scale)
        else:
            # Fit full matrix/cells content into the available viewport (no horizontal scroll).
            try:
                xs = []
                ys = []
                for (a, b, c, d) in coords[start:end]:
                    xs.extend([a, c])
                    ys.extend([b, d])
                minx, maxx = (min(xs), max(xs)) if xs else (x0, x1)
                miny, maxy = (min(ys), max(ys)) if ys else (y0, y1)
                ww = max(1e-6, float(maxx - minx))
                wh = max(1e-6, float(maxy - miny))
                sx = max(1e-6, (self.width() - pad_x * 2.0) / ww)
                sy = max(1e-6, (self.height() - pad_y * 2.0) / wh)
                self.vp.scale = min(sx, sy)
                content_w = ww * self.vp.scale
                content_h = wh * self.vp.scale
                self.vp.ox = pad_x - (minx * self.vp.scale) + max(0.0, (self.width() - pad_x * 2.0 - content_w) / 2.0)
                self.vp.oy = pad_y - (miny * self.vp.scale) + max(0.0, (self.height() - pad_y * 2.0 - content_h) / 2.0)
            except Exception:
                self.vp.scale = float(self.bar.led_px) / cell_world_w
                self.vp.ox = pad_x - (x0 * self.vp.scale)

        if surface_kind == 'strip':
            # Strip preview should live along the top of the preview canvas,
            # not vertically centered in the middle. The previous centering logic
            # caused the strip to appear "stuck" mid-pane even when the header
            # strip line was correct.
            try:
                ys = []
                for (a, b, c, d) in coords[start:end]:
                    ys.extend([b, d])
                miny, _maxy = (min(ys), max(ys)) if ys else (y0, y1)
                self.vp.oy = pad_y - (miny * self.vp.scale)
            except Exception:
                self.vp.oy = pad_y - (y0 * self.vp.scale)
        try:
            sel = set(self.app_core.get_selection_indices() or [])
        except Exception:
            sel = set()

        # ----------------------------
        # Editor-only debug overlays (zone + active layer footprint)
        # These overlays never change the underlying LED colors or export.
        # ----------------------------
        zone_overlay = set()
        layer_overlay = set()
        zone_color = None
        layer_color = None
        try:
            proj = self.app_core.project or {}
        except Exception:
            proj = {}
        try:
            zones = list(proj.get("zones") or [])
        except Exception:
            zones = []

        try:
            zsel = getattr(self.app_core, "_ui_selected_zone", None)
            if zsel is not None and 0 <= int(zsel) < len(zones):
                z = zones[int(zsel)] or {}
                # Prefer exact index set (works for matrix). Fall back to range.
                idxs = None
                try:
                    raw = z.get("indices", None)
                    if isinstance(raw, (list, tuple)) and raw:
                        idxs = [int(x) for x in raw]
                except Exception:
                    idxs = None
                if idxs is None:
                    st = int(z.get("start", 0) or 0)
                    en = int(z.get("end", st) or st)
                    idxs = list(range(min(st, en), max(st, en) + 1))
                zone_overlay = set(idxs)
                dc = z.get("debug_color") or pick_debug_color(int(zsel))
                if isinstance(dc, (list, tuple)) and len(dc) >= 3:
                    zone_color = (int(dc[0]) & 255, int(dc[1]) & 255, int(dc[2]) & 255)
        except Exception:
            zone_overlay = set()
            zone_color = None

        try:
            layers = list(proj.get("layers") or [])
        except Exception:
            layers = []
        try:
            try:
                if hasattr(self.app_core, 'get_selected_layer'):
                    lsel = int(self.app_core.get_selected_layer())
                else:
                    raise AttributeError('missing get_selected_layer')
            except Exception:
                try:
                    lsel = int(getattr(self.app_core, '_ui_selected_layer', -1))
                except Exception:
                    lsel = -1
            if lsel is None:
                lsel = -1
            lsel = int(lsel)
            if 0 <= lsel < len(layers):
                L = layers[lsel] or {}
                dc = L.get("debug_color") or pick_debug_color(lsel)
                if isinstance(dc, (list, tuple)) and len(dc) >= 3:
                    layer_color = (int(dc[0]) & 255, int(dc[1]) & 255, int(dc[2]) & 255)
                tk = str(L.get("target_kind", "all") or "all").lower().strip()
                if tk == "zone":
                    tid = str(L.get("target_id", "") or "").strip()
                    tref = int(L.get("target_ref", 0) or 0)
                    z = None
                    if tid:
                        for zz in zones:
                            if isinstance(zz, dict) and str(zz.get("id", "")) == tid:
                                z = zz
                                break
                    if z is None and 0 <= tref < len(zones):
                        z = zones[tref]
                    if isinstance(z, dict):
                        idxs = None
                        try:
                            raw = z.get("indices", None)
                            if isinstance(raw, (list, tuple)) and raw:
                                idxs = [int(x) for x in raw]
                        except Exception:
                            idxs = None
                        if idxs is None:
                            st = int(z.get("start", 0) or 0)
                            en = int(z.get("end", st) or st)
                            idxs = list(range(min(st, en), max(st, en) + 1))
                        layer_overlay = set(idxs)
        except Exception:
            layer_overlay = set()
            layer_color = None

        w = self.width()
        h = self.height()
        margin = 2

        for i in range(start, end):
            x0, y0, x1, y1 = coords[i]
            sx0, sy0 = self.vp.world_to_screen(x0, y0)
            sx1, sy1 = self.vp.world_to_screen(x1, y1)

            if sx1 < -margin or sy1 < -margin or sx0 > w + margin or sy0 > h + margin:
                continue

            r, g, b = leds[i]
            p.fillRect(QtCore.QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0),
                       QtGui.QColor(int(r) & 255, int(g) & 255, int(b) & 255))

            # Zone debug overlay (tinted fill)
            if zone_color is not None and i in zone_overlay:
                zr, zg, zb = zone_color
                p.fillRect(QtCore.QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0),
                           QtGui.QColor(int(zr) & 255, int(zg) & 255, int(zb) & 255, 160))

            # Active layer debug overlay (outline)
            if layer_color is not None and i in layer_overlay:
                lr, lg, lb = layer_color
                pen2 = QtGui.QPen(QtGui.QColor(int(lr) & 255, int(lg) & 255, int(lb) & 255, 220))
                pen2.setWidth(3)
                p.setPen(pen2)
                p.drawRect(QtCore.QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))

            if i in sel:
                pen = QtGui.QPen(QtGui.QColor(68, 170, 255))
                pen.setWidth(2)
                p.setPen(pen)
                p.drawRect(QtCore.QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))
            else:
                pen = QtGui.QPen(QtGui.QColor(64, 64, 64))
                pen.setWidth(1)
                p.setPen(pen)
                p.drawRect(QtCore.QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))


        # HUB75/matrix mapping overlay (editor-only). Helps verify rotate/flip/origin/serpentine.
        try:
            ui = (self.app_core.project.get('ui') or {}) if isinstance(self.app_core.project, dict) else {}
            show_overlay = bool(int(ui.get('preview_hub75_overlay') or 0))
        except Exception:
            show_overlay = False

        if show_overlay and surface_kind != 'strip':
            try:
                snap = get_surface_snapshot(self.app_core.project) if callable(get_surface_snapshot) else {}
                if callable(get_surface_geometry_values):
                    _mkind, _mcount, mw, mh = get_surface_geometry_values(snap or {}, default_kind='cells', default_count=1)
                else:
                    mw = int((snap or {}).get('width') or 0)
                    mh = int((snap or {}).get('height') or 0)
                raw_mapping = get_surface_mapping(self.app_core.project) if callable(get_surface_mapping) else ((snap or {}).get('mapping') if isinstance((snap or {}).get('mapping'), dict) else {})
                mp = normalize_surface_mapping(raw_mapping, fallback=(snap or {}))
                mapping = MatrixMapping(
                    w=max(1, mw),
                    h=max(1, mh),
                    serpentine=mp.get('serpentine', False),
                    flip_x=mp.get('flip_x', False),
                    flip_y=mp.get('flip_y', False),
                    rotate=mp.get('rotate', 0),
                    origin=mp.get('origin', 'top_left'),
                )
                lw, lh = logical_dims(mapping)

                # Corner markers by logical (x,y)
                corners = [
                    ("TL", (0, 0), QtGui.QColor(255, 0, 0, 220)),
                    ("TR", (lw-1, 0), QtGui.QColor(0, 255, 0, 220)),
                    ("BL", (0, lh-1), QtGui.QColor(0, 0, 255, 220)),
                    ("BR", (lw-1, lh-1), QtGui.QColor(255, 255, 255, 220)),
                ]
                font = p.font()
                font.setPointSize(max(7, int(font.pointSize()*0.9)))
                p.setFont(font)

                for label, (x, y), col in corners:
                    idx2 = xy_index(mapping, int(x), int(y))
                    if 0 <= idx2 < len(coords):
                        cx0, cy0, cx1, cy1 = coords[idx2]
                        sx0, sy0 = self.vp.world_to_screen(cx0, cy0)
                        sx1, sy1 = self.vp.world_to_screen(cx1, cy1)
                        r = QtCore.QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0)
                        p.fillRect(r, col)
                        p.setPen(QtGui.QColor(0,0,0))
                        p.drawText(r, QtCore.Qt.AlignmentFlag.AlignCenter, label)

                # Axis guides (top row + left column) with subtle tint
                pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 140))
                pen.setWidth(2)
                p.setPen(pen)

                # Top row line
                idx_a = xy_index(mapping, 0, 0)
                idx_b = xy_index(mapping, lw-1, 0)
                if 0 <= idx_a < len(coords) and 0 <= idx_b < len(coords):
                    ax0, ay0, ax1, ay1 = coords[idx_a]
                    bx0, by0, bx1, by1 = coords[idx_b]
                    sx0, sy0 = self.vp.world_to_screen(ax0, ay0)
                    sx1, sy1 = self.vp.world_to_screen(bx1, by1)
                    p.drawLine(QtCore.QPointF(sx0, sy0), QtCore.QPointF(sx1, sy0))

                # Left column line
                idx_a = xy_index(mapping, 0, 0)
                idx_b = xy_index(mapping, 0, lh-1)
                if 0 <= idx_a < len(coords) and 0 <= idx_b < len(coords):
                    ax0, ay0, ax1, ay1 = coords[idx_a]
                    bx0, by0, bx1, by1 = coords[idx_b]
                    sx0, sy0 = self.vp.world_to_screen(ax0, ay0)
                    sx1, sy1 = self.vp.world_to_screen(bx1, by1)
                    p.drawLine(QtCore.QPointF(sx0, sy0), QtCore.QPointF(sx0, sy1))

                # Small text banner
                p.setPen(QtGui.QColor(200,200,200))
                p.drawText(10, self.height()-10, f"Overlay: {lw}x{lh} rot={rot} fx={int(fx)} fy={int(fy)} serp={int(serp)}")
            except Exception:
                pass

        # Drag selection rectangle overlay
        if self._drag_rect is not None:
            x0, y0, x1, y1 = self._drag_rect
            pen = QtGui.QPen(QtGui.QColor(255, 255, 255))
            pen.setStyle(QtCore.Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawRect(QtCore.QRectF(x0, y0, x1 - x0, y1 - y0))

        warn_tag = ""
        try:
            tid = self.app_core.get_export_target_id() if hasattr(self.app_core, "get_export_target_id") else "arduino_avr_fastled_msgeq7"
            t = load_target(tid)
            gate = gate_project_for_target(self.app_core.project or {}, t.meta or {})
            if getattr(gate, "errors", None):
                warn_tag = "EXPORT BLOCKED"
            elif getattr(gate, "warnings", None):
                warn_tag = "WARN"
        except Exception:
            pass

        if warn_tag:
            p.setPen(QtGui.QColor(255, 255, 255))
            p.drawText(10, 20, warn_tag)
        # Mark that we've painted at least one valid frame to avoid clearing-to-black flicker.
        self._ever_painted = True
