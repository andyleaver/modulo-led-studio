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

class LayersPanelTargetingMixin:
    def _selected_layer_addresses(self):
            idx = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx < 0 or idx >= len(layers):
                return []
            ly = layers[idx]
            out = [
                f"layers[{idx}].enabled",
                f"layers[{idx}].name",
                f"layers[{idx}].opacity",
                f"layers[{idx}].blend_mode",
                f"layers[{idx}].target_kind",
                f"layers[{idx}].target_ref",
                f"layers[{idx}].behavior",
            ]
            if isinstance(ly, dict):
                params = ly.get("params") or {}
                if isinstance(params, dict):
                    for k in sorted(params.keys()):
                        out.append(f"layers[{idx}].params.{k}")
            return out

    def _reload_layer_address_browser(self):
            try:
                current = str(self.txt_selected_layer_address.text() or "").strip()
            except Exception:
                current = ""
            addrs = self._selected_layer_addresses()
            self.list_layer_addresses.blockSignals(True)
            self.list_layer_addresses.clear()
            for addr in addrs:
                self.list_layer_addresses.addItem(addr)
            self.list_layer_addresses.blockSignals(False)
            if self.list_layer_addresses.count() > 0:
                row = 0
                if current:
                    matches = self.list_layer_addresses.findItems(current, QtCore.Qt.MatchFlag.MatchExactly)
                    if matches:
                        row = self.list_layer_addresses.row(matches[0])
                self.list_layer_addresses.setCurrentRow(row)
                try:
                    self.txt_selected_layer_address.setText(self.list_layer_addresses.item(row).text())
                except Exception:
                    pass
            else:
                try:
                    self.txt_selected_layer_address.setText("")
                except Exception:
                    pass

    def _on_layer_address_selected(self, text: str):
            try:
                self.txt_selected_layer_address.setText(str(text or ""))
            except Exception:
                pass

    def _copy_selected_layer_address(self):
            try:
                text = str(self.txt_selected_layer_address.text() or "").strip()
                if not text:
                    return
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    cb = app.clipboard()
                    if cb is not None:
                        cb.setText(text)
            except Exception:
                pass

    def _base_field_address(self, field_name: str):
            idx = self._selected_index()
            if idx < 0:
                return ""
            return f"layers[{idx}].{str(field_name or '').strip()}"

    def _set_address_for_base_field(self, field_name: str):
            self._set_address_inspector(self._base_field_address(field_name))

    def _set_address_inspector(self, addr: str):
            try:
                if hasattr(self, "txt_address"):
                    self.txt_address.setText(str(addr))
            except Exception:
                pass

    def _clear_targeting(self):
            try:
                self.cmb_target_kind.blockSignals(True)
                self.cmb_target_ref.blockSignals(True)
                self.cmb_target_kind.setCurrentText("none")
                self.cmb_target_ref.setCurrentText("")
            finally:
                try:
                    self.cmb_target_kind.blockSignals(False)
                    self.cmb_target_ref.blockSignals(False)
                except Exception:
                    pass
            self._apply()

    def _target_ref_items(self, kind: str):
            pd = self._project_data()
            if not isinstance(pd, dict):
                return []
            kind = str(kind or "none").strip().lower()
            if kind == "mask":
                masks = pd.get("masks") or {}
                return sorted(str(k) for k in masks.keys()) if isinstance(masks, dict) else []
            if kind == "zone":
                zones = pd.get("zones") or []
                out = []
                if isinstance(zones, list):
                    for z in zones:
                        if isinstance(z, dict):
                            nm = str(z.get("name") or "").strip()
                            if nm:
                                out.append(nm)
                return out
            if kind == "group":
                groups = pd.get("groups") or []
                out = []
                if isinstance(groups, list):
                    for g in groups:
                        if isinstance(g, dict):
                            nm = str(g.get("name") or "").strip()
                            if nm:
                                out.append(nm)
                        elif isinstance(g, str):
                            out.append(g)
                return out
            return []

    def _reload_target_refs(self, kind: str):
            current = ""
            try:
                current = str(self.cmb_target_ref.currentText() or "")
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self.cmb_target_ref.blockSignals(True)
            self.cmb_target_ref.clear()
            items = self._target_ref_items(kind)
            if items:
                self.cmb_target_ref.addItems(items)
            self.cmb_target_ref.setCurrentText(current)
            self.cmb_target_ref.blockSignals(False)

    def _on_target_kind_changed(self, _value=None):
            try:
                self._reload_target_refs(str(self.cmb_target_kind.currentText() or "none"))
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._apply()

    def _apply(self, *args):
            idx = self._selected_index()
            if idx < 0:
                return
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx >= len(layers):
                return
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_set_address"):
                    pm.guarded_set_address(f"layers[{idx}].enabled", bool(self.chk_enabled.isChecked()))
                    self._set_address_for_base_field("enabled")
                    pm.guarded_set_address(f"layers[{idx}].name", str(self.txt_name.text()).strip() or f"Layer {idx}")
                    self._set_address_for_base_field("name")
                    pm.guarded_set_address(f"layers[{idx}].opacity", float(self.spn_opacity.value()))
                    self._set_address_for_base_field("opacity")
                    pm.guarded_set_address(f"layers[{idx}].blend_mode", str(self.cmb_blend.currentText()).strip() or "over")
                    self._set_address_for_base_field("blend_mode")
                    tk = str(self.cmb_target_kind.currentText()).strip().lower() or "none"
                    tr = str(self.cmb_target_ref.currentText()).strip()
                    pm.guarded_set_address(f"layers[{idx}].target_kind", "" if tk == "none" else tk)
                    self._set_address_for_base_field("target_kind")
                    pm.guarded_set_address(f"layers[{idx}].target_ref", "" if tk == "none" else tr)
                    self._set_address_for_base_field("target_ref")
                    if hasattr(pm, "guarded_set_layer_effect"):
                        eff_key = str(self.cmb_effect.currentText()).strip() or "solid"
                        pd0 = self._project_data()
                        layers0 = pd0.get("layers", []) if isinstance(pd0, dict) else []
                        params0 = {}
                        if idx < len(layers0) and isinstance(layers0[idx], dict) and isinstance(layers0[idx].get("params"), dict):
                            params0 = dict(layers0[idx].get("params") or {})
                        params0 = ensure_params(params0, self._effect_uses(eff_key))
                        pm.guarded_set_layer_effect(idx, eff_key, params=params0)
                        self._set_address_for_base_field("behavior")
                    self._reload_kernel_author_summary()
                    self._sync_project_from_pm()
                else:
                    pnew = copy.deepcopy(pd) if isinstance(pd, dict) else {}
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].enabled", value=bool(self.chk_enabled.isChecked()))
                    self._set_address_for_base_field("enabled")
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].name", value=str(self.txt_name.text()).strip() or f"Layer {idx}")
                    self._set_address_for_base_field("name")
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].opacity", value=float(self.spn_opacity.value()))
                    self._set_address_for_base_field("opacity")
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].blend_mode", value=str(self.cmb_blend.currentText()).strip() or "over")
                    self._set_address_for_base_field("blend_mode")
                    tk = str(self.cmb_target_kind.currentText()).strip().lower() or "none"
                    tr = str(self.cmb_target_ref.currentText()).strip()
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].target_kind", value=("" if tk == "none" else tk))
                    self._set_address_for_base_field("target_kind")
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].target_ref", value=("" if tk == "none" else tr))
                    self._set_address_for_base_field("target_ref")
                    layers2 = pnew.get("layers", []) if isinstance(pnew, dict) else []
                    if idx < len(layers2) and isinstance(layers2[idx], dict):
                        eff_key = str(self.cmb_effect.currentText()).strip() or "solid"
                        layers2[idx]["behavior"] = eff_key
                        layers2[idx]["behavior"] = eff_key
                        layers2[idx].pop("effect", None)
                        self._set_address_for_base_field("behavior")
                        p0 = dict((layers2[idx].get("params") or {}) if isinstance(layers2[idx].get("params"), dict) else {})
                        layers2[idx]["params"] = ensure_params(p0, self._effect_uses(eff_key))
                    if isinstance(pnew, dict):
                        self.app_core.project = pnew
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._request_preview_rebuild("layers_mutated")
            self.refresh()

