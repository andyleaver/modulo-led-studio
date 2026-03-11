from __future__ import annotations

# --- diagnostics helper (no silent failure) ---
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

def _flatten_variables_tree(tree: dict | None) -> dict[str, tuple[str, object]]:
    flat: dict[str, tuple[str, object]] = {}
    src = tree if isinstance(tree, dict) else {}
    for kind in ("number", "toggle"):
        bucket = src.get(kind)
        if not isinstance(bucket, dict):
            continue
        for name, value in bucket.items():
            flat[f"{kind}.{str(name)}"] = (kind, value)
    return flat

def _parse_flat_key(key: str) -> tuple[str, str] | None:
    k = str(key or "").strip()
    if not k or "." not in k:
        return None
    kind, name = k.split(".", 1)
    kind = kind.strip().lower()
    name = name.strip()
    if kind not in ("number", "toggle") or not name:
        return None
    return kind, name

def _coerce_variable_value(kind: str, raw):
    if kind == "number":
        return float(raw)
    text = str(raw).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off", ""):
        return False
    return bool(raw)

class VariablesPanel(QtWidgets.QWidget):
    """Canonical variables editor.

    Variables are first-class runtime values used by rules, operators,
    behaviors, and signals. This UI keeps the canonical project structure
    visible while adding helpers to reduce friction.
    """

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        helpers = QtWidgets.QGroupBox("Variable Helpers")
        hlay = QtWidgets.QHBoxLayout(helpers)

        self.cmb_kind = QtWidgets.QComboBox()
        self.cmb_kind.addItems(["number", "toggle"])
        hlay.addWidget(self.cmb_kind, 0)

        self.txt_name = QtWidgets.QLineEdit()
        self.txt_name.setPlaceholderText("variable name")
        hlay.addWidget(self.txt_name, 1)

        self.txt_value = QtWidgets.QLineEdit()
        self.txt_value.setPlaceholderText("initial value")
        hlay.addWidget(self.txt_value, 1)

        self.btn_add = QtWidgets.QPushButton("Add Variable")
        self.btn_remove = QtWidgets.QPushButton("Remove Selected")
        hlay.addWidget(self.btn_add, 0)
        hlay.addWidget(self.btn_remove, 0)
        hlay.addStretch(1)
        outer.addWidget(helpers, 0)

        btns = QtWidgets.QHBoxLayout()
        self.btn_commit_rt_to_proj = QtWidgets.QPushButton("Commit Runtime → Project")
        self.btn_commit_proj_to_rt = QtWidgets.QPushButton("Commit Project → Runtime")
        self.btn_revert_rt = QtWidgets.QPushButton("Revert Runtime")
        btns.addWidget(self.btn_commit_rt_to_proj)
        btns.addWidget(self.btn_commit_proj_to_rt)
        btns.addWidget(self.btn_revert_rt)
        btns.addStretch(1)
        outer.addLayout(btns)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Key", "Project", "Runtime"])
        try:
            self.table.horizontalHeader().setStretchLastSection(True)
        except Exception as e:
            _diag_exc(e, "qt/variables_panel.py.header")
        outer.addWidget(self.table, 1)

        note = QtWidgets.QLabel(
            "Variables are canonical and namespaced. Use keys like number.score and toggle.enabled."
        )
        note.setWordWrap(True)
        outer.addWidget(note)

        self.btn_commit_rt_to_proj.clicked.connect(self._commit_runtime_to_project)
        self.btn_commit_proj_to_rt.clicked.connect(self._commit_project_to_runtime)
        self.btn_revert_rt.clicked.connect(self._revert_runtime)
        self.btn_add.clicked.connect(self._add_variable)
        self.btn_remove.clicked.connect(self._remove_selected_variable)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_buttons)

        self.refresh()

    def _project(self) -> dict:
        p = getattr(self.app_core, "project", None)
        return p if isinstance(p, dict) else {}

    def _project_vars(self) -> dict:
        return _flatten_variables_tree(self._project().get("variables"))

    def _runtime_vars_tree(self) -> dict:
        getter = getattr(self.app_core, "get_runtime_variables_state", None)
        if callable(getter):
            try:
                data = getter()
                return data if isinstance(data, dict) else {}
            except Exception as e:
                _diag_exc(e, "qt/variables_panel.py.get_runtime_variables_state")
        rv = getattr(self.app_core, "runtime_vars", None)
        if isinstance(rv, dict):
            return rv
        p = self._project()
        rv = p.get("variables_runtime")
        return rv if isinstance(rv, dict) else {}

    def _runtime_vars(self) -> dict:
        return _flatten_variables_tree(self._runtime_vars_tree())

    def _notify_changed(self):
        for name in ("on_project_changed", "notify_project_changed", "mark_dirty", "set_dirty"):
            fn = getattr(self.app_core, name, None)
            if callable(fn):
                try:
                    fn()
                    return
                except Exception as e:
                    _diag_exc(e, f"qt/variables_panel.py.{name}")

    def _set_project_variable(self, kind: str, name: str, value) -> bool:
        try:
            from runtime.resolver import set_address
            p2, changed = set_address(project=self._project(), address=f"project.variables.{kind}.{name}", value=value)
            if changed:
                self.app_core.project = p2
            return bool(changed)
        except Exception as e:
            _diag_exc(e, "qt/variables_panel.py.set_address")
            return False

    def _delete_project_variable(self, kind: str, name: str) -> bool:
        try:
            from app.project_canonical import apply_project_root

            project = dict(self._project())
            vars_tree = dict(project.get("variables") or {})
            bucket = dict(vars_tree.get(kind) or {})
            if name not in bucket:
                return False
            bucket.pop(name, None)
            vars_tree[kind] = bucket
            project, _validation, _changes = apply_project_root(project, "variables", vars_tree)
            self.app_core.project = project
            return True
        except Exception as e:
            _diag_exc(e, "qt/variables_panel.py.delete_project_variable")
            return False

    def _set_runtime_variable(self, kind: str, name: str, value) -> bool:
        setter = getattr(self.app_core, "set_runtime_variable", None)
        if callable(setter):
            try:
                setter(kind, name, value)
                return True
            except Exception as e:
                _diag_exc(e, "qt/variables_panel.py.set_runtime_variable")
                return False
        rv = self._runtime_vars_tree()
        bucket = dict(rv.get(kind) or {}) if isinstance(rv.get(kind), dict) else {}
        bucket[name] = value
        rv[kind] = bucket
        if isinstance(getattr(self.app_core, "runtime_vars", None), dict):
            self.app_core.runtime_vars = rv
            return True
        return False

    def _delete_runtime_variable(self, kind: str, name: str) -> bool:
        try:
            rv = self._runtime_vars_tree()
            bucket = dict(rv.get(kind) or {}) if isinstance(rv.get(kind), dict) else {}
            if name not in bucket:
                return False
            bucket.pop(name, None)
            rv[kind] = bucket
            if isinstance(getattr(self.app_core, "runtime_vars", None), dict):
                self.app_core.runtime_vars = rv
                return True
        except Exception as e:
            _diag_exc(e, "qt/variables_panel.py.delete_runtime_variable")
        return False

    def refresh(self):
        pv = dict(self._project_vars())
        rv = dict(self._runtime_vars())
        keys = sorted(set(pv.keys()) | set(rv.keys()))

        self.table.blockSignals(True)
        self.table.setRowCount(len(keys))
        for r, key in enumerate(keys):
            ik = QtWidgets.QTableWidgetItem(str(key))
            ik.setFlags(ik.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, ik)
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(pv.get(key, (None, ""))[1] if key in pv else "")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(rv.get(key, (None, ""))[1] if key in rv else "")))
        self.table.blockSignals(False)
        self._update_buttons()

    def _diff_count(self) -> int:
        pv = self._project_vars()
        rv = self._runtime_vars()
        keys = set(pv.keys()) | set(rv.keys())
        diff = 0
        for key in keys:
            if str(pv.get(key, (None, ""))[1]) != str(rv.get(key, (None, ""))[1]):
                diff += 1
        return diff

    def _update_buttons(self):
        diff = self._diff_count()
        self.btn_commit_rt_to_proj.setEnabled(diff > 0)
        self.btn_commit_proj_to_rt.setEnabled(diff > 0)
        self.btn_revert_rt.setEnabled(diff > 0)
        self.btn_remove.setEnabled(self.table.currentRow() >= 0)

    def _on_item_changed(self, item):
        row = item.row()
        col = item.column()
        key_item = self.table.item(row, 0)
        if key_item is None:
            return
        parsed = _parse_flat_key(key_item.text())
        if parsed is None:
            return
        kind, name = parsed
        try:
            value = _coerce_variable_value(kind, item.text())
        except Exception:
            self.refresh()
            return

        changed = False
        if col == 1:
            changed = self._set_project_variable(kind, name, value)
            if changed:
                self._notify_changed()
        elif col == 2:
            changed = self._set_runtime_variable(kind, name, value)
            if changed:
                self._notify_changed()
        self._update_buttons()

    def _add_variable(self):
        kind = str(self.cmb_kind.currentText() or "number").strip().lower()
        name = str(self.txt_name.text() or "").strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Invalid Variable", "Please enter a variable name.")
            return
        try:
            value = _coerce_variable_value(kind, self.txt_value.text())
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Invalid Variable", str(e))
            return

        if not self._set_project_variable(kind, name, value):
            QtWidgets.QMessageBox.warning(self, "Variable Not Added", "Unable to add the variable to the project.")
            return

        self._notify_changed()
        self.txt_name.clear()
        self.txt_value.clear()
        self.refresh()
        QtWidgets.QMessageBox.information(self, "Variable Added", f"Added {kind}.{name} to the project.")

    def _remove_selected_variable(self):
        row = self.table.currentRow()
        if row < 0:
            return
        key_item = self.table.item(row, 0)
        if key_item is None:
            return
        parsed = _parse_flat_key(key_item.text())
        if parsed is None:
            return
        kind, name = parsed

        self._delete_runtime_variable(kind, name)
        removed = self._delete_project_variable(kind, name)
        if removed:
            self._notify_changed()
        self.refresh()
        QtWidgets.QMessageBox.information(self, "Variable Removed", f"Removed {kind}.{name}.")

    def _commit_runtime_to_project(self):
        fn = getattr(self.app_core, "commit_runtime_variables_to_project", None)
        if callable(fn):
            try:
                fn()
            except Exception as e:
                _diag_exc(e, "qt/variables_panel.py.commit_runtime_variables_to_project")
        else:
            rt = self._runtime_vars()
            changed = False
            for key, (kind, value) in rt.items():
                parsed = _parse_flat_key(key)
                if parsed is None:
                    continue
                changed = self._set_project_variable(kind, parsed[1], value) or changed
            if changed:
                self._notify_changed()
        self.refresh()

    def _commit_project_to_runtime(self):
        proj = self._project_vars()
        changed = False
        for key, (kind, value) in proj.items():
            parsed = _parse_flat_key(key)
            if parsed is None:
                continue
            changed = self._set_runtime_variable(kind, parsed[1], value) or changed
        if changed:
            self._notify_changed()
        self.refresh()

    def _revert_runtime(self):
        fn = getattr(self.app_core, "revert_runtime_variables_from_project", None)
        if callable(fn):
            try:
                fn()
            except Exception as e:
                _diag_exc(e, "qt/variables_panel.py.revert_runtime_variables_from_project")
        else:
            self._commit_project_to_runtime()
        self.refresh()
