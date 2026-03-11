from __future__ import annotations

from typing import Tuple

from app.eras.era_history import get_era, get_eras, get_phase_note, get_workbench_for_era
from qt.era_panel_workbench import _diag_exc, QTimer


class EraPanelWorkbenchFlowMixin:
    def _verify_state(self, era_id: str) -> Tuple[bool, str]:
        s = self._wb_state
        if era_id == "era_1962_red":
            if str(s.get("kind") or "") != "strip" or int(s.get("count", 0)) != 1:
                return False, "Layout must be a strip with exactly 1 LED."
            if tuple(s.get("color", ())) != (255, 0, 0):
                return False, "LED must be red."
            if not bool(s.get("power")): return False, "Turn the LED ON."
            if not bool(s.get("did_pulse")): return False, "Switch to PULSE at least once."
            return True, "Verified ✅"
        if era_id == "era_1972_yellow_green":
            if not bool(s.get("power")): return False, "Turn the indicator ON."
            if not bool(s.get("did_pulse")): return False, "Use PULSE at least once."
            selected = s.get("selected_colors")
            if not isinstance(selected, set) or len(selected) < 2: return False, "Select at least two colours."
            return True, "Verified ✅"
        if era_id == "era_1980s_high_brightness":
            if not bool(s.get("power")): return False, "Turn the indicator ON."
            if not bool(s.get("did_fast_pulse")): return False, "Set pulse rate to FAST."
            if not bool(s.get("did_dim")): return False, "Change brightness at least once to create contrast."
            return True, "Verified ✅"
        if era_id == "era_1993_blue":
            if not bool(s.get("power")): return False, "Turn the LED ON."
            if not bool(s.get("did_mixed_rgb")): return False, "Blend at least two RGB channels to make a mixed hue."
            return True, "Verified ✅"
        if era_id == "era_1996_white":
            if not bool(s.get("power")): return False, "Turn the lamp ON."
            if not bool(s.get("did_white_change")): return False, "Change the white type at least once."
            if not bool(s.get("did_dim")): return False, "Dim at least once."
            return True, "Verified ✅"
        if era_id == "era_2000s_matrices":
            if not bool(s.get("power")): return False, "Power ON."
            if not bool(s.get("did_move")): return False, "Move the dot (prove coordinates)."
            if not bool(s.get("did_scroll")): return False, "Trigger scrolling/motion."
            return True, "Verified ✅"
        if era_id == "era_2012_addressable":
            if not bool(s.get("power")): return False, "Power ON."
            if not bool(s.get("did_index_move")): return False, "Move the pixel to a different index."
            if not bool(s.get("did_mode_change")): return False, "Change the animation mode."
            if not bool(s.get("did_color_change")): return False, "Change colour during motion."
            return True, "Verified ✅"
        return True, "No verification required."

    def _on_verify(self):
        era_id = self._active_era_id()
        if self._display_id() != era_id:
            self.wb_status.setText("Browsing only. Jump to current era to verify.")
            return
        ok, msg = self._verify_state(era_id)
        self.wb_status.setText(msg)
        if ok:
            self._wb_verified[era_id] = True
            self._progress_mark_verified(era_id, True)
            try:
                nxt = self._progress_unlock_next()
                if nxt:
                    nxt_title = getattr(get_era(nxt), "title", nxt)
                    self.wb_status.setText(msg + f" Next era unlocked: {nxt_title}")
                    try:
                        self._set_display_id(nxt)
                    except Exception as exc:
                        _diag_exc(exc, "qt/era_panel.py")
            except Exception as exc:
                _diag_exc(exc, "qt/era_panel.py")
            try:
                self._populate_browse()
            except Exception as exc:
                _diag_exc(exc, "qt/era_panel.py")
        self._update_buttons()

    def _update_buttons(self):
        active = self._active_era_id()
        display = self._display_id()
        is_active_view = active == display
        is_plateau = display == "era_usage_plateau" and is_active_view
        try:
            self.btn_workspace.setVisible(bool(is_plateau)); self.btn_workspace.setEnabled(bool(is_plateau))
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")
        try:
            self.btn_unlock_modulo.setVisible(bool(is_plateau)); self.btn_unlock_modulo.setEnabled(bool(is_plateau))
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")

        self.btn_continue.setText("Open Modulo" if display == "era_now" and is_active_view else "Continue")
        if not is_active_view:
            self.btn_continue.setEnabled(False)
            return
        if active in ("era_usage_plateau", "era_now"):
            self.btn_continue.setEnabled(active == "era_now")
            self.wb_verify.setEnabled(False); self.wb_verify.setText("No verification")
            return
        self.wb_verify.setEnabled(is_active_view); self.wb_verify.setText("Verify this era")
        if bool(self._wb_verified.get(active, False)):
            self.wb_verify.setEnabled(False); self.wb_verify.setText("Verified ✅")
        self.btn_continue.setEnabled(bool(self._wb_verified.get(active, False)))

    def _owner_window(self):
        try:
            cur = self.parent(); seen = set()
            while cur is not None and id(cur) not in seen:
                seen.add(id(cur))
                if hasattr(cur, 'refresh_era_ui') and hasattr(cur, 'tabs'):
                    return cur
                cur = cur.parent() if hasattr(cur, 'parent') else None
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")
        try:
            win = self.window()
            if win is not None and hasattr(win, 'refresh_era_ui') and hasattr(win, 'tabs'):
                return win
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")
        return None

    def _refresh_owner_ui(self, focus_modulo: bool = False):
        try:
            owner = self._owner_window()
            if owner is not None and hasattr(owner, 'refresh_era_ui'):
                owner.refresh_era_ui(focus_modulo=bool(focus_modulo))
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")

    def _on_continue(self):
        eras = get_eras()
        cur = self._active_era_id()
        ids = [e.era_id for e in eras]
        if cur not in ids:
            return
        i = ids.index(cur)

        if cur == "era_now":
            try: self._progress_mark_verified("era_now", True)
            except Exception as exc: _diag_exc(exc, "qt/era_panel.py")
            try:
                if hasattr(self.app_core, "set_era_complete"):
                    self.app_core.set_era_complete(True)
            except Exception as exc:
                _diag_exc(exc, "qt/era_panel.py")
            self._display_era_id = None
            try: self.refresh()
            except Exception as exc: _diag_exc(exc, "qt/era_panel.py")
            try:
                owner = self._owner_window()
                if owner is not None:
                    try:
                        from qt.tab_registry import _set_tab_visible_safe
                        for spec in list(getattr(owner, '_era_tab_specs', []) or []):
                            idx = int(spec.get('index', -1))
                            if idx >= 0:
                                _set_tab_visible_safe(owner.tabs, idx, True)
                    except Exception as exc:
                        _diag_exc(exc, "qt/era_panel.py")
                    try:
                        if hasattr(owner, 'refresh_era_ui'):
                            owner.refresh_era_ui(focus_modulo=True)
                    except Exception as exc:
                        _diag_exc(exc, "qt/era_panel.py")
                    def _jump_to_studio():
                        try:
                            tabs = getattr(owner, 'tabs', None)
                            if tabs is None:
                                return
                            target_idx = 1
                            try:
                                if hasattr(tabs, 'isTabVisible') and not tabs.isTabVisible(target_idx):
                                    target_idx = None
                            except Exception:
                                pass
                            if target_idx is None:
                                for spec in list(getattr(owner, '_era_tab_specs', []) or []):
                                    idx = int(spec.get('index', -1))
                                    tool = str(spec.get('tool') or '').strip()
                                    if idx < 0 or tool == 'era_panel':
                                        continue
                                    try:
                                        if not hasattr(tabs, 'isTabVisible') or tabs.isTabVisible(idx):
                                            target_idx = idx
                                            break
                                    except Exception:
                                        target_idx = idx
                                        break
                            if target_idx is not None:
                                tabs.setCurrentIndex(int(target_idx))
                        except Exception as exc:
                            _diag_exc(exc, "qt/era_panel.py")
                    try:
                        QTimer.singleShot(0, _jump_to_studio); QTimer.singleShot(50, _jump_to_studio)
                    except Exception:
                        _jump_to_studio()
            except Exception as exc:
                _diag_exc(exc, "qt/era_panel.py")
            self.era_completed.emit()
            return

        if cur not in ("era_usage_plateau", "era_now") and not bool(self._wb_verified.get(cur, False)):
            self.wb_status.setText("Verify this era to continue.")
            return

        if i + 1 < len(ids):
            nxt = None
            unlocked = set(self._progress_unlocked_ids())
            for cand in ids[i + 1:]:
                if cand in unlocked:
                    nxt = cand; break
            if not nxt: nxt = self._progress_unlock_next()
            if not nxt: nxt = ids[i + 1]
            self._progress_set_active_era(nxt)
            self._display_era_id = None
            self.refresh()
            self._refresh_owner_ui(focus_modulo=(str(nxt) == "era_now"))
            if str(nxt) == "era_usage_plateau":
                try:
                    QTimer.singleShot(0, self._open_workspace); QTimer.singleShot(50, self._open_workspace)
                except Exception:
                    self._open_workspace()

    def refresh(self):
        display_id = self._display_id()
        try:
            for i in range(self.browse_combo.count()):
                if self.browse_combo.itemData(i) == display_id:
                    self.browse_combo.blockSignals(True); self.browse_combo.setCurrentIndex(i); self.browse_combo.blockSignals(False)
                    break
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")

        era = get_era(display_id)
        try:
            done_map = self._progress_done_map() or {}
            self._wb_verified.update({str(k): bool(v) for k, v in dict(done_map).items()})
        except Exception as exc:
            _diag_exc(exc, "qt/era_panel.py")
        self.era_title.setText(era.title)
        phase_note = get_phase_note(era)
        caps = list(getattr(getattr(era, 'gates', None), 'control_capabilities', []) or [])
        gates = getattr(era, 'gates', None)
        try:
            from app.eras.era_history import get_studio_tools_for_era
            studio_tools = list(get_studio_tools_for_era(era))
        except Exception:
            studio_tools = []
        phase_kind = str(getattr(gates, 'phase_kind', 'historical') or 'historical')
        if phase_kind == 'historical':
            stop_line = "Advance to continue the historical control ladder."
        elif phase_kind == 'plateau':
            stop_line = "You can stay here and use the familiar effect-picker model, or explicitly unlock Modulo when you are ready to move beyond the effect-picker plateau."
        else:
            stop_line = "Modulo appears here: full first-class control, plus escape hatches for user code if you ever need to go lower-level."
        self.era_meta.setText(f"{era.start_year} — {era.key_person}\n{phase_note}\n{era.summary}\n{stop_line}")

        wb = get_workbench_for_era(era)
        if wb is None:
            self.wb_hint.setText("")
        else:
            steps = "\n".join([f"• {x}" for x in (getattr(wb, "verify_steps", []) or [])])
            self.wb_hint.setText(f"Goal: {wb.goal}" + (("\n\nVerify by:\n" + steps) if steps else ""))

        bullets = "\n".join([f"• {x}" for x in (era.what_was_possible or [])])
        if bullets: bullets += "\n"
        bullets += f"\nControl capabilities: {', '.join(caps) if caps else '-'}"
        if phase_kind == "plateau":
            bullets += "\n\nChoice here: stay with the effect-picker app model, or unlock Modulo."
        self.era_possible.setText(bullets)

        self._ensure_state()
        self._configure_controls_for(display_id)
        self._sync_controls_from_state()
        self._update_preview()
        if display_id in ("era_usage_plateau", "era_now"):
            self.wb_status.setText("")
        self._update_buttons()
