from __future__ import annotations

import json

from qt.qt_compat import QtWidgets  # type: ignore
from runtime.resolver import set_address


class OperatorsTabActionsMixin:
    def apply(self):
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
            if not isinstance(data, dict):
                raise ValueError("postfx must be a JSON object")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Invalid JSON", str(e))
            return

        changed = False
        rejected = []
        pm = getattr(self.app_core, "pm", None)
        if pm is not None and hasattr(pm, "guarded_set_address"):
            for k, v in data.items():
                if bool(pm.guarded_set_address(f"project.postfx.{k}", v)):
                    changed = True
                else:
                    rejected.append(str(k))
            if changed and hasattr(pm, "get"):
                self.app_core.project = pm.get()
        else:
            p = dict(self.app_core.project)
            for k, v in data.items():
                p2, did = set_address(project=p, address=f"project.postfx.{k}", value=v)
                if did:
                    p = p2
                    changed = True
                else:
                    rejected.append(str(k))
            if changed:
                self._set_project(p)

        if rejected:
            QtWidgets.QMessageBox.warning(self, "Unknown Operator Keys", ", ".join(rejected))
        self.reload()

    def _add_operator_key(self):
        key = str(self.cmb_add_operator.currentText() or "").strip()
        if not key:
            return
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault(key, self._default_value_for_key(key))
        self.txt.setPlainText(json.dumps(data, indent=2, sort_keys=True))
        self._reload_active_operator_keys(data)
        items = self.list_ops.findItems(key, QtWidgets.Qt.MatchFlag.MatchExactly)
        if items:
            self.list_ops.setCurrentItem(items[0])

    def _remove_selected_operator_key(self):
        key = self._selected_operator_key()
        if not key:
            return
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
        except Exception:
            data = {}
        if isinstance(data, dict) and key in data:
            data.pop(key, None)
            self.txt.setPlainText(json.dumps(data, indent=2, sort_keys=True))
            self._reload_active_operator_keys(data)

    def _apply_selected_operator_value(self):
        key = self._selected_operator_key()
        if not key:
            return
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[key] = self._read_operator_editor_value(key)
        self.txt.setPlainText(json.dumps(data, indent=2, sort_keys=True))
        self._reload_active_operator_keys(data)
        items = self.list_ops.findItems(key, QtWidgets.Qt.MatchFlag.MatchExactly)
        if items:
            self.list_ops.setCurrentItem(items[0])

    def _set_postfx_values(self, *, trail=None, bleed=None, radius=None):
        data = {}
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if trail is not None:
            data["trail"] = trail
        if bleed is not None:
            data["bleed"] = bleed
        if radius is not None:
            data["blur_radius"] = radius
        self.txt.setPlainText(json.dumps(data, indent=2, sort_keys=True))

    def _apply_trail_preset(self):
        self._set_postfx_values(trail=True, bleed=0.15)

    def _apply_bleed_preset(self):
        self._set_postfx_values(bleed=0.25, radius=1.0)

    def _clear_postfx(self):
        self.txt.setPlainText("{}")
        self._reload_active_operator_keys({})
        self._set_operator_address("")
        self.btn_apply_operator_value.setEnabled(False)

    def _move_operator_up(self):
        row = self.list_ops.currentRow()
        if row <= 0:
            return
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
        except Exception:
            return
        if not isinstance(data, dict):
            return
        keys = list(data.keys())
        keys[row - 1], keys[row] = keys[row], keys[row - 1]
        new_data = {k: data[k] for k in keys}
        self.txt.setPlainText(json.dumps(new_data, indent=2))
        self._reload_active_operator_keys(new_data)
        self.list_ops.setCurrentRow(row - 1)

    def _move_operator_down(self):
        row = self.list_ops.currentRow()
        if row < 0:
            return
        try:
            data = json.loads(self.txt.toPlainText() or "{}")
        except Exception:
            return
        if not isinstance(data, dict):
            return
        keys = list(data.keys())
        if row >= len(keys) - 1:
            return
        keys[row + 1], keys[row] = keys[row], keys[row + 1]
        new_data = {k: data[k] for k in keys}
        self.txt.setPlainText(json.dumps(new_data, indent=2))
        self._reload_active_operator_keys(new_data)
        self.list_ops.setCurrentRow(row + 1)

    def _operator_gates(self):
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            return dict(fn() if callable(fn) else {})
        except Exception:
            return {}

    def _apply_operator_gate(self):
        gates = self._operator_gates()
        allow = bool(gates.get("allow_operators", True))
        model = str(gates.get("control_model") or "").strip().lower()
        msg = f"Historical operator gate: control model = {model or 'full_modulo'} · operators {'enabled' if allow else 'locked'}."
        self.lbl_operator_gate.setText(msg)
        for name in (
            "btn_trail_preset", "btn_bleed_preset", "btn_clear_postfx", "cmb_add_operator",
            "btn_add_operator", "list_ops", "btn_remove_operator", "btn_move_up", "btn_move_down",
            "btn_apply_operator_value", "btn_reload", "btn_apply", "txt"
        ):
            widget = getattr(self, name, None)
            try:
                if widget is not None:
                    widget.setEnabled(allow)
            except Exception:
                pass
