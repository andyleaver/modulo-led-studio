from __future__ import annotations

from typing import Optional

from qt.qt_compat import QtCore, QtWidgets  # type: ignore

from qt.signals_panel import SignalsPanel

class SignalsTab(QtWidgets.QWidget):
    """Signals tab (mounted from SignalsPanel)."""

    def __init__(self, app_core, controller, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller
        self._all_signal_routes = []

        root = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            "Signals feed the system with data such as audio, time, and derived metrics. Use this before Variables and Rules."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.grp_signal_gate = QtWidgets.QGroupBox("Historical Signal Gate")
        sg = QtWidgets.QVBoxLayout(self.grp_signal_gate)
        self.lbl_signal_gate = QtWidgets.QLabel("")
        self.lbl_signal_gate.setWordWrap(True)
        sg.addWidget(self.lbl_signal_gate)
        root.addWidget(self.grp_signal_gate)

        routing_hdr = QtWidgets.QLabel("Signal Routing Inspector")
        routing_hdr.setStyleSheet("font-weight:600;")
        root.addWidget(routing_hdr)

        routing_info = QtWidgets.QLabel(
            "Browse canonical signal-style addresses and related routing targets used across layers, vars, rules, and operators."
        )
        routing_info.setWordWrap(True)
        root.addWidget(routing_info)

        routing_row = QtWidgets.QHBoxLayout()
        self.txt_signal_filter = QtWidgets.QLineEdit()
        self.txt_signal_filter.setPlaceholderText(
            "Filter routing addresses (signal, vars, postfx, params, layers...)"
        )
        routing_row.addWidget(self.txt_signal_filter, 1)

        self.btn_refresh_signal_routes = QtWidgets.QPushButton("Refresh Routes")
        routing_row.addWidget(self.btn_refresh_signal_routes)

        self.btn_copy_signal_route = QtWidgets.QPushButton("Copy Selected Route")
        routing_row.addWidget(self.btn_copy_signal_route)
        root.addLayout(routing_row)

        self.list_signal_routes = QtWidgets.QListWidget()
        root.addWidget(self.list_signal_routes, 1)

        self.txt_selected_signal_route = QtWidgets.QLineEdit()
        self.txt_selected_signal_route.setReadOnly(True)
        root.addWidget(self.txt_selected_signal_route)

        self.lbl_signal_summary = QtWidgets.QLabel("")
        self.lbl_signal_summary.setWordWrap(True)
        root.addWidget(self.lbl_signal_summary)

        step = QtWidgets.QLabel("Define signal inputs such as time, audio, and derived metrics.")
        step.setStyleSheet("font-weight:600;")
        root.addWidget(step)

        summary = QtWidgets.QLabel(
            "Workflow Summary: signals provide reusable inputs that can drive rules, behaviors, variables, and operators."
        )
        summary.setWordWrap(True)
        root.addWidget(summary)

        divider = QtWidgets.QLabel("Signal Sources")
        divider.setStyleSheet("font-weight:600; margin-top:6px;")
        root.addWidget(divider)

        next_step = QtWidgets.QLabel(
            "Next: use Variables for shared state, then Rules to connect signals to actions."
        )
        next_step.setWordWrap(True)
        root.addWidget(next_step)

        root.setContentsMargins(0, 0, 0, 0)
        self._signals_panel = SignalsPanel(app_core)
        root.addWidget(self._signals_panel)

        self.btn_refresh_signal_routes.clicked.connect(self._reload_signal_routes)
        self.btn_copy_signal_route.clicked.connect(self._copy_selected_signal_route)
        self.list_signal_routes.currentTextChanged.connect(self._on_signal_route_selected)
        self.txt_signal_filter.textChanged.connect(self._filter_signal_routes)

        QtCore.QTimer.singleShot(0, self._reload_signal_routes)
        QtCore.QTimer.singleShot(0, self._apply_signal_gate)

    def _project(self):
        try:
            p = getattr(self.app_core, "project", {}) or {}
            return p if isinstance(p, dict) else {}
        except Exception:
            return {}

    def _signal_route_addresses(self):
        p = self._project()
        out = []

        for base in [
            "signals.audio.low",
            "signals.audio.mid",
            "signals.audio.high",
            "signals.time.seconds",
            "signals.time.minutes",
            "signals.clock.hour",
            "signals.clock.minute",
        ]:
            out.append(base)

        layers = p.get("layers") or []
        if isinstance(layers, list):
            for i, ly in enumerate(layers):
                out.extend([
                    f"layers[{i}].enabled",
                    f"layers[{i}].opacity",
                    f"layers[{i}].blend_mode",
                    f"layers[{i}].behavior",
                ])
                if isinstance(ly, dict):
                    params = ly.get("params") or {}
                    if isinstance(params, dict):
                        for k in sorted(params.keys()):
                            out.append(f"layers[{i}].params.{k}")

        vars_dict = p.get("vars") or p.get("variables") or {}
        if isinstance(vars_dict, dict):
            for k in sorted(vars_dict.keys()):
                out.append(f"vars.{k}")

        postfx = p.get("postfx") or {}
        if isinstance(postfx, dict):
            for k in sorted(postfx.keys()):
                out.append(f"project.postfx.{k}")

        seen = set()
        uniq = []
        for a in out:
            if a not in seen:
                uniq.append(a)
                seen.add(a)
        return uniq

    def _signal_summary_text(self, addrs):
        signals_n = sum(1 for a in addrs if a.startswith("signals."))
        layers_n = sum(1 for a in addrs if a.startswith("layers["))
        vars_n = sum(1 for a in addrs if a.startswith("vars."))
        postfx_n = sum(1 for a in addrs if a.startswith("project.postfx."))
        return (
            f"Route Summary: signals {signals_n} · "
            f"layer addresses {layers_n} · vars {vars_n} · operator keys {postfx_n}"
        )

    def _reload_signal_routes(self):
        try:
            current = str(self.txt_selected_signal_route.text() or "").strip()
        except Exception:
            current = ""

        addrs = self._signal_route_addresses()
        self._all_signal_routes = list(addrs)
        try:
            self.lbl_signal_summary.setText(self._signal_summary_text(addrs))
        except Exception:
            pass

        self.list_signal_routes.blockSignals(True)
        self.list_signal_routes.clear()
        for addr in addrs:
            self.list_signal_routes.addItem(addr)
        self.list_signal_routes.blockSignals(False)

        if self.list_signal_routes.count() > 0:
            row = 0
            if current:
                matches = self.list_signal_routes.findItems(current, QtCore.Qt.MatchFlag.MatchExactly)
                if matches:
                    row = self.list_signal_routes.row(matches[0])
            self.list_signal_routes.setCurrentRow(row)
            try:
                self.txt_selected_signal_route.setText(self.list_signal_routes.item(row).text())
            except Exception:
                pass
        else:
            self.txt_selected_signal_route.setText("")

    def _filter_signal_routes(self, text: str):
        try:
            base = list(getattr(self, "_all_signal_routes", []))
            q = str(text or "").strip().lower()
            filtered = [a for a in base if q in a.lower()] if q else base

            self.list_signal_routes.blockSignals(True)
            self.list_signal_routes.clear()
            for addr in filtered:
                self.list_signal_routes.addItem(addr)
            self.list_signal_routes.blockSignals(False)

            if filtered:
                self.list_signal_routes.setCurrentRow(0)
            else:
                self.txt_selected_signal_route.setText("")
        except Exception:
            pass

    def _on_signal_route_selected(self, text: str):
        try:
            self.txt_selected_signal_route.setText(str(text or ""))
        except Exception:
            pass

    def _copy_selected_signal_route(self):
        try:
            text = str(self.txt_selected_signal_route.text() or "").strip()
            if not text:
                return
            app = QtWidgets.QApplication.instance()
            if app is not None:
                cb = app.clipboard()
                if cb is not None:
                    cb.setText(text)
        except Exception:
            pass

    def _signal_gates(self):
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            return dict(fn() if callable(fn) else {})
        except Exception:
            return {}

    def _apply_signal_gate(self):
        gates = self._signal_gates()
        allow_audio = bool(gates.get("allow_audio", True))
        allow_rules = bool(gates.get("allow_rules", True))
        model = str(gates.get("control_model") or "").strip().lower()
        enabled = bool(allow_audio or allow_rules)
        try:
            self.lbl_signal_gate.setText(
                f"Historical signal gate: control model = {model or 'full_modulo'} · "
                f"signal routing {'enabled' if enabled else 'locked'}."
            )
        except Exception:
            pass
        for w in [getattr(self, "_signals_panel", None), self.btn_refresh_signal_routes, self.btn_copy_signal_route, self.txt_signal_filter, self.list_signal_routes]:
            try:
                if w is not None:
                    w.setEnabled(enabled)
            except Exception:
                pass
