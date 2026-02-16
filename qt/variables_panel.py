from __future__ import annotations

"""Variables Panel (Phase 6.2)

Minimal UI to create/edit persistent variables used by Rules.

Project schema:
  project['variables']['number'][name] = float
  project['variables']['toggle'][name] = bool

This panel is intentionally simple and deterministic.
"""

from PyQt6 import QtCore, QtWidgets

from runtime.variables import ensure_variables


def _safe_name(s: str) -> str:
    s = (s or "").strip()
    # Keep simple: alnum, underscore, dash. Replace spaces with underscore.
    s = s.replace(" ", "_")
    out = []
    for ch in s:
        if ch.isalnum() or ch in "_-":
            out.append(ch)
    return "".join(out)


class VariablesPanel(QtWidgets.QWidget):
    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Variables"))

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search… (e.g., speed, toggle)")
        hdr.addWidget(self.search, 1)

        self.btn_add_num = QtWidgets.QPushButton("+ Number")
        self.btn_add_tog = QtWidgets.QPushButton("+ Toggle")
        self.btn_del = QtWidgets.QPushButton("Delete")
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        hdr.addWidget(self.btn_add_num)
        hdr.addWidget(self.btn_add_tog)
        hdr.addWidget(self.btn_del)
        hdr.addWidget(self.btn_refresh)
        outer.addLayout(hdr)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Type", "Name", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed)
        outer.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.btn_add_num.clicked.connect(lambda: self._add_var(kind="number"))
        self.btn_add_tog.clicked.connect(lambda: self._add_var(kind="toggle"))
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_refresh.clicked.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)

        self.table.itemChanged.connect(self._on_item_changed)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll_project_rev)
        self._timer.start()
        self._last_rev = -1
        self._suspend_item_changed = False

        self.refresh()

    def _poll_project_rev(self):
        try:
            rev = int(getattr(self.app_core, "project_revision", 0))
        except Exception:
            rev = 0
        if rev != self._last_rev:
            self._last_rev = rev
            self.refresh()

    def _get_vars(self):
        p = self.app_core.project or {}
        p2, changed = ensure_variables(p)
        if changed:
            self.app_core.project = p2
            p = p2
        v = p.get("variables") or {}
        num = v.get("number") or {}
        tog = v.get("toggle") or {}
        return num if isinstance(num, dict) else {}, tog if isinstance(tog, dict) else {}

    def refresh(self):
        num, tog = self._get_vars()
        q = (self.search.text() or "").strip().lower()

        rows = []
        for name in sorted(num.keys(), key=lambda x: str(x)):
            if q and q not in str(name).lower() and q not in "number":
                continue
            rows.append(("number", str(name), float(num.get(name, 0.0))))
        for name in sorted(tog.keys(), key=lambda x: str(x)):
            if q and q not in str(name).lower() and q not in "toggle":
                continue
            rows.append(("toggle", str(name), bool(tog.get(name, False))))

        self._suspend_item_changed = True
        try:
            self.table.setRowCount(len(rows))
            for r, (kind, name, val) in enumerate(rows):
                it0 = QtWidgets.QTableWidgetItem(kind)
                it0.setFlags(it0.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                it1 = QtWidgets.QTableWidgetItem(name)
                it1.setFlags(it1.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                it2 = QtWidgets.QTableWidgetItem("true" if (kind == "toggle" and val) else ("false" if kind == "toggle" else f"{val:.4f}"))
                self.table.setItem(r, 0, it0)
                self.table.setItem(r, 1, it1)
                self.table.setItem(r, 2, it2)
        finally:
            self._suspend_item_changed = False

        self.status.setText(f"{len(rows)} variables shown" + (" (filtered)" if q else ""))

    def _selected_row(self) -> int:
        try:
            sel = self.table.selectionModel().selectedRows()
            if sel:
                return int(sel[0].row())
        except Exception:
            pass
        return -1

    def _selected_key(self):
        row = self._selected_row()
        if row < 0:
            return None
        try:
            kind = (self.table.item(row, 0).text() or "").strip()
            name = (self.table.item(row, 1).text() or "").strip()
            return kind, name
        except Exception:
            return None

    def _add_var(self, kind: str):
        name, ok = QtWidgets.QInputDialog.getText(self, "Add variable", "Name:")
        if not ok:
            return
        name = _safe_name(name)
        if not name:
            return

        p = self.app_core.project or {}
        p2, _ = ensure_variables(p)
        v = dict(p2.get("variables") or {})
        num = dict(v.get("number") or {})
        tog = dict(v.get("toggle") or {})

        if kind == "number":
            if name in num or name in tog:
                QtWidgets.QMessageBox.warning(self, "Exists", "A variable with that name already exists.")
                return
            num[name] = 0.0
        else:
            if name in num or name in tog:
                QtWidgets.QMessageBox.warning(self, "Exists", "A variable with that name already exists.")
                return
            tog[name] = False

        v["number"] = num
        v["toggle"] = tog
        p3 = dict(p2)
        p3["variables"] = v
        self.app_core.project = p3
        self.refresh()

    def _delete_selected(self):
        key = self._selected_key()
        if not key:
            return
        kind, name = key
        p = self.app_core.project or {}
        p2, _ = ensure_variables(p)
        v = dict(p2.get("variables") or {})
        num = dict(v.get("number") or {})
        tog = dict(v.get("toggle") or {})
        if kind == "number":
            num.pop(name, None)
        else:
            tog.pop(name, None)
        v["number"] = num
        v["toggle"] = tog
        p3 = dict(p2)
        p3["variables"] = v
        self.app_core.project = p3
        self.refresh()

    def _on_item_changed(self, item: QtWidgets.QTableWidgetItem):
        if self._suspend_item_changed:
            return
        # Only value column editable
        try:
            col = int(item.column())
        except Exception:
            return
        if col != 2:
            return
        row = int(item.row())
        try:
            kind = (self.table.item(row, 0).text() or "").strip()
            name = (self.table.item(row, 1).text() or "").strip()
        except Exception:
            return
        raw = (item.text() or "").strip()

        p = self.app_core.project or {}
        p2, _ = ensure_variables(p)
        v = dict(p2.get("variables") or {})
        num = dict(v.get("number") or {})
        tog = dict(v.get("toggle") or {})

        if kind == "number":
            try:
                num[name] = float(raw)
            except Exception:
                # revert
                self._suspend_item_changed = True
                try:
                    item.setText(f"{float(num.get(name, 0.0)):.4f}")
                finally:
                    self._suspend_item_changed = False
                return
        else:
            val = raw.lower() in ("1", "true", "yes", "on", "y", "t")
            tog[name] = bool(val)

        v["number"] = num
        v["toggle"] = tog
        p3 = dict(p2)
        p3["variables"] = v
        self.app_core.project = p3
