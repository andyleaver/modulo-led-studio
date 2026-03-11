from __future__ import annotations

import time

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
    get_surface_count,
    load_target,
    pick_debug_color,
)


class PreviewWidgetInteractionMixin:

    def _check_layout(self):
        # Keep strip bar controls in sync with canonical surface spec.
        try:
            spec = get_surface_spec(getattr(self.app_core, 'project', None)) if callable(get_surface_spec) else None
        except Exception:
            spec = None

        self.bar.setVisible(True)

        try:
            if spec is not None:
                cur = int(spec.count)
            elif callable(get_surface_count):
                cur = int(get_surface_count(getattr(self.app_core, 'project', None)) or 144)
            elif callable(get_surface_snapshot):
                cur = int((get_surface_snapshot(getattr(self.app_core, 'project', None)) or {}).get('count', 144) or 144)
            else:
                cur = 144
            if (not self.bar.count.hasFocus()) and self.bar.count.value() != cur:
                self.bar.count.blockSignals(True)
                self.bar.count.setValue(cur)
                self.bar.count.blockSignals(False)
                self.bar._update_ui()
        except Exception:
            pass

    def _hit_test_led(self, coords, start, end, px, py):
        # coords are in world units; convert point to world by inverse transform
        try:
            wx, wy = self.vp.screen_to_world(px, py)
        except Exception:
            return None
        for i in range(start, end):
            x0, y0, x1, y1 = coords[i]
            if x0 <= wx <= x1 and y0 <= wy <= y1:
                return i
        return None

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._drag_start = (e.position().x(), e.position().y()) if hasattr(e, "position") else (e.x(), e.y())
        self._drag_rect = None

    def mouseMoveEvent(self, e):  # noqa: N802
        if not self._dragging or self._drag_start is None:
            return
        x, y = (e.position().x(), e.position().y()) if hasattr(e, "position") else (e.x(), e.y())
        x0, y0 = self._drag_start
        self._drag_rect = (min(x0, x), min(y0, y), max(x0, x), max(y0, y))
        self.update()

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        x, y = (e.position().x(), e.position().y()) if hasattr(e, "position") else (e.x(), e.y())

        # rebuild needed state for hit-test / selection
        geom = getattr(self.app_core, "_full_preview_geom", None)
        eng = getattr(self.app_core, "_full_preview_engine", None)
        if geom is None or eng is None or not getattr(geom, "coords", None):
            self._dragging = False
            self._drag_start = None
            self._drag_rect = None
            return

        coords = geom.coords
        # Apply global target_mask from app_core to preview engine (Phase A1)
        try:
            tm = getattr(self.app_core, 'target_mask', None)
            setattr(eng, 'target_mask', tm)
        except Exception:
            pass
        # Keep preview engine bound to the latest project dict each paint (no stale layers).
        try:
            pd = getattr(self.app_core, 'project', None)
            if callable(pd):
                pd = pd()
            if isinstance(pd, dict):
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
        # Phase 6.1: update signal bus from stepped preview audio
        try:
            if hasattr(self.app_core, '_update_signals_from_preview'):
                self.app_core._update_signals_from_preview(tnow)
        except Exception:
            pass
        total = min(len(coords), len(leds))
        if total <= 0:
            self._dragging = False
            self._drag_start = None
            self._drag_rect = None
            return

        self.bar.set_preview_width(self.width())
        self.bar._update_ui()
        vis = self.bar.visible_count()
        start = max(0, min(int(self.bar.view_start), max(0, total - 1)))
        end = min(total, start + vis)

        # set viewport transform (same as paint)
        x0w, y0w, x1w, y1w = coords[start]
        cell_world_w = max(1e-6, float(x1w - x0w))
        self.vp.set_size(self.width(), self.height())
        self.vp.scale = float(self.bar.led_px) / cell_world_w
        pad_x = 6.0
        pad_y = 10.0
        self.vp.ox = pad_x - (x0w * self.vp.scale)
        try:
            ys = []
            for (a, b, c, d) in coords[start:end]:
                ys.extend([b, d])
            miny, maxy = (min(ys), max(ys)) if ys else (y0w, y1w)
            wh = max(1e-6, float(maxy - miny))
            content_h = wh * self.vp.scale
            self.vp.oy = pad_y - (miny * self.vp.scale) + max(0.0, (self.height() - pad_y * 2.0 - content_h) / 2.0)
        except Exception:
            self.vp.oy = pad_y - (y0w * self.vp.scale)

        mods = e.modifiers()
        ctrl = bool(mods & QtCore.Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & QtCore.Qt.KeyboardModifier.ShiftModifier)

        # If we dragged enough, marquee select
        if self._drag_rect is not None:
            rx0, ry0, rx1, ry1 = self._drag_rect
            # convert rect corners to world, then pick any LED whose bbox intersects
            try:
                wx0, wy0 = self.vp.screen_to_world(rx0, ry0)
                wx1, wy1 = self.vp.screen_to_world(rx1, ry1)
            except Exception:
                wx0 = wy0 = wx1 = wy1 = 0.0
            minx, maxx = (min(wx0, wx1), max(wx0, wx1))
            miny, maxy = (min(wy0, wy1), max(wy0, wy1))

            hit = []
            for i in range(start, end):
                x0, y0, x1, y1 = coords[i]
                if x1 < minx or x0 > maxx or y1 < miny or y0 > maxy:
                    continue
                hit.append(i)

            if not ctrl and not shift:
                new_sel = set(hit)
            else:
                cur = set(self.app_core.get_selection_indices() or [])
                if ctrl:
                    new_sel = cur.symmetric_difference(set(hit))
                else:  # shift with drag -> union
                    new_sel = cur.union(set(hit))

            self.app_core.set_selection_indices(sorted(new_sel))
        else:
            # click select
            idx = self._hit_test_led(coords, start, end, x, y)
            if idx is not None:
                cur = set(self.app_core.get_selection_indices() or [])
                if shift and self.bar._last_anchor is not None:
                    a = self.bar._last_anchor
                    lo, hi = (min(a, idx), max(a, idx))
                    rng = set(range(lo, hi + 1))
                    if ctrl:
                        new_sel = cur.symmetric_difference(rng)
                    else:
                        new_sel = rng
                else:
                    if ctrl:
                        if idx in cur:
                            cur.remove(idx)
                        else:
                            cur.add(idx)
                        new_sel = cur
                    else:
                        new_sel = {idx}
                    self.bar._last_anchor = idx

                self.app_core.set_selection_indices(sorted(new_sel))

        self._dragging = False
        self._drag_start = None
        self._drag_rect = None
        self.update()
