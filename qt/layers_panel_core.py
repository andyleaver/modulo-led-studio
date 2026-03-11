from __future__ import annotations

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

try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

import copy
import time as _time

from runtime.resolver import set_address
from params.registry import PARAMS
from params.ensure import ensure_params
from behaviors.registry import get_effect

class LayersPanelCoreMixin:
    def _project_data(self):
            pd = getattr(self.app_core, "project_data", None)
            if isinstance(pd, dict):
                return pd
            p = getattr(self.app_core, "project", None)
            if isinstance(p, dict):
                return p
            if self.controller is not None:
                br = getattr(self.controller, "bridge", None)
                if br is not None:
                    p2 = getattr(br, "project", None)
                    if isinstance(p2, dict):
                        return p2
            return {}

    def _pm(self):
            return getattr(self.app_core, "pm", None)

    def _sync_project_from_pm(self):
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "get"):
                    self.app_core.project = pm.get()
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

    def _request_preview_rebuild(self, reason: str):
            try:
                cb = self.app_core
                fn = getattr(cb, "rebuild_preview", None) if cb is not None else None
                if callable(fn):
                    fn(reason)
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            try:
                if self.controller is not None and hasattr(self.controller, "_request_preview_rebuild"):
                    self.controller._request_preview_rebuild()
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

    def _populate_effects(self):
            try:
                from behaviors.registry import list_effect_keys
                keys = list_effect_keys()
            except Exception:
                keys = []
            if not keys:
                keys = ["solid"]
            self.cmb_effect.blockSignals(True)
            self.cmb_effect.clear()
            self.cmb_effect.addItems(keys)
            self.cmb_effect.blockSignals(False)

    def _selected_index(self) -> int:
            try:
                ac = getattr(self, 'app_core', None)
                if ac is not None and hasattr(ac, 'get_selected_layer'):
                    return int(ac.get_selected_layer())
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            return int(self.list.currentRow()) if self.list.currentRow() >= 0 else -1

    def _set_selected_index(self, idx: int):
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_set_selected_layer"):
                    if pm.guarded_set_selected_layer(int(idx)):
                        self._sync_project_from_pm()
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

    def refresh(self):
            prev = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            self.list.blockSignals(True)
            self.list.clear()
            for i, ly in enumerate(layers):
                if not isinstance(ly, dict):
                    self.list.addItem(f"{i}: (invalid layer)")
                    continue
                nm = str(ly.get("name") or f"Layer {i}")
                beh = str(ly.get("behavior") or "solid")
                enabled = bool(ly.get("enabled", True))
                tk = str(ly.get("target_kind") or "").strip()
                tr = str(ly.get("target_ref") or "").strip()
                target_txt = f" [{tk}:{tr}]" if tk and tr else ""
                prefix = "●" if enabled else "○"
                self.list.addItem(f"{prefix} {i}: {nm} — {beh}{target_txt}")
            self.list.blockSignals(False)
            if self.list.count() > 0:
                if prev < 0:
                    prev = 0
                if prev >= self.list.count():
                    prev = self.list.count() - 1
                self.list.setCurrentRow(prev)
            else:
                self._load_selected(-1)
            self._update_action_buttons()

    def _on_row_changed(self, idx: int):
            self._set_selected_index(idx)
            self._load_selected(idx)
            self._update_action_buttons()

    def _load_selected(self, idx: int):
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx < 0:
                idx = self._selected_index()
            if idx < 0 or idx >= len(layers):
                self.grp_kernel.setVisible(False)
                try:
                    self.grp_params.setVisible(False)
                except Exception:
                    pass
                try:
                    self._reload_layer_address_browser()
                except Exception:
                    pass
                return
            ly = layers[idx]

            self.chk_enabled.blockSignals(True)
            self.txt_name.blockSignals(True)
            self.cmb_effect.blockSignals(True)
            self.spn_opacity.blockSignals(True)
            self.cmb_blend.blockSignals(True)
            self.cmb_target_kind.blockSignals(True)
            self.cmb_target_ref.blockSignals(True)

            enabled_val = bool(ly.get("enabled", True))
            opacity_val = float(ly.get("opacity", 1.0) or 1.0)
            blend_val = str(ly.get("blend_mode", "over") or "over")
            try:
                ac = getattr(self, 'app_core', None)
                if ac is not None and hasattr(ac, 'resolve_layer_canonical'):
                    enabled_val = bool(getattr(ac.resolve_layer_canonical(idx, 'enabled', default=enabled_val), 'value', enabled_val))
                    opacity_val = float(getattr(ac.resolve_layer_canonical(idx, 'opacity', default=opacity_val), 'value', opacity_val) or opacity_val)
                    blend_val = str(getattr(ac.resolve_layer_canonical(idx, 'blend_mode', default=blend_val), 'value', blend_val) or blend_val)
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

            self.chk_enabled.setChecked(bool(enabled_val))
            self.txt_name.setText(str(ly.get("name") or f"Layer {idx}"))
            eff = ly.get("behavior") or "solid"
            self.cmb_effect.setCurrentText(str(eff))
            self.spn_opacity.setValue(float(opacity_val))
            self.cmb_blend.setCurrentText(str(blend_val))
            target_kind = str(ly.get("target_kind") or "none").strip().lower() or "none"
            target_ref = str(ly.get("target_ref") or "").strip()
            self._reload_target_refs(target_kind)
            self.cmb_target_kind.setCurrentText(target_kind if target_kind in ("none", "mask", "zone", "group") else "none")
            self.cmb_target_ref.setCurrentText(target_ref)

            self.chk_enabled.blockSignals(False)
            self.txt_name.blockSignals(False)
            self.cmb_effect.blockSignals(False)
            self.spn_opacity.blockSignals(False)
            self.cmb_blend.blockSignals(False)
            self.cmb_target_kind.blockSignals(False)
            self.cmb_target_ref.blockSignals(False)

            try:
                eff = str(ly.get("behavior") or "")
                kind = str(ly.get("kind") or "")
                is_kernel = (eff == "kernel") or (kind == "kernel")
                self.grp_kernel.setVisible(bool(is_kernel))
                if is_kernel:
                    params = ly.get("params") if isinstance(ly.get("params"), dict) else {}
                    self.spn_budget.setValue(float(params.get("budget_ms", 10.0) or 10.0))
                    self.spn_strikes.setValue(int(params.get("strike_limit", 3) or 3))
                    self.txt_py.setPlainText(str(params.get("py") or ""))
                    self.txt_cpp.setPlainText(str(params.get("cpp") or ""))
                self._load_params_for_layer(idx, ly if isinstance(ly, dict) else {})
                self._reload_layer_address_browser()
                self._reload_kernel_addresses()
                self._reload_kernel_author_summary()
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

    def _update_action_buttons(self):
            idx = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            n = len(layers)
            has = 0 <= idx < n
            try:
                self.btn_dup.setEnabled(has)
                if hasattr(self, "btn_solo"):
                    self.btn_solo.setEnabled(has and n > 0)
                if hasattr(self, "btn_clear_target"):
                    self.btn_clear_target.setEnabled(has)
                self.btn_del.setEnabled(has)
                if hasattr(self, "btn_up"):
                    self.btn_up.setEnabled(has and idx > 0)
                if hasattr(self, "btn_down"):
                    self.btn_down.setEnabled(has and idx >= 0 and idx < n - 1)
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

