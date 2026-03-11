from __future__ import annotations

from typing import Any

from qt.qt_compat import QtCore, QtWidgets

def build_layers_panel_ui(self: Any) -> None:
    outer = QtWidgets.QVBoxLayout(self)
    outer.setContentsMargins(8, 8, 8, 8)
    outer.setSpacing(8)

    top = QtWidgets.QHBoxLayout()
    top.addWidget(QtWidgets.QLabel("Layers"))
    top.addStretch(1)

    self.btn_add = QtWidgets.QPushButton("Add")
    self.btn_add.clicked.connect(self._add_layer)
    top.addWidget(self.btn_add)

    self.btn_add_kernel = QtWidgets.QPushButton("Add Kernel")
    self.btn_add_kernel.clicked.connect(self._add_kernel_layer)
    top.addWidget(self.btn_add_kernel)

    self.btn_dup = QtWidgets.QPushButton("Duplicate")
    self.btn_dup.clicked.connect(self._dup_layer)
    top.addWidget(self.btn_dup)

    self.btn_solo = QtWidgets.QPushButton("Solo")
    self.btn_solo.clicked.connect(self._solo_layer)
    top.addWidget(self.btn_solo)

    self.btn_up = QtWidgets.QPushButton("Move Up")
    self.btn_up.clicked.connect(self._move_layer_up)
    top.addWidget(self.btn_up)

    self.btn_down = QtWidgets.QPushButton("Move Down")
    self.btn_down.clicked.connect(self._move_layer_down)
    top.addWidget(self.btn_down)

    self.btn_del = QtWidgets.QPushButton("Delete")
    self.btn_del.clicked.connect(self._del_layer)
    top.addWidget(self.btn_del)

    outer.addLayout(top)

    intro = QtWidgets.QLabel("Layers are the building blocks of the project. Add layers here, then assign behaviors, targeting, and rules in the later workflow stages.")
    intro.setWordWrap(True)
    outer.addWidget(intro)

    stage = QtWidgets.QLabel("This is the third stage of the workflow. Build the layer stack after defining the surface and targeting structure.")
    stage.setWordWrap(True)
    outer.addWidget(stage)

    body = QtWidgets.QHBoxLayout()
    outer.addLayout(body, 1)

    self.list = QtWidgets.QListWidget()
    self.list.currentRowChanged.connect(self._on_row_changed)
    body.addWidget(self.list, 1)

    editor = QtWidgets.QVBoxLayout()
    body.addLayout(editor, 2)

    legend = QtWidgets.QLabel("Layer List Legend: ● enabled, ○ disabled. Each row shows layer name, behavior, and targeting. Layer order affects composition. Target Quick Action: use Clear Target to remove layer targeting instantly.")
    legend.setWordWrap(True)
    editor.insertWidget(0, legend)
    target_help = QtWidgets.QLabel("Target Edit Flow: choose Target Kind, choose Target Ref, or use Clear Target to return the layer to full-surface rendering.")
    target_help.setWordWrap(True)
    editor.insertWidget(1, target_help)

    form = QtWidgets.QFormLayout()
    form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
    editor.addLayout(form)

    self.chk_enabled = QtWidgets.QCheckBox("Enabled")
    self.chk_enabled.stateChanged.connect(self._apply)
    form.addRow("Enabled", self.chk_enabled)

    self.txt_name = QtWidgets.QLineEdit()
    self.txt_name.setPlaceholderText("Layer name")
    self.txt_name.editingFinished.connect(self._apply)
    form.addRow("Name", self.txt_name)

    self.cmb_effect = QtWidgets.QComboBox()
    self.cmb_effect.currentTextChanged.connect(self._apply)
    form.addRow("Effect", self.cmb_effect)

    self.spn_opacity = QtWidgets.QDoubleSpinBox()
    self.spn_opacity.setRange(0.0, 1.0)
    self.spn_opacity.setSingleStep(0.05)
    self.spn_opacity.valueChanged.connect(self._apply)
    form.addRow("Opacity", self.spn_opacity)

    self.cmb_blend = QtWidgets.QComboBox()
    self.cmb_blend.addItems(["over", "add", "screen", "multiply", "max", "min"])
    self.cmb_blend.currentTextChanged.connect(self._apply)
    form.addRow("Blend", self.cmb_blend)

    self.cmb_target_kind = QtWidgets.QComboBox()
    self.cmb_target_kind.addItems(["none", "mask", "zone", "group"])
    self.cmb_target_kind.currentTextChanged.connect(self._on_target_kind_changed)
    form.addRow("Target Kind", self.cmb_target_kind)

    self.cmb_target_ref = QtWidgets.QComboBox()
    self.cmb_target_ref.setEditable(True)
    self.cmb_target_ref.currentTextChanged.connect(self._apply)
    form.addRow("Target Ref", self.cmb_target_ref)

    self.btn_clear_target = QtWidgets.QPushButton("Clear Target")
    self.btn_clear_target.clicked.connect(self._clear_targeting)
    form.addRow("Target Actions", self.btn_clear_target)

    self.grp_kernel = QtWidgets.QGroupBox("Per-Pixel Kernel (Advanced / Escape Hatch)")
    kbox = QtWidgets.QVBoxLayout(self.grp_kernel)
    kernel_note = QtWidgets.QLabel("Escape Hatch: write your own per-pixel logic here when built-in behaviors are not enough.")
    kernel_note.setWordWrap(True)
    kbox.addWidget(kernel_note)
    kform = QtWidgets.QFormLayout()
    kbox.addLayout(kform)

    self.spn_budget = QtWidgets.QDoubleSpinBox()
    self.spn_budget.setRange(0.5, 200.0)
    self.spn_budget.setSingleStep(0.5)
    self.spn_budget.setSuffix(" ms")
    kform.addRow("Budget", self.spn_budget)

    self.spn_strikes = QtWidgets.QSpinBox()
    self.spn_strikes.setRange(0, 100)
    self.spn_strikes.setSingleStep(1)
    kform.addRow("Strike limit", self.spn_strikes)

    self.txt_py = QtWidgets.QPlainTextEdit()
    self.txt_py.setPlaceholderText("Python per-pixel kernel source (init/update/pixel)…")
    self.txt_py.setTabStopDistance(4 * 8)
    kbox.addWidget(QtWidgets.QLabel("Python"))
    kbox.addWidget(self.txt_py, 2)

    self.txt_cpp = QtWidgets.QPlainTextEdit()
    self.txt_cpp.setPlaceholderText("C++ export body for the kernel (assign r,g,b floats 0..1)…")
    self.txt_cpp.setTabStopDistance(4 * 8)
    kbox.addWidget(QtWidgets.QLabel("C++ Export"))
    kbox.addWidget(self.txt_cpp, 1)

    kbtns = QtWidgets.QHBoxLayout()
    self.btn_kernel_apply = QtWidgets.QPushButton("Apply")
    self.btn_kernel_apply.clicked.connect(self._apply_kernel)
    kbtns.addWidget(self.btn_kernel_apply)

    self.btn_kernel_reset_vars = QtWidgets.QPushButton("Reset Vars")
    self.btn_kernel_reset_vars.clicked.connect(self._reset_kernel_vars)
    kbtns.addWidget(self.btn_kernel_reset_vars)

    self.btn_kernel_reset = QtWidgets.QPushButton("Reset Kernel")
    self.btn_kernel_reset.clicked.connect(self._reset_kernel_state)
    kbtns.addWidget(self.btn_kernel_reset)

    kbtns.addSpacing(12)

    self.btn_kernel_tpl_py = QtWidgets.QPushButton("Insert Python Template")
    self.btn_kernel_tpl_py.clicked.connect(self._insert_kernel_py_template)
    kbtns.addWidget(self.btn_kernel_tpl_py)

    self.btn_kernel_tpl_cpp = QtWidgets.QPushButton("Insert C++ Template")
    self.btn_kernel_tpl_cpp.clicked.connect(self._insert_kernel_cpp_template)
    kbtns.addWidget(self.btn_kernel_tpl_cpp)
    kbtns.addStretch(1)
    kbox.addLayout(kbtns)

    editor.addWidget(self.grp_kernel)
    self.grp_kernel.setVisible(False)

    self.grp_params = QtWidgets.QGroupBox("Behavior Parameters")
    pbox = QtWidgets.QVBoxLayout(self.grp_params)
    self.lbl_params = QtWidgets.QLabel("Full Power: parameters and available bindings are exposed from the selected behavior metadata.")
    self.lbl_params.setWordWrap(True)
    pbox.addWidget(self.lbl_params)
    self.params_form = QtWidgets.QFormLayout()
    pbox.addLayout(self.params_form)
    self._param_widgets = {}
    self._param_bind_widgets = {}
    self._param_bind_widgets = {}
    editor.addWidget(self.grp_params)
    self.grp_params.setVisible(False)


    # Canonical Address Inspector
    self.grp_address_inspector = QtWidgets.QGroupBox("Canonical Address")
    abox = QtWidgets.QVBoxLayout(self.grp_address_inspector)
    self.lbl_address_info = QtWidgets.QLabel("Read-only canonical address for the selected control. This includes base layer fields, behavior parameters, and parameter bindings.")
    self.lbl_address_info.setWordWrap(True)
    abox.addWidget(self.lbl_address_info)
    self.txt_address = QtWidgets.QLineEdit()
    self.txt_address.setReadOnly(True)
    abox.addWidget(self.txt_address)
    editor.addWidget(self.grp_address_inspector)

    self.grp_layer_addresses = QtWidgets.QGroupBox("Selected Layer Address Browser")
    lbox = QtWidgets.QVBoxLayout(self.grp_layer_addresses)

    self.lbl_layer_addresses = QtWidgets.QLabel(
        "Full Power: browse canonical addresses for the currently selected layer."
    )
    self.lbl_layer_addresses.setWordWrap(True)
    lbox.addWidget(self.lbl_layer_addresses)

    addr_top = QtWidgets.QHBoxLayout()
    self.btn_refresh_layer_addresses = QtWidgets.QPushButton("Refresh Layer Addresses")
    addr_top.addWidget(self.btn_refresh_layer_addresses)
    self.btn_copy_layer_address = QtWidgets.QPushButton("Copy Selected Address")
    addr_top.addWidget(self.btn_copy_layer_address)
    addr_top.addStretch(1)
    lbox.addLayout(addr_top)

    self.list_layer_addresses = QtWidgets.QListWidget()
    lbox.addWidget(self.list_layer_addresses, 1)

    self.txt_selected_layer_address = QtWidgets.QLineEdit()
    self.txt_selected_layer_address.setReadOnly(True)
    lbox.addWidget(self.txt_selected_layer_address)

    editor.addWidget(self.grp_layer_addresses)
    self.grp_param_binding = QtWidgets.QGroupBox("Parameter Binding Inspector")
    pbox = QtWidgets.QVBoxLayout(self.grp_param_binding)

    self.lbl_param_binding = QtWidgets.QLabel(
        "Inspect canonical parameter bindings (signals, vars, time) for the selected layer."
    )
    self.lbl_param_binding.setWordWrap(True)
    pbox.addWidget(self.lbl_param_binding)

    row = QtWidgets.QHBoxLayout()
    self.btn_refresh_bindings = QtWidgets.QPushButton("Refresh Bindings")
    row.addWidget(self.btn_refresh_bindings)
    self.btn_copy_binding = QtWidgets.QPushButton("Copy Selected Binding Address")
    row.addWidget(self.btn_copy_binding)
    row.addStretch(1)
    pbox.addLayout(row)

    self.list_param_bindings = QtWidgets.QListWidget()
    pbox.addWidget(self.list_param_bindings, 1)

    self.txt_selected_binding = QtWidgets.QLineEdit()
    self.txt_selected_binding.setReadOnly(True)
    pbox.addWidget(self.txt_selected_binding)

    editor.addWidget(self.grp_param_binding)

    self.grp_kernel_addresses = QtWidgets.QGroupBox("Kernel Address Browser")
    kaddr_box = QtWidgets.QVBoxLayout(self.grp_kernel_addresses)

    self.lbl_kernel_addresses = QtWidgets.QLabel(
        "Escape Hatch: browse canonical kernel-related addresses for the selected layer."
    )
    self.lbl_kernel_addresses.setWordWrap(True)
    kaddr_box.addWidget(self.lbl_kernel_addresses)

    kaddr_row = QtWidgets.QHBoxLayout()
    self.btn_refresh_kernel_addresses = QtWidgets.QPushButton("Refresh Kernel Addresses")
    kaddr_row.addWidget(self.btn_refresh_kernel_addresses)
    self.btn_copy_kernel_address = QtWidgets.QPushButton("Copy Selected Kernel Address")
    kaddr_row.addWidget(self.btn_copy_kernel_address)
    kaddr_row.addStretch(1)
    kaddr_box.addLayout(kaddr_row)

    self.list_kernel_addresses = QtWidgets.QListWidget()
    kaddr_box.addWidget(self.list_kernel_addresses, 1)

    self.txt_selected_kernel_address = QtWidgets.QLineEdit()
    self.txt_selected_kernel_address.setReadOnly(True)
    kaddr_box.addWidget(self.txt_selected_kernel_address)

    editor.addWidget(self.grp_kernel_addresses)

    self.grp_kernel_author = QtWidgets.QGroupBox("Kernel Authoring Surface")
    ka_box = QtWidgets.QVBoxLayout(self.grp_kernel_author)

    self.lbl_kernel_author = QtWidgets.QLabel(
        "Escape Hatch: inspect and target the core kernel authoring fields directly."
    )
    self.lbl_kernel_author.setWordWrap(True)
    ka_box.addWidget(self.lbl_kernel_author)

    self.lbl_kernel_author_summary = QtWidgets.QLabel("")
    self.lbl_kernel_author_summary.setWordWrap(True)
    ka_box.addWidget(self.lbl_kernel_author_summary)

    ka_row = QtWidgets.QHBoxLayout()
    self.btn_kernel_addr_budget = QtWidgets.QPushButton("Budget Address")
    ka_row.addWidget(self.btn_kernel_addr_budget)
    self.btn_kernel_addr_strikes = QtWidgets.QPushButton("Strike Limit Address")
    ka_row.addWidget(self.btn_kernel_addr_strikes)
    self.btn_kernel_addr_py = QtWidgets.QPushButton("Python Address")
    ka_row.addWidget(self.btn_kernel_addr_py)
    self.btn_kernel_addr_cpp = QtWidgets.QPushButton("C++ Address")
    ka_row.addWidget(self.btn_kernel_addr_cpp)
    ka_row.addStretch(1)
    ka_box.addLayout(ka_row)

    editor.addWidget(self.grp_kernel_author)

    editor.addStretch(1)

    self.btn_refresh_layer_addresses.clicked.connect(self._reload_layer_address_browser)
    self.btn_copy_layer_address.clicked.connect(self._copy_selected_layer_address)
    self.btn_refresh_bindings.clicked.connect(self._reload_param_bindings)
    self.btn_copy_binding.clicked.connect(self._copy_selected_binding)
    self.btn_refresh_kernel_addresses.clicked.connect(self._reload_kernel_addresses)
    self.btn_copy_kernel_address.clicked.connect(self._copy_selected_kernel_address)
    self.list_kernel_addresses.currentTextChanged.connect(self._on_kernel_address_selected)
    self.btn_kernel_addr_budget.clicked.connect(lambda: self._set_kernel_field_address("budget_ms"))
    self.btn_kernel_addr_strikes.clicked.connect(lambda: self._set_kernel_field_address("strike_limit"))
    self.btn_kernel_addr_py.clicked.connect(lambda: self._set_kernel_field_address("py"))
    self.btn_kernel_addr_cpp.clicked.connect(lambda: self._set_kernel_field_address("cpp"))
    self.list_param_bindings.currentTextChanged.connect(self._on_binding_selected)

    self.list_layer_addresses.currentTextChanged.connect(self._on_layer_address_selected)