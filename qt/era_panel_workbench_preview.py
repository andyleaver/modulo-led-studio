from __future__ import annotations

from qt.era_panel_workbench import _diag_exc


class EraPanelWorkbenchPreviewMixin:
    def _update_preview(self):
        self._ensure_state()
        state = self._wb_state
        widget = getattr(self, 'wb_preview', None)
        if widget is not None and hasattr(widget, 'set_state'):
            try:
                widget.set_state(dict(state))
            except Exception as exc:
                _diag_exc(exc, "qt/era_panel.py")

    def _on_wb_changed(self):
        self._ensure_state()
        s = self._wb_state
        era_id = self._display_id()

        s["power"] = bool(self.wb_power.isChecked())
        if era_id in ("era_1972_yellow_green", "era_1980s_high_brightness"):
            self.wb_color.setVisible(bool(s["power"]))
        if era_id == "era_1980s_high_brightness":
            self.wb_pulse_rate.setVisible(bool(s["power"]))
            self.wb_brightness.setVisible(bool(s["power"]))
            self.wb_brightness_label.setVisible(bool(s["power"]))

        if self.wb_brightness.isVisible():
            new_b = int(self.wb_brightness.value())
            if "brightness" in s and new_b != int(s.get("brightness", 100)):
                s["did_dim"] = True
            s["brightness"] = new_b

        if self.wb_mode.isVisible():
            mode = self.wb_mode.currentText().strip().lower()
            prev = str(s.get("mode", "")).strip().lower()
            s["mode"] = mode
            if era_id in ("era_1962_red", "era_1972_yellow_green") and mode == "pulse":
                s["did_pulse"] = True
            if era_id == "era_2012_addressable" and mode != prev:
                s["did_mode_change"] = True

        if self.wb_color.isVisible():
            cname = self.wb_color.currentText().strip().lower()
            prev_col = tuple(s.get("color", (255, 0, 0)))
            self._set_color(cname)
            if era_id == "era_1972_yellow_green":
                selected = s.get("selected_colors")
                if not isinstance(selected, set):
                    selected = set()
                selected.add(cname)
                s["selected_colors"] = selected
                if tuple(s.get("color")) != prev_col:
                    s["did_color_change"] = True
            if era_id == "era_2012_addressable" and tuple(s.get("color")) != prev_col:
                s["did_color_change"] = True

        if self.wb_pulse_rate.isVisible():
            pulse_rate = self.wb_pulse_rate.currentText().strip().lower()
            s["pulse_rate"] = pulse_rate
            if era_id == "era_1980s_high_brightness" and pulse_rate == "fast":
                s["did_fast_pulse"] = True

        if self.rgb_group.isVisible():
            rgb = (int(self.rgb_r.value()), int(self.rgb_g.value()), int(self.rgb_b.value()))
            if s.get("last_rgb") is None:
                s["last_rgb"] = rgb
            s["rgb"] = rgb
            s["color"] = rgb
            if era_id == "era_1993_blue":
                if sum(1 for c in rgb if int(c) > 0) >= 2:
                    s["did_mixed_rgb"] = True

        if self.white_group.isVisible():
            wt = self.wb_white_type.currentText().strip().lower()
            prev = s.get("white_type", "cool")
            s["white_type"] = wt
            if wt != prev:
                s["did_white_change"] = True
            if wt == "cool":
                s["color"] = (220, 235, 255)
            elif wt == "neutral":
                s["color"] = (245, 245, 235)
            else:
                s["color"] = (255, 235, 210)

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
        width = int(s.get("width", 8)); height = int(s.get("height", 8))
        x = int(s.get("cursor_x", 0)); y = int(s.get("cursor_y", 0))
        x += 1
        if x >= width:
            x = 0
            y = (y + 1) % height
        s["cursor_x"] = x; s["cursor_y"] = y
        s["did_move"] = True
        self._update_preview(); self._update_buttons()

    def _on_matrix_scroll(self):
        self._ensure_state()
        self._wb_state["did_scroll"] = True
        self._on_matrix_move()
