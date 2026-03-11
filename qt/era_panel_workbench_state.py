from __future__ import annotations

from typing import Dict, Any

from qt.era_panel_workbench import _diag_exc
from app.project_model import build_surface_dict


class EraPanelWorkbenchStateMixin:
    def _seed_state_for(self, era_id: str) -> Dict[str, Any]:
        if era_id == "era_1962_red":
            return build_surface_dict(kind="strip", count=1, extras={"color": (255, 0, 0), "power": False, "mode": "steady", "did_pulse": False})
        if era_id == "era_1972_yellow_green":
            return build_surface_dict(kind="strip", count=1, extras={"color": (255, 0, 0), "power": False, "mode": "steady", "brightness": 100, "selected_colors": set(), "did_color_change": False, "did_pulse": False})
        if era_id == "era_1980s_high_brightness":
            return build_surface_dict(kind="strip", count=1, extras={"color": (255, 0, 0), "power": False, "mode": "pulse", "pulse_rate": "slow", "brightness": 100, "did_fast_pulse": False, "did_dim": False})
        if era_id == "era_1993_blue":
            return build_surface_dict(kind="strip", count=1, extras={"color": (0, 0, 255), "power": False, "rgb": (255, 0, 0), "brightness": 100, "did_mixed_rgb": False, "last_rgb": None})
        if era_id == "era_1996_white":
            return build_surface_dict(kind="strip", count=1, extras={"color": (255, 255, 255), "power": False, "white_type": "cool", "brightness": 100, "did_dim": False, "did_white_change": False})
        if era_id == "era_2000s_matrices":
            return build_surface_dict(kind="cells", width=8, height=8, extras={"power": False, "color": (255, 0, 0), "cursor_x": 0, "cursor_y": 0, "did_move": False, "did_scroll": False})
        if era_id == "era_2012_addressable":
            return build_surface_dict(kind="strip", count=30, extras={"power": False, "active_index": 0, "mode": "single", "color": (255, 0, 0), "did_index_move": False, "did_mode_change": False, "did_color_change": False, "last_index": 0})
        return build_surface_dict(kind="indicator", count=1, extras={"power": False, "color": (255, 0, 0)})

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

    def _configure_controls_for(self, era_id: str):
        self.wb_group.setVisible(True)
        self.rgb_group.setVisible(False)
        self.white_group.setVisible(False)
        self.matrix_group.setVisible(False)
        self.strip_group.setVisible(False)

        self.wb_power.setVisible(True)
        self.wb_mode.setVisible(True)
        self.wb_color.setVisible(False)
        self.wb_pulse_rate.setVisible(False)
        self.wb_brightness.setVisible(False)
        self.wb_brightness_label.setVisible(False)

        if era_id in ("era_usage_plateau", "era_now"):
            self.wb_group.setVisible(False)
            return

        if era_id == "era_1962_red":
            self.wb_mode.clear(); self.wb_mode.addItems(["steady", "pulse"])
            if not bool(self._wb_state.get("power", False)):
                self.wb_mode.setVisible(False)
        elif era_id == "era_1972_yellow_green":
            self.wb_mode.clear(); self.wb_mode.addItems(["steady", "pulse"])
            self.wb_color.setVisible(True); self.wb_color.clear(); self.wb_color.addItems(["red", "yellow"])
            if not bool(self._wb_state.get("power", False)):
                self.wb_mode.setVisible(False); self.wb_color.setVisible(False)
        elif era_id == "era_1980s_high_brightness":
            self.wb_mode.clear(); self.wb_mode.addItems(["pulse"])
            self.wb_color.setVisible(True); self.wb_color.clear(); self.wb_color.addItems(["red", "yellow", "green"])
            self.wb_pulse_rate.setVisible(True); self.wb_pulse_rate.clear(); self.wb_pulse_rate.addItems(["slow", "fast"])
            self.wb_brightness.setVisible(True); self.wb_brightness_label.setVisible(True)
            if not bool(self._wb_state.get("power", False)):
                self.wb_color.setVisible(False); self.wb_pulse_rate.setVisible(False); self.wb_brightness.setVisible(False); self.wb_brightness_label.setVisible(False)
        elif era_id == "era_1993_blue":
            self.wb_mode.clear(); self.wb_mode.addItems(["mix"])
            self.rgb_group.setVisible(True)
            self.wb_brightness.setVisible(True); self.wb_brightness_label.setVisible(True)
        elif era_id == "era_1996_white":
            self.wb_mode.clear(); self.wb_mode.addItems(["white"])
            self.white_group.setVisible(True)
            self.wb_white_type.clear(); self.wb_white_type.addItems(["cool", "neutral", "warm"])
            self.wb_brightness.setVisible(True); self.wb_brightness_label.setVisible(True)
        elif era_id == "era_2000s_matrices":
            self.wb_mode.clear(); self.wb_mode.addItems(["cells"])
            self.matrix_group.setVisible(True)
        elif era_id == "era_2012_addressable":
            self.wb_mode.clear(); self.wb_mode.addItems(["single", "chase", "wipe"])
            self.wb_color.setVisible(True); self.wb_color.clear(); self.wb_color.addItems(["red", "green", "blue", "white", "yellow"])
            self.strip_group.setVisible(True)
            self.wb_index.setRange(0, int(self._wb_state.get("count", 30)) - 1)

    def _sync_controls_from_state(self):
        s = self._wb_state
        self.wb_power.blockSignals(True); self.wb_power.setChecked(bool(s.get("power", False))); self.wb_power.blockSignals(False)
        try:
            mode = str(s.get("mode", "")).strip().lower()
            mi = self.wb_mode.findText(mode)
            if mi >= 0:
                self.wb_mode.blockSignals(True); self.wb_mode.setCurrentIndex(mi); self.wb_mode.blockSignals(False)
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")
        if self.wb_color.isVisible():
            col = s.get("color", (255, 0, 0))
            name = "red"
            if tuple(col) == (255, 220, 0): name = "yellow"
            elif tuple(col) == (0, 255, 0): name = "green"
            elif tuple(col) == (0, 0, 255): name = "blue"
            elif tuple(col) == (255, 255, 255): name = "white"
            ci = self.wb_color.findText(name)
            if ci >= 0:
                self.wb_color.blockSignals(True); self.wb_color.setCurrentIndex(ci); self.wb_color.blockSignals(False)
        if self.wb_pulse_rate.isVisible():
            pr = str(s.get("pulse_rate", "slow"))
            pi = self.wb_pulse_rate.findText(pr)
            if pi >= 0:
                self.wb_pulse_rate.blockSignals(True); self.wb_pulse_rate.setCurrentIndex(pi); self.wb_pulse_rate.blockSignals(False)
        if self.wb_brightness.isVisible():
            self.wb_brightness.blockSignals(True); self.wb_brightness.setValue(int(s.get("brightness", 100))); self.wb_brightness.blockSignals(False)
        if self.rgb_group.isVisible():
            r, g, b = tuple(s.get("rgb", (255, 0, 0)))
            for spin, val in ((self.rgb_r, r), (self.rgb_g, g), (self.rgb_b, b)):
                spin.blockSignals(True); spin.setValue(int(val)); spin.blockSignals(False)
        if self.white_group.isVisible():
            wt = str(s.get("white_type", "cool"))
            wi = self.wb_white_type.findText(wt)
            if wi >= 0:
                self.wb_white_type.blockSignals(True); self.wb_white_type.setCurrentIndex(wi); self.wb_white_type.blockSignals(False)
        if self.strip_group.isVisible():
            self.wb_index.blockSignals(True); self.wb_index.setValue(int(s.get("active_index", 0))); self.wb_index.blockSignals(False)
