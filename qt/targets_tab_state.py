from __future__ import annotations

import json


class TargetsTabStateMixin:
    def _target_gates(self):
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            return dict(fn() if callable(fn) else {})
        except Exception:
            return {}

    def _apply_target_gate(self):
        gates = self._target_gates()
        allow_targets = bool(gates.get("allow_targets", True))
        model = str(gates.get("control_model") or "").strip().lower()
        msg = (
            f"Historical target gate: control model = {model or 'full_modulo'} · "
            f"targets {'enabled' if allow_targets else 'locked'}."
        )
        try:
            self.lbl_target_gate.setText(msg)
        except Exception:
            pass
        widgets = [
            getattr(self, "mask_panel", None), getattr(self, "btn_add_mask", None), getattr(self, "btn_add_zone", None),
            getattr(self, "btn_add_group", None), getattr(self, "btn_add_zone_rect", None),
            getattr(self, "btn_apply_mask_layer", None), getattr(self, "btn_apply_zone_layer", None),
            getattr(self, "btn_apply_group_layer", None), getattr(self, "btn_apply", None),
        ]
        for w in widgets:
            try:
                if w is not None:
                    w.setEnabled(bool(allow_targets))
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

    def _make_editor(self, title: str):
        from qt.qt_compat import QtWidgets  # type: ignore
        box = QtWidgets.QGroupBox(title)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        txt = QtWidgets.QPlainTextEdit(); txt.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(txt, 1)
        return {"box": box, "txt": txt}

    def _project(self):
        try:
            return getattr(self.app_core, "project", {}) or {}
        except Exception:
            return {}

    def _set_project(self, project: dict) -> None:
        try:
            setattr(self.app_core, "project", project)
        except Exception:
            try:
                self.app_core._project = project
            except Exception:
                pass
        try:
            pm = getattr(self.app_core, "pm", None)
            if pm is not None:
                try:
                    pm.project = project
                except Exception:
                    pass
                try:
                    pm.dirty = True
                except Exception:
                    pass
                try:
                    pm._notify()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self.app_core, "rebuild_preview"):
                self.app_core.rebuild_preview("targeting_tab_apply")
        except Exception:
            pass

    def _refresh_target_mask_items(self, project: dict) -> None:
        items = [("None", "")]
        masks = project.get("masks") or {}
        if isinstance(masks, dict):
            for key in sorted(str(k) for k in masks.keys()):
                items.append((key, key))
        current = None
        try:
            current = getattr(self.app_core, "target_mask", None)
        except Exception:
            current = None
        try:
            self.mask_panel.set_items(items, current_key=("" if current in (None, "") else str(current)))
        except Exception:
            pass

    def _load_json(self, editor, default):
        try:
            return json.loads(editor["txt"].toPlainText() or json.dumps(default))
        except Exception:
            return default

    def _write_json(self, editor, data, *, sort_keys=False):
        editor["txt"].setPlainText(json.dumps(data, indent=2, sort_keys=sort_keys))

    def _next_name(self, prefix: str, existing) -> str:
        names = {str(x) for x in existing}
        i = 1
        while f"{prefix}_{i}" in names:
            i += 1
        return f"{prefix}_{i}"

    def _refresh_apply_target_picklists(self):
        try:
            masks = self._load_json(self.txt_masks, {})
        except Exception:
            masks = {}
        try:
            zones = self._load_json(self.txt_zones, [])
        except Exception:
            zones = []
        try:
            groups = self._load_json(self.txt_groups, [])
        except Exception:
            groups = []

        cur_mask = str(self.cmb_apply_mask.currentText() or "") if hasattr(self, "cmb_apply_mask") else ""
        cur_zone = str(self.cmb_apply_zone.currentText() or "") if hasattr(self, "cmb_apply_zone") else ""
        cur_group = str(self.cmb_apply_group.currentText() or "") if hasattr(self, "cmb_apply_group") else ""

        if hasattr(self, "cmb_apply_mask"):
            self.cmb_apply_mask.blockSignals(True); self.cmb_apply_mask.clear()
            if isinstance(masks, dict):
                self.cmb_apply_mask.addItems([str(k) for k in sorted(masks.keys())])
            self.cmb_apply_mask.setCurrentText(cur_mask); self.cmb_apply_mask.blockSignals(False)

        if hasattr(self, "cmb_apply_zone"):
            self.cmb_apply_zone.blockSignals(True); self.cmb_apply_zone.clear()
            if isinstance(zones, list):
                names = []
                for z in zones:
                    if isinstance(z, dict):
                        nm = str(z.get("name") or "").strip()
                        if nm:
                            names.append(nm)
                    elif isinstance(z, str):
                        names.append(z)
                self.cmb_apply_zone.addItems(names)
            self.cmb_apply_zone.setCurrentText(cur_zone); self.cmb_apply_zone.blockSignals(False)

        if hasattr(self, "cmb_apply_group"):
            self.cmb_apply_group.blockSignals(True); self.cmb_apply_group.clear()
            if isinstance(groups, list):
                names = []
                for g in groups:
                    if isinstance(g, dict):
                        nm = str(g.get("name") or "").strip()
                        if nm:
                            names.append(nm)
                    elif isinstance(g, str):
                        names.append(g)
                self.cmb_apply_group.addItems(names)
            self.cmb_apply_group.setCurrentText(cur_group); self.cmb_apply_group.blockSignals(False)

    def refresh(self):
        project = self._project()
        masks = project.get("masks") or {}
        zones = project.get("zones") or []
        groups = project.get("groups") or []
        if not isinstance(masks, dict): masks = {}
        if not isinstance(zones, list): zones = []
        if not isinstance(groups, list): groups = []
        self.summary.setText(f"Current project: {len(masks)} masks · {len(zones)} zones · {len(groups)} groups")
        self._write_json(self.txt_masks, masks, sort_keys=True)
        self._write_json(self.txt_zones, zones)
        self._write_json(self.txt_groups, groups)
        self._refresh_target_mask_items(project)
        self._refresh_apply_target_picklists()
