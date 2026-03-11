from __future__ import annotations

from qt.qt_compat import QtCore, QtGui, QtWidgets  # type: ignore
from qt.wiretap_support import set_log_panel


class _DiagnosticsDockWiretapBridge:
    def __init__(self, console):
        self._console = console

    def log(self, line: str) -> None:
        try:
            self._console._log(str(line))
        except Exception:
            pass


def build_diagnostics_console_ui(self) -> None:
    host = QtWidgets.QWidget(self)
    self.setWidget(host)
    root = QtWidgets.QVBoxLayout(host)
    root.setContentsMargins(8, 8, 8, 8)
    root.setSpacing(8)

    header = QtWidgets.QHBoxLayout()
    header.setSpacing(8)
    root.addLayout(header)

    def pill(label: str) -> QtWidgets.QLabel:
        w = QtWidgets.QLabel(label)
        w.setMinimumHeight(20)
        w.setStyleSheet(
            "QLabel { padding: 3px 8px; border-radius: 9px; background: #222; color: #ddd; }"
        )
        return w

    self.lbl_phase6 = pill("Phase6: ?")
    self.lbl_rules = pill("Rules: ?")
    self.lbl_preview = pill("Preview: ?")
    self.lbl_export = pill("Parity: ?")
    self.lbl_surface = pill("Surface: ?")
    for w in (self.lbl_phase6, self.lbl_rules, self.lbl_preview, self.lbl_export, self.lbl_surface):
        header.addWidget(w)
    header.addStretch(1)

    runner = QtWidgets.QHBoxLayout()
    runner.addWidget(QtWidgets.QLabel("Diagnostic:"))
    self.cmb_probe = QtWidgets.QComboBox()
    self.cmb_probe.setMinimumWidth(460)
    self.cmb_probe.setMaxVisibleItems(28)
    try:
        self.cmb_probe.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
    except Exception:
        pass

    self._probe_specs_by_comboindex = {}
    self._probe_specs = [
        ("Quick Start", ("header", None)),
        ("System Triage", ("probe", self._probe_triage)),
        ("Full Health Check", ("door", "E1")),
        ("Preview Chain Inspector", ("probe", self._probe_preview_chain)),
        ("Wiretap & UI", ("header", None)),
        ("Wiretap Focus Snapshot", ("probe", self._probe_wiretap_focus_snapshot)),
        ("Wiretap Hover Snapshot", ("probe", self._probe_wiretap_hover_snapshot)),
        ("Wiretap UI Dump", ("probe", self._probe_wiretap_dump)),
        ("UI Layout Dump", ("probe", self._probe_dump_ui_layout)),
        ("Core Wiring", ("header", None)),
        ("Composition Suite (D1)", ("door", "D1")),
        ("Override Priority (J1)", ("door", "J1")),
        (
            "Rules Parity",
            (
                "probe",
                lambda: __import__("app.rules_parity_probe", fromlist=["run_rules_parity_probe"]).run_rules_parity_probe(
                    self.app_core.project, self.app_core
                ),
            ),
        ),
        ("Resolver Inspector", ("probe", self._probe_resolver_inspector)),
        ("Layer Field Probe", ("probe", self._probe_layer_field_scan)),
        ("Layer Wiring Inspector", ("probe", self._probe_layer_wiring)),
        ("Surface & Mapping", ("header", None)),
        ("Surface / Mapping Inspector", ("probe", self._probe_surface_mapping)),
        ("Mapping Parity Check (Quick)", ("probe", lambda: self._probe_mapping_parity("quick"))),
        ("Mapping Parity Check (Full)", ("probe", lambda: self._probe_mapping_parity("full"))),
        ("Mapping Parity Flags Sweep", ("probe", self._probe_mapping_parity_sweep)),
        ("Export & Runtime", ("header", None)),
        ("Preview / Export Parity", ("probe", self._probe_preview_export_semantic_parity)),
        (
            "Kernel Export Probe",
            (
                "probe",
                lambda: __import__("app.kernel_export_probe", fromlist=["run_kernel_export_probe"]).run_kernel_export_probe(),
            ),
        ),
        ("Audio Wiring Dump", ("probe", self._probe_audio_signals)),
        ("Runtime Diagnostics Tail", ("probe", lambda: self._runtime_diag_tail())),
        ("Doors & Deep Checks", ("header", None)),
        ("Operator Overrides (F1)", ("door", "F1")),
        ("Canonical Resolver Door (I1)", ("door", "I1")),
        ("Time Signals (G1)", ("door", "G1")),
        ("Audio Signals (H1)", ("door", "H1")),
        ("Persistence Policy (K1)", ("door", "K1")),
        ("Export Canonical Params (L1)", ("door", "L1")),
        ("Preview ↔ Export Semantic Door (M1)", ("door", "M1")),
        ("Layer Composition (C1)", ("door", "C1")),
        ("Canonical Address Registry", ("probe", self._probe_canonical_registry)),
        (
            "Project Round-Trip Check",
            (
                "probe",
                lambda: __import__(
                    "app.project_roundtrip_probe", fromlist=["run_project_roundtrip_probe", "format_probe_result"]
                ).format_probe_result(
                    __import__("app.project_roundtrip_probe", fromlist=["run_project_roundtrip_probe"]).run_project_roundtrip_probe(
                        self.app_core.project
                    )
                ),
            ),
        ),
        (
            "Rules Parity Cases",
            (
                "probe",
                lambda: __import__("app.rules_parity_probe", fromlist=["run_rules_parity_cases"]).run_rules_parity_cases(
                    self.app_core.project, self.app_core
                ),
            ),
        ),
        ("Preview Visibility Mode Check", ("probe", self._probe_preview_display_assertion)),
        ("Render Output Check", ("probe", self._probe_per_cell_render_assertion)),
        ("Painted Widget Output", ("probe", self._probe_widget_paint_proof)),
        ("Visible Strip Preview Proof", ("probe", self._probe_visible_strip_preview_proof)),
        ("Effect Rendering Audit", ("probe", self._probe_effect_audit)),
        ("Full Audit", ("full_audit", None)),
    ]

    _last_header = False
    for idx, (label, spec) in enumerate(self._probe_specs):
        kind, _payload = spec
        if kind == "header" and idx > 0 and not _last_header:
            try:
                self.cmb_probe.insertSeparator(self.cmb_probe.count())
            except Exception:
                pass
        self.cmb_probe.addItem(label)
        combo_index = self.cmb_probe.count() - 1
        self._probe_specs_by_comboindex[combo_index] = (label, spec)
        model = self.cmb_probe.model()
        item = model.item(combo_index)
        if kind == "header" and item is not None:
            item.setEnabled(False)
            item.setForeground(QtGui.QBrush(QtGui.QColor("#9aa7b4")))
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        _last_header = kind == "header"

    for i in range(self.cmb_probe.count()):
        spec_entry = self._probe_specs_by_comboindex.get(i)
        if spec_entry and spec_entry[1][0] != "header":
            self.cmb_probe.setCurrentIndex(i)
            break

    runner.addWidget(self.cmb_probe, 1)
    self.chk_clean_each = QtWidgets.QCheckBox("Clean each")
    self.chk_clean_each.setChecked(True)
    runner.addWidget(self.chk_clean_each)
    self.spn_repeat = QtWidgets.QSpinBox()
    self.spn_repeat.setRange(1, 200)
    self.spn_repeat.setValue(20)
    self.spn_repeat.setSuffix("x")
    self.spn_repeat.setToolTip("Used for Doors Open items only")
    runner.addWidget(self.spn_repeat)
    self.btn_run_probe = QtWidgets.QPushButton("Run")
    self.btn_run_probe.clicked.connect(self._run_selected_probe)
    runner.addWidget(self.btn_run_probe)
    self.btn_hb = QtWidgets.QPushButton("Start Heartbeat")
    self.btn_hb.clicked.connect(self._toggle_heartbeat)
    runner.addWidget(self.btn_hb)
    self.btn_snapshot = QtWidgets.QPushButton("Snapshot Now")
    self.btn_snapshot.clicked.connect(self._snapshot_now)
    runner.addWidget(self.btn_snapshot)
    self.btn_clear = QtWidgets.QPushButton("Clear Output")
    runner.addWidget(self.btn_clear)
    self.btn_copy = QtWidgets.QPushButton("Copy Output")
    runner.addWidget(self.btn_copy)
    root.addLayout(runner)

    self.lbl_next = QtWidgets.QLabel(
        "Diagnostics, triage, and wiretap live only in this hideable dock. The runner is grouped by job: Quick Start, Wiretap & UI, Core Wiring, Surface & Mapping, Export & Runtime, then deep checks. Start with System Triage, Full Health Check, and Preview Chain Inspector. Press F12 to hide/show this console."
    )
    self.lbl_next.setWordWrap(True)
    self.lbl_next.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    root.addWidget(self.lbl_next)

    self.prg_runs = QtWidgets.QProgressBar()
    self.prg_runs.setRange(0, 1)
    self.prg_runs.setValue(0)
    self.prg_runs.setTextVisible(True)
    self.prg_runs.setFormat("Idle")
    root.addWidget(self.prg_runs)

    self.lbl_hb_detail = QtWidgets.QLabel("tick: 0   last_eval: —   last_fired: —")
    self.lbl_hb_detail.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    root.addWidget(self.lbl_hb_detail)

    self.lbl_audit_summary = QtWidgets.QLabel("No diagnostics run yet.")
    self.lbl_audit_summary.setWordWrap(True)
    self.lbl_audit_summary.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    root.addWidget(self.lbl_audit_summary)

    self.log = QtWidgets.QPlainTextEdit()
    self.log.setReadOnly(True)
    self.log.setObjectName("diagnostics_console_log")
    self.log.setMinimumWidth(620)
    root.addWidget(self.log, 1)

    self.txt_audit_details = self.log
    try:
        set_log_panel(self.log)
    except Exception:
        pass
    try:
        self.app_core.wiretap = _DiagnosticsDockWiretapBridge(self)
    except Exception:
        pass
    self.btn_clear.clicked.connect(self.log.clear)
    self.btn_copy.clicked.connect(self._copy_report)

    self._ui_timer = QtCore.QTimer(self)
    self._ui_timer.setInterval(250)
    self._ui_timer.timeout.connect(self._refresh_status)
    self._ui_timer.start()

    self._hb_timer = QtCore.QTimer(self)
    self._hb_timer.setInterval(50)
    self._hb_timer.timeout.connect(self._heartbeat_tick)

    self._log("[DiagnosticsConsole] ready. Press F12 to toggle console.")
