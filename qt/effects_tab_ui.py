from __future__ import annotations

from typing import Any, Dict, List, Optional

from qt.qt_compat import QtCore, QtWidgets  # type: ignore


class EffectsTabUiMixin:
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel("Behaviors are the systems that generate pixels for a layer. The output of behaviors becomes the layer image. Assign a behavior to each layer to produce visual output.")
        intro.setWordWrap(True)
        root.addWidget(intro)
        header = QtWidgets.QLabel("Assign behaviors to layers.")
        header.setWordWrap(True)
        root.addWidget(header)
        quick = QtWidgets.QLabel("Quick Tip: Behaviors define how LEDs evolve over time or react to signals.")
        quick.setWordWrap(True)
        root.addWidget(quick)
        rel = QtWidgets.QLabel("Behavior → Layer relationship: Each layer runs exactly one behavior. Behaviors generate the pixels that fill the layer.")
        rel.setWordWrap(True)
        root.addWidget(rel)

        self.grp_era_gate = QtWidgets.QGroupBox("Historical Era Gate")
        eg = QtWidgets.QVBoxLayout(self.grp_era_gate)
        self.lbl_era_gate = QtWidgets.QLabel(
            "The visible behavior list is limited by the active historical era. "
            "Before the effect-picker plateau, only era-accurate behavior choices should appear."
        )
        self.lbl_era_gate.setWordWrap(True)
        eg.addWidget(self.lbl_era_gate)
        self.lbl_era_gate_status = QtWidgets.QLabel("")
        self.lbl_era_gate_status.setWordWrap(True)
        eg.addWidget(self.lbl_era_gate_status)
        root.addWidget(self.grp_era_gate)

        self.grp_mode_help = QtWidgets.QGroupBox("Mode Help")
        mh = QtWidgets.QVBoxLayout(self.grp_mode_help)
        self.lbl_mode_help = QtWidgets.QLabel(
            "Effect Picker mode keeps the workflow simple. Full Modulo restores the whole behavior engine workflow."
        )
        self.lbl_mode_help.setWordWrap(True)
        mh.addWidget(self.lbl_mode_help)
        mh_row = QtWidgets.QHBoxLayout()
        self.btn_go_presets = QtWidgets.QPushButton("Go To Presets")
        mh_row.addWidget(self.btn_go_presets)
        self.btn_go_export = QtWidgets.QPushButton("Go To Export")
        mh_row.addWidget(self.btn_go_export)
        mh_row.addStretch(1)
        mh.addLayout(mh_row)
        root.addWidget(self.grp_mode_help)

        unlock_box = QtWidgets.QGroupBox("Advanced Control")
        ub = QtWidgets.QVBoxLayout(unlock_box)
        lbl = QtWidgets.QLabel("If the effect picker feels limiting, you can unlock the full Modulo workflow.")
        lbl.setWordWrap(True)
        ub.addWidget(lbl)
        self.btn_unlock_modulo = QtWidgets.QPushButton("Unlock Full Modulo")
        ub.addWidget(self.btn_unlock_modulo)
        ub.addStretch(1)
        root.addWidget(unlock_box)

        usage = QtWidgets.QLabel("Behavior Usage: Select a layer, choose a behavior, then apply it to that layer or add it as a new layer.")
        usage.setWordWrap(True)
        root.addWidget(usage)
        flow = QtWidgets.QLabel("Behavior Workflow: Add Behavior Layer to create a new layer, or Apply To Selected Layer to change the current layer.")
        flow.setWordWrap(True)
        root.addWidget(flow)
        next_step = QtWidgets.QLabel("Next: go to Signals, Variables, and Rules if the behavior should react over time, audio, or state.")
        next_step.setWordWrap(True)
        root.addWidget(next_step)
        prev_step = QtWidgets.QLabel("Layers define the stack that behaviors are assigned to.")
        prev_step.setWordWrap(True)
        root.addWidget(prev_step)

        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Behaviors"))
        hdr.addStretch(1)
        root.addLayout(hdr)

        intro2 = QtWidgets.QLabel(
            "Choose what this layer does. In Effect Picker mode this works like a normal effect browser. "
            "In Full Modulo it is the behavior stage of the workflow."
        )
        intro2.setWordWrap(True)
        root.addWidget(intro2)

        filt = QtWidgets.QHBoxLayout()
        self.txt_search = QtWidgets.QLineEdit()
        self.txt_search.setPlaceholderText("Search behaviors…")
        self.txt_search.textChanged.connect(self._rebuild)
        filt.addWidget(self.txt_search, 2)
        self.chk_shipped = QtWidgets.QCheckBox("Shipped only")
        self.chk_shipped.setChecked(True)
        self.chk_shipped.stateChanged.connect(self._rebuild)
        filt.addWidget(self.chk_shipped, 0)
        root.addLayout(filt)

        body = QtWidgets.QHBoxLayout()
        root.addLayout(body, 1)
        self.list = QtWidgets.QListWidget()
        self.list.currentRowChanged.connect(self._select)
        body.addWidget(self.list, 2)

        right = QtWidgets.QVBoxLayout()
        body.addLayout(right, 3)
        self.lbl_title = QtWidgets.QLabel("—")
        f = self.lbl_title.font(); f.setBold(True); self.lbl_title.setFont(f)
        right.addWidget(self.lbl_title)
        self.lbl_key = QtWidgets.QLabel("")
        self.lbl_key.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        right.addWidget(self.lbl_key)
        self.lbl_export = QtWidgets.QLabel("")
        right.addWidget(self.lbl_export)
        self.txt_desc = QtWidgets.QTextEdit(); self.txt_desc.setReadOnly(True)
        right.addWidget(self.txt_desc, 1)

        btns = QtWidgets.QHBoxLayout()
        self.btn_apply_selected = QtWidgets.QPushButton("Apply To Selected Layer")
        self.btn_apply_selected.clicked.connect(self._apply_to_selected_layer)
        btns.addWidget(self.btn_apply_selected)
        self.btn_add_with_behavior = QtWidgets.QPushButton("Add Behavior Layer")
        self.btn_add_with_behavior.clicked.connect(self._add_with_behavior)
        btns.addWidget(self.btn_add_with_behavior)
        self.btn_add = QtWidgets.QPushButton("Add as Layer")
        self.btn_add.clicked.connect(self._add)
        btns.addWidget(self.btn_add)
        btns.addStretch(1)
        right.addLayout(btns)

        self._rows: List[Dict[str, Any]] = []

        try:
            if not self._can_add_layer_under_era_gate():
                try:
                    self.lbl_era_gate_status.setText(f"Era gate: layer limit reached ({self._era_max_layers()}).")
                except Exception:
                    pass
                return
            self.btn_unlock_modulo.clicked.connect(self._unlock_full_modulo)
            self.btn_go_presets.clicked.connect(self._goto_presets_tab)
            self.btn_go_export.clicked.connect(self._goto_export_tab)
        except Exception:
            pass

        self._rebuild()
