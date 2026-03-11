
from __future__ import annotations

import time

from qt.preview_shared import QtCore, QtGui, QtWidgets, get_surface_spec, get_surface_snapshot, get_surface_count

class StripPreviewBar(QtWidgets.QWidget):
    """Top strip bar shown only when the canonical surface kind is strip.

    Presentation modes:
      - full: controls + mini preview
      - compact: mini preview only (no chrome/background bar)
    """

    def __init__(self, app_core, *, compact: bool = False):
        super().__init__()
        self.app_core = app_core

        self.compact = bool(compact)

        # IMPORTANT: QWidget has a built-in scroll() method.
        # In compact mode we do not create the scrollbar widget, so we must
        # explicitly shadow the name to avoid accidentally calling QWidget.scroll.
        self.scroll = None

        self.view_start = 0
        self.led_px = 12  # default pixels per LED cell
        self._preview_w: int | None = None  # set by PreviewWidget
        self._last_anchor: int | None = None  # for shift-click ranges

        # Compact mode: only the strip preview line (no black bar).
        if self.compact:
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            self.mini_preview = StripMiniPreview(self.app_core)
            self.mini_preview.setFixedHeight(22)
            try:
                _pol = getattr(QtWidgets.QSizePolicy, 'Policy', QtWidgets.QSizePolicy)
                self.mini_preview.setSizePolicy(_pol.Expanding, _pol.Fixed)
            except Exception:
                pass
            root.addWidget(self.mini_preview)

            try:
                self.setMinimumHeight(22)
                self.setMaximumHeight(22)
            except Exception:
                pass
            try:
                self.setAutoFillBackground(False)
                self.setStyleSheet("background: transparent;")
            except Exception:
                pass

            self._update_ui()
            return

        # Full mode: Two-row header bar:
        #   row 1: controls + scroll
        #   row 2: mini strip preview (full width)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        lay = QtWidgets.QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        root.addLayout(lay)
        lay.setSpacing(10)

        lay.addWidget(QtWidgets.QLabel("LEDs:"))
        self.count = QtWidgets.QSpinBox()
        self.count.setRange(1, 50000)
        self.count.setKeyboardTracking(False)
        self.count.setValue(self._get_led_count())
        self.count.valueChanged.connect(self._on_led_count_changed)
        lay.addWidget(self.count)

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

        # Mini strip pixel preview (strip across the top of the app)
        self.mini_preview = StripMiniPreview(self.app_core)
        self.mini_preview.setFixedHeight(22)
        _pol = getattr(QtWidgets.QSizePolicy, 'Policy', QtWidgets.QSizePolicy)
        try:
            self.mini_preview.setSizePolicy(_pol.Expanding, _pol.Fixed)
        except Exception:
            pass
        root.addWidget(self.mini_preview)

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
        """Return LED count from canonical helpers when available."""
        try:
            if callable(get_surface_spec):
                spec = get_surface_spec(getattr(self.app_core, 'project', None))
            else:
                spec = None
            if spec is not None:
                return int(spec.count)
        except Exception:
            pass
        try:
            if callable(get_surface_count):
                return int(get_surface_count(getattr(self.app_core, 'project', None)) or 144)
        except Exception:
            pass
        try:
            if callable(get_surface_snapshot):
                snap = get_surface_snapshot(getattr(self.app_core, 'project', None)) or {}
                return int(snap.get('count', 144) or 144)
        except Exception:
            pass
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
            val = int(self.count.value())
            pm = getattr(self.app_core, 'pm', None)
            if pm is not None and hasattr(pm, 'guarded_set_address'):
                try:
                    if bool(pm.guarded_set_address('project.surface.count', val)) and hasattr(pm, 'get'):
                        self.app_core.project = pm.get()
                except Exception:
                    pass
            else:
                proj = self.app_core.project
                if callable(set_address):
                    proj, _did = set_address(project=proj, address='project.surface.count', value=val)
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
        # Compact mode has no controls/scroll/range label; the mini preview line
        # repaints itself directly.
        if getattr(self, 'compact', False):
            return

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
