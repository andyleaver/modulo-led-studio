from __future__ import annotations

from app.project_canonical import apply_project_roots

import json

from qt.qt_compat import QtWidgets  # type: ignore


class TargetsTabActionsMixin:
    def _apply_mask_to_selected_layer(self):
        ref = str(self.cmb_apply_mask.currentText() or "").strip() if hasattr(self, "cmb_apply_mask") else ""
        self._apply_target_to_selected_layer("mask", ref, "targets_apply_mask_layer")

    def _add_rect_zone_from_fields(self):
        name = str(self.txt_zone_name.text() or "").strip()
        rect = str(self.txt_zone_rect.text() or "").strip()
        if not name or not rect:
            QtWidgets.QMessageBox.warning(self, "Invalid Zone", "Enter a zone name and rect as x,y,w,h.")
            return
        try:
            parts = [int(x.strip()) for x in rect.split(",")]
            if len(parts) != 4:
                raise ValueError("Need exactly 4 integers.")
            x, y, w, h = parts
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Invalid Zone", f"Rect must be x,y,w,h.\n{e}")
            return
        zones = self._load_json(self.txt_zones, [])
        if not isinstance(zones, list):
            zones = []
        zones.append({"name": name, "kind": "rect", "x": x, "y": y, "w": w, "h": h})
        self._write_json(self.txt_zones, zones)
        self.txt_zone_name.clear(); self.txt_zone_rect.clear(); self._refresh_apply_target_picklists()

    def _apply_zone_to_selected_layer(self):
        ref = str(self.cmb_apply_zone.currentText() or "").strip() if hasattr(self, "cmb_apply_zone") else ""
        self._apply_target_to_selected_layer("zone", ref, "targets_apply_zone_layer")

    def _apply_group_to_selected_layer(self):
        ref = str(self.cmb_apply_group.currentText() or "").strip() if hasattr(self, "cmb_apply_group") else ""
        self._apply_target_to_selected_layer("group", ref, "targets_apply_group_layer")

    def _apply_target_to_selected_layer(self, kind: str, ref: str, rebuild_reason: str):
        idx = self._selected_layer_index()
        if idx < 0 or not str(ref or "").strip():
            return
        pm = getattr(self.app_core, "pm", None)
        try:
            if pm is not None and hasattr(pm, "guarded_set_address"):
                pm.guarded_set_address(f"layers[{idx}].target_kind", str(kind))
                pm.guarded_set_address(f"layers[{idx}].target_ref", str(ref))
            else:
                proj = dict(getattr(self.app_core, "project") or {})
                layers = list(proj.get("layers") or [])
                if idx < len(layers):
                    ly = dict(layers[idx])
                    ly["target_kind"] = str(kind)
                    ly["target_ref"] = str(ref)
                    layers[idx] = ly
                    proj, _snap, _changes = apply_project_roots(proj, {"layers": layers})
                    setattr(self.app_core, "project", proj)
        except Exception:
            pass
        try:
            fn = getattr(self.app_core, "rebuild_preview", None)
            if callable(fn):
                fn(rebuild_reason)
        except Exception:
            pass

    def _add_mask_template(self):
        masks = self._load_json(self.txt_masks, {})
        if not isinstance(masks, dict): masks = {}
        name = self._next_name("mask", masks.keys())
        masks[name] = {"kind": "pixels", "indices": []}
        self._write_json(self.txt_masks, masks, sort_keys=True)
        self._refresh_apply_target_picklists()

    def _add_zone_template(self):
        zones = self._load_json(self.txt_zones, [])
        if not isinstance(zones, list): zones = []
        existing = [str(z.get("name") or "") for z in zones if isinstance(z, dict)]
        name = self._next_name("zone", existing)
        zones.append({"name": name, "kind": "rect", "x": 0, "y": 0, "w": 1, "h": 1})
        self._write_json(self.txt_zones, zones)
        self._refresh_apply_target_picklists()

    def _add_group_template(self):
        groups = self._load_json(self.txt_groups, [])
        if not isinstance(groups, list): groups = []
        existing = []
        for g in groups:
            if isinstance(g, dict): existing.append(str(g.get("name") or ""))
            else: existing.append(str(g))
        name = self._next_name("group", existing)
        groups.append({"name": name, "members": []})
        self._write_json(self.txt_groups, groups)
        self._refresh_apply_target_picklists()

    def apply(self):
        try:
            masks = json.loads(self.txt_masks["txt"].toPlainText() or "{}")
            zones = json.loads(self.txt_zones["txt"].toPlainText() or "[]")
            groups = json.loads(self.txt_groups["txt"].toPlainText() or "[]")
            if not isinstance(masks, dict): raise ValueError("Masks must be a JSON object/dict.")
            if not isinstance(zones, list): raise ValueError("Zones must be a JSON list.")
            if not isinstance(groups, list): raise ValueError("Groups must be a JSON list.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Invalid Targeting JSON", str(e)); return
        project = dict(self._project())
        project, _snap, _changes = apply_project_roots(project, {"masks": masks, "zones": zones, "groups": groups})
        self._set_project(project); self.refresh()
        QtWidgets.QMessageBox.information(self, "Targeting Updated", "Applied targeting changes to the project (masks/zones/groups).")
