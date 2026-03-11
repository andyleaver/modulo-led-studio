from __future__ import annotations

import copy
from typing import Any

from app.project_canonical import apply_project_root
from qt.qt_compat import QtWidgets  # type: ignore


class EffectsTabActionsMixin:
    def _rebuild(self):
        self.list.clear()

        q = str(self.txt_search.text() or "").strip().lower()
        shipped_only = bool(self.chk_shipped.isChecked())

        items = []
        try:
            from behaviors.registry import load_capabilities_catalog
            catalog = load_capabilities_catalog() or []
            for row in catalog:
                if isinstance(row, dict):
                    items.append(dict(row))
        except Exception:
            pass
        return False

        if not items:
            try:
                from behaviors.registry import get_all_effects
                for key, spec in (get_all_effects() or {}).items():
                    d = dict(spec or {})
                    d.setdefault("key", str(key))
                    items.append(d)
            except Exception:
                pass

        allowed = self._allowed_effects_for_era()
        total_count = len(items)

        filtered = []
        for it in items:
            key = str(it.get("key") or "")
            title = str(it.get("title") or it.get("name") or key)
            shipped = bool(it.get("shipped", True))

            if shipped_only and not shipped:
                continue
            if allowed is not None and key not in allowed:
                continue
            if q and q not in key.lower() and q not in title.lower():
                continue
            filtered.append(it)

        self._items = filtered
        self._rows = filtered
        self._update_era_gate_status(total_count=total_count, shown_count=len(filtered))

        for it in filtered:
            key = str(it.get("key") or "")
            title = str(it.get("title") or it.get("name") or key)
            label = f"{title} ({key})" if title != key else key
            self.list.addItem(label)

        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        else:
            try:
                self.lbl_title.setText("—")
                self.lbl_key.setText("")
            except Exception:
                pass

    def _select(self, idx: int):
        if idx < 0 or idx >= len(self._rows):
            self.lbl_title.setText("—")
            self.lbl_key.setText("")
            self.lbl_export.setText("")
            self.txt_desc.setPlainText("")
            self.btn_add.setEnabled(False)
            if hasattr(self, "btn_add_with_behavior"):
                self.btn_add_with_behavior.setEnabled(False)
            self.btn_apply_selected.setEnabled(False)
            return
        r = self._rows[idx]
        key = str(r.get("key"))
        self.lbl_title.setText(str(r.get("title") or key))
        self.lbl_key.setText(f"Key: {key}")
        self.lbl_export.setText(self._export_label(key) if hasattr(self, '_export_label') else '')
        self.txt_desc.setPlainText(str(r.get("desc") or ""))
        self.btn_add.setEnabled(True)
        if hasattr(self, "btn_add_with_behavior"):
            self.btn_add_with_behavior.setEnabled(True)
        self.btn_apply_selected.setEnabled(True)

    def _base_layer_dict(self, key: str, title: str) -> dict:
        layer = {
            "name": title,
            "enabled": True,
            "behavior": key,
            "opacity": 1.0,
            "blend_mode": "over",
            "params": {},
            "operators": [],
        }
        if key == "kernel":
            layer["kind"] = "kernel"
            layer["params"] = {
                "budget_ms": 10.0,
                "strike_limit": 3,
                "py": "",
                "cpp": "",
            }
        return layer

    def _sync_project_from_pm(self):
        pm = getattr(self.app_core, "pm", None)
        try:
            if pm is not None and hasattr(pm, "get"):
                self.app_core.project = pm.get()
        except Exception:
            pass

    def _request_preview_rebuild(self, reason: str):
        try:
            fn = getattr(self.app_core, "rebuild_preview", None)
            if callable(fn):
                fn(reason)
        except Exception:
            pass
        try:
            if self.controller is not None and hasattr(self.controller, "_request_preview_rebuild"):
                self.controller._request_preview_rebuild()
        except Exception:
            pass

    def _select_new_layer(self, idx: int):
        try:
            pm = getattr(self.app_core, "pm", None)
            if pm is not None and hasattr(pm, "guarded_set_selected_layer"):
                pm.guarded_set_selected_layer(int(idx))
                self._sync_project_from_pm()
                return
        except Exception:
            pass
        try:
            fn = getattr(self.app_core, "set_selected_layer", None)
            if callable(fn):
                fn(int(idx))
        except Exception:
            pass

    def _selected_layer_index(self):
        try:
            fn = getattr(self.app_core, "get_selected_layer", None)
            if callable(fn):
                idx = int(fn())
                return idx if idx >= 0 else -1
        except Exception:
            pass
        try:
            pm = getattr(self.app_core, "pm", None)
            if pm is not None and hasattr(pm, "selected_layer"):
                idx = int(getattr(pm, "selected_layer"))
                return idx if idx >= 0 else -1
        except Exception:
            pass
        return -1

    def _apply_to_selected_layer(self):
        idx = self._selected_layer_index()
        if idx < 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No Layer Selected",
                "Select or create a layer first, then apply the chosen behavior to it."
            )
            return

        row = int(self.list.currentRow())
        if row < 0 or row >= len(self._rows):
            return

        key = str(self._rows[row].get("key"))
        pm = getattr(self.app_core, "pm", None)
        try:
            if pm is not None and hasattr(pm, "guarded_set_layer_effect"):
                params = None
                if key == "kernel":
                    params = {
                        "budget_ms": 10.0,
                        "strike_limit": 3,
                        "py": "",
                        "cpp": "",
                    }
                pm.guarded_set_layer_effect(idx, key, params=params)
                if hasattr(pm, "guarded_set_address"):
                    pm.guarded_set_address(f"layers[{idx}].behavior", key)
                    if key == "kernel":
                        pm.guarded_set_address(f"layers[{idx}].kind", "kernel")
                    else:
                        pm.guarded_set_address(f"layers[{idx}].kind", "")
                self._sync_project_from_pm()
            else:
                proj = dict(getattr(self.app_core, "project") or {})
                layers = list(proj.get("layers") or []) if isinstance(proj.get("layers"), list) else []
                if idx >= len(layers):
                    raise IndexError("Selected layer index is out of range.")
                ly = dict(layers[idx] or {})
                ly["behavior"] = key
                ly.pop("effect", None)
                if key == "kernel":
                    ly["kind"] = "kernel"
                    ly["params"] = {
                        "budget_ms": 10.0,
                        "strike_limit": 3,
                        "py": "",
                        "cpp": "",
                    }
                else:
                    ly["kind"] = ""
                layers[idx] = ly
                proj, _snap, _changes = apply_project_root(proj, "layers", layers)
                setattr(self.app_core, "project", proj)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Apply Behavior Failed", str(e))
            return

        self._request_preview_rebuild("effects_tab_apply_selected_layer")
        QtWidgets.QMessageBox.information(
            self,
            "Behavior Applied",
            f"Applied behavior '{key}' to the selected layer."
        )

    def _add_with_behavior(self):
        self._add()

    def _add(self):
        idx = int(self.list.currentRow())
        if idx < 0 or idx >= len(self._rows):
            return

        key = str(self._rows[idx].get("key"))
        title = str(self._rows[idx].get("title") or key)
        layer_dict = self._base_layer_dict(key, title)

        pm = getattr(self.app_core, "pm", None)
        new_idx = None

        try:
            if pm is not None and hasattr(pm, "guarded_add_layer"):
                pm.guarded_add_layer(copy.deepcopy(layer_dict))
                self._sync_project_from_pm()
                proj = getattr(self.app_core, "project", {}) or {}
                layers = proj.get("layers") if isinstance(proj, dict) else []
                new_idx = len(layers) - 1 if isinstance(layers, list) and layers else None
            else:
                proj = dict(getattr(self.app_core, "project") or {})
                layers = list(proj.get("layers") or []) if isinstance(proj.get("layers"), list) else []
                layers.append(layer_dict)
                proj, _snap, _changes = apply_project_root(proj, "layers", layers)
                setattr(self.app_core, "project", proj)
                new_layers = proj.get("layers") if isinstance(proj, dict) else []
                new_idx = len(new_layers) - 1 if isinstance(new_layers, list) and new_layers else None
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Add Layer Failed", str(e))
            return

        self._request_preview_rebuild("effects_tab_add_layer")
        if new_idx is not None and new_idx >= 0:
            self._select_new_layer(new_idx)

        QtWidgets.QMessageBox.information(
            self,
            "Layer Added",
            f"Added behavior '{key}' as a new layer."
        )

    def _unlock_full_modulo(self):
        try:
            if self.controller and hasattr(self.controller,"_apply_studio_mode"):
                self.controller._apply_studio_mode("full_modulo")
        except Exception:
            pass

    def _goto_tab_by_prefix(self, prefix: str):
        try:
            tabs = getattr(self.controller, "tabs", None) if self.controller is not None else None
            if tabs is None:
                return
            for i in range(tabs.count()):
                label = str(tabs.tabText(i) or "")
                if label == prefix or label.startswith(prefix) or prefix in label:
                    tabs.setCurrentIndex(i)
                    return True
        except Exception:
            pass

    def _goto_presets_tab(self):
        self._goto_tab_by_prefix("Presets") or self._goto_tab_by_prefix("Behaviour")

    def _goto_export_tab(self):
        self._goto_tab_by_prefix("Export")
