try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except ImportError:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

from qt.rules_panel import RulesPanel


class RulesTabUiMixin:
    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Rules"))
        hdr.addStretch(1)
        outer.addLayout(hdr)

        intro = QtWidgets.QLabel("Rules define triggers and actions. A rule listens for a signal or variable condition and then changes layers, variables, or behaviors. Rules connect Signals and Variables to Layers and Behaviors. Use this area to automate changes in your show. The current UI exposes Rules directly as editable canonical JSON.")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        self.grp_rule_gate = QtWidgets.QGroupBox("Historical Rule Gate")
        rg = QtWidgets.QVBoxLayout(self.grp_rule_gate)
        self.lbl_rule_gate = QtWidgets.QLabel("")
        self.lbl_rule_gate.setWordWrap(True)
        rg.addWidget(self.lbl_rule_gate)
        outer.addWidget(self.grp_rule_gate)

        self.grp_addresses = QtWidgets.QGroupBox("Canonical Address Browser")
        abox = QtWidgets.QVBoxLayout(self.grp_addresses)

        self.lbl_addresses = QtWidgets.QLabel(
            "Full Power: browse canonical addresses that Rules can target. "
            "This exposes the real project schema used by the engine."
        )
        self.lbl_addresses.setWordWrap(True)
        abox.addWidget(self.lbl_addresses)

        self.filter_row = QtWidgets.QHBoxLayout()
        self.txt_address_filter = QtWidgets.QLineEdit()
        self.txt_address_filter.setPlaceholderText("Filter addresses (layers, params, vars, postfx...)")
        self.filter_row.addWidget(self.txt_address_filter, 1)
        abox.addLayout(self.filter_row)

        top = QtWidgets.QHBoxLayout()
        self.btn_refresh_addresses = QtWidgets.QPushButton("Refresh Addresses")
        top.addWidget(self.btn_refresh_addresses)
        self.btn_copy_address = QtWidgets.QPushButton("Copy Selected Address")
        top.addWidget(self.btn_copy_address)
        top.addStretch(1)
        abox.addLayout(top)

        self.lbl_address_summary = QtWidgets.QLabel("")
        self.lbl_address_summary.setWordWrap(True)
        abox.addWidget(self.lbl_address_summary)

        self.list_addresses = QtWidgets.QListWidget()
        abox.addWidget(self.list_addresses, 1)

        self.txt_selected_address = QtWidgets.QLineEdit()
        self.txt_selected_address.setReadOnly(True)
        abox.addWidget(self.txt_selected_address)

        self.lbl_address_hint = QtWidgets.QLabel(
            "Select an address to inspect its canonical path for use in rules, diagnostics, or advanced editing."
        )
        self.lbl_address_hint.setWordWrap(True)
        abox.addWidget(self.lbl_address_hint)

        outer.addWidget(self.grp_addresses)

        self.grp_rule_target = QtWidgets.QGroupBox("Rule Target Picker")
        tbox = QtWidgets.QVBoxLayout(self.grp_rule_target)

        self.lbl_rule_target = QtWidgets.QLabel(
            "Pick a canonical address from the browser and stage it here for rule targeting."
        )
        self.lbl_rule_target.setWordWrap(True)
        tbox.addWidget(self.lbl_rule_target)

        row = QtWidgets.QHBoxLayout()
        self.txt_rule_target = QtWidgets.QLineEdit()
        self.txt_rule_target.setReadOnly(True)
        row.addWidget(self.txt_rule_target, 1)

        self.btn_use_selected_address = QtWidgets.QPushButton("Use Selected Address")
        row.addWidget(self.btn_use_selected_address)

        self.btn_clear_rule_target = QtWidgets.QPushButton("Clear")
        row.addWidget(self.btn_clear_rule_target)

        tbox.addLayout(row)

        self.lbl_rule_target_hint = QtWidgets.QLabel(
            "This does not change rule runtime logic. It exposes canonical addresses so target selection is less hidden."
        )
        self.lbl_rule_target_hint.setWordWrap(True)
        tbox.addWidget(self.lbl_rule_target_hint)

        outer.addWidget(self.grp_rule_target)

        self.panel = RulesPanel(self.app_core)
        outer.addWidget(self.panel, 1)
        self.grp_vars = QtWidgets.QGroupBox("Variables (Project State)")
        vbox = QtWidgets.QVBoxLayout(self.grp_vars)

        self.vars_intro = QtWidgets.QLabel(
            "Project Variables: persistent state values used by rules, signals, and behaviors."
        )
        self.vars_intro.setWordWrap(True)
        vbox.addWidget(self.vars_intro)

        rowv = QtWidgets.QHBoxLayout()
        self.cmb_var_key = QtWidgets.QComboBox()
        self.cmb_var_key.setEditable(True)
        self.cmb_var_key.addItems(["tempo", "energy", "state", "threshold", "gate"])
        rowv.addWidget(self.cmb_var_key, 1)
        self.spn_var_value = QtWidgets.QDoubleSpinBox()
        self.spn_var_value.setRange(-999999.0, 999999.0)
        self.spn_var_value.setDecimals(3)
        rowv.addWidget(self.spn_var_value)
        self.btn_set_var = QtWidgets.QPushButton("Set")
        rowv.addWidget(self.btn_set_var)
        self.btn_del_var = QtWidgets.QPushButton("Delete Selected")
        rowv.addWidget(self.btn_del_var)
        vbox.addLayout(rowv)

        self.list_vars = QtWidgets.QListWidget()
        vbox.addWidget(self.list_vars)
        outer.addWidget(self.grp_vars)

        self.btn_refresh_addresses.clicked.connect(self._populate_address_browser)
        self.btn_copy_address.clicked.connect(self._copy_selected_address)
        self.list_addresses.currentTextChanged.connect(self._on_address_selected)
        self.txt_address_filter.textChanged.connect(self._filter_addresses)
        self.btn_use_selected_address.clicked.connect(self._use_selected_address)
        self.btn_clear_rule_target.clicked.connect(self._clear_rule_target)

        QtCore.QTimer.singleShot(0, self._populate_address_browser)
        self.btn_set_var.clicked.connect(self._set_variable)
        self.btn_del_var.clicked.connect(self._delete_variable)
        QtCore.QTimer.singleShot(0, self._reload_variables)
        QtCore.QTimer.singleShot(0, self._apply_rules_gate)
