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

from app.project_canonical import apply_project_root

from runtime.resolver import set_address
from params.registry import PARAMS
from params.ensure import ensure_params
from behaviors.registry import get_effect

class LayersPanelKernelMixin:
    def _add_layer(self):
            pd = self._project_data()
            if not isinstance(pd, dict):
                return
            layer_dict = {
                "name": f"Layer {len(pd.get('layers', []))}",
                "enabled": True,
                "behavior": "solid",
                "opacity": 1.0,
                "blend_mode": "over",
                "params": {},
                "operators": [],
            }
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_add_layer"):
                    pm.guarded_add_layer(layer_dict)
                    self._sync_project_from_pm()
                else:
                    layers = list(pd.get("layers", []) if isinstance(pd.get("layers"), list) else [])
                    layers.append(layer_dict)
                    p2, _validation, _changes = apply_project_root(pd, "layers", layers)
                    self.app_core.project = p2
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._request_preview_rebuild("layers_add")
            self.refresh()
            if self.list.count() > 0:
                self.list.setCurrentRow(self.list.count() - 1)

    def _add_kernel_layer(self):
            pd = self._project_data()
            if not isinstance(pd, dict):
                return
            layer_dict = {
                "name": f"Kernel {len(pd.get('layers', []))}",
                "enabled": True,
                "kind": "kernel",
                "behavior": "kernel",
                "opacity": 1.0,
                "blend_mode": "over",
                "params": {
                    "budget_ms": 10.0,
                    "strike_limit": 3,
                    "py": "",
                    "cpp": "",
                },
                "operators": [],
            }
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_add_layer"):
                    pm.guarded_add_layer(layer_dict)
                    self._sync_project_from_pm()
                else:
                    layers = list(pd.get("layers", []) if isinstance(pd.get("layers"), list) else [])
                    layers.append(layer_dict)
                    p2, _validation, _changes = apply_project_root(pd, "layers", layers)
                    self.app_core.project = p2
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._request_preview_rebuild("layers_add_kernel")
            self.refresh()
            if self.list.count() > 0:
                self.list.setCurrentRow(self.list.count() - 1)

    def _apply_kernel(self):
            idx = self._selected_index()
            if idx < 0:
                return
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx >= len(layers):
                return
            params = dict((layers[idx].get("params") or {}) if isinstance(layers[idx].get("params"), dict) else {})
            params["budget_ms"] = float(self.spn_budget.value())
            params["strike_limit"] = int(self.spn_strikes.value())
            params["py"] = str(self.txt_py.toPlainText() or "")
            params["cpp"] = str(self.txt_cpp.toPlainText() or "")
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_set_layer_effect"):
                    pm.guarded_set_layer_effect(idx, "kernel", params=params)
                    pm.guarded_set_address(f"layers[{idx}].kind", "kernel")
                    self._sync_project_from_pm()
                else:
                    pnew = copy.deepcopy(pd) if isinstance(pd, dict) else {}
                    layers2 = pnew.get("layers", []) if isinstance(pnew, dict) else []
                    if idx < len(layers2) and isinstance(layers2[idx], dict):
                        layers2[idx]["params"] = params
                        layers2[idx]["behavior"] = "kernel"
                        layers2[idx]["behavior"] = "kernel"
                        layers2[idx].pop("effect", None)
                        layers2[idx]["kind"] = "kernel"
                    if isinstance(pnew, dict):
                        self.app_core.project = pnew
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._set_kernel_field_address("py")
            self._request_preview_rebuild("kernel_apply")
            self.refresh()

    def _reset_kernel_vars(self):
            idx = self._selected_index()
            if idx < 0:
                return
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx >= len(layers):
                return
            params = dict((layers[idx].get("params") or {}) if isinstance(layers[idx].get("params"), dict) else {})
            try:
                params["vars_reset_token"] = float(_time.time())
            except Exception:
                params["vars_reset_token"] = (params.get("vars_reset_token") or 0) + 1
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_set_address"):
                    pm.guarded_set_address(f"layers[{idx}].params.vars_reset_token", params["vars_reset_token"])
                    pm.guarded_set_layer_effect(idx, "kernel")
                    pm.guarded_set_address(f"layers[{idx}].kind", "kernel")
                    self._sync_project_from_pm()
                else:
                    pnew = copy.deepcopy(pd) if isinstance(pd, dict) else {}
                    layers2 = pnew.get("layers", []) if isinstance(pnew, dict) else []
                    if idx < len(layers2) and isinstance(layers2[idx], dict):
                        p0 = dict((layers2[idx].get("params") or {}) if isinstance(layers2[idx].get("params"), dict) else {})
                        p0["vars_reset_token"] = params["vars_reset_token"]
                        layers2[idx]["params"] = p0
                        layers2[idx]["behavior"] = "kernel"
                        layers2[idx]["behavior"] = "kernel"
                        layers2[idx].pop("effect", None)
                        layers2[idx]["kind"] = "kernel"
                    if isinstance(pnew, dict):
                        self.app_core.project = pnew
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._set_kernel_field_address("vars_reset_token")
            self._request_preview_rebuild("kernel_vars_reset")
            self.refresh()

    def _insert_kernel_py_template(self):
            tpl = (
                "def init(ctx):\n"
                "    # ctx.vars persists across frames\n"
                "    ctx.vars['t0'] = ctx.t\n"
                "\n"
                "def update(ctx):\n"
                "    pass\n"
                "\n"
                "def pixel(ctx):\n"
                "    # ctx.x, ctx.y are normalized 0..1\n"
                "    r = int(255 * ctx.x)\n"
                "    g = int(255 * ctx.y)\n"
                "    b = 0\n"
                "    return r, g, b\n"
            )
            try:
                self.txt_py.setPlainText(tpl)
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

    def _insert_kernel_cpp_template(self):
            tpl = (
                "// NOTE: Kernel export is currently preview-only.\n"
                "// This C++ body will be used once kernel export runtime is implemented.\n"
                "// Expected to set r,g,b (0..255) for the current pixel.\n"
                "r = (uint8_t)(x * 255.0f);\n"
                "g = (uint8_t)(y * 255.0f);\n"
                "b = 0;\n"
            )
            try:
                self.txt_cpp.setPlainText(tpl)
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

    def _reset_kernel_state(self):
            try:
                cb = self.app_core
                fn = getattr(cb, "rebuild_preview_clean", None) if cb is not None else None
                if callable(fn):
                    fn("kernel_reset")
                else:
                    fn2 = getattr(cb, "rebuild_preview", None)
                    if callable(fn2):
                        fn2("kernel_reset")
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")

    def _move_layer_up(self):
            idx = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx <= 0 or idx >= len(layers):
                return
            pm = self._pm()
            moved = False
            try:
                if pm is not None and hasattr(pm, "guarded_move_layer"):
                    moved = bool(pm.guarded_move_layer(idx, idx - 1))
                    if moved:
                        self._sync_project_from_pm()
                else:
                    layers[idx - 1], layers[idx] = layers[idx], layers[idx - 1]
                    moved = True
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            if moved:
                self._request_preview_rebuild("layers_move_up")
                self.refresh()
                self.list.setCurrentRow(idx - 1)

    def _move_layer_down(self):
            idx = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx < 0 or idx >= len(layers) - 1:
                return
            pm = self._pm()
            moved = False
            try:
                if pm is not None and hasattr(pm, "guarded_move_layer"):
                    moved = bool(pm.guarded_move_layer(idx, idx + 1))
                    if moved:
                        self._sync_project_from_pm()
                else:
                    layers[idx + 1], layers[idx] = layers[idx], layers[idx + 1]
                    moved = True
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            if moved:
                self._request_preview_rebuild("layers_move_down")
                self.refresh()
                self.list.setCurrentRow(idx + 1)

    def _dup_layer(self):
            idx = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx < 0 or idx >= len(layers):
                return
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_duplicate_layer"):
                    pm.guarded_duplicate_layer(idx)
                    self._sync_project_from_pm()
                else:
                    clone = copy.deepcopy(layers[idx])
                    clone["name"] = (clone.get("name") or "Layer") + " (copy)"
                    layers.insert(idx + 1, clone)
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._request_preview_rebuild("layers_duplicate")
            self.refresh()
            if self.list.count() > idx + 1:
                self.list.setCurrentRow(idx + 1)

    def _del_layer(self):
            idx = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx < 0 or idx >= len(layers):
                return
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_remove_layer"):
                    pm.guarded_remove_layer(idx)
                    self._sync_project_from_pm()
                else:
                    layers.pop(idx)
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._request_preview_rebuild("layers_delete")
            self.refresh()
            if self.list.count() > 0:
                self.list.setCurrentRow(max(0, min(idx, self.list.count() - 1)))

    def _solo_layer(self):
            idx = self._selected_index()
            pd = self._project_data()
            layers = pd.get("layers", []) if isinstance(pd, dict) else []
            if idx < 0 or idx >= len(layers):
                return
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_set_address"):
                    for i in range(len(layers)):
                        pm.guarded_set_address(f"layers[{i}].enabled", bool(i == idx))
                    self._sync_project_from_pm()
                else:
                    pnew = copy.deepcopy(pd) if isinstance(pd, dict) else {}
                    for i in range(len(layers)):
                        pnew, _ = set_address(project=pnew, address=f"layers[{i}].enabled", value=bool(i == idx))
                    if isinstance(pnew, dict):
                        self.app_core.project = pnew
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._request_preview_rebuild("layers_solo")
            self.refresh()
            if self.list.count() > idx:
                self.list.setCurrentRow(idx)

    def _kernel_field_address(self, field_name: str):
            idx = self._selected_index()
            if idx < 0:
                return ""
            return f"layers[{idx}].params.{str(field_name or '').strip()}"

    def _set_kernel_field_address(self, field_name: str):
            addr = self._kernel_field_address(field_name)
            try:
                self.txt_selected_kernel_address.setText(addr)
            except Exception:
                pass
            try:
                self._set_address_inspector(addr)
            except Exception:
                pass

    def _reload_kernel_author_summary(self):
            try:
                idx = self._selected_index()
                pd = self._project_data()
                layers = pd.get("layers", []) if isinstance(pd, dict) else []
                if idx < 0 or idx >= len(layers):
                    self.lbl_kernel_author_summary.setText("")
                    return
                ly = layers[idx]
                if not isinstance(ly, dict):
                    self.lbl_kernel_author_summary.setText("")
                    return
                eff = str(ly.get("behavior") or "")
                kind = str(ly.get("kind") or "")
                is_kernel = (eff == "kernel") or (kind == "kernel")
                if not is_kernel:
                    self.lbl_kernel_author_summary.setText("Selected layer is not using the kernel escape hatch.")
                    return
                params = ly.get("params") or {}
                if not isinstance(params, dict):
                    params = {}
                py_src = str(params.get("py") or "")
                cpp_src = str(params.get("cpp") or "")
                py_lines = len(py_src.splitlines()) if py_src else 0
                cpp_lines = len(cpp_src.splitlines()) if cpp_src else 0
                budget = float(params.get("budget_ms", 10.0) or 10.0)
                strikes = int(params.get("strike_limit", 3) or 3)
                self.lbl_kernel_author_summary.setText(
                    f"Kernel Summary: budget {budget:g} ms · strike limit {strikes} · "
                    f"python lines {py_lines} · c++ lines {cpp_lines}"
                )
            except Exception:
                pass

    def _reload_kernel_addresses(self):
            try:
                idx = self._selected_index()
                pd = self._project_data()
                layers = pd.get("layers", []) if isinstance(pd, dict) else []
                self.list_kernel_addresses.clear()

                if idx < 0 or idx >= len(layers):
                    return

                ly = layers[idx]
                if not isinstance(ly, dict):
                    return

                eff = str(ly.get("behavior") or "")
                kind = str(ly.get("kind") or "")
                is_kernel = (eff == "kernel") or (kind == "kernel")
                if not is_kernel:
                    return

                for suffix in ("kind", "behavior"):
                    self.list_kernel_addresses.addItem(f"layers[{idx}].{suffix}")

                params = ly.get("params") or {}
                if isinstance(params, dict):
                    for k in sorted(params.keys()):
                        self.list_kernel_addresses.addItem(f"layers[{idx}].params.{k}")
            except Exception:
                pass

    def _on_kernel_address_selected(self, text: str):
            try:
                self.txt_selected_kernel_address.setText(str(text or ""))
            except Exception:
                pass

    def _copy_selected_kernel_address(self):
            try:
                text = str(self.txt_selected_kernel_address.text() or "").strip()
                if not text:
                    return
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    cb = app.clipboard()
                    if cb is not None:
                        cb.setText(text)
            except Exception:
                pass

