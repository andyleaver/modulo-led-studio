from __future__ import annotations

"""Signals Inspector (Phase 6.1)

Minimal UI panel that displays current SignalBus values.

Reads from app_core.get_signal_snapshot() (CoreBridge) and displays a searchable
table of signal names and current values.
"""

from PyQt6 import QtCore, QtWidgets


def _fmt_value(v) -> str:
    try:
        if isinstance(v, float):
            return f"{v:.4f}"
        if isinstance(v, (list, tuple)):
            # Keep compact.
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

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search signals… (e.g., audio.energy)")
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.setToolTip("Force refresh the signals table")
        header.addWidget(QtWidgets.QLabel("Signals"))
        header.addWidget(self.search, 1)
        header.addWidget(self.btn_refresh)
        outer.addLayout(header)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Name", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        outer.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.search.textChanged.connect(self.refresh)
        self.btn_refresh.clicked.connect(self.refresh)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self.refresh()

    def refresh(self):
        # Pull snapshot
        snap = {}
        try:
            if hasattr(self.app_core, "get_signal_snapshot"):
                snap = self.app_core.get_signal_snapshot() or {}
        except Exception:
            snap = {}

        # Filter
        q = str(self.search.text() or "").strip().lower()
        items = []
        try:
            for k in sorted(snap.keys(), key=lambda x: str(x)):
                if q and q not in str(k).lower():
                    continue
                items.append((str(k), snap.get(k)))
        except Exception:
            items = []

        self.table.setRowCount(len(items))
        for row, (name, val) in enumerate(items):
            it0 = QtWidgets.QTableWidgetItem(name)
            it1 = QtWidgets.QTableWidgetItem(_fmt_value(val))
            self.table.setItem(row, 0, it0)
            self.table.setItem(row, 1, it1)

        try:
            self.status.setText(f"{len(items)} signals shown" + (" (filtered)" if q else ""))
        except Exception:
            pass
