try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except ImportError:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

from qt.export_panel import ExportPanel

class ExportTab(QtWidgets.QWidget):
    """Export tab container extracted from qt_app.py."""

    def __init__(self, app_core, controller=None):
        super().__init__()
        self.app_core = app_core
        self.controller = controller

        outer = QtWidgets.QVBoxLayout(self)
        step = QtWidgets.QLabel("Export")
        step.setStyleSheet("font-weight:600;")
        outer.addWidget(step)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Export"))
        hdr.addStretch(1)
        outer.addLayout(hdr)

        intro = QtWidgets.QLabel("Export converts your project into firmware for supported hardware targets. Use this after building the project in the earlier workflow areas.")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        self.grp_export_gate = QtWidgets.QGroupBox("Historical Export Gate")
        eg = QtWidgets.QVBoxLayout(self.grp_export_gate)
        self.lbl_export_gate = QtWidgets.QLabel("")
        self.lbl_export_gate.setWordWrap(True)
        eg.addWidget(self.lbl_export_gate)
        outer.addWidget(self.grp_export_gate)

        self.grp_simple_export = QtWidgets.QGroupBox("Simple Export Path")
        sx = QtWidgets.QVBoxLayout(self.grp_simple_export)

        self.lbl_simple_export = QtWidgets.QLabel(
            "In Effect Picker mode the shortest path is Behaviors → Presets → Playlist (optional) → Export."
        )
        self.lbl_simple_export.setWordWrap(True)
        sx.addWidget(self.lbl_simple_export)

        row = QtWidgets.QHBoxLayout()
        self.btn_export_to_behaviors = QtWidgets.QPushButton("Back To Behaviors")
        row.addWidget(self.btn_export_to_behaviors)
        self.btn_export_unlock = QtWidgets.QPushButton("Unlock Full Modulo")
        row.addWidget(self.btn_export_unlock)
        row.addStretch(1)
        sx.addLayout(row)

        outer.addWidget(self.grp_simple_export)
        self.btn_export_to_behaviors.clicked.connect(self._goto_behaviors_tab)
        self.btn_export_unlock.clicked.connect(self._unlock_full_modulo)
        stage = QtWidgets.QLabel("Build the verified project for hardware output.")
        stage.setStyleSheet("font-weight:600;")
        outer.addWidget(stage)
        summary = QtWidgets.QLabel("Workflow Summary: export is the final handoff once the project has been configured, sequenced if needed, and verified.")
        summary.setWordWrap(True)
        outer.addWidget(summary)
        quick = QtWidgets.QLabel("Quick Tip: Export is the hardware handoff stage. Use it only after the project is configured and verified.")
        quick.setWordWrap(True)
        outer.addWidget(quick)
        final_step = QtWidgets.QLabel("Final Build Step: Export comes after Surface, Targeting, Layers, Behaviors, Rules, and Operators are set up.")
        final_step.setWordWrap(True)
        outer.addWidget(final_step)
        workflow_hint = QtWidgets.QLabel("Workflow Reminder: Surface → Targets → Layers → Behaviors → Signals → Variables → Rules → Operators → Presets → Playlist → Export")
        workflow_hint.setWordWrap(True)
        workflow_hint.setStyleSheet("font-weight:600;")
        outer.addWidget(workflow_hint)
        ready = QtWidgets.QLabel("Export Ready Check: the project should already be configured, targeted, layered, verified, and stable before you export.")
        ready.setWordWrap(True)
        outer.addWidget(ready)
        finish = QtWidgets.QLabel("Final Stage: Export turns the verified project into hardware output. If something looks wrong, go back to Diagnostics or the earlier workflow tabs before exporting again.")
        finish.setWordWrap(True)
        outer.addWidget(finish)

        self.panel = ExportPanel(app_core)
        self._scroll = QtWidgets.QScrollArea()

        self._scroll.setWidgetResizable(True)

        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._scroll.setWidget(self.panel)

        outer.addWidget(self._scroll, 1)
        self._apply_export_gate()

    def _goto_tab_by_prefix(self, prefix: str):
        try:
            tabs = getattr(self.controller, "tabs", None) if self.controller is not None else None
            if tabs is None:
                return
            for i in range(tabs.count()):
                label = str(tabs.tabText(i) or "")
                if label == prefix or label.startswith(prefix) or prefix in label:
                    tabs.setCurrentIndex(i)
                    return True
        except Exception:
            pass
        return False

    def _goto_behaviors_tab(self):
        self._goto_tab_by_prefix("Behaviour") or self._goto_tab_by_prefix("Layers")

    def _unlock_full_modulo(self):
        try:
            if self.controller and hasattr(self.controller, "_apply_studio_mode"):
                self.controller._apply_studio_mode("full_modulo")
        except Exception:
            pass

    def _export_gates(self):
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            return dict(fn() if callable(fn) else {})
        except Exception:
            return {}

    def _apply_export_gate(self):
        gates = self._export_gates()
        allow_export = bool(gates.get("allow_export", True))
        model = str(gates.get("control_model") or "").strip().lower()
        try:
            self.lbl_export_gate.setText(
                f"Historical export gate: control model = {model or 'full_modulo'} · "
                f"export {'enabled' if allow_export else 'locked'}."
            )
        except Exception:
            pass
        try:
            self.panel.setEnabled(bool(allow_export))
        except Exception:
            pass
