from __future__ import annotations

from typing import Optional, Dict, Any, Tuple

import time

try:
    from PySide6.QtCore import Qt, Signal, QTimer  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QTextEdit, QGroupBox,
        QHBoxLayout, QCheckBox, QComboBox, QSizePolicy, QSlider, QSpinBox
    )
    from PySide6.QtGui import QPainter, QColor, QPen  # type: ignore
except Exception:  # pragma: no cover
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal  # type: ignore
    from PyQt6.QtWidgets import (  # type: ignore
        QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QTextEdit, QGroupBox,
        QHBoxLayout, QCheckBox, QComboBox, QSizePolicy, QSlider, QSpinBox
    )
    from PyQt6.QtGui import QPainter, QColor, QPen  # type: ignore

from app.eras.era_history import get_era, get_eras

# Qt6 enum compatibility
_QFRAME_HLINE = getattr(getattr(QFrame, 'Shape', None), 'HLine', getattr(QFrame, 'HLine', None))
_QFRAME_SUNKEN = getattr(getattr(QFrame, 'Shadow', None), 'Sunken', getattr(QFrame, 'Sunken', None))
_QT_ALIGN_LEFT = getattr(Qt, 'AlignLeft', getattr(getattr(Qt, 'AlignmentFlag', None), 'AlignLeft', None)) or 0
_QT_HORIZONTAL = getattr(Qt, "Horizontal", getattr(getattr(Qt, "Orientation", None), "Horizontal", None)) or 0


