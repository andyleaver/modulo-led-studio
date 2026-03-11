from app.project_canonical import apply_project_root
try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except ImportError:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore


class RulesTabActionsMixin:
    def _copy_selected_address(self):
        try:
            text = str(self.txt_selected_address.text() or "").strip()
            if not text:
                return
            app = QtWidgets.QApplication.instance()
            if app is not None:
                cb = app.clipboard()
                if cb is not None:
                    cb.setText(text)
        except Exception:
            pass

    def _populate_address_browser(self):
        try:
            current = self.txt_selected_address.text().strip()
        except Exception:
            current = ""
        addresses = self._canonical_addresses()
        self._all_addresses_cache = list(addresses)
        try:
            self.lbl_address_summary.setText(self._address_summary_text())
        except Exception:
            pass
        self.list_addresses.blockSignals(True)
        self.list_addresses.clear()
        for addr in addresses:
            self.list_addresses.addItem(addr)
        self.list_addresses.blockSignals(False)
        if self.list_addresses.count() > 0:
            row = 0
            if current:
                matches = self.list_addresses.findItems(current, QtCore.Qt.MatchFlag.MatchExactly)
                if matches:
                    row = self.list_addresses.row(matches[0])
            self.list_addresses.setCurrentRow(row)
            try:
                self.txt_selected_address.setText(self.list_addresses.item(row).text())
            except Exception:
                pass
        else:
            self.txt_selected_address.setText("")

    def _on_address_selected(self, text: str):
        try:
            self.txt_selected_address.setText(str(text or ""))
        except Exception:
            pass

    def _filter_addresses(self, text: str):
        try:
            base = list(getattr(self, "_all_addresses_cache", []))
            q = str(text or "").lower().strip()
            filtered = base if not q else [a for a in base if q in a.lower()]
            self.list_addresses.blockSignals(True)
            self.list_addresses.clear()
            for a in filtered:
                self.list_addresses.addItem(a)
            self.list_addresses.blockSignals(False)
        except Exception:
            pass

    def _reload_variables(self):
        try:
            p = self._project()
            vars_dict = p.get("vars") or p.get("variables") or {}
            self.list_vars.clear()
            if isinstance(vars_dict, dict):
                for k, v in sorted(vars_dict.items()):
                    self.list_vars.addItem(f"{k} = {v}")
        except Exception:
            pass

    def _set_variable(self):
        try:
            key = str(self.cmb_var_key.text() or "").strip()
            if not key:
                return
            val = float(self.spn_var_value.value())
            p = dict(self._project())
            vars_dict = dict(p.get("variables") or p.get("vars") or {})
            vars_dict[key] = val
            p2, _validation, _changes = apply_project_root(p, "variables", vars_dict)
            self._set_project(p2)
            self._reload_variables()
        except Exception:
            pass

    def _delete_variable(self):
        try:
            item = self.list_vars.currentItem()
            if not item:
                return
            key = str(item.text().split("=")[0]).strip()
            p = dict(self._project())
            vars_dict = dict(p.get("variables") or p.get("vars") or {})
            if key in vars_dict:
                vars_dict.pop(key, None)
                p2, _validation, _changes = apply_project_root(p, "variables", vars_dict)
                self._set_project(p2)
            self._reload_variables()
        except Exception:
            pass

    def _use_selected_address(self):
        try:
            text = str(self.txt_selected_address.text() or "").strip()
            if not text:
                return
            self.txt_rule_target.setText(text)
        except Exception:
            pass

    def _clear_rule_target(self):
        try:
            self.txt_rule_target.setText("")
        except Exception:
            pass

    def _apply_rules_gate(self):
        gates = self._rules_gates()
        allow_rules = bool(gates.get("allow_rules", True))
        model = str(gates.get("control_model") or "").strip().lower()
        try:
            self.lbl_rule_gate.setText(
                f"Historical rule gate: control model = {model or 'full_modulo'} · "
                f"rules {'enabled' if allow_rules else 'locked'}."
            )
        except Exception:
            pass
        widgets = [getattr(self, "panel", None), self.grp_addresses, self.grp_rule_target, self.grp_vars]
        for w in widgets:
            try:
                if w is not None:
                    w.setEnabled(bool(allow_rules))
            except Exception:
                pass
