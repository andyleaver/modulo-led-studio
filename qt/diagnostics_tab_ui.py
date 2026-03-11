
from __future__ import annotations

from qt.qt_compat import QtWidgets  # type: ignore


def build_diagnostics_tab_ui(owner):
    outer = QtWidgets.QVBoxLayout(owner)
    step = QtWidgets.QLabel("Diagnostics")
    step.setStyleSheet("font-weight:600;")
    outer.addWidget(step)
    outer.setContentsMargins(8, 8, 8, 8)
    outer.setSpacing(8)

    intro = QtWidgets.QLabel(
        "Diagnostics gives Full Modulo users access to engine proof tools, triage, parity checks, wiring inspection, and health reporting. These are part of the real app capability, not hidden internals."
    )
    intro.setWordWrap(True)
    outer.addWidget(intro)

    owner.grp_diag_gate = QtWidgets.QGroupBox("Historical Diagnostics Gate")
    dg = QtWidgets.QVBoxLayout(owner.grp_diag_gate)
    owner.lbl_diag_gate = QtWidgets.QLabel("")
    owner.lbl_diag_gate.setWordWrap(True)
    dg.addWidget(owner.lbl_diag_gate)
    outer.addWidget(owner.grp_diag_gate)

    owner.grp_mode_context = QtWidgets.QGroupBox("Mode Context")
    mc = QtWidgets.QVBoxLayout(owner.grp_mode_context)
    owner.lbl_mode_context = QtWidgets.QLabel(
        "Diagnostics remains visible in all modes. In Effect Picker mode it is for validation only; in Full Modulo it also helps inspect the full engine surfaces."
    )
    owner.lbl_mode_context.setWordWrap(True)
    mc.addWidget(owner.lbl_mode_context)
    row = QtWidgets.QHBoxLayout()
    owner.btn_mode_context_full = QtWidgets.QPushButton("Show Full Studio")
    row.addWidget(owner.btn_mode_context_full)
    row.addStretch(1)
    mc.addLayout(row)
    outer.addWidget(owner.grp_mode_context)

    for text, style in [
        ("Verify health, wiring, parity, and export-readiness.", "font-weight:600;"),
        ("Workflow Summary: diagnostics validates that the built project is correct before hardware export.", None),
        ("Quick Tip: Diagnostics proves that the project wiring, mapping, parity, and export-readiness are actually correct.", None),
        ("Diagnostics is the proof stage: use it to verify wiring, parity, health, and export-readiness after building the project.", None),
        ("Studio Workflow Reminder: Surface → Targets → Layers → Behaviors → Signals → Variables → Rules → Operators → Presets → Playlist → Export", "font-weight:600;"),
        ("Next: after the project verifies cleanly here, move to Export for the final build.", None),
        ("Operators, Presets, and Playlist shape and organize the project before verification.", None),
    ]:
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        if style:
            label.setStyleSheet(style)
        outer.addWidget(label)

    top = QtWidgets.QHBoxLayout()
    top.addWidget(QtWidgets.QLabel("What to run first:"))
    owner.test_picker = QtWidgets.QComboBox()
    owner.test_picker.setMinimumWidth(420)
    try:
        owner.test_picker.setMaxVisibleItems(28)
        owner.test_picker.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
    except Exception:
        pass
    owner._test_specs = [
        ("1. System Triage", owner._run_triage_summary),
        ("2. Full Health Check", owner._run_health),
        ("3. Preview Chain Inspector", owner._run_preview_chain_probe),
        ("4. Composition Suite", owner._run_composition_parity_probe),
        ("5. Override Priority", owner._run_resolver_priority_probe),
        ("6. Rules Parity", owner._run_rules_parity_probe),

        ("7. Resolver Inspector", owner._dump_resolver_inspector),
        ("8. Layer Wiring Inspector", owner._dump_layer_wiring),
        ("9. Layer Field Probe", owner._run_layer_field_probe),
        ("10. Surface / Mapping Inspector", owner._dump_surface_mapping),
        ("11. Mapping Parity (Quick)", lambda: owner._run_mapping_parity_probe(mode="quick")),
        ("12. Mapping Parity (Full)", lambda: owner._run_mapping_parity_probe(mode="full")),
        ("13. Mapping Parity Sweep", owner._run_mapping_parity_sweep),
        ("14. Mapping Parity Cases", owner._run_mapping_parity_cases),
        ("15. Mapping Pattern Probe", owner._run_mapping_pattern_probe),

        ("16. Kernel Export Probe", owner._run_kernel_export_probe),
        ("17. Project Round-Trip", owner._run_project_roundtrip_probe),
        ("18. Canonical Address Registry", owner._dump_canonical_registry),
        ("19. Effect Audit", owner._run_audit),
        ("20. UI Wiring Audit", owner._run_ui_wiring_audit),
        ("21. UI Layout Dump", owner._dump_ui),
        ("22. Audio Wiring Dump", owner._dump_audio),
        ("23. Runtime Diagnostics Tail", owner._dump_runtime_diags),
        ("24. Rules Parity Cases", owner._run_rules_parity_cases),
    ]
    for label, _fn in owner._test_specs:
        owner.test_picker.addItem(label)
    try:
        owner.test_picker.insertSeparator(6)
        owner.test_picker.insertSeparator(15)
        owner.test_picker.insertSeparator(18)
        owner.test_picker.setToolTip(
            "Run from top to bottom. Start with System Triage, then Health, then Preview/Composition/Override before deeper wiring or export checks."
        )
    except Exception:
        pass
    top.addWidget(owner.test_picker, 1)

    owner.btn_run = QtWidgets.QPushButton("Run Test")
    owner.btn_run.clicked.connect(owner._run_selected_test)
    top.addWidget(owner.btn_run)

    owner.btn_quick_health = QtWidgets.QPushButton("Run Quick Health Check")
    owner.btn_quick_health.clicked.connect(owner._run_quick_health_bundle)
    top.addWidget(owner.btn_quick_health)

    owner.chk_audio = QtWidgets.QCheckBox("Include audio effects")
    owner.chk_audio.setChecked(False)
    top.addWidget(owner.chk_audio)

    owner.btn_clear = QtWidgets.QPushButton("Clear")
    owner.btn_clear.clicked.connect(lambda: owner.out.setPlainText(""))
    top.addWidget(owner.btn_clear)
    outer.addLayout(top)

    owner.probe_output = QtWidgets.QPlainTextEdit()
    owner.probe_output.setObjectName('diagnostics_probe_output')
    owner.probe_output.setReadOnly(True)
    owner.probe_output.setMinimumHeight(140)
    owner.probe_output.setPlaceholderText('Probe Output')
    try:
        owner.probe_output.setStyleSheet('QPlainTextEdit{border:2px solid #444; border-radius:6px;}')
    except Exception:
        pass
    label = QtWidgets.QLabel('Probe Output')
    label.setObjectName('diagnostics_probe_output_label')
    try:
        font = label.font()
        font.setPointSize(max(10, font.pointSize() + 2))
        font.setBold(True)
        label.setFont(font)
    except Exception:
        pass
    outer.addWidget(label)
    outer.addWidget(owner.probe_output)

    owner.out = QtWidgets.QPlainTextEdit()
    owner.out.setReadOnly(True)
    try:
        owner.out.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
    except Exception:
        pass
    outer.addWidget(owner.out, 1)

    bottom = QtWidgets.QHBoxLayout()
    owner.btn_copy = QtWidgets.QPushButton("Copy report")
    owner.btn_copy.clicked.connect(owner._copy)
    bottom.addWidget(owner.btn_copy)
    bottom.addStretch(1)
    outer.addLayout(bottom)

    owner.out.setPlainText("Choose a diagnostics test and click Run Test…")
    return outer
