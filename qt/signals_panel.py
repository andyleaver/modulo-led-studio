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

"""Signals Inspector.

Workflow-facing panel that shows live signal values plus contract metadata
from the canonical signal registry. Keeps signal truth visible without
reducing access to raw runtime values.
"""

try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

def _fmt_value(v) -> str:
    try:
        if isinstance(v, float):
            return f"{v:.4f}"
        if isinstance(v, (list, tuple)):
            if len(v) <= 12:
                return "[" + ", ".join(_fmt_value(x) for x in v) + "]"
            return "[" + ", ".join(_fmt_value(x) for x in v[:12]) + ", …]"
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "(none)"
        return str(v)
    except Exception:
        return "(error)"

class SignalsPanel(QtWidgets.QWidget):
    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core
        self._defs = {}

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search signals… (e.g., audio.energy)")
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.setToolTip("Force refresh the signals table")
        self.btn_copy_key = QtWidgets.QPushButton("Copy Selected Key")
        self.btn_copy_key.setToolTip("Copy the selected signal key for rules / operators / routing")
        self.btn_copy_rule = QtWidgets.QPushButton("Copy Rule Snippet")
        self.btn_copy_rule.setToolTip("Copy a starter rule condition using the selected signal")
        header.addWidget(QtWidgets.QLabel("Signals"))
        header.addWidget(self.search, 1)
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_copy_key)
        header.addWidget(self.btn_copy_rule)
        outer.addLayout(header)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Value", "Preview", "Export"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        outer.addWidget(self.table, 1)

        details_box = QtWidgets.QGroupBox("Selected Signal")
        dlay = QtWidgets.QVBoxLayout(details_box)
        dlay.setContentsMargins(8, 8, 8, 8)
        dlay.setSpacing(6)
        self.lbl_selected = QtWidgets.QLabel("No signal selected.")
        self.lbl_selected.setWordWrap(True)
        dlay.addWidget(self.lbl_selected)
        outer.addWidget(details_box, 0)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.search.textChanged.connect(self.refresh)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_copy_key.clicked.connect(self._copy_selected_key)
        self.btn_copy_rule.clicked.connect(self._copy_rule_snippet)
        self.table.itemSelectionChanged.connect(self._update_selected_details)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self.refresh()

    def _load_registry_defs(self):
        defs = {}
        try:
            from app.signal_registry import REGISTRY
            for sd in REGISTRY.all():
                defs[str(sd.key)] = sd
        except Exception as e:
            _diag_exc(e, "qt/signals_panel.py.signal_registry")
        self._defs = defs

    def _copy_selected_key(self):
        try:
            row = self.table.currentRow()
            if row < 0:
                return
            item = self.table.item(row, 0)
            if item is None:
                return
            key = str(item.text() or "")
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.clipboard().setText(key)
            self.status.setText(f"Copied signal key: {key}")
        except Exception as e:
            _diag_exc(e, "qt/signals_panel.py.copy_selected_key")

    def _selected_signal_key(self) -> str:
        try:
            row = self.table.currentRow()
            if row < 0:
                return ""
            item = self.table.item(row, 0)
            return str(item.text() or "") if item is not None else ""
        except Exception:
            return ""

    def _copy_rule_snippet(self):
        try:
            key = self._selected_signal_key()
            if not key:
                return
            snippet = (
                '{\n'
                '  "when": {\n'
                f'    "signal": "{key}",\n'
                '    "op": ">",\n'
                '    "value": 0.5\n'
                '  },\n'
                '  "then": {\n'
                '    "set": {\n'
                '      "layers[0].opacity": 1.0\n'
                '    }\n'
                '  }\n'
                '}'
            )
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.clipboard().setText(snippet)
            self.status.setText(f"Copied rule snippet for signal: {key}")
        except Exception as e:
            _diag_exc(e, "qt/signals_panel.py.copy_rule_snippet")

    def _update_selected_details(self):
        try:
            row = self.table.currentRow()
            if row < 0:
                self.lbl_selected.setText("No signal selected.")
                return
            item = self.table.item(row, 0)
            if item is None:
                self.lbl_selected.setText("No signal selected.")
                return
            key = str(item.text() or "")
            value_item = self.table.item(row, 1)
            val = value_item.text() if value_item is not None else ""
            sd = self._defs.get(key)
            if sd is None:
                self.lbl_selected.setText(
                    f"Key: {key}\nValue: {val}\n\nNo registry metadata available for this runtime signal."
                )
                return
            self.lbl_selected.setText(
                f"Key: {key}\n"
                f"Label: {getattr(sd, 'label', key)}\n"
                f"Value: {val}\n"
                f"Preview: {'yes' if getattr(sd, 'available_in_preview', False) else 'no'}\n"
                f"Export: {'yes' if getattr(sd, 'available_in_export', False) else 'no'}\n"
                f"Notes: {getattr(sd, 'notes', '') or '(none)'}"
            )
        except Exception as e:
            _diag_exc(e, "qt/signals_panel.py.update_selected_details")

    def refresh(self):
        self._load_registry_defs()

        snap = {}
        try:
            if hasattr(self.app_core, "get_signal_snapshot"):
                snap = self.app_core.get_signal_snapshot() or {}
        except Exception:
            snap = {}

        q = str(self.search.text() or "").strip().lower()
        items = []
        try:
            keys = sorted(set(list(snap.keys()) + list(self._defs.keys())), key=lambda x: str(x))
            for k in keys:
                if q and q not in str(k).lower():
                    continue
                sd = self._defs.get(str(k))
                preview = "yes" if getattr(sd, "available_in_preview", True) else "no"
                export = "yes" if getattr(sd, "available_in_export", False) else "no"
                items.append((str(k), snap.get(k), preview, export))
        except Exception:
            items = []

        current_key = None
        try:
            row = self.table.currentRow()
            if row >= 0:
                item = self.table.item(row, 0)
                if item is not None:
                    current_key = str(item.text() or "")
        except Exception:
            current_key = None

        self.table.setRowCount(len(items))
        restore_row = -1
        for row, (name, val, preview, export) in enumerate(items):
            it0 = QtWidgets.QTableWidgetItem(name)
            it1 = QtWidgets.QTableWidgetItem(_fmt_value(val))
            it2 = QtWidgets.QTableWidgetItem(preview)
            it3 = QtWidgets.QTableWidgetItem(export)
            self.table.setItem(row, 0, it0)
            self.table.setItem(row, 1, it1)
            self.table.setItem(row, 2, it2)
            self.table.setItem(row, 3, it3)
            if current_key and name == current_key:
                restore_row = row

        if restore_row >= 0:
            self.table.selectRow(restore_row)

        try:
            runtime_only = 0
            registry_total = len(self._defs)
            for k in snap.keys():
                if str(k) not in self._defs:
                    runtime_only += 1
            self.status.setText(
                f"{len(items)} signals shown"
                + (" (filtered)" if q else "")
                + f" · registry: {registry_total} · runtime-only: {runtime_only}"
            )
        except Exception as e:
            _diag_exc(e, "qt/signals_panel.py.status")

        self._update_selected_details()
