from __future__ import annotations

import json

from runtime.resolver import resolver_registry, set_address, resolve_address
from params.registry import PARAMS


class OperatorsTabStateMixin:
    def reload(self):
        p = self.app_core.project
        reg = resolver_registry()
        postfx = {}
        for addr in sorted(reg.keys()):
            if not addr.startswith("project.postfx."):
                continue
            res = resolve_address(project=p, address=addr, runtime=None, default=None)
            if res.value is not None:
                postfx[addr.split("project.postfx.", 1)[1]] = res.value
        self.txt.setPlainText(json.dumps(postfx, indent=2, sort_keys=True))
        self._reload_active_operator_keys(postfx)
        try:
            idx = int(self.list_ops.currentRow())
            if idx >= 0:
                self._select_operator_key(idx)
            else:
                self._set_operator_address("")
        except Exception:
            pass

    def _operator_choices(self):
        choices = []
        for addr in sorted(resolver_registry().keys()):
            if addr.startswith("project.postfx."):
                key = addr.split("project.postfx.", 1)[1]
                choices.append(key)
        return choices

    def _populate_operator_choices(self):
        self.cmb_add_operator.clear()
        self.cmb_add_operator.addItems(self._operator_choices())

    def _reload_active_operator_keys(self, postfx: dict):
        self.list_ops.clear()
        for key in sorted(postfx.keys()):
            self.list_ops.addItem(str(key))

    def _selected_operator_key(self) -> str:
        item = self.list_ops.currentItem()
        return str(item.text()).strip() if item is not None else ""

    def _operator_spec(self, key: str) -> dict:
        addr = f"project.postfx.{key}"
        spec = PARAMS.get(addr) if isinstance(PARAMS, dict) else None
        return dict(spec or {}) if isinstance(spec, dict) else {}

    def _default_value_for_key(self, key: str):
        spec = self._operator_spec(key)
        if "default" in spec:
            return spec.get("default")
        kind = str(spec.get("type") or "float").strip().lower()
        if kind in {"bool", "boolean"}:
            return False
        if kind in {"int", "integer"}:
            return 0
        return 0.0

    def _set_operator_editor_value(self, key: str, value):
        spec = self._operator_spec(key)
        kind = str(spec.get("type") or "float").strip().lower()
        self.op_value_enum.clear()
        if kind in {"bool", "boolean"}:
            self.operator_value_stack.setCurrentWidget(self.op_value_bool)
            self.op_value_bool.setChecked(bool(value))
        elif kind in {"int", "integer"}:
            self.operator_value_stack.setCurrentWidget(self.op_value_int)
            self.op_value_int.setValue(int(value or 0))
        elif kind == "enum":
            self.operator_value_stack.setCurrentWidget(self.op_value_enum)
            for option in list(spec.get("options") or []):
                self.op_value_enum.addItem(str(option))
            current = str(value if value is not None else spec.get("default") or "")
            idx = self.op_value_enum.findText(current)
            if idx >= 0:
                self.op_value_enum.setCurrentIndex(idx)
        elif kind in {"text", "string"}:
            self.operator_value_stack.setCurrentWidget(self.op_value_text)
            self.op_value_text.setText(str(value if value is not None else ""))
        else:
            self.operator_value_stack.setCurrentWidget(self.op_value_float)
            try:
                if "min" in spec:
                    self.op_value_float.setMinimum(float(spec.get("min")))
                if "max" in spec:
                    self.op_value_float.setMaximum(float(spec.get("max")))
                if "step" in spec:
                    self.op_value_float.setSingleStep(float(spec.get("step")))
            except Exception:
                pass
            self.op_value_float.setValue(float(value or 0.0))
        self.btn_apply_operator_value.setEnabled(bool(key))

    def _read_operator_editor_value(self, key: str):
        spec = self._operator_spec(key)
        kind = str(spec.get("type") or "float").strip().lower()
        if kind in {"bool", "boolean"}:
            return bool(self.op_value_bool.isChecked())
        if kind in {"int", "integer"}:
            return int(self.op_value_int.value())
        if kind == "enum":
            return str(self.op_value_enum.currentText() or "")
        if kind in {"text", "string"}:
            return str(self.op_value_text.text() or "")
        return float(self.op_value_float.value())

    def _select_operator_key(self, idx: int):
        if idx < 0:
            self._set_operator_address("")
            self.btn_apply_operator_value.setEnabled(False)
            return
        key = self._selected_operator_key()
        self._set_operator_address(key)
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
            current = data.get(key)
        except Exception:
            current = None
        if current is None:
            current = self._default_value_for_key(key)
        self._set_operator_editor_value(key, current)
        self._sync_json_selection_to_key(key)

    def _set_operator_address(self, key: str):
        self.txt_operator_addr.setText(f"project.postfx.{key}" if key else "")

    def _sync_json_selection_to_key(self, key: str):
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
            if isinstance(data, dict) and key in data:
                self.txt.setFocus()
        except Exception:
            pass

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
                self.app_core.rebuild_preview("operators_tab_apply")
        except Exception:
            pass