class _WorkbenchPreview(QWidget):
    """Small preview for era workbench.

    - indicator: single dot
    - strip: row of N pixels with an active index
    - matrix: WxH grid with a cursor
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state: Dict[str, Any] = {}
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Keep the pulse preview animated without touching the main engine.
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def set_state(self, state: Dict[str, Any]):
        self.state = dict(state or {})
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()

        layout_type = str(self.state.get("layout_type", "indicator"))
        power = bool(self.state.get("power", False))
        mode = str(self.state.get("mode", "steady")).strip().lower()
        pulse_rate = str(self.state.get("pulse_rate", "slow")).strip().lower()
        brightness = int(self.state.get("brightness", 100) or 100)
        brightness = max(0, min(100, brightness))

        # Simple deterministic pulse preview.
        lit = power
        if power and mode == "pulse":
            hz = 2.0 if pulse_rate == "fast" else 1.0
            lit = (int(time.monotonic() * hz * 2.0) % 2) == 0

        color = self.state.get("color", (255, 0, 0))
        r, g, b = color if isinstance(color, (tuple, list)) and len(color) == 3 else (255, 0, 0)
        scale = brightness / 100.0
        on_col = QColor(int(r * scale), int(g * scale), int(b * scale))
        off_col = QColor(20, 20, 20)

        pen = QPen(QColor(60, 60, 60))
        painter.setPen(pen)

        if layout_type == "strip":
            n = int(self.state.get("led_count", 30) or 30)
            n = max(1, min(60, n))
            active = int(self.state.get("active_index", 0) or 0)
            active = max(0, min(n - 1, active))
            pad = 8
            cell = max(6, min(14, (w - pad * 2) // n))
            x0 = (w - cell * n) // 2
            y0 = (h - cell) // 2
            for i in range(n):
                x = x0 + i * cell
                painter.setBrush(on_col if (lit and i == active) else off_col)
                painter.drawRect(x, y0, cell - 1, cell - 1)
            return

        if layout_type == "matrix":
            mw = int(self.state.get("matrix_w", 8) or 8)
            mh = int(self.state.get("matrix_h", 8) or 8)
            mw = max(4, min(16, mw))
            mh = max(4, min(16, mh))
            cx = int(self.state.get("cursor_x", 0) or 0)
            cy = int(self.state.get("cursor_y", 0) or 0)
            cx = max(0, min(mw - 1, cx))
            cy = max(0, min(mh - 1, cy))
            pad = 8
            cell = max(6, min(14, min((w - pad * 2) // mw, (h - pad * 2) // mh)))
            grid_w = cell * mw
            grid_h = cell * mh
            x0 = (w - grid_w) // 2
            y0 = (h - grid_h) // 2
            for y in range(mh):
                for x in range(mw):
                    painter.setBrush(on_col if (lit and x == cx and y == cy) else off_col)
                    painter.drawRect(x0 + x * cell, y0 + y * cell, cell - 1, cell - 1)
            return

        # indicator default
        radius = 18
        cx = w // 2
        cy = h // 2
        painter.setBrush(on_col if lit else off_col)
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)


class EraPanel(QWidget):
    era_completed = Signal()

    def __init__(self, app_core, parent=None):
        super().__init__(parent)
        self.app_core = app_core

        self._display_era_id: Optional[str] = None  # browsing without unlocking
        self._wb_state: Dict[str, Any] = {}
        self._wb_verified: Dict[str, bool] = {}

        layout = QVBoxLayout(self)

        self.h_title = QLabel("LED Era System")
        self.h_title.setStyleSheet("font-size: 18px; font-weight: 800;")
        layout.addWidget(self.h_title)

        self.h_sub = QLabel(
            "Modulo unlocks capabilities through the real history of LEDs. "
            "Each era focuses on what was possible at the time."
        )
        self.h_sub.setWordWrap(True)
        layout.addWidget(self.h_sub)

        # Browse row (read any era without unlocking)
        browse_row = QHBoxLayout()
        browse_row.addWidget(QLabel("Browse:"))
        self.browse_combo = QComboBox()
        self.browse_combo.currentIndexChanged.connect(self._on_browse_changed)
        browse_row.addWidget(self.browse_combo, stretch=1)
        self.btn_jump_active = QPushButton("Jump to current")
        self.btn_jump_active.clicked.connect(self._jump_to_active)
        browse_row.addWidget(self.btn_jump_active)
        layout.addLayout(browse_row)

        sep = QFrame()
        sep.setFrameShape(_QFRAME_HLINE)
        sep.setFrameShadow(_QFRAME_SUNKEN)
        layout.addWidget(sep)

        self.era_title = QLabel("")
        self.era_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(self.era_title)

        self.era_meta = QLabel("")
        self.era_meta.setWordWrap(True)
        layout.addWidget(self.era_meta)

        self.era_possible = QLabel("")
        self.era_possible.setWordWrap(True)
        layout.addWidget(self.era_possible)

        # ---- Workbench ----
        self.wb_group = QGroupBox("Era workbench")
        wb = QVBoxLayout(self.wb_group)

        self.wb_preview = _WorkbenchPreview()
        wb.addWidget(self.wb_preview)

        self.wb_hint = QLabel("")
        self.wb_hint.setWordWrap(True)
        wb.addWidget(self.wb_hint)

        # Controls row 1
        row1 = QHBoxLayout()
        self.wb_power = QCheckBox("Power")
        self.wb_power.stateChanged.connect(self._on_wb_changed)
        row1.addWidget(self.wb_power)

        self.wb_mode = QComboBox()
        self.wb_mode.currentIndexChanged.connect(self._on_wb_changed)
        row1.addWidget(self.wb_mode)

        self.wb_color = QComboBox()
        self.wb_color.currentIndexChanged.connect(self._on_wb_changed)
        row1.addWidget(self.wb_color)

        self.wb_pulse_rate = QComboBox()
        self.wb_pulse_rate.currentIndexChanged.connect(self._on_wb_changed)
        row1.addWidget(self.wb_pulse_rate)

        row1.addStretch(1)
        wb.addLayout(row1)

        # Controls row 2 (brightness / sliders)
        row2 = QHBoxLayout()
        self.wb_brightness_label = QLabel("Brightness")
        row2.addWidget(self.wb_brightness_label)
        self.wb_brightness = QSlider(_QT_HORIZONTAL)
        self.wb_brightness.setMinimum(0)
        self.wb_brightness.setMaximum(100)
        self.wb_brightness.setValue(100)
        self.wb_brightness.valueChanged.connect(self._on_wb_changed)
        row2.addWidget(self.wb_brightness, stretch=1)
        wb.addLayout(row2)

        # RGB controls (1993)
        self.rgb_group = QGroupBox("RGB mix")
        rgb = QVBoxLayout(self.rgb_group)
        self.rgb_r = QSlider(_QT_HORIZONTAL); self.rgb_r.setRange(0, 255); self.rgb_r.setValue(255); self.rgb_r.valueChanged.connect(self._on_wb_changed)
        self.rgb_g = QSlider(_QT_HORIZONTAL); self.rgb_g.setRange(0, 255); self.rgb_g.setValue(0); self.rgb_g.valueChanged.connect(self._on_wb_changed)
        self.rgb_b = QSlider(_QT_HORIZONTAL); self.rgb_b.setRange(0, 255); self.rgb_b.setValue(0); self.rgb_b.valueChanged.connect(self._on_wb_changed)
        rgb.addWidget(QLabel("R")); rgb.addWidget(self.rgb_r)
        rgb.addWidget(QLabel("G")); rgb.addWidget(self.rgb_g)
        rgb.addWidget(QLabel("B")); rgb.addWidget(self.rgb_b)
        wb.addWidget(self.rgb_group)

        # White type (1996)
        self.white_group = QGroupBox("White type")
        wg = QHBoxLayout(self.white_group)
        self.wb_white_type = QComboBox()
        self.wb_white_type.currentIndexChanged.connect(self._on_wb_changed)
        wg.addWidget(self.wb_white_type, stretch=1)
        wb.addWidget(self.white_group)

        # Matrix controls (2000s)
        self.matrix_group = QGroupBox("Matrix")
        mg = QHBoxLayout(self.matrix_group)
        self.btn_move = QPushButton("Move dot")
        self.btn_move.clicked.connect(self._on_matrix_move)
        mg.addWidget(self.btn_move)
        self.btn_scroll = QPushButton("Scroll")
        self.btn_scroll.clicked.connect(self._on_matrix_scroll)
        mg.addWidget(self.btn_scroll)
        wb.addWidget(self.matrix_group)

        # Addressable strip controls (2012)
        self.strip_group = QGroupBox("Strip")
        sg = QHBoxLayout(self.strip_group)
        sg.addWidget(QLabel("Index"))
        self.wb_index = QSpinBox()
        self.wb_index.setRange(0, 59)
        self.wb_index.valueChanged.connect(self._on_wb_changed)
        sg.addWidget(self.wb_index)
        wb.addWidget(self.strip_group)

        # Verify row
        vr = QHBoxLayout()
        self.wb_verify = QPushButton("Verify this era")
        self.wb_verify.clicked.connect(self._on_verify)
        vr.addWidget(self.wb_verify)
        self.wb_status = QLabel("")
        self.wb_status.setWordWrap(True)
        vr.addWidget(self.wb_status, stretch=1)
        wb.addLayout(vr)

        layout.addWidget(self.wb_group)

        self.btn_continue = QPushButton("Continue")
        self.btn_continue.clicked.connect(self._on_continue)
        layout.addWidget(self.btn_continue, alignment=_QT_ALIGN_LEFT)

        self.cap_text = QTextEdit()
        self.cap_text.setReadOnly(True)
        self.cap_text.setVisible(False)
        self.cap_text.setMinimumHeight(220)
        self.cap_text.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self.cap_text)

        layout.addStretch(1)

        self._populate_browse()
        self.refresh()

    # ---------- helpers ----------
    def _active_era_id(self) -> str:
        return getattr(self.app_core, "get_era_id", lambda: "era_1962_red")()

    def _display_id(self) -> str:
        return self._display_era_id or self._active_era_id()

    def _populate_browse(self):
        self.browse_combo.blockSignals(True)
        self.browse_combo.clear()
        for e in get_eras():
            self.browse_combo.addItem(e.title, e.era_id)
        self.browse_combo.blockSignals(False)

    def _on_browse_changed(self, idx: int):
        try:
            era_id = self.browse_combo.itemData(idx)
            if isinstance(era_id, str) and era_id:
                self._display_era_id = era_id
        except Exception:
            self._display_era_id = None
        self.refresh()

    def _jump_to_active(self):
        self._display_era_id = None
        self.refresh()

    # ---------- workbench state ----------
    def _seed_state_for(self, era_id: str) -> Dict[str, Any]:
        # defaults that match the spec
        if era_id == "era_1962_red":
            return {"layout_type": "strip", "led_count": 1, "color": (255, 0, 0),
                    "power": False, "mode": "steady", "brightness": 100,
                    "did_dim": False, "did_pulse": False}
        if era_id == "era_1972_yellow_green":
            return {"layout_type": "strip", "led_count": 1, "color": (255, 0, 0),
                    "power": False, "mode": "steady", "brightness": 100,
                    "selected_colors": set(), "did_color_change": False,
                    "did_dim": False, "did_pulse": False}
        if era_id == "era_1980s_high_brightness":
            return {"layout_type": "strip", "led_count": 1, "color": (255, 0, 0),
                    "power": False, "mode": "pulse", "pulse_rate": "slow",
                    "did_fast_pulse": False}
        if era_id == "era_1993_blue":
            return {"layout_type": "strip", "led_count": 1, "color": (0, 0, 255),
                    "power": False, "rgb": (255, 0, 0), "brightness": 100,
                    "did_dim": False, "did_white_mix": False, "last_rgb": None}
        if era_id == "era_1996_white":
            return {"layout_type": "strip", "led_count": 1, "color": (255, 255, 255),
                    "power": False, "white_type": "cool", "brightness": 100,
                    "did_dim": False, "did_white_change": False}
        if era_id == "era_2000s_matrices":
            return {"layout_type": "matrix", "matrix_w": 8, "matrix_h": 8,
                    "power": False, "color": (255, 0, 0),
                    "cursor_x": 0, "cursor_y": 0,
                    "did_move": False, "did_scroll": False}
        if era_id == "era_2012_addressable":
            return {"layout_type": "strip", "led_count": 30, "power": False,
                    "active_index": 0, "mode": "single",
                    "color": (255, 0, 0),
                    "did_index_move": False, "did_mode_change": False, "did_color_change": False,
                    "last_index": 0}
        # plateau / now: no workbench
        return {"layout_type": "indicator", "led_count": 1, "power": False, "color": (255, 0, 0)}

    def _ensure_state(self):
        era_id = self._display_id()
        if not self._wb_state or self._wb_state.get("_era_id") != era_id:
            self._wb_state = self._seed_state_for(era_id)
            self._wb_state["_era_id"] = era_id

    def _set_color(self, name: str):
        n = name.strip().lower()
        if n == "red":
            self._wb_state["color"] = (255, 0, 0)
        elif n == "yellow":
            self._wb_state["color"] = (255, 220, 0)
        elif n == "green":
            self._wb_state["color"] = (0, 255, 0)
        elif n == "blue":
            self._wb_state["color"] = (0, 0, 255)
        elif n == "white":
            self._wb_state["color"] = (255, 255, 255)

    # ---------- UI wiring ----------
    def _configure_controls_for(self, era_id: str):
        # hide all optional groups by default
        self.wb_group.setVisible(True)
        self.rgb_group.setVisible(False)
        self.white_group.setVisible(False)
        self.matrix_group.setVisible(False)
        self.strip_group.setVisible(False)

        # default control visibility
        self.wb_power.setVisible(True)
        self.wb_mode.setVisible(True)
        self.wb_color.setVisible(False)
        self.wb_pulse_rate.setVisible(False)
        self.wb_brightness.setVisible(False)
        self.wb_brightness_label.setVisible(False)

        # plateau / now: no workbench
        if era_id in ("era_usage_plateau", "era_now"):
            self.wb_group.setVisible(False)
            return

        if era_id == "era_1962_red":
            self.wb_mode.clear()
            self.wb_mode.addItems(["steady", "pulse"])
            self.wb_brightness.setVisible(True)
            self.wb_brightness_label.setVisible(True)

            # Era 1962: keep the interface physically-authentic.
            # Power is the only control visible until the LED is turned on.
            if not bool(self._wb_state.get("power", False)):
                self.wb_mode.setVisible(False)
                self.wb_brightness.setVisible(False)
                self.wb_brightness_label.setVisible(False)
            else:
                self.wb_mode.setVisible(True)
                self.wb_brightness.setVisible(True)
                self.wb_brightness_label.setVisible(True)

        elif era_id == "era_1972_yellow_green":
            self.wb_mode.clear()
            self.wb_mode.addItems(["steady", "pulse"])
            self.wb_color.setVisible(True)
            self.wb_color.clear()
            self.wb_color.addItems(["red", "yellow", "green"])
            self.wb_brightness.setVisible(True)
            self.wb_brightness_label.setVisible(True)

            # Same physical-authentic flow as 1962: start with Power only.
            if not bool(self._wb_state.get("power", False)):
                self.wb_mode.setVisible(False)
                self.wb_color.setVisible(False)
                self.wb_brightness.setVisible(False)
                self.wb_brightness_label.setVisible(False)

        elif era_id == "era_1980s_high_brightness":
            self.wb_mode.clear()
            self.wb_mode.addItems(["pulse"])
            self.wb_color.setVisible(True)
            self.wb_color.clear()
            self.wb_color.addItems(["red", "yellow", "green"])
            self.wb_pulse_rate.setVisible(True)
            self.wb_pulse_rate.clear()
            self.wb_pulse_rate.addItems(["slow", "fast"])

            # Physical-authentic flow: start with Power only (no controls until ON).
            if not bool(self._wb_state.get("power", False)):
                self.wb_color.setVisible(False)
                self.wb_pulse_rate.setVisible(False)

        elif era_id == "era_1993_blue":
            self.wb_mode.clear()
            self.wb_mode.addItems(["mix"])
            self.rgb_group.setVisible(True)
            self.wb_brightness.setVisible(True)
            self.wb_brightness_label.setVisible(True)

        elif era_id == "era_1996_white":
            self.wb_mode.clear()
            self.wb_mode.addItems(["white"])
            self.white_group.setVisible(True)
            self.wb_white_type.clear()
            self.wb_white_type.addItems(["cool", "neutral", "warm"])
            self.wb_brightness.setVisible(True)
            self.wb_brightness_label.setVisible(True)

        elif era_id == "era_2000s_matrices":
            self.wb_mode.clear()
            self.wb_mode.addItems(["matrix"])
            self.matrix_group.setVisible(True)

        elif era_id == "era_2012_addressable":
            self.wb_mode.clear()
            self.wb_mode.addItems(["single", "chase", "wipe"])
            self.wb_color.setVisible(True)
            self.wb_color.clear()
            self.wb_color.addItems(["red", "green", "blue", "white", "yellow"])
            self.strip_group.setVisible(True)
            self.wb_index.setRange(0, int(self._wb_state.get("led_count", 30)) - 1)

    def _sync_controls_from_state(self):
        s = self._wb_state
        self.wb_power.blockSignals(True)
        self.wb_power.setChecked(bool(s.get("power", False)))
        self.wb_power.blockSignals(False)

        # mode
        try:
            mode = str(s.get("mode", "")).strip().lower()
            mi = self.wb_mode.findText(mode)
            if mi >= 0:
                self.wb_mode.blockSignals(True)
                self.wb_mode.setCurrentIndex(mi)
                self.wb_mode.blockSignals(False)
        except Exception:
            pass

        # color combo
        if self.wb_color.isVisible():
            col = s.get("color", (255, 0, 0))
            name = "red"
            if tuple(col) == (255, 220, 0): name = "yellow"
            elif tuple(col) == (0, 255, 0): name = "green"
            elif tuple(col) == (0, 0, 255): name = "blue"
            elif tuple(col) == (255, 255, 255): name = "white"
            ci = self.wb_color.findText(name)
            if ci >= 0:
                self.wb_color.blockSignals(True)
                self.wb_color.setCurrentIndex(ci)
                self.wb_color.blockSignals(False)

        # pulse rate
        if self.wb_pulse_rate.isVisible():
            pr = str(s.get("pulse_rate", "slow"))
            pi = self.wb_pulse_rate.findText(pr)
            if pi >= 0:
                self.wb_pulse_rate.blockSignals(True)
                self.wb_pulse_rate.setCurrentIndex(pi)
                self.wb_pulse_rate.blockSignals(False)

        # brightness
        if self.wb_brightness.isVisible():
            self.wb_brightness.blockSignals(True)
            self.wb_brightness.setValue(int(s.get("brightness", 100)))
            self.wb_brightness.blockSignals(False)

        # rgb
        if self.rgb_group.isVisible():
            r,g,b = s.get("rgb", (255,0,0))
            self.rgb_r.blockSignals(True); self.rgb_r.setValue(int(r)); self.rgb_r.blockSignals(False)
            self.rgb_g.blockSignals(True); self.rgb_g.setValue(int(g)); self.rgb_g.blockSignals(False)
            self.rgb_b.blockSignals(True); self.rgb_b.setValue(int(b)); self.rgb_b.blockSignals(False)

        # white type
        if self.white_group.isVisible():
            wt = str(s.get("white_type", "cool"))
            wi = self.wb_white_type.findText(wt)
            if wi >= 0:
                self.wb_white_type.blockSignals(True)
                self.wb_white_type.setCurrentIndex(wi)
                self.wb_white_type.blockSignals(False)

        # index
        if self.strip_group.isVisible():
            self.wb_index.blockSignals(True)
            self.wb_index.setValue(int(s.get("active_index", 0)))
            self.wb_index.blockSignals(False)

    def _update_preview(self):
        self.wb_preview.set_state(self._wb_state)

    def _on_wb_changed(self, *args):
        self._ensure_state()
        era_id = self._display_id()
        s = self._wb_state

        # power
        s["power"] = self.wb_power.isChecked()

        # Era 1962: reveal mode/brightness only once powered.
        if era_id == "era_1962_red":
            self.wb_mode.setVisible(bool(s["power"]))
            self.wb_brightness.setVisible(bool(s["power"]))
            self.wb_brightness_label.setVisible(bool(s["power"]))

        # Era 1972: still a physical indicator era.
        # Keep the UX consistent: only Power is visible until the LED is on.
        if era_id == "era_1972_yellow_green":
            self.wb_mode.setVisible(bool(s["power"]))
            self.wb_color.setVisible(bool(s["power"]))
            self.wb_brightness.setVisible(bool(s["power"]))
            self.wb_brightness_label.setVisible(bool(s["power"]))

        # Era 1980s: alert indicator era.
        # Keep the same UX rule: only Power is visible until the LED is on.
        if era_id == "era_1980s_high_brightness":
            self.wb_color.setVisible(bool(s["power"]))
            self.wb_pulse_rate.setVisible(bool(s["power"]))

        # brightness
        if self.wb_brightness.isVisible():
            new_b = int(self.wb_brightness.value())
            if "brightness" in s and new_b != int(s.get("brightness", 100)):
                s["did_dim"] = True
            s["brightness"] = new_b

        # mode
        if self.wb_mode.isVisible():
            m = self.wb_mode.currentText().strip().lower()
            prev = str(s.get("mode", "")).strip().lower()
            s["mode"] = m
            if era_id in ("era_1962_red", "era_1972_yellow_green") and m == "pulse":
                s["did_pulse"] = True
            if era_id == "era_2012_addressable" and m != prev:
                s["did_mode_change"] = True

        # color selection
        if self.wb_color.isVisible():
            cname = self.wb_color.currentText().strip().lower()
            prev_col = tuple(s.get("color", (255, 0, 0)))
            self._set_color(cname)
            if era_id == "era_1972_yellow_green":
                sc = s.get("selected_colors")
                if not isinstance(sc, set):
                    sc = set()
                sc.add(cname)
                s["selected_colors"] = sc
                if tuple(s.get("color")) != prev_col:
                    s["did_color_change"] = True
            if era_id == "era_2012_addressable" and tuple(s.get("color")) != prev_col:
                s["did_color_change"] = True

        # pulse rate
        if self.wb_pulse_rate.isVisible():
            pr = self.wb_pulse_rate.currentText().strip().lower()
            s["pulse_rate"] = pr
            if era_id == "era_1980s_high_brightness" and pr == "fast":
                s["did_fast_pulse"] = True

        # rgb
        if self.rgb_group.isVisible():
            rgb = (int(self.rgb_r.value()), int(self.rgb_g.value()), int(self.rgb_b.value()))
            last = s.get("last_rgb")
            if last is None:
                s["last_rgb"] = rgb
            s["rgb"] = rgb
            s["color"] = rgb

            # Era 1993: demonstrate practical mixing by making WHITE (R≈G≈B).
            # We treat "white" as equal channels within a small tolerance and nonzero output.
            if era_id == "era_1993_blue":
                r, g, b = rgb
                tol = 8
                if max(r, g, b) > 0 and (max(r, g, b) - min(r, g, b)) <= tol:
                    s["did_white_mix"] = True

        # white type
        if self.white_group.isVisible():
            wt = self.wb_white_type.currentText().strip().lower()
            prev = s.get("white_type", "cool")
            s["white_type"] = wt
            if wt != prev:
                s["did_white_change"] = True
            # map to discrete white-ish colour for preview only
            if wt == "cool":
                s["color"] = (220, 235, 255)
            elif wt == "neutral":
                s["color"] = (245, 245, 235)
            else:
                s["color"] = (255, 235, 210)

        # addressable index
        if self.strip_group.isVisible():
            new_i = int(self.wb_index.value())
            last_i = int(s.get("last_index", new_i))
            s["active_index"] = new_i
            if new_i != last_i:
                s["did_index_move"] = True
            s["last_index"] = new_i

        self._update_preview()
        self._update_buttons()

    def _on_matrix_move(self):
        self._ensure_state()
        s = self._wb_state
        # simple deterministic move: advance x, wrap, then y
        mw = int(s.get("matrix_w", 8)); mh = int(s.get("matrix_h", 8))
        x = int(s.get("cursor_x", 0)); y = int(s.get("cursor_y", 0))
        x += 1
        if x >= mw:
            x = 0
            y = (y + 1) % mh
        s["cursor_x"] = x; s["cursor_y"] = y
        s["did_move"] = True
        self._update_preview()
        self._update_buttons()

    def _on_matrix_scroll(self):
        self._ensure_state()
        s = self._wb_state
        s["did_scroll"] = True
        # for preview: move cursor one step
        self._on_matrix_move()

    # ---------- verify / progress ----------
    def _verify_state(self, era_id: str) -> Tuple[bool, str]:
        s = self._wb_state
        if era_id == "era_1962_red":
            if str(s.get("layout_type")) != "strip" or int(s.get("led_count", 0)) != 1:
                return False, "Layout must be a strip with exactly 1 LED."
            if tuple(s.get("color", ())) != (255, 0, 0):
                return False, "LED must be red."
            if not bool(s.get("power")):
                return False, "Turn the LED ON."
            if not bool(s.get("did_pulse")):
                return False, "Switch to PULSE at least once."
            if not bool(s.get("did_dim")):
                return False, "Change brightness at least once (DIM)."
            return True, "Verified ✅"
        if era_id == "era_1972_yellow_green":
            if not bool(s.get("power")):
                return False, "Turn the indicator ON."
            if not bool(s.get("did_pulse")):
                return False, "Use PULSE at least once."
            if not bool(s.get("did_dim")):
                return False, "Dim at least once."
            sc = s.get("selected_colors")
            if not isinstance(sc, set) or len(sc) < 2:
                return False, "Select at least two colours."
            return True, "Verified ✅"
        if era_id == "era_1980s_high_brightness":
            if not bool(s.get("power")):
                return False, "Turn the indicator ON."
            if not bool(s.get("did_fast_pulse")):
                return False, "Set pulse rate to FAST."
            return True, "Verified ✅"
        if era_id == "era_1993_blue":
            if not bool(s.get("power")):
                return False, "Turn the LED ON."
            if not bool(s.get("did_white_mix")):
                return False, "Mix RGB to make WHITE (R≈G≈B)."
            return True, "Verified ✅"
        if era_id == "era_1996_white":
            if not bool(s.get("power")):
                return False, "Turn the lamp ON."
            if not bool(s.get("did_white_change")):
                return False, "Change the white type at least once."
            if not bool(s.get("did_dim")):
                return False, "Dim at least once."
            return True, "Verified ✅"
        if era_id == "era_2000s_matrices":
            if not bool(s.get("power")):
                return False, "Power ON."
            if not bool(s.get("did_move")):
                return False, "Move the dot (prove coordinates)."
            if not bool(s.get("did_scroll")):
                return False, "Trigger scrolling/motion."
            return True, "Verified ✅"
        if era_id == "era_2012_addressable":
            if not bool(s.get("power")):
                return False, "Power ON."
            if not bool(s.get("did_index_move")):
                return False, "Move the pixel to a different index."
            if not bool(s.get("did_mode_change")):
                return False, "Change the animation mode."
            if not bool(s.get("did_color_change")):
                return False, "Change colour during motion."
            return True, "Verified ✅"
        # plateau/now: no verify needed
        return True, "No verification required."

    def _on_verify(self):
        era_id = self._active_era_id()
        # Only verify when viewing the active era
        if self._display_id() != era_id:
            self.wb_status.setText("Browsing only. Jump to current era to verify.")
            return
        ok, msg = self._verify_state(era_id)
        self.wb_status.setText(msg)
        if ok:
            self._wb_verified[era_id] = True
        self._update_buttons()

    def _update_buttons(self):
        active = self._active_era_id()
        display = self._display_id()
        is_active_view = (active == display)

        # Continue label
        if display == "era_now" and is_active_view:
            self.btn_continue.setText("Open Modulo")
        else:
            self.btn_continue.setText("Continue")

        # enable continue?
        if not is_active_view:
            self.btn_continue.setEnabled(False)
            return

        # plateau and now do not require verification
        if active in ("era_usage_plateau", "era_now"):
            self.btn_continue.setEnabled(True)
            self.wb_verify.setEnabled(False)
            self.wb_verify.setText("No verification")
            return

        # default verify button state
        self.wb_verify.setEnabled(is_active_view)
        self.wb_verify.setText("Verify this era")

        # If already verified, reflect that in the UI
        if bool(self._wb_verified.get(active, False)):
            self.wb_verify.setEnabled(False)
            self.wb_verify.setText("Verified ✅")

        self.btn_continue.setEnabled(bool(self._wb_verified.get(active, False)))

    def _on_continue(self):
        eras = get_eras()
        cur = self._active_era_id()
        ids = [e.era_id for e in eras]
        if cur not in ids:
            return
        i = ids.index(cur)

        # Final panel -> open full app
        if cur == "era_now":
            if hasattr(self.app_core, "set_era_complete"):
                self.app_core.set_era_complete(True)
            self.era_completed.emit()
            return

        # Require verification on capability eras
        if cur not in ("era_usage_plateau", "era_now") and not bool(self._wb_verified.get(cur, False)):
            self.wb_status.setText("Verify this era to continue.")
            return

        if i + 1 < len(ids):
            nxt = ids[i + 1]
            if hasattr(self.app_core, "set_era_id"):
                self.app_core.set_era_id(nxt)
            self._display_era_id = None
            self.refresh()

    # ---------- render ----------
    def refresh(self):
        # Update browse selection text/ID
        display_id = self._display_id()
        try:
            # align browse combo to display id
            for i in range(self.browse_combo.count()):
                if self.browse_combo.itemData(i) == display_id:
                    self.browse_combo.blockSignals(True)
                    self.browse_combo.setCurrentIndex(i)
                    self.browse_combo.blockSignals(False)
                    break
        except Exception:
            pass

        era = get_era(display_id)
        self.era_title.setText(era.title)
        self.era_meta.setText(f"{era.start_year} — {era.key_person}\n{era.summary}")

        bullets = "\n".join([f"• {x}" for x in (era.what_was_possible or [])])
        self.era_possible.setText(bullets)

        # Setup workbench for this display era
        self._ensure_state()
        self._configure_controls_for(display_id)
        self._sync_controls_from_state()
        self._update_preview()

        # For plateau/now: disable verify and show button behavior
        if display_id in ("era_usage_plateau", "era_now"):
            self.wb_status.setText("")
        self._update_buttons()