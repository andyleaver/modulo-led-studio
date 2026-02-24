"""Qt application."""

from __future__ import annotations

# Timeless UI title (versions belong in release tags/changelog, not runtime code).
APP_TITLE = "Modulo LED Studio"

def _install_global_excepthook(app_name: str = "Modulo"):
    """Show a fatal error dialog instead of silently closing on uncaught exceptions."""
    try:
        from PySide6 import QtWidgets  # type: ignore
    except Exception:
        try:
            from PyQt6 import QtWidgets  # type: ignore
        except Exception:
            QtWidgets = None  # type: ignore

    def _hook(exctype, value, tb):
        try:
            import traceback as _tb
            msg = "".join(_tb.format_exception(exctype, value, tb))
        except Exception:
            msg = f"{exctype.__name__}: {value}"
        # Always print to stderr
        try:
            sys.stderr.write(msg + "\n")
        except Exception:
            pass
        # Best-effort UI dialog
        try:
            if QtWidgets is not None and QtWidgets.QApplication.instance() is not None:
                QtWidgets.QMessageBox.critical(
                    None,
                    f"{app_name} — Fatal Error",
                    "An unexpected error occurred.\n\n" + msg[-4000:],
                )
        except Exception:
            pass

    sys.excepthook = _hook

import sys
import time
import uuid

# Phase 6.1: Signals inspector panel
try:
    from qt.signals_panel import SignalsPanel
    from qt.variables_panel import VariablesPanel
except Exception:
    SignalsPanel = None  # type: ignore
    VariablesPanel = None  # type: ignore


# () Beta deterministic signal set (documentation + capability note)
BETA_DETERMINISTIC_SIGNAL_SET = [
    # Time/engine (always available)
    "time_ms",
    "frame",
    "dt_ms",
    # Audio (available when audio backend is enabled; simulated or MSGEQ7)
    "audio_energy",
    "audio_peak",
    "audio_mono_band_0..6",
    "audio_left_band_0..6",
    "audio_right_band_0..6",
]

# () Beta target capability flags (doc-only)
# These flags are informational for UI messaging/parity gate explanations.
BETA_TARGET_CAPABILITIES = {
    "preview": {
        "operators_runtime": False,
        "modulotors": False,
        "audio": True,   # simulated or external
        "stateful_effects": True,
    },
    "arduino": {
        "operators_runtime": False,
        "modulotors": False,
        "audio": True,   # MSGEQ7 supported when exporter implements it
        "stateful_effects": False,  # blocked until integrated into multi-layer exporter
    }
}
try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
    _BINDING = "PySide6"
except Exception:  # pragma: no cover
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    _BINDING = "PyQt6"

# : Parameter Registry MVP (Qt auto-controls)
from params.registry import PARAMS
from params.ensure import ensure_params, defaults_for
from behaviors.registry import get_effect, load_capabilities_catalog

from preview.viewport import Viewport
from preview.mapping import MatrixMapping, xy_index, logical_dims
from export.targets.registry import load_target
from export.gating import gate_project_for_target
from qt.showcase_panel import ShowcasePanel
import json
import time

from app.autosave import write_autosave
from pathlib import Path
from app.build_id import get_build_id as _get_build_id
BUILD_ID = _get_build_id(Path(__file__).resolve().parents[1])



# Qt6 binding compatibility
try:
    _ORI_H = QtCore.Qt.Horizontal  # Qt5 style
except Exception:
    _ORI_H = QtCore.Qt.Orientation.Horizontal  # Qt6 style

# ----------------------------
# Editor-only debug colors (never exported as pixels)
# ----------------------------
_DEBUG_PALETTE = [
    (230, 57, 70),   # red
    (241, 250, 238), # near-white (outline-only usually)
    (29, 53, 87),    # navy
    (69, 123, 157),  # blue
    (42, 157, 143),  # teal
    (233, 196, 106), # yellow
    (244, 162, 97),  # orange
    (231, 111, 81),  # coral
    (155, 93, 229),  # purple
    (0, 180, 216),   # cyan
    (144, 190, 109), # green
]

def _pick_debug_color(i: int) -> tuple[int,int,int]:
    try:
        return _DEBUG_PALETTE[int(i) % len(_DEBUG_PALETTE)]
    except Exception:
        return (200, 200, 200)

def _ensure_zone_ids_and_debug(p: dict) -> dict:
    """Normalize project zones: ensure each zone has a stable id + debug_color."""
    zones = list(p.get("zones") or [])
    changed = False
    out = []
    for i, z in enumerate(zones):
        if not isinstance(z, dict):
            continue
        z2 = dict(z)
        if not z2.get("id"):
            z2["id"] = uuid.uuid4().hex
            changed = True
        if not z2.get("debug_color"):
            z2["debug_color"] = list(_pick_debug_color(i))
            changed = True
        out.append(z2)
    if changed:
        p2 = dict(p)
        p2["zones"] = out
        return p2
    return p

def _ensure_layer_debug(p: dict) -> dict:
    """Ensure each layer has debug_color (editor overlay) and a stable id."""
    layers = list(p.get("layers") or [])
    changed = False
    out = []
    for i, L in enumerate(layers):
        if not isinstance(L, dict):
            continue
        L2 = dict(L)
        if not L2.get("id"):
            L2["id"] = uuid.uuid4().hex
            changed = True
        if not L2.get("debug_color"):
            L2["debug_color"] = list(_pick_debug_color(i))
            changed = True
        out.append(L2)
    if changed:
        p2 = dict(p)
        p2["layers"] = out
        return p2
    return p

def _normalize_project(p: dict) -> dict:
    p2 = _ensure_zone_ids_and_debug(p)
    p3 = _ensure_layer_debug(p2)
    return p3


def _hline() -> QtWidgets.QFrame:
    """Return a thin horizontal separator line."""
    f = QtWidgets.QFrame()
    try:
        f.setFrameShape(QtWidgets.QFrame.Shape.HLine)  # Qt6
    except Exception:
        f.setFrameShape(QtWidgets.QFrame.HLine)  # type: ignore
    try:
        f.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
    except Exception:
        try:
            f.setFrameShadow(QtWidgets.QFrame.Sunken)  # type: ignore
        except Exception:
            pass
    return f




class StripPreviewBar(QtWidgets.QWidget):
    """Top strip bar shown only when layout.shape == 'strip'."""

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        self.view_start = 0
        self.led_px = 12  # default pixels per LED cell
        self._preview_w: int | None = None  # set by PreviewWidget
        self._last_anchor: int | None = None  # for shift-click ranges

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(10)

        lay.addWidget(QtWidgets.QLabel("LEDs:"))
        self.led_count = QtWidgets.QSpinBox()
        self.led_count.setRange(1, 50000)
        self.led_count.setKeyboardTracking(False)
        self.led_count.setValue(self._get_led_count())
        self.led_count.valueChanged.connect(self._on_led_count_changed)
        lay.addWidget(self.led_count)

        lay.addWidget(QtWidgets.QLabel("Size:"))
        self.size = QtWidgets.QSlider(_ORI_H)
        self.size.setRange(4, 30)
        self.size.setValue(self.led_px)
        self.size.valueChanged.connect(self._on_size_changed)
        self.size.setFixedWidth(140)
        lay.addWidget(self.size)

        lay.addWidget(QtWidgets.QLabel("Jump:"))
        self.jump = QtWidgets.QLineEdit()
        self.jump.setPlaceholderText("510:570")
        self.jump.setFixedWidth(110)
        # : State to prevent focus-out autofill from clobbering a pending Go.
        self._jump_action_active = False
        self._pending_jump_text = None
        self.jump.returnPressed.connect(self._on_jump)
        # : When focus leaves the Jump box, resume viewport-driven autofill.
        try:
            self.jump.editingFinished.connect(self._on_jump_editing_finished)
        except Exception:
            pass
        lay.addWidget(self.jump)

        self.go = QtWidgets.QPushButton("Go")
        # : Capture Jump text before focus-out (Go click causes editingFinished).
        try:
            self.go.pressed.connect(self._on_go_pressed)
        except Exception:
            pass
        self.go.clicked.connect(self._on_jump)
        lay.addWidget(self.go)

        self.range_label = QtWidgets.QLabel("")
        lay.addWidget(self.range_label)

        self.scroll = QtWidgets.QScrollBar(_ORI_H)
        self.scroll.valueChanged.connect(self._on_scroll)
        lay.addWidget(self.scroll, 1)

        self._update_ui()

    # -----------------------------
    # : Jump autofill helpers
    # -----------------------------

    #  UI: allow ControlsPanel to move the Target Mask widget into this Targets tab.
    def _install_target_mask_widget(self, w: QtWidgets.QWidget):
        try:
            if w is None:
                return
            # Reparent and place at top.
            try:
                w.setParent(self._target_mask_holder)
            except Exception:
                pass
            # Clear existing
            try:
                while self._target_mask_holder_lay.count():
                    item = self._target_mask_holder_lay.takeAt(0)
                    ww = item.widget()
                    if ww is not None:
                        ww.setParent(None)
            except Exception:
                pass
            self._target_mask_holder_lay.addWidget(w, 0)
        except Exception:
            pass

    def _desired_jump_text(self, total: int, vis: int) -> str:
        """Return the canonical Jump text for the current viewport."""
        if total <= 0:
            return ""
        end = min(total, int(self.view_start) + int(vis))
        if end <= int(self.view_start):
            end = min(total, int(self.view_start) + 1)
        return f"{int(self.view_start)}:{int(end - 1)}"

    def _sync_jump_text(self, *, force: bool = False):
        """Keep Jump text in sync with the viewport.

        - If the user is editing (has focus), do not overwrite.
        - If force=True, overwrite even when focused (used after Enter).
        """
        try:
            if (not force) and self.jump.hasFocus():
                return
        except Exception:
            pass

        total = self._get_led_count()
        vis = self.visible_count()
        desired = self._desired_jump_text(total, vis)
        try:
            if self.jump.text() != desired:
                self.jump.blockSignals(True)
                self.jump.setText(desired)
                self.jump.blockSignals(False)
        except Exception:
            pass

    def _on_jump_editing_finished(self):
        """Triggered when Jump editing ends (usually focus-out)."""
        # :
        # When the user clicks the Go button, QLineEdit can emit editingFinished (focus-out)
        # before the button's pressed()/clicked() handlers run. If we autofill here, we'd
        # overwrite the user's input and Go won't jump.
        # NOTE: Depending on the platform/style, focus may not have transferred to the
        # Go button yet at the moment editingFinished fires. So we detect "Go click"
        # using both focusWidget() and an underMouse()+mouseButtons() fallback.
        try:
            fw = QtWidgets.QApplication.focusWidget()
        except Exception:
            fw = None

        go_click_in_progress = (fw is self.go)
        if not go_click_in_progress:
            try:
                btns = QtWidgets.QApplication.mouseButtons()
                go_click_in_progress = bool(self.go.underMouse() and (btns & QtCore.Qt.MouseButton.LeftButton))
            except Exception:
                go_click_in_progress = False

        if go_click_in_progress:
            # Treat this focus-out as part of a Go-click jump: capture text and suppress autofill.
            self._pending_jump_text = self.jump.text()
            self._jump_action_active = True
            return

        # If a jump action is already active, don't clobber the user's input.
        if getattr(self, "_jump_action_active", False):
            return

        # Normal focus-out: make Jump reflect the current viewport.
        self._sync_jump_text(force=False)

    def set_preview_width(self, w: int):
        try:
            self._preview_w = int(w)
        except Exception:
            self._preview_w = None

    def _get_led_count(self) -> int:
        try:
            layout = (self.app_core.project.get("layout") or {})
            return int(layout.get("num_leds", 144) or 144)
        except Exception:
            return 144

    def visible_count(self) -> int:
        w = self._preview_w
        if w is None:
            return 160
        return max(1, int(w // max(1, int(self.led_px))))

    def _on_size_changed(self, v: int):
        self.led_px = int(v)
        self._clamp_view_start()
        self._update_ui()

    def _on_led_count_changed(self, _v: int):
        self._apply_led_count()

    def _apply_led_count(self):
        try:
            val = int(self.led_count.value())
            proj = self.app_core.project
            proj.setdefault("layout", {})["num_leds"] = val
            self.app_core.project = proj
        except Exception:
            pass

        try:
            self.app_core._rebuild_full_preview_engine()
        except Exception:
            pass

        self.view_start = 0
        self._update_ui()

    def _clamp_view_start(self):
        total = self._get_led_count()
        vis = self.visible_count()
        max_start = max(0, total - vis)
        self.view_start = max(0, min(int(self.view_start), max_start))

    def _on_scroll(self, v: int):
        self.view_start = int(v)
        self._update_ui()

    def _parse_jump(self, s: str):
        s = (s or "").strip()
        if not s:
            return None
        if ":" in s:
            a, b = s.split(":", 1)
            try:
                start = int(a.strip())
                end = int(b.strip())
            except Exception:
                return None
            if end < start:
                start, end = end, start
            return start, end
        try:
            n = int(s)
            return n, n
        except Exception:
            return None

    def _on_go_pressed(self):
        """
        :
        Go-click workflow: QLineEdit emits editingFinished on focus-out BEFORE clicked().
        Capture the user's text here so focus-out autofill can't overwrite it.
        """
        self._pending_jump_text = self.jump.text()
        self._jump_action_active = True

    def _on_jump(self):
        # : Use captured text if this jump was triggered by a Go click.
        s = self._pending_jump_text if getattr(self, "_jump_action_active", False) else self.jump.text()
        # Clear pending state immediately so viewport-driven updates can resume after we jump.
        self._pending_jump_text = None
        self._jump_action_active = False
        rng = self._parse_jump(s)
        if rng is None:
            return
        total = self._get_led_count()
        start, end = rng
        start = max(0, min(start, total - 1))
        end = max(0, min(end, total - 1))
        if end < start:
            start, end = end, start

        vis = self.visible_count()
        view_start = start
        if view_start + vis - 1 < end:
            view_start = max(0, end - (vis - 1))
        max_start = max(0, total - vis)
        view_start = max(0, min(view_start, max_start))
        self.view_start = int(view_start)
        self._update_ui()
        # : After a successful Enter/Go, normalize to the current visible range
        # even if the Jump box still has focus.
        self._sync_jump_text(force=True)

    def _update_ui(self):
        total = self._get_led_count()
        vis = self.visible_count()
        max_start = max(0, total - vis)

        self.view_start = max(0, min(int(self.view_start), max_start))

        self.scroll.blockSignals(True)
        self.scroll.setRange(0, max_start)
        self.scroll.setPageStep(vis)
        if self.scroll.value() != self.view_start:
            self.scroll.setValue(self.view_start)
        self.scroll.blockSignals(False)

        end = min(total, self.view_start + vis)
        if end <= self.view_start:
            end = min(total, self.view_start + 1)
        self.range_label.setText(f"Showing {self.view_start}–{end-1} of {total}")

        # : Keep Jump box reflecting the visible range, unless user is editing.
        self._sync_jump_text(force=False)


class PreviewWidget(QtWidgets.QWidget):
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

        # drag-select state
        self._dragging = False
        self._drag_start = None  # (x,y)
        self._drag_rect = None   # (x0,y0,x1,y1)

        self.setMouseTracking(True)
        self._ever_painted = False
        # Reduce flicker: avoid Qt background erase; we explicitly paint.
        self.setAutoFillBackground(False)
        try:
            self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, True)
        except Exception:
            pass

    def _check_layout(self):
        shape = (self.app_core.project.get("layout") or {}).get("shape", "strip")
        self.bar.setVisible(shape == "strip")

        try:
            cur = int((self.app_core.project.get("layout") or {}).get("num_leds", 144) or 144)
            if (not self.bar.led_count.hasFocus()) and self.bar.led_count.value() != cur:
                self.bar.led_count.blockSignals(True)
                self.bar.led_count.setValue(cur)
                self.bar.led_count.blockSignals(False)
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
        shape = (self.app_core.project.get('layout') or {}).get('shape', 'strip')

        # For strip layouts we keep the scrollable window (view_start/visible_count).
        # For matrix/cells layouts we render the full buffer and auto-fit to the widget.
        if str(shape).lower().strip() == 'strip':
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

        if str(shape).lower().strip() == 'strip':
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

        if str(shape).lower().strip() == 'strip':
            try:
                ys = []
                for (a, b, c, d) in coords[start:end]:
                    ys.extend([b, d])
                miny, maxy = (min(ys), max(ys)) if ys else (y0, y1)
                wh = max(1e-6, float(maxy - miny))
                content_h = wh * self.vp.scale
                self.vp.oy = pad_y - (miny * self.vp.scale) + max(0.0, (self.height() - pad_y * 2.0 - content_h) / 2.0)
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
                dc = z.get("debug_color") or _pick_debug_color(int(zsel))
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
            lsel = getattr(self.app_core, "_ui_selected_layer", None)
            if lsel is None:
                lsel = int(proj.get("active_layer", 0) or 0)
            lsel = int(lsel)
            if 0 <= lsel < len(layers):
                L = layers[lsel] or {}
                dc = L.get("debug_color") or _pick_debug_color(lsel)
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

        if show_overlay and str(shape).lower().strip() != 'strip':
            try:
                lay = (self.app_core.project.get('layout') or {}) if isinstance(self.app_core.project, dict) else {}
                mw = int(lay.get('matrix_w') or lay.get('mw') or 0)
                mh = int(lay.get('matrix_h') or lay.get('mh') or 0)
                serp = bool(lay.get('serpentine') or lay.get('matrix_serpentine') or False)
                fx = bool(lay.get('flip_x') or lay.get('matrix_flip_x') or False)
                fy = bool(lay.get('flip_y') or lay.get('matrix_flip_y') or False)
                rot = int(lay.get('rotate') or lay.get('matrix_rotate') or 0)
                mapping = MatrixMapping(w=max(1,mw), h=max(1,mh), serpentine=serp, flip_x=fx, flip_y=fy, rotate=rot)
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
        self._timer.timeout.connect((self.update if hasattr(self, 'update') else (lambda *a, **k: None)))
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
    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        z = max(self._zoom_min, min(self._zoom_max, z))
        self._zoom = z
        self.update()


    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        z = max(self._zoom_min, min(self._zoom_max, z))
        self._zoom = z
        self.update()


    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        z = max(self._zoom_min, min(self._zoom_max, z))
        self._zoom = z
        self.update()


    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        z = max(self._zoom_min, min(self._zoom_max, z))
        self._zoom = z
        self.update()


    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        z = max(self._zoom_min, min(self._zoom_max, z))
        self._zoom = z
        self.update()


    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        z = max(self._zoom_min, min(self._zoom_max, z))
        self._zoom = z
        self.update()

    def keyPressEvent(self, e):  # noqa: N802
        # Touchpad-friendly zoom shortcuts: + / -
        try:
            key = e.key()
            if key in (QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Equal):
                self.set_zoom_percent(int(round(self._zoom * 100.0)) + 10)
                e.accept(); return
            if key in (QtCore.Qt.Key.Key_Minus, QtCore.Qt.Key.Key_Underscore):
                self.set_zoom_percent(int(round(self._zoom * 100.0)) - 10)
                e.accept(); return
        except Exception:
            pass
        super().keyPressEvent(e)

    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        z = max(self._zoom_min, min(self._zoom_max, z))
        self._zoom = z
        self.update()

    def keyPressEvent(self, e):  # noqa: N802
        try:
            k = e.key()
            if k in (QtCore.Qt.Key.Key_Plus, QtCore.Qt.Key.Key_Equal):
                self.set_zoom_percent(int(round(self._zoom * 100.0)) + 10)
                return
            if k == QtCore.Qt.Key.Key_Minus:
                self.set_zoom_percent(int(round(self._zoom * 100.0)) - 10)
                return
        except Exception:
            pass
        try:
            super().keyPressEvent(e)
        except Exception:
            pass

    # --- Viewport helpers () ---
    def _cell_px(self) -> int:
        try:
            return max(2, int(round(self._base_cell * float(self._zoom))))
        except Exception:
            return max(2, int(self._base_cell))

    def _center_origin(self, cell: int, mw: int, mh: int):
        grid_w = cell * mw
        grid_h = cell * mh
        # Center the grid in the widget, then apply pan.
        cx = (float(self.width()) - grid_w) / 2.0
        cy = (float(self.height()) - grid_h) / 2.0
        return cx, cy

    def _screen_to_world(self, sx: float, sy: float, *, ox: float, oy: float, cell: int):
        # World units are in grid-cells (can be fractional).
        if cell <= 0:
            return 0.0, 0.0
        return (sx - ox) / float(cell), (sy - oy) / float(cell)

    def _world_to_screen(self, wx: float, wy: float, *, ox: float, oy: float, cell: int):
        return ox + wx * float(cell), oy + wy * float(cell)


    def fit_to_view(self):
        """Fit the matrix grid to the available widget size (aspect-preserving)."""
        if getattr(self, '_in_fit', False):
            return
        self._in_fit = True
        try:
            mw, mh = self._matrix_dims()
            mw = max(1, int(mw)); mh = max(1, int(mh))
            avail_w = max(10, int(self.width()) - 2 * int(getattr(self, '_pad', 12)))
            avail_h = max(10, int(self.height()) - 2 * int(getattr(self, '_pad', 12)))
            cell_fit = min(float(avail_w) / float(mw), float(avail_h) / float(mh))
            try:
                z = float(cell_fit) / float(getattr(self, '_base_cell', 20))
            except Exception:
                z = 1.0
            z = max(float(getattr(self, '_zoom_min', 0.25)), min(float(getattr(self, '_zoom_max', 10.0)), float(z)))
            self._zoom = float(z)
            self._pan = QtCore.QPointF(0.0, 0.0)
            self._fit_mode = True
            self._last_fit_key = (mw, mh, int(self.width()), int(self.height()))
        finally:
            self._in_fit = False
        try:
            self.update()
        except Exception:
            pass

    def resizeEvent(self, e):  # noqa: N802
        # Auto-refit when the available viewport changes, unless user manually zoomed.
        try:
            if getattr(self, '_fit_mode', False):
                mw, mh = self._matrix_dims()
                key = (int(mw), int(mh), int(self.width()), int(self.height()))
                if key != getattr(self, '_last_fit_key', None):
                    self.fit_to_view()
        except Exception:
            pass
        try:
            super().resizeEvent(e)
        except Exception:
            pass
    def _matrix_dims(self) -> tuple[int, int]:
        """Return logical (post-rotate) matrix dims for drawing/hit-testing."""
        try:
            lw, lh = self._logical_dims()
            return max(1, int(lw)), max(1, int(lh))
        except Exception:
            return 16, 16
        except Exception:
            return 16, 16

    def _layout_mapping(self) -> MatrixMapping:
        try:
            p = self.app_core.project or {}
            lay = dict(p.get("layout") or {})
        except Exception:
            lay = {}
        mw = int(lay.get("matrix_w", lay.get("mw", 16)) or 16)
        mh = int(lay.get("matrix_h", lay.get("mh", 16)) or 16)
        return MatrixMapping(
            w=mw,
            h=mh,
            serpentine=bool(lay.get("serpentine", True)),
            flip_x=bool(lay.get("flip_x", False)),
            flip_y=bool(lay.get("flip_y", False)),
            rotate=int(lay.get("rotate", 0) or 0),
        )

    def _logical_dims(self) -> tuple[int, int]:
        m = self._layout_mapping()
        return logical_dims(m)

    def _rc_to_index(self, r: int, c: int) -> int:
        """Convert logical row/col (after rotate) to LED index."""
        m = self._layout_mapping()
        return int(xy_index(m, int(c), int(r)))

    def center_on_index(self, idx: int):
        """Center the matrix viewport on a given LED index (using current mapping)."""
        mw, mh = self._matrix_dims()
        if mw <= 0 or mh <= 0:
            return
        total = mw * mh
        try:
            i = int(idx)
        except Exception:
            return
        i = max(0, min(i, total - 1))

        # Find logical (r,c) for this LED index under current mapping.
        r = c = 0
        found = False
        try:
            m = self._layout_mapping()
            lw, lh = logical_dims(m)
            cache = getattr(self, "_idx_to_rc", None)
            if isinstance(cache, dict) and i in cache:
                r, c = cache[i]
                found = True
            else:
                for yy in range(int(lh)):
                    for xx in range(int(lw)):
                        if int(xy_index(m, xx, yy)) == i:
                            r, c = int(yy), int(xx)
                            found = True
                            break
                    if found:
                        break
        except Exception:
            pass

        cell = float(self._cell_px())
        ox, oy = self._center_origin(cell, mw, mh)

        target_x = ox + (float(c) + 0.5) * cell
        target_y = oy + (float(r) + 0.5) * cell

        cx = float(self.width()) * 0.5
        cy = float(self.height()) * 0.5

        self._pan = QtCore.QPointF(cx - target_x, cy - target_y)
        self.update()



    def _get_led_colors(self, count: int):
        """Return a list of RGB tuples length=count (best-effort)."""
        # Ensure engine/geom exist (same strategy as strip preview).
        try:
            if getattr(self.app_core, "_full_preview_engine", None) is None or getattr(self.app_core, "_full_preview_geom", None) is None:
                if hasattr(self.app_core, "_rebuild_full_preview_engine"):
                    self.app_core._rebuild_full_preview_engine()
        except Exception:
            pass

        eng = getattr(self.app_core, "_full_preview_engine", None)
        leds = None
        if eng is not None:
            try:
                # Apply global target_mask from app_core to preview engine (Phase A1)
                try:
                    tm = getattr(self.app_core, 'target_mask', None)
                    setattr(eng, 'target_mask', tm)
                except Exception:
                    pass

                # Keep preview engine bound to latest project data / registry (avoid stale layer-enabled state).
                try:
                    pd = getattr(self.app_core, 'project_data', None)
                    if pd is not None:
                        setattr(eng, 'project_data', pd)
                except Exception:
                    pass

                # If the project dict changed, sync the engine's normalized Project model.
                # This is what makes layer enable/disable toggles immediately affect preview.
                try:
                    if bool(getattr(self.app_core, '_preview_dirty', False)) and hasattr(self.app_core, 'sync_preview_engine_from_project_data'):
                        self.app_core.sync_preview_engine_from_project_data()
                except Exception:
                    pass
                try:
                    reg = getattr(self.app_core, 'effect_registry', None)
                    if reg is not None:
                        setattr(eng, 'effect_registry', reg)
                except Exception:
                    pass
            except Exception:
                pass

        # Render a frame from the shared PreviewEngine (same contract as strip preview).
        if eng is not None:
            try:
                tnow = time.time()
                leds = eng.render_frame(tnow)
                # Save paint telemetry for health check diagnostics.
                try:
                    _nz = 0
                    for _px in (leds or []):
                        if _px[0] or _px[1] or _px[2]:
                            _nz += 1
                    self._last_paint_info = {
                        'ts': tnow,
                        'leds_len': len(leds) if leds is not None else None,
                        'nonzero': _nz,
                    }
                except Exception:
                    pass
            except Exception:
                leds = None

        if not leds:
            # Dim placeholder colors.
            return [(18, 18, 22) for _ in range(count)]

        # Normalize to RGB tuples.
        out = []
        for i in range(count):
            try:
                v = leds[i]
            except Exception:
                v = (18, 18, 22)

            # Accept (r,g,b) tuples/lists, or dict-ish, or single ints.
            try:
                if isinstance(v, (tuple, list)) and len(v) >= 3:
                    r, g, b = int(v[0]), int(v[1]), int(v[2])
                elif isinstance(v, dict):
                    r, g, b = int(v.get("r", 0)), int(v.get("g", 0)), int(v.get("b", 0))
                else:
                    x = int(v) if v is not None else 0
                    r = g = b = x
            except Exception:
                r, g, b = 18, 18, 22

            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            out.append((r, g, b))
        return out

    # --- Hit test helpers () ---
    def _compute_grid_metrics(self):
        mw, mh = self._matrix_dims()
        # : use zoom/pan (do not auto-fit-to-window)
        cell = self._cell_px()
        cx, cy = self._center_origin(cell, mw, mh)
        ox = cx + float(self._pan.x())
        oy = cy + float(self._pan.y())

        # Cache metrics for hit testing.
        self._grid_metrics = (ox, oy, cell, mw, mh)

        try:
            sel = set(self.app_core.get_selection_indices() or [])
        except Exception:
            sel = set()
        return ox, oy, cell, mw, mh

    def _screen_to_rc(self, sx: float, sy: float):
        # Use cached metrics from last paint if available.
        if self._grid_metrics is None:
            ox, oy, cell, mw, mh = self._compute_grid_metrics()
        else:
            ox, oy, cell, mw, mh = self._grid_metrics

        if cell <= 0:
            return None
        cx = int((sx - ox) // cell)
        cy = int((sy - oy) // cell)
        if cx < 0 or cy < 0 or cx >= mw or cy >= mh:
            return None
        return cy, cx  # (r,c)

    def wheelEvent(self, e):  # noqa: N802
        # Ctrl+wheel zoom (common convention). If Ctrl isn't pressed, still zoom
        # because this preview is dedicated and users expect wheel zoom.
        # Keep cursor anchored on the same world cell.
        try:
            delta = e.angleDelta().y()
        except Exception:
            delta = 0
        if delta == 0:
            return

        # Current metrics
        ox, oy, cell_old, mw, mh = self._compute_grid_metrics()
        pos = e.position() if hasattr(e, "position") else QtCore.QPointF(e.x(), e.y())
        sx, sy = float(pos.x()), float(pos.y())
        wx, wy = self._screen_to_world(sx, sy, ox=ox, oy=oy, cell=cell_old)

        # Zoom step
        step = 1.10 if delta > 0 else 1.0 / 1.10
        new_zoom = float(self._zoom) * step
        new_zoom = max(self._zoom_min, min(self._zoom_max, new_zoom))
        if abs(new_zoom - float(self._zoom)) < 1e-9:
            return
        self._zoom = new_zoom

        # Recompute to keep cursor anchored.
        cell_new = self._cell_px()
        cx_new, cy_new = self._center_origin(cell_new, mw, mh)
        pan_x = sx - cx_new - wx * float(cell_new)
        pan_y = sy - cy_new - wy * float(cell_new)
        self._pan = QtCore.QPointF(pan_x, pan_y)

        self.update()

    def _begin_pan(self, sx: float, sy: float):
        self._panning = True
        self._pan_start = (sx, sy)
        self._pan_start_pan = (float(self._pan.x()), float(self._pan.y()))

    def _update_pan(self, sx: float, sy: float):
        if not self._panning or self._pan_start is None or self._pan_start_pan is None:
            return
        x0, y0 = self._pan_start
        px0, py0 = self._pan_start_pan
        self._pan = QtCore.QPointF(px0 + (sx - x0), py0 + (sy - y0))
        self.update()

    def _end_pan(self):
        self._panning = False
        self._pan_start = None
        self._pan_start_pan = None

    # --- Mouse events () ---
    def mousePressEvent(self, e):  # noqa: N802
        btn = e.button()
        pos = e.position() if hasattr(e, "position") else QtCore.QPointF(e.x(), e.y())
        sx, sy = float(pos.x()), float(pos.y())

        # Right-click drag pans (doesn't interfere with selection).
        if btn == QtCore.Qt.MouseButton.RightButton:
            self._begin_pan(sx, sy)
            return

        if btn != QtCore.Qt.MouseButton.LeftButton:
            return

        self._dragging = True
        self._drag_start = (sx, sy)
        self._drag_rect = None

    def mouseMoveEvent(self, e):  # noqa: N802
        pos = e.position() if hasattr(e, "position") else QtCore.QPointF(e.x(), e.y())
        x, y = float(pos.x()), float(pos.y())

        if self._panning:
            self._update_pan(x, y)
            return

        if not self._dragging or self._drag_start is None:
            return

        x0, y0 = self._drag_start
        self._drag_rect = (min(x0, x), min(y0, y), max(x0, x), max(y0, y))
        self.update()

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == QtCore.Qt.MouseButton.RightButton:
            self._end_pan()
            return

        if e.button() != QtCore.Qt.MouseButton.LeftButton:
            return

        mods = e.modifiers()
        ctrl = bool(mods & QtCore.Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & QtCore.Qt.KeyboardModifier.ShiftModifier)

        # Current selection
        try:
            cur = set(self.app_core.get_selection_indices() or [])
        except Exception:
            cur = set()

        # Marquee selection
        if self._drag_rect is not None:
            x0, y0, x1, y1 = self._drag_rect
            if self._grid_metrics is None:
                ox, oy, cell, mw, mh = self._compute_grid_metrics()
            else:
                ox, oy, cell, mw, mh = self._grid_metrics

            # Convert screen rect to grid cell bounds
            gx0 = int((min(x0, x1) - ox) // cell)
            gx1 = int((max(x0, x1) - ox) // cell)
            gy0 = int((min(y0, y1) - oy) // cell)
            gy1 = int((max(y0, y1) - oy) // cell)

            gx0 = max(0, min(mw - 1, gx0))
            gx1 = max(0, min(mw - 1, gx1))
            gy0 = max(0, min(mh - 1, gy0))
            gy1 = max(0, min(mh - 1, gy1))

            hit = set()
            for r in range(gy0, gy1 + 1):
                for c in range(gx0, gx1 + 1):
                    hit.add(self._rc_to_index(r, c))

            if not ctrl and not shift:
                new_sel = hit
            elif ctrl:
                new_sel = cur.symmetric_difference(hit)
            else:  # shift+drag unions
                new_sel = cur.union(hit)

            self.app_core.set_selection_indices(sorted(new_sel))

        else:
            # Click selection
            x, y = (e.position().x(), e.position().y()) if hasattr(e, "position") else (e.x(), e.y())
            rc = self._screen_to_rc(x, y)
            if rc is not None:
                r, c = rc
                # Use cached width from last paint when possible.
                mw = self._grid_metrics[3] if self._grid_metrics is not None else self._matrix_dims()[0]
                idx = self._rc_to_index(r, c)
                try:
                    if isinstance(getattr(self, '_idx_to_rc', None), dict):
                        self._idx_to_rc[int(idx)] = (int(r), int(c))
                except Exception:
                    pass

                if shift and self._last_anchor is not None:
                    a = int(self._last_anchor)
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
                    self._last_anchor = idx

                self.app_core.set_selection_indices(sorted(new_sel))
            else:
                # Clicked outside the grid: clear selection unless a modifier is held.
                if not ctrl and not shift:
                    self.app_core.set_selection_indices([])

        self._dragging = False
        self._drag_start = None
        self._drag_rect = None
        self.update()

    def paintEvent(self, e):  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        p.fillRect(self.rect(), QtGui.QColor(10, 10, 12))

        mw, mh = self._matrix_dims()
        total = mw * mh
        colors = self._get_led_colors(total)

        # : zoom/pan viewport metrics
        ox, oy, cell, mw, mh = self._compute_grid_metrics()

        try:
            sel = set(self.app_core.get_selection_indices() or [])
        except Exception:
            sel = set()

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
                dc = z.get("debug_color") or _pick_debug_color(int(zsel))
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
            lsel = getattr(self.app_core, "_ui_selected_layer", None)
            if lsel is None:
                lsel = int(proj.get("active_layer", 0) or 0)
            lsel = int(lsel)
            if 0 <= lsel < len(layers):
                L = layers[lsel] or {}
                dc = L.get("debug_color") or _pick_debug_color(lsel)
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

        # Draw cells (rectangles only).
        base_pen = QtGui.QPen(QtGui.QColor(0, 0, 0))
        base_pen.setWidth(1)
        p.setPen(base_pen)

        # Only draw visible cell range (perf for large matrices).
        if cell <= 0:
            return
        # Visible bounds in cell coordinates
        vx0 = int(max(0, ((0 - ox) // cell) - 1))
        vx1 = int(min(mw - 1, ((self.width() - ox) // cell) + 1))
        vy0 = int(max(0, ((0 - oy) // cell) - 1))
        vy1 = int(min(mh - 1, ((self.height() - oy) // cell) + 1))

        # Cache mapping from LED index -> (r,c) for jump/center operations
        try:
            self._idx_to_rc = {}
        except Exception:
            self._idx_to_rc = None

        for r in range(vy0, vy1 + 1):
            y = oy + r * cell
            for c in range(vx0, vx1 + 1):
                x = ox + c * cell
                idx = self._rc_to_index(r, c)
                try:
                    if isinstance(getattr(self, '_idx_to_rc', None), dict):
                        self._idx_to_rc[int(idx)] = (int(r), int(c))
                except Exception:
                    pass
                try:
                    cr, cg, cb = colors[idx]
                except Exception:
                    cr, cg, cb = (18, 18, 22)
                p.setBrush(QtGui.QColor(int(cr), int(cg), int(cb)))
                p.drawRect(QtCore.QRectF(x, y, cell, cell))

                # Zone debug overlay (tinted fill)
                if zone_color is not None and idx in zone_overlay:
                    zr, zg, zb = zone_color
                    p.fillRect(QtCore.QRectF(x, y, cell, cell),
                               QtGui.QColor(int(zr) & 255, int(zg) & 255, int(zb) & 255, 160))
                # Active layer debug overlay (outline)
                if layer_color is not None and idx in layer_overlay:
                    lr, lg, lb = layer_color
                    pen2 = QtGui.QPen(QtGui.QColor(int(lr) & 255, int(lg) & 255, int(lb) & 255, 220))
                    pen2.setWidth(3)
                    p.setPen(pen2)
                    p.drawRect(QtCore.QRectF(x, y, cell, cell))
                    p.setPen(base_pen)

                if idx in sel:
                    pen = QtGui.QPen(QtGui.QColor(68, 170, 255))
                    pen.setWidth(2)
                    p.setPen(pen)
                    p.drawRect(QtCore.QRectF(x, y, cell, cell))
                    p.setPen(base_pen)
                else:
                    # subtle grid line already drawn by base_pen
                    pass


        # HUB75/matrix mapping overlay (editor-only). Helps verify rotate/flip/origin/serpentine.
        try:
            ui = (self.app_core.project.get('ui') or {}) if isinstance(self.app_core.project, dict) else {}
            show_overlay = bool(int(ui.get('preview_hub75_overlay') or 0))
        except Exception:
            show_overlay = False

        if show_overlay and str(shape).lower().strip() != 'strip':
            try:
                lay = (self.app_core.project.get('layout') or {}) if isinstance(self.app_core.project, dict) else {}
                mw = int(lay.get('matrix_w') or lay.get('mw') or 0)
                mh = int(lay.get('matrix_h') or lay.get('mh') or 0)
                serp = bool(lay.get('serpentine') or lay.get('matrix_serpentine') or False)
                fx = bool(lay.get('flip_x') or lay.get('matrix_flip_x') or False)
                fy = bool(lay.get('flip_y') or lay.get('matrix_flip_y') or False)
                rot = int(lay.get('rotate') or lay.get('matrix_rotate') or 0)
                mapping = MatrixMapping(w=max(1,mw), h=max(1,mh), serpentine=serp, flip_x=fx, flip_y=fy, rotate=rot)
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
            p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRect(QtCore.QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)))

        # HUD text
        p.setPen(QtGui.QColor(220, 220, 220))
        p.drawText(12, 22, f"Matrix {mw}x{mh} (serpentine)  |  LEDs: {total}  |  Zoom: {self._zoom:.2f}  |  RMB-drag pan, wheel zoom")




    # : definitive zoom setter (manual zoom disables fit-mode until Fit pressed)
    def set_zoom_percent(self, pct: int):
        """Set zoom from a percent value (touchpad-friendly control)."""
        try:
            self._fit_mode = False
        except Exception:
            pass
        try:
            z = float(pct) / 100.0
        except Exception:
            z = 1.0
        try:
            z = max(float(self._zoom_min), min(float(self._zoom_max), float(z)))
        except Exception:
            pass
        try:
            self._zoom = float(z)
        except Exception:
            pass
        try:
            self.update()
        except Exception:
            pass
class ZonesMasksPanel(QtWidgets.QWidget):



    # Apply retargeting after Zone/Group/Mask rename/delete.
    # Contract: must be best-effort and MUST NOT crash the UI.
    # - Updates operator target_kind/target_key references.
    # - Updates ui.target_mask if it references zone:/group:/mask: synthesized masks.
    # - Cleans up synthesized masks (zone:<name>, group:<name>) on rename/delete.
    # - Forces a safe panel refresh.
    def _apply_retarget_and_refresh(self, kind, old_name, new_name_or_none):
        try:
            if not kind or not old_name:
                return
            kind = str(kind).strip().lower()
            old_name = str(old_name).strip()
            if not old_name:
                return
            new_name = None if (new_name_or_none is None) else str(new_name_or_none).strip()
            if new_name == "":
                new_name = None

            # Fetch current project (best-effort)
            try:
                proj = getattr(self.app_core, "project", None)
                proj = proj() if callable(proj) else proj
            except Exception:
                proj = None
            if not isinstance(proj, dict):
                return

            changed = False
            p2 = dict(proj)

            # 1) Retarget operator references (target_kind/target_key)
            try:
                layers = list(p2.get("layers") or [])
                layers2 = []
                for L in layers:
                    if not isinstance(L, dict):
                        layers2.append(L)
                        continue
                    ops = list(L.get("operators") or [])
                    ops2 = []
                    op_changed = False
                    for op in ops:
                        if not isinstance(op, dict):
                            ops2.append(op)
                            continue
                        tk = str(op.get("target_kind") or "").strip().lower()
                        tkey = op.get("target_key")
                        if tk == kind and str(tkey or "") == old_name:
                            op2 = dict(op)
                            if new_name is None:
                                # delete: clear targeting
                                for k in ("target_kind", "target_key", "target_ref", "target_id", "target"):
                                    if k in op2:
                                        op2.pop(k, None)
                            else:
                                op2["target_key"] = new_name
                            ops2.append(op2)
                            op_changed = True
                        else:
                            ops2.append(op)
                    if op_changed:
                        L2 = dict(L)
                        L2["operators"] = ops2
                        layers2.append(L2)
                        changed = True
                    else:
                        layers2.append(L)
                if changed:
                    p2["layers"] = layers2
            except Exception:
                pass

            # 2) Retarget ui.target_mask + mask graph references (pure dict transform)
            try:
                ui = p2.get("ui") or {}
                if not isinstance(ui, dict):
                    ui = {}

                old_ref = f"{kind}:{old_name}"
                new_ref = None if new_name is None else f"{kind}:{new_name}"

                # ui.target_mask may point at synthesized zone:/group: masks
                try:
                    if str(ui.get("target_mask") or "") == old_ref:
                        ui2 = dict(ui)
                        if new_ref is None:
                            ui2["target_mask"] = ""
                        else:
                            ui2["target_mask"] = new_ref
                        p2["ui"] = ui2
                        changed = True
                except Exception:
                    pass

                # Replace string references inside mask nodes (compose operations)
                def _replace_mask_refs(node):
                    try:
                        if isinstance(node, str):
                            if node == old_ref:
                                return new_ref if new_ref is not None else ""
                            return node
                        if isinstance(node, dict):
                            nd = dict(node)
                            if "a" in nd:
                                nd["a"] = _replace_mask_refs(nd.get("a"))
                            if "b" in nd:
                                nd["b"] = _replace_mask_refs(nd.get("b"))
                            return nd
                        return node
                    except Exception:
                        return node

                masks = p2.get("masks") or {}
                if isinstance(masks, dict) and masks:
                    masks2 = dict(masks)
                    any_mask_changed = False
                    for mk, mnode in list(masks2.items()):
                        nn = _replace_mask_refs(mnode)
                        if nn != mnode:
                            masks2[mk] = nn
                            any_mask_changed = True
                    if any_mask_changed:
                        p2["masks"] = masks2
                        changed = True
            except Exception:
                pass

            # 3) Clean up synthesized masks: zone:<name>, group:<name>
            # Normalizer will recreate the new synthesized key, but it will NOT remove the old one.
            # Keep the project tidy to avoid dangling references and confusing UI lists.
            try:
                if kind in ("zone", "group"):
                    masks = p2.get("masks") or {}
                    if isinstance(masks, dict):
                        old_key = f"{kind}:{old_name}"
                        new_key = None if new_name is None else f"{kind}:{new_name}"
                        if old_key in masks:
                            masks2 = dict(masks)
                            node = masks2.pop(old_key, None)
                            # On rename, preserve the node under the new key if it doesn't already exist
                            if new_key is not None and (new_key not in masks2) and isinstance(node, dict):
                                masks2[new_key] = node
                            p2["masks"] = masks2
                            changed = True
            except Exception:
                pass

            # Commit project only if we changed it; the setter will normalize + validate and bump revision.
            try:
                if changed:
                    try:
                        self.app_core.project = p2
                    except Exception:
                        pass

                # Keep app_core.project_data in sync for preview/diagnostics.
                try:
                    setattr(self.app_core, 'project_data', self.app_core.project)
                except Exception:
                    pass
                try:
                    setattr(self.app_core, '_preview_dirty', True)
                except Exception:
                    pass
            except Exception:
                pass

            # Final: force UI refresh (safe)
            try:
                self._force_panel_refresh()
            except Exception:
                pass
        except Exception:
            return

    # () Force a full panel refresh (safe; must not crash)
    def _force_panel_refresh(self):
        try:
            try:
                setattr(self, "_panel_last_rev", -1)
            except Exception:
                pass
            try:
                self.refresh()
            except Exception:
                pass
            try:
                mp = getattr(self, "masks_panel", None)
                if mp is not None:
                    fn = getattr(mp, "refresh", None)
                    if callable(fn):
                        fn()
            except Exception:
                pass
        except Exception:
            pass

    # () Rename/Delete retargeting utility (safe, best-effort; must not crash)
    def _retarget_mask_refs(self, kind, old_name, new_name_or_none):
        try:
            if not kind or not old_name:
                return
            kind = str(kind).strip().lower()
            old_name = str(old_name).strip()
            if not old_name:
                return
            new_name = None if (new_name_or_none is None) else str(new_name_or_none).strip()
            if new_name == "":
                new_name = None

            # Get project dict
            try:
                proj = getattr(self.app_core, "project", None)
                proj = proj() if callable(proj) else proj
            except Exception:
                proj = None
            if not isinstance(proj, dict):
                return

            masks = proj.get("masks") or {}
            ui = proj.get("ui") or {}

            old_ref = f"{kind}:{old_name}"
            new_ref = (None if new_name is None else f"{kind}:{new_name}")

            log_lines = []  # () last retarget log
                        # Retarget ui.target_mask (: delete fallback selection)
            try:
                if ui.get("target_mask") == old_ref:
                    if new_ref is None:
                        # delete: remove target_mask and optionally choose a sane fallback
                        try:
                            if 'target_mask' in ui:
                                del ui['target_mask']
                        except Exception:
                            pass
                        # fallback: first zone, else first group, else none
                        try:
                            zkeys = list((proj.get("zones") or {}).keys())
                            gkeys = list((proj.get("groups") or {}).keys())
                            if zkeys:
                                ui["target_mask"] = "zone:" + str(zkeys[0])
                            elif gkeys:
                                ui["target_mask"] = "group:" + str(gkeys[0])
                        except Exception:
                            pass
                    else:
                        ui["target_mask"] = new_ref
                    proj["ui"] = ui
                    try:
                        log_lines.append(f"ui.target_mask: {old_ref} -> {new_ref if new_ref is not None else '(cleared)'}")
                    except Exception:
                        pass
            except Exception:
                pass
            # Retarget inside masks: refs or targets arrays
            try:
                for mn, mdef in list(masks.items()):
                    if not isinstance(mdef, dict):
                        continue
                    for key in ("refs", "targets"):
                        try:
                            refs = mdef.get(key)
                        except Exception:
                            refs = None
                        if refs is None:
                            continue
                        # normalize to list
                        if isinstance(refs, str):
                            refs_list = [refs]
                            was_str = True
                        else:
                            refs_list = list(refs) if isinstance(refs, (list, tuple)) else None
                            was_str = False
                        if refs_list is None:
                            continue

                        changed = False
                        new_list = []
                        for r in refs_list:
                            if r == old_ref:
                                changed = True
                                if new_ref is not None:
                                    new_list.append(new_ref)
                                # else drop it
                            else:
                                new_list.append(r)
                        if changed:
                            try:
                                log_lines.append(f"mask '{mn}' {key}: {old_ref} -> {new_ref if new_ref is not None else '(dropped)'}")
                            except Exception:
                                pass
                            mdef[key] = (new_list[0] if (was_str and len(new_list) == 1) else (';'.join([str(x) for x in new_list]) if was_str else new_list))  # ( string-multi safety)
                    masks[mn] = mdef
                proj["masks"] = masks
            except Exception:
                pass

                        # ( post-retarget refresh)
            try:
                if hasattr(self, '_force_panel_refresh') and callable(getattr(self, '_force_panel_refresh')):
                    self._force_panel_refresh()
            except Exception:
                pass

            # () store last retarget log for diagnostics
            try:
                self._last_retarget_log = list(log_lines)
            except Exception:
                pass

            # Push project back (prefer panel/app_core setter; fallback to assignment)
            try:
                if hasattr(self, '_set_project') and callable(getattr(self, '_set_project')):
                    self._set_project(proj)
                else:
                    sp = getattr(self.app_core, 'set_project', None)
                    if callable(sp):
                        sp(proj)
                    else:
                        try:
                            self.app_core.project = proj
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            pass

    """Zones/Masks MVP panel.

    - Zones: contiguous inclusive ranges (start/end)
    - Groups: explicit index sets (non-contiguous allowed)

    This panel is STRUCTURE-only: it turns the current temporary selection
    into persistent targets that Layers can later reference.
    """

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        outer = QtWidgets.QVBoxLayout(self)

        #  UI: Target Mask belongs in Targets, not in always-visible Controls.
        # A compact holder row sits above the Targets splitter.
        self._target_mask_holder = QtWidgets.QWidget()
        self._target_mask_holder_lay = QtWidgets.QVBoxLayout(self._target_mask_holder)
        self._target_mask_holder_lay.setContentsMargins(0, 0, 0, 0)
        self._target_mask_holder_lay.setSpacing(6)
        outer.addWidget(self._target_mask_holder, 0)
        #  UI: make Targets panel resizable (lists vs diagnostics)
        self._targets_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        outer.addWidget(self._targets_splitter, 1)
        self._targets_left = QtWidgets.QWidget()
        self._targets_right = QtWidgets.QWidget()
        self._targets_left_lay = QtWidgets.QVBoxLayout(self._targets_left)
        self._targets_right_lay = QtWidgets.QVBoxLayout(self._targets_right)
        self._targets_left_lay.setContentsMargins(0, 0, 0, 0)
        self._targets_right_lay.setContentsMargins(0, 0, 0, 0)
        self._targets_left_lay.setSpacing(8)
        self._targets_right_lay.setSpacing(8)
        self._targets_splitter.addWidget(self._targets_left)
        self._targets_splitter.addWidget(self._targets_right)
        try:
            self._targets_splitter.setStretchFactor(0, 2)
            self._targets_splitter.setStretchFactor(1, 1)
        except Exception:
            pass
        # ---- Phase A1: Masks panel (minimal management) ----
        self.masks_panel = MasksManagerPanel(self.app_core)
        self._targets_left_lay.addWidget(self.masks_panel)
        # () Single refresh authority for Zones/Masks/Groups panel.
        # We refresh *all* lists (Zones, Groups, Masks, Diagnostics) from one timer keyed to project revision,
        # and we avoid refreshing while the user is actively interacting with list/table widgets.
        self._panel_refresh_timer = QtCore.QTimer(self)
        self._panel_refresh_timer.setInterval(250)
        self._panel_last_rev = -1

        def _panel_tick():
            try:
                # Only refresh when project revision changes
                try:
                    rev = int(getattr(self.app_core, 'project_revision', lambda: 0)() if self.app_core is not None else 0)
                except Exception:
                    rev = 0
                if rev == int(getattr(self, '_panel_last_rev', -1)):
                    return

                # Don't fight user interaction: if any relevant widget has focus, skip this tick.
                try:
                    if (hasattr(self, 'zones_list') and self.zones_list.hasFocus()) or (hasattr(self, 'groups_list') and self.groups_list.hasFocus()):
                        return
                except Exception:
                    pass
                try:
                    mp = getattr(self, 'masks_panel', None)
                    tbl = getattr(mp, 'table', None) if mp is not None else None
                    if tbl is not None and hasattr(tbl, 'hasFocus') and tbl.hasFocus():
                        return
                except Exception:
                    pass

                self._panel_last_rev = rev

                # Refresh Zones/Groups/Diagnostics
                try:
                    self.refresh()
                except Exception:
                    pass

                # Refresh Masks list only if the masks panel is expanded
                try:
                    mp = getattr(self, 'masks_panel', None)
                    if mp is not None:
                        try:
                            if hasattr(mp, 'isChecked') and (not mp.isChecked()):
                                return
                        except Exception:
                            pass
                        fn = getattr(mp, 'refresh', None)
                        if callable(fn):
                            fn()
                except Exception:
                    pass
            except Exception:
                pass

        self._panel_refresh_timer.timeout.connect(_panel_tick)
        self._panel_refresh_timer.start()

        
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(8)

        # Zones (range masks)
        self.zones_box = QtWidgets.QGroupBox("Zones (Range)")
        zlay = QtWidgets.QVBoxLayout(self.zones_box)
        zlay.setContentsMargins(8, 8, 8, 8)
        zlay.setSpacing(6)

        self.zones_list = QtWidgets.QListWidget()
        # PyQt6: selection mode enums live under QAbstractItemView.SelectionMode
        self.zones_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        def _zone_sel_changed():
            try:
                rows = self.zones_list.selectionModel().selectedRows()
                if not rows:
                    return
                r = rows[0].row()
                it = self.zones_list.item(r)
                name = str(it.text()) if it else None
                if not name:
                    return
                # Store selection in panel and refresh details
                try:
                    self._selected_zone = name
                except Exception:
                    pass
                try:
                    if hasattr(self, '_refresh_zone_details'):
                        self._refresh_zone_details()
                except Exception:
                    pass
            except Exception:
                return
        
        self.zones_list.itemSelectionChanged.connect(_zone_sel_changed)
        zlay.addWidget(self.zones_list, 1)

        zbtn = QtWidgets.QHBoxLayout()
        self.z_create = QtWidgets.QPushButton("Create from selection")
        def _z_create_from_sel():
            try:
                # selection indices from core
                sel = []
                try:
                    sel = list(getattr(self.app_core, 'get_selection_indices', lambda: [])() or [])
                except Exception:
                    sel = []
                if not sel:
                    QtWidgets.QMessageBox.information(self, 'No selection', 'Select pixels first.')
                    return
                name, ok = QtWidgets.QInputDialog.getText(self, 'Create Zone', 'Zone name:')
                if not ok:
                    return
                name = str(name or '').strip()
                if not name:
                    return
                p = self._project() if hasattr(self, '_project') else (getattr(self.app_core, 'project', None) or {})
                zones = p.get('zones') or {}
                if not isinstance(zones, dict):
                    zones = {}
                zones2 = dict(zones)
                zones2[name] = {'indices': sorted(set(int(x) for x in sel))}
                p2 = dict(p)
                p2['zones'] = zones2
                if hasattr(self, '_set_project'):
                    self._set_project(p2)
                else:
                    try: self.app_core.project = p2
                    except Exception: pass
                try:
                    self._selected_zone = name
                except Exception:
                    pass
                try:
                    self.refresh()
                except Exception:
                    pass
            except Exception:
                return
        
        self.z_create.clicked.connect(_z_create_from_sel)
        zbtn.addWidget(self.z_create, 1)
        self.z_rename = QtWidgets.QPushButton("Rename")
        def _z_rename_zone():
            try:
                # current selection
                name = getattr(self, '_selected_zone', None)
                if not name:
                    try:
                        rows = self.zones_list.selectionModel().selectedRows()
                        if rows:
                            it = self.zones_list.item(rows[0].row())
                            name = str(it.text()) if it else None
                    except Exception:
                        name = None
                if not name:
                    return
                new, ok = QtWidgets.QInputDialog.getText(self, 'Rename Zone', 'New zone name:', text=str(name))
                if not ok:
                    return
                new = str(new or '').strip()
                if not new or new == name:
                    return
                p = self._project() if hasattr(self, '_project') else (getattr(self.app_core, 'project', None) or {})
                zones = p.get('zones') or {}
                if not isinstance(zones, dict) or name not in zones:
                    return
                if new in zones:
                    QtWidgets.QMessageBox.warning(self, 'Rename failed', f"Zone '{new}' already exists.")
                    return
                z2 = dict(zones)
                z2[new] = z2.pop(name)
                p2 = dict(p)
                p2['zones'] = z2
                if hasattr(self, '_set_project'):
                    self._set_project(p2)
                else:
                    try: self.app_core.project = p2
                    except Exception: pass
                self._apply_retarget_and_refresh('zone', name, new)
                try:
                    self._selected_zone = new
                except Exception:
                    pass
                try:
                    self.refresh()
                except Exception:
                    pass
            except Exception:
                return
        
        self.z_rename.clicked.connect(_z_rename_zone)
        zbtn.addWidget(self.z_rename)
        self.z_delete = QtWidgets.QPushButton("Delete")
        self.z_to_mask = QtWidgets.QPushButton('Zone → Mask')
        self.z_to_sel = QtWidgets.QPushButton('Zone → Selection')
        self.z_to_sel.setToolTip('Replace current selection with the selected zone indices')

        self.z_to_mask.setToolTip('Create a mask from the selected zone (copies start/end or indices) and set it as Target Mask')

        def _z_delete_zone():
            try:
                name = getattr(self, '_selected_zone', None)
                if not name:
                    try:
                        rows = self.zones_list.selectionModel().selectedRows()
                        if rows:
                            it = self.zones_list.item(rows[0].row())
                            name = str(it.text()) if it else None
                    except Exception:
                        name = None
                if not name:
                    return
                resp = QtWidgets.QMessageBox.question(self, 'Delete Zone', f"Delete zone '{name}'?",
                                                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if resp != QtWidgets.QMessageBox.Yes:
                    return
                p = self._project() if hasattr(self, '_project') else (getattr(self.app_core, 'project', None) or {})
                zones = p.get('zones') or {}
                if not isinstance(zones, dict) or name not in zones:
                    return
                z2 = dict(zones)
                z2.pop(name, None)
                p2 = dict(p)
                p2['zones'] = z2
                if hasattr(self, '_set_project'):
                    self._set_project(p2)
                else:
                    try: self.app_core.project = p2
                    except Exception: pass
                self._apply_retarget_and_refresh('zone', name, None)
                try:
                    self._selected_zone = None
                except Exception:
                    pass
                try:
                    self.refresh()
                except Exception:
                    pass
            except Exception:
                return
        
        self.z_delete.clicked.connect(_z_delete_zone)

        def _z_to_mask():
            try:
                # selected zone name
                zname = None
                try: zname = getattr(self, 'selected_zone', None)
                except Exception: zname = None
                if not zname:
                    QtWidgets.QMessageBox.information(self, 'No zone selected', 'Select a zone first.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                if not isinstance(p, dict): return
                zones = p.get('zones') or {}
                if not isinstance(zones, dict): zones = {}
                znode = zones.get(zname)
                if not isinstance(znode, dict):
                    QtWidgets.QMessageBox.information(self, 'Bad zone', 'Selected zone data is not a dict.')
                    return
                masks = p.get('masks') or {}
                if not isinstance(masks, dict): masks = {}
                base = f'Zone_{zname}'
                mname = base
                k = 1
                while mname in masks:
                    k += 1
                    mname = f'{base}_{k}'
                masks2 = dict(masks)
                # copy only indices or start/end for safety
                if 'indices' in znode and isinstance(znode.get('indices'), list):
                    masks2[mname] = {'op': 'indices', 'indices': list(znode.get('indices') or [])}
                else:
                    masks2[mname] = {'start': znode.get('start', 0), 'end': znode.get('end', -1)}
                p2 = dict(p); p2['masks'] = masks2
                ui = p2.get('ui') or {}
                if not isinstance(ui, dict): ui = {}
                ui2 = dict(ui); ui2['target_mask'] = mname
                p2['ui'] = ui2
                try: self.app_core.project = p2
                except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.z_to_mask.clicked.connect(_z_to_mask)
        except Exception: pass

        zbtn.addWidget(self.z_delete)
        zlay.addLayout(zbtn)

        self._targets_left_lay.addWidget(self.zones_box, 1)

        # Groups (set masks)
        self.groups_box = QtWidgets.QGroupBox("Groups (Set)")
        glay = QtWidgets.QVBoxLayout(self.groups_box)
        glay.setContentsMargins(8, 8, 8, 8)
        glay.setSpacing(6)

        self.groups_list = QtWidgets.QListWidget()
        # Info labels (safe; only used if present)
        self.zone_info = QtWidgets.QLabel('')
        self.group_info = QtWidgets.QLabel('')
        self.zone_info.setWordWrap(True)
        self.group_info.setWordWrap(True)
        try:
            # best-effort: add under lists if local layouts exist
            if 'zcol' in locals(): zcol.addWidget(self.zone_info)
            elif 'z_layout' in locals(): z_layout.addWidget(self.zone_info)
        except Exception:
            pass
        try:
            if 'gcol' in locals(): gcol.addWidget(self.group_info)
            elif 'g_layout' in locals(): g_layout.addWidget(self.group_info)
        except Exception:
            pass

        self.groups_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        def _group_sel_changed():
            try:
                rows = self.groups_list.selectionModel().selectedRows()
                if not rows:
                    return
                r = rows[0].row()
                it = self.groups_list.item(r)
                name = str(it.text()) if it else None
                if not name:
                    return
                try:
                    self._selected_group = name
                except Exception:
                    pass
                try:
                    if hasattr(self, '_refresh_group_details'):
                        self._refresh_group_details()
                except Exception:
                    pass
            except Exception:
                return
        
        self.groups_list.itemSelectionChanged.connect(_group_sel_changed)
        glay.addWidget(self.groups_list, 1)

        gbtn = QtWidgets.QHBoxLayout()
        self.g_create = QtWidgets.QPushButton("Create from selection")
        def _g_create_from_sel():
            try:
                sel = []
                try:
                    sel = list(getattr(self.app_core, 'get_selection_indices', lambda: [])() or [])
                except Exception:
                    sel = []
                if not sel:
                    QtWidgets.QMessageBox.information(self, 'No selection', 'Select pixels first.')
                    return
                name, ok = QtWidgets.QInputDialog.getText(self, 'Create Group', 'Group name:')
                if not ok:
                    return
                name = str(name or '').strip()
                if not name:
                    return
                p = self._project() if hasattr(self, '_project') else (getattr(self.app_core, 'project', None) or {})
                groups = p.get('groups') or {}
                if not isinstance(groups, dict):
                    groups = {}
                g2 = dict(groups)
                g2[name] = {'indices': sorted(set(int(x) for x in sel))}
                p2 = dict(p)
                p2['groups'] = g2
                if hasattr(self, '_set_project'):
                    self._set_project(p2)
                else:
                    try: self.app_core.project = p2
                    except Exception: pass
                try:
                    self._selected_group = name
                except Exception:
                    pass
                try:
                    self.refresh()
                except Exception:
                    pass
                    # --- Target active layer convenience (Zone/Group) ---
                    self.btn_zone_target_active = QtWidgets.QPushButton('Target active layer → Zone')
                    self.btn_group_target_active = QtWidgets.QPushButton('Target active layer → Group')
                    self.btn_zone_target_active.setToolTip('Sets the active layer target_kind/target_ref to the selected zone')
                    self.btn_group_target_active.setToolTip('Sets the active layer target_kind/target_ref to the selected group')
                    def _set_active_layer_target(kind):
                        try:
                            p = self._project() if hasattr(self, '_project') else (getattr(self.app_core, 'project', None) or {})
                            if not isinstance(p, dict):
                                return
                            layers = p.get('layers') or []
                            if not isinstance(layers, list) or not layers:
                                return
                            ai = int(p.get('active_layer', 0) or 0)
                            if ai < 0 or ai >= len(layers):
                                ai = 0
                            L = layers[ai] if isinstance(layers[ai], dict) else {}
                            name = None
                            idx = 0
                            if kind == 'zone':
                                name = getattr(self, '_selected_zone', None)
                                zones = p.get('zones') or []
                                if isinstance(zones, list):
                                    for zi, Z in enumerate(zones):
                                        zname = None
                                        if isinstance(Z, dict): zname = Z.get('name')
                                        else:
                                            try: zname = getattr(Z, 'name', None)
                                            except Exception: zname = None
                                        if str(zname or '') == str(name or ''):
                                            idx = zi; break
                                elif isinstance(zones, dict):
                                    keys = sorted(zones.keys())
                                    if str(name or '') in keys:
                                        idx = keys.index(str(name))
                            else:
                                name = getattr(self, '_selected_group', None)
                                groups = p.get('groups') or []
                                if isinstance(groups, list):
                                    for gi, G in enumerate(groups):
                                        gname = None
                                        if isinstance(G, dict): gname = G.get('name')
                                        else:
                                            try: gname = getattr(G, 'name', None)
                                            except Exception: gname = None
                                        if str(gname or '') == str(name or ''):
                                            idx = gi; break
                                elif isinstance(groups, dict):
                                    keys = sorted(groups.keys())
                                    if str(name or '') in keys:
                                        idx = keys.index(str(name))
                            if not name:
                                QtWidgets.QMessageBox.information(self, 'Nothing selected', f'Select a {kind} first.')
                                return
                            L2 = dict(L)
                            L2['target_kind'] = 'zone' if kind=='zone' else 'group'
                            L2['target_ref'] = int(idx)
                            layers2 = list(layers)
                            layers2[ai] = L2
                            p2 = dict(p)
                            p2['layers'] = layers2
                            # write back
                            if hasattr(self, '_set_project'):
                                self._set_project(p2)
                            else:
                                try: self.app_core.project = p2
                                except Exception: pass
                        except Exception:
                            return
                    self.btn_zone_target_active.clicked.connect(lambda: _set_active_layer_target('zone'))
                    self.btn_group_target_active.clicked.connect(lambda: _set_active_layer_target('group'))
                    try:
                        if 'zlay' in locals(): zlay.addWidget(self.btn_zone_target_active)
                        if 'glay' in locals(): glay.addWidget(self.btn_group_target_active)
                    except Exception:
                        pass
                    
            except Exception:
                return
        
        self.g_create.clicked.connect(_g_create_from_sel)
        gbtn.addWidget(self.g_create, 1)
        self.g_rename = QtWidgets.QPushButton("Rename")
        def _g_rename_group():
            try:
                name = getattr(self, '_selected_group', None)
                if not name:
                    try:
                        rows = self.groups_list.selectionModel().selectedRows()
                        if rows:
                            it = self.groups_list.item(rows[0].row())
                            name = str(it.text()) if it else None
                    except Exception:
                        name = None
                if not name:
                    return
                new, ok = QtWidgets.QInputDialog.getText(self, 'Rename Group', 'New group name:', text=str(name))
                if not ok:
                    return
                new = str(new or '').strip()
                if not new or new == name:
                    return
                p = self._project() if hasattr(self, '_project') else (getattr(self.app_core, 'project', None) or {})
                groups = p.get('groups') or {}
                if not isinstance(groups, dict) or name not in groups:
                    return
                if new in groups:
                    QtWidgets.QMessageBox.warning(self, 'Rename failed', f"Group '{new}' already exists.")
                    return
                g2 = dict(groups)
                g2[new] = g2.pop(name)
                p2 = dict(p)
                p2['groups'] = g2
                if hasattr(self, '_set_project'):
                    self._set_project(p2)
                else:
                    try: self.app_core.project = p2
                    except Exception: pass
                self._apply_retarget_and_refresh('group', name, new)
                try:
                    self._selected_group = new
                except Exception:
                    pass
                try:
                    self.refresh()
                except Exception:
                    pass
            except Exception:
                return
        
        self.g_rename.clicked.connect(_g_rename_group)
        gbtn.addWidget(self.g_rename)
        self.g_delete = QtWidgets.QPushButton("Delete")
        self.g_to_mask = QtWidgets.QPushButton('Group → Mask')
        self.g_to_sel = QtWidgets.QPushButton('Group → Selection')
        self.g_to_sel.setToolTip('Replace current selection with the selected group indices')

        self.g_to_mask.setToolTip('Create a mask from the selected group (copies indices) and set it as Target Mask')

        def _g_delete_group():
            try:
                name = getattr(self, '_selected_group', None)
                if not name:
                    try:
                        rows = self.groups_list.selectionModel().selectedRows()
                        if rows:
                            it = self.groups_list.item(rows[0].row())
                            name = str(it.text()) if it else None
                    except Exception:
                        name = None
                if not name:
                    return
                resp = QtWidgets.QMessageBox.question(self, 'Delete Group', f"Delete group '{name}'?",
                                                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if resp != QtWidgets.QMessageBox.Yes:
                    return
                p = self._project() if hasattr(self, '_project') else (getattr(self.app_core, 'project', None) or {})
                groups = p.get('groups') or {}
                if not isinstance(groups, dict) or name not in groups:
                    return
                g2 = dict(groups)
                g2.pop(name, None)
                p2 = dict(p)
                p2['groups'] = g2
                if hasattr(self, '_set_project'):
                    self._set_project(p2)
                else:
                    try: self.app_core.project = p2
                    except Exception: pass
                self._apply_retarget_and_refresh('group', name, None)
                try:
                    self._selected_group = None
                except Exception:
                    pass
                try:
                    self.refresh()
                except Exception:
                    pass
            except Exception:
                return
        
        self.g_delete.clicked.connect(_g_delete_group)

        def _g_to_mask():
            try:
                gname = None
                try: gname = getattr(self, 'selected_group', None)
                except Exception: gname = None
                if not gname:
                    QtWidgets.QMessageBox.information(self, 'No group selected', 'Select a group first.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                if not isinstance(p, dict): return
                groups = p.get('groups') or {}
                if not isinstance(groups, dict): groups = {}
                gnode = groups.get(gname)
                if not isinstance(gnode, dict):
                    QtWidgets.QMessageBox.information(self, 'Bad group', 'Selected group data is not a dict.')
                    return
                masks = p.get('masks') or {}
                if not isinstance(masks, dict): masks = {}
                base = f'Group_{gname}'
                mname = base
                k = 1
                while mname in masks:
                    k += 1
                    mname = f'{base}_{k}'
                masks2 = dict(masks)
                masks2[mname] = {'op': 'indices', 'indices': list(gnode.get('indices') or [])}
                p2 = dict(p); p2['masks'] = masks2
                ui = p2.get('ui') or {}
                if not isinstance(ui, dict): ui = {}
                ui2 = dict(ui); ui2['target_mask'] = mname
                p2['ui'] = ui2
                try: self.app_core.project = p2
                except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.g_to_mask.clicked.connect(_g_to_mask)
        except Exception: pass

        gbtn.addWidget(self.g_delete)
        glay.addLayout(gbtn)

        self._targets_left_lay.addWidget(self.groups_box, 1)

        # ---- : Read-only diagnostics (empty / invalid / dangling) ----
        try:
            self.diagnostics_box = QtWidgets.QGroupBox("Diagnostics")
            dlay = QtWidgets.QVBoxLayout(self.diagnostics_box)
            dlay.setContentsMargins(8, 8, 8, 8)
            dlay.setSpacing(6)
            # () Diagnostics actions
            abar = QtWidgets.QHBoxLayout()
            abar.setContentsMargins(0, 0, 0, 0)
            abar.setSpacing(6)

            self.diag_copy_btn = QtWidgets.QPushButton("Copy")
            self.diag_save_btn = QtWidgets.QPushButton("Save…")
            self.diag_refresh_btn = QtWidgets.QPushButton("Refresh")
            self.diag_clear_btn = QtWidgets.QPushButton("Clear")
            try:
                self.diag_clear_btn.setToolTip("Clear LAST RETARGET log")
            except Exception:
                pass
            try:
                self.diag_refresh_btn.setToolTip("Force a refresh of Zones/Groups/Masks + diagnostics")
            except Exception:
                pass
            try:
                self.diag_copy_btn.setToolTip("Copy diagnostics text to clipboard")
                self.diag_save_btn.setToolTip("Save diagnostics text to a file")
            except Exception:
                pass

            abar.addWidget(self.diag_copy_btn)
            abar.addWidget(self.diag_save_btn)
            abar.addWidget(self.diag_refresh_btn)
            abar.addWidget(self.diag_clear_btn)
            abar.addStretch(1)
            dlay.addLayout(abar)
            self.diagnostics_text = QtWidgets.QPlainTextEdit()
            self.diagnostics_header_label = QtWidgets.QLabel("")
            try:
                self.diagnostics_header_label.setWordWrap(True)
            except Exception:
                pass
            dlay.addWidget(self.diagnostics_header_label, 0)
            self.diagnostics_text.setReadOnly(True)
            # () Hook up actions (best-effort; must not block launch)
            try:
                def _diag_copy():
                    try:
                        t = ""
                        try:
                            t = self.diagnostics_text.toPlainText()
                        except Exception:
                            t = ""
                        cb = QtWidgets.QApplication.clipboard()
                        if cb is not None:
                            cb.setText(t)
                    except Exception:
                        pass

                def _diag_save():
                    try:
                        t = ""
                        try:
                            t = self.diagnostics_text.toPlainText()
                        except Exception:
                            t = ""
                        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Diagnostics", "modulo_diagnostics.txt", "Text Files (*.txt);;All Files (*)")
                        if path:
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(t)
                    except Exception:
                        pass

                if hasattr(self, 'diag_copy_btn') and self.diag_copy_btn is not None:
                    self.diag_copy_btn.clicked.connect(_diag_copy)
                if hasattr(self, 'diag_save_btn') and self.diag_save_btn is not None:
                    self.diag_save_btn.clicked.connect(_diag_save)
                def _diag_clear():
                    try:
                        try:
                            self._last_retarget_log = None
                        except Exception:
                            pass
                        try:
                            # force refresh so diagnostics updates immediately
                            if hasattr(self, "_panel_last_rev"):
                                setattr(self, "_panel_last_rev", -1)
                        except Exception:
                            pass
                        try:
                            self.refresh()
                        except Exception:
                            pass
                        try:
                            mp = getattr(self, "masks_panel", None)
                            if mp is not None:
                                fn = getattr(mp, "refresh", None)
                                if callable(fn):
                                    fn()
                        except Exception:
                            pass
                    except Exception:
                        pass

                if hasattr(self, 'diag_clear_btn') and self.diag_clear_btn is not None:
                    self.diag_clear_btn.clicked.connect(_diag_clear)
                def _diag_force_refresh():
                    try:
                        # Force next timer tick to rebuild everything
                        try:
                            setattr(self, "_panel_last_rev", -1)
                        except Exception:
                            pass
                        try:
                            self.refresh()
                        except Exception:
                            pass
                        try:
                            mp = getattr(self, "masks_panel", None)
                            if mp is not None:
                                fn = getattr(mp, "refresh", None)
                                if callable(fn):
                                    fn()
                        except Exception:
                            pass
                    except Exception:
                        pass

                if hasattr(self, 'diag_refresh_btn') and self.diag_refresh_btn is not None:
                    self.diag_refresh_btn.clicked.connect(_diag_force_refresh)
            except Exception:
                pass
            try:
                self.diagnostics_text.setMaximumBlockCount(500)
            except Exception:
                pass
            dlay.addWidget(self.diagnostics_text, 1)
            try:
                self._targets_right_lay.addWidget(self.diagnostics_box, 1)
            except Exception:
                pass
            outer.addWidget(self.diagnostics_box, 0)
        except Exception:
            pass
            # diagnostics are best-effort and must never block launch
            self.diagnostics_box = None
            self.diagnostics_text = None
        outer.addStretch(1)

        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception: pass

        def _z_to_selection():
            try:
                zname = None
                try: zname = getattr(self, 'selected_zone', None)
                except Exception: zname = None
                if not zname:
                    QtWidgets.QMessageBox.information(self, 'No zone selected', 'Select a zone first.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                zones = p.get('zones') if isinstance(p, dict) else None
                znode = zones.get(zname) if isinstance(zones, dict) else None
                idxs = []
                if isinstance(znode, dict) and isinstance(znode.get('indices'), list):
                    for x in (znode.get('indices') or []):
                        try: idxs.append(int(x))
                        except Exception: pass
                elif isinstance(znode, dict):
                    try:
                        s = int(znode.get('start', 0)); e = int(znode.get('end', -1))
                        if e >= s: idxs = list(range(s, e+1))
                    except Exception: idxs = []
                idxs = sorted(set(i for i in idxs if isinstance(i, int) and i >= 0))
                if not idxs:
                    QtWidgets.QMessageBox.information(self, 'Empty zone', 'Selected zone has no indices.')
                    return
                selset = set(idxs)
                for attr in ('selection','selected_indices','selected','sel'):
                    if hasattr(self.app_core, attr):
                        try: setattr(self.app_core, attr, selset)
                        except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.z_to_sel.clicked.connect(_z_to_selection)
        except Exception: pass

        def _g_to_selection():
            try:
                gname = None
                try: gname = getattr(self, 'selected_group', None)
                except Exception: gname = None
                if not gname:
                    QtWidgets.QMessageBox.information(self, 'No group selected', 'Select a group first.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                groups = p.get('groups') if isinstance(p, dict) else None
                gnode = groups.get(gname) if isinstance(groups, dict) else None
                idxs = []
                if isinstance(gnode, dict) and isinstance(gnode.get('indices'), list):
                    for x in (gnode.get('indices') or []):
                        try: idxs.append(int(x))
                        except Exception: pass
                idxs = sorted(set(i for i in idxs if isinstance(i, int) and i >= 0))
                if not idxs:
                    QtWidgets.QMessageBox.information(self, 'Empty group', 'Selected group has no indices.')
                    return
                selset = set(idxs)
                for attr in ('selection','selected_indices','selected','sel'):
                    if hasattr(self.app_core, attr):
                        try: setattr(self.app_core, attr, selset)
                        except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.g_to_sel.clicked.connect(_g_to_selection)
        except Exception: pass

        except Exception:
            pass

    # ----------------------------
    # Project helpers
    # ----------------------------

    def _update_v6_last_fired(self):
        try:
            fn = getattr(self.app_core, "get_rules_v6_last_fired_summary", None)
            if callable(fn):
                s = str(fn() or "")
            else:
                ids = getattr(self.app_core, "_rules_v6_last_fired_ids", []) or []
                s = "Last fired: " + (", ".join([str(x) for x in ids]) if ids else "(none)")
            if not s.lower().startswith("last fired"):
                s = "Last fired: " + s
            try:
                self.v6_last_fired.setText(s)
            except Exception:
                pass
        except Exception:
            pass

    def _project(self):
        try:
            return self.app_core.project or {}
        except Exception:
            try:
                return self.app_core.project or {}
            except Exception:
                return {}




    def refresh(self):
        # () Ensure _last_retarget_log exists (do not clear on refresh)
        try:
            if not hasattr(self, '_last_retarget_log'):
                self._last_retarget_log = None
        except Exception:
            pass
        """Rebuild Zones/Groups lists from the current project."""
        p = self._project()
        zones = p.get('zones') or {}
        groups = p.get('groups') or {}
        if not isinstance(zones, dict):
            zones = {}
        if not isinstance(groups, dict):
            groups = {}
        # ---- Zones list ----
        try:
            self.zones_list.blockSignals(True)
            self.zones_list.clear()
            for k in sorted(zones.keys()):
                self.zones_list.addItem(str(k))
        finally:
            try: self.zones_list.blockSignals(False)
            except Exception: pass
        # ---- Groups list ----
        try:
            self.groups_list.blockSignals(True)
            self.groups_list.clear()
            for k in sorted(groups.keys()):
                self.groups_list.addItem(str(k))
        finally:
            try: self.groups_list.blockSignals(False)
            except Exception: pass
        # restore selections
        try:
            sz = getattr(self, '_selected_zone', None)
            if sz:
                for i in range(self.zones_list.count()):
                    if self.zones_list.item(i).text() == sz:
                        self.zones_list.setCurrentRow(i)
                        break
        except Exception:
            pass
        try:
            sg = getattr(self, '_selected_group', None)
            if sg:
                for i in range(self.groups_list.count()):
                    if self.groups_list.item(i).text() == sg:
                        self.groups_list.setCurrentRow(i)
                        break
        except Exception:
            pass
        # lightweight details
        try:
            self.zones_box.setTitle(f"Zones (Range) — {len(zones)}")
        except Exception:
            pass
        try:
            self.groups_box.setTitle(f"Groups (Set) — {len(groups)}")
        except Exception:
            pass

        # ---- : diagnostics snapshot (read-only) ----
        try:
            dt = getattr(self, 'diagnostics_text', None)
            if dt is not None:
                try:
                    from app.project_diagnostics import diagnostics_text as _diagnostics_text
                except Exception:
                    _diagnostics_text = None
                if _diagnostics_text is not None:
                    txt = str(_diagnostics_text(p) or "")
                    # Don't fight user selection/cursor; just replace whole text.
                    try:
                        dt.blockSignals(True)
                        
                        # () Expanded invariant diagnostics (best-effort; must not crash)
                        try:
                            # Counts
                            try:
                                proj = getattr(self.app_core, "project", None)
                                if callable(proj):
                                    proj = proj()
                            except Exception:
                                proj = None
                            zones = {}
                            groups = {}
                            masks = {}
                            ui_target = None
                            try:
                                if isinstance(proj, dict):
                                    zones = (proj.get("zones") or {})
                                    groups = (proj.get("groups") or {})
                                    masks = (proj.get("masks") or {})
                                    ui = proj.get("ui") or {}
                                    ui_target = ui.get("target_mask")
                            except Exception:
                                pass

                            def _count_items(d):
                                try:
                                    return len(d) if isinstance(d, dict) else 0
                                except Exception:
                                    return 0

                            txt += "\n=== SUMMARY ===\n"
                            txt += f"zones: {_count_items(zones)}\n"
                            txt += f"groups: {_count_items(groups)}\n"
                            txt += f"masks: {_count_items(masks)}\n"
                            if ui_target:
                                txt += f"ui.target_mask: {ui_target}\n"
                            else:
                                txt += "ui.target_mask: (none)\n"

                            # Validate ui.target_mask resolves
                            try:
                                missing = None
                                if isinstance(ui_target, str) and ":" in ui_target:
                                    kind, name = ui_target.split(":", 1)
                                    kind = kind.strip().lower()
                                    name = name.strip()
                                    if kind == "zone" and name and name not in zones:
                                        missing = f"ui.target_mask points to missing zone '{name}'"
                                    if kind == "group" and name and name not in groups:
                                        missing = f"ui.target_mask points to missing group '{name}'"
                                    if kind == "mask" and name and name not in masks:
                                        missing = f"ui.target_mask points to missing mask '{name}'"
                                if missing:
                                    txt += "\nDANGLING:\n- " + missing + "\n"
                            except Exception:
                                pass

                            # Empty definitions: zones/groups with empty indices, masks with no indices/resolution
                            empty_lines = []
                            try:
                                for zn, zdef in (zones or {}).items():
                                    try:
                                        idxs = (zdef or {}).get("indices")
                                        if not idxs:
                                            empty_lines.append(f"- zone '{zn}' has empty indices")
                                    except Exception:
                                        pass
                                for gn, gdef in (groups or {}).items():
                                    try:
                                        idxs = (gdef or {}).get("indices")
                                        if not idxs:
                                            empty_lines.append(f"- group '{gn}' has empty indices")
                                    except Exception:
                                        pass
                                for mn, mdef in (masks or {}).items():
                                    try:
                                        # allow either explicit indices or refs; treat as empty if both absent
                                        idxs = (mdef or {}).get("indices")
                                        refs = (mdef or {}).get("refs") or (mdef or {}).get("targets")
                                        if (not idxs) and (not refs):
                                            empty_lines.append(f"- mask '{mn}' has no indices/refs")
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            if empty_lines:
                                txt += "\nEMPTY:\n" + "\n".join(empty_lines) + "\n"

                                                        # () Dangling refs inside masks (zone:/group:/mask:)
                            try:
                                dangling_ref_lines = []
                                for mn, mdef in (masks or {}).items():
                                    refs = None
                                    try:
                                        refs = (mdef or {}).get("refs")
                                    except Exception:
                                        refs = None
                                    if not refs:
                                        try:
                                            refs = (mdef or {}).get("targets")
                                        except Exception:
                                            refs = None
                                    if refs is None:
                                        refs = []
                                    if isinstance(refs, str):
                                        refs = [refs]
                                    if not isinstance(refs, (list, tuple)):
                                        refs = []
                                    for ref in refs:
                                        if not isinstance(ref, str):
                                            continue
                                        if ":" not in ref:
                                            continue
                                        try:
                                            kind, name = ref.split(":", 1)
                                        except Exception:
                                            continue
                                        kind = (kind or "").strip().lower()
                                        name = (name or "").strip()
                                        if not name:
                                            continue
                                        if kind == "zone" and name not in (zones or {}):
                                            dangling_ref_lines.append(f"- mask '{mn}' refs missing zone '{name}'")
                                        elif kind == "group" and name not in (groups or {}):
                                            dangling_ref_lines.append(f"- mask '{mn}' refs missing group '{name}'")
                                        elif kind == "mask" and name not in (masks or {}):
                                            dangling_ref_lines.append(f"- mask '{mn}' refs missing mask '{name}'")
                                if dangling_ref_lines:
                                    txt += "\nDANGLING (mask refs):\n" + "\n".join(dangling_ref_lines) + "\n"
                            except Exception:
                                pass

# Duplicate / out-of-range indices if we can infer pixel count
                            try:
                                # best-effort pixel count inference
                                pixel_count = None
                                try:
                                    if isinstance(proj, dict):
                                        layout = proj.get("layout") or {}
                                        pixel_count = layout.get("pixel_count") or layout.get("num_pixels") or None
                                        if pixel_count is not None:
                                            pixel_count = int(pixel_count)
                                except Exception:
                                    pixel_count = None

                                def _scan_indices(label, name, idxs):
                                    issues=[]
                                    try:
                                        if not idxs:
                                            return issues
                                        seen=set()
                                        for i in idxs:
                                            try:
                                                ii=int(i)
                                            except Exception:
                                                issues.append(f"- {label} '{name}' has non-int index: {i}")
                                                continue
                                            if ii in seen:
                                                issues.append(f"- {label} '{name}' has duplicate index: {ii}")
                                            else:
                                                seen.add(ii)
                                            if pixel_count is not None and (ii < 0 or ii >= pixel_count):
                                                issues.append(f"- {label} '{name}' has out-of-range index: {ii} (0..{pixel_count-1})")
                                    except Exception:
                                        pass
                                    return issues

                                idx_issues=[]
                                for zn, zdef in (zones or {}).items():
                                    idx_issues += _scan_indices("zone", zn, (zdef or {}).get("indices") or [])
                                for gn, gdef in (groups or {}).items():
                                    idx_issues += _scan_indices("group", gn, (gdef or {}).get("indices") or [])
                                if idx_issues:
                                    txt += "\nINDICES:\n" + "\n".join(idx_issues) + "\n"
                            except Exception:
                                pass

                        except Exception:
                            pass

                        # () Prepend LAST RETARGET (boot-safe; no new try blocks)

                        lr = getattr(self, '_last_retarget_log', None)

                        if lr:

                            try:

                                txt = "=== LAST RETARGET ===\n" + "\n".join([str(x) for x in lr]) + "\n\n" + txt

                            except Exception:

                                pass

                        dt.setPlainText(txt)
                        try:
                            hl = getattr(self, "diagnostics_header_label", None)
                            if hl is not None:
                                # Best-effort stamp; avoid crashes
                                try:
                                    rev = int(getattr(self.app_core, 'project_revision', lambda: 0)() if self.app_core is not None else 0)
                                except Exception:
                                    rev = 0
                                try:
                                    ts = time.strftime('%Y-%m-%d %H:%M:%S')
                                except Exception:
                                    ts = ""
                                hl.setText(f"Last updated: {ts}   |   project_revision: {rev}")
                        except Exception:
                            pass
                    finally:
                        try: dt.blockSignals(False)
                        except Exception: pass
        except Exception:
            pass

    def sync_from_project(self):
        """Compatibility shim used by some older call sites."""
        try:
            self.refresh()
        except Exception:
            pass

    def _refresh_zone_details(self):
        # Minimal: keep titles updated; full details UI can come later.
        try:
            self.refresh()
        except Exception:
            pass

    def _refresh_group_details(self):
        try:
            self.refresh()
        except Exception:
            pass






# () Removed stray duplicated top-level Zones/Groups helpers; panel methods handle this.


class _RuleRow(QtWidgets.QWidget):
    def __init__(self, app_core, index: int, on_change, on_remove):
        super().__init__()
        self.app_core = app_core
        self.index = index
        self._on_change = on_change
        self._on_remove = on_remove
        self._suppress = False

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.enabled = QtWidgets.QCheckBox()
        self.enabled.setChecked(True)
        self.enabled.toggled.connect(self._changed)
        lay.addWidget(self.enabled)

        # Source type: parameter (layer param) or audio signal.
        self.src_kind = QtWidgets.QComboBox()
        self.src_kind.addItems(["Param", "Audio"])
        self.src_kind.currentIndexChanged.connect(self._src_kind_changed)
        lay.addWidget(self.src_kind)

        # Parameter source controls
        self.src_layer = QtWidgets.QComboBox(); lay.addWidget(self.src_layer)
        self.src_param = QtWidgets.QComboBox(); lay.addWidget(self.src_param)

        # Audio source controls (hidden unless src_kind == Audio)
        self.src_audio = QtWidgets.QComboBox(); lay.addWidget(self.src_audio)
        self.src_audio.setVisible(False)

        self.cond = QtWidgets.QComboBox(); self.cond.addItems([">", "<", "between"])
        self.cond.currentIndexChanged.connect(self._cond_changed)
        lay.addWidget(self.cond)

        self.a = QtWidgets.QDoubleSpinBox(); self.a.setRange(-1e6, 1e6); self.a.setDecimals(4); self.a.setValue(0.5)
        self.a.valueChanged.connect(self._changed)
        lay.addWidget(self.a)

        self.b = QtWidgets.QDoubleSpinBox(); self.b.setRange(-1e6, 1e6); self.b.setDecimals(4); self.b.setValue(1.0)
        self.b.valueChanged.connect(self._changed)
        self.b.setVisible(False)
        lay.addWidget(self.b)

        self.dst_layer = QtWidgets.QComboBox(); lay.addWidget(self.dst_layer)
        self.dst_param = QtWidgets.QComboBox(); lay.addWidget(self.dst_param)

        self.action = QtWidgets.QComboBox(); self.action.addItems(["set", "add"])
        self.action.currentIndexChanged.connect(self._action_changed)
        lay.addWidget(self.action)

        self.value = QtWidgets.QDoubleSpinBox(); self.value.setRange(-1e6, 1e6); self.value.setDecimals(4); self.value.setValue(0.0)
        self.value.valueChanged.connect(self._changed)
        lay.addWidget(self.value)

        self.del_btn = QtWidgets.QToolButton(); self.del_btn.setText("✕")
        self.del_btn.clicked.connect(lambda: self._on_remove(self.index))
        lay.addWidget(self.del_btn)

        for cb in (self.src_layer, self.src_param, self.dst_layer, self.dst_param):
            cb.currentIndexChanged.connect(self._changed)

        self.src_audio.currentIndexChanged.connect(self._changed)

        # Populate audio source list once.
        self.src_audio.addItems(self._audio_source_names())

        # Default UI state
        self._src_kind_changed()

    def _audio_source_names(self):
        # Mirror Spectrum Shield style sources (0..1): energy, mono0..6, l0..6, r0..6
        out = ["energy"]
        for i in range(7):
            out.append(f"mono{i}")
        for i in range(7):
            out.append(f"l{i}")
        for i in range(7):
            out.append(f"r{i}")
        return out

    def _src_kind_changed(self):
        is_audio = (self.src_kind.currentText().strip().lower() == "audio")
        self.src_layer.setVisible(not is_audio)
        self.src_param.setVisible(not is_audio)
        self.src_audio.setVisible(is_audio)
        self._changed()

    def _float_param_names(self):
        out = []
        try:
            for k, meta in (PARAMS or {}).items():
                if (meta or {}).get("type") == "float":
                    out.append(str(k))
        except Exception:
            out = []
        return sorted(set(out))

    def _layer_names(self):
        try:
            p = self.app_core.project or {}
            layers = list(p.get("layers") or [])
            return [f"{i}: {str(L.get('name','Layer'))}" for i, L in enumerate(layers)]
        except Exception:
            return []

    def sync(self, rule: dict):
        self._suppress = True
        try:
            self.src_layer.clear(); self.dst_layer.clear()
            self.src_param.clear(); self.dst_param.clear()
            # Do not clear src_audio items; it is static

            ln = self._layer_names()
            if not ln:
                ln = ["0: Layer 0"]
            self.src_layer.addItems(ln)
            self.dst_layer.addItems(ln)

            pn = self._float_param_names()
            if not pn:
                pn = ["brightness"]
            self.src_param.addItems(pn)
            self.dst_param.addItems(pn)

            self.enabled.setChecked(bool(rule.get("enabled", True)))

            sk = str(rule.get("src_kind", "param") or "param").strip().lower()
            self.src_kind.setCurrentText("Audio" if sk in ("audio","a") else "Param")

            sl = int(rule.get("src_layer", 0) or 0)
            dl = int(rule.get("dst_layer", 0) or 0)
            self.src_layer.setCurrentIndex(max(0, min(sl, self.src_layer.count()-1)))
            self.dst_layer.setCurrentIndex(max(0, min(dl, self.dst_layer.count()-1)))

            sp = str(rule.get("src_param", "brightness") or "brightness")
            dp = str(rule.get("dst_param", "brightness") or "brightness")
            ix = self.src_param.findText(sp); self.src_param.setCurrentIndex(ix if ix >= 0 else 0)
            ix = self.dst_param.findText(dp); self.dst_param.setCurrentIndex(ix if ix >= 0 else 0)

            sa = str(rule.get("src_audio", "energy") or "energy").strip().lower()
            ix = self.src_audio.findText(sa)
            self.src_audio.setCurrentIndex(ix if ix >= 0 else 0)

            cond = str(rule.get("cond", "gt") or "gt").lower().strip()
            if cond in ("lt", "<"):
                self.cond.setCurrentText("<")
            elif cond in ("between", "rng", "range"):
                self.cond.setCurrentText("between")
            else:
                self.cond.setCurrentText(">")

            self.a.setValue(float(rule.get("a", 0.5) or 0.5))
            self.b.setValue(float(rule.get("b", 1.0) or 1.0))

            act = str(rule.get("action", "set") or "set").lower().strip()
            self.action.setCurrentText("add" if act in ("add","inc","+") else "set")
            self.value.setValue(float(rule.get("value", 0.0) or 0.0))

            self._cond_changed()
            self._src_kind_changed()
        finally:
            self._suppress = False

    def _cond_changed(self):
        txt = self.cond.currentText().strip().lower()
        self.b.setVisible(txt == "between")
        self._changed()

    def to_dict(self) -> dict:
        cond_txt = self.cond.currentText().strip().lower()
        cond = "between" if cond_txt == "between" else ("lt" if cond_txt == "<" else "gt")
        sk_txt = self.src_kind.currentText().strip().lower()
        src_kind = "audio" if sk_txt == "audio" else "param"
        return {
            "enabled": bool(self.enabled.isChecked()),
            "src_kind": src_kind,
            "src_layer": int(self.src_layer.currentIndex()),
            "src_param": str(self.src_param.currentText()),
            "src_audio": str(self.src_audio.currentText()).strip().lower(),
            "cond": cond,
            "a": float(self.a.value()),
            "b": float(self.b.value()),
            "dst_layer": int(self.dst_layer.currentIndex()),
            "dst_param": str(self.dst_param.currentText()),
            "action": str(self.action.currentText()),
            "value": float(self.value.value()),
        }

    def _changed(self):
        if self._suppress:
            return
        try:
            self._on_change(self.index, self.to_dict())
        except Exception:
            pass


class _ModRow(QtWidgets.QWidget):
    """One continuous audio->parameter modulotor row."""

    def __init__(self, app_core, index: int, on_change, on_remove):
        super().__init__()
        self.app_core = app_core
        self.index = index
        self._on_change = on_change
        self._on_remove = on_remove
        self._suppress = False

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.enabled = QtWidgets.QCheckBox()
        self.enabled.setChecked(True)
        self.enabled.toggled.connect(self._changed)
        lay.addWidget(self.enabled)

        self.src = QtWidgets.QComboBox()
        # User-friendly labels, stable internal source IDs matching params.modulotors.Modulotor
        for label, sid in self._audio_source_items():
            self.src.addItem(label, sid)
        self.src.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.src)

        self.layer = QtWidgets.QComboBox(); lay.addWidget(self.layer)
        self.param = QtWidgets.QComboBox(); lay.addWidget(self.param)

        self.mode = QtWidgets.QComboBox(); self.mode.addItems(["mul", "add", "set"])
        self.mode.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.mode)

        self.amount = QtWidgets.QDoubleSpinBox()
        self.amount.setRange(-10.0, 10.0)
        self.amount.setDecimals(4)
        self.amount.setSingleStep(0.05)
        self.amount.valueChanged.connect(self._changed)
        lay.addWidget(self.amount)

        self.smooth = QtWidgets.QDoubleSpinBox()
        self.smooth.setRange(0.0, 0.99)
        self.smooth.setDecimals(3)
        self.smooth.setSingleStep(0.02)
        self.smooth.valueChanged.connect(self._changed)
        lay.addWidget(self.smooth)

        self.del_btn = QtWidgets.QToolButton(); self.del_btn.setText("✕")
        self.del_btn.clicked.connect(lambda: self._on_remove(self.index))
        lay.addWidget(self.del_btn)

        self.layer.currentIndexChanged.connect(self._layer_changed)
        self.param.currentIndexChanged.connect(self._changed)

        self._populate_layers()

    def _audio_source_items(self):
        """Populate modulotor sources.

        IMPORTANT: Sources should reflect the normalized signal bus *labels*,
        but store stable internal IDs compatible with params.registry.SOURCES
        / params.modulotors.Modulotor.sample().
        """
        try:
            from export.exportable_surface import MODULATION_SOURCES_EXPORTABLE
            srcs = list(MODULATION_SOURCES_EXPORTABLE)
        except Exception:
            srcs = ["none", "lfo_sine", "audio_energy"]

        def _label(sid: str) -> str:
            sid = (sid or "none").strip()
            if sid == "none":
                return "none"
            if sid == "lfo_sine":
                return "lfo.sine"
            if sid == "audio_energy":
                return "audio.energy"
            if sid.startswith("audio_mono"):
                return "audio.mono" + sid.replace("audio_mono", "")
            if sid.startswith("audio_L"):
                return "audio.L" + sid.replace("audio_L", "")
            if sid.startswith("audio_R"):
                return "audio.R" + sid.replace("audio_R", "")
            if sid.startswith("audio_tr_L"):
                return "audio.tr.L" + sid.replace("audio_tr_L", "")
            if sid.startswith("audio_tr_R"):
                return "audio.tr.R" + sid.replace("audio_tr_R", "")
            if sid.startswith("audio_pk_L"):
                return "audio.pk.L" + sid.replace("audio_pk_L", "")
            if sid.startswith("audio_pk_R"):
                return "audio.pk.R" + sid.replace("audio_pk_R", "")
            if sid.startswith("audio_"):
                return "audio." + sid.replace("audio_", "")
            if sid.startswith("purpose_f"):
                return "purpose.f" + sid.replace("purpose_f", "")
            return sid

        items = []
        for sid in srcs:
            items.append((_label(sid), sid))
        return items

    def _populate_layers(self):
        self.layer.blockSignals(True)
        self.layer.clear()
        try:
            p = self.app_core.project or {}
        except Exception:
            p = {}
        layers = list(p.get("layers") or [])
        for i, L in enumerate(layers):
            name = (L or {}).get("name") or f"Layer {i}"
            self.layer.addItem(str(name), i)
        self.layer.blockSignals(False)
        self._populate_params()

    def _populate_params(self):
        """Populate modulotion targets.

        IMPORTANT: This dropdown must *not* reflect arbitrary layer params.
        It should surface only targets that are known-exportable (surface matrix),
        to avoid creating projects that cannot export.

        Back-compat: if the current mod target is not in the exportable list,
        we still include it so older projects can be edited without data loss.
        """
        self.param.blockSignals(True)
        self.param.clear()

        try:
            from export.exportable_surface import MODULATION_TARGETS_EXPORTABLE
            allowed = list(MODULATION_TARGETS_EXPORTABLE)
        except Exception:
            allowed = ["speed", "brightness", "width", "softness", "density"]

        # Keep stable ordering
        for k in allowed:
            self.param.addItem(k, k)

        self.param.blockSignals(False)

    def _layer_changed(self):
        if self._suppress:
            return
        self._populate_params()
        self._changed()

    def _changed(self):
        if self._suppress:
            return
        self._on_change(self.index, self.to_dict())

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled.isChecked()),
            "layer": int(self.layer.currentData() or 0),
            "target": str(self.param.currentData() or self.param.currentText() or "brightness"),
            "source": str(self.src.currentData() or "audio_energy"),
            "mode": str(self.mode.currentText() or "mul"),
            "amount": float(self.amount.value()),
            "smooth": float(self.smooth.value()),
        }

    def sync(self, mod: dict):
        self._suppress = True
        try:
            if not isinstance(mod, dict):
                mod = {}
            self.enabled.setChecked(bool(mod.get("enabled", True)))
            self._populate_layers()

            src = str(mod.get("source", "audio_energy"))
            # Select by internal data when possible
            k = self.src.findData(src)
            if k >= 0:
                self.src.setCurrentIndex(k)

            li = int(mod.get("layer", 0) or 0)
            idx = self.layer.findData(li)
            if idx >= 0:
                self.layer.setCurrentIndex(idx)
            self._populate_params()

            tgt = str(mod.get("target", "brightness"))
            j = self.param.findData(tgt)
            if j >= 0:
                self.param.setCurrentIndex(j)
            else:
                self.param.addItem(tgt, tgt)
                self.param.setCurrentIndex(self.param.count() - 1)

            mode = str(mod.get("mode", "mul"))
            if mode in ["mul", "add", "set"]:
                self.mode.setCurrentText(mode)

            self.amount.setValue(float(mod.get("amount", 0.5) or 0.0))
            self.smooth.setValue(float(mod.get("smooth", 0.0) or 0.0))
        finally:
            self._suppress = False



class _V6ConditionsDialog(QtWidgets.QDialog):
    """Edit Phase 6 rule conditions (AND/OR list)."""

    def __init__(self, parent, conditions: list, signal_names: list, mode: str = "all"):
        super().__init__(parent)
        self._mode = str(mode or "all")
        if self._mode not in ("all","any"):
            self._mode = "all"
        self.setWindowTitle("Edit Conditions")
        self._signal_names = list(signal_names or [])
        self._rows = []

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        mode_row = QtWidgets.QHBoxLayout()

        mode_lbl = QtWidgets.QLabel("Mode")
        mode_row.addWidget(mode_lbl)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("ALL (AND)", "all")
        self.mode_combo.addItem("ANY (OR)", "any")
        k_mode = self.mode_combo.findData(self._mode)
        if k_mode >= 0:
            self.mode_combo.setCurrentIndex(k_mode)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch(1)
        outer.addLayout(mode_row)

        info = QtWidgets.QLabel("")
        info.setWordWrap(True)
        self._info_label = info
        def _sync_info():
            try:
                m = str(self.mode_combo.currentData() or "all")
            except Exception:
                m = "all"
            if m == "any":
                info.setText("Rule fires if ANY enabled condition is true (OR).")
            else:
                info.setText("Rule fires only if ALL enabled conditions are true (AND).")
        try:
            self.mode_combo.currentIndexChanged.connect(_sync_info)
        except Exception:
            pass
        _sync_info()
        outer.addWidget(info)
        self._warn_label = QtWidgets.QLabel("")
        self._warn_label.setWordWrap(True)
        self._warn_label.setStyleSheet("font-size: 10px; color: #b36b00;")
        outer.addWidget(self._warn_label)

        self.rows_lay = QtWidgets.QVBoxLayout()
        self.rows_lay.setSpacing(6)
        outer.addLayout(self.rows_lay)

        btn_row = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("+ Add condition")
        self.add_btn.clicked.connect(self._add_row)
        btn_row.addWidget(self.add_btn)
        btn_row.addStretch(1)

        ok = QtWidgets.QPushButton("OK")
        ok.clicked.connect(self.accept)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        outer.addLayout(btn_row)

        for c in (conditions or []):
            if isinstance(c, dict):
                self._add_row(c)
        if not self._rows:
            self._add_row({})
        try:
            self._sync_warn()
        except Exception:
            pass

    def get_mode(self) -> str:
        try:
            m = str(self.mode_combo.currentData() or "all")
        except Exception:
            m = "all"
        if m not in ("all","any"):
            m = "all"
        return m


    def _sync_warn(self):
        try:
            known = set([str(x) for x in (self._signal_names or []) if str(x).strip()])
            unknown = []
            for row in (self._rows or []):
                try:
                    # row tuple: (widget, sig_combo, op_combo, val_spin, ...)
                    sig = row[1] if isinstance(row, (list, tuple)) and len(row) > 1 else None
                    s = str(sig.currentText() or '') if sig is not None else ''
                except Exception:
                    s = ''
                if s and s not in known:
                    unknown.append(s)
            if unknown:
                self._warn_label.setText("⚠ Unknown signal(s): " + ", ".join(sorted(set(unknown))))
            else:
                self._warn_label.setText("")
        except Exception:
            try:
                self._warn_label.setText("")
            except Exception:
                pass


    def _add_row(self, c: dict | None = None):
        c = c if isinstance(c, dict) else {}
        roww = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(roww)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        sig = QtWidgets.QComboBox()
        sig.setEditable(True)
        sig.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        sig.addItems(self._signal_names)
        cs = str(c.get("signal","") or "")
        if cs:
            k = sig.findText(cs)
            if k >= 0:
                sig.setCurrentIndex(k)
            else:
                sig.setEditText(cs)
        sig.setMinimumWidth(220)
        lay.addWidget(sig)
        try:
            sig.currentTextChanged.connect(self._sync_warn)
        except Exception:
            pass

        op = QtWidgets.QComboBox()
        for o in [">", ">=", "<", "<=", "=="]:
            op.addItem(o, o)
        oo = str(c.get("op", ">") or ">")
        k2 = op.findData(oo)
        if k2 >= 0:
            op.setCurrentIndex(k2)
        op.setFixedWidth(60)
        lay.addWidget(op)

        val = QtWidgets.QDoubleSpinBox()
        val.setDecimals(3)
        val.setRange(-9999.0, 9999.0)
        val.setSingleStep(0.05)
        try:
            val.setValue(float(c.get("value", 0.0)))
        except Exception:
            val.setValue(0.0)
        val.setFixedWidth(110)
        lay.addWidget(val)

        rm = QtWidgets.QToolButton()
        rm.setText("✕")
        rm.setToolTip("Remove this condition")
        rm.clicked.connect(lambda: self._remove_row(roww))
        rm.setFixedWidth(28)
        lay.addWidget(rm)

        self.rows_lay.addWidget(roww)
        self._rows.append((roww, sig, op, val))
        try:
            self._sync_warn()
        except Exception:
            pass

    def _remove_row(self, roww):
        self._rows = [(w,s,o,v) for (w,s,o,v) in self._rows if w is not roww]
        roww.setParent(None)
        roww.deleteLater()
        if not self._rows:
            self._add_row({})
        try:
            self._sync_warn()
        except Exception:
            pass

    def get_conditions(self) -> list:
        out = []
        for (_, sig, op, val) in self._rows:
            s = str(sig.currentText() or "").strip()
            if not s:
                continue
            out.append({
                "signal": s,
                "op": str(op.currentData() or ">"),
                "value": float(val.value()),
            })
        return out

class _RuleV6Row(QtWidgets.QWidget):
    """Phase 6.3 Rules row (Signals -> Variables / Layer Params)."""

    def __init__(self, app_core, idx: int, write_cb, remove_cb):
        super().__init__()
        self.app_core = app_core
        self.index = idx
        self._on_change = write_cb
        self._on_remove = remove_cb
        self._suppress = False

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.enabled = QtWidgets.QCheckBox()
        self.enabled.stateChanged.connect(self._changed)
        lay.addWidget(self.enabled)

        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("name")
        self.name.setFixedWidth(120)
        self.name.editingFinished.connect(self._changed)
        lay.addWidget(self.name)

        self.trigger = QtWidgets.QComboBox()
        self.trigger.addItem("Tick", "tick")
        self.trigger.addItem("Threshold", "threshold")
        self.trigger.addItem("Rising", "rising")
        self.trigger.currentIndexChanged.connect(self._changed)
        self.trigger.setFixedWidth(95)
        lay.addWidget(self.trigger)

        self.signal = QtWidgets.QComboBox()
        self.signal.setEditable(True)
        self.signal.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.signal.setFixedWidth(150)
        self.signal.currentIndexChanged.connect(self._changed)
        self.signal.lineEdit().editingFinished.connect(self._changed)
        lay.addWidget(self.signal)

        self.op = QtWidgets.QComboBox()
        for o in [">", ">=", "<", "<=", "=="]:
            self.op.addItem(o, o)
        self.op.setFixedWidth(55)
        self.op.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.op)

        self.thr = QtWidgets.QDoubleSpinBox()
        self.thr.setDecimals(3)
        self.thr.setRange(-9999.0, 9999.0)
        self.thr.setSingleStep(0.05)
        self.thr.valueChanged.connect(self._changed)
        self.thr.setFixedWidth(90)
        lay.addWidget(self.thr)

        self.hyst = QtWidgets.QDoubleSpinBox()
        self.hyst.setDecimals(3)
        self.hyst.setRange(0.0, 9999.0)
        self.hyst.setSingleStep(0.02)
        self.hyst.valueChanged.connect(self._changed)
        self.hyst.setFixedWidth(80)
        lay.addWidget(self.hyst)

        # Phase 6.7: AND conditions list editor (multi-condition)
        self.cond_enable = QtWidgets.QCheckBox("C")
        self.cond_enable.setToolTip("Enable conditions gate (AND/OR selectable).")
        self.cond_enable.setFixedWidth(32)
        self.cond_enable.stateChanged.connect(self._changed)
        lay.addWidget(self.cond_enable)

        self._conds = []
        self._cond_mode = "all"

        self.cond_summary = QtWidgets.QLabel("cond: (none)")
        self.cond_summary.setToolTip("Conditions summary. Click '…' to edit conditions list.")
        self.cond_summary.setFixedWidth(220)
        self.cond_summary.setStyleSheet("font-size: 10px; color: #777;")
        lay.addWidget(self.cond_summary)

        self.cond_edit = QtWidgets.QToolButton()
        self.cond_edit.setText("…")
        self.cond_edit.setToolTip("Edit conditions (AND/OR)")
        self.cond_edit.clicked.connect(self._edit_conditions)
        self.cond_edit.setFixedWidth(26)
        lay.addWidget(self.cond_edit)

        self.action = QtWidgets.QComboBox()
        self.action.addItem("Set #Var", "set_var_num")
        self.action.addItem("Add #Var", "add_var_num")
        self.action.addItem("Pulse #Var", "pulse_var_num")
        self.action.addItem("Set Toggle", "set_var_toggle")
        self.action.addItem("Flip Toggle", "flip_toggle")
        self.action.addItem("Set Layer Param", "set_layer_param")
        self.action.setFixedWidth(120)
        self.action.currentIndexChanged.connect(self._action_changed)
        lay.addWidget(self.action)
        # Phase 6.9: conflict policy (applies to 'set' style actions)
        self.conflict = QtWidgets.QComboBox()
        self.conflict.setFixedWidth(80)
        self.conflict.setToolTip("Conflict policy when multiple rules set the same target in one tick.")
        self.conflict.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.conflict)


        self.var = QtWidgets.QComboBox()
        self.var.setEditable(True)
        self.var.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.var.setFixedWidth(120)
        self.var.currentIndexChanged.connect(self._changed)
        self.var.lineEdit().editingFinished.connect(self._changed)
        lay.addWidget(self.var)

        self.layer = QtWidgets.QSpinBox()
        self.layer.setRange(0, 999)
        self.layer.setFixedWidth(60)
        self.layer.valueChanged.connect(self._changed)
        lay.addWidget(self.layer)
        self.layer = QtWidgets.QSpinBox()
        self.layer.setRange(0, 999)
        self.layer.setFixedWidth(60)
        self.layer.valueChanged.connect(self._changed)
        lay.addWidget(self.layer)

        self.layer_active = QtWidgets.QCheckBox("AL")
        self.layer_active.setToolTip("Use active layer instead of the numeric index.")
        self.layer_active.setFixedWidth(40)
        self.layer_active.stateChanged.connect(self._changed)
        lay.addWidget(self.layer_active)

        # Exportable Surface Matrix: offer only exportable params for set_layer_param.
        self.param = QtWidgets.QComboBox()
        self.param.setFixedWidth(155)
        self.param.setToolTip("Layer param to set (exportable subset)")
        try:
            from export.exportable_surface import RULES_LAYER_PARAMS_EXPORTABLE
            for p in RULES_LAYER_PARAMS_EXPORTABLE:
                self.param.addItem(p, p)
        except Exception:
            pass
            # Fail-safe: keep a minimal list.
            for p in ("opacity", "brightness"):
                self.param.addItem(p, p)
        self.param.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.param)

        self.expr_src = QtWidgets.QComboBox()
        self.expr_src.addItem("Const", "const")
        self.expr_src.addItem("Signal", "signal")
        self.expr_src.setFixedWidth(75)
        self.expr_src.currentIndexChanged.connect(self._changed)
        lay.addWidget(self.expr_src)

        self.const = QtWidgets.QDoubleSpinBox()
        self.const.setDecimals(3)
        self.const.setRange(-9999.0, 9999.0)
        self.const.setSingleStep(0.05)
        self.const.setFixedWidth(90)
        self.const.valueChanged.connect(self._changed)
        lay.addWidget(self.const)

        self.scale = QtWidgets.QDoubleSpinBox()
        self.scale.setDecimals(3)
        self.scale.setRange(-9999.0, 9999.0)
        self.scale.setSingleStep(0.05)
        self.scale.setFixedWidth(80)
        self.scale.valueChanged.connect(self._changed)
        lay.addWidget(self.scale)

        self.bias = QtWidgets.QDoubleSpinBox()
        self.bias.setDecimals(3)
        self.bias.setRange(-9999.0, 9999.0)
        self.bias.setSingleStep(0.05)
        self.bias.setFixedWidth(80)
        self.bias.valueChanged.connect(self._changed)
        lay.addWidget(self.bias)

        self.del_btn = QtWidgets.QPushButton("✕")
        self.del_btn.setFixedWidth(28)
        self.del_btn.clicked.connect(lambda: self._on_remove(self.index))
        lay.addWidget(self.del_btn)

        try:
            self._update_conflict_choices()
        except Exception:
            pass

        # Phase 6.5: per-rule debug display (last state / fired / errors)
        self.debug = QtWidgets.QLabel("")
        self.debug.setWordWrap(True)
        try:
            self.debug.setStyleSheet("font-size: 10px; color: #888;")
        except Exception:
            pass
        self.debug.setFixedWidth(220)
        lay.addWidget(self.debug)

        lay.addStretch(1)

    def populate_signal_choices(self, names: List[str]) -> None:
        try:
            cur = str(self.signal.currentText() or "")
            self.signal.blockSignals(True)
            self.signal.clear()
            for n in names:
                self.signal.addItem(n, n)
            if cur:
                k = self.signal.findText(cur)
                if k >= 0:
                    self.signal.setCurrentIndex(k)
                else:
                    self.signal.setEditText(cur)
        except Exception:
            pass
        finally:
            try:
                self.signal.blockSignals(False)
            except Exception:
                pass

        # Keep condition signal list in sync
        try:
            cur2 = str(getattr(self, "cond_signal", None).currentText() or "") if hasattr(self, "cond_signal") else ""
            if hasattr(self, "cond_signal"):
                self.cond_signal.blockSignals(True)
                self.cond_signal.clear()
                for n in names:
                    self.cond_signal.addItem(n, n)
                if cur2:
                    k2 = self.cond_signal.findText(cur2)
                    if k2 >= 0:
                        self.cond_signal.setCurrentIndex(k2)
                    else:
                        self.cond_signal.setEditText(cur2)
        except Exception:
            pass
        finally:
            try:
                if hasattr(self, "cond_signal"):
                    self.cond_signal.blockSignals(False)
            except Exception:
                pass

    def populate_var_choices(self, nums: List[str], toggles: List[str]) -> None:
        try:
            cur = str(self.var.currentText() or "")
            self.var.blockSignals(True)
            self.var.clear()
            # Show both, but keep stable order.
            for n in sorted(set(nums + toggles), key=lambda x: str(x)):
                self.var.addItem(n, n)
            if cur:
                k = self.var.findText(cur)
                if k >= 0:
                    self.var.setCurrentIndex(k)
                else:
                    self.var.setEditText(cur)
        except Exception:
            pass
        finally:
            try:
                self.var.blockSignals(False)
            except Exception:
                pass

    def _changed(self):
        if self._suppress:
            return
        try:
            self._on_change(self.index, self.to_dict())
        except Exception:
            pass

    def _update_v6_last_fired(self):
        try:
            fn = getattr(self.app_core, "get_rules_v6_last_fired_summary", None)
            if callable(fn):
                s = str(fn() or "")
            else:
                ids = getattr(self.app_core, "_rules_v6_last_fired_ids", []) or []
                s = "Last fired: " + (", ".join([str(x) for x in ids]) if ids else "(none)")
            if not s.lower().startswith("last fired"):
                s = "Last fired: " + s
            try:
                self.v6_last_fired.setText(s)
            except Exception:
                pass
        except Exception:
            pass



    def _edit_conditions(self):
        # Prefer the same normalized signal list used by the row UI.
        sigs = list(getattr(self, '_signal_names', []) or [])
        if not sigs:
            try:
                snap = self.app_core.get_signal_snapshot() if hasattr(self.app_core, 'get_signal_snapshot') else {}
                sigs = sorted([k for k in (snap or {}).keys() if isinstance(k, str)])
            except Exception:
                sigs = []
        try:
            dlg = _V6ConditionsDialog(self, list(self._conds or []), sigs, mode=getattr(self, "_cond_mode", "all"))
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                self._conds = dlg.get_conditions()
                try:
                    self._cond_mode = dlg.get_mode()
                except Exception:
                    self._cond_mode = "all"
                self._update_cond_summary()
                self._changed()
        except Exception:
            pass

    def _update_cond_summary(self):
        try:
            if not self._conds:
                self.cond_summary.setText("cond: (none)")
                return
            parts = []
            for c in self._conds[:2]:
                if not isinstance(c, dict):
                    continue
                s = str(c.get("signal","") or "")
                op = str(c.get("op",">") or ">")
                v = c.get("value", 0.0)
                try:
                    vv = float(v)
                except Exception:
                    vv = 0.0
                parts.append(f"{s}{op}{vv:g}")
            extra = ""
            if len(self._conds) > 2:
                extra = f" +{len(self._conds)-2}"
            sep = " & " if getattr(self, "_cond_mode", "all") != "any" else " | "
            text = "cond: " + sep.join(parts) + extra
            unknown = []
            try:
                known = set([str(x) for x in (getattr(self, '_signal_names', []) or [])])
                for cc in (self._conds or []):
                    if isinstance(cc, dict):
                        ss = str(cc.get('signal','') or '')
                        if ss and ss not in known:
                            unknown.append(ss)
            except Exception:
                unknown = []
            if unknown:
                text += "  ⚠"
                try:
                    self.cond_summary.setStyleSheet("font-size: 10px; color: #b36b00;")
                    self.cond_summary.setToolTip("Conditions include unknown signal(s): " + ", ".join(sorted(set(unknown))))
                except Exception:
                    pass
            else:
                try:
                    self.cond_summary.setStyleSheet("font-size: 10px; color: #777;")
                    self.cond_summary.setToolTip("Conditions summary. Click '…' to edit conditions list.")
                except Exception:
                    pass
            self.cond_summary.setText(text)
        except Exception:
            try:
                self.cond_summary.setText("cond: ?")
            except Exception:
                pass


    
    def _action_changed(self):
        try:
            self._update_conflict_choices()
        except Exception:
            pass
        self._changed()

    def _update_conflict_choices(self):
        actk = str(self.action.currentData() or "set_var_num")
        cur = str(self.conflict.currentData() or "last")
        self.conflict.blockSignals(True)
        try:
            self.conflict.clear()
            if actk == "set_var_num":
                for k in ("last", "first", "max", "min"):
                    self.conflict.addItem(k, k)
                self.conflict.setEnabled(True)
            elif actk == "set_var_toggle":
                for k in ("last", "first", "or", "and", "xor"):
                    self.conflict.addItem(k, k)
                self.conflict.setEnabled(True)
            elif actk == "set_layer_param":
                for k in ("last", "first"):
                    self.conflict.addItem(k, k)
                self.conflict.setEnabled(True)
            else:
                self.conflict.addItem("—", "na")
                self.conflict.setEnabled(False)

            j = self.conflict.findData(cur)
            if j >= 0:
                self.conflict.setCurrentIndex(j)
            else:
                self.conflict.setCurrentIndex(0)
        finally:
            self.conflict.blockSignals(False)
    def to_dict(self) -> dict:
        trig = str(self.trigger.currentData() or "tick")
        actk = str(self.action.currentData() or "set_var_num")
        sname = str(self.signal.currentText() or "")
        when = {"signal": sname}
        if trig == "threshold":
            when["op"] = str(self.op.currentData() or ">")
            when["value"] = float(self.thr.value())
            when["hyst"] = float(self.hyst.value())

        conditions = []
        try:
            if bool(self.cond_enable.isChecked()):
                # Multi-condition AND list
                if not isinstance(self._conds, list):
                    self._conds = []
                # If enabled but empty, create a default condition placeholder on the main signal (best-effort).
                if not self._conds:
                    ms = str(self.signal.currentText() or "").strip()
                    if ms:
                        self._conds = [{"signal": ms, "op": ">", "value": 0.0}]
                conditions = [c for c in (self._conds or []) if isinstance(c, dict)]
        except Exception:
            conditions = []

# action mapping
        action: dict = {}
        if actk in ("set_var_num", "add_var_num", "pulse_var_num"):
            action["kind"] = ("set_var" if actk == "set_var_num" else ("pulse_var" if actk == "pulse_var_num" else "add_var"))
            action["var_kind"] = "number"
            action["var"] = str(self.var.currentText() or "")
        elif actk == "set_var_toggle":
            action["kind"] = "set_var"
            action["var_kind"] = "toggle"
            action["var"] = str(self.var.currentText() or "")
        elif actk == "flip_toggle":
            action["kind"] = "flip_toggle"
            action["var_kind"] = "toggle"
            action["var"] = str(self.var.currentText() or "")
        elif actk == "set_layer_param":
            action["kind"] = "set_layer_param"
            if getattr(self, "layer_active", None) is not None and self.layer_active.isChecked():
                action["layer"] = -1  # active layer
            else:
                action["layer"] = int(self.layer.value())
            action["param"] = str(self.param.currentData() or self.param.currentText() or "")

        expr = {
            "src": str(self.expr_src.currentData() or "const"),
            "const": float(self.const.value()),
            "signal": str(self.signal.currentText() or ""),
            "scale": float(self.scale.value()),
            "bias": float(self.bias.value()),
        }
        if action.get("var_kind") == "toggle":
            # Toggle uses bool conversion by default.
            expr["as_bool"] = True
        # Phase 6.9: conflict policy
        try:
            if hasattr(self, "conflict") and self.conflict.isEnabled():
                action["conflict"] = str(self.conflict.currentData() or "last")
        except Exception:
            pass

        action["expr"] = expr

        return {
            "id": str(getattr(self, "_id", "") or ""),
            "enabled": bool(self.enabled.isChecked()),
            "name": str(self.name.text() or ""),
            "trigger": trig,
            "when": when,
            "cond_mode": str(getattr(self, "_cond_mode", "all") or "all"),
            "conditions": conditions,
            "action": action,
        }

    def sync(self, rule: dict, signal_names: List[str], num_vars: List[str], toggle_vars: List[str]):
        self._suppress = True
        self._signal_names = list(signal_names or [])
        try:
            r = rule if isinstance(rule, dict) else {}
            self._id = str(r.get("id", "") or "")
            self.enabled.setChecked(bool(r.get("enabled", True)))
            self.name.setText(str(r.get("name", "") or ""))

            trig = str(r.get("trigger", "tick") or "tick")
            k = self.trigger.findData(trig)
            if k >= 0:
                self.trigger.setCurrentIndex(k)

            when = r.get("when") if isinstance(r.get("when"), dict) else {}
            sname = str((when or {}).get("signal", "") or "")
            self.populate_signal_choices(signal_names)
            if sname:
                kk = self.signal.findText(sname)
                if kk >= 0:
                    self.signal.setCurrentIndex(kk)
                else:
                    self.signal.setEditText(sname)

            op = str((when or {}).get("op", ">") or ">")
            j = self.op.findData(op)
            if j >= 0:
                self.op.setCurrentIndex(j)
            self.thr.setValue(float((when or {}).get("value", 0.5) or 0.0))
            self.hyst.setValue(float((when or {}).get("hyst", 0.05) or 0.0))

            # Conditions (AND list)
            try:
                conds = r.get("conditions")
                cond_list = list(conds or []) if isinstance(conds, list) else []
            except Exception:
                cond_list = []
            self._conds = [c for c in cond_list if isinstance(c, dict)]
            try:
                self._cond_mode = str(r.get("cond_mode", getattr(self, "_cond_mode", "all")) or "all")
            except Exception:
                self._cond_mode = "all"
            if self._cond_mode not in ("all","any"):
                self._cond_mode = "all"
            self.cond_enable.setChecked(bool(self._conds))
            self._update_cond_summary()

            kind = str((act or {}).get("kind", "set_var") or "set_var")
            vkind = str((act or {}).get("var_kind", "number") or "number")
            actk = "set_var_num"
            if kind == "add_var" and vkind == "number":
                actk = "add_var_num"
            elif kind == "flip_toggle":
                actk = "flip_toggle"
            elif vkind == "toggle":
                actk = "set_var_toggle"
            elif kind == "set_layer_param":
                actk = "set_layer_param"
            kk = self.action.findData(actk)
            if kk >= 0:
                self.action.setCurrentIndex(kk)

                # Phase 6.9 conflict policy
                try:
                    self._update_conflict_choices()
                    cpol = str((act or {}).get("conflict", "last") or "last")
                    j2 = self.conflict.findData(cpol)
                    if j2 >= 0:
                        self.conflict.setCurrentIndex(j2)
                except Exception:
                    pass

            self.populate_var_choices(num_vars, toggle_vars)
            self.var.setEditText(str((act or {}).get("var", "") or ""))

            try:
                lv = int((act or {}).get("layer", 0) or 0)
            except Exception:
                lv = 0
            if getattr(self, "layer_active", None) is not None and lv == -1:
                try:
                    self.layer_active.setChecked(True)
                except Exception:
                    pass
                try:
                    self.layer.setEnabled(False)
                except Exception:
                    pass
                try:
                    self.layer.setValue(0)
                except Exception:
                    pass
            else:
                try:
                    self.layer_active.setChecked(False)
                except Exception:
                    pass
                try:
                    self.layer.setEnabled(True)
                except Exception:
                    pass
                try:
                    self.layer.setValue(lv)
                except Exception:
                    self.layer.setValue(0)
            _pp = str((act or {}).get("param", "") or "")
            try:
                j = self.param.findData(_pp)
                if j >= 0:
                    self.param.setCurrentIndex(j)
                else:
                    # Unknown param (likely preview-only from older projects). Preserve it as a selectable value.
                    self.param.addItem(_pp, _pp)
                    self.param.setCurrentIndex(self.param.count() - 1)
            except Exception:
                pass

            expr = (act or {}).get("expr") if isinstance((act or {}).get("expr"), dict) else {}
            src = str((expr or {}).get("src", "const") or "const")
            ksrc = self.expr_src.findData(src)
            if ksrc >= 0:
                self.expr_src.setCurrentIndex(ksrc)
            self.const.setValue(float((expr or {}).get("const", 0.0) or 0.0))
            self.scale.setValue(float((expr or {}).get("scale", 1.0) or 1.0))
            self.bias.setValue(float((expr or {}).get("bias", 0.0) or 0.0))
        finally:
            self._suppress = False


class RulesPanel(QtWidgets.QWidget):
    """Rules MVP: Param/Audio -> Param, plus continuous audio modulotors."""

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core
        self._rows = []

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        header = QtWidgets.QLabel("Phase 6 Rules (Signals): Triggers on signals -> set/add Variables or set Layer params")
        header.setWordWrap(True)
        outer.addWidget(header)

        self.v6_last_fired = QtWidgets.QLabel("Last fired: (none)")
        self.v6_last_fired.setWordWrap(True)
        try:
            self.v6_last_fired.setStyleSheet("font-size: 11px; color: #888;")
        except Exception:
            pass
        outer.addWidget(self.v6_last_fired)

        # Phase 6.6: show current rule validation/runtime errors (top-level)
        self.v6_errors = QtWidgets.QLabel("")
        self.v6_errors.setWordWrap(True)
        try:
            self.v6_errors.setStyleSheet("font-size: 10px; color: #b55;")
        except Exception:
            pass
        outer.addWidget(self.v6_errors)

        # Periodically update the last-fired indicator (cheap, UI-only)
        self._v6_fired_timer = QtCore.QTimer(self)
        self._v6_fired_timer.setInterval(200)
        self._v6_fired_timer.timeout.connect(self._update_v6_last_fired)
        self._v6_fired_timer.start()

        # ----------------------------
        # Phase 6.3 Rules (Signals)
        # ----------------------------
        self._v6_rows: List[_RuleV6Row] = []

        self.v6_box = QtWidgets.QWidget()
        self.v6_lay = QtWidgets.QVBoxLayout(self.v6_box)
        self.v6_lay.setContentsMargins(0, 0, 0, 0)
        self.v6_lay.setSpacing(6)
        self.v6_lay.addStretch(1)

        self.v6_scroll = QtWidgets.QScrollArea()
        self.v6_scroll.setWidgetResizable(True)
        self.v6_scroll.setWidget(self.v6_box)
        outer.addWidget(self.v6_scroll, 1)

        v6_btns = QtWidgets.QHBoxLayout()
        self.v6_add_btn = QtWidgets.QPushButton("Add Rule")
        self.v6_add_btn.clicked.connect(self._add_rule_v6)
        v6_btns.addWidget(self.v6_add_btn)

        # Helper: normalize legacy signal names in Rules/Mods to the preferred bus keys.
        self.v6_norm_btn = QtWidgets.QPushButton("Normalize signals")
        self.v6_norm_btn.setToolTip(
            "Convert legacy signal ids (audio_energy, audio_mono0, purpose_f0, etc.) to the normalized bus (audio.energy, audio.mono0, purpose.f0, lfo.sine).\n"
            "Applies to Rules V6 and layer modulotors. Back-compat values are preserved if unknown."
        )
        self.v6_norm_btn.clicked.connect(self._normalize_signals_v6)
        v6_btns.addWidget(self.v6_norm_btn)

        # Helper: suggest and apply replacements for unknown signal ids.
        # This is intentionally interactive and never rewrites anything silently.
        self.v6_fix_unknown_btn = QtWidgets.QPushButton("Fix unknown signals")
        self.v6_fix_unknown_btn.setToolTip(
            "Find signal ids referenced by Rules V6 and Modulotors that are not present in the current signal bus,\n"
            "suggest likely replacements (closest normalized match), and apply selected fixes.\n"
            "No silent rewrites: you must choose each replacement explicitly."
        )
        self.v6_fix_unknown_btn.clicked.connect(self._fix_unknown_signals_v6)
        v6_btns.addWidget(self.v6_fix_unknown_btn)
        self.v6_note = QtWidgets.QLabel("Note: Layer-param actions mutate project params; keep rule counts small for now.")
        try:
            self.v6_note.setStyleSheet("font-style: italic;")
        except Exception:
            pass
        v6_btns.addWidget(self.v6_note)
        v6_btns.addStretch(1)
        outer.addLayout(v6_btns)

        outer.addWidget(_hline())

        legacy = QtWidgets.QLabel("Legacy Rules (pre-Phase6): kept for compatibility")
        legacy.setWordWrap(True)
        outer.addWidget(legacy)

        self.rows_box = QtWidgets.QWidget()
        self.rows_lay = QtWidgets.QVBoxLayout(self.rows_box)
        self.rows_lay.setContentsMargins(0, 0, 0, 0)
        self.rows_lay.setSpacing(6)
        self.rows_lay.addStretch(1)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.rows_box)
        outer.addWidget(self.scroll, 1)

        btns = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Add Rule")
        self.add_btn.clicked.connect(self._add_rule)
        btns.addWidget(self.add_btn)
        btns.addStretch(1)
        outer.addLayout(btns)

        # ----------------------------
        # Continuous modulotion (Audio -> Param)
        # ----------------------------
        # () Modulotors are now surfaced again, but constrained to the
        # exportable surface matrix. Export gating remains fail-closed when the
        # selected target lacks modulotion runtime.
        self._mods_enabled = True

        mods_hdr = QtWidgets.QLabel("Modulotors (continuous): Signal → Target")
        mods_hdr.setWordWrap(True)
        outer.addWidget(mods_hdr)

        # Target capability warning (preview may work, export may block)
        self.mods_warn = QtWidgets.QLabel("")
        self.mods_warn.setWordWrap(True)
        try:
            self.mods_warn.setStyleSheet("font-size: 10px; color: #b55;")
        except Exception:
            pass
        outer.addWidget(self.mods_warn)

        self.mod_box = QtWidgets.QWidget()
        self.mod_rows_lay = QtWidgets.QVBoxLayout(self.mod_box)
        self.mod_rows_lay.setContentsMargins(0, 0, 0, 0)
        self.mod_rows_lay.setSpacing(6)
        self.mod_rows_lay.addStretch(1)

        self.mod_scroll = QtWidgets.QScrollArea()
        self.mod_scroll.setWidgetResizable(True)
        self.mod_scroll.setWidget(self.mod_box)
        outer.addWidget(self.mod_scroll, 1)

        mod_btns = QtWidgets.QHBoxLayout()
        self.mod_add_btn = QtWidgets.QPushButton("Add Mod")
        self.mod_add_btn.clicked.connect(self._add_mod)
        mod_btns.addWidget(self.mod_add_btn)
        mod_btns.addStretch(1)
        outer.addLayout(mod_btns)

        self._mod_rows = []

        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass

    # ----------------------------
    # Phase 6.5: debug + status
    # ----------------------------
    def _update_v6_last_fired(self):
        """Update the Phase 6 'Last fired' label and per-row debug info."""
        # Top-level errors (validation/runtime)
        try:
            errs = getattr(self.app_core, "_rules_v6_last_errors", [])
            if not isinstance(errs, list):
                errs = []
            msg = "\n".join([str(e) for e in errs[:5] if str(e).strip()])
            if len(errs) > 5:
                msg = (msg + "\n…") if msg else "…"
            if not msg:
                msg = ""
            if hasattr(self, "v6_errors"):
                self.v6_errors.setText(msg)
        except Exception:
            pass
        try:
            fn = getattr(self.app_core, "get_rules_v6_last_fired_summary", None)
            if callable(fn):
                s = str(fn() or "")
            else:
                ids = getattr(self.app_core, "_rules_v6_last_fired_ids", []) or []
                s = "Last fired: " + (", ".join([str(x) for x in ids]) if ids else "(none)")
            if not s.lower().startswith("last fired"):
                s = "Last fired: " + s
            try:
                self.v6_last_fired.setText(s)
            except Exception:
                pass
        except Exception:
            pass

        # Per-rule debug status
        try:
            per = getattr(self.app_core, "_rules_v6_per_rule", None)
            if not isinstance(per, dict):
                per = {}
            nowt = float(getattr(self.app_core, "_rules_v6_last_eval_t", 0.0) or 0.0)
        except Exception:
            per = {}
            nowt = 0.0

        try:
            for row in list(getattr(self, "_v6_rows", []) or []):
                rid = str(getattr(row, "_id", "") or "")
                if not rid or not hasattr(row, "debug"):
                    continue
                d = per.get(rid) if isinstance(per.get(rid), dict) else {}
                st = d.get("state", None)
                st_s = "state=?" if st is None else ("state=ON" if bool(st) else "state=OFF")
                try:
                    cond_ok = d.get("cond_ok", True)
                    cond_s = "cond=OK" if bool(cond_ok) else "cond=NO"
                except Exception:
                    cond_s = "cond=?"
                lf = d.get("last_fire_t", None)
                if isinstance(lf, (int, float)) and nowt > 0.0:
                    age = max(0.0, float(nowt) - float(lf))
                    fire_s = f"fired {age:.2f}s ago"
                elif isinstance(lf, (int, float)):
                    fire_s = "fired"
                else:
                    fire_s = "not fired"
                err = d.get("last_error", None)
                if isinstance(err, str) and err.strip():
                    # keep it short
                    e = err.strip()
                    if len(e) > 80:
                        e = e[:77] + "..."
                    txt = f"{st_s} | {cond_s} | {fire_s} | ERR: {e}"
                else:
                    txt = f"{st_s} | {cond_s} | {fire_s}"
                try:
                    row.debug.setText(txt)
                except Exception:
                    pass
        except Exception:
            pass


    def _project(self):
        try:
            return self.app_core.project or {}
        except Exception:
            return {}

    def _set_project(self, p2: dict):
        try:
            self.app_core.project = p2
            try:
                self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass
        except Exception:
            pass

    # ----------------------------
    # Modulotors (continuous)
    # ----------------------------
    def _gather_mods(self):
        """Return a flat list of mod dicts, each with a 'layer' field."""
        p = self._project()
        layers = list(p.get("layers") or [])
        out = []
        for li, L in enumerate(layers):
            mods = []
            try:
                mods = list((L or {}).get("modulotors") or (L or {}).get("mods") or [])
            except Exception:
                mods = []
            for m in (mods or []):
                if isinstance(m, dict):
                    mm = dict(m)
                    mm["layer"] = int(mm.get("layer", li) if "layer" in mm else li)
                    out.append(mm)
        return out

    def _write_mod(self, idx: int, mod: dict):
        mods = self._gather_mods()
        if idx < 0 or idx >= len(mods):
            return
        mods[idx] = dict(mod)
        self._set_mods(mods)

    def _remove_mod(self, idx: int):
        mods = self._gather_mods()
        if idx < 0 or idx >= len(mods):
            return
        mods.pop(idx)

        # Re-write back per-layer
        p = self._project()
        layers = list(p.get("layers") or [])
        per = {i: [] for i in range(len(layers))}
        for m in mods:
            try:
                li = int(m.get("layer", 0) or 0)
            except Exception:
                li = 0
            li = max(0, min(li, len(layers) - 1)) if layers else 0
            mm = dict(m)
            mm.pop("layer", None)
            per.setdefault(li, []).append(mm)

        for li in range(len(layers)):
            L = dict(layers[li] or {})
            L["modulotors"] = per.get(li, [])
            layers[li] = L

        p2 = dict(p)
        p2["layers"] = layers
        self._set_project(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass


    def _set_mods(self, mods):
        """Write a flat mods list back into project layers[].modulotors."""
        p = self._project()
        layers = list(p.get("layers") or [])
        # bucket by layer index
        per = {i: [] for i in range(len(layers))}
        for m in (mods or []):
            try:
                li = int(m.get("layer", 0) or 0)
            except Exception:
                li = 0
            li = max(0, min(li, len(layers) - 1)) if layers else 0
            mm = dict(m)
            mm.pop("layer", None)
            per.setdefault(li, []).append(mm)

        for li in range(len(layers)):
            L = dict(layers[li] or {})
            L["modulotors"] = per.get(li, [])
            layers[li] = L

        p2 = dict(p)
        p2["layers"] = layers
        self._set_project(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass

    def _add_mod(self):
        mods = self._gather_mods()
        mods.append({
            "enabled": True,
            "layer": 0,
            "target": "brightness",
            "source": "audio_energy",
            "mode": "mul",
            "amount": 0.5,
            "smooth": 0.0,
        })
        self._set_mods(mods)

    def _sync_mods_from_project(self):
        mods = self._gather_mods()

        if len(getattr(self, "_mod_rows", [])) == len(mods):
            for i, m in enumerate(mods):
                try:
                    self._mod_rows[i].sync(m if isinstance(m, dict) else {})
                except Exception:
                    pass
            return

        for w in list(getattr(self, "_mod_rows", [])):
            try:
                w.setParent(None)
            except Exception:
                pass
        self._mod_rows = []

        while self.mod_rows_lay.count():
            item = self.mod_rows_lay.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                try:
                    w.setParent(None)
                except Exception:
                    pass

        for i, m in enumerate(mods):
            row = _ModRow(self.app_core, i, self._write_mod, self._remove_mod)
            row.sync(m if isinstance(m, dict) else {})
            self.mod_rows_lay.addWidget(row)
            self._mod_rows.append(row)
        self.mod_rows_lay.addStretch(1)

    # ----------------------------
    # Phase 6.3 Rules (Signals)
    # ----------------------------
    def _rules_v6(self) -> list:
        p = self._project()
        rules = p.get("rules_v6")
        return list(rules or []) if isinstance(rules, list) else []

    def _write_rule_v6(self, idx: int, rule: dict):
        # Popups guard
        try:
            if QtWidgets.QApplication.activePopupWidget() is not None:
                return
        except Exception:
            pass
        rules = self._rules_v6()
        if idx < 0 or idx >= len(rules):
            return
        rules[idx] = dict(rule)
        p2 = dict(self._project())
        p2["rules_v6"] = rules
        self._set_project(p2)

    def _remove_rule_v6(self, idx: int):
        rules = self._rules_v6()
        if idx < 0 or idx >= len(rules):
            return
        rules.pop(idx)
        p2 = dict(self._project())
        p2["rules_v6"] = rules
        self._set_project(p2)
        try:
            self.refresh()
        except Exception:
            pass

    def _add_rule_v6(self):
        import uuid as _uuid

        rules = self._rules_v6()
        rid = _uuid.uuid4().hex
        rules.append({
            "id": rid,
            "enabled": True,
            "name": "",
            "trigger": "threshold",
            "when": {"signal": "audio.energy", "op": ">", "value": 0.5, "hyst": 0.05},
            "action": {
                "kind": "set_var",
                "var_kind": "number",
                "var": "",  # choose a variable name
                "expr": {"src": "signal", "signal": "audio.energy", "const": 0.0, "scale": 1.0, "bias": 0.0},
            },
        })
        p2 = dict(self._project())
        p2["rules_v6"] = rules
        self._set_project(p2)
        try:
            self.refresh()
        except Exception:
            pass

    def _normalize_signals_v6(self):
        """Normalize legacy signal ids across Rules V6 + layer modulotors.

        This is a UI convenience that keeps projects aligned with the preferred
        normalized signal bus (audio.*, vars.*, purpose.*, lfo.*), while preserving
        any unknown/third-party keys (fail-closed on export anyway).
        """

        def norm_one(sig: str) -> str:
            s = (sig or "").strip()
            if not s:
                return s

            # Already normalized.
            if s.startswith("audio.") or s.startswith("vars.") or s.startswith("purpose.") or s.startswith("lfo.") or s.startswith("time.") or s.startswith("engine."):
                return s

            # purpose / lfo legacy
            if s.startswith("purpose_"):
                return "purpose." + s.split("purpose_", 1)[1].replace("_", "")
            if s == "lfo_sine":
                return "lfo.sine"

            # audio legacy styles
            if s.startswith("audio_"):
                core = s.split("audio_", 1)[1]
                if core == "energy":
                    return "audio.energy"
                if core.startswith("mono") and core[4:].isdigit():
                    return f"audio.mono{core[4:]}"
                if core.startswith("left_") and core[5:].isdigit():
                    return f"audio.L{core[5:]}"
                if core.startswith("right_") and core[6:].isdigit():
                    return f"audio.R{core[6:]}"
                # already like mono0 / L0 / R0
                if core.startswith("mono") and core[4:].isdigit():
                    return f"audio.mono{core[4:]}"
                if core.startswith("l") and core[1:].isdigit():
                    return f"audio.L{core[1:]}"
                if core.startswith("r") and core[1:].isdigit():
                    return f"audio.R{core[1:]}"

            # UI label legacy (Energy/Mono0/L0/R0)
            if s.lower() == "energy":
                return "audio.energy"
            if s.lower().startswith("mono") and s[4:].isdigit():
                return f"audio.mono{s[4:]}"
            if (s.startswith("L") or s.startswith("l")) and s[1:].isdigit():
                return f"audio.L{s[1:]}"
            if (s.startswith("R") or s.startswith("r")) and s[1:].isdigit():
                return f"audio.R{s[1:]}"

            return s

        p = dict(self._project())
        changed = 0

        # Rules V6
        rv6 = p.get("rules_v6")
        if isinstance(rv6, list):
            rv6_2 = []
            for r in rv6:
                if not isinstance(r, dict):
                    rv6_2.append(r)
                    continue
                r2 = dict(r)
                # when.signal
                when = r2.get("when")
                if isinstance(when, dict) and "signal" in when:
                    ns = norm_one(str(when.get("signal") or ""))
                    if ns != when.get("signal"):
                        w2 = dict(when)
                        w2["signal"] = ns
                        r2["when"] = w2
                        changed += 1
                # action.expr.signal
                act = r2.get("action")
                if isinstance(act, dict):
                    expr = act.get("expr")
                    if isinstance(expr, dict) and expr.get("src") == "signal" and "signal" in expr:
                        ns = norm_one(str(expr.get("signal") or ""))
                        if ns != expr.get("signal"):
                            e2 = dict(expr)
                            e2["signal"] = ns
                            a2 = dict(act)
                            a2["expr"] = e2
                            r2["action"] = a2
                            changed += 1

                # conditions[].signal
                conds = r2.get("conditions")
                if isinstance(conds, list):
                    conds2 = []
                    for c in conds:
                        if not isinstance(c, dict):
                            conds2.append(c)
                            continue
                        c2 = dict(c)
                        if "signal" in c2:
                            ns = norm_one(str(c2.get("signal") or ""))
                            if ns != c2.get("signal"):
                                c2["signal"] = ns
                                changed += 1
                        conds2.append(c2)
                    r2["conditions"] = conds2

                rv6_2.append(r2)
            p["rules_v6"] = rv6_2

        # Layer modulotors
        layers = p.get("layers")
        if isinstance(layers, list):
            layers2 = []
            for ld in layers:
                if not isinstance(ld, dict):
                    layers2.append(ld)
                    continue
                ld2 = dict(ld)
                params = ld2.get("params")
                if isinstance(params, dict):
                    mods = params.get("_mods")
                    if isinstance(mods, list):
                        mods2 = []
                        for m in mods:
                            if not isinstance(m, dict):
                                mods2.append(m)
                                continue
                            m2 = dict(m)
                            if "signal" in m2:
                                ns = norm_one(str(m2.get("signal") or ""))
                                if ns != m2.get("signal"):
                                    m2["signal"] = ns
                                    changed += 1
                            if "source" in m2:
                                ns = norm_one(str(m2.get("source") or ""))
                                if ns != m2.get("source"):
                                    m2["source"] = ns
                                    changed += 1
                            mods2.append(m2)
                        p2 = dict(params)
                        p2["_mods"] = mods2
                        ld2["params"] = p2
                layers2.append(ld2)
            p["layers"] = layers2

        if changed:
            self._set_project(p)
            try:
                self.refresh()
            except Exception:
                pass
            try:
                QtWidgets.QMessageBox.information(self, "Normalize signals", f"Normalized {changed} signal reference(s).")
            except Exception:
                pass
        else:
            try:
                QtWidgets.QMessageBox.information(self, "Normalize signals", "No legacy signal ids found.")
            except Exception:
                pass

    def _fix_unknown_signals_v6(self):
        """Interactive helper: suggest replacements for unknown signal ids.

        Scans Rules V6 (when/expr/conditions) and layer modulotors (_mods) to find
        signal ids that are not present in the current signal bus.

        Presents a small chooser dialog with suggested replacements (closest match)
        and applies only the selected replacements.
        """

        import difflib

        proj = dict(self._project())

        # Known signals: current bus snapshot + exportable surface list + vars.*
        known = []
        try:
            snap = {}
            if hasattr(self.app_core, "get_signal_snapshot"):
                snap = self.app_core.get_signal_snapshot() or {}
            if isinstance(snap, dict):
                known.extend([str(k) for k in snap.keys()])
        except Exception:
            pass

        try:
            from export.exportable_surface import MODULATION_SOURCES_EXPORTABLE
            known.extend([str(k) for k in (MODULATION_SOURCES_EXPORTABLE or [])])
        except Exception:
            pass

        vars_ = proj.get("variables") if isinstance(proj, dict) else None
        if isinstance(vars_, dict):
            for nm in (vars_.get("number") or {}).keys():
                known.append(f"vars.number.{nm}")
            for nm in (vars_.get("toggle") or {}).keys():
                known.append(f"vars.toggle.{nm}")

        # De-dup + stable sort
        known = sorted(set([k.strip() for k in known if str(k).strip()]))

        def norm_pref(sig: str) -> str:
            # Use the same normalizer as the "Normalize signals" button for suggestion.
            s = str(sig or "").strip()
            if not s:
                return s
            if s.startswith("audio.") or s.startswith("vars.") or s.startswith("purpose.") or s.startswith("lfo.") or s.startswith("time.") or s.startswith("engine."):
                return s
            if s.startswith("audio_"):
                core = s.split("audio_", 1)[1]
                if core == "energy":
                    return "audio.energy"
                if core.startswith("mono") and core[4:].isdigit():
                    return f"audio.mono{core[4:]}"
                if core.startswith("left_") and core[5:].isdigit():
                    return f"audio.L{core[5:]}"
                if core.startswith("right_") and core[6:].isdigit():
                    return f"audio.R{core[6:]}"
            if s.startswith("purpose_"):
                return "purpose." + s.split("purpose_", 1)[1].replace("_", "")
            if s == "lfo_sine":
                return "lfo.sine"
            if s.lower() == "energy":
                return "audio.energy"
            if s.lower().startswith("mono") and s[4:].isdigit():
                return f"audio.mono{s[4:]}"
            if (s.startswith("L") or s.startswith("l")) and s[1:].isdigit():
                return f"audio.L{s[1:]}"
            if (s.startswith("R") or s.startswith("r")) and s[1:].isdigit():
                return f"audio.R{s[1:]}"
            return s

        # Collect references and their paths
        refs = []  # list of (path_tuple, original_value)

        def add_ref(path, val):
            s = str(val or "").strip()
            if s:
                refs.append((tuple(path), s))

        # Rules V6
        rv6 = proj.get("rules_v6") if isinstance(proj, dict) else None
        if isinstance(rv6, list):
            for ri, r in enumerate(rv6):
                if not isinstance(r, dict):
                    continue
                when = r.get("when")
                if isinstance(when, dict) and when.get("src") == "signal":
                    add_ref(["rules_v6", ri, "when", "signal"], when.get("signal"))
                act = r.get("action")
                if isinstance(act, dict):
                    expr = act.get("expr")
                    if isinstance(expr, dict) and expr.get("src") == "signal":
                        add_ref(["rules_v6", ri, "action", "expr", "signal"], expr.get("signal"))
                conds = r.get("conditions")
                if isinstance(conds, list):
                    for ci, c in enumerate(conds):
                        if isinstance(c, dict) and "signal" in c:
                            add_ref(["rules_v6", ri, "conditions", ci, "signal"], c.get("signal"))

        # Modulotors
        layers = proj.get("layers") if isinstance(proj, dict) else None
        if isinstance(layers, list):
            for li, ld in enumerate(layers):
                if not isinstance(ld, dict):
                    continue
                params = ld.get("params")
                if not isinstance(params, dict):
                    continue
                mods = params.get("_mods")
                if isinstance(mods, list):
                    for mi, m in enumerate(mods):
                        if not isinstance(m, dict):
                            continue
                        if "signal" in m:
                            add_ref(["layers", li, "params", "_mods", mi, "signal"], m.get("signal"))
                        if "source" in m:
                            add_ref(["layers", li, "params", "_mods", mi, "source"], m.get("source"))

        unknown_vals = []
        for _, s in refs:
            if s in known:
                continue
            ns = norm_pref(s)
            if ns in known:
                continue
            unknown_vals.append(s)
        unknown_vals = sorted(set(unknown_vals))

        if not unknown_vals:
            try:
                QtWidgets.QMessageBox.information(self, "Fix unknown signals", "No unknown signals detected. ✅")
            except Exception:
                pass
            return

        # Build suggestions per unknown
        suggestions = {}
        for u in unknown_vals:
            opts = []
            nu = norm_pref(u)
            if nu and nu in known:
                opts.append(nu)
            # closest matches
            try:
                opts.extend(difflib.get_close_matches(u, known, n=5, cutoff=0.5))
            except Exception:
                pass
            # ensure stable + no duplicates
            opts2 = []
            for o in opts:
                if o and o not in opts2:
                    opts2.append(o)
            suggestions[u] = opts2

        # Dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Fix unknown signals")
        lay = QtWidgets.QVBoxLayout(dlg)

        info = QtWidgets.QLabel(
            "Select replacements for unknown signal ids. Nothing will change unless you click Apply."
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        table = QtWidgets.QTableWidget(len(unknown_vals), 2)
        table.setHorizontalHeaderLabels(["Unknown", "Replace with"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        try:
            table.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass

        combos = {}
        for row, u in enumerate(unknown_vals):
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(u))
            cb = QtWidgets.QComboBox()
            cb.addItem("(keep as-is)", "")
            for opt in suggestions.get(u, []):
                cb.addItem(opt, opt)
            combos[u] = cb
            table.setCellWidget(row, 1, cb)

        lay.addWidget(table)

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel")
        apply = QtWidgets.QPushButton("Apply")
        btns.addWidget(cancel)
        btns.addWidget(apply)
        lay.addLayout(btns)

        cancel.clicked.connect(dlg.reject)

        def get_by_path(d, path):
            cur = d
            for p in path[:-1]:
                cur = cur[p]
            return cur, path[-1]

        def on_apply():
            rep_map = {}
            for u in unknown_vals:
                v = combos[u].currentData() if combos[u] is not None else ""
                v = str(v or "").strip()
                if v:
                    rep_map[u] = v

            if not rep_map:
                dlg.reject()
                return

            p2 = dict(proj)
            changed = 0
            # Apply replacements to all matching paths.
            for path, val in refs:
                if val not in rep_map:
                    continue
                try:
                    root, leaf = get_by_path(p2, path)
                    if isinstance(root, (dict, list)):
                        root[leaf] = rep_map[val]
                        changed += 1
                except Exception:
                    continue

            if changed:
                self._set_project(p2)
                try:
                    self.refresh()
                except Exception:
                    pass
                try:
                    QtWidgets.QMessageBox.information(self, "Fix unknown signals", f"Applied {changed} replacement(s).")
                except Exception:
                    pass
            dlg.accept()

        apply.clicked.connect(on_apply)

        dlg.exec_()

    def _signal_names_for_ui(self) -> list:
        """Return the list of signals offered in Rules V6 UI.

        The Rules V6 editor should prefer the normalized signal bus (audio.*, vars.*,
        purpose.*, lfo.*). Legacy/unknown values are still preserved because the
        ComboBox remains editable and `sync()` keeps any existing value even if it is
        not present in this list.
        """

        # Start from the exportable surface (single source of truth).
        base: list[str] = []
        try:
            from export.exportable_surface import MODULATION_SOURCES_EXPORTABLE
            base = list(MODULATION_SOURCES_EXPORTABLE or [])
        except Exception:
            base = []

        # Always include a minimal time/engine set for advanced rules.
        for k in ("time.t", "time.dt", "engine.frame"):
            if k not in base:
                base.append(k)

        # Preview-only real-time clock signals (published by PreviewEngine).
        # These are not user-defined project variables, but they are useful for
        # Mario-clock-style rules like "on minute change".
        for ck in (
            "vars.number.clock.hour",
            "vars.number.clock.minute",
            "vars.number.clock.second",
            "vars.number.clock.minute_changed",
            "vars.number.clock.second_changed",
        ):
            if ck not in base:
                base.append(ck)

        # Include project variables as signals.
        try:
            nums, toggles = self._variable_names_for_ui()
            for n in nums:
                base.append(f"vars.number.{n}")
            for t in toggles:
                base.append(f"vars.toggle.{t}")
        except Exception:
            pass

        # Deterministic ordering for UI.
        try:
            return sorted([str(x) for x in base if str(x).strip()])
        except Exception:
            return base

    def _variable_names_for_ui(self) -> tuple[list, list]:
        p = self._project()
        v = p.get("variables") or {}
        nums = []
        tgls = []
        try:
            if isinstance(v, dict):
                n = v.get("number")
                t = v.get("toggle")
                if isinstance(n, dict):
                    nums = sorted([str(k) for k in n.keys()])
                if isinstance(t, dict):
                    tgls = sorted([str(k) for k in t.keys()])
        except Exception:
            pass
        return nums, tgls

    def _rules(self):
        p = self._project()
        rules = p.get("rules")
        return list(rules or []) if isinstance(rules, list) else []

    def _write_rule(self, idx: int, rule: dict):
        # If a popup is open (e.g., a QComboBox dropdown), do not sync.
        try:
            if QtWidgets.QApplication.activePopupWidget() is not None:
                return
        except Exception:
            pass

        rules = self._rules()
        if idx < 0 or idx >= len(rules):
            return
        rules[idx] = dict(rule)
        p2 = dict(self._project())
        p2["rules"] = rules
        self._set_project(p2)

    def _remove_rule(self, idx: int):
        rules = self._rules()
        if idx < 0 or idx >= len(rules):
            return
        rules.pop(idx)
        p2 = dict(self._project())
        p2["rules"] = rules
        self._set_project(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass

    def _add_rule(self):
        rules = self._rules()
        rules.append({
            "enabled": True,
            "src_kind": "param",
            "src_layer": 0,
            "src_param": "brightness",
            "src_audio": "energy",
            "cond": "gt",
            "a": 0.5,
            "b": 1.0,
            "dst_layer": 0,
            "dst_param": "brightness",
            "action": "set",
            "value": 1.0,
        })
        p2 = dict(self._project())
        p2["rules"] = rules
        self._set_project(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass

    def sync_from_project(self):
        """Sync the rules UI from the project.

        IMPORTANT: Do NOT destroy/recreate the row widgets on every tick.
        Rebuilding the widgets while a QComboBox popup is open will instantly
        close the popup and make the UI feel 'unusable'. We only rebuild when
        the rule count changes; otherwise we update in-place.
        """

        rules = self._rules()

        # If the rule count matches, update existing rows in-place.
        if len(self._rows) == len(rules):
            for i, r in enumerate(rules):
                try:
                    self._rows[i].sync(r if isinstance(r, dict) else {})
                except Exception:
                    pass
            # Keep modulotors in sync too (disabled in beta)
            if getattr(self, '_mods_enabled', False):
                if getattr(self, '_mods_enabled', False):
                    try:
                        self._sync_mods_from_project()
                    except Exception:
                        pass
            return

        # Otherwise, rebuild the rows (count changed).
        for w in list(self._rows):
            try:
                w.setParent(None)
            except Exception:
                pass
        self._rows = []

        # Clear layout completely.
        while self.rows_lay.count():
            item = self.rows_lay.takeAt(0)
            if item is None:
                break

        for i, r in enumerate(rules):
            row = _RuleRow(self.app_core, i, self._write_rule, self._remove_rule)
            row.sync(r if isinstance(r, dict) else {})
            self.rows_lay.addWidget(row)
            self._rows.append(row)
        self.rows_lay.addStretch(1)

        try:
            self._sync_mods_from_project()
        except Exception:
            pass

    def _sync_v6_from_project(self):
        rules = self._rules_v6()
        sig_names = self._signal_names_for_ui()
        num_vars, tog_vars = self._variable_names_for_ui()

        # Update in-place when count matches
        if len(getattr(self, '_v6_rows', [])) == len(rules):
            for i, r in enumerate(rules):
                try:
                    self._v6_rows[i].sync(r if isinstance(r, dict) else {}, sig_names, num_vars, tog_vars)
                except Exception:
                    pass
            return

        # Rebuild
        for w in list(getattr(self, '_v6_rows', [])):
            try:
                w.setParent(None)
            except Exception:
                pass
        self._v6_rows = []

        while self.v6_lay.count():
            item = self.v6_lay.takeAt(0)
            if item is None:
                break

        for i, r in enumerate(rules):
            row = _RuleV6Row(self.app_core, i, self._write_rule_v6, self._remove_rule_v6)
            try:
                row.sync(r if isinstance(r, dict) else {}, sig_names, num_vars, tog_vars)
            except Exception:
                pass
            self.v6_lay.addWidget(row)
            self._v6_rows.append(row)
        self.v6_lay.addStretch(1)

    def refresh(self):
        """Compatibility refresh hook (called from main window sync loop)."""
        # v6 rules
        try:
            self._sync_v6_from_project()
        except Exception:
            pass
        # legacy rules
        try:
            self.sync_from_project()
        except Exception:
            pass

        # Modulotors (if surfaced)
        try:
            if bool(getattr(self, "_mods_enabled", False)):
                self._sync_mods_from_project()
        except Exception:
            pass

        # Capability warning: preview may work, export may block
        try:
            warn = ""
            caps = getattr(self.app_core, "export_target_capabilities", None)
            if caps is not None:
                ok = bool(getattr(caps, "supports_modulotion_runtime", False))
                if not ok:
                    warn = "Selected export target does not support modulotion runtime; export will be blocked."
            if hasattr(self, "mods_warn"):
                self.mods_warn.setText(str(warn))
        except Exception:
            pass

class ExportPanel(QtWidgets.QWidget):
    """Export Targets MVP: choose a target pack and emit an Arduino sketch with gating/report."""

    def __init__(self, app_core):
        super().__init__()
        # ( operators export note)
        try:
            self._ops_note = QtWidgets.QLabel("Note: Operators/PostFX export depends on target runtime capabilities. FastLED targets support Operators (Gain/Gamma/Posterize) and PostFX; other targets may block.")
            try:
                self._ops_note.setWordWrap(True)
            except Exception:
                pass
            try:
                self._ops_note.setStyleSheet("font-style: italic;")
            except Exception:
                pass
        except Exception:
            self._ops_note = None
        self.app_core = app_core

        # ( selftest button fallback)
        try:
            btn_selftest = QtWidgets.QPushButton("Run selftests")
            def _run_selftests():
                try:
                    import subprocess, sys, os
                    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    subprocess.run([sys.executable, "-m", "selftest.run_all"], cwd=root_dir, check=False)
                except Exception as e:
                    try:
                        QtWidgets.QMessageBox.warning(self, "Selftests", str(e))
                    except Exception:
                        pass
            btn_selftest.clicked.connect(_run_selftests)
            try:
                self.layout().addWidget(btn_selftest)
            except Exception:
                pass
        except Exception:
            pass

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        # Target pack dropdown
        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        form.addRow("Target", self.target_combo)

        # Output mode (future: platformio); for now Arduino sketch
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["arduino"])
        form.addRow("Output", self.mode_combo)

        # Hardware defaults (stored in project['ui'])
        self.data_pin = QtWidgets.QLineEdit()
        self.data_pin.setPlaceholderText("e.g. 6 or A0")
        form.addRow("Data pin", self.data_pin)

        self.led_type = QtWidgets.QLineEdit()
        self.led_type.setPlaceholderText("e.g. WS2812B")
        form.addRow("LED type", self.led_type)

        self.color_order = QtWidgets.QLineEdit()
        self.color_order.setPlaceholderText("e.g. GRB")
        form.addRow("Color order", self.color_order)

        self.brightness = QtWidgets.QSpinBox()
        self.brightness.setRange(0, 255)
        form.addRow("Brightness", self.brightness)

        # Audio pins (MSGEQ7 / Spectrum Shield)
        aud_box = QtWidgets.QGroupBox("Audio (MSGEQ7 / Spectrum Shield)")
        aud_form = QtWidgets.QFormLayout(aud_box)
        aud_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.msgeq7_reset = QtWidgets.QLineEdit(); self.msgeq7_reset.setPlaceholderText("e.g. 5")
        self.msgeq7_strobe = QtWidgets.QLineEdit(); self.msgeq7_strobe.setPlaceholderText("e.g. 4")
        self.msgeq7_left = QtWidgets.QLineEdit(); self.msgeq7_left.setPlaceholderText("e.g. A0")
        self.msgeq7_right = QtWidgets.QLineEdit(); self.msgeq7_right.setPlaceholderText("e.g. A1")

        aud_form.addRow("Reset pin", self.msgeq7_reset)
        aud_form.addRow("Strobe pin", self.msgeq7_strobe)
        aud_form.addRow("Left ADC", self.msgeq7_left)
        aud_form.addRow("Right ADC", self.msgeq7_right)

        outer.addLayout(form)

        # Project export status (informational; does not affect preview)
        self.project_status = QtWidgets.QLabel("Project export status: …")
        self.project_status.setWordWrap(True)
        try:
            self.project_status.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
            self.project_status.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        except Exception:
            pass
        outer.addWidget(self.project_status)

        # Unknown signals diagnostic (authoring-time visibility)
        self.unknown_signals = QtWidgets.QLabel("Unknown signals referenced: …")
        self.unknown_signals.setWordWrap(True)
        try:
            self.unknown_signals.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
            self.unknown_signals.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        except Exception:
            pass
        outer.addWidget(self.unknown_signals)

        # Convenience: allow fixing unknown signals directly from Export.
        # This forwards to the Rules panel helper when available.
        try:
            fix_row = QtWidgets.QHBoxLayout()
            fix_row.setContentsMargins(0, 0, 0, 0)
            fix_row.setSpacing(6)
            self.btn_fix_unknown_signals = QtWidgets.QPushButton("Fix unknown signals")
            self.btn_fix_unknown_signals.setToolTip(
                "Open the interactive fixer for unknown signal ids referenced by Rules V6 and Modulotors.\n"
                "No silent rewrites: you must choose each replacement explicitly."
            )

            def _do_fix():
                fn = getattr(self.app_core, "_ui_fix_unknown_signals", None)
                if callable(fn):
                    fn()
                else:
                    try:
                        QtWidgets.QMessageBox.information(
                            self,
                            "Fix unknown signals",
                            "Fixer not available. Open the Rules tab and use 'Fix unknown signals'.",
                        )
                    except Exception:
                        pass

            self.btn_fix_unknown_signals.clicked.connect(_do_fix)
            fix_row.addWidget(self.btn_fix_unknown_signals)
            fix_row.addStretch(1)
            outer.addLayout(fix_row)
        except Exception:
            self.btn_fix_unknown_signals = None


        # Exportable surface matrix (single source of truth)
        try:
            from export.exportable_surface import surface_matrix
            sm = surface_matrix()
            self.surface_box = QtWidgets.QGroupBox("Exportable surface (v1)")
            vb = QtWidgets.QVBoxLayout(self.surface_box)
            txt = QtWidgets.QPlainTextEdit()
            txt.setReadOnly(True)
            # Compact, deterministic formatting
            lines = []
            for k in sorted(sm.keys()):
                vals = ", ".join(sm[k])
                lines.append(f"{k}: {vals}")
            txt.setPlainText("\n".join(lines))
            vb.addWidget(txt)
            outer.addWidget(self.surface_box)
        except Exception:
            self.surface_box = None

        # () Z/M/G quick actions (UI-only; exporter remains frozen)
        try:
            act_row = QtWidgets.QHBoxLayout()
            act_row.setContentsMargins(0, 0, 0, 0)
            act_row.setSpacing(6)
            self.btn_open_zmg = QtWidgets.QPushButton("Open Targets Diagnostics")
            self.btn_open_zmg.setToolTip("Jump to Targets → Diagnostics")
            act_row.addWidget(self.btn_open_zmg)
            self.btn_repair_zmg = QtWidgets.QPushButton("Repair Targets (safe)")
            self.btn_repair_zmg.setToolTip("Run safe Z/M/G normalization/repairs and re-validate")
            self.btn_repair_zmg.setEnabled(False)
            act_row.addWidget(self.btn_repair_zmg)
            act_row.addStretch(1)
            outer.addLayout(act_row)
        except Exception:
            self.btn_open_zmg = None
            self.btn_repair_zmg = None

        # () Keep Export tab status/gate in sync when validation changes elsewhere.
        # We poll app_core.last_validation cheaply and update the status box + export button gating.
        try:
            self._last_validation_sig = None
            self._validation_poll_timer = QtCore.QTimer(self)
            self._validation_poll_timer.setInterval(250)
            self._validation_poll_timer.timeout.connect(self._poll_validation)
            self._validation_poll_timer.start()
        except Exception:
            self._validation_poll_timer = None

        outer.addWidget(aud_box)

        # HUB75 Matrix (export-only) settings (shown when target uses HUB75 backend)
        self.hub75_box = QtWidgets.QGroupBox("HUB75 Matrix (I2S-DMA)")
        self.hub75_box.setToolTip("Settings used by HUB75 export target packs (panel geometry + output tweaks).")
        hub_form = QtWidgets.QFormLayout(self.hub75_box)
        hub_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.hub75_panel_x = QtWidgets.QSpinBox(); self.hub75_panel_x.setRange(1, 1024); self.hub75_panel_x.setValue(64)
        self.hub75_panel_y = QtWidgets.QSpinBox(); self.hub75_panel_y.setRange(1, 1024); self.hub75_panel_y.setValue(32)
        self.hub75_chain   = QtWidgets.QSpinBox(); self.hub75_chain.setRange(1, 64);   self.hub75_chain.setValue(1)

        self.hub75_auto_chain = QtWidgets.QCheckBox("Auto chain (rows×cols)")
        self.hub75_auto_chain.setChecked(True)

        # WiFi + Web Update (optional). Requires an initial USB upload; afterwards you can update from a browser.
        self.hub75_wifi_enable = QtWidgets.QCheckBox("Enable WiFi + Web Update")
        self.hub75_wifi_enable.setChecked(False)

        self.hub75_wifi_ssid = QtWidgets.QLineEdit(); self.hub75_wifi_ssid.setPlaceholderText("WiFi SSID")
        self.hub75_wifi_pass = QtWidgets.QLineEdit(); self.hub75_wifi_pass.setPlaceholderText("WiFi Password")
        try:
            self.hub75_wifi_pass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        except Exception:
            pass
        self.hub75_wifi_host = QtWidgets.QLineEdit(); self.hub75_wifi_host.setPlaceholderText("Hostname (mDNS), e.g. modulo-hub75")

        # AP fallback (optional): if WiFi can't connect, start a setup AP with a small config page.
        self.hub75_wifi_ap_fallback = QtWidgets.QCheckBox("AP fallback setup portal (if WiFi fails)")
        self.hub75_wifi_ap_fallback.setChecked(True)

        self.hub75_wifi_ap_pass = QtWidgets.QLineEdit(); self.hub75_wifi_ap_pass.setPlaceholderText("Setup AP password (optional)")
        try:
            self.hub75_wifi_ap_pass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        except Exception:
            pass

        # NTP time sync (optional): enables real clock time on ESP32 for clock-driven effects.
        self.hub75_wifi_ntp = QtWidgets.QCheckBox("NTP time sync (clock effects)")
        self.hub75_wifi_ntp.setChecked(True)
        self.hub75_wifi_tz = QtWidgets.QLineEdit(); self.hub75_wifi_tz.setPlaceholderText("TZ string (POSIX), e.g. GMT0BST,M3.5.0/1,M10.5.0/2")

        def _hub75_wifi_ui_enable_state():
            try:
                en = bool(self.hub75_wifi_enable.isChecked())
                for w in (self.hub75_wifi_ssid, self.hub75_wifi_pass, self.hub75_wifi_host, self.hub75_wifi_ap_fallback, self.hub75_wifi_ap_pass, self.hub75_wifi_ntp, self.hub75_wifi_tz):
                    try: w.setEnabled(en)
                    except Exception: pass
            except Exception:
                pass

        try:
            self.hub75_wifi_enable.stateChanged.connect(lambda *_: _hub75_wifi_ui_enable_state())
        except Exception:
            pass

        # Panel module preset (sets Panel W/H quickly; does not change grid cols/rows)
        self.hub75_panel_preset = QtWidgets.QComboBox()
        self.hub75_panel_preset.addItem("Custom", None)
        self.hub75_panel_preset.addItem("64x32", (64, 32))
        self.hub75_panel_preset.addItem("64x64", (64, 64))
        self.hub75_panel_preset.addItem("32x16", (32, 16))
        self.hub75_panel_preset.addItem("32x32", (32, 32))

        def _hub75_apply_panel_preset():
            try:
                data = self.hub75_panel_preset.currentData()
                if isinstance(data, (tuple, list)) and len(data) == 2:
                    self.hub75_panel_x.setValue(int(data[0]))
                    self.hub75_panel_y.setValue(int(data[1]))
            except Exception:
                pass

        try:
            self.hub75_panel_preset.currentIndexChanged.connect(lambda *_: _hub75_apply_panel_preset())
        except Exception:
            pass

        # HUB75 mapping presets (rotate/flip/serpentine) for preview+export parity.
        self.hub75_mapping_preset = QtWidgets.QComboBox()
        self.hub75_mapping_preset.addItem("Default (no rotate/flip)", {"rotate": 0, "flip_x": 0, "flip_y": 0, "serpentine": 0})
        self.hub75_mapping_preset.addItem("Rotate 90°", {"rotate": 90, "flip_x": 0, "flip_y": 0, "serpentine": 0})
        self.hub75_mapping_preset.addItem("Rotate 180°", {"rotate": 180, "flip_x": 0, "flip_y": 0, "serpentine": 0})
        self.hub75_mapping_preset.addItem("Rotate 270°", {"rotate": 270, "flip_x": 0, "flip_y": 0, "serpentine": 0})
        self.hub75_mapping_preset.addItem("Flip X", {"rotate": 0, "flip_x": 1, "flip_y": 0, "serpentine": 0})
        self.hub75_mapping_preset.addItem("Flip Y", {"rotate": 0, "flip_x": 0, "flip_y": 1, "serpentine": 0})
        self.hub75_mapping_preset.addItem("Serpentine (snake)", {"rotate": 0, "flip_x": 0, "flip_y": 0, "serpentine": 1})

        def _hub75_apply_mapping_preset():
            try:
                d = self.hub75_mapping_preset.currentData() or {}
                if not isinstance(d, dict):
                    return
                # Apply to project layout (preview + export parity)
                try:
                    proj = getattr(self.app_core, 'project', None) or {}
                except Exception:
                    proj = {}
                if not isinstance(proj, dict):
                    return
                lay = dict(proj.get('layout') or {})
                lay['shape'] = 'cells'
                # Keep matrix dimensions aligned to HUB75 panel/grid if possible
                try:
                    pw = int(self.hub75_panel_x.value()); ph = int(self.hub75_panel_y.value())
                    cols = int(self.hub75_num_cols.value()); rows = int(self.hub75_num_rows.value())
                    lay['matrix_w'] = max(1, pw * cols)
                    lay['matrix_h'] = max(1, ph * rows)
                    lay['mw'] = int(lay['matrix_w']); lay['mh'] = int(lay['matrix_h'])
                except Exception:
                    pass
                lay['rotate'] = int(d.get('rotate') or 0)
                lay['matrix_rotate'] = int(lay['rotate'])
                lay['flip_x'] = bool(int(d.get('flip_x') or 0))
                lay['flip_y'] = bool(int(d.get('flip_y') or 0))
                lay['matrix_flip_x'] = 1 if lay['flip_x'] else 0
                lay['matrix_flip_y'] = 1 if lay['flip_y'] else 0
                lay['serpentine'] = bool(int(d.get('serpentine') or 0))
                lay['matrix_serpentine'] = 1 if lay['serpentine'] else 0
                proj2 = dict(proj)
                proj2['layout'] = lay
                try:
                    self.app_core.project = proj2
                except Exception:
                    pass
                # Also mirror to ui keys for older exporters that consult ui.*
                try:
                    ui = (proj2.get('ui') or {}) if isinstance(proj2.get('ui'), dict) else {}
                    ui['export_hub75_mapping_preset'] = str(self.hub75_mapping_preset.currentText())
                    proj2['ui'] = ui
                    self.app_core.project = proj2
                except Exception:
                    pass
            except Exception:
                pass

        try:
            self.hub75_mapping_preset.currentIndexChanged.connect(lambda *_: _hub75_apply_mapping_preset())
        except Exception:
            pass

        
        # HUB75 grid configuration (for multi-panel setups). Used by GRID target packs.
        self.hub75_num_cols = QtWidgets.QSpinBox(); self.hub75_num_cols.setRange(1, 16); self.hub75_num_cols.setValue(1)
        self.hub75_num_rows = QtWidgets.QSpinBox(); self.hub75_num_rows.setRange(1, 16); self.hub75_num_rows.setValue(1)

        def _hub75_sync_chain():
            try:
                if not self.hub75_auto_chain.isChecked():
                    self.hub75_chain.setEnabled(True)
                    return
                rows = int(self.hub75_num_rows.value())
                cols = int(self.hub75_num_cols.value())
                chain = max(1, rows * cols)
                self.hub75_chain.setValue(chain)
                self.hub75_chain.setEnabled(False)
            except Exception:
                try:
                    self.hub75_chain.setEnabled(True)
                except Exception:
                    pass

        try:
            self.hub75_auto_chain.toggled.connect(lambda *_: _hub75_sync_chain())
            self.hub75_num_rows.valueChanged.connect(lambda *_: _hub75_sync_chain())
            self.hub75_num_cols.valueChanged.connect(lambda *_: _hub75_sync_chain())
        except Exception:
            pass

        # initialize
        _hub75_sync_chain()

        # VirtualMatrixPanel chain type (how the physical panels are chained in a grid)
        self.hub75_vchain_type = QtWidgets.QComboBox()
        self.hub75_vchain_type.addItem("Top-left down (default)", "CHAIN_TOP_LEFT_DOWN")
        self.hub75_vchain_type.addItem("Top-right down", "CHAIN_TOP_RIGHT_DOWN")
        self.hub75_vchain_type.addItem("Bottom-left up", "CHAIN_BOTTOM_LEFT_UP")
        self.hub75_vchain_type.addItem("Bottom-right up", "CHAIN_BOTTOM_RIGHT_UP")

        self.hub75_brightness = QtWidgets.QSpinBox(); self.hub75_brightness.setRange(0, 255); self.hub75_brightness.setValue(96)

        self.hub75_use_gamma = QtWidgets.QCheckBox("Enable")
        self.hub75_gamma = QtWidgets.QLineEdit(); self.hub75_gamma.setPlaceholderText("e.g. 2.2f")

        # Color order swizzle for HUB75 output
        self.hub75_color_order = QtWidgets.QComboBox()
        self.hub75_color_order.addItems(["RGB", "GRB", "BRG", "RBG", "GBR", "BGR"])

        # Debug output mode (0=off, 1=gradient, 2=corner markers)
        self.hub75_debug_mode = QtWidgets.QComboBox()
        self.hub75_debug_mode.addItems(["0 - Off", "1 - Gradient", "2 - Corners"])
        # Preview overlay: draw HUB75/matrix mapping guides on the preview (editor-only)
        self.hub75_preview_overlay = QtWidgets.QCheckBox("Show mapping overlay")
        self.hub75_preview_overlay.setToolTip("Editor-only overlay to verify matrix mapping/orientation. Does not affect export.")


        hub_form.addRow("Panel preset", self.hub75_panel_preset)
        hub_form.addRow("Mapping preset", self.hub75_mapping_preset)
        hub_form.addRow("Panel W", self.hub75_panel_x)
        hub_form.addRow("Panel H", self.hub75_panel_y)
        hub_form.addRow("Chain", self.hub75_chain)
        hub_form.addRow("", self.hub75_auto_chain)
        hub_form.addRow("", self.hub75_wifi_enable)
        hub_form.addRow("WiFi SSID", self.hub75_wifi_ssid)
        hub_form.addRow("WiFi Pass", self.hub75_wifi_pass)
        hub_form.addRow("Hostname", self.hub75_wifi_host)
        hub_form.addRow("", self.hub75_wifi_ap_fallback)
        hub_form.addRow("AP Pass", self.hub75_wifi_ap_pass)
        hub_form.addRow("", self.hub75_wifi_ntp)
        hub_form.addRow("TZ", self.hub75_wifi_tz)
        hub_form.addRow("Grid cols", self.hub75_num_cols)
        hub_form.addRow("Grid rows", self.hub75_num_rows)
        hub_form.addRow("Grid chain type", self.hub75_vchain_type)
        hub_form.addRow("HUB75 Brightness", self.hub75_brightness)

        gamma_row = QtWidgets.QHBoxLayout()
        gamma_row.addWidget(self.hub75_use_gamma)
        gamma_row.addWidget(self.hub75_gamma, 1)
        gamma_wrap = QtWidgets.QWidget(); gamma_wrap.setLayout(gamma_row)
        hub_form.addRow("Gamma", gamma_wrap)

        hub_form.addRow("HUB75 Color order", self.hub75_color_order)
        hub_form.addRow("HUB75 Debug", self.hub75_debug_mode)

        # Hidden by default; shown only when HUB75 target is selected.
        self.hub75_box.setVisible(False)
        outer.addWidget(self.hub75_box)


        btn_row = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("Refresh targets")
        self.export_btn = QtWidgets.QPushButton("Export sketch (.ino)")
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.export_btn)
        outer.addLayout(btn_row)

        self.report = QtWidgets.QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setPlaceholderText("Export report will appear here...")
        outer.addWidget(self.report, 1)

        self.refresh_btn.clicked.connect(self._refresh_targets)
        self.export_btn.clicked.connect(self._do_export)

        # () Hook up Z/M/G navigation action (best-effort)
        try:
            if self.btn_open_zmg is not None:
                def _go_zmg():
                    try:
                        nav = getattr(self.app_core, '_nav_to_panels', None)
                        if callable(nav):
                            nav()
                    except Exception:
                        pass
                self.btn_open_zmg.clicked.connect(_go_zmg)
                try:
                    def _repair_zmg():
                        try:
                            nav = getattr(self.app_core, '_nav_to_panels', None)
                            if callable(nav):
                                nav()
                        except Exception:
                            pass
                        try:
                            zp = getattr(self.app_core, '_zones_panel', None)
                            if zp is not None and hasattr(zp, '_normalize_project'):
                                zp._normalize_project()
                        except Exception:
                            pass


                        # () Ensure validation snapshot is refreshed even if normalize didn't
                        # reassign project for some reason.
                        try:
                            p_now = getattr(self.app_core, 'project', None) or {}
                            if not isinstance(p_now, dict):
                                p_now = {}
                            from app.project_validation import validate_project
                            snap = validate_project(p_now)
                            setattr(self.app_core, 'last_validation', snap)
                        except Exception:
                            pass
# () After repair/normalize, immediately refresh export status UI so
                        # the button gating + integrity line reflect the latest validation snapshot.
                        try:
                            self._update_project_export_status()
                        except Exception:
                            pass
                    if hasattr(self, 'btn_repair_zmg') and self.btn_repair_zmg is not None:
                        self.btn_repair_zmg.clicked.connect(_repair_zmg)
                except Exception:
                    pass
        except Exception:
            pass

        self.target_combo.currentIndexChanged.connect(self._sync_defaults_from_target)

        self._refresh_targets()
        self._sync_fields_from_project()

    def _ui(self) -> dict:
        # UI state lives under project['ui'] (always dict)
        try:
            p = getattr(self.app_core, 'project', None) or {}
        except Exception:
            p = {}
        ui = None
        try:
            ui = p.get('ui')
        except Exception:
            ui = None
        if not isinstance(ui, dict):
            ui = {}
            try:
                p2 = dict(p)
                p2['ui'] = ui
                try:
                    self.app_core.project = p2
                except Exception:
                    pass
            except Exception:
                pass
        return ui

    def _sync_fields_from_project(self):
        ui = self._ui()
        # use strings for pins
        self.data_pin.setText(str(ui.get('export_data_pin') or '').replace('a','A',1) if str(ui.get('export_data_pin') or '').lower().startswith('a') else str(ui.get('export_data_pin') or ''))
        self.led_type.setText(str(ui.get('export_led_type') or ''))
        self.color_order.setText(str(ui.get('export_color_order') or ''))
        try:
            self.brightness.setValue(int(ui.get('export_brightness') or 255))
        except Exception:
            self.brightness.setValue(255)

        self.msgeq7_reset.setText(str(ui.get('export_msgeq7_reset_pin') or ''))
        self.msgeq7_strobe.setText(str(ui.get('export_msgeq7_strobe_pin') or ''))
        self.msgeq7_left.setText(str(ui.get('export_msgeq7_left_pin') or '').replace('a','A',1) if str(ui.get('export_msgeq7_left_pin') or '').lower().startswith('a') else str(ui.get('export_msgeq7_left_pin') or ''))
        self.msgeq7_right.setText(str(ui.get('export_msgeq7_right_pin') or '').replace('a','A',1) if str(ui.get('export_msgeq7_right_pin') or '').lower().startswith('a') else str(ui.get('export_msgeq7_right_pin') or ''))

        # HUB75 fields (if present)
        try:
            if getattr(self, 'hub75_panel_x', None) is not None:
                # Prefer project.export.hub75.*, then UI export_hub75_* keys
                try:
                    proj = getattr(self.app_core, 'project', None) or {}
                except Exception:
                    proj = {}
                exp = ((proj.get('export') or {}).get('hub75') or {}) if isinstance(proj, dict) else {}

                self.hub75_panel_x.setValue(int(exp.get('panel_res_x') or ui.get('export_hub75_panel_res_x') or 64))
                self.hub75_panel_y.setValue(int(exp.get('panel_res_y') or ui.get('export_hub75_panel_res_y') or 32))

                # Sync panel preset selector
                try:
                    saved_preset = exp.get('panel_preset') or ui.get('export_hub75_panel_preset')
                    if isinstance(saved_preset, str) and saved_preset.strip():
                        # Try match by text
                        for i in range(self.hub75_panel_preset.count()):
                            if self.hub75_panel_preset.itemText(i) == saved_preset:
                                self.hub75_panel_preset.setCurrentIndex(i)
                                break
                    else:
                        xy = (int(self.hub75_panel_x.value()), int(self.hub75_panel_y.value()))
                        matched = False
                        for i in range(self.hub75_panel_preset.count()):
                            d = self.hub75_panel_preset.itemData(i)
                            if isinstance(d, (tuple, list)) and tuple(d) == xy:
                                self.hub75_panel_preset.setCurrentIndex(i)
                                matched = True
                                break
                        if not matched:
                            self.hub75_panel_preset.setCurrentIndex(0)
                except Exception:
                    pass
                self.hub75_chain.setValue(int(exp.get('chain') or ui.get('export_hub75_chain') or 1))
                try:
                    self.hub75_auto_chain.setChecked(bool(int(exp.get('auto_chain') or ui.get('export_hub75_auto_chain') or 1)))
                except Exception:
                    pass
                # WiFi + Web Update
                try:
                    self.hub75_wifi_enable.setChecked(bool(int(exp.get('wifi_enable') or ui.get('export_hub75_wifi_enable') or 0)))
                except Exception:
                    pass
                try:
                    self.hub75_wifi_ssid.setText(str(exp.get('wifi_ssid') or ui.get('export_hub75_wifi_ssid') or ''))
                    self.hub75_wifi_pass.setText(str(exp.get('wifi_password') or ui.get('export_hub75_wifi_password') or ''))
                    self.hub75_wifi_host.setText(str(exp.get('wifi_hostname') or ui.get('export_hub75_wifi_hostname') or 'modulo-hub75'))
                    self.hub75_wifi_ap_fallback.setChecked(bool(int(exp.get('wifi_ap_fallback') or ui.get('export_hub75_wifi_ap_fallback') or 1)))
                    self.hub75_wifi_ap_pass.setText(str(exp.get('wifi_ap_password') or ui.get('export_hub75_wifi_ap_password') or ''))
                except Exception:
                    pass
                    self.hub75_wifi_ntp.setChecked(bool(int(exp.get('wifi_ntp') or ui.get('export_hub75_wifi_ntp') or 1)))
                    self.hub75_wifi_tz.setText(str(exp.get('wifi_tz') or ui.get('export_hub75_wifi_tz') or 'GMT0BST,M3.5.0/1,M10.5.0/2'))
                try:
                    _hub75_wifi_ui_enable_state()
                except Exception:
                    pass
                try:
                    _hub75_sync_chain()
                except Exception:
                    pass
                self.hub75_num_cols.setValue(int(exp.get('num_cols') or ui.get('export_hub75_num_cols') or 1))
                self.hub75_num_rows.setValue(int(exp.get('num_rows') or ui.get('export_hub75_num_rows') or 1))
                # Virtual chain type stored as CHAIN_* string (or numeric). Default to CHAIN_TOP_LEFT_DOWN.
                vct = str(exp.get('virtual_chain_type') or ui.get('export_hub75_virtual_chain_type') or "CHAIN_TOP_LEFT_DOWN")
                # Select matching item if present
                found = False
                for _i in range(self.hub75_vchain_type.count()):
                    if str(self.hub75_vchain_type.itemData(_i)) == vct:
                        self.hub75_vchain_type.setCurrentIndex(_i)
                        found = True
                        break
                if not found:
                    # If a numeric was stored, attempt mapping to our list ordering
                    vmap = {"0":"CHAIN_TOP_LEFT_DOWN","1":"CHAIN_TOP_RIGHT_DOWN","2":"CHAIN_BOTTOM_LEFT_UP","3":"CHAIN_BOTTOM_RIGHT_UP"}
                    vct2 = vmap.get(vct.strip(), "CHAIN_TOP_LEFT_DOWN")
                    for _i in range(self.hub75_vchain_type.count()):
                        if str(self.hub75_vchain_type.itemData(_i)) == vct2:
                            self.hub75_vchain_type.setCurrentIndex(_i)
                            break
                self.hub75_brightness.setValue(int(exp.get('brightness') or ui.get('export_hub75_brightness') or 96))
                self.hub75_use_gamma.setChecked(bool(int(exp.get('use_gamma') or ui.get('export_hub75_use_gamma') or 0)))
                self.hub75_gamma.setText(str(exp.get('gamma') or ui.get('export_hub75_gamma') or '2.2f'))
                try:
                    self.hub75_color_order.setCurrentIndex(int(exp.get('color_order') or ui.get('export_hub75_color_order') or 0))
                except Exception:
                    self.hub75_color_order.setCurrentIndex(0)
                try:
                    self.hub75_debug_mode.setCurrentIndex(int(exp.get('debug_mode') or ui.get('export_hub75_debug_mode') or 0))
                except Exception:
                    self.hub75_debug_mode.setCurrentIndex(0)
                # Preview overlay is UI-only
                try:
                    self.hub75_preview_overlay.setChecked(bool(int(ui.get('preview_hub75_overlay') or 0)))
                except Exception:
                    self.hub75_preview_overlay.setChecked(False)

                except Exception:
                    self.hub75_debug_mode.setCurrentIndex(0)
        except Exception:
            pass


    def _write_fields_to_project(self):
        ui = self._ui()
        ui['export_data_pin'] = self.data_pin.text().strip()
        ui['export_led_type'] = self.led_type.text().strip()
        ui['export_color_order'] = self.color_order.text().strip()
        ui['export_brightness'] = int(self.brightness.value())

        ui['export_msgeq7_reset_pin'] = self.msgeq7_reset.text().strip()
        ui['export_msgeq7_strobe_pin'] = self.msgeq7_strobe.text().strip()
        ui['export_msgeq7_left_pin'] = self.msgeq7_left.text().strip()
        ui['export_msgeq7_right_pin'] = self.msgeq7_right.text().strip()

        # HUB75 fields (if present)
        try:
            if getattr(self, 'hub75_panel_x', None) is not None:
                # UI mirror (used for display + backwards compatibility)
                ui['export_hub75_panel_res_x'] = int(self.hub75_panel_x.value())
                ui['export_hub75_panel_preset'] = str(getattr(self, 'hub75_panel_preset', None).currentText()) if getattr(self, 'hub75_panel_preset', None) is not None else 'Custom'
                ui['export_hub75_panel_res_y'] = int(self.hub75_panel_y.value())
                ui['export_hub75_chain'] = int(self.hub75_chain.value())
                ui['export_hub75_auto_chain'] = 1 if self.hub75_auto_chain.isChecked() else 0
                ui['export_hub75_wifi_enable'] = 1 if getattr(self, 'hub75_wifi_enable', None) is not None and self.hub75_wifi_enable.isChecked() else 0
                ui['export_hub75_wifi_ssid'] = self.hub75_wifi_ssid.text().strip() if getattr(self, 'hub75_wifi_ssid', None) is not None else ''
                ui['export_hub75_wifi_password'] = self.hub75_wifi_pass.text() if getattr(self, 'hub75_wifi_pass', None) is not None else ''
                ui['export_hub75_wifi_hostname'] = self.hub75_wifi_host.text().strip() if getattr(self, 'hub75_wifi_host', None) is not None else 'modulo-hub75'
                ui['export_hub75_wifi_ap_fallback'] = 1 if getattr(self, 'hub75_wifi_ap_fallback', None) is not None and self.hub75_wifi_ap_fallback.isChecked() else 0
                ui['export_hub75_wifi_ap_password'] = self.hub75_wifi_ap_pass.text() if getattr(self, 'hub75_wifi_ap_pass', None) is not None else ''
                ui['export_hub75_wifi_ntp'] = 1 if getattr(self, 'hub75_wifi_ntp', None) is not None and self.hub75_wifi_ntp.isChecked() else 0
                ui['export_hub75_wifi_tz'] = self.hub75_wifi_tz.text().strip() if getattr(self, 'hub75_wifi_tz', None) is not None else ''
                ui['export_hub75_num_cols'] = int(self.hub75_num_cols.value())
                ui['export_hub75_num_rows'] = int(self.hub75_num_rows.value())
                ui['export_hub75_virtual_chain_type'] = str(self.hub75_vchain_type.currentData() or 'CHAIN_TOP_LEFT_DOWN')
                ui['export_hub75_mapping_preset'] = str(getattr(self, 'hub75_mapping_preset', None).currentText()) if getattr(self, 'hub75_mapping_preset', None) is not None else 'Default (no rotate/flip)'

                ui['export_hub75_brightness'] = int(self.hub75_brightness.value())
                ui['export_hub75_use_gamma'] = 1 if self.hub75_use_gamma.isChecked() else 0
                ui['export_hub75_gamma'] = self.hub75_gamma.text().strip() or "2.2f"
                ui['export_hub75_color_order'] = int(self.hub75_color_order.currentIndex())
                ui['export_hub75_debug_mode'] = int(self.hub75_debug_mode.currentIndex())
                ui['preview_hub75_overlay'] = 1 if self.hub75_preview_overlay.isChecked() else 0

                # Canonical export config lives under project.export.hub75.*
                try:
                    proj = getattr(self.app_core, 'project', None) or {}
                except Exception:
                    proj = {}
                if not isinstance(proj, dict):
                    proj = {}

                export_root = proj.get('export')
                if not isinstance(export_root, dict):
                    export_root = {}
                hub75 = export_root.get('hub75')
                if not isinstance(hub75, dict):
                    hub75 = {}

                hub75['panel_res_x'] = int(ui['export_hub75_panel_res_x'])
                hub75['panel_res_y'] = int(ui['export_hub75_panel_res_y'])

                hub75['panel_preset'] = str(ui.get('export_hub75_panel_preset') or 'Custom')
                hub75['chain'] = int(ui['export_hub75_chain'])
                hub75['wifi_enable'] = int(ui.get('export_hub75_wifi_enable') or 0)
                hub75['wifi_ssid'] = str(ui.get('export_hub75_wifi_ssid') or '')
                hub75['wifi_password'] = str(ui.get('export_hub75_wifi_password') or '')
                hub75['wifi_hostname'] = str(ui.get('export_hub75_wifi_hostname') or 'modulo-hub75')
                hub75['wifi_ap_fallback'] = int(ui.get('export_hub75_wifi_ap_fallback') or 1)
                hub75['wifi_ap_password'] = str(ui.get('export_hub75_wifi_ap_password') or '')
                hub75['wifi_ntp'] = int(ui.get('export_hub75_wifi_ntp') or 1)
                hub75['wifi_tz'] = str(ui.get('export_hub75_wifi_tz') or 'GMT0BST,M3.5.0/1,M10.5.0/2')
                hub75['num_cols'] = int(ui.get('export_hub75_num_cols') or 1)
                hub75['num_rows'] = int(ui.get('export_hub75_num_rows') or 1)
                hub75['virtual_chain_type'] = str(ui.get('export_hub75_virtual_chain_type') or 'CHAIN_TOP_LEFT_DOWN')

                hub75['brightness'] = int(ui['export_hub75_brightness'])
                hub75['use_gamma'] = int(ui['export_hub75_use_gamma'])
                hub75['gamma'] = str(ui['export_hub75_gamma'])
                hub75['color_order'] = int(ui['export_hub75_color_order'])
                hub75['debug_mode'] = int(ui['export_hub75_debug_mode'])

                export_root['hub75'] = hub75
                proj['export'] = export_root
                try:
                    self.app_core.project = proj
                except Exception:
                    pass
        except Exception:
            pass


    def _poll_validation(self):
        """Cheap poller to keep export status/gate in sync with latest validation snapshot.

        This avoids requiring signals across panels while keeping exporter frozen.
        """
        try:
            snap = getattr(self.app_core, 'last_validation', None)
            if isinstance(snap, dict):
                ok = bool(snap.get('ok', True))
                sig = (ok, len(snap.get('errors') or []), len(snap.get('warnings') or []), snap.get('project_revision'))
            else:
                sig = ('none',)
        except Exception:
            sig = ('err',)

        try:
            if sig == getattr(self, '_last_validation_sig', None):
                return
            self._last_validation_sig = sig
        except Exception:
            pass

        try:
            self._update_project_export_status()
        except Exception:
            pass

    def _refresh_targets(self):
        # Preserve current selection while refreshing list
        current = self.target_combo.currentData() if self.target_combo.count() > 0 else None

        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        try:
            from export.targets.registry import list_targets
            metas = list_targets()
        except Exception as e:
            metas = []
            self.report.setPlainText(f"Failed to list targets: {e}")

        self._targets_meta = metas
        for meta in metas:
            name = meta.get('name') or meta.get('id') or 'unknown'
            tid = meta.get('id') or ''
            lvl = str(meta.get('support_level') or '').strip().lower()
            if lvl == 'experimental':
                name = f"[EXPERIMENTAL] {name}"
            self.target_combo.addItem(name, tid)

        self.target_combo.blockSignals(False)

        ui = self._ui()
        # Prefer: current selection -> ui stored selection -> first item
        preferred = current or str(ui.get('export_target_id') or '').strip()
        if preferred:
            for i in range(self.target_combo.count()):
                if self.target_combo.itemData(i) == preferred:
                    self.target_combo.setCurrentIndex(i)
                    break

        if self.target_combo.count() > 0 and self.target_combo.currentIndex() < 0:
            self.target_combo.setCurrentIndex(0)

        self._sync_defaults_from_target()
        self._update_project_export_status()

    def _update_project_export_status(self):
        """Update the informational export-status badge for the current project.

        UI-only summary. Must stay cheap and must never touch preview state.
        """
        try:
            from export.parity_summary import summarize_layers, format_project_badge
        except Exception:
            return

        try:
            layers = list((self.app_core.project or {}).get('layers') or [])
        except Exception:
            layers = []

        try:
            summary = summarize_layers(layers)
            headline, tail = format_project_badge(summary)
            # () include Z/M/G integrity in the status box and gate the export button.
            zmg_ok = True
            zmg_errs = []
            zmg_warns = []
            try:
                snap = getattr(self.app_core, 'last_validation', None)
                if isinstance(snap, dict):
                    zmg_ok = bool(snap.get('ok', True))
                    zmg_errs = list(snap.get('errors') or [])
                    zmg_warns = list(snap.get('warnings') or [])
            except Exception:
                zmg_ok = True
            zmg_line = "\n\nZ/M/G Integrity: " + ("OK" if zmg_ok else f"FAIL ({len(zmg_errs)} errors, {len(zmg_warns)} warnings)")
            self.project_status.setText(headline + tail + zmg_line)

            # Unknown signals referenced (rules/modulotors) vs current signal bus.
            try:
                proj = self.app_core.project or {}
                snap = {}
                if hasattr(self.app_core, "get_signal_snapshot"):
                    snap = self.app_core.get_signal_snapshot() or {}
                known = set(str(k) for k in (snap.keys() if isinstance(snap, dict) else []))

                # Also include the normalized bus list (single source of truth).
                try:
                    from export.exportable_surface import MODULATION_SOURCES_EXPORTABLE
                    for k in (MODULATION_SOURCES_EXPORTABLE or []):
                        known.add(str(k))
                except Exception:
                    pass

                # Include project variables as signal keys.
                vars_ = proj.get("variables") if isinstance(proj, dict) else None
                if isinstance(vars_, dict):
                    for nm in (vars_.get("number") or {}).keys():
                        known.add(f"vars.number.{nm}")
                    for nm in (vars_.get("toggle") or {}).keys():
                        known.add(f"vars.toggle.{nm}")

                def _norm_sig(s: str) -> str:
                    s = str(s or "").strip()
                    if not s:
                        return s
                    # Common legacy → normalized
                    m = {
                        "audio_energy": "audio.energy",
                        "audio_kick": "audio.kick",
                        "lfo_sine": "lfo.sine",
                        "purpose_f0": "purpose.f0",
                        "purpose_f1": "purpose.f1",
                        "purpose_f2": "purpose.f2",
                        "purpose_f3": "purpose.f3",
                    }
                    if s in m:
                        return m[s]
                    if s.startswith("audio_mono") and s[9:].isdigit():
                        return f"audio.mono{s[9:]}"
                    if s.startswith("audio_left_") and s[10:].isdigit():
                        return f"audio.L{s[10:]}"
                    if s.startswith("audio_right_") and s[11:].isdigit():
                        return f"audio.R{s[11:]}"
                    # UI label forms
                    if s.lower() == "energy":
                        return "audio.energy"
                    if s.lower().startswith("mono") and s[4:].isdigit():
                        return f"audio.mono{s[4:]}"
                    if (s.startswith("L") or s.startswith("l")) and s[1:].isdigit():
                        return f"audio.L{s[1:]}"
                    if (s.startswith("R") or s.startswith("r")) and s[1:].isdigit():
                        return f"audio.R{s[1:]}"
                    return s

                refs = set()

                # Rules V6
                rv6 = proj.get("rules_v6") if isinstance(proj, dict) else None
                if isinstance(rv6, list):
                    for r in rv6:
                        if not isinstance(r, dict):
                            continue
                        w = r.get("when")
                        if isinstance(w, dict) and w.get("src") == "signal":
                            refs.add(str(w.get("signal") or ""))
                        a = r.get("action")
                        if isinstance(a, dict):
                            e = a.get("expr")
                            if isinstance(e, dict) and e.get("src") == "signal":
                                refs.add(str(e.get("signal") or ""))
                        conds = r.get("conditions")
                        if isinstance(conds, list):
                            for c in conds:
                                if isinstance(c, dict) and "signal" in c:
                                    refs.add(str(c.get("signal") or ""))

                # Modulotors
                layers = proj.get("layers") if isinstance(proj, dict) else None
                if isinstance(layers, list):
                    for ld in layers:
                        if not isinstance(ld, dict):
                            continue
                        params = ld.get("params")
                        if not isinstance(params, dict):
                            continue
                        mods = params.get("_mods")
                        if isinstance(mods, list):
                            for md in mods:
                                if not isinstance(md, dict):
                                    continue
                                if "signal" in md:
                                    refs.add(str(md.get("signal") or ""))
                                if "source" in md:
                                    refs.add(str(md.get("source") or ""))

                unknown = []
                for s in sorted(refs):
                    if not s:
                        continue
                    if s in known:
                        continue
                    ns = _norm_sig(s)
                    if ns in known:
                        continue
                    unknown.append(s)

                if hasattr(self, "unknown_signals") and self.unknown_signals is not None:
                    if unknown:
                        # Determine whether unknown signals are blocking vs warning-only based on current target context.
                        sev = "info"
                        try:
                            tid = ""
                            try:
                                tid = str(self.target_combo.currentData() or "").strip()
                            except Exception:
                                tid = ""
                            if tid:
                                try:
                                    from export.targets.registry import load_target
                                    from export.parity_summary import compute_export_parity_summary
                                    tmeta = load_target(tid)
                                    ps = compute_export_parity_summary(proj, tmeta) or {}
                                    errs = "\n".join(ps.get("errors") or [])
                                    warns = "\n".join(ps.get("warnings") or [])
                                    if "[E_UNKNOWN_SIGNALS_REQUIRED]" in errs:
                                        sev = "BLOCKING"
                                    elif "[W_UNKNOWN_SIGNALS_IGNORED]" in warns:
                                        sev = "warning"
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        self.unknown_signals.setText(f"Unknown signals ({sev}): " + ", ".join(unknown))
                        try:
                            if getattr(self, "btn_fix_unknown_signals", None) is not None:
                                self.btn_fix_unknown_signals.setEnabled(True)
                        except Exception:
                            pass
                    else:
                        self.unknown_signals.setText("Unknown signals: none")
                        try:
                            if getattr(self, "btn_fix_unknown_signals", None) is not None:
                                self.btn_fix_unknown_signals.setEnabled(False)
                        except Exception:
                            pass
            except Exception:
                pass

            try:
                if hasattr(self, 'export_btn') and self.export_btn is not None:
                    self.export_btn.setEnabled(bool(zmg_ok))
                    if not zmg_ok:
                        self.export_btn.setToolTip("Export disabled: Zones/Masks/Groups validation failed. Fix Diagnostics first.")
                    else:
                        self.export_btn.setToolTip("")
                    try:
                        if hasattr(self, 'btn_repair_zmg') and self.btn_repair_zmg is not None:
                            self.btn_repair_zmg.setEnabled(not bool(zmg_ok))
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            return


    def _sync_defaults_from_target(self):
        """Apply target defaults when the selected target changes.

        Truth contract:
        - Defaults come from target pack capabilities.defaults (not ad-hoc meta keys).
        - Switching targets updates both UI fields and project['export'] so parity/gating uses the same truth.
        """
        try:
            tid = self.target_combo.currentData() or ''
            if not tid:
                return

            from export.targets.registry import load_target, resolve_target_meta, resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw
            target = load_target(tid)
            meta = (target.meta or {})

            project = self.app_core.project or {}
            ui = project.setdefault('ui', {})

            prev_tid = str(ui.get('export_target_id') or '').strip()
            if prev_tid == tid:
                return

            caps = meta.get('capabilities') or {}
            defs = (caps.get('defaults') or {})

            def _norm_pin(v):
                s = str(v or '').strip()
                if s.lower().startswith('a') and len(s) >= 2:
                    return 'A' + s[1:]
                return s

            # Base defaults (capabilities.defaults preferred)
            d_data = _norm_pin(defs.get('data_pin') or defs.get('led_pin') or meta.get('default_data_pin') or '6')
            d_led  = str(defs.get('led_type') or meta.get('default_led_type') or 'WS2812B')
            d_ord  = str(defs.get('color_order') or meta.get('default_color_order') or 'GRB')
            d_bri  = int(defs.get('brightness') or meta.get('default_brightness') or 255)

            # Audio defaults
            ab = str(defs.get('audio_backend') or '').strip().lower()
            use_msgeq7 = ('msgeq7' in ab) or ('msgeq7' in tid.lower())

            if use_msgeq7:
                d_r  = _norm_pin(defs.get('msgeq7_reset_pin') or meta.get('default_msgeq7_reset_pin') or '5')
                d_s  = _norm_pin(defs.get('msgeq7_strobe_pin') or meta.get('default_msgeq7_strobe_pin') or '4')
                d_l  = _norm_pin(defs.get('msgeq7_left_pin') or meta.get('default_msgeq7_left_pin') or 'A0')
                d_rr = _norm_pin(defs.get('msgeq7_right_pin') or meta.get('default_msgeq7_right_pin') or 'A1')
            else:
                d_r = d_s = d_l = d_rr = ''

            # Persist UI defaults for new target
            ui['export_target_id'] = tid
            ui['export_data_pin'] = d_data
            ui['export_led_type'] = d_led
            ui['export_color_order'] = d_ord
            ui['export_brightness'] = d_bri
            ui['export_msgeq7_reset_pin'] = d_r
            ui['export_msgeq7_strobe_pin'] = d_s
            ui['export_msgeq7_left_pin'] = d_l
            ui['export_msgeq7_right_pin'] = d_rr

            # HUB75 defaults (only for HUB75 targets)
            try:
                led_backend = str(defs.get('led_backend') or meta.get('default_led_backend') or '').strip().lower()
                is_hub75 = ('hub75' in led_backend) or ('hub75' in tid.lower())
                if is_hub75:
                    ui['export_hub75_panel_res_x'] = int(meta.get('default_hub75_panel_res_x', 64))
                    ui['export_hub75_panel_res_y'] = int(meta.get('default_hub75_panel_res_y', 32))
                    ui['export_hub75_chain'] = int(meta.get('default_hub75_chain', 1))
                    ui['export_hub75_brightness'] = int(meta.get('default_hub75_brightness', d_bri))
                    ui['export_hub75_use_gamma'] = int(meta.get('default_hub75_use_gamma', 0))
                    ui['export_hub75_gamma'] = str(meta.get('default_hub75_gamma', '2.2f'))
                    try:
                        ui['export_hub75_color_order'] = int(meta.get('default_hub75_color_order', 0))
                    except Exception:
                        ui['export_hub75_color_order'] = 0
                    ui['export_hub75_debug_mode'] = int(meta.get('default_hub75_debug_mode', 0))
            except Exception:
                pass


            # Also normalize project export config using the same resolvers used by emit/parity.
            try:
                export_cfg = (project.get('export') or {})
                export_cfg['target_id'] = tid
                tmeta = resolve_target_meta(tid)
                sel = resolve_requested_backends(project, tmeta)
                export_cfg['led_backend'] = sel.get('led_backend')
                export_cfg['audio_backend'] = sel.get('audio_backend')
                export_cfg['hw'] = resolve_requested_hw(project, tmeta)
                export_cfg['audio_hw'] = resolve_requested_audio_hw(project, tmeta)
                project['export'] = export_cfg
            except Exception:
                pass

            self.app_core.project = project
            
            # Show HUB75 panel controls only when selected target uses HUB75 backend.
            try:
                led_backend = str(defs.get('led_backend') or meta.get('default_led_backend') or '').strip().lower()
                is_hub75 = ('hub75' in led_backend) or ('hub75' in tid.lower())
                if getattr(self, 'hub75_box', None) is not None:
                    self.hub75_box.setVisible(bool(is_hub75))
                # HUB75 targets do not use strip pin/type/order fields; keep them disabled to reduce confusion.
                try:
                    self.data_pin.setEnabled(not bool(is_hub75))
                    self.led_type.setEnabled(not bool(is_hub75))
                    self.color_order.setEnabled(not bool(is_hub75))
                except Exception:
                    pass
            except Exception:
                pass

            self._sync_fields_from_project()
        except Exception:
            return

    def _do_export(self):
        # Refresh the informational badge (cheap)
        try:
            self._update_project_export_status()
        except Exception:
            pass
        # : export gate — block export when validation errors exist
        try:
            from app.project_validation import validate_project
            p = getattr(self.app_core, 'project', None) or {}
            if not isinstance(p, dict):
                p = {}
            snap = validate_project(p)
            if isinstance(snap, dict) and (not snap.get('ok', True)):
                errs = snap.get('errors') or []
                msg = 'Project validation failed. Fix these before export:\n\n' + '\n'.join(f'- {e}' for e in errs[:30])
                if len(errs) > 30:
                    msg += f"\n... and {len(errs)-30} more"
                QtWidgets.QMessageBox.critical(self, 'Export blocked', msg)
                return
        except Exception:
            pass

        # Persist UI settings
        self._write_fields_to_project()
        tid = self.target_combo.currentData() or ''
        if not tid:
            self.report.setPlainText("No target selected.")
            return
        self._ui()['export_target_id'] = tid

        # Step 2: parity summary in the report pane (single source of truth)
        try:
            from export.parity_summary import build_parity_summary, summarize_layers, format_export_report_line
            project = self.app_core.project or {}
            ps = build_parity_summary(project, target_id=tid)
            summary = summarize_layers(ps)
            self.report.setPlainText(format_export_report_line(summary))
        except Exception:
            pass
        # Step 2b: hard export gate using parity summary (reasons are authoritative)
        try:
            from export.parity_summary import build_parity_summary, format_export_block_message
            project = self.app_core.project or {}
            ps = build_parity_summary(project, target_id=tid)
            msg = format_export_block_message(ps, target_id=tid)
            if msg:
                # Block and show reasons (single source of truth)
                QtWidgets.QMessageBox.critical(self, 'Export blocked', msg)
                try:
                    self.report.setPlainText(msg)
                except Exception:
                    pass
                return
        except Exception:
            pass


        # Step 3: If this project was loaded from a showcase that is export-blocked, stop early with reasons.
        try:
            ui = dict((self.app_core.project or {}).get('ui') or {})
            if bool(ui.get('showcase_export_blocked')):
                reasons = ui.get('showcase_export_blocked_reasons') or []
                title = str(ui.get('showcase_title') or 'Showcase')
                msg = f"Export blocked for showcase: {title}\n\n" + "\n".join([str(r) for r in reasons])
                QtWidgets.QMessageBox.critical(self, 'Export blocked', msg)
                self.report.setPlainText(msg)
                return
        except Exception:
            pass

        # Pick output path
        default_name = "modulo_export.ino"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Arduino Sketch", default_name, "Arduino Sketch (*.ino)")
        if not path:
            return

        try:
            from pathlib import Path
            from export.emit import emit_project
            out_path = Path(path)
            # Step 2: parity gate (single source)
            from export.parity_summary import summarize_layers, format_export_block_message
            project = self.app_core.project or {}
            layers = project.get('layers', []) or []
            summary = summarize_layers(layers)

            msg = format_export_block_message(summary)
            if msg:
                QtWidgets.QMessageBox.critical(self, 'Export blocked', msg)
                self.report.setPlainText(msg)
                return

            
            # Signal key validation preflight (no closed doors: rules/modulation must reference known keys)
            try:
                sig_ok, sig_msg = _export_preflight_validate_signals(self)
                if not sig_ok:
                    QtWidgets.QMessageBox.critical(self, 'Export blocked', sig_msg)
                    self.report.setPlainText(sig_msg)
                    return
            except Exception:
                pass
            # Modulation validation preflight
            try:
                for _ld in (self.app_core.project or {}).get('layers', []) or []:
                    if not isinstance(_ld, dict):
                        continue
                    ok, msg = validate_layer_mods(_ld)
                    if not ok:
                        QtWidgets.QMessageBox.critical(self, 'Export blocked', 'Modulation invalid: ' + msg)
                        self.report.setPlainText('Modulation invalid: ' + msg)
                        return
            except Exception:
                pass



            written, report = emit_project(project=self.app_core.project or {}, out_path=out_path, target_id=tid, output_mode=str(self.mode_combo.currentText()))
            self.report.setPlainText((report or "") + f"\nWritten: {written}\n")
        except Exception as e:
            self.report.setPlainText(str(e))



# () Export preflight: validate any discovered signal keys against registry.
# Conservative: if keys can't be discovered, this is a no-op.

def _export_preflight_validate_signals(self):
    """Export preflight: validate discovered signal keys against the canonical registry."""
    try:
        from app.signal_validation import validate_signal_keys
    except Exception:
        return (True, "")

    keys = []
    proj = None
    try:
        proj = getattr(self.app_core, "project", None)
        if proj is None:
            proj = getattr(self.app_core, "get_project", lambda: None)()
    except Exception:
        proj = None

    project = proj or {}

    # Collect keys from rules_v6
    try:
        rules = (project.get("rules_v6") or [])
        for r in rules:
            if not isinstance(r, dict):
                continue
            k = r.get("signal_key") or r.get("signal") or ""
            if isinstance(k, str) and k.strip():
                keys.append(k.strip())
    except Exception:
        pass

    # Collect keys from modulotors
    try:
        for ld in (project.get("layers") or []):
            if not isinstance(ld, dict):
                continue
            mods = ld.get("modulotors") or (ld.get("params") or {}).get("_mods") or []
            if not isinstance(mods, list):
                continue
            for mm in mods:
                if not isinstance(mm, dict) or not bool(mm.get("enabled", False)):
                    continue
                src = str(mm.get("source") or "").strip()
                if src:
                    keys.append(_mod_source_to_signal_key(src))
    except Exception:
        pass

    # Filter empty and validate
    keys = [k for k in keys if isinstance(k, str) and k]
    res = validate_signal_keys(keys)
    if not res.ok:
        return (False, res.message)
    return (True, "OK")


def _mod_source_to_signal_key(src: str) -> str:
    s = (src or "").strip().lower()
    if s in ("energy", "audio_energy"):
        return "audio.energy"
    if s in ("mono", "audio_mono"):
        return "audio.mono"
    # mono0..6
    if s.startswith("mono") and len(s) == 5 and s[-1].isdigit():
        return f"audio.band.{int(s[-1])}"
    if s.startswith("l") and len(s) == 2 and s[-1].isdigit():
        return f"audio.L.{int(s[-1])}"
    if s.startswith("r") and len(s) == 2 and s[-1].isdigit():
        return f"audio.R.{int(s[-1])}"
    if s.startswith("audio."):
        return s
    return s

class MasksManagerPanel(QtWidgets.QGroupBox):
    """Minimal Masks Panel (Phase A1)

    - List masks
    - Show type + size
    - Rename key
    - Duplicate
    - Delete

    Safe: operates on project dict copy-on-write.
    """

    def __init__(self, app_core):
        super().__init__("Masks")
        self.app_core = app_core
        self.setCheckable(True)
        self.setChecked(False)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Mask', 'Type'])
        # Selecting a mask row sets Target Mask
        def _mm_row_selected():
            try:
                items = self.table.selectedItems() if hasattr(self, 'table') else []
                if not items:
                    return
                name = str(items[0].text())
                if name:
                    self.app_core.target_mask = name
            except Exception:
                pass
        try:
            self.table.itemSelectionChanged.connect(_mm_row_selected)
        except Exception:
            pass

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        def _row_sel_changed():
            try:
                rows = self.table.selectionModel().selectedRows()
                if not rows:
                    return
                r = rows[0].row()
                it = self.table.item(r, 0)
                key = str(it.text()) if it else None
                if not key:
                    return
                try:
                    self.app_core.target_mask = key
                except Exception:
                    pass
            except Exception:
                return
        
        self.table.itemSelectionChanged.connect(_row_sel_changed)
        outer.addWidget(self.table)

        btnrow = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_rename = QtWidgets.QPushButton("Rename")
        self.btn_dup = QtWidgets.QPushButton("Duplicate")
        self.btn_del = QtWidgets.QPushButton("Delete")
        self.btn_compose = QtWidgets.QPushButton("Compose")
        self.btn_invert = QtWidgets.QPushButton("Invert")
        self.btn_from_sel = QtWidgets.QPushButton('New from selection')
        self.btn_from_sel.setToolTip('Create a new mask from the current selection and set it as Target Mask')
        self.btn_update_sel = QtWidgets.QPushButton('Update from selection')
        self.btn_update_sel.setToolTip('Replace the selected mask (indices-op only) with the current selection')
        self.btn_to_zone = QtWidgets.QPushButton('Mask → Zone')
        self.btn_to_zone.setToolTip('Create a zone from the selected mask (indices-only supported)')
        self.btn_select = QtWidgets.QPushButton('Mask → Selection')
        self.btn_select.setToolTip('Replace current selection with the selected mask indices (indices-op only)')

        self.btn_to_group = QtWidgets.QPushButton('Mask → Group')
        self.btn_to_group.setToolTip('Create a group from the selected mask (indices-only supported)')



        self.btn_validate = QtWidgets.QPushButton('Validate')
        self.btn_normalize = QtWidgets.QPushButton('Normalize')

        self.btn_info = QtWidgets.QPushButton('Info')


        btnrow.addWidget(self.btn_refresh)
        btnrow.addWidget(self.btn_rename)
        btnrow.addWidget(self.btn_dup)
        btnrow.addWidget(self.btn_del)
        btnrow.addWidget(self.btn_from_sel)
        btnrow.addWidget(self.btn_update_sel)
        btnrow.addWidget(self.btn_select)
        btnrow.addWidget(self.btn_to_zone)
        btnrow.addWidget(self.btn_to_group)
        btnrow.addWidget(self.btn_compose)
        btnrow.addWidget(self.btn_validate)
        btnrow.addWidget(self.btn_normalize)
        btnrow.addWidget(self.btn_info)
        btnrow.addWidget(self.btn_invert)
        btnrow.addStretch(1)
        outer.addLayout(btnrow)

        try: self.btn_refresh.clicked.connect(getattr(self, 'refresh', lambda: None))
        except Exception: pass
        try: self.btn_rename.clicked.connect(self._rename)
        except Exception: pass
        try: self.btn_dup.clicked.connect(self._duplicate)
        except Exception: pass
        try: self.btn_del.clicked.connect(self._delete)
        except Exception: pass
        def _mm_new_from_selection():
            try:
                sel = None
                for attr in ('selection', 'selected_indices', 'selected', 'sel'):
                    try:
                        sel = getattr(self.app_core, attr, None)
                    except Exception:
                        sel = None
                    if sel is not None:
                        break
                idxs = []
                if isinstance(sel, set):
                    for x in sel:
                        try: idxs.append(int(x))
                        except Exception: pass
                elif isinstance(sel, list):
                    for x in sel:
                        try: idxs.append(int(x))
                        except Exception: pass
                idxs = sorted(set(i for i in idxs if isinstance(i, int) and i >= 0))
                if not idxs:
                    QtWidgets.QMessageBox.information(self, 'No selection', 'Select some pixels first (click/drag), then try again.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                if not isinstance(p, dict):
                    return
                masks = p.get('masks') or {}
                if not isinstance(masks, dict): masks = {}
                base = 'SelectionMask'
                name = base
                n = 1
                while name in masks:
                    n += 1
                    name = f'{base}{n}'
                masks2 = dict(masks)
                masks2[name] = {'op': 'indices', 'indices': idxs}
                p2 = dict(p); p2['masks'] = masks2
                ui = p2.get('ui') or {}
                if not isinstance(ui, dict): ui = {}
                ui2 = dict(ui); ui2['target_mask'] = name
                p2['ui'] = ui2
                try:
                    self.app_core.project = p2
                except Exception:
                    pass
                try:
                    self.refresh()
                except Exception:
                    pass
            except Exception:
                return
        try: self.btn_from_sel.clicked.connect(_mm_new_from_selection)
        except Exception: pass

        def _mm_update_from_selection():
            try:
                name = None
                try: name = getattr(self, 'selected_name', None)
                except Exception: name = None
                if not name:
                    QtWidgets.QMessageBox.information(self, 'No mask selected', 'Select a mask row first.')
                    return
                sel = None
                for attr in ('selection', 'selected_indices', 'selected', 'sel'):
                    try: sel = getattr(self.app_core, attr, None)
                    except Exception: sel = None
                    if sel is not None: break
                idxs = []
                if isinstance(sel, (set, list)):
                    for x in sel:
                        try: idxs.append(int(x))
                        except Exception: pass
                idxs = sorted(set(i for i in idxs if isinstance(i, int) and i >= 0))
                if not idxs:
                    QtWidgets.QMessageBox.information(self, 'No selection', 'Select some pixels first (click/drag), then try again.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                if not isinstance(p, dict): return
                masks = p.get('masks') or {}
                if not isinstance(masks, dict):
                    QtWidgets.QMessageBox.warning(self, 'Bad project', 'Project masks are not a dict.')
                    return
                node = masks.get(name)
                if not isinstance(node, dict) or str(node.get('op','')) != 'indices':
                    QtWidgets.QMessageBox.information(self, 'Not an indices mask', 'Only masks with op = indices can be updated from selection.')
                    return
                node2 = dict(node); node2['indices'] = idxs
                masks2 = dict(masks); masks2[name] = node2
                p2 = dict(p); p2['masks'] = masks2
                try: self.app_core.project = p2
                except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.btn_update_sel.clicked.connect(_mm_update_from_selection)
        except Exception: pass

        def _mm_mask_to_zone():
            try:
                name = None
                try: name = getattr(self, 'selected_name', None)
                except Exception: name = None
                if not name:
                    QtWidgets.QMessageBox.information(self, 'No mask selected', 'Select a mask row first.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                if not isinstance(p, dict): return
                masks = p.get('masks') or {}
                node = masks.get(name) if isinstance(masks, dict) else None
                if not isinstance(node, dict) or str(node.get('op','')) != 'indices':
                    QtWidgets.QMessageBox.information(self, 'Not supported', 'Only masks with op = indices can be converted to a Zone right now.')
                    return
                idxs = node.get('indices') or []
                if not isinstance(idxs, list) or not idxs:
                    QtWidgets.QMessageBox.information(self, 'Empty mask', 'Selected mask has no indices.')
                    return
                try: idxs2 = sorted(set(int(x) for x in idxs))
                except Exception: idxs2 = [int(x) for x in idxs if isinstance(x, int)]
                zones = p.get('zones') or {}
                if not isinstance(zones, dict): zones = {}
                base = f'FromMask_{name}'
                zname = base
                k = 1
                while zname in zones:
                    k += 1
                    zname = f'{base}_{k}'
                # store indices list (most general)
                znode = {'indices': idxs2, 'start': int(idxs2[0]), 'end': int(idxs2[-1])}
                zones2 = dict(zones); zones2[zname] = znode
                ui = p.get('ui') or {}
                if not isinstance(ui, dict): ui = {}
                ui2 = dict(ui); ui2['target_mask'] = f"zone:{zname}"
                p2 = dict(p); p2['zones'] = zones2; p2['ui'] = ui2
                try: self.app_core.project = p2
                except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.btn_to_zone.clicked.connect(_mm_mask_to_zone)
        except Exception: pass

        def _mm_mask_to_group():
            try:
                name = None
                try: name = getattr(self, 'selected_name', None)
                except Exception: name = None
                if not name:
                    QtWidgets.QMessageBox.information(self, 'No mask selected', 'Select a mask row first.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                if not isinstance(p, dict): return
                masks = p.get('masks') or {}
                node = masks.get(name) if isinstance(masks, dict) else None
                if not isinstance(node, dict) or str(node.get('op','')) != 'indices':
                    QtWidgets.QMessageBox.information(self, 'Not supported', 'Only masks with op = indices can be converted to a Group right now.')
                    return
                idxs = node.get('indices') or []
                if not isinstance(idxs, list) or not idxs:
                    QtWidgets.QMessageBox.information(self, 'Empty mask', 'Selected mask has no indices.')
                    return
                try: idxs2 = sorted(set(int(x) for x in idxs))
                except Exception: idxs2 = [int(x) for x in idxs if isinstance(x, int)]
                groups = p.get('groups') or {}
                if not isinstance(groups, dict): groups = {}
                base = f'FromMask_{name}'
                gname = base
                k = 1
                while gname in groups:
                    k += 1
                    gname = f'{base}_{k}'
                groups2 = dict(groups); groups2[gname] = {'indices': idxs2}
                ui = p.get('ui') or {}
                if not isinstance(ui, dict): ui = {}
                ui2 = dict(ui); ui2['target_mask'] = f"group:{gname}"
                p2 = dict(p); p2['groups'] = groups2; p2['ui'] = ui2
                try: self.app_core.project = p2
                except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.btn_to_group.clicked.connect(_mm_mask_to_group)
        except Exception: pass



        def _mm_invert():
            key = self._selected_key()
            if not key:
                return
            name, ok = QtWidgets.QInputDialog.getText(self, 'Invert Mask', 'New mask name:', text=f'{key}_inv')
            if not ok:
                return
            name = str(name or '').strip()
            if not name:
                return
            p = getattr(self.app_core, 'project', None) or {}
            masks = p.get('masks') or {}
            if not isinstance(masks, dict):
                masks = {}
            if name in masks:
                QtWidgets.QMessageBox.warning(self, 'Exists', f"Mask '{name}' already exists.")
                return
            masks2 = dict(masks)
            masks2[name] = {'op': 'invert', 'a': key}
            p2 = dict(p)
            p2['masks'] = masks2
            try:
                self.app_core.project = p2
            except Exception:
                return
            try:
                self.app_core.target_mask = name
            except Exception:
                pass
            try:
                self.refresh()
            except Exception:
                pass
        
        def _mm_compose():
            masks = self._get_masks()
            keys = sorted(str(k) for k in masks.keys()) if isinstance(masks, dict) else []
            if not keys:
                return
            a0 = self._selected_key() or keys[0]
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle('Compose Mask')
            lay = QtWidgets.QVBoxLayout(dlg)
            form = QtWidgets.QFormLayout()
            op = QtWidgets.QComboBox()
            op.addItems(['union','intersect','subtract','xor'])
            cb_a = QtWidgets.QComboBox(); cb_a.addItems(keys); cb_a.setCurrentText(str(a0))
            cb_b = QtWidgets.QComboBox(); cb_b.addItems(keys)
            for k in keys:
                if k != str(a0):
                    cb_b.setCurrentText(k)
                    break
            name = QtWidgets.QLineEdit(f"{cb_a.currentText()}_{op.currentText()}_{cb_b.currentText()}")
            def _sync_name():
                try:
                    name.setText(f"{cb_a.currentText()}_{op.currentText()}_{cb_b.currentText()}")
                except Exception:
                    pass
            op.currentIndexChanged.connect(_sync_name)
            cb_a.currentIndexChanged.connect(_sync_name)
            cb_b.currentIndexChanged.connect(_sync_name)
            form.addRow('Operation', op)
            form.addRow('A', cb_a)
            form.addRow('B', cb_b)
            form.addRow('New name', name)
            inv = QtWidgets.QCheckBox('Invert result')
            form.addRow('Invert', inv)
            lay.addLayout(form)
            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            lay.addWidget(btns)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            new_name = str(name.text() or '').strip()
            if not new_name:
                return
            p = getattr(self.app_core, 'project', None) or {}
            masks2 = p.get('masks') or {}
            if not isinstance(masks2, dict):
                masks2 = {}
            if new_name in masks2:
                QtWidgets.QMessageBox.warning(self, 'Exists', f"Mask '{new_name}' already exists.")
                return
            out = dict(masks2)
            node = {'op': op.currentText(), 'a': cb_a.currentText(), 'b': cb_b.currentText()}
            if inv.isChecked():
                node = {'op': 'invert', 'a': node}
            out[new_name] = node
            p2 = dict(p); p2['masks'] = out
            try:
                self.app_core.project = p2
            except Exception:
                return
            try:
                self.app_core.target_mask = new_name
            except Exception:
                pass
            try:
                self.refresh()
            except Exception:
                pass
        
        self.btn_compose.clicked.connect(_mm_compose)
        self.btn_invert.clicked.connect(_mm_invert)
        try:
            self.btn_validate.clicked.connect(self._validate_all)
        except Exception:
            pass
        try:
            self.btn_normalize.clicked.connect(self._normalize_project)
        except Exception:
            pass

        try:
            self.btn_info.clicked.connect(self._info)
        except Exception:
            pass


        def _mm_mask_to_selection():
            try:
                name = None
                try: name = getattr(self, 'selected_name', None)
                except Exception: name = None
                if not name:
                    QtWidgets.QMessageBox.information(self, 'No mask selected', 'Select a mask row first.')
                    return
                p = getattr(self.app_core, 'project', None) or {}
                masks = p.get('masks') if isinstance(p, dict) else None
                node = masks.get(name) if isinstance(masks, dict) else None
                if not isinstance(node, dict) or str(node.get('op','')) != 'indices':
                    QtWidgets.QMessageBox.information(self, 'Not supported', 'Only masks with op = indices can be selected into the selection.')
                    return
                idxs = node.get('indices') or []
                if not isinstance(idxs, list) or not idxs:
                    QtWidgets.QMessageBox.information(self, 'Empty mask', 'Selected mask has no indices.')
                    return
                idxs2=[]
                for x in idxs:
                    try: idxs2.append(int(x))
                    except Exception: pass
                selset = set(i for i in idxs2 if isinstance(i,int) and i>=0)
                for attr in ('selection','selected_indices','selected','sel'):
                    if hasattr(self.app_core, attr):
                        try: setattr(self.app_core, attr, selset)
                        except Exception: pass
                try: self.refresh()
                except Exception: pass
            except Exception:
                return
        try: self.btn_select.clicked.connect(_mm_mask_to_selection)
        except Exception: pass



        self.refresh()

    def _get_masks(self):
        p = getattr(self.app_core, "project", None) or {}
        masks = p.get("masks") or {}
        return masks if isinstance(masks, dict) else {}

    def refresh(self):
        masks = self._get_masks()
        keys = sorted(str(k) for k in masks.keys())
        self.table.setRowCount(len(keys))
        for r, k in enumerate(keys):
            v = masks.get(k) or {}
            typ = "indices"
            size = 0
            if isinstance(v, dict):
                if "op" in v:
                    typ = str(v.get("op") or "op")
                if "indices" in v and isinstance(v.get("indices"), list):
                    try:
                        size = len(set(int(x) for x in v.get("indices") or []))
                    except Exception:
                        size = len(v.get("indices") or [])
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(k))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(typ))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(size)))

# select current target_mask if present (best-effort; never fight focus/selection)
try:
    cur = getattr(self.app_core, 'target_mask', None)
    if cur:
        try:
            if hasattr(self.table, 'hasFocus') and self.table.hasFocus():
                raise RuntimeError('table focused')
        except Exception:
            pass
        try:
            if hasattr(self.table, 'selectedItems') and self.table.selectedItems():
                raise RuntimeError('user selection')
        except Exception:
            pass
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and str(it.text()) == str(cur):
                self.table.selectRow(r)
                break
        self.table.blockSignals(False)
except Exception:
    try:
        self.table.blockSignals(False)
    except Exception:
        pass




    def _selected_key(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        r = rows[0].row()
        it = self.table.item(r, 0)
        return str(it.text()) if it else None

    def _rename(self):
        old = self._selected_key()
        if not old:
            return
        new, ok = QtWidgets.QInputDialog.getText(self, "Rename mask", "New key:", text=old)
        if not ok:
            return
        new = str(new or "").strip()
        if not new or new == old:
            return
        p = getattr(self.app_core, "project", None) or {}
        masks = p.get("masks") or {}
        if not isinstance(masks, dict) or old not in masks:
            return
        if new in masks:
            QtWidgets.QMessageBox.warning(self, "Rename failed", f"Mask '{new}' already exists.")
            return
        masks2 = dict(masks)
        masks2[new] = masks2.pop(old)
        # Keep Target Mask aligned if we renamed the currently-applied one
        try:
            if getattr(self.app_core, 'target_mask', None) == key:
                self.app_core.target_mask = new_key
        except Exception:
            pass

        p2 = dict(p)
        p2["masks"] = masks2
        ui0 = p2.get("ui") or {}
        ui = dict(ui0) if isinstance(ui0, dict) else {}
        if ui.get("target_mask") == old:
            ui["target_mask"] = new
        p2["ui"] = ui
        self.app_core.project = p2
        try:
            self.app_core.target_mask = ui.get("target_mask")
        except Exception:
            pass
        self.refresh()

    def _duplicate(self):
        old = self._selected_key()
        if not old:
            return
        new, ok = QtWidgets.QInputDialog.getText(self, "Duplicate mask", "New key:")
        if not ok:
            return
        new = str(new or "").strip()
        if not new or new == old:
            return
        p = getattr(self.app_core, "project", None) or {}
        masks = p.get("masks") or {}
        if not isinstance(masks, dict) or old not in masks:
            return
        if new in masks:
            QtWidgets.QMessageBox.warning(self, "Duplicate failed", f"Mask '{new}' already exists.")
            return
        masks2 = dict(masks)
        masks2[new] = json.loads(json.dumps(masks2[old]))
        p2 = dict(p)
        p2["masks"] = masks2
        self.app_core.project = p2
        self.refresh()

    def _delete(self):
        key = self._selected_key()
        if not key:
            return
        p = getattr(self.app_core, "project", None) or {}
        masks = p.get("masks") or {}
        if not isinstance(masks, dict) or key not in masks:
            return
        resp = QtWidgets.QMessageBox.question(self, "Delete mask", f"Delete mask '{key}'?",
                                             QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if resp != QtWidgets.QMessageBox.Yes:
            return
        masks2 = dict(masks)
        masks2.pop(key, None)
        # If we just deleted the currently-applied Target Mask, clear it immediately
        try:
            if getattr(self.app_core, 'target_mask', None) == key:
                self.app_core.target_mask = None
        except Exception:
            pass

        p2 = dict(p)
        p2["masks"] = masks2
        ui0 = p2.get("ui") or {}
        ui = dict(ui0) if isinstance(ui0, dict) else {}
        if ui.get("target_mask") == key:
            ui.pop("target_mask", None)
        p2["ui"] = ui
        self.app_core.project = p2
        try:
            self.app_core.target_mask = ui.get("target_mask")
        except Exception:
            pass
        self.refresh()





def _invert(self):
    key = self._selected_key()
    if not key:
        return
    name, ok = QtWidgets.QInputDialog.getText(self, "Invert Mask", "New mask name:", text=f"{key}_inv")
    if not ok:
        return
    name = str(name or "").strip()
    if not name:
        return
    p = getattr(self.app_core, "project", None) or {}
    masks = dict((p.get("masks") or {}) if isinstance(p.get("masks") or {}, dict) else {})
    if name in masks:
        QtWidgets.QMessageBox.warning(self, "Exists", f"Mask '{name}' already exists.")
        return
    masks[name] = {"op": "invert", "a": key}
    p2 = dict(p)
    p2["masks"] = masks
    self.app_core.project = p2
    try:
        self.app_core.target_mask = name
    except Exception:
        pass
    self.refresh()

def _compose(self):
    a = self._selected_key()
    masks = self._get_masks()
    keys = sorted(str(k) for k in masks.keys())
    if not keys:
        return
    if not a:
        a = keys[0]
    # Dialog: op + B + name
    dlg = QtWidgets.QDialog(self)
    dlg.setWindowTitle("Compose Mask")
    lay = QtWidgets.QVBoxLayout(dlg)
    form = QtWidgets.QFormLayout()
    op = QtWidgets.QComboBox()
    op.addItems(["union", "intersect", "subtract", "xor"])
    cb_a = QtWidgets.QComboBox()
    cb_a.addItems(keys)
    cb_a.setCurrentText(str(a))
    cb_b = QtWidgets.QComboBox()
    cb_b.addItems(keys)
    # default B = next different
    for k in keys:
        if k != str(a):
            cb_b.setCurrentText(k)
            break
    name = QtWidgets.QLineEdit(f"{a}_{op.currentText()}_{cb_b.currentText()}")
    def _sync_name():
        name.setText(f"{cb_a.currentText()}_{op.currentText()}_{cb_b.currentText()}")
    op.currentIndexChanged.connect(_sync_name)
    cb_a.currentIndexChanged.connect(_sync_name)
    cb_b.currentIndexChanged.connect(_sync_name)
    form.addRow("Operation", op)
    form.addRow("A", cb_a)
    form.addRow("B", cb_b)
    form.addRow("New name", name)
    lay.addLayout(form)
    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    lay.addWidget(btns)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    if dlg.exec() != QtWidgets.QDialog.Accepted:
        return
    new_name = str(name.text() or "").strip()
    if not new_name:
        return
    p = getattr(self.app_core, "project", None) or {}
    masks2 = dict((p.get("masks") or {}) if isinstance(p.get("masks") or {}, dict) else {})
    if new_name in masks2:
        QtWidgets.QMessageBox.warning(self, "Exists", f"Mask '{new_name}' already exists.")
        return
    masks2[new_name] = {"op": op.currentText(), "a": cb_a.currentText(), "b": cb_b.currentText()}



def _validate_all(self):
    """Validate zones/groups/masks/target_mask and show a dialog."""
    try:
        from app.project_validation import validate_project
    except Exception:
        validate_project = None  # type: ignore

    p = getattr(self.app_core, 'project', None)
    p = p if isinstance(p, dict) else {}

    if validate_project is None:
        try:
            QtWidgets.QMessageBox.critical(self, 'Validate Project', 'Project validator not available.')
        except Exception:
            pass
        return

    ok, probs = validate_project(p)
    if ok:
        try:
            QtWidgets.QMessageBox.information(self, 'Validate Project', 'OK: zones/groups/masks structure looks valid.')
        except Exception:
            pass
        return

    # show up to 40 problems
    probs = [str(x) for x in (probs or []) if str(x).strip()]
    msg = f"{len(probs)} problem(s) found:\n\n" + "\n".join([f"- {x}" for x in probs[:40]])
    if len(probs) > 40:
        msg += f"\n... (+{len(probs)-40} more)"
    try:
        QtWidgets.QMessageBox.critical(self, 'Validate Project', msg)
    except Exception:
        pass
    return
def _selected_mask_name(self):
    try:
        items = self.table.selectedItems() if hasattr(self, 'table') else []
        if not items:
            return None
        return str(items[0].text())
    except Exception:
        return None


    def _info(self):
        """Show resolved info for the selected mask (count/min/max)."""
        key = None
        try:
            key = self._selected_mask_name()
        except Exception:
            key = None
        if not key:
            try:
                QtWidgets.QMessageBox.information(self, 'Mask Info', 'Select a mask first.')
            except Exception:
                pass
            return

        try:
            from app.masks_resolver import resolve_mask_to_indices
        except Exception as e:
            try:
                QtWidgets.QMessageBox.critical(self, 'Mask Info', f'Mask resolver not available: {e}')
            except Exception:
                pass
            return

        p = getattr(self.app_core, 'project', None)
        p = p if isinstance(p, dict) else {}
        layout = p.get('layout') or {}
        n = None
        try:
            if isinstance(layout, dict) and 'count' in layout:
                nn = int(layout.get('count') or 0)
                n = nn if nn > 0 else None
        except Exception:
            n = None

        try:
            idx = sorted(set(resolve_mask_to_indices(p, key, n=n)))
        except Exception as e:
            try:
                QtWidgets.QMessageBox.critical(self, 'Mask Info', f"Failed to resolve '{key}':\n{e}")
            except Exception:
                pass
            return

        if not idx:
            msg = f"'{key}' resolved to 0 indices."
        else:
            msg = f"'{key}' resolved to {len(idx)} indices.\nmin={idx[0]}  max={idx[-1]}"
            if n is not None:
                msg += f"\nlayout count: {n}"
        try:
            QtWidgets.QMessageBox.information(self, 'Mask Info', msg)
        except Exception:
            pass


    def _normalize_project(self):
        """Normalize zones/groups/masks and persist to project (beta lock tool)."""
        try:
            from app.project_normalize import normalize_project_zones_masks_groups
        except Exception as e:
            try:
                QtWidgets.QMessageBox.critical(self, 'Normalize', f'Normalizer not available: {e}')
            except Exception:
                pass
            return

        p = getattr(self.app_core, 'project', None)
        p = p if isinstance(p, dict) else {}
        p2, changes = normalize_project_zones_masks_groups(p)
        self.app_core.project = p2
        try:
            self.refresh()
        except Exception:
            pass
        msg = 'No changes needed.' if not changes else ('Applied:\n' + '\n'.join(changes[:50]) + ('' if len(changes)<=50 else '\n...'))
        try:
            QtWidgets.QMessageBox.information(self, 'Normalize', msg)
        except Exception:
            pass

class LayerStackPanel(QtWidgets.QWidget):






    # () Active Layer Authority helpers (single place to get/set active layer index)
    def _ls_get_active_idx(self):
        try:
            try:
                fn = getattr(self.app_core, "ui_active_layer_index", None)
                if callable(fn):
                    v = fn()
                    if v is not None:
                        return int(v)
            except Exception:
                pass
            try:
                fn2 = getattr(self.app_core, "active_layer_index", None)
                if callable(fn2):
                    v = fn2()
                    if v is not None:
                        return int(v)
            except Exception:
                pass
            try:
                ui = getattr(self.app_core, "ui_state", lambda: {})()
                if isinstance(ui, dict) and ui.get("active_layer_index", None) is not None:
                    return int(ui.get("active_layer_index"))
            except Exception:
                pass
        except Exception:
            pass
        return None

    def _ls_set_active_idx(self, idx: int):
        try:
            idx = int(idx)
            if idx < 0:
                return
            try:
                fn = getattr(self.app_core, "set_ui_active_layer_index", None)
                if callable(fn):
                    fn(idx)
                    return
            except Exception:
                pass
            try:
                fn2 = getattr(self.app_core, "set_active_layer_index", None)
                if callable(fn2):
                    fn2(idx)
                    return
            except Exception:
                pass
            try:
                ui = getattr(self.app_core, "ui_state", lambda: {})()
                if isinstance(ui, dict):
                    ui["active_layer_index"] = idx
            except Exception:
                pass
        except Exception:
            pass

    # () Update [ACTIVE] markers in-place (boot-safe; no nested try injection)
    def _ls_update_active_labels(self):
        try:
            # Identify list widget by first .addItem target used in this class (cached)
            lw = None
            try:
                lw_name = getattr(self, "_ls_list_widget_name", None)
                if lw_name:
                    lw = getattr(self, lw_name, None)
            except Exception:
                lw = None
            if lw is None:
                return

            # Determine active index (best-effort)
            active_idx = self._ls_get_active_idx()
            try:
                fn = getattr(self.app_core, "ui_active_layer_index", None)
                if callable(fn):
                    v = fn()
                    if v is not None:
                        active_idx = int(v)
            except Exception:
                active_idx = None
            if active_idx is None:
                try:
                    ui = getattr(self.app_core, "ui_state", lambda: {})()
                    if isinstance(ui, dict) and ui.get("active_layer_index", None) is not None:
                        active_idx = int(ui.get("active_layer_index"))
                except Exception:
                    pass

            try:
                n = int(getattr(lw, "count", lambda: 0)())
            except Exception:
                n = 0
            for i in range(n):
                try:
                    it = lw.item(i)
                except Exception:
                    it = None
                if it is None:
                    continue
                try:
                    t = str(it.text())
                except Exception:
                    t = ""
                t2 = t.replace("  [ACTIVE]", "")
                if active_idx is not None and i == active_idx:
                    t2 = t2 + "  [ACTIVE]"
                try:
                    if t2 != t:
                        it.setText(t2)
                except Exception:
                    pass
        except Exception:
            pass

    # () Runtime bind: ensure active-layer wiring attaches to the actual list widget used by refresh.
    def _ls_bind_active_widget(self, lw):
        try:
            if lw is None:
                return
            # prevent double-binding
            if getattr(self, "_ls_active_bound", False):
                return
            self._ls_active_bound = True

            def _apply():
                try:
                    idx = -1
                    try:
                        idx = int(getattr(lw, "currentRow", lambda: -1)())
                    except Exception:
                        idx = -1
                    if idx < 0:
                        return
                    # best-effort setter
                    try:
                        fn = getattr(self.app_core, "set_ui_active_layer_index", None)
                        if callable(fn):
                            fn(idx); return
                    except Exception:
                        pass
                    try:
                        fn2 = getattr(self.app_core, "set_active_layer_index", None)
                        if callable(fn2):
                            fn2(idx); return
                    except Exception:
                        pass
                    try:
                        ui = getattr(self.app_core, "ui_state", lambda: {})()
                        if isinstance(ui, dict):
                            ui["active_layer_index"] = idx
                    except Exception:
                        pass
                    # () mark active label dirty (separate try block)
                    try:
                        self._ls_active_dirty = True
                    except Exception:
                        pass
                except Exception:
                    pass

            # connect signals
            try:
                lw.currentRowChanged.connect(lambda *_: _apply())
                return
            except Exception:
                pass
            try:
                lw.itemSelectionChanged.connect(lambda *_: _apply())
                return
            except Exception:
                pass
            try:
                lw.clicked.connect(lambda *_: _apply())
                return
            except Exception:
                pass
        except Exception:
            pass
    # () Set active layer index from UI selection (best-effort; UI-only)
    def _set_active_from_row(self, idx: int):
        try:
            idx = int(idx)
            if idx < 0:
                return
            try:
                fn = getattr(self.app_core, 'set_ui_active_layer_index', None)
                if callable(fn):
                    fn(idx)
                    return
            except Exception:
                pass
            try:
                fn2 = getattr(self.app_core, 'set_active_layer_index', None)
                if callable(fn2):
                    fn2(idx)
                    return
            except Exception:
                pass
            try:
                ui = getattr(self.app_core, 'ui_state', lambda: {})()
                if isinstance(ui, dict):
                    ui['active_layer_index'] = idx
            except Exception:
                pass
        except Exception:
            pass
    # () Layer Stack refresh guard & throttle (UI-only)
    def _ls_refresh_guard(self) -> bool:
        """Return True if refresh should proceed."""
        try:
            # Don't refresh while user is interacting with the list
            lw = getattr(self, 'list', None)
            if lw is not None:
                try:
                    # On some systems the layer list grabs initial focus on window
                    # show; blocking refresh in that moment can leave the list blank
                    # until the user triggers another refresh.
                    #
                    # We only block refresh while the user is interacting *and* the
                    # list already has content.
                    if lw.hasFocus():
                        try:
                            if int(lw.count()) > 0:
                                return False
                        except Exception:
                            return False
                except Exception:
                    pass
            return True
        except Exception:
            return True

    def _ls_should_refresh(self, project_rev) -> bool:
        try:
            last = getattr(self, '_ls_last_project_rev', None)
            if last == project_rev:
                return False
            self._ls_last_project_rev = project_rev
            return True
        except Exception:
            return True

    # () Format layer label with Active marker (UI-only; no preview/export changes)
    def _fmt_layer_label(self, layer, is_active: bool) -> str:
        try:
            name = ""
            try:
                if isinstance(layer, dict):
                    name = str(layer.get("name") or "")
                else:
                    name = str(getattr(layer, "name", "") or "")
            except Exception:
                name = ""
            if not name:
                name = "Layer"
            return f"{name}  [ACTIVE]" if is_active else name
        except Exception:
            return "Layer"
    """Layer Stack MVP (Qt).

    Minimal authoring surface:
      - list layers
      - select active layer
      - enable/disable
      - add / delete
      - move up / down

    Structural only: no per-effect editing here.
    """

    # : minimal operator catalog for the layer operator stack.
    # These are UI-friendly names and param 'uses' lists.
    OP_CATALOG = {
        # Exportable operator kinds (v1). Legacy kinds may still be loaded from older projects.
        'gain':  {'title': 'Gain',  'uses': ['gain']},
        'gamma': {'title': 'Gamma', 'uses': ['gamma']},
        'posterize': {'title': 'Posterize', 'uses': ['posterize_levels']},
        # Legacy (preview-only) kinds retained for backward compatibility display:
        'clamp': {'title': 'Clamp (legacy)', 'uses': ['clamp_min', 'clamp_max']},
        'threshold': {'title': 'Threshold (legacy)', 'uses': ['threshold']},
        'invert': {'title': 'Invert (legacy)', 'uses': []},
    }

    # : Curated starter set to keep effect-picking user-friendly.
    # Users can reveal all shipped effects via a toggle.
    FEATURED_EFFECTS = [
        'solid',
        'fade',
        'strobe',
        'rainbow',
        'gradient',
        'palette',
        'pulse',
        'sparkle',
        'twinkle',
        'noise',
        'chase',
        'wipe',
        'scanner',
        'sweep',
    ]



    def _populate_effects(self, show_all: bool = False):
        """Populate Effect dropdown.

        Default: show a curated starter set + any effects already used in the project.
        Advanced: show all shipped effects.
        """
        used = set()
        hidden = set()
        try:
            caps = load_capabilities_catalog() or {}
            eff = caps.get('effects', {}) or {}
            # Hide preview-only / utility effects from the default picker.
            for k, v in eff.items():
                if isinstance(v, dict):
                    if v.get('preview_only') or v.get('ui_hidden') or v.get('ui_category') == 'utility':
                        hidden.add(str(k))
            shipped = []
            for k, v in eff.items():
                try:
                    if isinstance(v, dict) and v.get('shipped', False):
                        shipped.append(str(k))
                except Exception:
                    pass
            shipped = sorted(set(shipped))
        except Exception:
            shipped = []
        # Fallback: whatever is registered.
        if not shipped:
            try:
                from behaviors.registry import list_effects
                shipped = sorted(list_effects())
            except Exception:
                shipped = ['solid']


        # Release R5 Parity Gate: only surface exportable effects by default.
        # Non-exportable effects remain visible ONLY if already used in the project, so nothing "disappears".
        elig_map = {}
        try:
            from export.export_eligibility import get_eligibility, ExportStatus
            for k in list(shipped):
                try:
                    e = get_eligibility(k)
                    elig_map[str(k)] = e
                except Exception:
                    pass
        except Exception:
            ExportStatus = None
            get_eligibility = None

        # Curate by default (beginner-friendly).
        if not show_all:
            used = set()
            try:
                p = self.app_core.project or {}
                for L in (p.get('layers') or []):
                    if isinstance(L, dict):
                        b = L.get('behavior') or L.get('effect')
                        if b:
                            used.add(str(b))
            except Exception:
                used = set()
            featured = [k for k in self.FEATURED_EFFECTS if k in shipped]
            # Always include anything already used, so nothing disappears.
            extras = sorted([k for k in used if k in shipped and k not in featured])
            shipped = featured + extras

        self.effect.blockSignals(True)
        self.effect.clear()
        for key in shipped:
            if (not show_all) and (key in hidden) and (key not in used):
                continue

            # Parity gate filter: hide non-exportable unless used or show_all.
            tag = ""
            try:
                e = elig_map.get(str(key))
                st = getattr(e, "status", "")
                if st and (ExportStatus is not None):
                    if st == ExportStatus.PREVIEW_ONLY:
                        tag = "[PREVIEW] "
                        if (not show_all) and (key not in used):
                            continue
                    elif st == ExportStatus.BLOCKED:
                        tag = "[BLOCKED] "
                        if (not show_all) and (key not in used):
                            continue
                    elif st == ExportStatus.EXPORTABLE:
                        tag = ""
                # If status unknown, treat as exportable for now.
            except Exception:
                pass

            title = key
            try:
                d = get_effect(key)
                if d is not None:
                    title = getattr(d, 'title', None) or title
            except Exception:
                pass
            self.effect.addItem(str(tag) + str(title), key)
        self.effect.blockSignals(False)

    def _on_effect_changed(self, idx: int):
        if self._effect_block:
            return
        try:
            key = self.effect.itemData(idx)
        except Exception:
            key = None
        if not key:
            return
        # Apply to active layer
        p, layers = self._project_layers()
        ai = int((p.get('active_layer') or 0))
        if ai < 0 or ai >= len(layers):
            return
        L = dict(layers[ai] or {})
        # Update behavior keys
        L['behavior'] = str(key)
        self._sync_ops_with_behavior(L)  # 
        L['effect'] = str(key)
        self._sync_ops_with_behavior(L)  # 
        # Ensure params contain defaults required by the effect
        uses = []
        try:
            d = get_effect(str(key))
            uses = list(getattr(d, 'uses', []) or [])
        except Exception:
            uses = []
        # IMPORTANT: when changing effects, reset params to that effect's defaults.
        # Keeping stale params from a previous effect can blank or "freeze" some renderers.
        L['params'] = defaults_for(uses)
        # Keep operator[0] in sync for parameter UI / future operator pipeline
        try:
            ops = L.get('operators')
            if not isinstance(ops, list) or not ops:
                ops = [{'type': str(key), 'params': {}}]
            op0 = dict(ops[0] or {})
            op0['type'] = str(key)
            # Mirror subset of params into operator params for UI controls
            op0_params = dict(op0.get('params') or {})
            for nm in uses:
                if nm in (L['params'] or {}):
                    op0_params[nm] = (L['params'] or {}).get(nm)
            op0['params'] = op0_params
            ops[0] = op0
            L['operators'] = ops
        except Exception:
            pass

        layers2 = list(layers)
        layers2[ai] = L
        p2 = dict(p)
        p2['layers'] = layers2
        self._commit(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass

    def _on_show_all_effects(self, checked: bool):
        """Toggle between curated effects list and full shipped list."""
        # Remember current layer effect so we can keep selection stable.
        cur_key = None
        try:
            p = self.app_core.project or {}
            layers = p.get('layers') or []
            ai = int((p.get('active_layer') or 0))
            if 0 <= ai < len(layers) and isinstance(layers[ai], dict):
                cur_key = layers[ai].get('behavior') or layers[ai].get('effect')
        except Exception:
            cur_key = None

        self._populate_effects(show_all=bool(checked))

        if cur_key:
            # Re-select without firing change.
            self._effect_block = True
            try:
                for i in range(self.effect.count()):
                    if self.effect.itemData(i) == cur_key:
                        self.effect.setCurrentIndex(i)
                        break
            except Exception:
                pass
            self._effect_block = False

        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass
    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        # ( wire active on self.effect) selection sets active layer
        try:
            lw = getattr(self, 'effect', None)
            if lw is not None:
                try:
                    lw.currentRowChanged.connect(lambda r: self._set_active_from_row(r) if hasattr(self, '_set_active_from_row') else self._set_active_from_row(r))
                except Exception:
                    try:
                        lw.itemSelectionChanged.connect(lambda: (self._set_active_from_row(lw.currentRow()) if hasattr(self, '_set_active_from_row') else self._set_active_from_row(lw.currentRow())))
                    except Exception:
                        pass
        except Exception:
            pass

        # ( wire selection) set active layer when selection changes
        try:
            lw = getattr(self, 'add_btn', None)
            if lw is not None:
                try:
                    lw.currentRowChanged.connect(lambda r: self._set_active_from_row(r))
                except Exception:
                    try:
                        lw.clicked.connect(lambda *_: self._set_active_from_row(getattr(lw, 'currentRow', lambda: -1)()))
                    except Exception:
                        pass
        except Exception:
            pass

        # : Refresh throttling / change detection.
        # The main window may call layers_panel.refresh() frequently during UI sync.
        # A full sync_from_project() rebuild is expensive and can cause visible preview flicker.
        # We cache a lightweight signature of the layer stack and only rebuild when it changes.
        self._last_layers_sig = None
        self._last_refresh_t = 0.0

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.list.itemSelectionChanged.connect(self._on_selected)
        self.list.itemChanged.connect(self._on_item_changed)
        outer.addWidget(self.list, 1)
        # Optional per-operator mask targeting (Phase O3 MVP)
        
        # Per-operator targeting (Phase O3 MVP):
        # Apply operator to: All / Mask / Zone / Group
        trow = QtWidgets.QHBoxLayout()
        trow.setSpacing(6)
        trow.addWidget(QtWidgets.QLabel("Apply To:"), 0)

        self.op_target_kind = QtWidgets.QComboBox()
        self.op_target_kind.setToolTip("Choose where this operator applies: All, Mask, Zone, or Group.")
        self.op_target_kind.addItems(["All", "Layer Target", "Mask", "Zone", "Group"])
        self.op_target_kind.setMinimumWidth(110)
        trow.addWidget(self.op_target_kind, 0)

        self.op_target_key = QtWidgets.QComboBox()
        self.op_target_key.setToolTip("Select the specific Mask/Zone/Group key. (All = none)")
        self.op_target_key.setMinimumWidth(220)
        trow.addWidget(self.op_target_key, 1)

        self.btn_target_jump = QtWidgets.QPushButton("Edit Targets…")
        self.btn_target_jump.setToolTip("Go to Targets tab to edit Zones/Masks/Groups.")
        trow.addWidget(self.btn_target_jump, 0)

        outer.addLayout(trow, 0)
        try:
            self.list.currentRowChanged.connect(self._sync_target_from_selection)
        except Exception:
            pass
        try:
            self.op_target_kind.currentIndexChanged.connect(self._on_op_target_kind_changed)
            self.op_target_key.currentIndexChanged.connect(self._on_op_target_key_changed)
        except Exception:
            pass

        # NOTE: Legacy hard-coded Gain slider removed ().
        # Operator parameters are edited via the auto-generated Parameters panel,
        # which binds to the currently-selected operator and is always correct.

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(6)
        self.add_btn = QtWidgets.QPushButton("Add")
        self.del_btn = QtWidgets.QPushButton("Delete")
        self.dup_btn = QtWidgets.QPushButton("Duplicate")
        self.up_btn = QtWidgets.QPushButton("Up")
        self.down_btn = QtWidgets.QPushButton("Down")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.dup_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.up_btn)
        btn_row.addWidget(self.down_btn)
        outer.addLayout(btn_row)

        self.add_btn.clicked.connect(self._add_layer)
        self.dup_btn.clicked.connect(self._duplicate_layer)
        self.del_btn.clicked.connect(self._delete_layer)
        self.up_btn.clicked.connect(lambda: self._move_layer(-1))
        self.down_btn.clicked.connect(lambda: self._move_layer(+1))

        hint = QtWidgets.QLabel("Tip: top = highest priority. Uncheck to disable.")
        hint.setWordWrap(True)
        outer.addWidget(hint)


        # Operators/PostFX MVP: minimal per-layer properties
        props = QtWidgets.QGroupBox("Layer Properties")
        props_lay = QtWidgets.QFormLayout(props)
        props_lay.setContentsMargins(8, 8, 8, 8)

        # : Effect picker (shipped effects). This sets the layer behavior.
        self.effect = QtWidgets.QComboBox()
        self._effect_block = False
        self.show_all_effects = QtWidgets.QCheckBox("Show all")
        self.show_all_effects.setToolTip("Show the full shipped effects library")
        self._populate_effects(show_all=False)
        self.effect.currentIndexChanged.connect(self._on_effect_changed)
        eff_row = QtWidgets.QHBoxLayout()
        eff_row.addWidget(self.effect, 1)
        eff_row.addWidget(self.show_all_effects)
        props_lay.addRow("Effect", eff_row)
        self.show_all_effects.toggled.connect(self._on_show_all_effects)

        self.opacity = QtWidgets.QSlider(_ORI_H)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(100)
        self.opacity.valueChanged.connect(self._on_opacity_changed)
        self.opacity_lbl = QtWidgets.QLabel("1.00")
        op_row = QtWidgets.QHBoxLayout()
        op_row.addWidget(self.opacity, 1)
        op_row.addWidget(self.opacity_lbl)
        props_lay.addRow("Opacity", op_row)

        self.blend = QtWidgets.QComboBox()
        self.blend.addItems(["over", "add", "multiply", "screen"])
        self.blend.currentTextChanged.connect(self._on_blend_changed)
        props_lay.addRow("Blend", self.blend)

        self.target = QtWidgets.QComboBox()
        self.target.currentIndexChanged.connect(self._on_target_changed)
        props_lay.addRow("Target", self.target)

        outer.addWidget(props)

        # : Operators (MVP)
        self.ops_group = QtWidgets.QGroupBox("Operators")
        og_lay = QtWidgets.QVBoxLayout(self.ops_group)
        og_lay.setContentsMargins(8, 8, 8, 8)
        og_lay.setSpacing(6)

        self.ops_list = QtWidgets.QListWidget()
        self.ops_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.ops_list.itemSelectionChanged.connect(self._on_op_selected)
        og_lay.addWidget(self.ops_list, 1)

        ops_btns = QtWidgets.QHBoxLayout()
        ops_btns.setSpacing(6)
        self.op_add_btn = QtWidgets.QPushButton("+")
        self.op_del_btn = QtWidgets.QPushButton("−")
        self.op_up_btn = QtWidgets.QPushButton("Up")
        self.op_down_btn = QtWidgets.QPushButton("Down")
        ops_btns.addWidget(self.op_add_btn)
        ops_btns.addWidget(self.op_del_btn)
        ops_btns.addStretch(1)
        ops_btns.addWidget(self.op_up_btn)
        ops_btns.addWidget(self.op_down_btn)
        og_lay.addLayout(ops_btns)

        self.op_add_btn.clicked.connect(self._add_operator)
        self.op_del_btn.clicked.connect(self._delete_operator)
        self.op_up_btn.clicked.connect(lambda: self._move_operator(-1))
        self.op_down_btn.clicked.connect(lambda: self._move_operator(+1))

        outer.addWidget(self.ops_group)

        # : Effect parameter panel (auto-generated, user-friendly)
        self.params_group = QtWidgets.QGroupBox("Effect Parameters")
        pg_lay = QtWidgets.QVBoxLayout(self.params_group)
        pg_lay.setContentsMargins(8, 8, 8, 8)
        pg_lay.setSpacing(6)

        self._params_inner = QtWidgets.QWidget()
        self.params_form = QtWidgets.QFormLayout(self._params_inner)
        self.params_form.setContentsMargins(0, 0, 0, 0)
        self.params_form.setSpacing(6)

        self.params_scroll = QtWidgets.QScrollArea()
        self.params_scroll.setWidgetResizable(True)
        self.params_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.params_scroll.setWidget(self._params_inner)
        pg_lay.addWidget(self.params_scroll, 1)

        self._params_hint = QtWidgets.QLabel("(Select a layer to edit its effect parameters)")
        self._params_hint.setWordWrap(True)
        pg_lay.addWidget(self._params_hint)

        outer.addWidget(self.params_group)

        self._suppress = False
        self._target_zone_ids = []  # combo index -> zone id (or None)
        #  param UI state
        self._param_widgets = {}  # name -> (widget(s), meta)
        self._param_names = []
        self._param_layer_index = -1
        self._param_behavior_key = None
        #  operator UI state
        self._op_layer_index = -1
        self._op_index = 0
        #  operator selection
        self._op_index = 0
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass


        # : Ensure the layer list is populated on startup.
        try:
            QtCore.QTimer.singleShot(0, self.sync_from_project)
        except Exception:
            try:
                self.sync_from_project()
            except Exception:
                pass


    def _sync_ops_with_behavior(self, layer: dict):
        """Ensure operators[0].type mirrors layer behavior/effect ()."""
        try:
            if not isinstance(layer, dict):
                return
            beh = str(layer.get('behavior') or layer.get('effect') or 'solid')
            ops = layer.get('operators')
            if not isinstance(ops, list):
                ops = []
            if not ops:
                layer['operators'] = [{'type': beh, 'params': {}}]
                return
            op0 = ops[0] if isinstance(ops[0], dict) else {}
            params = op0.get('params')
            if not isinstance(params, dict):
                params = {}
            ops2 = list(ops)
            ops2[0] = {'type': beh, 'params': params}
            layer['operators'] = ops2
        except Exception:
            return

    def _project_layers(self):
        try:
            p = self.app_core.project or {}
        except Exception:
            p = {}
        try:
            layers = list(p.get('layers') or [])
        except Exception:
            layers = []
        return p, layers

    # --- : operators helpers ---
    def _ensure_layer_ops(self, lay: dict):
        """Ensure layer has an operator list; migrate from behavior/params if missing."""
        try:
            ops = lay.get('operators', None)
        except Exception:
            ops = None
        if not isinstance(ops, list) or len(ops) == 0:
            beh = str(lay.get('behavior') or 'solid')
            params = dict(lay.get('params') or {})
            ops = [{'type': beh, 'params': params}]
            lay['operators'] = ops
        # Normalize operator entries
        norm = []
        # Allow ANY registered effect id as the base operator (index 0).
        # Post operators (index > 0) are restricted to OP_CATALOG (e.g. gain).
        for i, op in enumerate(ops):
            if not isinstance(op, dict):
                continue
            raw_t = str(op.get('type') or ('solid' if i == 0 else 'gain')).lower().strip()
            t = raw_t
            if i == 0:
                # Base operator: must exist in the behaviors registry; otherwise fallback to solid.
                try:
                    _ = get_effect(t)
                except Exception:
                    t = 'solid'
            else:
                if t not in self.OP_CATALOG:
                    t = 'gain'
            prm = dict(op.get('params') or {})
            norm.append({'type': t, 'params': prm})
        if not norm:
            norm = [{'type': 'solid', 'params': {}}]
        lay['operators'] = norm
        # Keep legacy fields in sync with the first operator for preview/export parity
        try:
            lay['behavior'] = str(norm[0].get('type') or 'solid')
        except Exception:
            lay['behavior'] = 'solid'
        try:
            lay['params'] = dict(norm[0].get('params') or {})
        except Exception:
            lay['params'] = {}
        return lay

    def _sync_ops_list(self, layer_index: int):
        """Populate operator list for a given layer index."""
        p, layers = self._project_layers()
        if layer_index < 0 or layer_index >= len(layers):
            self.ops_list.clear()
            self._op_layer_index = -1
            self._op_index = 0
            return
        lay = dict(layers[layer_index] or {})
        lay = self._ensure_layer_ops(lay)
        layers[layer_index] = lay
        # Commit migration if needed
        p2 = dict(p)
        p2['layers'] = layers
        self._commit(p2)

        ops = list(lay.get('operators') or [])
        self._suppress = True
        try:
            self.ops_list.clear()
            for i, op in enumerate(ops):
                if i == 0:
                    # Hide base effect (operator 0) from this UI list
                    continue
                t = str((op or {}).get('type') or ('solid' if i == 0 else 'gain'))
                title = str((self.OP_CATALOG.get(t) or {}).get('title') or t)
                if i == 0 and title == t:
                    try:
                        d = get_effect(t)
                        title = str(getattr(d, 'title', None) or title)
                    except Exception:
                        pass
                it = QtWidgets.QListWidgetItem(title)
                it.setData(QtCore.Qt.ItemDataRole.UserRole, int(i))
                self.ops_list.addItem(it)
            # Select current op index (stored as real op index in UserRole)
            want = int(self._op_index or 0)
            if self.ops_list.count() > 0:
                found = False
                for r in range(self.ops_list.count()):
                    it2 = self.ops_list.item(r)
                    try:
                        if int(it2.data(QtCore.Qt.ItemDataRole.UserRole)) == want:
                            self.ops_list.setCurrentRow(r)
                            found = True
                            break
                    except Exception:
                        pass
                if not found:
                    self.ops_list.setCurrentRow(0)
            self._op_layer_index = int(layer_index)
            # Keep stored index as the real op index
            try:
                it = self.ops_list.currentItem()
                self._op_index = int(it.data(QtCore.Qt.ItemDataRole.UserRole)) if it is not None else 0
            except Exception:
                self._op_index = 0
        finally:
            self._suppress = False

    def _current_operator(self):
        p, layers = self._project_layers()
        li = int(self.list.currentRow())
        if li < 0 or li >= len(layers):
            return None, None, None
        lay = dict(layers[li] or {})
        lay = self._ensure_layer_ops(lay)
        ops = list(lay.get('operators') or [])
        oi = 0
        try:
            it = self.ops_list.currentItem()
            if it is not None:
                oi = int(it.data(QtCore.Qt.ItemDataRole.UserRole))
        except Exception:
            oi = 0
        if oi < 0 or oi >= len(ops):
            oi = 0
        op = ops[oi] if ops else None
        return li, oi, op

    def _commit(self, p2):
        old_pd = getattr(self.app_core, 'project_data', None)
        new_pd = _normalize_project(p2)
        self.app_core.project = new_pd
        # Keep a canonical live project_data reference for all preview/render paths.
        try:
            setattr(self.app_core, 'project_data', new_pd)
        except Exception:
            pass
        # Only rebuild the full preview engine when layout changes; other edits should not blank/flicker.
        try:
            layout_changed = False
            if isinstance(old_pd, dict) and isinstance(new_pd, dict):
                layout_changed = (new_pd.get('layout') != old_pd.get('layout'))
            if layout_changed and hasattr(self.app_core, '_rebuild_full_preview_engine'):
                self.app_core._rebuild_full_preview_engine()
        except Exception:
            pass

        # Mark preview dirty so the next paint (or explicit rebuild_preview) syncs engine.project.
        try:
            setattr(self.app_core, '_preview_dirty', True)
        except Exception:
            pass

        # Sync enabled/deleted layer changes into the PreviewEngine's Project object.
        # Use rebuild_preview so widgets get a redraw nudge.
        try:
            if hasattr(self.app_core, 'rebuild_preview'):
                self.app_core.rebuild_preview('layers_commit')
            elif hasattr(self.app_core, 'sync_preview_engine_from_project_data'):
                self.app_core.sync_preview_engine_from_project_data()
        except Exception:
            pass

    def sync_from_project(self):
        if self._suppress:
            return
        p, layers = self._project_layers()
        try:
            active = int(p.get('active_layer', 0) or 0)
        except Exception:
            active = 0

        self._suppress = True
        try:
            self.list.clear()
            for i, lay in enumerate(layers):
                name = str((lay or {}).get('name') or f'Layer {i}')
                enabled = bool((lay or {}).get('enabled', True))
                export_tip = ''
                # Step 2: show export status next to the layer name (single source)
                try:
                    from export.parity_summary import layer_parity, layer_tag_text
                    lp = layer_parity(i, lay or {})
                    if lp is not None:
                        export_tip = str(lp.reason or '')
                        name = f"{name}  {layer_tag_text(lp.status)}"
                except Exception:
                    pass
                it = QtWidgets.QListWidgetItem(name)
                # PARITY_FIX_ACTIVE_BOLD: visually mark the active layer
                try:
                    fnt = it.font()
                    fnt.setBold(bool(i == active))
                    it.setFont(fnt)
                    tip_parts = []
                    if i == active:
                        tip_parts.append('Active layer')
                    if export_tip:
                        tip_parts.append(export_tip)
                    it.setToolTip('\n'.join(tip_parts))
                except Exception:
                    pass
                # Show a small color swatch (editor-only)
                try:
                    dc = (lay or {}).get("debug_color") or _pick_debug_color(i)
                    if isinstance(dc, (list, tuple)) and len(dc) >= 3:
                        pm = QtGui.QPixmap(14, 14)
                        pm.fill(QtGui.QColor(int(dc[0]) & 255, int(dc[1]) & 255, int(dc[2]) & 255))
                        it.setIcon(QtGui.QIcon(pm))
                except Exception:
                    pass
                # Enum compatibility (PyQt6/PySide6)
                it.setData(QtCore.Qt.ItemDataRole.UserRole, int(i))
                it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEditable)
                it.setCheckState(QtCore.Qt.CheckState.Checked if enabled else QtCore.Qt.CheckState.Unchecked)
                self.list.addItem(it)
            if 0 <= active < self.list.count():
                self.list.setCurrentRow(active)
            try:
                self._rebuild_target_items()
            except Exception:
                pass
            try:
                self._sync_props_from_project()
            except Exception:
                pass
            try:
                self._sync_ops_list(int(active))
            except Exception:
                pass
            try:
                self._build_param_controls(int(active))
            except Exception:
                pass
        finally:
            self._suppress = False


    # : Compatibility alias — other panels/tooling may call refresh().
    def refresh(self):
        # () throttle by project revision
        try:
            pr = None
            try:
                pr = getattr(self.app_core, 'project_rev', lambda: None)()
            except Exception:
                pr = None
            if pr is not None and not self._ls_should_refresh(pr):
                return
        except Exception:
            pass
        # () focus guard
        try:
            if not self._ls_refresh_guard():
                return
        except Exception:
            pass
        # ( cache list widget)
        try:
            self._ls_list_widget_name = 'effect'
        except Exception:
            pass
        # ( active dirty update)
        try:
            if getattr(self, '_ls_active_dirty', False):
                self._ls_active_dirty = False
                if hasattr(self, '_ls_update_active_labels'):
                    self._ls_update_active_labels()
        except Exception:
            pass
        # ( runtime bind) bind active-layer selection to the actual list widget
        try:
            lw = getattr(self, 'effect', None)
            self._ls_bind_active_widget(lw)
        except Exception:
            pass
        # ( selection snapshot)
        sel_row = None
        try:
            lw = getattr(self, 'list', None)
            if lw is not None:
                sel_row = lw.currentRow()
        except Exception:
            sel_row = None
        # ( active fallback) ensure active layer is valid
        try:
            # Prefer app_core UI active index if available
            active_idx = None
            try:
                active_idx = int(getattr(self.app_core, "ui_active_layer_index", lambda: None)())
            except Exception:
                try:
                    active_idx = int(getattr(self.app_core, "active_layer_index", lambda: None)())
                except Exception:
                    active_idx = None
            if active_idx is None:
                try:
                    ui = getattr(self.app_core, "ui_state", lambda: {})()
                    if isinstance(ui, dict):
                        v = ui.get("active_layer_index", None)
                        if v is not None:
                            active_idx = int(v)
                except Exception:
                    pass
            # Normalize active_idx into range when layers are available
            try:
                if 'layers' in locals() and isinstance(layers, (list, tuple)) and layers:
                    if active_idx is None or active_idx < 0 or active_idx >= len(layers):
                        active_idx = 0
                        # best-effort writeback
                        try:
                            sp = getattr(self.app_core, "set_ui_active_layer_index", None)
                            if callable(sp):
                                sp(active_idx)
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            active_idx = None
        # : Throttle + only rebuild when layer stack actually changes.
        try:
            import time as _time
            now = _time.monotonic()
        except Exception:
            now = 0.0

        # ( restore selection)
        try:
            lw = getattr(self, 'list', None)
            if lw is not None and lw.count() > 0:
                # Prefer active_idx if present
                if 'active_idx' in locals() and isinstance(active_idx, int) and 0 <= active_idx < lw.count():
                    lw.setCurrentRow(active_idx)
                elif sel_row is not None and 0 <= int(sel_row) < lw.count():
                    lw.setCurrentRow(int(sel_row))
        except Exception:
            pass

        # Prevent re-entrant / excessively frequent rebuilds.
        try:
            if now and (now - float(getattr(self, '_last_refresh_t', 0.0)) < 0.08):
                # Even when throttling, keep property widgets in sync for active layer.
                try:
                    self._sync_props_from_project()
                except Exception:
                    pass
                return
        except Exception:
            pass

        sig = None
        try:
            p, layers = self._project_layers()
            active = int(p.get('active_layer', 0) or 0)
            parts = [active, len(layers)]
            for L in layers:
                if not isinstance(L, dict):
                    parts.append(('?', False, ''))
                    continue
                uid = L.get('__uid') or L.get('uid') or ''
                name = L.get('name') or ''
                en = bool(L.get('enabled', True))
                parts.append((str(uid), en, str(name)))
            sig = tuple(parts)
        except Exception:
            sig = None

        try:
            if sig is not None and sig == getattr(self, '_last_layers_sig', None):
                # Only the active index might have changed; keep props and bolding in sync.
                try:
                    self._sync_props_from_project()
                except Exception:
                    pass
                try:
                    # Ensure bold state matches active without rebuilding the whole list.
                    if isinstance(sig, tuple) and len(sig) >= 2:
                        active = int(sig[0])
                        for i in range(self.list.count()):
                            it = self.list.item(i)
                            if it is None:
                                continue
                            fnt = it.font(); fnt.setBold(bool(i == active)); it.setFont(fnt)
                except Exception:
                    pass
                self._last_refresh_t = now or getattr(self, '_last_refresh_t', 0.0)
                return
        except Exception:
            pass

        self._last_layers_sig = sig
        self._last_refresh_t = now or getattr(self, '_last_refresh_t', 0.0)
        return self.sync_from_project()


    def _rebuild_target_items(self):
        """Rebuild Target dropdown from current project zones (stable ids)."""
        self.target.blockSignals(True)
        try:
            self.target.clear()
            self._target_zone_ids = [None]  # index 0 = all
            self.target.addItem("all")

            p, _layers = self._project_layers()
            try:
                zones = list((p.get("zones") or []))
            except Exception:
                zones = []

            # Only expose zones for now (Groups can come later)
            for zi, z in enumerate(zones):
                name = None
                zid = None
                if isinstance(z, dict):
                    name = z.get("name")
                    zid = z.get("id")
                try:
                    if name is None and hasattr(z, "name"):
                        name = getattr(z, "name")
                except Exception:
                    name = None
                try:
                    if zid is None and hasattr(z, "id"):
                        zid = getattr(z, "id")
                except Exception:
                    zid = None

                label = f"zone:{zi}" if not name else f"zone:{zi} — {name}"
                self.target.addItem(label)
                self._target_zone_ids.append(str(zid or ""))  # aligns with combo index
        finally:
            self.target.blockSignals(False)

    def _sync_props_from_project(self):
        """Sync property widgets from the active layer."""
        p, layers = self._project_layers()
        try:
            active = int(p.get("active_layer", 0) or 0)
        except Exception:
            active = 0
        if not (0 <= active < len(layers)):
            return
        L = layers[active] or {}
        # effect
        try:
            beh = str(L.get('behavior') or 'solid')
        except Exception:
            beh = 'solid'
        try:
            self._effect_block = True
            # find index by userData key
            idx = -1
            for i in range(self.effect.count()):
                try:
                    if str(self.effect.itemData(i)) == beh:
                        idx = i
                        break
                except Exception:
                    pass
            if idx >= 0:
                self.effect.setCurrentIndex(idx)
        finally:
            self._effect_block = False

        # opacity
        try:
            op = float(L.get("opacity", 1.0) or 1.0)
        except Exception:
            op = 1.0
        if op < 0.0: op = 0.0
        if op > 1.0: op = 1.0
        try:
            self.opacity.blockSignals(True)
            self.opacity.setValue(int(round(op * 100.0)))
        finally:
            self.opacity.blockSignals(False)
        try:
            self.opacity_lbl.setText(f"{op:.2f}")
        except Exception:
            pass
        # blend mode
        blend = str(L.get("blend_mode", "over") or "over").lower().strip()
        if blend not in ("over", "add", "multiply", "screen"):
            blend = "over"
        try:
            self.blend.blockSignals(True)
            self.blend.setCurrentText(blend)
        finally:
            self.blend.blockSignals(False)
        # target
        tk = str(L.get("target_kind", "all") or "all").lower().strip()
        tr = int(L.get("target_ref", 0) or 0)
        target_index = 0
        if tk == "zone":
            target_index = 1 + max(0, tr)
        try:
            self.target.blockSignals(True)
            if 0 <= target_index < self.target.count():
                self.target.setCurrentIndex(target_index)
            else:
                self.target.setCurrentIndex(0)
        finally:
            self.target.blockSignals(False)

    def _set_active_layer_fields(self, updates: dict):
        p, layers = self._project_layers()
        try:
            active = int(p.get("active_layer", 0) or 0)
        except Exception:
            active = 0
        if not (0 <= active < len(layers)):
            return
        layers = list(layers)
        lay = dict(layers[active] or {})
        lay.update(updates)
        layers[active] = lay
        p2 = dict(p)
        p2["layers"] = layers
        self._commit(p2)

    def _on_opacity_changed(self, v: int):
        if self._suppress:
            return
        op = float(int(v)) / 100.0
        try:
            self.opacity_lbl.setText(f"{op:.2f}")
        except Exception:
            pass
        self._set_active_layer_fields({"opacity": op})

    def _on_blend_changed(self, txt: str):
        if self._suppress:
            return
        b = str(txt or "over").lower().strip()
        if b not in ("over","add","multiply","screen"):
            b = "over"
        self._set_active_layer_fields({"blend_mode": b})

    def _on_target_changed(self, idx: int):
        if self._suppress:
            return
        idx = int(idx)

        if idx <= 0:
            # Clear target routing (full canvas)
            self._set_active_layer_fields({"target_kind": "all", "target_ref": 0, "target_id": ""})
            return

        # idx 1.. maps to zones. We store stable ids in _target_zone_ids
        zi = idx - 1
        zid = ""
        try:
            if 0 <= idx < len(self._target_zone_ids):
                zid = str(self._target_zone_ids[idx] or "")
        except Exception:
            zid = ""

        self._set_active_layer_fields({"target_kind": "zone", "target_ref": int(zi), "target_id": zid})
    def _on_selected(self):
        if self._suppress:
            return
        row = int(self.list.currentRow())
        if row < 0:
            return
        # Editor-only: remember selected layer for debug overlay (no export impact)
        try:
            self.app_core._ui_selected_layer = int(row)
        except Exception:
            self.app_core._ui_selected_layer = None
        p, _layers = self._project_layers()
        p2 = dict(p)
        p2['active_layer'] = int(row)
        self._commit(p2)
        try:
            self._sync_props_from_project()
        except Exception:
            pass
        try:
            # When switching layers, default operator selection to the base operator.
            # This avoids confusing "blank" parameter panels when the previous layer
            # had a different operator selected (e.g., Gain).
            self._op_index = 0
            self._sync_ops_list(int(row))
        except Exception:
            pass
        try:
            self._build_param_controls(int(row))
        except Exception:
            pass

    def _on_item_changed(self, item):
        if self._suppress:
            return
        row = int(self.list.row(item))
        if row < 0:
            return
        p, layers = self._project_layers()
        if not (0 <= row < len(layers)):
            return
        lay = dict(layers[row] or {})
        lay['name'] = str(item.text() or f'Layer {row}')
        lay['enabled'] = (item.checkState() == QtCore.Qt.CheckState.Checked)
        layers[row] = lay
        p2 = dict(p)
        p2['layers'] = layers
        self._commit(p2)

    # --- : operator stack handlers ---
    def _on_op_selected(self):
        if self._suppress:
            return
        li = int(self.list.currentRow())
        if li < 0:
            return
        # Store real operator index (UserRole). Base op (0) is hidden.
        try:
            it = self.ops_list.currentItem()
            self._op_index = int(it.data(QtCore.Qt.ItemDataRole.UserRole)) if it is not None else 0
        except Exception:
            self._op_index = 0
        # Rebuild parameter controls for selected operator
        try:
            self._build_param_controls(li)
        except Exception:
            pass

    def _add_operator(self):
        li = int(self.list.currentRow())
        if li < 0:
            return
        p, layers = self._project_layers()
        if not (0 <= li < len(layers)):
            return
        lay = dict(layers[li] or {})
        lay = self._ensure_layer_ops(lay)
        ops = list(lay.get('operators') or [])
        # MVP rule: first op is always Solid. Additional ops currently allow Gain.
        choices = []
        if len(ops) == 0:
            choices = ['solid']
        else:
            choices = ['gain', 'gamma', 'clamp', 'posterize', 'threshold', 'invert']
        # Simple chooser if multiple (future-proof)
        pick = choices[0]
        if len(choices) > 1:
            items = [self.OP_CATALOG[c]['title'] for c in choices]
            title, ok = QtWidgets.QInputDialog.getItem(self, 'Add Operator', 'Type:', items, 0, False)
            if not ok:
                return
            # map title back
            for c in choices:
                if self.OP_CATALOG[c]['title'] == title:
                    pick = c
                    break
        # Defaults
        prm = {}
        if pick == 'gain':
            prm = {'gain': 1.0}
        elif pick == 'gamma':
            prm = {'gamma': 1.0}
        elif pick == 'clamp':
            prm = {'clamp_min': 0.0, 'clamp_max': 255.0}
        elif pick == 'posterize':
            prm = {'posterize_levels': 6.0}
        elif pick == 'threshold':
            prm = {'threshold': 128.0}
        elif pick == 'invert':
            prm = {}
        new_op = {'type': pick, 'params': prm}
        # Default: new post operators follow the layer's target unless user overrides.
        if pick != 'solid':
            new_op['target_kind'] = 'layer'
            new_op['target_key'] = ''
        ops.append(new_op)
        lay['operators'] = ops
        lay = self._ensure_layer_ops(lay)
        layers[li] = lay
        p2 = dict(p); p2['layers'] = layers
        self._commit(p2)
        self._op_index = len(ops) - 1
        self._sync_ops_list(li)
        self._build_param_controls(li)

    def _delete_operator(self):
        li, oi, op = self._current_operator()
        if li is None:
            return
        if oi == 0:
            # Don't allow deleting the base op
            return
        p, layers = self._project_layers()
        lay = dict(layers[li] or {})
        lay = self._ensure_layer_ops(lay)
        ops = list(lay.get('operators') or [])
        if 0 <= oi < len(ops):
            ops.pop(oi)
        lay['operators'] = ops
        lay = self._ensure_layer_ops(lay)
        layers[li] = lay
        p2 = dict(p); p2['layers'] = layers
        self._commit(p2)
        self._op_index = max(0, oi - 1)
        self._sync_ops_list(li)
        self._build_param_controls(li)

    def _move_operator(self, delta: int):
        li, oi, op = self._current_operator()
        if li is None:
            return
        if oi <= 0:
            return
        p, layers = self._project_layers()
        lay = dict(layers[li] or {})
        lay = self._ensure_layer_ops(lay)
        ops = list(lay.get('operators') or [])
        nj = oi + int(delta)
        if nj <= 0 or nj >= len(ops):
            return
        ops[oi], ops[nj] = ops[nj], ops[oi]
        lay['operators'] = ops
        lay = self._ensure_layer_ops(lay)
        layers[li] = lay
        p2 = dict(p); p2['layers'] = layers
        self._commit(p2)
        self._op_index = nj
        self._sync_ops_list(li)
        self._build_param_controls(li)

    def _new_default_layer(self):
        """Create a fresh layer with a valid behavior key + parameter defaults.

        UX note:
          - In  we started new layers disabled to avoid the "everything turns red" surprise.
          - With per-layer default colors + editor overlays in place, it's now more user-friendly
            for a newly-added layer to be immediately visible when enabled.

        Correctness note:
          - Preview engine expects layers to use the 'behavior' key (not 'effect').
            If we only set 'effect', the engine may skip the layer.
        """
        return {
            'enabled': True,
            'name': 'New Layer',
            'behavior': 'solid',
            'effect': 'solid',
            'params': {'color': [255, 0, 0], 'brightness': 1.0},
            'operators': [{'type': 'solid', 'params': {'color': [255, 0, 0], 'brightness': 1.0}}],
            'modulotors': [],
            'mods': [],
            'opacity': 1.0,
            'blend_mode': 'over',
            'target_kind': 'all',
            'target_ref': 0,
            'target_id': '',
        }

    def _add_layer(self):
        p, layers = self._project_layers()
        layers = list(layers)
        newL = self._new_default_layer()
        # Make new layers visually distinct by default (safe placeholder).
        try:
            dc = list(_pick_debug_color(len(layers)))
            newL['debug_color'] = dc
            if isinstance(newL.get('params'), dict):
                newL['params'] = dict(newL['params'])
                newL['params']['color'] = dc[:]  # placeholder render color
                try:
                    if isinstance(newL.get('operators'), list) and newL['operators']:
                        op0 = dict(newL['operators'][0] or {})
                        prm = dict(op0.get('params') or {})
                        prm['color'] = dc[:]
                        op0['params'] = prm
                        newL['operators'][0] = op0
                except Exception:
                    pass
        except Exception:
            pass
        layers.append(newL)
        p2 = dict(p)
        p2['layers'] = layers
        p2['active_layer'] = len(layers) - 1
        self._commit(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass

    
    def _duplicate_layer(self):
        row = int(self.list.currentRow())
        if row < 0:
            return
        p, layers = self._project_layers()
        if not (0 <= row < len(layers)):
            return
        src = dict(layers[row] or {})
        dup = dict(src)
        # New stable uid (engine-owned state keys depend on this)
        try:
            import uuid as _uuid
            uid = _uuid.uuid4().hex
        except Exception:
            uid = ""
        if uid:
            dup['uid'] = uid
            dup['__uid'] = uid
        # Name
        base_name = str(src.get('name') or f'Layer {row}')
        dup['name'] = f"Copy of {base_name}"
        # Ensure enabled defaults
        dup['enabled'] = bool(dup.get('enabled', True))
        layers2 = list(layers)
        new_index = row + 1
        layers2.insert(new_index, dup)
        p2 = dict(p)
        p2['layers'] = layers2
        p2['active_layer'] = int(new_index)
        self._commit(p2)
        try:
            self.refresh()
        except Exception:
            pass

    def _delete_layer(self):
        row = int(self.list.currentRow())
        if row < 0:
            return
        p, layers = self._project_layers()
        if len(layers) <= 1:
            return
        layers = list(layers)
        layers.pop(row)
        active = int(p.get('active_layer', 0) or 0)
        if active >= len(layers):
            active = len(layers) - 1
        p2 = dict(p)
        p2['layers'] = layers
        p2['active_layer'] = int(active)
        self._commit(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass

    def _move_layer(self, delta: int):
        row = int(self.list.currentRow())
        if row < 0:
            return
        p, layers = self._project_layers()
        layers = list(layers)
        j = row + int(delta)
        if not (0 <= j < len(layers)):
            return
        layers[row], layers[j] = layers[j], layers[row]
        active = int(p.get('active_layer', 0) or 0)
        if active == row:
            active = j
        elif active == j:
            active = row
        p2 = dict(p)
        p2['layers'] = layers
        p2['active_layer'] = int(active)
        self._commit(p2)
        # compatibility: refresh from project
        try:
            self.refresh()
        except Exception:
            pass


    # ----------------------------
    # : Auto-generated effect parameters (Qt)
    # ----------------------------

    def _clear_param_form(self):
        try:
            # remove all rows
            while self.params_form.rowCount() > 0:
                self.params_form.removeRow(0)
        except Exception:
            pass
        self._param_widgets = {}
        self._param_names = []

    def _active_layer_index(self) -> int:
        try:
            return int(self.list.currentRow())
        except Exception:
            return -1

    def _set_layer_param(self, layer_index: int, name: str, value):
        try:
            p, layers = self._project_layers()
            if layer_index < 0 or layer_index >= len(layers):
                return
            lay = dict(layers[layer_index] or {})
            lay = self._ensure_layer_ops(lay)
            ops = list(lay.get('operators') or [])
            oi = 0
            try:
                it = self.ops_list.currentItem()
                if it is not None:
                    oi = int(it.data(QtCore.Qt.ItemDataRole.UserRole))
            except Exception:
                oi = 0
            if oi < 0 or oi >= len(ops):
                oi = 0
            op = dict(ops[oi] or {})
            params = dict(op.get('params') or {})
            params[name] = value
            op['params'] = params
            ops[oi] = op
            lay['operators'] = ops
            # Keep legacy fields in sync with first operator
            lay = self._ensure_layer_ops(lay)
            # For now: if a Gain operator exists, apply it as a post-multiplier in preview (handled elsewhere).
            layers[layer_index] = lay
            p2 = dict(p)
            p2['layers'] = layers
            self._commit(p2)
        except Exception:
            return

    def _get_layer_param(self, layer_index: int, name: str, default=None):
        """Get a param from the currently-selected operator (fallback to legacy layer params)."""
        try:
            _p, layers = self._project_layers()
            if layer_index < 0 or layer_index >= len(layers):
                return default
            # Prefer selected operator params
            li, oi, op = self._current_operator()
            if li == layer_index and isinstance(op, dict):
                params = dict(op.get('params') or {})
                if name in params:
                    return params.get(name, default)
            # Fallback: legacy layer params
            lay = layers[layer_index] or {}
            params = (lay.get('params') or {})
            return params.get(name, default)
        except Exception:
            return default

    def _build_param_controls(self, layer_index: int):
        # Determine selected operator uses list
        p, layers = self._project_layers()
        if layer_index < 0 or layer_index >= len(layers):
            self._clear_param_form()
            self._params_hint.setText("(Select a layer to edit its parameters)")
            return

        lay = dict(layers[layer_index] or {})
        lay = self._ensure_layer_ops(lay)
        layers[layer_index] = lay

        # Current operator
        try:
            op_index = 0
            try:
                it = self.ops_list.currentItem()
                if it is not None:
                    op_index = int(it.data(QtCore.Qt.ItemDataRole.UserRole))
            except Exception:
                op_index = 0
        except Exception:
            op_index = 0
        ops = list(lay.get('operators') or [])
        if op_index < 0 or op_index >= len(ops):
            op_index = 0
        op = ops[op_index] if ops else {'type': str(lay.get('behavior') or 'solid'), 'params': dict(lay.get('params') or {})}
        op_type = str((op or {}).get('type') or 'solid').lower().strip()

        # Cache key includes operator type+index
        cache_key = f"{op_type}:{op_index}"
        if self._param_layer_index == layer_index and self._param_behavior_key == cache_key and self._param_widgets:
            self._sync_param_values(layer_index)
            return

        # Determine uses list
        uses = []
        # Base operator (index 0) maps to a shipped effect behavior key.
        if int(op_index) == 0:
            try:
                eff = get_effect(str(op_type))
                uses = list(getattr(eff, 'uses', []) or [])
            except Exception:
                uses = []
            if not uses and str(op_type) in self.OP_CATALOG:
                uses = list((self.OP_CATALOG.get(str(op_type)) or {}).get('uses') or [])
        else:
            uses = list((self.OP_CATALOG.get(str(op_type)) or {}).get('uses') or [])

        self._clear_param_form()
        self._param_layer_index = layer_index
        self._param_behavior_key = cache_key
        self._param_names = uses[:]

        if not uses:
            self._params_hint.setText("(This operator has no editable parameters)")
            return

        # Friendly label
        title = str((self.OP_CATALOG.get(op_type) or {}).get('title') or op_type)
        self._params_hint.setText(f"Operator: {title}")

        # Create controls
        for pname in uses:
            meta = PARAMS.get(pname, None)
            if not meta:
                continue
            ptype = str(meta.get("type", "float"))
            label = str(meta.get("label") or pname)

            if ptype == "rgb":
                btn = QtWidgets.QPushButton()
                btn.setText("Choose…")
                btn.clicked.connect(lambda _=False, n=pname: self._pick_color(layer_index, n))
                sw = QtWidgets.QLabel()
                sw.setFixedSize(18, 18)
                sw.setFrameShape(QtWidgets.QFrame.Shape.Box)
                row = QtWidgets.QHBoxLayout()
                row.setSpacing(6)
                row.addWidget(sw)
                row.addWidget(btn, 1)
                w = QtWidgets.QWidget()
                w.setLayout(row)
                self.params_form.addRow(label, w)
                self._param_widgets[pname] = (("rgb", btn, sw), meta)

            elif ptype in ("float", "int"):
                mn = meta.get("min", 0.0)
                mx = meta.get("max", 1.0)
                try:
                    mn = float(mn)
                    mx = float(mx)
                except Exception:
                    mn, mx = 0.0, 1.0
                if mx <= mn:
                    mx = mn + 1.0

                slider = QtWidgets.QSlider(_ORI_H)
                slider.setRange(0, 1000)
                val_lbl = QtWidgets.QLabel("")
                val_lbl.setMinimumWidth(52)

                if ptype == "int":
                    spin = QtWidgets.QSpinBox()
                    spin.setRange(int(mn), int(mx))
                else:
                    spin = QtWidgets.QDoubleSpinBox()
                    spin.setDecimals(int(meta.get("decimals", 3) or 3))
                    spin.setSingleStep(float(meta.get("step", (mx-mn)/100.0) or 0.01))
                    spin.setRange(mn, mx)

                def _slider_to_value(v):
                    return mn + (mx - mn) * (float(v) / 1000.0)

                def _value_to_slider(val):
                    try:
                        val = float(val)
                    except Exception:
                        val = mn
                    t = 0.0 if (mx-mn) == 0 else (val - mn) / (mx - mn)
                    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                    return int(round(t * 1000))

                def _on_slider(v, n=pname, pt=ptype):
                    if self._suppress:
                        return
                    val = _slider_to_value(v)
                    if pt == "int":
                        val = int(round(val))
                    self._suppress = True
                    try:
                        spin.setValue(val)
                    finally:
                        self._suppress = False
                    val_lbl.setText(f"{val:.3f}" if pt != "int" else str(int(val)))
                    self._set_layer_param(layer_index, n, val)

                def _on_spin(v, n=pname, pt=ptype):
                    if self._suppress:
                        return
                    val = int(v) if pt == "int" else float(v)
                    self._suppress = True
                    try:
                        slider.setValue(_value_to_slider(val))
                    finally:
                        self._suppress = False
                    val_lbl.setText(f"{val:.3f}" if pt != "int" else str(int(val)))
                    self._set_layer_param(layer_index, n, val)

                slider.valueChanged.connect(_on_slider)
                spin.valueChanged.connect(_on_spin)

                row = QtWidgets.QHBoxLayout()
                row.setSpacing(6)
                row.addWidget(slider, 1)
                row.addWidget(spin)
                row.addWidget(val_lbl)
                w = QtWidgets.QWidget()
                w.setLayout(row)
                self.params_form.addRow(label, w)
                self._param_widgets[pname] = (("num", slider, spin, val_lbl, mn, mx, ptype), meta)

            elif ptype == "bool":
                cb = QtWidgets.QCheckBox()
                cb.stateChanged.connect(lambda _st, n=pname: self._on_bool_changed(layer_index, n))
                self.params_form.addRow(label, cb)
                self._param_widgets[pname] = (("bool", cb), meta)

            elif ptype == "enum":
                combo = QtWidgets.QComboBox()
                choices = meta.get("choices") or []
                try:
                    for c in choices:
                        combo.addItem(str(c))
                except Exception:
                    pass
                combo.currentTextChanged.connect(lambda v, n=pname: self._on_enum_changed(layer_index, n, v))
                self.params_form.addRow(label, combo)
                self._param_widgets[pname] = (("enum", combo), meta)

            elif ptype == "string":
                le = QtWidgets.QLineEdit()
                le.editingFinished.connect(lambda n=pname, w=le: self._on_string_changed(layer_index, n, w))
                self.params_form.addRow(label, le)
                self._param_widgets[pname] = (("string", le), meta)

        self._sync_param_values(layer_index)

    def _sync_param_values(self, layer_index: int):
        self._suppress = True
        try:
            for pname, (spec, meta) in (self._param_widgets or {}).items():
                kind = spec[0]
                default = meta.get("default")
                val = self._get_layer_param(layer_index, pname, default)
                if kind == "rgb":
                    _btn, sw = spec[1], spec[2]
                    try:
                        r,g,b = int(val[0])&255, int(val[1])&255, int(val[2])&255
                    except Exception:
                        r,g,b = 255,0,0
                    sw.setStyleSheet(f"background: rgb({r},{g},{b});")
                elif kind == "num":
                    slider, spin, val_lbl, mn, mx, ptype = spec[1], spec[2], spec[3], spec[4], spec[5], spec[6]
                    try:
                        if ptype == "int":
                            v = int(val)
                        else:
                            v = float(val)
                    except Exception:
                        v = float(meta.get("default", 0.0) or 0.0)
                    # map to slider
                    t = 0.0 if (mx-mn)==0 else (float(v)-mn)/(mx-mn)
                    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                    slider.setValue(int(round(t*1000)))
                    spin.setValue(v)
                    val_lbl.setText(f"{v:.3f}" if ptype != "int" else str(int(v)))
                elif kind == "bool":
                    cb = spec[1]
                    cb.setChecked(bool(val))
                elif kind == "enum":
                    combo = spec[1]
                    sval = "" if val is None else str(val)
                    ix = combo.findText(sval)
                    if ix >= 0:
                        combo.setCurrentIndex(ix)
                elif kind == "string":
                    le = spec[1]
                    le.setText("" if val is None else str(val))
        finally:
            self._suppress = False

    def _pick_color(self, layer_index: int, pname: str):
        cur = self._get_layer_param(layer_index, pname, (255,0,0))
        try:
            r,g,b = int(cur[0])&255, int(cur[1])&255, int(cur[2])&255
        except Exception:
            r,g,b = 255,0,0
        col = QtGui.QColor(r, g, b)
        chosen = QtWidgets.QColorDialog.getColor(col, self, "Choose Color")
        if not chosen.isValid():
            return
        rgb = [chosen.red(), chosen.green(), chosen.blue()]
        self._set_layer_param(layer_index, pname, rgb)
        self._sync_param_values(layer_index)

    def _on_bool_changed(self, layer_index: int, pname: str):
        if self._suppress:
            return
        spec, meta = self._param_widgets.get(pname, (None, None))
        if not spec:
            return
        cb = spec[1]
        self._set_layer_param(layer_index, pname, bool(cb.isChecked()))

    def _on_enum_changed(self, layer_index: int, pname: str, v: str):
        if self._suppress:
            return
        self._set_layer_param(layer_index, pname, str(v))

    def _on_string_changed(self, layer_index: int, pname: str, le: QtWidgets.QLineEdit):
        if self._suppress:
            return
        self._set_layer_param(layer_index, pname, str(le.text() or ""))



class OperatorsPanel(QtWidgets.QWidget):
    """Operators/PostFX.

    Sanity:
      - Operators are applied in preview (per-layer, pre-blend) via preview_engine.
      - Export depends on target runtime capabilities (gated + surfaced in Export tab).

    Contract:
      - project['layers'][i]['operators'] is a list of dicts: {'type': str, 'params': dict, ...}
      - operator[0] may mirror the layer behavior for compatibility with older schema paths.
    """

    OP_CATALOG = {
        'solid': {'title': 'Solid'},
        'gain':  {'title': 'Gain'},
        'gamma': {'title': 'Gamma'},
        'clamp': {'title': 'Clamp'},
        'posterize': {'title': 'Posterize'},
        'threshold': {'title': 'Threshold'},
        'invert': {'title': 'Invert'},
    }

    def __init__(self, app_core):
        super().__init__()
        # ( metadata-only banner)
        try:
            self._beta_note = QtWidgets.QLabel("Operators/PostFX: export/runtime supports Gain/Gamma/Posterize on FastLED targets; other targets may block export.")
            try:
                self._beta_note.setWordWrap(True)
            except Exception:
                pass
            try:
                self._beta_note.setStyleSheet("font-style: italic;")
            except Exception:
                pass
        except Exception:
            self._beta_note = None
        self.app_core = app_core
        outer = QtWidgets.QVBoxLayout(self)
        try:
            if self._beta_note is not None:
                outer.addWidget(self._beta_note)
        except Exception:
            pass
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # ( disable controls)
        try:
            for _nm in ['enable_cb','enabled_cb','apply_btn','run_btn','exec_btn']:
                try:
                    w = getattr(self, _nm, None)
                    if w is not None:
                        try:
                            w.setEnabled(False)
                        except Exception:
                            pass
                        try:
                            w.setToolTip('Metadata-only in this beta')
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        title = QtWidgets.QLabel('Operators (MVP)')
        title.setStyleSheet('font-weight:600;')
        outer.addWidget(title)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        self.combo = QtWidgets.QComboBox()
        # Offer only exportable operator kinds by default; legacy kinds may be added on refresh if present in the project.
        try:
            from export.exportable_surface import OPERATORS_KINDS_EXPORTABLE
            _kinds = list(OPERATORS_KINDS_EXPORTABLE)
        except Exception:
            _kinds = ['gain', 'gamma', 'posterize']
        for _k in _kinds:
            try:
                self.combo.addItem(str(_k))
            except Exception:
                pass
        row.addWidget(self.combo, 1)

        self.btn_add = QtWidgets.QPushButton('Add')
        self.btn_remove = QtWidgets.QPushButton('Remove')
        self.btn_up = QtWidgets.QPushButton('Up')
        self.btn_down = QtWidgets.QPushButton('Down')
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_remove)
        row.addWidget(self.btn_up)
        row.addWidget(self.btn_down)
        outer.addLayout(row)

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        try:
            self.list.itemChanged.connect(self._on_list_item_changed)
        except Exception:
            pass
        outer.addWidget(self.list, 1)
        # Optional per-operator mask targeting (Phase O3 MVP)
        
        # Per-operator targeting (Phase O3 MVP):
        # Apply operator to: All / Mask / Zone / Group
        trow = QtWidgets.QHBoxLayout()
        trow.setSpacing(6)
        trow.addWidget(QtWidgets.QLabel("Apply To:"), 0)

        self.op_target_kind = QtWidgets.QComboBox()
        self.op_target_kind.setToolTip("Choose where this operator applies: All, Mask, Zone, or Group.")
        self.op_target_kind.addItems(["All", "Layer Target", "Mask", "Zone", "Group"])
        self.op_target_kind.setMinimumWidth(110)
        trow.addWidget(self.op_target_kind, 0)

        self.op_target_key = QtWidgets.QComboBox()
        self.op_target_key.setToolTip("Select the specific Mask/Zone/Group key. (All = none)")
        self.op_target_key.setMinimumWidth(220)
        trow.addWidget(self.op_target_key, 1)

        self.btn_target_jump = QtWidgets.QPushButton("Edit Targets…")
        self.btn_target_jump.setToolTip("Go to Targets tab to edit Zones/Masks/Groups.")
        trow.addWidget(self.btn_target_jump, 0)

        outer.addLayout(trow, 0)
        try:
            self.list.currentRowChanged.connect(self._sync_target_from_selection)
        except Exception:
            pass
        try:
            self.op_target_kind.currentIndexChanged.connect(self._on_op_target_kind_changed)
            self.op_target_key.currentIndexChanged.connect(self._on_op_target_key_changed)
        except Exception:
            pass


        hint = QtWidgets.QLabel('Note: Operators runtime (Gain/Gamma/Posterize) is exportable on targets that declare supports_operators_runtime.\n'
                                'If export is blocked, switch target or remove preview-only operators.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color:#888; font-size:11px;')
        
        # Runtime support warnings (target capabilities)
        self._ops_warn = QtWidgets.QLabel("")
        try:
            self._ops_warn.setWordWrap(True)
            self._ops_warn.setStyleSheet("color:#b66; font-size:11px;")
        except Exception:
            pass
        outer.addWidget(self._ops_warn)

        # PostFX controls (exportable subset)
        pf_box = QtWidgets.QGroupBox("PostFX (exportable subset)")
        pf_form = QtWidgets.QFormLayout(pf_box)
        pf_form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.pf_trail = QtWidgets.QDoubleSpinBox(); self.pf_trail.setRange(0.0, 1.0); self.pf_trail.setSingleStep(0.05)
        self.pf_bleed = QtWidgets.QDoubleSpinBox(); self.pf_bleed.setRange(0.0, 1.0); self.pf_bleed.setSingleStep(0.05)
        self.pf_radius = QtWidgets.QSpinBox(); self.pf_radius.setRange(1, 2)

        pf_form.addRow("Trail amount", self.pf_trail)
        pf_form.addRow("Bleed amount", self.pf_bleed)
        pf_form.addRow("Bleed radius", self.pf_radius)

        self._postfx_warn = QtWidgets.QLabel("")
        try:
            self._postfx_warn.setWordWrap(True)
            self._postfx_warn.setStyleSheet("color:#b66; font-size:11px;")
        except Exception:
            pass
        pf_form.addRow(self._postfx_warn)

        outer.addWidget(pf_box)

        try:
            self.pf_trail.valueChanged.connect(self._on_postfx_changed)
            self.pf_bleed.valueChanged.connect(self._on_postfx_changed)
            self.pf_radius.valueChanged.connect(self._on_postfx_changed)
        except Exception:
            pass

        outer.addWidget(hint)

        try: self.btn_add.clicked.connect(self._add_op)
        except Exception: pass
        try: self.btn_remove.clicked.connect(self._remove_op)
        except Exception: pass
        try: self.btn_up.clicked.connect(lambda: self._move(-1))
        except Exception: pass
        try: self.btn_down.clicked.connect(lambda: self._move(+1))
        except Exception: pass

        # refresh periodically (safe, non-invasive)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(350)
        try: self._timer.timeout.connect(self.refresh)
        except Exception: pass
        self._timer.start()

        try:
            self.btn_target_jump.clicked.connect(lambda: getattr(self.app_core,'_nav_to_targets', None) or getattr(self.app_core,'_nav_to_panels', None)() if getattr(self.app_core,'_nav_to_targets', None) or getattr(self.app_core,'_nav_to_panels', None) is not None else None)
        except Exception:
            pass

        self.refresh()
        try:
            self._sync_target_from_selection()
        except Exception:
            pass

    def _commit(self, p2: dict):
        try:
            self.app_core.project = p2
        except Exception:
            try:
                self.app_core.set_project(p2)
            except Exception:
                return

    def _get_active_layer(self):
        try:
            p = self.app_core.project or {}
            layers = p.get('layers') or []
            ai = int(p.get('active_layer') or 0)
            if not isinstance(layers, list) or not (0 <= ai < len(layers)):
                return None, None, None
            return p, layers, ai
        except Exception:
            return None, None, None

    def _ops_and_offset_for_ui(self, L: dict):
        """Return (ops, offset) for Operators UI.

        Policy: operators[0] is the *base effect* operator (internal mirror of the layer behavior/effect).
        The Operators UI must hide this base operator and only show post-effect operators (Gain/Gamma/etc).

        Robustness notes:
        - Some projects store the base op as {'kind': ...} instead of {'type': ...}
        - Some projects do not persist layer['behavior'] reliably; in that case, op0 being an export-eligible
          behavior is the strongest signal that it is the base effect.
        """
        try:
            ops = L.get('operators')
            if not isinstance(ops, list) or not ops:
                return (ops if isinstance(ops, list) else []), 0

            # Known behavior ids (base effects). Keep in sync with export/parity eligible behaviors.
            # This is intentionally a small, fail-closed set.
            ELIGIBLE_BEHAVIORS = {
                'solid','chase','wipe','sparkle','scanner','fade','strobe','rainbow','bouncer'
            }

            beh = str(L.get('behavior') or L.get('effect') or '').strip().lower()
            op0 = ops[0] or {}
            try:
                t0 = str(op0.get('type') or op0.get('kind') or '').strip().lower()
            except Exception:
                t0 = ''

            # Hide the base effect operator when:
            #  - it matches the persisted behavior/effect id, OR
            #  - it is a known behavior id (even if layer['behavior'] is missing/legacy)
            if t0 and (t0 == beh or t0 in ELIGIBLE_BEHAVIORS):
                return ops, 1

            return ops, 0
        except Exception:
            return [], 0

    def refresh(self):
        try:
            p, layers, ai = self._get_active_layer()
            if p is None:
                return
            L = layers[ai] if isinstance(layers[ai], dict) else {}
            ops_all, _off = self._ops_and_offset_for_ui(L)
            self._ui_ops_offset = int(_off)
            ops_view = ops_all[self._ui_ops_offset:] if isinstance(ops_all, list) else []
            # Ensure combo includes any legacy operator types present in the project (back-compat)
            try:
                present = set()
                for i in range(self.combo.count()):
                    try: present.add(str(self.combo.itemText(i)))
                    except Exception: pass
                for op in (ops_all if isinstance(ops_all, list) else []):
                    try:
                        t = str((op or {}).get('type') or '')
                    except Exception:
                        t = ''
                    if t and (t not in present):
                        try:
                            self.combo.addItem(t)
                            present.add(t)
                        except Exception:
                            pass
            except Exception:
                pass

            # Sync PostFX controls from project (project-level)
            try:
                pf = (p.get('postfx') or {}) if isinstance(p.get('postfx'), dict) else {}
                try:
                    self.pf_trail.blockSignals(True); self.pf_bleed.blockSignals(True); self.pf_radius.blockSignals(True)
                except Exception:
                    pass
                try:
                    self.pf_trail.setValue(float(pf.get('trail_amount', 0.0) or 0.0))
                    self.pf_bleed.setValue(float(pf.get('bleed_amount', 0.0) or 0.0))
                    self.pf_radius.setValue(int(pf.get('bleed_radius', 1) or 1))
                except Exception:
                    pass
                try:
                    self.pf_trail.blockSignals(False); self.pf_bleed.blockSignals(False); self.pf_radius.blockSignals(False)
                except Exception:
                    pass
            except Exception:
                pass

            # Update warnings based on current target capabilities
            try:
                self._update_runtime_warnings(p)
            except Exception:
                pass

            # : preserve selection across refresh (operators are metadata-only; selection should not drop)
            try:
                _sel = int(self.list.currentRow()) if hasattr(self, 'list') else -1
            except Exception:
                _sel = -1
            self.list.blockSignals(True)
            self.list.clear()
            for op in ops_view:
                try:
                    t = str((op or {}).get('type') or '')
                except Exception:
                    t = ''
                it = QtWidgets.QListWidgetItem(t or '(unknown)')
                try:
                    it.setFlags(it.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                    en = True
                    try:
                        en = bool((op or {}).get('enabled', True))
                    except Exception:
                        en = True
                    it.setCheckState(QtCore.Qt.CheckState.Checked if en else QtCore.Qt.CheckState.Unchecked)
                except Exception:
                    pass
                self.list.addItem(it)
            self.list.blockSignals(False)
            try:
                if _sel >= 0 and self.list.count() > 0:
                    self.list.setCurrentRow(min(_sel, self.list.count()-1))
            except Exception:
                pass
            try:
                self._sync_target_from_selection()
            except Exception:
                pass
        except Exception:
            return

    def _on_list_item_changed(self, item):
        # Toggle operator enabled flag (preview runtime respects 'enabled')
        try:
            row = int(self.list.row(item))
        except Exception:
            return
        if row < 0:
            return
        try:
            p, layers, ai = self._get_active_layer()
            if p is None:
                return
            L = dict(layers[ai] or {})
            ops = L.get('operators')
            if not isinstance(ops, list):
                return
            off = int(getattr(self, '_ui_ops_offset', 0) or 0)
            oi = row + off
            if oi < 0 or oi >= len(ops):
                return
            op = dict(ops[oi] or {})
            en = (item.checkState() == QtCore.Qt.CheckState.Checked)
            op['enabled'] = bool(en)
            ops2 = list(ops)
            ops2[oi] = op
            L['operators'] = ops2
            layers2 = list(layers)
            layers2[ai] = L
            p2 = dict(p); p2['layers'] = layers2
            self._commit(p2)
        except Exception:
            return

    def _add_op(self):
        try:
            p, layers, ai = self._get_active_layer()
            if p is None:
                return
            L = dict(layers[ai] or {})
            ops = L.get('operators')
            if not isinstance(ops, list):
                ops = []
            k = str(self.combo.currentText() or 'solid')
            ops2 = list(ops) + [{'type': k, 'params': {}}]
            L['operators'] = ops2
            layers2 = list(layers)
            layers2[ai] = L
            p2 = dict(p); p2['layers'] = layers2
            self._commit(p2)
            self.refresh()
        except Exception:
            return

    def _remove_op(self):
        try:
            p, layers, ai = self._get_active_layer()
            if p is None:
                return
            row = int(self.list.currentRow())
            L = dict(layers[ai] or {})
            ops = L.get('operators')
            if not isinstance(ops, list) or not ops:
                return
            off = int(getattr(self, '_ui_ops_offset', 0) or 0)
            oi = row + off
            if oi < off or oi >= len(ops):
                return
            ops2 = list(ops)
            ops2.pop(oi)
            L['operators'] = ops2
            layers2 = list(layers)
            layers2[ai] = L
            p2 = dict(p); p2['layers'] = layers2
            self._commit(p2)
            self.refresh()
        except Exception:
            return

    def _move(self, delta: int):
        try:
            p, layers, ai = self._get_active_layer()
            if p is None:
                return
            row = int(self.list.currentRow())
            L = dict(layers[ai] or {})
            ops = L.get('operators')
            if not isinstance(ops, list) or len(ops) < 2:
                return
            off = int(getattr(self, '_ui_ops_offset', 0) or 0)
            oi = row + off
            if oi < off or oi >= len(ops):
                return
            new = oi + int(delta)
            if new < off or new >= len(ops):
                return
            ops2 = list(ops)
            ops2[oi], ops2[new] = ops2[new], ops2[oi]
            L['operators'] = ops2
            layers2 = list(layers)
            layers2[ai] = L
            p2 = dict(p); p2['layers'] = layers2
            self._commit(p2)
            self.list.setCurrentRow(new - off)
            self.refresh()
        except Exception:
            return


    def _on_postfx_changed(self, *_args):
        """Commit project-level postfx values (exportable subset)."""
        try:
            p = self.app_core.project or {}
            pf = dict((p.get('postfx') or {}) if isinstance(p.get('postfx'), dict) else {})
            pf['trail_amount'] = float(getattr(self, 'pf_trail').value())
            pf['bleed_amount'] = float(getattr(self, 'pf_bleed').value())
            # Exportable surface clamps radius to 1..2
            try:
                pf['bleed_radius'] = int(getattr(self, 'pf_radius').value())
            except Exception:
                pf['bleed_radius'] = 1
            p2 = dict(p); p2['postfx'] = pf
            self._commit(p2)
        except Exception:
            return

    def _update_runtime_warnings(self, project_dict):
        try:
            tid = self.app_core.get_export_target_id() if hasattr(self.app_core, 'get_export_target_id') else None
            caps = {}
            if tid:
                try:
                    t = load_target(str(tid))
                    caps = dict((t.meta or {}).get('capabilities') or {})
                except Exception:
                    caps = {}
            supports_ops = bool(caps.get('supports_operators_runtime', False))
            supports_pf = bool(caps.get('supports_postfx_runtime', False))

            # Operators warning: only if layer uses operators beyond the behavior mirroring
            ops_used = False
            try:
                p = project_dict or {}
                p_layers = p.get('layers') or []
                # only check active layer (cheap) if possible
                _p, layers, ai = self._get_active_layer()
                L = layers[ai] if _p is not None and isinstance(layers, list) and ai is not None and ai < len(layers) else None
                if isinstance(L, dict):
                    ops = L.get('operators')
                    if isinstance(ops, list) and len(ops) > 0:
                        # treat any operator dict as usage; export/runtime will still gate if unsupported
                        ops_used = any(bool((o or {}).get('enabled', True)) for o in ops)
            except Exception:
                ops_used = False

            if hasattr(self, '_ops_warn') and self._ops_warn is not None:
                if ops_used and not supports_ops:
                    self._ops_warn.setText("Warning: current export target does not support Operators runtime. Export will be blocked unless you switch targets or remove operators.")
                else:
                    self._ops_warn.setText("")

            # PostFX warning: if any enabled postfx value > 0 and target lacks runtime
            pf_used = False
            try:
                pf = (project_dict or {}).get('postfx') or {}
                pf_used = (float(pf.get('trail_amount', 0.0) or 0.0) > 0.0) or (float(pf.get('bleed_amount', 0.0) or 0.0) > 0.0)
            except Exception:
                pf_used = False

            if hasattr(self, '_postfx_warn') and self._postfx_warn is not None:
                if pf_used and not supports_pf:
                    self._postfx_warn.setText("Warning: current export target does not support PostFX runtime. Export will be blocked unless you switch targets or disable PostFX.")
                else:
                    self._postfx_warn.setText("")
        except Exception:
            return


    # NOTE: Legacy per-operator Gain slider UI was removed in .
    # Operators are edited via the unified "Effect Parameters" panel (which edits the selected operator).

def _jump_targets(self):
    fn = getattr(self.app_core, '_nav_to_targets', None) or getattr(self.app_core, '_nav_to_panels', None)
    if callable(fn):
        try:
            fn()
        except Exception:
            pass

def _get_target_keys(self, kind: str):
    p = getattr(self.app_core, 'project', None)
    p = p if isinstance(p, dict) else {}
    kind = (kind or '').lower().strip()
    if kind == 'mask':
        d = p.get('masks')
    elif kind == 'zone':
        d = p.get('zones')
    elif kind == 'group':
        d = p.get('groups')
    else:
        d = None
    if not isinstance(d, dict):
        return []
    keys = [str(k) for k in d.keys() if isinstance(k, str) and k.strip()]
    keys.sort()
    return keys

def _populate_target_key_combo(self):
    try:
        kind = str(self.op_target_kind.currentText() or 'All')
    except Exception:
        kind = 'All'
    kind_l = kind.lower().strip()
    self.op_target_key.blockSignals(True)
    try:
        self.op_target_key.clear()
        if kind_l == 'all':
            self.op_target_key.addItem("(All)")
            self.op_target_key.setEnabled(False)
        elif kind_l == 'layer':
            self.op_target_key.addItem("(Layer Target)")
            self.op_target_key.setEnabled(False)
        else:
            self.op_target_key.setEnabled(True)
            self.op_target_key.addItem("(None)")
            for k in self._get_target_keys(kind_l):
                self.op_target_key.addItem(k)
    finally:
        self.op_target_key.blockSignals(False)

def _current_operator_ref(self):
    try:
        p, layers, ai = self._get_active_layer()
        if p is None:
            return None
        L = layers[ai] if isinstance(layers[ai], dict) else {}
        ops = L.get('operators')
        if not isinstance(ops, list):
            return None
        ui = int(self.list.currentRow())
        off = int(getattr(self, '_ui_ops_offset', 0) or 0)
        oi = ui + off
        if oi < off or oi >= len(ops):
            return None
        return (p, layers, ai, oi, dict(ops[oi] or {}))
    except Exception:
        return None

def _sync_target_from_selection(self):
    ref = self._current_operator_ref()
    if not ref:
        return
    _p, _layers, _ai, _oi, op = ref
    # Backwards compat: op['mask'] implies target_kind=mask
    kind = (op.get('target_kind') or '').strip()
    key = (op.get('target_key') or '').strip()
    if not kind:
        mk = op.get('mask')
        if isinstance(mk, str) and mk.strip():
            kind = 'mask'
            key = mk.strip()
    if not kind:
        kind = 'all'
        key = ''
    kind = kind.lower().strip()
    # Set kind combo
    try:
        idx = {'all':0,'layer':1,'mask':2,'zone':3,'group':4}.get(kind, 0)
        self.op_target_kind.blockSignals(True)
        self.op_target_kind.setCurrentIndex(idx)
    finally:
        try: self.op_target_kind.blockSignals(False)
        except Exception: pass
    self._populate_target_key_combo()
    # Set key combo
    if kind == 'all':
        return
    try:
        self.op_target_key.blockSignals(True)
        if key:
            # find
            found = self.op_target_key.findText(key)
            if found >= 0:
                self.op_target_key.setCurrentIndex(found)
            else:
                self.op_target_key.setCurrentIndex(0)
        else:
            self.op_target_key.setCurrentIndex(0)
    finally:
        try: self.op_target_key.blockSignals(False)
        except Exception: pass

def _commit_operator_target(self, kind: str, key: str):
    ref = self._current_operator_ref()
    if not ref:
        return
    p, layers, ai, oi, op = ref
    kind_l = (kind or '').lower().strip()
    if kind_l in ('layer target','layer_target','layer'):
        kind_l = 'layer'
    key_s = (key or '').strip()
    if kind_l in ('', 'all'):
        op.pop('target_kind', None)
        op.pop('target_key', None)
        op.pop('mask', None)
    elif kind_l == 'layer':
        op['target_kind'] = 'layer'
        op.pop('target_key', None)
        op.pop('mask', None)
    else:
        op['target_kind'] = kind_l
        op['target_key'] = key_s if key_s and key_s.lower() not in ('(none)','none','(all)','all') else ''
        # Backwards compat for preview_engine: keep op['mask'] only when kind=mask
        if kind_l == 'mask':
            op['mask'] = op.get('target_key') or ''
        else:
            op.pop('mask', None)
    # write back
    try:
        L = dict(layers[ai] or {})
        ops = L.get('operators')
        if not isinstance(ops, list):
            return
        ops2 = list(ops)
        ops2[oi] = op
        L['operators'] = ops2
        layers2 = list(layers)
        layers2[ai] = L
        p2 = dict(p); p2['layers'] = layers2
        self._commit(p2)
    except Exception:
        return

def _on_op_target_kind_changed(self, _idx=0):
    self._populate_target_key_combo()
    try:
        kind = str(self.op_target_kind.currentText() or 'All')
    except Exception:
        kind = 'All'
    # reset key to none on kind change
    key = ''
    if kind.lower().strip() not in ('all','layer target','layer'):
        try:
            key = str(self.op_target_key.currentText() or '')
        except Exception:
            key = ''
    self._commit_operator_target(kind, key)

def _on_op_target_key_changed(self, _idx=0):
    try:
        kind = str(self.op_target_kind.currentText() or 'All')
    except Exception:
        kind = 'All'
    try:
        key = str(self.op_target_key.currentText() or '')
    except Exception:
        key = ''
    self._commit_operator_target(kind, key)


class EffectAuditPanel(QtWidgets.QWidget):
    """One-click effect audit so you can paste results without manual testing.

    Runs each registered effect on a single clean layer (operators disabled),
    renders a few frames, and reports whether the effect produces any non-black
    pixels, whether it is animated, and whether it threw an exception.

    Audio-dependent effects are skipped by default.
    """

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run Effect Audit")
        self.run_btn.setToolTip("Sweeps all effects (skipping audio) and produces a copy/paste report")
        top.addWidget(self.run_btn)

        self.include_audio = QtWidgets.QCheckBox("Include audio effects")
        self.include_audio.setChecked(False)
        top.addWidget(self.include_audio)

        top.addStretch(1)
        outer.addLayout(top)

        self.out = QtWidgets.QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText("Click 'Run Effect Audit' to generate a report…")
        outer.addWidget(self.out, 1)

        self.copy_btn = QtWidgets.QPushButton("Copy report")
        outer.addWidget(self.copy_btn)

        self.copy_btn.clicked.connect(self._copy)
        self.run_btn.clicked.connect(self._run)

    def _copy(self):
        try:
            QtWidgets.QApplication.clipboard().setText(self.out.toPlainText() or "")
        except Exception:
            pass

    def _run(self):
        self.run_btn.setEnabled(False)
        try:
            self.out.setPlainText("Running audit…\n")
        except Exception:
            pass

        try:
            report = self._run_audit(include_audio=bool(getattr(self.include_audio,'isChecked',lambda:False)()))
        except Exception as e:
            report = f"Effect audit failed: {type(e).__name__}: {e}"

        try:
            # persist to out/ for easy sharing
            from pathlib import Path
            root = Path(getattr(getattr(self.app_core, 'pm', None), 'root_dir', '.') or '.')
            p = root / 'out' / 'effect_audit_report.txt'
            p.parent.mkdir(exist_ok=True)
            p.write_text(report, encoding='utf-8')
        except Exception:
            pass

        try:
            self.out.setPlainText(report)
        except Exception:
            pass
        self.run_btn.setEnabled(True)

    def _run_audit(self, *, include_audio: bool=False) -> str:
        # Ensure effects are registered
        try:
            from behaviors import auto_load
            if hasattr(auto_load, 'register_all'):
                auto_load.register_all()
        except Exception:
            pass

        from behaviors.registry import REGISTRY
        from params.ensure import defaults_for

        # Snapshot current project so we can restore at end
        p0 = dict(self.app_core.project or {})

        # Build a clean single-layer project
        layout = dict((p0.get('layout') or {}) if isinstance(p0.get('layout'), dict) else {})
        if not layout:
            layout = {'shape': 'strip', 'num_leds': 575}

        keys = sorted(list(REGISTRY.keys()))

        # capability-driven classification for audio/support

        results = []
        try:
            for k in keys:
                kk = str(k)
                defn = REGISTRY.get(kk)
                caps = dict(getattr(defn, 'capabilities', {}) or {})
                # classify by capabilities
                if (not include_audio) and bool(caps.get('requires_audio', False)):
                    results.append((kk, 'SKIP(audio)', '', ''))
                    continue
                shape = str((layout or {}).get('shape','strip'))
                # Project layouts use 'cells' for matrix-style worlds. For audit capability
                # classification, treat 'cells' as matrix.
                if shape == 'cells':
                    shape = 'matrix'
                if shape == 'strip' and caps.get('supports_strip', True) is False:
                    results.append((kk, 'UNSUPPORTED(strip)', '', ''))
                    continue
                if shape == 'matrix' and caps.get('supports_matrix', True) is False:
                    results.append((kk, 'UNSUPPORTED(matrix)', '', ''))
                    continue

                uses = list(getattr(defn, 'uses', []) or [])
                params = defaults_for(uses)
                # Diagnostics overrides: make certain bursty effects deterministic/visible
                # so the audit reflects whether the renderer works (not whether a random
                # bucket happened to be dark).
                if kk in ('lightning',):
                    try:
                        params['density'] = 1.0
                    except Exception:
                        pass

                # NOTE: Engine schema uses 'effect' as the primary behavior key.
                # Keep 'behavior' too for backwards-compat snapshots.
                layer = {
                    'effect': kk,
                    'behavior': kk,
                    'opacity': 1.0,
                    'blend': 'over',
                    'params': params,
                    # no operators/postfx for audit (must validate effect renderer itself)
                    'operators': [],
                }

                # Seed deterministic non-zero "purpose_*" params so purpose-driven showcase effects
                # are visibly active during effect audit (audit project has no rules/variables).
                if isinstance(kk, str) and kk.startswith('purpose_') and isinstance(params, dict):
                    params.setdefault('purpose_i0', 42)
                    params.setdefault('purpose_i1', 7)
                    params.setdefault('purpose_f0', 0.75)
                    params.setdefault('purpose_f1', 0.35)
                    params.setdefault('purpose_f2', 0.15)
                # Build an isolated project for audit.
                #
                # IMPORTANT: do NOT inherit the user's current project rules/audio/variables
                # into the audit project. Rules can legitimately drive parameters to 0.0
                # (e.g. brightness) based on audio.* signals, which would make unrelated
                # effects appear BLANK during audit. The audit must validate the renderer
                # itself under deterministic defaults.
                p = {
                    'name': f"AUDIT:{kk}",
                    'schema_version': p0.get('schema_version', 0),
                    'layout': layout,
                    'layers': [layer],
                    'active_layer': 0,
                    # keep empty containers so engine code that expects keys stays happy
                    'zones': [],
                    'masks': {},
                    'groups': [],
                    'rules': [],
                    'rules_v6': [],
                    'variables': {},
                    'audio': {},
                    'export': {},
                    'ui': {},
                }

                # Apply project and rebuild preview engine
                self.app_core.project = p
                try:
                    if hasattr(self.app_core, '_rebuild_full_preview_engine'):
                        self.app_core._rebuild_full_preview_engine()
                except Exception:
                    pass

                eng = getattr(self.app_core, '_full_preview_engine', None)
                if eng is None:
                    _pe_err = getattr(self.app_core, '_full_preview_last_error', None)
                    _pe_trace = getattr(self.app_core, '_full_preview_last_trace', None)
                    if _pe_err:
                        return f"SKIP(full_preview_engine): {_pe_err}"
                    if _pe_trace:
                        return "SKIP(full_preview_engine): trace present"
                    return "SKIP(full_preview_engine): unavailable"
                    results.append((kk, 'NO_ENGINE', '', ''))
                    continue

                # Render a few frames
                frames = []
                errs = ''
                try:
                    # Sample across multiple "buckets" to correctly validate
                    # bursty/stochastic effects (e.g. lightning/confetti).
                    t0 = time.time()
                    for i in range(12):
                        tt = t0 + i * 0.10
                        try:
                            if include_audio:
                                # R3: audit uses engine-owned always-on audio (no audit-only injection).
                                try:
                                    svc = getattr(self.app_core, "audio_service", None)
                                    if svc is not None:
                                        # Ensure the preview engine reads from the canonical backend.
                                        if hasattr(svc, "backend"):
                                            eng.audio = svc.backend
                                        if hasattr(svc, "step"):
                                            svc.step(tt)
                                except Exception:
                                    pass
                            frames.append(list(eng.render_frame(tt)))
                        except Exception:
                            pass
                except Exception as e:
                    errs = f"{type(e).__name__}: {e}"

                if getattr(eng, 'last_error', None):
                    errs = str(getattr(eng, 'last_error', ''))

                if not frames:
                    results.append((kk, 'NO_FRAMES', '', errs))
                    continue

                def _lit(frame):
                    return sum(1 for (r,g,b) in frame if (int(r)|int(g)|int(b)) != 0)

                # NOTE: Some effects are intentionally "bursty" (e.g. lightning/confetti)
                # and may be fully dark on some frames. For diagnostics, treat an effect as
                # working if it lights *any* pixel in *any* sampled frame.
                lit_per_frame = [_lit(fr) for fr in frames]
                lit0 = lit_per_frame[0]
                litN = lit_per_frame[-1]
                lit_max = max(lit_per_frame) if lit_per_frame else 0

                # Animated if any frame differs from the first.
                animated = 'YES' if any(fr != frames[0] for fr in frames[1:]) else 'NO'

                # unique colors (rough)
                try:
                    uniq = len({(int(r)&255, int(g)&255, int(b)&255) for (r,g,b) in frames[-1]})
                except Exception:
                    uniq = 0

                status = 'OK' if lit_max > 0 else 'BLANK'
                results.append((kk, status, f"lit {lit0}->{litN}, uniq {uniq}, anim {animated}", errs))
        finally:
            # Restore original project
            try:
                self.app_core.project = p0
            except Exception:
                pass
            try:
                if hasattr(self.app_core, '_rebuild_full_preview_engine'):
                    self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass

        lines = []
        lines.append('=== EFFECT AUDIT REPORT ===')
        lines.append('Legend: OK=emits pixels, BLANK=no lit pixels, SKIP(audio)=skipped (audio required), UNSUPPORTED(*)=not supported on current layout, errors show exception')
        lines.append('')
        for (name, status, meta, err) in results:
            if err:
                lines.append(f"- {name} — {status} — {meta} — ERR: {err}")
            else:
                lines.append(f"- {name} — {status} — {meta}")
        return "\n".join(lines)


class DiagnosticsHubPanel(QtWidgets.QWidget):

    # --- Diagnostics: Target Resolution Matrix helpers (read-only) ---

    def _diag_get_target(self, op: dict):
        """Best-effort extract of target kind/ref across schema variants."""
        flags = []
        tk = None
        tr = None

        if isinstance(op, dict):
            # Explicit fields
            if ("target_kind" in op) or ("target_ref" in op) or ("target_key" in op):
                tk = op.get("target_kind") or op.get("target")
                tr = op.get("target_ref") or op.get("target_key") or op.get("target_id")
            # Legacy: nested dict
            if (tk is None and tr is None) and ("targeting" in op):
                t = op.get("targeting")
                if isinstance(t, dict):
                    tk = t.get("kind") or t.get("type")
                    tr = t.get("ref") or t.get("id") or t.get("name")
            # Legacy: 'target' can be dict or string
            if ("target" in op):
                t = op.get("target")
                if isinstance(t, dict):
                    tk = tk or (t.get("kind") or t.get("type"))
                    tr = tr or (t.get("ref") or t.get("id") or t.get("name"))
                elif isinstance(t, str):
                    if (not tr) and t.strip():
                        if ":" in t:
                            a,b = t.split(":",1)
                            tk = tk or a.strip()
                            tr = b.strip()
                        else:
                            tr = t.strip()

        tk = (str(tk).strip().lower() if tk is not None else "")
        tr = (str(tr).strip() if tr is not None else "")

        if tk in ("", "none", "null"):
            tk = "none"
        if tr in ("", "none", "null"):
            tr = ""

        if tk == "none" and tr:
            flags.append("MISSING_KIND")

        return tk, tr, flags

    def _diag_resolve_target_indices(self, pd: dict, op: dict, led_count: int):
        flags = []
        target_kind, target_ref, _f = self._diag_get_target(op)
        flags.extend(_f)

        if target_kind in ("", "none"):
            return ("none", target_ref, [], flags)

        if target_kind not in ("mask", "zone", "group"):
            flags.append(f"INVALID_KIND:{target_kind or '∅'}")
            return ("invalid", target_ref, [], flags)

        if not target_ref:
            flags.append("MISSING_REF")
            return (target_kind, "", [], flags)

        try:
            if target_kind == "mask":
                from app.masks_resolver import resolve_mask_to_indices
                idx = resolve_mask_to_indices(pd, target_ref, n=led_count)
            elif target_kind == "zone":
                z = (pd.get("zones") or {}).get(target_ref)
                if not z:
                    flags.append("MISSING_REF")
                    return ("zone", target_ref, [], flags)
                a = z.get("start", z.get("a", z.get("from")))
                b = z.get("end", z.get("b", z.get("to")))
                if a is None or b is None:
                    flags.append("ZONE_BAD_SHAPE")
                    return ("zone", target_ref, [], flags)
                a = int(a); b = int(b)
                lo, hi = (a, b) if a <= b else (b, a)
                idx = list(range(lo, hi + 1))
            else:
                g = (pd.get("groups") or {}).get(target_ref)
                if not g:
                    flags.append("MISSING_REF")
                    return ("group", target_ref, [], flags)
                raw = g.get("indices", g.get("members", []))
                idx = [int(v) for v in raw] if isinstance(raw, (list, tuple)) else []

            idx = sorted(set(int(i) for i in idx))
            if not idx:
                flags.append("EMPTY")
            return (target_kind, target_ref, idx, flags)
        except Exception as e:
            flags.append(f"EXC:{type(e).__name__}")
            return (target_kind, target_ref, [], flags)

    def _diag_split_oob(self, indices, led_count: int):
        inb, oob = [], []
        for i in indices:
            i = int(i)
            if 0 <= i < int(led_count):
                inb.append(i)
            else:
                oob.append(i)
        return inb, oob

    def _diag_sample(self, xs, limit: int = 10) -> str:
        if not xs:
            return "-"
        xs = list(xs)
        s = xs[:limit]
        tail = "" if len(xs) <= limit else f" …(+{len(xs)-limit})"
        return "[" + ", ".join(str(v) for v in s) + "]" + tail
    # --- end helpers ---

    """Whole-app health checks to reduce manual testing.

    Includes:
      - Project schema validation + structural diagnostics
      - Operator sanity checks (enabled/type/targets)
      - Effect audit (existing) summary, with optional audio inclusion
    """
    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        row = QtWidgets.QHBoxLayout()
        self.run_full_btn = QtWidgets.QPushButton("Run Full Health Check")
        self.run_full_btn.setToolTip("Runs project validation + operator sanity + effect audit summary")
        row.addWidget(self.run_full_btn)

        self.run_audit_btn = QtWidgets.QPushButton("Run Effect Audit (detail)")
        self.run_audit_btn.setToolTip("Runs the full effect audit and prints the detailed report")
        row.addWidget(self.run_audit_btn)

        self.include_audio = QtWidgets.QCheckBox("Include audio effects")
        self.include_audio.setChecked(False)
        row.addWidget(self.include_audio)

        row.addStretch(1)
        outer.addLayout(row)

        self.out = QtWidgets.QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText("Run a health check to generate a report…")
        outer.addWidget(self.out, 1)

        btnrow = QtWidgets.QHBoxLayout()
        self.copy_btn = QtWidgets.QPushButton("Copy report")
        btnrow.addWidget(self.copy_btn)
        btnrow.addStretch(1)
        outer.addLayout(btnrow)

        # Reuse the existing audit runner logic (no extra UI).
        self._audit_runner = EffectAuditPanel(self.app_core)

        self.copy_btn.clicked.connect(self._copy)
        self.run_full_btn.clicked.connect(self._run_full)
        self.run_audit_btn.clicked.connect(self._run_audit_detail)

    def _copy(self):
        try:
            QtWidgets.QApplication.clipboard().setText(self.out.toPlainText() or "")
        except Exception:
            pass

    def _get_project_dict(self):
        pd = None
        try:
            pm = getattr(self.app_core, "pm", None)
            if pm is not None:
                # common shapes
                if hasattr(pm, "project") and hasattr(pm.project, "to_dict"):
                    pd = pm.project.to_dict()
                elif hasattr(pm, "project") and isinstance(getattr(pm, "project", None), dict):
                    pd = pm.project
                elif hasattr(pm, "get_project_dict"):
                    pd = pm.get_project_dict()
        except Exception:
            pd = None
        if pd is None:
            try:
                pd = getattr(getattr(self.app_core, "project", None), "to_dict", lambda: None)()
            except Exception:
                pd = None
        if not isinstance(pd, dict):
            pd = {}
        return pd

    def _persist_report(self, text: str, fname: str):
        try:
            from pathlib import Path
            root = Path(getattr(getattr(self.app_core, 'pm', None), 'root_dir', '.') or '.')
            p = root / 'out' / fname
            p.parent.mkdir(exist_ok=True)
            p.write_text(text, encoding='utf-8')
        except Exception:
            pass

    def _run_full(self):
        self.run_full_btn.setEnabled(False)
        self.run_audit_btn.setEnabled(False)
        try:
            self.out.setPlainText("Running full health check…\n")
        except Exception:
            pass

        try:
            pd = self._get_project_dict()
            lines = []
            from datetime import datetime, timezone
            lines.append("=== HEALTH CHECK REPORT ===")
            lines.append(f"timestamp: {datetime.now(timezone.utc).isoformat()}Z")
            try:
                import sys
                from pathlib import Path
                lines.append(f"run_argv0: {Path(sys.argv[0]).resolve()}")
                lines.append(f"run_root: {Path(__file__).resolve().parents[1]}")
                lines.append(f"run_root: {Path(__file__).resolve().parents[1]}")
                lines.append(f"build_id: {BUILD_ID}")
            except Exception:
                pass
            lines.append("")

            # ---- schema/project validation ----
            try:
                from app.project_validation import validate_project
                snap = validate_project(pd)
                errs = snap.get("errors") or []
                warns = snap.get("warnings") or []
                lines.append("== Project Validation ==")
                lines.append(f"errors: {len(errs)}")
                for e in errs[:50]:
                    lines.append(f"  - {e}")
                if len(errs) > 50:
                    lines.append(f"  … ({len(errs)-50} more)")
                lines.append(f"warnings: {len(warns)}")
                for w in warns[:50]:
                    lines.append(f"  - {w}")
                if len(warns) > 50:
                    lines.append(f"  … ({len(warns)-50} more)")
                lines.append("")
            except Exception as e:
                lines.append("== Project Validation ==")
                lines.append(f"FAILED: {type(e).__name__}: {e}")
                lines.append("")

            # ---- structural diagnostics (zones/masks/groups) ----
            try:
                from app.project_diagnostics import diagnose_project
                d = diagnose_project(pd)
                inv = d.get("invalid") or []
                dang = d.get("dangling") or []
                emp = d.get("empty") or []
                lines.append("== Structural Diagnostics (Zones/Masks/Groups) ==")
                lines.append(f"invalid: {len(inv)}")
                for x in inv[:50]:
                    lines.append(f"  - {x}")
                if len(inv) > 50:
                    lines.append(f"  … ({len(inv)-50} more)")
                lines.append(f"dangling: {len(dang)}")
                for x in dang[:50]:
                    lines.append(f"  - {x}")
                if len(dang) > 50:
                    lines.append(f"  … ({len(dang)-50} more)")
                lines.append(f"empty: {len(emp)}")
                for x in emp[:50]:
                    lines.append(f"  - {x}")
                if len(emp) > 50:
                    lines.append(f"  … ({len(emp)-50} more)")
                lines.append("")
            except Exception as e:
                lines.append("== Structural Diagnostics (Zones/Masks/Groups) ==")
                lines.append(f"FAILED: {type(e).__name__}: {e}")
                lines.append("")


            # ---- audio snapshot + signal consumers (engine truth) ----
            try:
                lines.append("== Audio Snapshot ==")
                # Prefer engine-owned audio service (Release R1)
                svc = getattr(self.app_core, "audio_service", None)
                mode = getattr(svc, "mode", None) if svc is not None else None
                backend = getattr(svc, "backend_name", None) if svc is not None else None
                status = getattr(svc, "status", None) if svc is not None else None
                lines.append(f"mode: {mode or 'unknown'}")
                lines.append(f"backend: {backend or (type(getattr(svc,'backend',None)).__name__ if svc is not None else 'unknown')}")
                lines.append(f"status: {status or 'unknown'}")

                # Pull current audio_state dict (energy, mono0..6, l0..6, r0..6)
                astate = None
                try:
                    if svc is not None and hasattr(svc, "get_audio_state_dict"):
                        astate = svc.get_audio_state_dict()
                except Exception:
                    astate = None

                # Also report SignalBus snapshot values (authoritative for rules)
                sb = getattr(self.app_core, "signal_bus", None)
                snap = sb.snapshot() if sb is not None and hasattr(sb, "snapshot") else None
                sig = snap.signals if snap is not None else {}
                try:
                    lines.append(f"signal_bus.frame: {getattr(snap,'frame',0)}")
                except Exception:
                    pass

                # Minimal numeric summary
                try:
                    lines.append(f"audio.energy: {float(sig.get('audio.energy', 0.0)):.3f}")
                except Exception:
                    lines.append(f"audio.energy: {sig.get('audio.energy', 0.0)}")
                try:
                    # Show mono bands compactly
                    mono = sig.get("audio.mono")
                    if isinstance(mono, list) and len(mono) == 7:
                        lines.append("audio.mono: [" + ", ".join(f"{float(x):.2f}" for x in mono) + "]")
                except Exception:
                    pass

                # Consumers (best-effort): layers with audio-ish effects + rules that reference audio.*
                layers = pd.get("layers") or []
                audio_layers = []
                for li, ld in enumerate(layers if isinstance(layers, list) else []):
                    if not isinstance(ld, dict):
                        continue
                    eff = str(ld.get("effect") or ld.get("behavior") or ld.get("type") or "").strip().lower()
                    if "audio" in eff:
                        audio_layers.append(f"layer[{li}] {ld.get('name','(unnamed)')} -> {eff}")
                if audio_layers:
                    lines.append("consumers.layers:")
                    for x in audio_layers[:100]:
                        lines.append(f"  - {x}")
                    if len(audio_layers) > 100:
                        lines.append(f"  … ({len(audio_layers)-100} more)")
                else:
                    lines.append("consumers.layers: 0")

                # Rules_v6 referenced signals + invalid refs
                refs = set()
                def _walk(node):
                    if isinstance(node, dict):
                        if str(node.get("src","")) == "signal" and node.get("signal"):
                            refs.add(str(node.get("signal")))
                        for v in node.values():
                            _walk(v)
                    elif isinstance(node, list):
                        for v in node:
                            _walk(v)
                _walk(pd.get("rules_v6") or [])
                if refs:
                    bad = [r for r in sorted(refs) if r not in sig]
                    audio_refs = [r for r in sorted(refs) if r.startswith("audio.")]
                    lines.append(f"rules.signals_used: {len(refs)}")
                    if audio_refs:
                        lines.append("consumers.rules.audio:")
                        for r in audio_refs[:80]:
                            lines.append(f"  - {r}")
                        if len(audio_refs) > 80:
                            lines.append(f"  … ({len(audio_refs)-80} more)")
                    if bad:
                        lines.append(f"invalid_signal_refs: {len(bad)}")
                        for r in bad[:80]:
                            lines.append(f"  - {r}")
                        if len(bad) > 80:
                            lines.append(f"  … ({len(bad)-80} more)")
                    else:
                        lines.append("invalid_signal_refs: 0")
                else:
                    lines.append("rules.signals_used: 0")
                    lines.append("invalid_signal_refs: 0")

                lines.append("")
            except Exception as e:
                lines.append("== Audio Snapshot ==")
                lines.append(f"FAILED: {type(e).__name__}: {e}")
                lines.append("")
            # ---- operator sanity ----
            try:
                zones = pd.get("zones") or {}
                groups = pd.get("groups") or {}
                masks = pd.get("masks") or {}
                layers = pd.get("layers") or []
                issues = []
                op_count = 0
                enabled_count = 0
                for li, layer in enumerate(layers if isinstance(layers, list) else []):
                    if not isinstance(layer, dict):
                        issues.append(f"layer[{li}] not dict")
                        continue
                    ops = layer.get("operators") or []
                    if not isinstance(ops, list):
                        continue
                    for oi, op in enumerate(ops):
                        if not isinstance(op, dict):
                            issues.append(f"layer[{li}].operators[{oi}] not dict")
                            continue
                        op_count += 1
                        if bool(op.get("enabled", True)):
                            enabled_count += 1
                        otype = (op.get("type") or op.get("kind") or "").strip()
                        if not otype:
                            issues.append(f"layer[{li}].operators[{oi}] missing type/kind")
                        params = op.get("params")
                        if params is not None and not isinstance(params, dict):
                            issues.append(f"layer[{li}].operators[{oi}].params not dict")
                        tk = (op.get("target_kind") or "").lower().strip()
                        kk = (op.get("target_key") or "").strip()
                        if tk in ("mask","zone","group") and kk:
                            if tk == "mask" and (not isinstance(masks, dict) or kk not in masks):
                                issues.append(f"layer[{li}].operators[{oi}] targets missing mask '{kk}'")
                            if tk == "zone" and (not isinstance(zones, dict) or kk not in zones):
                                issues.append(f"layer[{li}].operators[{oi}] targets missing zone '{kk}'")
                            if tk == "group" and (not isinstance(groups, dict) or kk not in groups):
                                issues.append(f"layer[{li}].operators[{oi}] targets missing group '{kk}'")
                lines.append("== Operators Sanity ==")
                lines.append(f"operators_total: {op_count} (enabled: {enabled_count})")
                lines.append(f"issues: {len(issues)}")
                for it in issues[:100]:
                    lines.append(f"  - {it}")
                if len(issues) > 100:
                    lines.append(f"  … ({len(issues)-100} more)")
                lines.append("")
            except Exception as e:
                lines.append("== Operators Sanity ==")
                lines.append(f"FAILED: {type(e).__name__}: {e}")
                lines.append("")

            # ---- effect audit summary ----
            try:
                import re
                rep = self._audit_runner._run_audit(include_audio=True)
                if rep.startswith('SKIP('):
                    # Preserve SKIP reason verbatim and don't pretend OK/BLANK counts mean anything.
                    lines.append(rep)
                    rep = ''
                ok = len(re.findall(r"— OK —", rep))
                blank = len(re.findall(r"— BLANK —", rep))
                skip = len(re.findall(r"— SKIP\(audio\)", rep))
                unsup = len(re.findall(r"— UNSUPPORTED\(", rep))
                lines.append("== Effect Audit Summary ==")
                lines.append(f"OK: {ok}   BLANK: {blank}   SKIP(audio): {skip}   UNSUPPORTED: {unsup}")
                # list the non-OK entries (names only) to keep report short
                bad = []
                for ln in rep.splitlines():
                    if "— BLANK —" in ln or "— SKIP(audio)" in ln or "— UNSUPPORTED(" in ln:
                        bad.append(ln.strip())
                if bad:
                    lines.append("non-OK:")
                    for ln in bad[:200]:
                        lines.append(f"  {ln}")
                    if len(bad) > 200:
                        lines.append(f"  … ({len(bad)-200} more)")
                lines.append("")
            except Exception as e:
                lines.append("== Effect Audit Summary ==")
                lines.append(f"FAILED: {type(e).__name__}: {e}")
                lines.append("")

            # ---- Targeting Diagnostics (Zones/Masks/Groups resolution + safety) ----
            try:
                tgt_results = []
                def _tok(name, msg=""): tgt_results.append((name, "PASS", msg))
                def _tfail(name, msg=""): tgt_results.append((name, "FAIL", msg))

                n = None
                try:
                    lay = (pd or {}).get("layout") or {}
                    n = lay.get("led_count") or lay.get("n") or (pd or {}).get("led_count") or None
                    if n is None:
                        # try nested previews
                        n = ((pd or {}).get("preview") or {}).get("led_count")
                    n = int(n) if n is not None else 575
                except Exception:
                    n = 575

                zones = (pd or {}).get("zones")
                groups = (pd or {}).get("groups")
                masks = (pd or {}).get("masks") or {}

                # normalize zones/groups into accessors
                def _get_zone(ref):
                    if zones is None: return None
                    if isinstance(zones, list):
                        try:
                            r = int(ref)
                            return zones[r] if 0 <= r < len(zones) else None
                        except Exception:
                            return None
                    if isinstance(zones, dict):
                        return zones.get(str(ref))
                    return None

                def _get_group(ref):
                    if groups is None: return None
                    if isinstance(groups, list):
                        try:
                            r = int(ref)
                            return groups[r] if 0 <= r < len(groups) else None
                        except Exception:
                            return None
                    if isinstance(groups, dict):
                        return groups.get(str(ref))
                    return None

                
                # ---- export dry-run diagnostics ----
                try:
                    from pathlib import Path
                    lines.append("")
                    lines.append("== Export Diagnostics ==")
                    root = Path(__file__).resolve().parents[1]
                    outdir = root / "out" / "diagnostics_exports"
                    try:
                        outdir.mkdir(parents=True, exist_ok=True)
                    except Exception:
                        pass

                    try:
                        from export.arduino_exporter import export_project_validated, validate_export_text
                        out_ino = outdir / "diagnostics_export.ino"
                        p = export_project_validated(project=pd, out_path=out_ino)
                        try:
                            code = Path(p).read_text(encoding="utf-8", errors="ignore")
                            validate_export_text(code)
                            lines.append(f"arduino_export: PASS ({p})")
                            lines.append("template_tokens: PASS")
                        except Exception as vex:
                            lines.append(f"arduino_export: PASS ({p})")
                            lines.append(f"template_tokens: FAIL — {type(vex).__name__}: {vex}")
                    except Exception as ex:
                        lines.append(f"arduino_export: BLOCKED — {type(ex).__name__}: {ex}")
                except Exception as ex:
                    lines.append("")
                    lines.append("== Export Diagnostics ==")
                    lines.append(f"FAILED: {type(ex).__name__}: {ex}")


                # --- Export Impact Report (per target pack) ---
                try:
                    lines.append("")
                    lines.append("== EXPORT IMPACT REPORT ==")

                    target_id = getattr(self.app_core, "export_target_id", None) or "arduino_export"
                    lines.append(f"target_id={target_id}")

                    pd_layers = (pd.get("layers") or [])
                    present_behaviors = []
                    present_ops = []
                    for li, layer in enumerate(pd_layers):
                        b = str(layer.get("effect") or layer.get("behavior") or "∅")
                        present_behaviors.append(b)
                        ops = (layer.get("operators") or [])
                        for oi, op in enumerate(ops):
                            if isinstance(op, dict):
                                present_ops.append(str(op.get("type") or op.get("kind") or "∅"))
                            else:
                                present_ops.append("BAD_SHAPE")

                    lines.append(f"layers={len(pd_layers)} behaviors={sorted(set(present_behaviors))}")
                    lines.append(f"operators_present={sorted(set(present_ops))}")

                    # Best-effort parity summary if available
                    ps = None
                    try:
                        from export.parity_summary import build_parity_summary
                        ps = build_parity_summary(pd, target_id=target_id)
                    except Exception:
                        ps = None

                    if isinstance(ps, dict):
                        status = ps.get("status") or ps.get("overall_status") or "∅"
                        lines.append(f"parity_summary_status={status}")
                        lay = ps.get("layers") or []
                        if lay:
                            for ent in lay:
                                if not ent.get("enabled", True):
                                    continue
                                li = ent.get("index")
                                st = ent.get("status") or ent.get("eligibility") or "∅"
                                reason = ent.get("reason") or ent.get("block_reason") or ""
                                lines.append(f"  - L{li}: {st}" + (f" — {reason}" if reason else ""))

                            # Action hint: if export is blocked only due to preview-only layers,
                            # print an explicit instruction.
                            try:
                                if str(status).upper() == "BLOCKED":
                                    preview_only = []
                                    for ent in lay:
                                        if not ent.get("enabled", True):
                                            continue
                                        # Preview-only utility layers are intentionally ignored for export.
                                        if not ent.get("export_participates", True):
                                            continue
                                        st2 = str(ent.get("status") or ent.get("eligibility") or "")
                                        if st2.lower().startswith("preview-only"):
                                            li2 = ent.get("index")
                                            eff2 = ent.get("effect") or ent.get("behavior") or ent.get("name") or ""
                                            preview_only.append((li2, str(eff2)))
                                    if preview_only:
                                        items = ", ".join([f"L{li3}" + (f"({eff3})" if eff3 else "") for li3, eff3 in preview_only])
                                        lines.append(f"export_action: Disable preview-only layers to export: {items}")
                            except Exception:
                                pass
                    else:
                        lines.append("parity_summary: ∅ (not available)")

                except Exception as e:
                    lines.append("")
                    lines.append("== EXPORT IMPACT REPORT ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end export impact ---

# basic zone/group existence + non-empty resolution
                try:
                    zcount = len(zones) if isinstance(zones, list) else (len(zones) if isinstance(zones, dict) else 0)
                    gcount = len(groups) if isinstance(groups, list) else (len(groups) if isinstance(groups, dict) else 0)
                    lines.append("== Targeting Diagnostics ==")
                    lines.append(f"zones: {zcount}   groups: {gcount}   masks: {len(masks) if isinstance(masks, dict) else 0}")
                except Exception:
                    lines.append("== Targeting Diagnostics ==")

                # Resolve one representative zone/group if present
                if isinstance(zones, list) and len(zones) > 0:
                    z = zones[0]
                    zkey = None
                    try:
                        if isinstance(z, dict):
                            zkey = z.get("key") or z.get("id") or z.get("name")
                    except Exception:
                        zkey = None
                    raw_s = (z.get("start") if isinstance(z, dict) else getattr(z, "start", None))
                    raw_e = (z.get("end") if isinstance(z, dict) else getattr(z, "end", None))
                    try:
                        s = int(raw_s if raw_s is not None else 0)
                        e = int(raw_e if raw_e is not None else -1)
                        if e >= s:
                            cnt = max(0, min(n-1, e) - max(0, min(n-1, s)) + 1)
                            if cnt > 0:
                                _tok("TARGET_ZONE_RESOLVES_NONEMPTY", f"count={cnt} (zone={zkey})")
                            else:
                                _tfail("TARGET_ZONE_RESOLVES_NONEMPTY", f"count={cnt} (zone={zkey})")
                        else:
                            _tfail("TARGET_ZONE_RESOLVES_NONEMPTY", f"invalid range (zone={zkey} start={raw_s} end={raw_e})")
                    except Exception as ex:
                        _tfail("TARGET_ZONE_RESOLVES_NONEMPTY", f"{type(ex).__name__}: {ex} (zone={zkey} start={raw_s} end={raw_e})")
                elif isinstance(zones, dict) and len(zones) > 0:
                    k = next(iter(zones.keys()))
                    z = zones.get(k)
                    s = (z.get("start") if isinstance(z, dict) else getattr(z, "start", 0)) or 0
                    e = (z.get("end") if isinstance(z, dict) else getattr(z, "end", -1))
                    try:
                        s = int(s); e = int(e)
                        cnt = max(0, min(n-1, e) - max(0, min(n-1, s)) + 1) if e >= s else 0
                        if cnt > 0:
                            _tok("TARGET_ZONE_RESOLVES_NONEMPTY", f"key={k} count={cnt}")
                        else:
                            _tfail("TARGET_ZONE_RESOLVES_NONEMPTY", f"key={k} count={cnt}")
                    except Exception as ex:
                        _tfail("TARGET_ZONE_RESOLVES_NONEMPTY", f"{type(ex).__name__}: {ex}")
                else:
                    _tok("TARGET_ZONE_RESOLVES_NONEMPTY", "SKIP (no zones)")

                if isinstance(groups, list) and len(groups) > 0:
                    g = groups[0]
                    idxs = g.get("indices") if isinstance(g, dict) else getattr(g, "indices", None)
                    cnt = len(idxs) if isinstance(idxs, list) else 0
                    if cnt > 0:
                        _tok("TARGET_GROUP_RESOLVES_NONEMPTY", f"count={cnt}")
                    else:
                        _tfail("TARGET_GROUP_RESOLVES_NONEMPTY", f"count={cnt}")
                elif isinstance(groups, dict) and len(groups) > 0:
                    k = next(iter(groups.keys()))
                    g = groups.get(k)
                    idxs = g.get("indices") if isinstance(g, dict) else getattr(g, "indices", None)
                    cnt = len(idxs) if isinstance(idxs, list) else 0
                    if cnt > 0:
                        _tok("TARGET_GROUP_RESOLVES_NONEMPTY", f"key={k} count={cnt}")
                    else:
                        _tfail("TARGET_GROUP_RESOLVES_NONEMPTY", f"key={k} count={cnt}")
                else:
                    _tok("TARGET_GROUP_RESOLVES_NONEMPTY", "SKIP (no groups)")

                # Masks resolver test (Phase A1 masks)
                try:
                    if isinstance(masks, dict) and len(masks) > 0:
                        from app.masks_resolver import resolve_mask_to_indices
                        k = next(iter(masks.keys()))
                        idxs = resolve_mask_to_indices(pd, k, n=n)
                        if isinstance(idxs, set) and len(idxs) > 0:
                            _tok("TARGET_MASK_RESOLVES_NONEMPTY", f"key={k} count={len(idxs)}")
                        else:
                            _tfail("TARGET_MASK_RESOLVES_NONEMPTY", f"key={k} count=0")
                    else:
                        _tok("TARGET_MASK_RESOLVES_NONEMPTY", "SKIP (no masks)")
                except Exception as ex:
                    _tfail("TARGET_MASK_RESOLVES_NONEMPTY", f"{type(ex).__name__}: {ex}")

                # Operator target reference sanity (no dangling/empty targets)
                try:
                    layers = (pd or {}).get("layers") or []
                    bad = 0
                    checked = 0
                    for L in layers:
                        ops = (L.get("operators") if isinstance(L, dict) else getattr(L, "operators", None)) or []
                        for j, op in enumerate(ops):
                            if not isinstance(op, dict): 
                                continue
                            # skip base op (slot 0) — internal
                            if j == 0:
                                continue
                            if op.get("enabled", True) is False:
                                continue
                            tk = str(op.get("target_kind") or op.get("target") or "all").lower().strip()
                            ref = op.get("target_key", None)
                            if ref is None:
                                ref = op.get("target_ref", None)
                            if tk in ("", "all", "layer"):
                                continue
                            checked += 1
                            ok = True
                            if tk == "zone":
                                z = _get_zone(ref)
                                if z is None:
                                    ok = False
                                else:
                                    s = (z.get("start") if isinstance(z, dict) else getattr(z, "start", 0)) or 0
                                    e = (z.get("end") if isinstance(z, dict) else getattr(z, "end", -1))
                                    try:
                                        s = int(s); e = int(e)
                                        ok = (e >= s)
                                    except Exception:
                                        ok = False
                            elif tk == "group":
                                g = _get_group(ref)
                                if g is None:
                                    ok = False
                                else:
                                    idxs = g.get("indices") if isinstance(g, dict) else getattr(g, "indices", None)
                                    ok = isinstance(idxs, list) and len(idxs) > 0
                            elif tk == "mask":
                                if not isinstance(masks, dict) or str(ref) not in masks:
                                    ok = False
                            else:
                                # unknown target kind: treat as issue
                                ok = False
                            if not ok:
                                bad += 1
                    if checked == 0:
                        _tok("OPERATORS_TARGET_SANITY", "SKIP (no targeted operators)")
                    elif bad == 0:
                        _tok("OPERATORS_TARGET_SANITY", f"checked={checked}")
                    else:
                        _tfail("OPERATORS_TARGET_SANITY", f"bad={bad} checked={checked}")
                except Exception as ex:
                    _tfail("OPERATORS_TARGET_SANITY", f"{type(ex).__name__}: {ex}")

                fails = [r for r in tgt_results if r[1] != "PASS"]
                lines.append(f"tests: {len(tgt_results)}   failed: {len(fails)}")
                for name, st, msg in tgt_results:
                    if st == "PASS":
                        lines.append(f"  - {name}: PASS" + (f" ({msg})" if msg else ""))
                    else:
                        lines.append(f"  - {name}: FAIL — {msg}")
                lines.append("")
            except Exception as e:
                lines.append("== Targeting Diagnostics ==")
                lines.append(f"FAILED: {type(e).__name__}: {e}")
                lines.append("")


            # ---- UI Action Diagnostics (core workflows) ----
            try:
                ui_results = []
                def _ok(name): ui_results.append((name, "PASS", ""))
                def _fail(name, msg): ui_results.append((name, "FAIL", msg))

                # 1) Effect change resets params (no stale carry-over)
                try:
                    # Pick two distinct shipped effects if available.
                    keys = []
                    try:
                        from behaviors.registry import list_effect_keys
                        keys = [k for k in (list_effect_keys() or []) if isinstance(k, str)]
                    except Exception:
                        keys = []
                    # Prefer common ones.
                    cand = [k for k in ("chase","rainbow","sparkle","solid","gradient","wave") if k in keys]
                    if len(cand) < 2 and len(keys) >= 2:
                        cand = keys[:2]
                    if len(cand) >= 2:
                        k1, k2 = cand[0], cand[1]
                        uses1 = []
                        uses2 = []
                        try:
                            d1 = get_effect(k1); uses1 = list(getattr(d1, "uses", []) or [])
                        except Exception:
                            uses1 = []
                        try:
                            d2 = get_effect(k2); uses2 = list(getattr(d2, "uses", []) or [])
                        except Exception:
                            uses2 = []
                        p1 = defaults_for(uses1)
                        p2 = defaults_for(uses2)
                        # simulate layer param carry-over bug: start with p1 + a junk key, then switch to k2
                        L = {"behavior": k1, "params": dict(p1)}
                        L["params"]["__junk_prev_effect__"] = 123
                        # "effect changed" should reset params to p2 exactly (no junk key)
                        L["behavior"] = k2
                        L["params"] = defaults_for(uses2)
                        if "__junk_prev_effect__" in (L.get("params") or {}):
                            _fail("UI_CHANGE_EFFECT_RESETS_PARAMS", "stale key survived reset")
                        else:
                            _ok("UI_CHANGE_EFFECT_RESETS_PARAMS")
                    else:
                        _fail("UI_CHANGE_EFFECT_RESETS_PARAMS", "not enough effects registered to test")
                except Exception as e:
                    _fail("UI_CHANGE_EFFECT_RESETS_PARAMS", f"{type(e).__name__}: {e}")

                # 2) Operator enabled flag survives normalize + JSON roundtrip
                try:
                    import copy as _copy
                    ptest = _copy.deepcopy(pd)
                    layers = ptest.get("layers") or []
                    if not isinstance(layers, list) or not layers:
                        layers = []
                        ptest["layers"] = layers
                    if layers:
                        L0 = layers[0] if isinstance(layers[0], dict) else {}
                        ops = L0.get("operators")
                        if not isinstance(ops, list):
                            ops = []
                        # ensure a real post-op
                        ops.append({"type": "gain", "enabled": False, "params": {"gain": 1.2}})
                        L0["operators"] = ops
                        layers[0] = L0
                        ptest["layers"] = layers
                        # run normalizer
                        try:
                            p2, _chg = normalize_project_zones_masks_groups(ptest)
                        except Exception:
                            p2 = ptest
                        # json roundtrip (sanitize to prevent accidental UI object graphs / cycles
                        # from crashing persistence).
                        try:
                            from app.json_sanitize import sanitize_for_json
                            p2_clean, _issues = sanitize_for_json(p2)
                        except Exception:
                            p2_clean = p2
                        p3 = json.loads(json.dumps(p2_clean))
                        Lx = (p3.get("layers") or [])[0]
                        opsx = (Lx.get("operators") or [])
                        enabled_vals = [bool(o.get("enabled", True)) for o in opsx if isinstance(o, dict) and (o.get("type") or o.get("kind")) == "gain"]
                        if enabled_vals and enabled_vals[-1] is False:
                            _ok("UI_TOGGLE_OPERATOR_PERSISTS")
                        else:
                            _fail("UI_TOGGLE_OPERATOR_PERSISTS", "enabled flag lost or coerced to True")
                    else:
                        _fail("UI_TOGGLE_OPERATOR_PERSISTS", "no layers to test")
                except Exception as e:
                    _fail("UI_TOGGLE_OPERATOR_PERSISTS", f"{type(e).__name__}: {e}")

                # 3) Jump range parser sanity (no exceptions; basic normalization)
                try:
                    def _parse_jump_local(s):
                        s = (s or "").strip()
                        if not s:
                            return None
                        if ":" in s:
                            a, b = s.split(":", 1)
                            try:
                                start = int(a.strip()); end = int(b.strip())
                            except Exception:
                                return None
                            if end < start:
                                start, end = end, start
                            return (start, end)
                        try:
                            n = int(s); return (n, n)
                        except Exception:
                            return None
                    cases = {
                        "10": (10,10),
                        "5:9": (5,9),
                        "9:5": (5,9),
                        "  7 : 8 ": (7,8),
                        "bad": None,
                        "": None,
                    }
                    ok = True
                    for k,v in cases.items():
                        if _parse_jump_local(k) != v:
                            ok = False
                            break
                    if ok:
                        _ok("UI_JUMP_RANGE_PARSE")
                    else:
                        _fail("UI_JUMP_RANGE_PARSE", "parse mismatch")
                except Exception as e:
                    _fail("UI_JUMP_RANGE_PARSE", f"{type(e).__name__}: {e}")


                # --- Target Resolution Matrix (per layer / operator) ---
                lines.append("")
                lines.append("== TARGET RESOLUTION MATRIX (PER LAYER / OPERATOR) ==")
                layers = (pd.get("layers") or [])
                led_count = int((pd.get("layout") or {}).get("num_leds", (pd.get("layout") or {}).get("n_leds", pd.get("n_leds", 0))) or 0)
                if led_count <= 0:
                    led_count = int((pd.get("preview") or {}).get("n_leds", 0) or 0)
                lines.append(f"led_count={led_count}")
                if led_count <= 0:
                    lines.append("WARN: led_count unknown; OOB checks may be inaccurate.")

                for li, layer in enumerate(layers):
                    effect = str(layer.get("effect") or layer.get("behavior") or layer.get("effect_key") or layer.get("kind") or "∅")
                    enabled = bool(layer.get("enabled", True))
                    ops = (layer.get("operators") or [])
                    lines.append("")
                    lines.append(f"-- Layer L{li}: enabled={enabled} effect={effect} ops={len(ops)} --")
                    any_rows = False

                    for oi, op in enumerate(ops):
                        if oi == 0:
                            continue
                        if not isinstance(op, dict):
                            lines.append(f"  Op{oi}: BAD_SHAPE (not a dict)")
                            continue
                        if not bool(op.get("enabled", True)):
                            continue

                        any_rows = True
                        op_type = str(op.get("type") or op.get("kind") or "∅")
                        tk, tr, idx, flags = self._diag_resolve_target_indices(pd, op, led_count if led_count > 0 else 10**9)
                        inb, oob = self._diag_split_oob(idx, led_count) if led_count > 0 else (idx, [])
                        flag_str = "" if not flags else (" FLAGS=" + ",".join(flags))

                        lines.append(
                            f"  Op{oi}: type={op_type} target={tk}:{tr or '∅'} "
                            f"resolved={len(inb)} oob={len(oob)} "
                            f"sample={self._diag_sample(inb)} oob_sample={self._diag_sample(oob)}"
                            f"{flag_str}"
                        )

                    if not any_rows:
                        lines.append("  (no enabled operators in slots > 0)")
                # --- end matrix ---


                # --- Per-Layer Health Table (summary) ---
                try:
                    lines.append("")
                    lines.append("== PER-LAYER HEALTH TABLE ==")
                    layers = (pd.get("layers") or [])
                    led_count = int((pd.get("layout") or {}).get("num_leds", (pd.get("layout") or {}).get("n_leds", pd.get("n_leds", 0))) or 0)

                    # Export eligibility summary (best-effort, never fatal)
                    export_by_layer = {}
                    try:
                        from export.parity_summary import build_parity_summary
                        ps = build_parity_summary(pd, target_id=getattr(self.app_core, "export_target_id", None))
                        # ps expected to include per-layer entries; tolerate missing keys
                        for ent in (ps.get("layers") or []):
                            li = ent.get("index")
                            export_by_layer[li] = ent
                    except Exception:
                        pass

                    # Header
                    lines.append("L | enabled | effect | opacity | blend | ops_en | targets_px | uses_audio | export")
                    lines.append("--|---------|--------|---------|-------|--------|------------|-----------|-------")

                    # Audio usage should be derived from effect capabilities, not string-searching the layer.
                    # This keeps diagnostics honest (e.g. sparkle/rainbow/wipe are not audio-required).
                    _req_audio = {}
                    try:
                        from behaviors.registry import load_capabilities_catalog
                        cat = load_capabilities_catalog() or {}
                        eff = (cat.get("effects") or {}) if isinstance(cat, dict) else {}
                        for k, v in eff.items():
                            if isinstance(v, dict):
                                _req_audio[str(k)] = bool(v.get("requires_audio")) or ("audio" in (v.get("requires") or []))
                    except Exception:
                        _req_audio = {}

                    def _uses_audio(layer_obj) -> bool:
                        try:
                            beh = str((layer_obj or {}).get("effect") or (layer_obj or {}).get("behavior") or "").strip()
                            return bool(_req_audio.get(beh, False))
                        except Exception:
                            return False

                    for li, layer in enumerate(layers):
                        enabled = bool(layer.get("enabled", True))
                        effect = str(layer.get("effect") or layer.get("behavior") or layer.get("effect_key") or layer.get("kind") or "∅")
                        opacity = layer.get("opacity", layer.get("alpha", 1))
                        blend = str(layer.get("blend") or layer.get("blend_mode") or "normal")
                        ops = (layer.get("operators") or [])
                        ops_en = 0
                        targets_px = 0

                        # summarize enabled operators in slots>0
                        for oi, op in enumerate(ops):
                            if oi == 0:
                                continue
                            if isinstance(op, dict) and bool(op.get("enabled", True)):
                                ops_en += 1
                                tk, tr, idx, flags = self._diag_resolve_target_indices(pd, op, led_count if led_count > 0 else 10**9)
                                if led_count > 0:
                                    inb, oob = self._diag_split_oob(idx, led_count)
                                    targets_px += len(inb)
                                else:
                                    targets_px += len(idx)

                        uses_audio = _uses_audio(layer)
                        exp = export_by_layer.get(li)
                        if exp:
                            exp_status = str(exp.get("status") or exp.get("eligibility") or "∅")
                            exp_reason = str(exp.get("reason") or exp.get("block_reason") or "")
                            export_str = exp_status + (f" ({exp_reason})" if exp_reason else "")
                        else:
                            export_str = "∅"

                        lines.append(f"{li} | {enabled} | {effect} | {opacity} | {blend} | {ops_en} | {targets_px} | {uses_audio} | {export_str}")
                except Exception as e:
                    lines.append("")
                    lines.append("== PER-LAYER HEALTH TABLE ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end per-layer health ---


                # --- Cross-References (who uses what) ---
                
                # --- Cross-References (who uses what) ---
                try:
                    import json as _json
                    lines.append("")
                    lines.append("== CROSS-REFERENCES (ZONES/MASKS/GROUPS/SIGNALS) ==")

                    pd_layers = (pd.get("layers") or [])
                    pd_masks = pd.get("masks")
                    if pd_masks is None:
                      pd_masks = {}
                    # Accept legacy list-of-mask-dicts as well.
                    if isinstance(pd_masks, list):
                      _m = {}
                      for mm in pd_masks:
                        if isinstance(mm, dict):
                          mid = mm.get("id") or mm.get("key") or mm.get("name")
                          if mid:
                            _m[str(mid)] = {k:v for (k,v) in mm.items() if k not in ("id","key","name")}
                      pd_masks = _m
                    pd_zones = pd.get("zones")
                    if pd_zones is None:
                      pd_zones = {}
                    # Accept both legacy list-of-zone-dicts and canonical dict form.
                    if isinstance(pd_zones, list):
                      _z = {}
                      for zz in pd_zones:
                        if isinstance(zz, dict):
                          zid = zz.get("id") or zz.get("key") or zz.get("name")
                          if zid:
                            _z[str(zid)] = {k:v for (k,v) in zz.items() if k not in ("id","key","name")}
                      pd_zones = _z
                    pd_groups = pd.get("groups")
                    if pd_groups is None:
                      pd_groups = {}
                    # Accept both legacy list-of-group-dicts and canonical dict form.
                    if isinstance(pd_groups, list):
                      _g = {}
                      for gg in pd_groups:
                        if isinstance(gg, dict):
                          gid = gg.get("id") or gg.get("key") or gg.get("name")
                          if gid:
                            _g[str(gid)] = {k:v for (k,v) in gg.items() if k not in ("id","key","name")}
                      pd_groups = _g

                    def _keys_from_collection(coll, fallback_prefix):
                        if isinstance(coll, dict):
                            return [str(k) for k in coll.keys()]
                        if isinstance(coll, list):
                            out = []
                            for i, item in enumerate(coll):
                                if isinstance(item, dict):
                                    out.append(str(item.get("name") or item.get("id") or f"{fallback_prefix}_{i}"))
                                else:
                                    out.append(f"{fallback_prefix}_{i}")
                            return out
                        return []

                    mask_keys = _keys_from_collection(pd_masks, "mask")
                    zone_keys = _keys_from_collection(pd_zones, "zone")
                    group_keys= _keys_from_collection(pd_groups,"group")

                    used_by = {
                        "mask": {k: [] for k in mask_keys},
                        "zone": {k: [] for k in zone_keys},
                        "group": {k: [] for k in group_keys},
                        "signal": {},
                    }

                    def _note(kind: str, key: str, who: str):
                        if not key:
                            return
                        d = used_by.get(kind)
                        if d is None:
                            return
                        d.setdefault(key, []).append(who)

                    for li, layer in enumerate(pd_layers):
                        ops = (layer.get("operators") or [])
                        for oi, op in enumerate(ops):
                            if oi == 0:
                                continue
                            if not isinstance(op, dict):
                                continue
                            if not bool(op.get("enabled", True)):
                                continue
                            tk = str(op.get("target_kind") or op.get("target") or "").strip().lower()
                            tr = str(op.get("target_ref") or op.get("target_key") or op.get("target_id") or "").strip()
                            if tk in ("mask", "zone", "group") and tr:
                                _note(tk, tr, f"L{li}.Op{oi}")

                    rules = pd.get("rules_v6") or pd.get("rules") or []
                    if isinstance(rules, dict):
                        rules_iter = list(rules.values())
                    elif isinstance(rules, list):
                        rules_iter = rules
                    else:
                        rules_iter = []

                    def _safe_dump(o):
                        try:
                            return _json.dumps(o, sort_keys=True)
                        except Exception:
                            return str(o)

                    for ri, r in enumerate(rules_iter):
                        s = _safe_dump(r)
                        if "audio." in s:
                            _note("signal", "audio.*", f"Rule{ri}")
                        for k in mask_keys:
                            if k and k in s:
                                _note("mask", k, f"Rule{ri}")
                        for k in zone_keys:
                            if k and k in s:
                                _note("zone", k, f"Rule{ri}")
                        for k in group_keys:
                            if k and k in s:
                                _note("group", k, f"Rule{ri}")

                    def _emit(kind: str, d: dict):
                        keys = list(d.keys())
                        lines.append(f"{kind}s: {len(keys)}")
                        if not keys:
                            return
                        for k in sorted(keys):
                            users = d.get(k) or []
                            if not users:
                                lines.append(f"  - {k}: UNUSED")
                            else:
                                sample = users[:10]
                                tail = "" if len(users) <= 10 else f" …(+{len(users)-10})"
                                lines.append(f"  - {k}: used_by={len(users)} {sample}{tail}")

                    _emit("mask", used_by["mask"])
                    _emit("zone", used_by["zone"])
                    _emit("group", used_by["group"])

                    sig_keys = sorted(used_by["signal"].keys())
                    lines.append(f"signals: {len(sig_keys)}")
                    for sk in sig_keys:
                        users = used_by["signal"].get(sk) or []
                        sample = users[:10]
                        tail = "" if len(users) <= 10 else f" …(+{len(users)-10})"
                        lines.append(f"  - {sk}: used_by={len(users)} {sample}{tail}")
                except Exception as e:
                    lines.append("")
                    lines.append("== CROSS-REFERENCES (ZONES/MASKS/GROUPS/SIGNALS) ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end cross-references ---



                # --- Audio Diagnostics Snapshot ---
                try:
                    lines.append("")
                    lines.append("== AUDIO DIAGNOSTICS ==")
                    # Best-effort: pull from app_core if available; never fatal.
                    mode = "∅"
                    backend = "∅"
                    status = "∅"
                    last_err = ""
                    snap = {}

                    try:
                        # Many builds store preview audio controller on core
                        pa = getattr(self.app_core, "preview_audio", None) or getattr(self.app_core, "_full_preview_audio", None) or getattr(self.app_core, "audio", None)
                        if pa is not None:
                            mode = str(getattr(pa, "mode", None) or getattr(pa, "_mode", None) or mode)
                            backend = str(getattr(pa, "backend", None) or getattr(pa, "_backend", None) or backend)
                            status = str(getattr(pa, "status", None) or getattr(pa, "_status", None) or status)
                            last_err = str(getattr(pa, "last_error", None) or getattr(pa, "_last_error", None) or "")
                            # snapshot if method exists
                            if hasattr(pa, "snapshot"):
                                try:
                                    snap = pa.snapshot()
                                except Exception:
                                    snap = {}
                    except Exception:
                        pass

                    # SignalBus snapshot (preferred because it reflects what rules/effects can read)
                    sb = getattr(self.app_core, "signal_bus", None) or getattr(self.app_core, "signals", None)
                    if sb is not None:
                        try:
                            # common API: get(name, default)
                            def _g(k, d=0.0):
                                try:
                                    return float(sb.get(k, d))
                                except Exception:
                                    return d
                            energy = _g("audio.energy", 0.0)
                            mono = [_g(f"audio.mono{i}", 0.0) for i in range(7)]
                            left = [_g(f"audio.L{i}", 0.0) for i in range(7)]
                            right= [_g(f"audio.R{i}", 0.0) for i in range(7)]
                            lines.append(f"mode={mode} backend={backend} status={status}")
                            if last_err:
                                lines.append(f"last_error={last_err}")
                            lines.append(f"audio.energy={energy:.4f}")
                            lines.append(f"audio.mono[0..6]={mono}")
                            lines.append(f"audio.L[0..6]={left}")
                            lines.append(f"audio.R[0..6]={right}")

                            # Audio consumers (rules + layers) for diagnostics
                            lines.append("")
                            lines.append("== AUDIO CONSUMERS ==")

                            import re as _re
                            _AUDIO_REF_RE = _re.compile(r"\baudio\.(?:energy|\*|mono(?:\[\d+\]|\d+)|L(?:\[\d+\]|\d+)|R(?:\[\d+\]|\d+))\b")

                            def _walk_strings(_obj, _seen=None):
                                if _seen is None:
                                    _seen = set()
                                oid = id(_obj)
                                if oid in _seen:
                                    return
                                _seen.add(oid)
                                if _obj is None:
                                    return
                                if isinstance(_obj, str):
                                    yield _obj
                                    return
                                if isinstance(_obj, (int, float, bool)):
                                    return
                                if isinstance(_obj, dict):
                                    for k, v in _obj.items():
                                        if isinstance(k, str):
                                            yield k
                                        yield from _walk_strings(v, _seen)
                                    return
                                if isinstance(_obj, (list, tuple, set)):
                                    for it in _obj:
                                        yield from _walk_strings(it, _seen)
                                    return
                                # Fallback: ignore other types

                            def _extract_audio_refs(_obj):
                                refs = set()
                                for s in _walk_strings(_obj):
                                    if "audio" not in s:
                                        continue
                                    for m in _AUDIO_REF_RE.finditer(s):
                                        refs.add(m.group(0))
                                return refs

                            # NOTE: project data is `pd` in this scope ("pdata" was a typo).
                            rules = pd.get("rules", []) or []
                            rules_using_audio = []
                            _all_rule_refs = []
                            for ri, r in enumerate(rules):
                                r_refs = sorted(_extract_audio_refs(r))
                                if r_refs:
                                    rules_using_audio.append((ri, str(r.get("name", f"Rule{ri}")), r_refs))
                                    _all_rule_refs.extend(r_refs)
                            
                            layers_requires_audio = []
                            for li, ld in enumerate(layers):
                                if _uses_audio(ld):
                                    layers_requires_audio.append((li, str(ld.get("name", f"L{li}")), str(ld.get("effect", "?"))))
                            
                            uniq_refs = sorted(set(_all_rule_refs))
                            lines.append(f"rules_using_audio={len(rules_using_audio)} {[ri for (ri,_,_) in rules_using_audio]}")
                            for (ri, rname, rrefs) in rules_using_audio:
                                lines.append(f"  Rule{ri} name={rname}: refs={rrefs}")
                            lines.append(f"layers_requires_audio={len(layers_requires_audio)} {[li for (li,_,_) in layers_requires_audio]}")
                            for (li, lname, leff) in layers_requires_audio:
                                lines.append(f"  L{li} effect={leff} name={lname}")
                            lines.append(f"project_audio_refs_unique={len(uniq_refs)} {uniq_refs}")
                            lines.append(f"project_audio_ref_occurrences={len(_all_rule_refs)}")
                            lines.append(f"project_audio_token_count={len(_all_rule_refs)}")
                            lines.append("")
                        except Exception as e:
                            lines.append("== AUDIO CONSUMERS ==")
                            lines.append(f"FAILED: {type(e).__name__}: {e}")
                            lines.append("")
                except Exception as e:
                    lines.append("== AUDIO DIAGNOSTICS ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end audio diagnostics ---


                # --- Runtime Invariant Checks (lightweight, non-fatal) ---
                try:
                    import json as _json
                    lines.append("")
                    lines.append("== RUNTIME INVARIANTS ==")

                    errs = []
                    warns = []

                    # Layout truth
                    lay = (pd.get("layout") or {})
                    shape = str(lay.get("shape") or lay.get("kind") or "")
                    num_leds = int(lay.get("num_leds", lay.get("n_leds", 0)) or 0)
                    if shape not in ("strip", "cells"):
                        warns.append(f"layout.shape unexpected: {shape!r}")
                    if num_leds <= 0:
                        errs.append(f"layout.num_leds invalid: {num_leds}")

                    # Layer UID stability (must exist and be unique for stateful effects)
                    layers = (pd.get("layers") or [])
                    uids = []
                    for li, layer in enumerate(layers):
                        uid = str(layer.get("__uid") or layer.get("uid") or "")
                        if not uid:
                            warns.append(f"L{li}: missing __uid/uid (stateful effects will reset)")
                        uids.append(uid)
                    # duplicates
                    seen = {}
                    for li, uid in enumerate(uids):
                        if not uid:
                            continue
                        if uid in seen:
                            errs.append(f"duplicate layer uid: {uid} (L{seen[uid]} and L{li})")
                        else:
                            seen[uid] = li

                    # Operators shape + enabled key presence
                    for li, layer in enumerate(layers):
                        ops = layer.get("operators")
                        if ops is None:
                            warns.append(f"L{li}: operators missing")
                            continue
                        if not isinstance(ops, list):
                            errs.append(f"L{li}: operators not list: {type(ops).__name__}")
                            continue
                        for oi, op in enumerate(ops):
                            if not isinstance(op, dict):
                                errs.append(f"L{li}.Op{oi}: operator not dict: {type(op).__name__}")
                                continue
                            if "enabled" not in op:
                                warns.append(f"L{li}.Op{oi}: operator missing 'enabled' key (defaults may vary)")

                    # Targets referential integrity (mask/zone/group refs must exist if present)
                    masks = pd.get("masks") or {}
                    zones = pd.get("zones") or []
                    groups = pd.get("groups") or []
                    # keys helper
                    def _keys(coll, prefix):
                        if isinstance(coll, dict):
                            return set(str(k) for k in coll.keys())
                        if isinstance(coll, list):
                            out=set()
                            for i,item in enumerate(coll):
                                if isinstance(item, dict):
                                    out.add(str(item.get("name") or item.get("id") or f"{prefix}_{i}"))
                            return out
                        return set()
                    mask_keys = _keys(masks, "mask")
                    zone_keys = _keys(zones, "zone")
                    group_keys= _keys(groups,"group")

                    for li, layer in enumerate(layers):
                        ops = (layer.get("operators") or [])
                        for oi, op in enumerate(ops):
                            if not isinstance(op, dict):
                                continue
                            tk = str(op.get("target_kind") or op.get("target") or "").strip().lower()
                            tr = str(op.get("target_ref") or op.get("target_key") or op.get("target_id") or "").strip()
                            if tk in ("mask","zone","group") and tr:
                                if tk=="mask" and tr not in mask_keys:
                                    errs.append(f"L{li}.Op{oi}: target mask ref missing: {tr}")
                                if tk=="zone" and tr not in zone_keys:
                                    errs.append(f"L{li}.Op{oi}: target zone ref missing: {tr}")
                                if tk=="group" and tr not in group_keys:
                                    errs.append(f"L{li}.Op{oi}: target group ref missing: {tr}")

                    # Rule referential scan (best-effort)
                    rules = pd.get("rules_v6") or pd.get("rules") or []
                    if isinstance(rules, dict):
                        rules_iter = list(rules.values())
                    elif isinstance(rules, list):
                        rules_iter = rules
                    else:
                        rules_iter = []

                    def _dump(o):
                        try:
                            return _json.dumps(o, sort_keys=True)
                        except Exception:
                            return str(o)

                    for ri, r in enumerate(rules_iter):
                        s = _dump(r)
                        # if rule mentions mask_demo etc but doesn't exist, flag
                        for k in list(mask_keys)[:100]:
                            pass
                        # detect references by common fields
                        if isinstance(r, dict):
                            sig = (r.get("when") or {}).get("signal")
                            if sig and isinstance(sig, str) and sig.startswith("audio."):
                                # ok, but audio currently flatline
                                pass

                    # Project signature (helps detect silent schema drift)
                    try:
                        sig_src = _dump(pd)[:200000].encode("utf-8", errors="ignore")
                        sig = hashlib.sha1(sig_src).hexdigest()
                        lines.append(f"project_sig_sha1={sig}")
                    except Exception:
                        pass

                    lines.append(f"errors={len(errs)} warnings={len(warns)}")
                    for e in errs[:50]:
                        lines.append(f"  - ERROR: {e}")
                    if len(errs) > 50:
                        lines.append(f"  ... (+{len(errs)-50} more errors)")
                    for w in warns[:50]:
                        lines.append(f"  - WARN: {w}")
                    if len(warns) > 50:
                        lines.append(f"  ... (+{len(warns)-50} more warnings)")

                except Exception as e:
                    lines.append("")
                    lines.append("== RUNTIME INVARIANTS ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end runtime invariants ---


                # --- Diagnostics Summary (Impact + Top Issues) ---
                try:
                    lines.append("")
                    lines.append("== DIAGNOSTICS SUMMARY (IMPACT + TOP ISSUES) ==")

                    # Collect top issues from prior sections (best-effort, from known signals)
                    issues = []

                    # 1) Export blocker (if present in earlier computed export line)
                    try:
                        # Look back in lines for 'arduino_export:'
                        exp_lines = [l for l in lines if isinstance(l, str) and l.startswith("arduino_export:")]
                        if exp_lines:
                            issues.append(f"export_blocker: {exp_lines[-1].split(':',1)[1].strip()}")
                    except Exception:
                        pass

                    # 2) Targeting failures
                    try:
                        # If targeting_tests exists in local scope in this function, we can't rely. Instead scan 'TARGET_*: FAIL' lines.
                        fail_t = [l for l in lines if isinstance(l, str) and "TARGET_" in l and "FAIL" in l]
                        for l in fail_t[-5:]:
                            issues.append(f"targeting: {l.strip()}")
                    except Exception:
                        pass

                    # 3) Audio flatline
                    try:
                        if any(isinstance(l,str) and l.startswith("audio_flatline=True") for l in lines):
                            issues.append("audio: flatline (all channels ~0.0)")
                    except Exception:
                        pass

                    # 4) Structural empties
                    try:
                        empties = [l for l in lines if isinstance(l,str) and "resolves to empty" in l]
                        for l in empties[:10]:
                            issues.append(f"structural: {l.strip()}")
                    except Exception:
                        pass

                    if not issues:
                        lines.append("top_issues: none detected (best-effort)")
                    else:
                        lines.append(f"top_issues: {len(issues)}")
                        for it in issues[:20]:
                            lines.append(f"  - {it}")
                        if len(issues) > 20:
                            lines.append(f"  ... (+{len(issues)-20} more)")

                    # Impact scoring hooks (uses Cross-References output when available)
                    # We compute impact = used_by_count * resolved_count_est (if resolvable), else used_by_count.
                    pd_masks = pd.get("masks")
                    if pd_masks is None:
                      pd_masks = {}
                    # Accept legacy list-of-mask-dicts as well.
                    if isinstance(pd_masks, list):
                      _m = {}
                      for mm in pd_masks:
                        if isinstance(mm, dict):
                          mid = mm.get("id") or mm.get("key") or mm.get("name")
                          if mid:
                            _m[str(mid)] = {k:v for (k,v) in mm.items() if k not in ("id","key","name")}
                      pd_masks = _m
                    pd_zones = pd.get("zones")
                    if pd_zones is None:
                      pd_zones = {}
                    # Accept both legacy list-of-zone-dicts and canonical dict form.
                    if isinstance(pd_zones, list):
                      _z = {}
                      for zz in pd_zones:
                        if isinstance(zz, dict):
                          zid = zz.get("id") or zz.get("key") or zz.get("name")
                          if zid:
                            _z[str(zid)] = {k:v for (k,v) in zz.items() if k not in ("id","key","name")}
                      pd_zones = _z
                    pd_groups = pd.get("groups")
                    if pd_groups is None:
                      pd_groups = {}
                    # Accept both legacy list-of-group-dicts and canonical dict form.
                    if isinstance(pd_groups, list):
                      _g = {}
                      for gg in pd_groups:
                        if isinstance(gg, dict):
                          gid = gg.get("id") or gg.get("key") or gg.get("name")
                          if gid:
                            _g[str(gid)] = {k:v for (k,v) in gg.items() if k not in ("id","key","name")}
                      pd_groups = _g

                    def _keys_from_collection(coll, prefix):
                        if isinstance(coll, dict):
                            return [str(k) for k in coll.keys()]
                        if isinstance(coll, list):
                            out=[]
                            for i,item in enumerate(coll):
                                if isinstance(item, dict):
                                    out.append(str(item.get("name") or item.get("id") or f"{prefix}_{i}"))
                                else:
                                    out.append(f"{prefix}_{i}")
                            return out
                        return []

                    mask_keys = _keys_from_collection(pd_masks, "mask")
                    zone_keys = _keys_from_collection(pd_zones, "zone")
                    group_keys= _keys_from_collection(pd_groups,"group")

                    # Build reverse index (same logic as Cross-References, minimal)
                    used_by = {"mask": {k: [] for k in mask_keys},
                               "zone": {k: [] for k in zone_keys},
                               "group":{k: [] for k in group_keys}}

                    pd_layers = (pd.get("layers") or [])
                    for li, layer in enumerate(pd_layers):
                        ops = (layer.get("operators") or [])
                        for oi, op in enumerate(ops):
                            if oi == 0:
                                continue
                            if not isinstance(op, dict):
                                continue
                            if not bool(op.get("enabled", True)):
                                continue
                            tk = str(op.get("target_kind") or op.get("target") or "").strip().lower()
                            tr = str(op.get("target_ref") or op.get("target_key") or op.get("target_id") or "").strip()
                            if tk in ("mask","zone","group") and tr:
                                used_by.setdefault(tk, {}).setdefault(tr, []).append(f"L{li}.Op{oi}")

                    # Estimate resolved counts for masks/zones/groups if resolver helper exists
                    led_count = int((pd.get("layout") or {}).get("num_leds", (pd.get("layout") or {}).get("n_leds", pd.get("n_leds", 0))) or 0)
                    def _est_resolve(tk, key):
                        try:
                            # fake operator dict to reuse resolver
                            op = {"target_kind": tk, "target_ref": key, "enabled": True}
                            _tk, _tr, idx, _flags = self._diag_resolve_target_indices(pd, op, led_count if led_count>0 else 10**9)
                            return len(idx or [])
                        except Exception:
                            return 0

                    rows=[]
                    for tk, keys in (("mask", mask_keys), ("zone", zone_keys), ("group", group_keys)):
                        for k in keys:
                            ub = len(used_by.get(tk, {}).get(k, []))
                            rc = _est_resolve(tk, k)
                            impact = ub * (rc if rc>0 else 1)
                            rows.append((impact, tk, k, ub, rc))

                    rows.sort(reverse=True, key=lambda r: r[0])
                    lines.append("")
                    lines.append("impact_top10: (impact = used_by * max(1,resolved_count_est))")
                    for impact, tk, k, ub, rc in rows[:10]:
                        lines.append(f"  - {tk}:{k} impact={impact} used_by={ub} resolved_est={rc}")
                    if len(rows) > 10:
                        lines.append(f"  ... (+{len(rows)-10} more entities)")

                except Exception as e:
                    lines.append("")
                    lines.append("== DIAGNOSTICS SUMMARY (IMPACT + TOP ISSUES) ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end summary ---


                # --- Target Entity Drilldown (defs + resolve + users) ---
                try:
                    lines.append("")
                    lines.append("== TARGET ENTITY DRILLDOWN ==")

                    lay = (pd.get("layout") or {})
                    led_count = int(lay.get("num_leds", lay.get("n_leds", 0)) or 0)
                    pd_layers = (pd.get("layers") or [])

                    pd_masks = pd.get("masks")
                    if pd_masks is None:
                      pd_masks = {}
                    # Accept legacy list-of-mask-dicts as well.
                    if isinstance(pd_masks, list):
                      _m = {}
                      for mm in pd_masks:
                        if isinstance(mm, dict):
                          mid = mm.get("id") or mm.get("key") or mm.get("name")
                          if mid:
                            _m[str(mid)] = {k:v for (k,v) in mm.items() if k not in ("id","key","name")}
                      pd_masks = _m
                    pd_zones = pd.get("zones")
                    if pd_zones is None:
                      pd_zones = {}
                    # Accept both legacy list-of-zone-dicts and canonical dict form.
                    if isinstance(pd_zones, list):
                      _z = {}
                      for zz in pd_zones:
                        if isinstance(zz, dict):
                          zid = zz.get("id") or zz.get("key") or zz.get("name")
                          if zid:
                            _z[str(zid)] = {k:v for (k,v) in zz.items() if k not in ("id","key","name")}
                      pd_zones = _z
                    pd_groups = pd.get("groups")
                    if pd_groups is None:
                      pd_groups = {}
                    # Accept both legacy list-of-group-dicts and canonical dict form.
                    if isinstance(pd_groups, list):
                      _g = {}
                      for gg in pd_groups:
                        if isinstance(gg, dict):
                          gid = gg.get("id") or gg.get("key") or gg.get("name")
                          if gid:
                            _g[str(gid)] = {k:v for (k,v) in gg.items() if k not in ("id","key","name")}
                      pd_groups = _g

                    zone_by_name = {}
                    if isinstance(pd_zones, list):
                        for z in pd_zones:
                            if isinstance(z, dict) and z.get("name"):
                                zone_by_name[str(z.get("name"))] = z

                    group_by_name = {}
                    if isinstance(pd_groups, list):
                        for g in pd_groups:
                            if isinstance(g, dict) and g.get("name"):
                                group_by_name[str(g.get("name"))] = g

                    users = {"mask": {}, "zone": {}, "group": {}}
                    for li, layer in enumerate(pd_layers):
                        ops = (layer.get("operators") or [])
                        for oi, op in enumerate(ops):
                            if oi == 0:
                                continue
                            if not isinstance(op, dict):
                                continue
                            if not bool(op.get("enabled", True)):
                                continue
                            tk, tr, _f = self._diag_get_target(op)
                            if tk in ("mask","zone","group") and tr:
                                users.setdefault(tk, {}).setdefault(tr, []).append(f"L{li}.Op{oi}")

                    # Masks
                    if isinstance(pd_masks, dict):
                        lines.append(f"masks={len(pd_masks)}")
                        for k, v in sorted(pd_masks.items()):
                            kind = (v.get("kind") if isinstance(v, dict) else None)
                            _tk, _tr, idx, flags = self._diag_resolve_target_indices(pd, {"target_kind":"mask","target_ref":k,"enabled":True}, led_count if led_count>0 else 10**9)
                            u = users.get("mask", {}).get(k, [])
                            lines.append(f"  - mask:{k} kind={kind} resolved={len(idx)} users={len(u)} flags={','.join(flags) if flags else '∅'}")
                    else:
                        lines.append("masks=∅")

                    # Zones
                    zkeys = []
                    if isinstance(pd_zones, dict):
                        zkeys = list(pd_zones.keys())
                    elif isinstance(pd_zones, list):
                        zkeys = [str((z or {}).get('name') or f'zone_{i}') for i,z in enumerate(pd_zones)]
                    lines.append(f"zones={len(zkeys)}")
                    for k in sorted(zkeys):
                        zd = pd_zones.get(k) if isinstance(pd_zones, dict) else zone_by_name.get(k)
                        _tk, _tr, idx, flags = self._diag_resolve_target_indices(pd, {"target_kind":"zone","target_ref":k,"enabled":True}, led_count if led_count>0 else 10**9)
                        u = users.get("zone", {}).get(k, [])
                        lines.append(f"  - zone:{k} def={str(zd)[:120]} resolved={len(idx)} users={len(u)} flags={','.join(flags) if flags else '∅'}")

                    # Groups
                    gkeys = []
                    if isinstance(pd_groups, dict):
                        gkeys = list(pd_groups.keys())
                    elif isinstance(pd_groups, list):
                        gkeys = [str((g or {}).get('name') or f'group_{i}') for i,g in enumerate(pd_groups)]
                    lines.append(f"groups={len(gkeys)}")
                    for k in sorted(gkeys):
                        gd = pd_groups.get(k) if isinstance(pd_groups, dict) else group_by_name.get(k)
                        _tk, _tr, idx, flags = self._diag_resolve_target_indices(pd, {"target_kind":"group","target_ref":k,"enabled":True}, led_count if led_count>0 else 10**9)
                        u = users.get("group", {}).get(k, [])
                        lines.append(f"  - group:{k} def={str(gd)[:120]} resolved={len(idx)} users={len(u)} flags={','.join(flags) if flags else '∅'}")
                except Exception as e:
                    lines.append("")
                    lines.append("== TARGET ENTITY DRILLDOWN ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end drilldown ---


                # --- Schema Introspection (what is actually in pd) ---
                try:
                    import json as _json
                    lines.append("")
                    lines.append("== SCHEMA INTROSPECTION ==")

                    def _t(v):
                        try:
                            return type(v).__name__
                        except Exception:
                            return "<?>"
                    def _short(v, n=160):
                        try:
                            s = _json.dumps(v, sort_keys=True)
                        except Exception:
                            s = str(v)
                        if len(s) > n:
                            return s[:n] + "…"
                        return s

                    top_keys = sorted(list(pd.keys())) if isinstance(pd, dict) else []
                    lines.append(f"pd_type={_t(pd)} keys={len(top_keys)}")
                    if top_keys:
                        lines.append("top_level_keys=" + ", ".join(top_keys[:60]) + ("" if len(top_keys)<=60 else f" …(+{len(top_keys)-60})"))

                    # Show possible alt containers for zones/groups/masks
                    for k in ["masks","masks_v2","zones","zones_v2","groups","groups_v2","targeting","targets","target_packs","packs"]:
                        if isinstance(pd, dict) and k in pd:
                            lines.append(f"pd['{k}'] type={_t(pd.get(k))} short={_short(pd.get(k))}")

                    # Layers/operator raw excerpts
                    layers = (pd.get("layers") or [])
                    lines.append(f"layers_type={_t(layers)} layers_n={len(layers) if isinstance(layers,list) else '∅'}")
                    for li, layer in enumerate(layers[:4] if isinstance(layers,list) else []):
                        if not isinstance(layer, dict):
                            lines.append(f"L{li}: type={_t(layer)} value={_short(layer)}")
                            continue
                        lines.append(f"L{li}: keys=" + ",".join(sorted(layer.keys())))
                        ops = layer.get("operators")
                        lines.append(f"  operators_type={_t(ops)} n={len(ops) if isinstance(ops,list) else '∅'}")
                        if isinstance(ops, list):
                            for oi, op in enumerate(ops[:5]):
                                if isinstance(op, dict):
                                    tk,tr,_f = self._diag_get_target(op) if hasattr(self,"_diag_get_target") else ("<?>","<?>",[])
                                    lines.append(f"  Op{oi}: type={op.get('type') or op.get('kind') or '∅'} keys=" + ",".join(sorted(op.keys())))
                                    lines.append(f"        target_extracted={tk}:{tr if tr else '∅'} raw_target_fields=" + _short({k:op.get(k) for k in ['target_kind','target_ref','target','targeting','target_key','target_id']}))
                                else:
                                    lines.append(f"  Op{oi}: type={_t(op)} value={_short(op)}")
                    # Also dump rules shape for audio signals
                    rules = pd.get("rules_v6") or pd.get("rules") or []
                    lines.append(f"rules_type={_t(rules)}")
                except Exception as e:
                    lines.append("")
                    lines.append("== SCHEMA INTROSPECTION ==")
                    lines.append(f"FAILED: {type(e).__name__}: {e}")
                # --- end schema introspection ---


                # --- UI / Preview init diagnostics (read-only, best-effort) ---

                try:
                    lines.append("== UI/PREVIEW INIT DIAGNOSTICS ==")
                    
                    def _t(v):
                        try:
                            return type(v).__name__
                        except Exception:
                            return "<?>"
                    
                    # Project layout snapshot
                    try:
                        lay = pd.get("layout", None) if isinstance(pd, dict) else None
                        if isinstance(lay, dict):
                            lines.append(f"pd.layout.type={_t(lay)} short={str(lay)[:240]}")
                        else:
                            lines.append(f"pd.layout.type={_t(lay)} short={str(lay)[:240] if lay is not None else '∅'}")
                    except Exception:
                        lines.append("pd.layout.type=<?> short=<?>")
                    
                    # Find the layout selector QComboBox (Diagnostics tab is nested; walk parents + window.controls)
                    lw = None
                    try:
                        p = self
                        while p is not None and lw is None:
                            if hasattr(p, "layout_combo"):
                                lw = getattr(p, "layout_combo", None)
                                break
                            p = p.parent() if hasattr(p, "parent") else None
                        if lw is None and hasattr(self, "window"):
                            w = self.window()
                            if w is not None and hasattr(w, "controls") and hasattr(w.controls, "layout_combo"):
                                lw = getattr(w.controls, "layout_combo", None)
                    except Exception:
                        lw = None
                    
                    lines.append(f"layout_widget={'QComboBox' if lw is not None else '∅'}")
                    if lw is not None:
                        try:
                            lines.append(f"layout.current='{lw.currentText()}' items={lw.count()}")
                        except Exception:
                            lines.append("layout.current=<?> items=?")
                    
                    # Core + preview engine (CoreBridge stores engine in _full_preview_engine on this build line)
                    core = getattr(self, "app_core", None) or getattr(self, "core", None)
                    if core is None:
                        try:
                            p = self.parent() if hasattr(self, "parent") else None
                            while p is not None and core is None:
                                core = getattr(p, "app_core", None) or getattr(p, "core", None)
                                p = p.parent() if hasattr(p, "parent") else None
                        except Exception:
                            pass
                    
                    lines.append(f"core_present={core is not None}")
                    
                    eng = None
                    if core is not None:
                        eng = (
                            getattr(core, "_full_preview_engine", None)
                            or getattr(core, "full_preview_engine", None)
                            or getattr(core, "preview_engine", None)
                            or getattr(core, "engine", None)
                            or getattr(core, "preview", None)
                        )
                    lines.append(f"preview_engine_present={eng is not None} type={_t(eng)}")
                    # PreviewEngine startup diagnostics: keep last error/trace visible even when
                    # preview creation fails (critical for field debugging).
                    _pe_err = getattr(core, '_full_preview_last_error', None) if core else None
                    _pe_trace = getattr(core, '_full_preview_last_trace', None) if core else None

                    if _pe_err not in (None, '', '∅'):
                        lines.append(f"preview_engine_last_error={_pe_err}")
                    else:
                        lines.append("preview_engine_last_error=∅")

                    if _pe_trace not in (None, '', '∅'):
                        lines.append("preview_engine_last_trace=present")

                    # Also surface where the rebuild happened (CoreBridge helper)
                    _pe_loc = getattr(core, '_full_preview_rebuild_loc', None) if core else None
                    if _pe_loc:
                        lines.append(f"preview_engine_rebuild_loc={_pe_loc}")
                    
                    # Behavior registry snapshot (authoritative)
                    try:
                        from behaviors import registry as _beh_reg
                        _r = getattr(_beh_reg, "REGISTRY", None)
                        if isinstance(_r, dict):
                            lines.append(f"effect_registry_present=True count={len(_r)}")
                        elif _r is not None:
                            try:
                                lines.append(f"effect_registry_present=True count={len(_r)}")
                            except Exception:
                                lines.append("effect_registry_present=True count=?")
                        else:
                            lines.append("effect_registry_present=False")
                    except Exception:
                        lines.append("effect_registry_present=False")
                except Exception as e:

                    lines.append("")

                    lines.append("== UI/PREVIEW INIT DIAGNOSTICS ==")

                    lines.append(f"FAILED: {type(e).__name__}: {e}")

                
                # 4) Conversion invariants (headless): selection→zone → mask → group should not create stale refs
                try:
                    import json as _json
                    try:
                        p0 = app_core.project
                    except Exception:
                        p0 = {}
                    # deep copy (JSON) so we don't mutate the live project
                    try:
                        ptest = _json.loads(_json.dumps(p0))
                    except Exception:
                        ptest = dict(p0) if isinstance(p0, dict) else {}

                    zones = ptest.get("zones") or {}
                    if not isinstance(zones, dict):
                        zones = {}
                    masks = ptest.get("masks") or {}
                    if not isinstance(masks, dict):
                        masks = {}
                    groups = ptest.get("groups") or {}
                    if not isinstance(groups, dict):
                        groups = {}

                    # deterministic tiny selection
                    idxs = [0, 1, 2, 3]

                    # (simulate) selection->zone
                    zname = "diag_conv_zone"
                    if zname in zones:
                        zname = f"{zname}_2"
                    zones2 = dict(zones)
                    zones2[zname] = {"indices": idxs}

                    # (simulate) zone->mask
                    mname = f"Zone_{zname}"
                    if mname in masks:
                        mname = f"{mname}_2"
                    masks2 = dict(masks)
                    masks2[mname] = {"op": "indices", "indices": idxs}

                    # (simulate) mask->group
                    gbase = f"FromMask_{mname}"
                    gname = gbase
                    k = 1
                    while gname in groups:
                        k += 1
                        gname = f"{gbase}_{k}"
                    groups2 = dict(groups)
                    groups2[gname] = {"indices": idxs}

                    ptest2 = dict(ptest)
                    ptest2["zones"] = zones2
                    ptest2["masks"] = masks2
                    ptest2["groups"] = groups2

                    from app.project_validation import validate_project
                    vr = validate_project(ptest2)
                    if isinstance(vr, dict) and vr.get("ok", False):
                        _ok("CONVERSION_INVARIANTS")
                    else:
                        err_n = len((vr or {}).get("errors", [])) if isinstance(vr, dict) else -1
                        _fail("CONVERSION_INVARIANTS", f"validate_project failed (errors={err_n})")
                except Exception as e:
                    _fail("CONVERSION_INVARIANTS", f"{type(e).__name__}: {e}")

# --- end UI / Preview init diagnostics ---


                # --- LIVE PREVIEW WIRING (Qt runtime) ---
                try:
                    lines.append("")
                    lines.append("== LIVE PREVIEW WIRING ==")
                    # Bridge + engine + widget linkage sanity
                    bridge = None
                    try:
                        bridge = getattr(self, 'app_core', None)
                    except Exception:
                        bridge = None
                    lines.append(f"bridge_present={bool(bridge)}")
                    try:
                        proj_live = getattr(bridge, 'project', None)
                        lines.append(f"bridge.project_present={bool(proj_live)}")
                        if isinstance(proj_live, dict):
                            lines.append(f"bridge.project.layers_n={len(proj_live.get('layers', []))}")
                            lay = proj_live.get('layout', {}) if isinstance(proj_live.get('layout', {}), dict) else {}
                            lines.append(f"bridge.project.layout.shape={lay.get('shape')}")
                    except Exception as e:
                        lines.append(f"bridge.project_read_err={type(e).__name__}: {e}")

                    try:
                        eng = getattr(bridge, '_full_preview_engine', None) or getattr(bridge, '_preview_engine', None) or getattr(bridge, 'preview_engine', None)
                        lines.append(f"preview_engine_present={bool(eng)}")
                        if eng is not None:
                            pd_eng = getattr(eng, 'project_data', None)
                            lines.append(f"engine.project_data_present={bool(pd_eng)}")
                            if isinstance(pd_eng, dict):
                                lines.append(f"engine.project_data.layers_n={len(pd_eng.get('layers', []))}")
                                lay2 = pd_eng.get('layout', {}) if isinstance(pd_eng.get('layout', {}), dict) else {}
                                lines.append(f"engine.project_data.layout.shape={lay2.get('shape')}")
                            stats = getattr(eng, '_last_render_stats', None)
                            lines.append(f"engine._last_render_stats={stats}")
                    except Exception as e:
                        lines.append(f"engine_read_err={type(e).__name__}: {e}")

                    try:
                        pw = getattr(self, 'preview_widget', None)
                        mw = getattr(self, 'matrix_preview_widget', None)
                        lines.append(f"qt.preview_widget_present={bool(pw)}")
                        lines.append(f"qt.matrix_widget_present={bool(mw)}")
                        if (pw is None) and (mw is None):
                            lines.append("qt.preview_note=No Qt preview widgets detected in this session. This is OK if PREVIEW RENDER PROBES below show nonzero output; if probes are blank, preview wiring/regression likely.")
                        if pw is not None:
                            lines.append(f"qt.preview_widget.last_mode={getattr(pw, '_last_mode_used', None)}")
                            lines.append(f"qt.preview_widget.last_paint_info={getattr(pw, '_last_paint_info', None)}")
                        if mw is not None:
                            lines.append(f"qt.matrix_widget.last_paint_info={getattr(mw, '_last_paint_info', None)}")
                    except Exception as e:
                        lines.append(f"preview_widget_read_err={type(e).__name__}: {e}")
                except Exception as e:
                    lines.append(f"== LIVE PREVIEW WIRING == FAILED: {type(e).__name__}: {e}")
                # --- end LIVE PREVIEW WIRING ---

                # --- PREVIEW RENDER PROBES (engine respects layer.enabled? + model divergence) ---
                try:
                    lines.append("")
                    lines.append("== PROJECT MODEL DIVERGENCE ==")
                    bridge = getattr(self, 'app_core', None)
                    eng = getattr(bridge, 'preview_engine', None) if bridge is not None else None
                    pd_live = getattr(bridge, 'project', None) if bridge is not None else None
                    proj = getattr(eng, 'project', None) if eng is not None else None
                    lines.append(f"bridge_present={bool(bridge)} engine_present={bool(eng)}")
                    # Bridge (dict) summary
                    if isinstance(pd_live, dict):
                        _pd_layers = list(pd_live.get('layers', []) or [])
                        _pd_en = [bool(L.get('enabled', True)) for L in _pd_layers if isinstance(L, dict)]
                        _pd_fx = [str(L.get('effect') or L.get('behavior') or L.get('name') or '?') for L in _pd_layers if isinstance(L, dict)]
                        lines.append(f"bridge.project(dict): layers_n={len(_pd_layers)} enabled_n={sum(1 for x in _pd_en if x)} enabled={_pd_en}")
                        lines.append(f"bridge.effects={_pd_fx}")
                    else:
                        lines.append(f"bridge.project(dict): unavailable type={type(pd_live).__name__}")
                    # Engine (object) summary
                    if proj is not None:
                        try:
                            _eng_layers = list(getattr(proj, 'layers', []) or [])
                        except Exception:
                            _eng_layers = []
                        def _get_enabled(obj):
                            if isinstance(obj, dict):
                                return bool(obj.get('enabled', True))
                            return bool(getattr(obj, 'enabled', True))
                        def _set_enabled(obj, v):
                            if isinstance(obj, dict):
                                obj['enabled'] = bool(v)
                            else:
                                setattr(obj, 'enabled', bool(v))
                        def _get_fx(obj):
                            if isinstance(obj, dict):
                                return str(obj.get('effect') or obj.get('behavior') or obj.get('name') or '?')
                            return str(getattr(obj, 'effect', None) or getattr(obj, 'behavior', None) or getattr(obj, 'name', None) or '?')
                        _eng_en = [_get_enabled(L) for L in _eng_layers]
                        _eng_fx = [_get_fx(L) for L in _eng_layers]
                        lines.append(f"engine.project(obj): layers_n={len(_eng_layers)} enabled_n={sum(1 for x in _eng_en if x)} enabled={_eng_en}")
                        lines.append(f"engine.effects={_eng_fx}")
                    else:
                        lines.append("engine.project(obj): MISSING")

                    lines.append("")
                    lines.append("== PREVIEW RENDER PROBES ==")
                    lines.append(f"probe.bridge={bool(bridge)} engine={bool(eng)} pd_live={bool(pd_live)} engine_project={bool(proj)}")
                    if eng is not None and proj is not None and hasattr(eng, 'render_frame'):
                        import time as _time
                        # helpers to count non-black and summarize colors
                        def _summarize(_leds):
                            if not _leds:
                                return {'nonzero': 0, 'leds_len': 0, 'uniq': 0}
                            _nz = 0
                            _uniq = set()
                            for _px in _leds:
                                _uniq.add((_px[0], _px[1], _px[2]))
                                if _px[0] or _px[1] or _px[2]:
                                    _nz += 1
                            return {'nonzero': _nz, 'leds_len': len(_leds), 'uniq': len(_uniq)}
                        # Snapshot current enabled flags on engine project layers
                        try:
                            _layers0 = list(getattr(proj, 'layers', []) or [])
                        except Exception:
                            _layers0 = []
                        _orig = []
                        for _L in _layers0:
                            try:
                                _orig.append(_get_enabled(_L))
                            except Exception:
                                _orig.append(True)
                        def _render(tag):
                            _tnow = _time.time()
                            _leds = eng.render_frame(float(_tnow))
                            s = _summarize(_leds)
                            lines.append(f"{tag}: nonzero={s['nonzero']} leds_len={s['leds_len']} uniq={s['uniq']}")
                        # A: as-is
                        _render('A_live_engine_project')
                        # B: all off on engine project
                        for _L in _layers0:
                            try: _set_enabled(_L, False)
                            except Exception: pass
                        _render('B_all_off_engine_project')
                        # C: first only (engine project)
                        for _idx2, _L in enumerate(_layers0):
                            try: _set_enabled(_L, _idx2 == 0)
                            except Exception: pass
                        _render('C_first_only_engine_project')
                        # D: last only (engine project)
                        _last_i = len(_layers0) - 1
                        for _idx2, _L in enumerate(_layers0):
                            try: _set_enabled(_L, _idx2 == _last_i)
                            except Exception: pass
                        _render('D_last_only_engine_project')
                        # Restore original enabled flags
                        for _L, _v in zip(_layers0, _orig):
                            try: _set_enabled(_L, _v)
                            except Exception: pass
                    else:
                        lines.append("probe_skipped: missing engine/project or render_frame")
                except Exception as e:
                    lines.append(f"== PREVIEW RENDER PROBES == FAILED: {type(e).__name__}: {e}")
                # --- end PREVIEW RENDER PROBES ---

                    # Extra deep-dive probes (read-only)
                    lines.append("")
                    lines.append("== UI WIDGET CONTRACT ==")
                    try:
                        cand = [a for a in dir(self) if ('preview' in a.lower() or 'matrix' in a.lower() or 'cells' in a.lower())]
                        cand = sorted(set(cand))
                        lines.append(f"qt.widget_attr_candidates_n={len(cand)} sample={cand[:25]}")
                    except Exception as e:
                        lines.append(f"qt.widget_attr_candidates_err={type(e).__name__}: {e}")
                    try:
                        pw = getattr(self, 'preview_widget', None)
                        mw = getattr(self, 'matrix_widget', None)
                        lines.append(f"qt.preview_widget.type={type(pw).__name__ if pw is not None else '∅'}")
                        lines.append(f"qt.matrix_widget.type={type(mw).__name__ if mw is not None else '∅'}")
                    except Exception as e:
                        lines.append(f"qt.widget_type_err={type(e).__name__}: {e}")

                    lines.append("")
                    lines.append("== LAYER ENABLE / DELETE PROBES ==")
                    try:
                        # Probe uses COPIES to avoid mutating live project
                        import copy as _copy
                        _proj = getattr(engine, 'project', None) if 'engine' in locals() else None
                        if _proj is None:
                            lines.append("engine.project=∅ (cannot probe)")
                        else:
                            # Helper: render with a modified enabled mask or removed layer
                            def _render_with(mod_fn, tag):
                                try:
                                    p2 = _copy.deepcopy(_proj)
                                    mod_fn(p2)
                                    buf = engine.render_frame(project=p2)
                                    nz = sum(1 for px in buf if (px[0] or px[1] or px[2]))
                                    lines.append(f"{tag}: layers_n={len(getattr(p2,'layers',[]))} nonzero={nz}")
                                except Exception as ee:
                                    lines.append(f"{tag}: ERR {type(ee).__name__}: {ee}")

                            # all disabled
                            _render_with(lambda p: [setattr(l,'enabled',False) for l in getattr(p,'layers',[])], "probe.all_disabled")
                            # only enabled indices from bridge, if available
                            if pd_live and isinstance(pd_live, dict) and 'layers' in pd_live:
                                enabled_mask = [bool(L.get('enabled', True)) for L in pd_live.get('layers',[])]
                                def _apply_mask(p):
                                    for i,l in enumerate(getattr(p,'layers',[])):
                                        if i < len(enabled_mask):
                                            setattr(l,'enabled', bool(enabled_mask[i]))
                                _render_with(_apply_mask, "probe.bridge_enabled_mask")
                            # delete first layer
                            _render_with(lambda p: p.layers.pop(0) if getattr(p,'layers',[]) else None, "probe.delete_first_layer")
                            # delete last layer
                            _render_with(lambda p: p.layers.pop(-1) if getattr(p,'layers',[]) else None, "probe.delete_last_layer")
                    except Exception as e:
                        lines.append(f"layer_probes_err={type(e).__name__}: {e}")

                    lines.append("")
                    lines.append("== SUMMARY: LIKELY ROOT CAUSES ==")
                    try:
                        issues = []
                        # Widget presence
                        if getattr(self, 'preview_widget', None) is None:
                            issues.append("qt.preview_widget missing (strip preview cannot update)")
                        if getattr(self, 'matrix_widget', None) is None:
                            issues.append("qt.matrix_widget missing (matrix preview cannot update)")
                        # Engine binding
                        if 'engine' in locals():
                            if getattr(engine, 'project', None) is None:
                                issues.append("engine.project is ∅ (preview engine not bound to project object)")
                        # Enabled divergence
                        if 'bridge' in locals() and bridge and hasattr(bridge, 'project_data'):
                            _bpd = getattr(bridge, 'project_data', None)
                            if isinstance(_bpd, dict) and 'layers' in _bpd and 'engine' in locals():
                                _ben = [bool(L.get('enabled', True)) for L in _bpd.get('layers',[])]
                                _een = [bool(getattr(L,'enabled',True)) for L in getattr(getattr(engine,'project',None),'layers',[])]
                                if _ben and _een and _ben != _een:
                                    issues.append("layer enabled flags diverge: UI edits not reaching engine.project")
                        if issues:
                            for it in issues:
                                lines.append(f"- {it}")
                        else:
                            lines.append("no obvious wiring issues detected by probes")
                    except Exception as e:
                        lines.append(f"summary_probe_err={type(e).__name__}: {e}")


                lines.append("== UI Action Diagnostics ==")
                fails = [r for r in ui_results if r[1] != "PASS"]
                lines.append(f"tests: {len(ui_results)}   failed: {len(fails)}")
                for name, st, msg in ui_results:
                    if st == "PASS":
                        lines.append(f"  - {name}: PASS")
                    else:
                        lines.append(f"  - {name}: FAIL — {msg}")
                lines.append("")
            except Exception as e:
                lines.append("== UI Action Diagnostics ==")
                lines.append(f"FAILED: {type(e).__name__}: {e}")
                lines.append("")
            # --- CODE MAP (file:line ranges) ---
            try:
                from app.codemap import build_default_codemap, get_effect_locations
                cm = build_default_codemap()
                lines.append("== CODE MAP (FILE:LINE) ==")
                for k,v in cm.items():
                    if v is None:
                        lines.append(f"{k}: ∅")
                    else:
                        lines.append(f"{k}: {v}")
                lines.append("")

                # --- EFFECT LOCATIONS (for safe future edits) ---
                try:
                    used_effects: List[str] = []
                    for layer in (pd.get('layers') or []):
                        ek = (layer or {}).get('effect') or (layer or {}).get('behavior')
                        if ek and ek not in used_effects:
                            used_effects.append(str(ek))
                    locs = get_effect_locations(used_effects, max_items=80)
                    lines.append("== EFFECT LOCATIONS (USED BY PROJECT) ==")
                    if not used_effects:
                        lines.append("(no effects found in project)")
                    else:
                        for key, info in locs:
                            prev = info.get('preview_emit') or "∅"
                            ard = info.get('arduino_emit') or "∅"
                            dloc = info.get('def') or "∅"
                            ok = info.get('ok')
                            status = "OK" if ok else "MISSING"
                            lines.append(f"- {key} [{status}]")
                            lines.append(f"    def: {dloc}")
                            lines.append(f"    preview_emit: {prev}")
                            lines.append(f"    arduino_emit: {ard}")
                    lines.append("")
                except Exception as _e2:
                    lines.append("== EFFECT LOCATIONS (USED BY PROJECT) ==")
                    lines.append(f"(unavailable) — {type(_e2).__name__}: {_e2}")
                    lines.append("")
            except Exception:
                lines.append("== CODE MAP (FILE:LINE) ==")
                lines.append("(unavailable)")
                lines.append("")
            report = "\n".join(lines)
        except Exception as e:
            report = f"Health check failed: {type(e).__name__}: {e}"

        try:
            self.out.setPlainText(report)
        except Exception:
            pass
        self._persist_report(report, "health_check_report.txt")
        self.run_full_btn.setEnabled(True)
        self.run_audit_btn.setEnabled(True)

    def _run_audit_detail(self):
        self.run_full_btn.setEnabled(False)
        self.run_audit_btn.setEnabled(False)
        try:
            self.out.setPlainText("Running effect audit…\n")
        except Exception:
            pass
        try:
            report = self._audit_runner._run_audit(include_audio=True)
        except Exception as e:
            report = f"Effect audit failed: {type(e).__name__}: {e}"
        try:
            self.out.setPlainText(report)
        except Exception:
            pass
        self._persist_report(report, "effect_audit_report.txt")
        self.run_full_btn.setEnabled(True)
        self.run_audit_btn.setEnabled(True)


class ControlsPanel(QtWidgets.QWidget):
    """Always-visible controls area (left side).

    Provides a layout selector (Strip / Matrix) and placeholder tabs for future UI.
    """

    def __init__(self, app_core, on_layout_changed, on_matrix_zoom_changed=None, on_matrix_jump=None, on_matrix_fit=None):
        super().__init__()
        self.app_core = app_core
        self._on_layout_changed = on_layout_changed
        self._on_matrix_zoom_changed = on_matrix_zoom_changed
        self._on_matrix_jump = on_matrix_jump
        self._on_matrix_fit = on_matrix_fit

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Layout selector row
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(QtWidgets.QLabel("Layout:"))
        self.layout_combo = QtWidgets.QComboBox()
        # Project validation status (Phase A1 lock)
        self.validation_badge = QtWidgets.QLabel('Validation: OK')
        self.validation_badge.setToolTip('Project structure validation status')
        try:
            self.validation_badge.setStyleSheet('font-weight: 600;')
        except Exception:
            pass

        self.layout_combo.addItems(["Strip", "Matrix"])
        # Sync selector from current project layout (strip vs matrix).
        try:
            p = self.app_core.project or {}
            lay = dict(p.get('layout') or {})
            shape = lay.get('shape', lay.get('type', 'strip'))
            idx = 1 if str(shape).lower() in ('cells', 'matrix', 'grid') else 0
            self.layout_combo.blockSignals(True)
            self.layout_combo.setCurrentIndex(idx)
            self.layout_combo.blockSignals(False)
        except Exception:
            pass

        self.layout_combo.currentIndexChanged.connect(self._layout_changed)
        self.layout_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.layout_combo.setFixedWidth(180)
        row.addWidget(self.layout_combo)
        row.addStretch(1)
        outer.addLayout(row)

        # Matrix size controls (only shown when Layout=Matrix)
        self.matrix_box = QtWidgets.QGroupBox('Matrix')
        form = QtWidgets.QFormLayout(self.matrix_box)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        self.mw_spin = QtWidgets.QSpinBox()
        self.mw_spin.setRange(1, 2048)
        self.mw_spin.setValue(16)
        form.addRow('Width:', self.mw_spin)

        self.mh_spin = QtWidgets.QSpinBox()
        self.mh_spin.setRange(1, 2048)
        self.mh_spin.setValue(16)
        form.addRow('Height:', self.mh_spin)

        self.mw_spin.valueChanged.connect(self._matrix_dims_changed)
        self.mh_spin.valueChanged.connect(self._matrix_dims_changed)

        # Matrix mapping (wiring)
        self.serp_check = QtWidgets.QCheckBox('Serpentine (zig-zag)')
        self.serp_check.setChecked(False)
        form.addRow(self.serp_check)

        self.flipx_check = QtWidgets.QCheckBox('Flip X')
        self.flipx_check.setChecked(False)
        form.addRow(self.flipx_check)

        self.flipy_check = QtWidgets.QCheckBox('Flip Y')
        self.flipy_check.setChecked(False)
        form.addRow(self.flipy_check)

        self.rot_combo = QtWidgets.QComboBox()
        self.rot_combo.addItems(['0°', '90°', '180°', '270°'])
        form.addRow('Rotate:', self.rot_combo)

        self.serp_check.toggled.connect(self._matrix_mapping_changed)
        self.flipx_check.toggled.connect(self._matrix_mapping_changed)
        self.flipy_check.toggled.connect(self._matrix_mapping_changed)
        self.rot_combo.currentIndexChanged.connect(self._matrix_mapping_changed)


        # Sync mapping widgets from current project (and migrate old key names).
        try:
            p = self.app_core.project or {}
            lay = dict(p.get("layout") or {})
            serp = lay.get("serpentine", lay.get("matrix_serpentine", False))
            fx = lay.get("flip_x", lay.get("matrix_flip_x", False))
            fy = lay.get("flip_y", lay.get("matrix_flip_y", False))
            rot = lay.get("rotate", lay.get("matrix_rotate", 0))
            self.serp_check.blockSignals(True); self.serp_check.setChecked(bool(serp)); self.serp_check.blockSignals(False)
            self.flipx_check.blockSignals(True); self.flipx_check.setChecked(bool(fx)); self.flipx_check.blockSignals(False)
            self.flipy_check.blockSignals(True); self.flipy_check.setChecked(bool(fy)); self.flipy_check.blockSignals(False)
            rot_map = {0: 0, 90: 1, 180: 2, 270: 3}
            self.rot_combo.blockSignals(True); self.rot_combo.setCurrentIndex(rot_map.get(int(rot), 0)); self.rot_combo.blockSignals(False)
        except Exception:
            pass


        # Matrix zoom (touchpad-friendly)
        self.mz_slider = QtWidgets.QSlider(_ORI_H)
        self.mz_slider.setRange(25, 400)  # percent
        self.mz_slider.setValue(100)
        self.mz_slider.setFixedWidth(160)
        # Zoom controls
        zrow = QtWidgets.QHBoxLayout()
        zrow.setSpacing(6)
        zrow.addWidget(self.mz_slider, 1)
        self.mz_fit_btn = QtWidgets.QPushButton("Fit")
        self.mz_fit_btn.setToolTip("Fit the matrix to the available preview area")
        zrow.addWidget(self.mz_fit_btn, 0)
        zw = QtWidgets.QWidget()
        zw.setLayout(zrow)
        form.addRow("Zoom (%):", zw)
        self.mz_slider.valueChanged.connect(self._matrix_zoom_changed)
        try:
            self.mz_fit_btn.clicked.connect(self._matrix_fit_clicked)
        except Exception:
            pass


        # Matrix jump (index -> center in view)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.mjump_edit = QtWidgets.QLineEdit()
        self.mjump_edit.setPlaceholderText("index")
        self.mjump_edit.setFixedWidth(90)
        self.mjump_edit.returnPressed.connect(self._matrix_jump_go)
        row.addWidget(self.mjump_edit)
        self.mjump_go = QtWidgets.QPushButton("Go")
        self.mjump_go.clicked.connect(self._matrix_jump_go)
        row.addWidget(self.mjump_go)
        roww = QtWidgets.QWidget()
        roww.setLayout(row)
        form.addRow("Jump:", roww)

        outer.addWidget(self.matrix_box)
        self.matrix_box.setVisible(False)

        # Tabs for controls/panels (placeholders for now)
        self.tabs = QtWidgets.QTabWidget()

        self.layers_panel = LayerStackPanel(self.app_core)
        self.tabs.addTab(_wrap_tab_widget(self.layers_panel), 'Layers')

        self.operators_panel = OperatorsPanel(self.app_core)
        self.tabs.addTab(_wrap_tab_widget(self.operators_panel), 'Operators')

        # Quick diagnostics for effect coverage/regressions
        self.diagnostics_panel = DiagnosticsHubPanel(self.app_core)
        self.tabs.addTab(_wrap_tab_widget(self.diagnostics_panel), 'Diagnostics')



        # Targets / Signals / Variables are first-class tabs (no more "Experimental" dumping-ground).
        self.zones_panel = ZonesMasksPanel(self.app_core)
        try:
            setattr(self.app_core, '_zones_panel', self.zones_panel)
        except Exception:
            pass

        self._targets_tab_index = self.tabs.addTab(_wrap_tab_widget(self.zones_panel), "Targets")

        self.signals_panel = None
        try:
            if SignalsPanel is not None:
                self.signals_panel = SignalsPanel(self.app_core)
                self.tabs.addTab(_wrap_tab_widget(self.signals_panel), "Signals")
                try:
                    setattr(self.app_core, '_signals_panel', self.signals_panel)
                except Exception:
                    pass
        except Exception:
            self.signals_panel = None

        self.variables_panel = None
        try:
            if VariablesPanel is not None:
                self.variables_panel = VariablesPanel(self.app_core)
                self.tabs.addTab(_wrap_tab_widget(self.variables_panel), "Variables")
                try:
                    setattr(self.app_core, '_variables_panel', self.variables_panel)
                except Exception:
                    pass
        except Exception:
            self.variables_panel = None

        # (+) Allow other panels (e.g., Export) to jump to Targets/Diagnostics.
        try:
            setattr(self.app_core, '_nav_to_panels', lambda: self.tabs.setCurrentIndex(int(getattr(self, '_targets_tab_index', 0))))
        except Exception:
            pass

        self.rules_panel = RulesPanel(self.app_core)

        # Allow other panels (e.g. Export) to invoke the interactive unknown-signal fixer.
        # This avoids duplicating the logic and keeps the workflow one-click from Export.
        try:
            setattr(self.app_core, "_ui_fix_unknown_signals", self.rules_panel._fix_unknown_signals_v6)
        except Exception:
            pass

        self.tabs.addTab(_wrap_tab_widget(self.rules_panel), "Rules")
        self.export_panel = ExportPanel(self.app_core)
        # ---- Phase A1: Target Mask selector (filters all layers in preview) ----
        self.target_mask_box = QtWidgets.QGroupBox('Target Mask')
        self.btn_clear_sel = QtWidgets.QPushButton('Clear selection')
        self.btn_clear_sel.setToolTip('Clear current pixel selection')

        # Keep this section compact and ensure content remains reachable.
        # Use a vertical layout with an internal scroll area for the tools.
        tlay = QtWidgets.QVBoxLayout(self.target_mask_box)
        tlay.setContentsMargins(8, 8, 8, 8)
        tlay.setSpacing(6)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.addWidget(QtWidgets.QLabel('Mask:'), 0)
        self.target_mask_combo = QtWidgets.QComboBox()
        try:
            self.target_mask_combo.installEventFilter(self)
        except Exception:
            pass

        self.target_mask_combo.setToolTip('Optional global mask filter for preview. Uses project.ui.target_mask')
        try:
            self.target_mask_combo.currentIndexChanged.connect(self._on_target_mask_changed)
        except Exception:
            pass

        top_row.addWidget(self.target_mask_combo, 1)
        btns = QtWidgets.QHBoxLayout()
        btns.setSpacing(6)
        self.btn_mask_new = QtWidgets.QPushButton('New from Selection')
        self.btn_mask_new.setToolTip('Create/overwrite a mask using the current selection indices')
        self.btn_mask_del = QtWidgets.QPushButton('Delete')
        self.btn_mask_del.setToolTip('Delete the selected mask key')
        btns.addWidget(self.btn_mask_new)
        btns.addWidget(self.btn_mask_del)
        top_row.addLayout(btns, 0)

        tlay.addLayout(top_row, 0)
        try:
            self._refresh_target_mask_choices()
        except Exception:
            pass

        
        def _mask_new_from_selection():
            try:
                sel = []
                try:
                    sel = list(getattr(self.app_core, 'get_selection_indices', lambda: [])() or [])
                except Exception:
                    sel = []
                if not sel:
                    QtWidgets.QMessageBox.information(self, 'No selection', 'Select some pixels first, then create a mask.')
                    return
                key, ok = QtWidgets.QInputDialog.getText(self, 'New Mask', 'Mask key (unique name):')
                if not ok:
                    return
                key = str(key or '').strip()
                if not key:
                    return
                p = getattr(self.app_core, 'project', None) or {}
                masks = p.get('masks') or {}
                if not isinstance(masks, dict):
                    masks = {}
                masks2 = dict(masks)
                masks2[key] = {'op': 'indices', 'indices': sorted(set(int(x) for x in sel))}
                p2 = dict(p)
                p2['masks'] = masks2
                # persist and set as current target mask for convenience
                ui = dict(p2.get('ui') or {}) if isinstance(p2.get('ui') or {}, dict) else {}
                # : ui may be missing; set ui.target_mask safely (previously a bug: ui['ui'] caused KeyError 'ui')
                ui['target_mask'] = key
                p2['ui'] = ui
                self.app_core.project = p2
                # refresh dropdown
                try: _tm_refresh()
                except Exception: pass
                # apply immediately
                try: self.app_core.target_mask = key
                except Exception: pass
            except Exception as e:
                try: QtWidgets.QMessageBox.warning(self, 'Mask error', str(e))
                except Exception: pass
        
        def _mask_delete_selected():
            try:
                key = str(self.target_mask_combo.currentText() or '').strip()
                if not key or key == '(none)':
                    return
                p = getattr(self.app_core, 'project', None) or {}
                masks = p.get('masks') or {}
                if not isinstance(masks, dict) or key not in masks:
                    return
                resp = QtWidgets.QMessageBox.question(self, 'Delete mask', f"Delete mask '{key}'?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if resp != QtWidgets.QMessageBox.Yes:
                    return
                masks2 = dict(masks)
                masks2.pop(key, None)
                p2 = dict(p)
                p2['masks'] = masks2
                ui = dict(p2.get('ui') or {}) if isinstance(p2.get('ui') or {}, dict) else {}
                if ui.get('target_mask') == key:
                    ui.pop('target_mask', None)
                p2['ui'] = ui
                self.app_core.project = p2
                try: self.app_core.target_mask = None
                except Exception: pass
                try: _tm_refresh()
                except Exception: pass
            except Exception:
                return
        
        self.btn_mask_new.clicked.connect(_mask_new_from_selection)
        self.btn_mask_del.clicked.connect(_mask_delete_selected)
        
        # ---- Compose masks (safe minimal UI) ----
        self.compose_box = QtWidgets.QGroupBox('Mask Tools')
        clay = QtWidgets.QGridLayout(self.compose_box)
        clay.setContentsMargins(8, 8, 8, 8)
        clay.setHorizontalSpacing(6)
        clay.setVerticalSpacing(6)
        self.compose_op = QtWidgets.QComboBox()
        self.compose_op.addItems(['union', 'intersect', 'subtract', 'xor'])
        self.compose_a = QtWidgets.QComboBox()
        self.compose_b = QtWidgets.QComboBox()
        self.btn_compose = QtWidgets.QPushButton('Create')
        self.btn_compose.setToolTip('Create a composed mask from A and B using the selected op')
        clay.addWidget(QtWidgets.QLabel('Op'), 0, 0)
        clay.addWidget(self.compose_op, 0, 1)
        clay.addWidget(QtWidgets.QLabel('A'), 1, 0)
        clay.addWidget(self.compose_a, 1, 1)
        clay.addWidget(QtWidgets.QLabel('B'), 2, 0)
        clay.addWidget(self.compose_b, 2, 1)
        clay.addWidget(self.btn_compose, 3, 0, 1, 2)
        # Put tools into a scroll area so the whole section can be resized
        # without hiding controls off-screen.
        self._target_mask_tools_scroll = QtWidgets.QScrollArea()
        self._target_mask_tools_scroll.setWidgetResizable(True)
        self._target_mask_tools_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._target_mask_tools_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._target_mask_tools_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._target_mask_tools_scroll.setWidget(self.compose_box)
        tlay.addWidget(self._target_mask_tools_scroll, 1)
        
        def _compose_refresh():
            try:
                p = getattr(self.app_core, 'project', None) or {}
                masks = p.get('masks') or {}
                if not isinstance(masks, dict):
                    masks = {}
                keys = sorted(str(k) for k in masks.keys())
                self.compose_a.blockSignals(True)
                self.compose_b.blockSignals(True)
                self.compose_a.clear(); self.compose_b.clear()
                for k in keys:
                    self.compose_a.addItem(k)
                    self.compose_b.addItem(k)
                self.compose_a.blockSignals(False)
                self.compose_b.blockSignals(False)
            except Exception:
                try: self.compose_a.blockSignals(False)
                except Exception: pass
                try: self.compose_b.blockSignals(False)
                except Exception: pass
        
        def _compose_create():
            try:
                op = str(self.compose_op.currentText() or '').strip()
                a = str(self.compose_a.currentText() or '').strip()
                b = str(self.compose_b.currentText() or '').strip()
                if not op or not a or not b:
                    return
                key, ok = QtWidgets.QInputDialog.getText(self, 'Composed Mask', 'New mask key:')
                if not ok:
                    return
                key = str(key or '').strip()
                if not key:
                    return
                # Use CoreBridge helper (validates and writes project copy-on-write)
                try:
                    self.app_core.add_composed_mask(key, op, a, b)
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, 'Compose failed', str(e))
                    return
                # set as active target mask
                try: self.app_core.target_mask = key
                except Exception: pass
                # refresh dropdowns
                try: _tm_refresh()
                except Exception: pass
                try: _compose_refresh()
                except Exception: pass
            except Exception:
                return
        
        self.btn_compose.clicked.connect(_compose_create)
        _compose_refresh()
        
        
        def _tm_refresh():
            try:
                p = getattr(self.app_core, 'project', None) or {}
                ui = p.get('ui') or {}
                cur = ui.get('target_mask', None)
                masks = p.get('masks') or {}
                if not isinstance(masks, dict):
                    masks = {}
                keys = ['(none)'] + sorted(str(k) for k in masks.keys())
                self.target_mask_combo.blockSignals(True)
                self.target_mask_combo.clear()
                for k in keys:
                    self.target_mask_combo.addItem(k)
                idx = 0
                if isinstance(cur, str) and cur in masks:
                    try:
                        idx = keys.index(cur)
                    except Exception:
                        idx = 0
                self.target_mask_combo.setCurrentIndex(idx)
                self.target_mask_combo.blockSignals(False)
            except Exception:
                try:
                    self.target_mask_combo.blockSignals(False)
                except Exception:
                    pass
        
        self._tm_refresh = _tm_refresh
        
        def _tm_changed(_idx: int):
            try:
                txt = str(self.target_mask_combo.currentText() or '').strip()
                if txt == '(none)' or txt == '':
                    self.app_core.target_mask = None
                else:
                    self.app_core.target_mask = txt
            except Exception:
                return
        
        self.target_mask_combo.currentIndexChanged.connect(_tm_changed)
        # : Target Mask UI should live ONLY in Targets tab.
        # Install into Targets tab holder; if it fails, fall back to showing it here.
                # +: Target Mask UI is owned by the Targets tab (ZonesMasksPanel).
        # Do not add Target Mask under Controls/Preview.

        self.tabs.addTab(_wrap_tab_widget(self.export_panel), "Export")
        self.showcase_panel = ShowcasePanel(self.app_core, on_layout_changed)
        self.tabs.addTab(_wrap_tab_widget(self.showcase_panel), "Showcase")
        outer.addWidget(self.tabs, 1)
        try: outer.addWidget(self.btn_clear_sel)
        except Exception: pass

        # keep combo synced to project
        self._sync_timer = QtCore.QTimer(self)
        self._validation_badge_timer = QtCore.QTimer(self)
        self._validation_badge_timer.setInterval(600)
        # Inline validation badge refresh (avoid missing method issues)
        def _do_refresh_validation_badge():
            try:
                snap = getattr(self.app_core, 'last_validation', None)
            except Exception:
                snap = None
            ok = True
            errs = []
            warns = []
            if isinstance(snap, dict):
                ok = bool(snap.get('ok', True))
                errs = snap.get('errors') or []
                warns = snap.get('warnings') or []
            text = 'Validation: OK' if ok else f'Validation: ERROR ({len(errs)})'
            try:
                self.validation_badge.setText(text)
                tip = ''
                if not ok and errs:
                    tip = '\n'.join(str(e) for e in errs[:10])
                elif warns:
                    tip = 'Warnings:\n' + '\n'.join(str(w) for w in warns[:10])
                else:
                    tip = 'Project structure validation status'
                self.validation_badge.setToolTip(tip)
            except Exception:
                pass
        self._refresh_validation_badge = _do_refresh_validation_badge

        self._validation_badge_timer.timeout.connect(self._refresh_validation_badge)
        self._validation_badge_timer.start()

        self._sync_timer.timeout.connect(self._sync_from_project)
        self._sync_timer.start(500)

        def _cp_clear_selection():
            try:
                for attr in ('selection','selected_indices','selected','sel'):
                    if hasattr(self.app_core, attr):
                        try: setattr(self.app_core, attr, set())
                        except Exception: pass
                try: self.app_core.rebuild_preview()
                except Exception: pass
            except Exception:
                return
        try: self.btn_clear_sel.clicked.connect(_cp_clear_selection)
        except Exception: pass

        self._sync_from_project()

        _tm_refresh()

    def _placeholder(self, name: str) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lab = QtWidgets.QLabel(f"{name} (placeholder)")
        lab.setWordWrap(True)
        lay.addWidget(lab)
        lay.addStretch(1)
        return w

    def _sync_from_project(self):
        # IMPORTANT: Don't sync UI while a popup (e.g. a QComboBox dropdown)
        # is open. Touching other widgets during a popup can cause the popup
        # to close immediately on some platforms/WMs, making dropdowns unusable.
        try:
            app = QtWidgets.QApplication.instance()
            if app is not None and app.activePopupWidget() is not None:
                return
        except Exception:
            pass
        try:
            layout = (self.app_core.project.get("layout") or {})
            shape = layout.get("shape", "strip")
            want = 0 if shape == "strip" else 1
            if self.layout_combo.currentIndex() != want:
                self.layout_combo.blockSignals(True)
                self.layout_combo.setCurrentIndex(want)
                self.layout_combo.blockSignals(False)

            # Sync matrix dims
            mw = int(layout.get("matrix_w", 16) or 16)
            mh = int(layout.get("matrix_h", 16) or 16)
            if self.mw_spin.value() != mw:
                self.mw_spin.blockSignals(True)
                self.mw_spin.setValue(mw)
                self.mw_spin.blockSignals(False)
            if self.mh_spin.value() != mh:
                self.mh_spin.blockSignals(True)
                self.mh_spin.setValue(mh)
                self.mh_spin.blockSignals(False)

            # Sync matrix mapping
            try:
                if hasattr(self, 'serp_check'):
                    val = bool(layout.get('serpentine', True))
                    if self.serp_check.isChecked() != val:
                        self.serp_check.blockSignals(True); self.serp_check.setChecked(val); self.serp_check.blockSignals(False)
                if hasattr(self, 'flipx_check'):
                    val = bool(layout.get('flip_x', False))
                    if self.flipx_check.isChecked() != val:
                        self.flipx_check.blockSignals(True); self.flipx_check.setChecked(val); self.flipx_check.blockSignals(False)
                if hasattr(self, 'flipy_check'):
                    val = bool(layout.get('flip_y', False))
                    if self.flipy_check.isChecked() != val:
                        self.flipy_check.blockSignals(True); self.flipy_check.setChecked(val); self.flipy_check.blockSignals(False)
                if hasattr(self, 'rot_combo'):
                    rot = int(layout.get('rotate', 0) or 0)
                    idx = {0:0,90:1,180:2,270:3}.get(rot,0)
                    if self.rot_combo.currentIndex() != idx:
                        self.rot_combo.blockSignals(True); self.rot_combo.setCurrentIndex(idx); self.rot_combo.blockSignals(False)
            except Exception:
                pass

            self.matrix_box.setVisible(want == 1)

            # Sync Zones/Groups panel (coalesced authority)
            try:
                if hasattr(self, 'zones_panel'):
                    zp = self.zones_panel
                    if hasattr(zp, '_request_panel_refresh'):
                        zp._request_panel_refresh()
                    else:
                        zp.refresh()
            except Exception:
                pass

            # Sync Rules panel
            try:
                if hasattr(self, 'rules_panel'):
                    self.rules_panel.refresh()
            except Exception:
                pass

            # Sync Layer stack panel
            try:
                if hasattr(self, 'layers_panel'):
                    self.layers_panel.refresh()
            except Exception:
                pass
            # Sync target mask dropdown (keeps UI consistent when target_mask is changed elsewhere)
            try:
                if hasattr(self, '_tm_refresh') and callable(getattr(self, '_tm_refresh', None)):
                    self._tm_refresh()
            except Exception:
                pass

        except Exception:
            pass

        # keep Target Mask combo in sync (target_mask may be changed by other panels)
        try:
            if hasattr(self, '_tm_refresh'):
                self._tm_refresh()
        except Exception:
            pass

        # keep Masks Manager table in sync
        try:
            mp = getattr(self, 'masks_panel', None)
            if mp is not None and hasattr(mp, 'refresh'):
                mp.refresh()
        except Exception:
            pass

    def _layout_changed(self, idx: int):
        try:
            p = self.app_core.project or {}
            lay = dict(p.get("layout") or {})
            want_shape = "strip" if int(idx) == 0 else "cells"
            lay["shape"] = want_shape

            # Preserve matrix dimensions when switching layouts.
            if want_shape != "strip":
                # Prefer existing values (mw/mh, matrix_w/matrix_h, width/height)
                def _get_int(k, default=None):
                    try:
                        v = lay.get(k, None)
                        return int(v) if v is not None else default
                    except Exception:
                        return default

                mw = _get_int("mw", None)
                mh = _get_int("mh", None)
                if mw is None: mw = _get_int("matrix_w", None)
                if mh is None: mh = _get_int("matrix_h", None)
                if mw is None: mw = _get_int("width", None)
                if mh is None: mh = _get_int("height", None)

                # Fall back to current UI spin values (or 16).
                try:
                    if mw is None:
                        mw = int(self.mw_spin.value()) if hasattr(self, "mw_spin") else 16
                    if mh is None:
                        mh = int(self.mh_spin.value()) if hasattr(self, "mh_spin") else 16
                except Exception:
                    mw = mw if mw is not None else 16
                    mh = mh if mh is not None else 16

                mw = int(mw); mh = int(mh)
                # Keep ALL naming styles in sync (the rest of the app reads different keys).
                lay["mw"] = mw
                lay["mh"] = mh
                lay["matrix_w"] = mw
                lay["matrix_h"] = mh
                lay["width"] = mw
                lay["height"] = mh
                lay["num_leds"] = mw * mh

                # Ensure UI reflects the preserved values.
                try:
                    if hasattr(self, "mw_spin"):
                        self.mw_spin.blockSignals(True); self.mw_spin.setValue(mw); self.mw_spin.blockSignals(False)
                    if hasattr(self, "mh_spin"):
                        self.mh_spin.blockSignals(True); self.mh_spin.setValue(mh); self.mh_spin.blockSignals(False)
                except Exception:
                    pass

            p2 = dict(p)
            p2["layout"] = lay
            self.app_core.project = p2
            # Keep a canonical live project_data reference for all preview/render paths.
            try:
                setattr(self.app_core, "project_data", self.app_core.project)
            except Exception:
                pass
            try:
                setattr(self.app_core, "_preview_dirty", True)
            except Exception:
                pass

            try:
                if hasattr(self.app_core, "_rebuild_full_preview_engine"):
                    self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass
            try:
                # Trim selection to the new LED count (avoid stale indices).
                if hasattr(self.app_core, "get_selection_indices") and hasattr(self.app_core, "set_selection_indices"):
                    sel = list(self.app_core.get_selection_indices() or [])
                    n = int(lay.get("num_leds", 0) or 0)
                    if n > 0:
                        sel2 = [i for i in sel if 0 <= int(i) < n]
                        if sel2 != sel:
                            self.app_core.set_selection_indices(sel2)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.matrix_box.setVisible(int(idx) == 1)
        except Exception:
            pass
        try:
            self._on_layout_changed()
        except Exception:
            pass

    def _matrix_zoom_changed(self, v: int):
        try:
            if callable(self._on_matrix_zoom_changed):
                self._on_matrix_zoom_changed(int(v))
        except Exception:
            pass

    def _matrix_jump_go(self):
        """Separate matrix jump box: center a single LED index."""
        try:
            s = (self.mjump_edit.text() or "").strip()
        except Exception:
            return
        if not s:
            return
        try:
            idx = int(s)
        except Exception:
            return
        try:
            cb = getattr(self, "_on_matrix_jump", None)
            if callable(cb):
                cb(int(idx))
        except Exception:
            pass

    def _matrix_fit_clicked(self):
        try:
            cb = getattr(self, "_on_matrix_fit", None)
            if callable(cb):
                cb()
        except Exception:
            pass

    def _matrix_dims_changed(self):
        """Persist matrix W/H to the project layout."""
        try:
            p = self.app_core.project or {}
            lay = dict(p.get("layout") or {})
            lay.setdefault("shape", "cells")
            # Keep BOTH naming styles in sync.
            mw = int(self.mw_spin.value())
            mh = int(self.mh_spin.value())
            lay["matrix_w"] = mw
            lay["matrix_h"] = mh
            # Older internal naming used by PreviewEngine
            lay["mw"] = mw
            lay["mh"] = mh
            # Keep cell size aliases in sync too (default if absent)
            if "cell_size" in lay and "cell" not in lay:
                lay["cell"] = int(lay.get("cell_size") or 20)
            if "cell" in lay and "cell_size" not in lay:
                lay["cell_size"] = int(lay.get("cell") or 20)

            lay["num_leds"] = mw * mh
            p2 = dict(p)
            p2["layout"] = lay
            self.app_core.project = p2
            try:
                if hasattr(self.app_core, "_rebuild_full_preview_engine"):
                    self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass
            try:
                # Trim selection to the new LED count (avoid stale indices).
                if hasattr(self.app_core, "get_selection_indices") and hasattr(self.app_core, "set_selection_indices"):
                    sel = list(self.app_core.get_selection_indices() or [])
                    n = int(lay.get("num_leds", 0) or 0)
                    if n > 0:
                        sel2 = [i for i in sel if 0 <= int(i) < n]
                        if len(sel2) != len(sel):
                            self.app_core.set_selection_indices(sel2)
            except Exception:
                pass
            try:
                if hasattr(self.app_core, "_rebuild_full_preview_engine"):
                    self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass
            try:
                # Trim selection to the new LED count (avoid stale indices).
                if hasattr(self.app_core, "get_selection_indices") and hasattr(self.app_core, "set_selection_indices"):
                    sel = list(self.app_core.get_selection_indices() or [])
                    n = int(lay.get("num_leds", 0) or 0)
                    if n > 0:
                        sel2 = [i for i in sel if 0 <= int(i) < n]
                        if len(sel2) != len(sel):
                            self.app_core.set_selection_indices(sel2)
            except Exception:
                pass
            try:
                if hasattr(self.app_core, "_rebuild_full_preview_engine"):
                    self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass
            try:
                # Trim selection to the new LED count (avoid stale indices).
                if hasattr(self.app_core, "get_selection_indices") and hasattr(self.app_core, "set_selection_indices"):
                    sel = list(self.app_core.get_selection_indices() or [])
                    n = int(lay.get("num_leds", 0) or 0)
                    if n > 0:
                        sel2 = [i for i in sel if 0 <= int(i) < n]
                        if len(sel2) != len(sel):
                            self.app_core.set_selection_indices(sel2)
            except Exception:
                pass
        except Exception:
            pass

    def _matrix_mapping_changed(self, *args):
        """Persist matrix wiring/mapping options to the project layout."""
        try:
            p = self.app_core.project or {}
            lay = dict(p.get("layout") or {})
            lay.setdefault("shape", "cells")
            val_serp = bool(self.serp_check.isChecked()) if hasattr(self, "serp_check") else False
            lay["serpentine"] = val_serp
            lay["matrix_serpentine"] = val_serp
            val_fx = bool(self.flipx_check.isChecked()) if hasattr(self, "flipx_check") else False
            lay["flip_x"] = val_fx
            lay["matrix_flip_x"] = val_fx
            val_fy = bool(self.flipy_check.isChecked()) if hasattr(self, "flipy_check") else False
            lay["flip_y"] = val_fy
            lay["matrix_flip_y"] = val_fy
            rot_idx = int(self.rot_combo.currentIndex()) if hasattr(self, "rot_combo") else 0
            val_rot = [0, 90, 180, 270][max(0, min(3, rot_idx))]
            lay["rotate"] = val_rot
            lay["matrix_rotate"] = val_rot
            p2 = dict(p)
            p2["layout"] = lay
            self.app_core.project = p2
            try:
                if hasattr(self.app_core, "_rebuild_full_preview_engine"):
                    self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass
        except Exception:
            pass
        try:
            self._on_layout_changed()
        except Exception:
            pass


    def _matrix_mapping_changed(self, *args):
        """Persist matrix wiring/mapping options to the project layout."""
        try:
            p = self.app_core.project or {}
            lay = dict(p.get('layout') or {})
            lay.setdefault('shape', 'cells')
            lay['serpentine'] = bool(getattr(self, 'serp_check', None).isChecked()) if hasattr(self, 'serp_check') else True
            lay['flip_x'] = bool(getattr(self, 'flipx_check', None).isChecked()) if hasattr(self, 'flipx_check') else False
            lay['flip_y'] = bool(getattr(self, 'flipy_check', None).isChecked()) if hasattr(self, 'flipy_check') else False
            rot_idx = int(getattr(self, 'rot_combo', None).currentIndex()) if hasattr(self, 'rot_combo') else 0
            lay['rotate'] = [0, 90, 180, 270][max(0, min(3, rot_idx))]
            p2 = dict(p)
            p2['layout'] = lay
            self.app_core.project = p2
            try:
                if hasattr(self.app_core, '_rebuild_full_preview_engine'):
                    self.app_core._rebuild_full_preview_engine()
            except Exception:
                pass
            try:
                self._on_layout_changed()
            except Exception:
                pass
        except Exception:
            pass
        try:
            self._on_layout_changed()
        except Exception:
            pass




def _refresh_target_mask_choices(self):
    try:
        p = getattr(self.app_core, "project", None) or {}
        ui = p.get("ui") or {}
        cur = ui.get("target_mask", None)
        masks = p.get("masks") or {}
        if not isinstance(masks, dict):
            masks = {}
        keys = ["(none)"] + sorted(str(k) for k in masks.keys())
        try:
            self.target_mask_combo.blockSignals(True)
        except Exception:
            pass
        try:
            self.target_mask_combo.clear()
            for k in keys:
                self.target_mask_combo.addItem(k)
            if isinstance(cur, str) and cur in masks:
                idx = keys.index(cur) if cur in keys else 0
            else:
                idx = 0
            self.target_mask_combo.setCurrentIndex(idx)
        finally:
            try:
                self.target_mask_combo.blockSignals(False)
            except Exception:
                pass
    except Exception:
        try:
            self.target_mask_combo.blockSignals(False)
        except Exception:
            pass

def _on_target_mask_changed(self, _idx: int):
    try:
        txt = str(self.target_mask_combo.currentText() or "").strip()
        if txt == "(none)" or txt == "":
            self.app_core.target_mask = None
        else:
            self.app_core.target_mask = txt
    except Exception:
        return

def eventFilter(self, obj, event):
    # Refresh right before user opens the dropdown so it always contains newest masks.
    try:
        if getattr(self, "target_mask_combo", None) is not None and obj is self.target_mask_combo:
            try:
                et = int(event.type())
            except Exception:
                et = None
            # QEvent.MouseButtonPress is 2 in Qt (works across PyQt/PySide)
            if et == 2:
                try:
                    self._refresh_target_mask_choices()
                except Exception:
                    pass
    except Exception:
        pass
    try:
        return super().eventFilter(obj, event)
    except Exception:
        return False


def _refresh_target_mask_choices(self):
    try:
        p = getattr(self.app_core, "project", None) or {}
        ui = p.get("ui") or {}
        cur = ui.get("target_mask", None)
        masks = p.get("masks") or {}
        if not isinstance(masks, dict):
            masks = {}
        keys = ["(none)"] + sorted(str(k) for k in masks.keys())
        self.target_mask_combo.blockSignals(True)
        self.target_mask_combo.clear()
        for k in keys:
            self.target_mask_combo.addItem(k)
        # set selection
        if isinstance(cur, str) and cur in masks:
            idx = keys.index(cur) if cur in keys else 0
        else:
            idx = 0
        self.target_mask_combo.setCurrentIndex(idx)
        self.target_mask_combo.blockSignals(False)
    except Exception:
        try:
            self.target_mask_combo.blockSignals(False)
        except Exception:
            pass

def _on_target_mask_changed(self, _idx: int):
    try:
        txt = str(self.target_mask_combo.currentText() or "").strip()
        if txt == "(none)" or txt == "":
            self.app_core.target_mask = None
        else:
            self.app_core.target_mask = txt
    except Exception:
        return

    def eventFilter(self, obj, event):
        try:
            if getattr(self, 'target_mask_combo', None) is not None and obj is self.target_mask_combo:
                # Refresh right before user opens the dropdown
                try:
                    et = int(event.type())
                except Exception:
                    et = None
                # QEvent.MouseButtonPress is 2 in Qt
                if et == 2:
                    try:
                        if hasattr(self, '_tm_refresh'):
                            self._tm_refresh()
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            return super().eventFilter(obj, event)
        except Exception:
            return False


    def _refresh_validation_badge(self):
        try:
            snap = getattr(self.app_core, 'last_validation', None)
        except Exception:
            snap = None
        ok = True
        errs = []
        warns = []
        if isinstance(snap, dict):
            ok = bool(snap.get('ok', True))
            errs = snap.get('errors') or []
            warns = snap.get('warnings') or []
        text = 'Validation: OK' if ok else f'Validation: ERROR ({len(errs)})'
        try:
            self.validation_badge.setText(text)
            tip = ''
            if not ok and errs:
                tip = '\n'.join(str(e) for e in errs[:10])
            elif warns:
                tip = 'Warnings:\n' + '\n'.join(str(w) for w in warns[:10])
            else:
                tip = 'Project structure validation status'
            self.validation_badge.setToolTip(tip)
        except Exception:
            pass

class QtMainWindow(QtWidgets.QMainWindow):
    def __init__(self, app_core):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} — {BUILD_ID}")

        # Ensure the OS/window-manager treats this as a normal resizable main window
        # (some WMs disable maximize if the window type/hints look like a tool/dialog).
        try:
            flags = self.windowFlags()
            flags |= QtCore.Qt.WindowType.Window
            flags |= QtCore.Qt.WindowType.WindowMaximizeButtonHint
            flags |= QtCore.Qt.WindowType.WindowMinimizeButtonHint
            flags |= QtCore.Qt.WindowType.WindowCloseButtonHint
            self.setWindowFlags(flags)
        except Exception:
            pass


        self.app_core = app_core

        # --- Header: strip preview (only visible in strip mode) ---
        self.bar = StripPreviewBar(app_core)
        self.preview = PreviewWidget(app_core, self.bar)
        self.preview_widget = self.preview  # diagnostics alias

        self.header = QtWidgets.QWidget()
        hbox = QtWidgets.QVBoxLayout(self.header)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)
        hbox.addWidget(self.bar)
        hbox.addWidget(self.preview)

        # Constrain strip preview height so it doesn't steal the app.
        # Height is kept just big enough for one row of cells + padding.
        self._apply_strip_header_height()

        # --- Main body: controls always visible + matrix preview surface ---
        self.controls = ControlsPanel(app_core, self._on_layout_changed, self._on_matrix_zoom_changed, self._on_matrix_jump, self._on_matrix_fit)

        # +: Move Target Mask UI into Targets tab (single owner).
        try:
            if hasattr(self, 'zones_panel') and self.zones_panel is not None:
                if hasattr(self.zones_panel, '_install_target_mask_widget'):
                    self.zones_panel._install_target_mask_widget(self.controls.target_mask_box)
        except Exception:
            pass

        self.matrix_preview = MatrixPreviewWidget(app_core)
        self.matrix_preview_widget = self.matrix_preview  # diagnostics alias

        self.body_split = QtWidgets.QSplitter(_ORI_H)
        self.body_split.addWidget(self.controls)
        self.body_split.addWidget(self.matrix_preview)
        self.body_split.setStretchFactor(0, 0)
        self.body_split.setStretchFactor(1, 1)

        # Default sizes: keep controls visible, matrix takes remaining.
        try:
            self.body_split.setSizes([360, 740])
        except Exception:
            pass

        # Root layout
        root = QtWidgets.QWidget()
        root_lay = QtWidgets.QVBoxLayout(root)
        root_lay.setContentsMargins(6, 6, 6, 6)
        root_lay.setSpacing(6)
        root_lay.addWidget(self.header)
        root_lay.addWidget(self.body_split, 1)
        self.setCentralWidget(root)

        # Sync initial mode.
        self._on_layout_changed()

        # If cell size changes, keep header height tight.
        try:
            self.bar.size.valueChanged.connect(self._apply_strip_header_height)
        except Exception:
            pass

        # : Minimal "auto-visible" startup pass.
        # One-shot hook; triggered by run_qt() after win.show().
        self._did_post_startup = False

        # : Qt autosave
        # Hard-disabled for release stability: autosave/restore previously caused
        # confusing startup states (e.g., stale layers from prior demos).
        self._autosave_last_rev = -1
        self._autosave_last_t = 0.0
        self._autosave_timer = None

    # : ensure changes are visible immediately on launch (no manual refresh clicks).
    def post_startup_init(self):
        try:
            if getattr(self, '_did_post_startup', False):
                return
            self._did_post_startup = True
        except Exception:
            pass

        # 1) Ensure preview engine exists (geometry + engine) so the preview paints immediately.
        try:
            fn = getattr(self.app_core, '_rebuild_full_preview_engine', None)
            if callable(fn):
                fn()
        except Exception:
            pass

        # 2) Ensure layout visibility matches current project.
        try:
            self._on_layout_changed()
        except Exception:
            pass

        # 3) Minimal, one-pass UI sync for the panels that commonly need a nudge.
        try:
            lp = getattr(getattr(self, 'controls', None), 'layers_panel', None)
            if lp is not None:
                try:
                    if hasattr(lp, 'sync_from_project'):
                        lp.sync_from_project()
                    elif hasattr(lp, 'refresh'):
                        lp.refresh()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            op = getattr(getattr(self, 'controls', None), 'operators_panel', None)
            if op is not None:
                try:
                    if hasattr(op, 'sync_from_project'):
                        op.sync_from_project()
                    elif hasattr(op, 'refresh'):
                        op.refresh()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            zp = getattr(getattr(self, 'controls', None), 'zones_panel', None)
            if zp is not None:
                # Zones/Masks/Groups panel already has its own timer refresh, but
                # call sync once to reflect migrations/diagnostics immediately.
                try:
                    if hasattr(zp, 'sync_from_project'):
                        zp.sync_from_project()
                    elif hasattr(zp, '_force_panel_refresh'):
                        zp._force_panel_refresh()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            ep = getattr(getattr(self, 'controls', None), 'export_panel', None)
            if ep is not None:
                try:
                    if hasattr(ep, 'sync_from_project'):
                        ep.sync_from_project()
                    elif hasattr(ep, '_refresh_targets'):
                        ep._refresh_targets()
                except Exception:
                    pass
        except Exception:
            pass

        # 4) Ask the preview surfaces to repaint once.
        try:
            if hasattr(self, 'preview') and self.preview is not None:
                self.preview.update()
        except Exception:
            pass
        try:
            if hasattr(self, 'matrix_preview') and self.matrix_preview is not None:
                self.matrix_preview.update()
        except Exception:
            pass

    # : throttled autosave so launch always restores last working state.
    def _autosave_tick(self):
        # Autosave is hard-disabled for release stability.
        return
        try:
            core = getattr(self, 'app_core', None)
            if core is None or not hasattr(core, 'project'):
                return
            rev = 0
            try:
                rev = int(core.project_revision())
            except Exception:
                rev = 0
            if rev <= int(getattr(self, '_autosave_last_rev', -1)):
                return
            now = time.time()
            last_t = float(getattr(self, '_autosave_last_t', 0.0) or 0.0)
            # throttle actual disk writes
            if (now - last_t) < 2.0:
                return
            write_autosave(core.project)
            self._autosave_last_rev = rev
            self._autosave_last_t = now
        except Exception:
            return

    def closeEvent(self, event):
        # Autosave disabled; proceed with normal close.
        try:
            return super().closeEvent(event)
        except Exception:
            try:
                event.accept()
            except Exception:
                pass

    def _apply_strip_header_height(self):
        try:
            cell = int(getattr(self.bar, "led_px", 12) or 12)
        except Exception:
            cell = 12
        # bar row (~32px) + preview cell row + padding
        total_h = 40 + int(cell) + 24
        try:
            self.preview.setFixedHeight(int(cell) + 26)
        except Exception:
            pass
        try:
            self.header.setMinimumHeight(int(total_h))
            self.header.setMaximumHeight(int(total_h))
        except Exception:
            pass

    def _on_layout_changed(self):
        """Switch UI without tabs: strip header vs matrix preview."""
        try:
            shape = (self.app_core.project.get("layout") or {}).get("shape", "strip")
        except Exception:
            shape = "strip"

        if shape == "strip":
            self.header.setVisible(True)
            self.matrix_preview.setVisible(False)
            # give controls the full width when matrix is hidden
            try:
                self.body_split.setSizes([1100, 0])
            except Exception:
                pass
        else:
            self.header.setVisible(False)
            self.matrix_preview.setVisible(True)
            try:
                self.body_split.setSizes([360, 740])
            except Exception:
                pass


    def _on_matrix_jump(self, idx: int):
        try:
            if hasattr(self.matrix_preview, "center_on_index"):
                self.matrix_preview.center_on_index(int(idx))
        except Exception:
            pass

    def _on_matrix_fit(self):
        # Fit-to-view: adjust matrix preview zoom so the selected matrix fills the available area.
        try:
            if hasattr(self.matrix_preview, "fit_to_view"):
                self.matrix_preview.fit_to_view()
                # Sync slider to actual zoom.
                try:
                    pct = int(round(float(getattr(self.matrix_preview, "_zoom", 1.0)) * 100.0))
                    self.controls.mz_slider.blockSignals(True)
                    self.controls.mz_slider.setValue(max(25, min(400, pct)))
                    self.controls.mz_slider.blockSignals(False)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_matrix_zoom_changed(self, pct: int):
        try:
            if hasattr(self.matrix_preview, "set_zoom_percent"):
                self.matrix_preview.set_zoom_percent(int(pct))
        except Exception:
            pass


def run_qt(app_core) -> None:
    app = QtWidgets.QApplication(sys.argv)
    _install_global_excepthook('Modulo')
    win = QtMainWindow(app_core)
    # Ensure the window is resizable / maximizable under Linux WMs (XFCE/KDE/GNOME).
    try:
        win.setMinimumSize(900, 520)
    except Exception:
        pass
    try:
        # QWIDGETSIZE_MAX is 16777215; use explicit values for compatibility.
        win.setMaximumSize(16777215, 16777215)
    except Exception:
        pass
    win.resize(1180, 640)
    win.show()
    # : one-shot post-startup sync (after show so sizes are valid).
    try:
        QtCore.QTimer.singleShot(0, getattr(win, 'post_startup_init'))
    except Exception:
        try:
            getattr(win, 'post_startup_init')()
        except Exception:
            pass
    app.exec()
def _wrap_tab_widget(inner):
    """Wrap a tab's content in a scroll area (Qt5/Qt6 compatible)."""
    s = QtWidgets.QScrollArea()
    s.setWidgetResizable(True)
    # Frame removal differs across Qt bindings
    try:
        s.setFrameShape(QtWidgets.QFrame.NoFrame)  # PyQt5
    except Exception:
        try:
            s.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)  # PyQt6
        except Exception:
            pass
    # Scrollbar policy enums differ too
    try:
        s.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        s.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    except Exception:
        try:
            s.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            s.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except Exception:
            pass
    s.setWidget(inner)
    return s
