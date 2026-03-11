from __future__ import annotations

from qt.layout_panel_common import QtWidgets


class LayoutPanelUiMixin:
    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(QtWidgets.QLabel('Layout:'))
        self.layout_combo = QtWidgets.QComboBox()
        self.layout_combo.addItems(['Strip', 'Matrix'])
        self.layout_combo.setFixedWidth(160)
        top.addWidget(self.layout_combo)
        top.addStretch(1)
        self.validation_badge = QtWidgets.QLabel('Validation: OK')
        self.validation_badge.setStyleSheet('font-weight: 600;')
        top.addWidget(self.validation_badge)
        outer.addLayout(top)

        for text in (
            'Surface / Hardware. Define the LED surface before adding layers or behaviors.',
            'Define the physical LED surface, size, mapping, and preview context.',
            'Quick Start: For a brand new project, start here. Strip 144 is the default fast path, then move to Targets and Layers.',
            'Next: go to Targets to define zones, masks, and groups for this surface.',
        ):
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)
            outer.addWidget(label)

        self._build_mode_group(outer)
        self._build_surface_gate_group(outer)
        self._build_helpers_group(outer)
        self._build_strip_group(outer)
        self._build_matrix_group(outer)
        outer.addStretch(1)

    def _build_mode_group(self, outer):
        self.mode_group = QtWidgets.QGroupBox('Studio Modes')
        box = QtWidgets.QVBoxLayout(self.mode_group)
        intro = QtWidgets.QLabel('Choose how you want to work: continue the LED Era journey, use the effect-picker path, or continue into full Modulo.')
        intro.setWordWrap(True)
        box.addWidget(intro)

        row = QtWidgets.QHBoxLayout()
        self.btn_mode_era = QtWidgets.QPushButton('Continue Era Journey')
        self.btn_mode_effect = QtWidgets.QPushButton('Effect Picker Path')
        self.btn_mode_modulo = QtWidgets.QPushButton('Full Modulo Path')
        row.addWidget(self.btn_mode_era); row.addWidget(self.btn_mode_effect); row.addWidget(self.btn_mode_modulo); row.addStretch(1)
        box.addLayout(row)

        self.lbl_mode_gate = QtWidgets.QLabel(''); self.lbl_mode_gate.setWordWrap(True); box.addWidget(self.lbl_mode_gate)
        self.lbl_mode_status = QtWidgets.QLabel('Mode Status: Studio tabs now follow the creation workflow. Era remains separate from the main editor.')
        self.lbl_mode_status.setWordWrap(True); box.addWidget(self.lbl_mode_status)

        reset_row = QtWidgets.QHBoxLayout()
        self.btn_mode_reset = QtWidgets.QPushButton('Show Full Studio')
        reset_row.addWidget(self.btn_mode_reset); reset_row.addStretch(1)
        box.addLayout(reset_row)
        outer.addWidget(self.mode_group)

    def _build_surface_gate_group(self, outer):
        self.grp_surface_gate = QtWidgets.QGroupBox('Historical Surface Gate')
        box = QtWidgets.QVBoxLayout(self.grp_surface_gate)
        self.lbl_surface_gate = QtWidgets.QLabel('')
        self.lbl_surface_gate.setWordWrap(True)
        box.addWidget(self.lbl_surface_gate)
        outer.addWidget(self.grp_surface_gate)

    def _build_helpers_group(self, outer):
        helpers = QtWidgets.QGroupBox('Surface Helpers')
        row = QtWidgets.QHBoxLayout(helpers)
        self.btn_strip_144 = QtWidgets.QPushButton('Strip 144')
        self.btn_strip_288 = QtWidgets.QPushButton('Strip 288')
        self.btn_matrix_32x32 = QtWidgets.QPushButton('Matrix 32x32')
        self.btn_matrix_64x32 = QtWidgets.QPushButton('Matrix 64x32')
        self.btn_matrix_64x64 = QtWidgets.QPushButton('Matrix 64x64')
        self.btn_matrix_128x64 = QtWidgets.QPushButton('Matrix 128x64')
        for widget in (self.btn_strip_144, self.btn_strip_288, self.btn_matrix_32x32, self.btn_matrix_64x32, self.btn_matrix_64x64, self.btn_matrix_128x64):
            row.addWidget(widget)
        row.addStretch(1)
        outer.addWidget(helpers)

    def _build_strip_group(self, outer):
        self.strip_box = QtWidgets.QGroupBox('Strip')
        box = QtWidgets.QVBoxLayout(self.strip_box)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel('Count'))
        self.strip_count = QtWidgets.QSpinBox(); self.strip_count.setObjectName('layout_strip_count'); self.strip_count.setRange(1, 100000); self.strip_count.setValue(144)
        row.addWidget(self.strip_count)
        self.strip_reverse = QtWidgets.QCheckBox('Reverse'); self.strip_reverse.setObjectName('layout_strip_reverse')
        row.addWidget(self.strip_reverse); row.addStretch(1)
        box.addLayout(row)
        outer.addWidget(self.strip_box)

    def _build_matrix_group(self, outer):
        self.matrix_box = QtWidgets.QGroupBox('Matrix')
        box = QtWidgets.QVBoxLayout(self.matrix_box)

        dims = QtWidgets.QHBoxLayout()
        dims.addWidget(QtWidgets.QLabel('Width'))
        self.w_spin = QtWidgets.QSpinBox(); self.w_spin.setObjectName('layout_matrix_width'); self.w_spin.setRange(1, 1024); self.w_spin.setValue(64)
        dims.addWidget(self.w_spin)
        dims.addWidget(QtWidgets.QLabel('Height'))
        self.h_spin = QtWidgets.QSpinBox(); self.h_spin.setObjectName('layout_matrix_height'); self.h_spin.setRange(1, 1024); self.h_spin.setValue(32)
        dims.addWidget(self.h_spin); dims.addStretch(1)
        box.addLayout(dims)

        flags = QtWidgets.QHBoxLayout()
        self.cb_serp = QtWidgets.QCheckBox('Serpentine')
        self.cb_flipx = QtWidgets.QCheckBox('Flip X')
        self.cb_flipy = QtWidgets.QCheckBox('Flip Y')
        self.cb_serp.setObjectName('layout_serpentine'); self.cb_flipx.setObjectName('layout_flip_x'); self.cb_flipy.setObjectName('layout_flip_y')
        flags.addWidget(self.cb_serp); flags.addWidget(self.cb_flipx); flags.addWidget(self.cb_flipy); flags.addStretch(1)
        box.addLayout(flags)

        preview_row = QtWidgets.QHBoxLayout()
        preview_row.addWidget(QtWidgets.QLabel('Zoom'))
        self.zoom = QtWidgets.QSpinBox(); self.zoom.setObjectName('preview_zoom'); self.zoom.setRange(1, 64); self.zoom.setValue(8)
        preview_row.addWidget(self.zoom)
        self.btn_fit = QtWidgets.QPushButton('Fit'); self.btn_fit.setObjectName('preview_fit')
        preview_row.addWidget(self.btn_fit); preview_row.addStretch(1)
        box.addLayout(preview_row)

        outer.addWidget(self.matrix_box)

    def _wire_signals(self):
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        self.w_spin.valueChanged.connect(self._on_matrix_changed)
        self.h_spin.valueChanged.connect(self._on_matrix_changed)
        self.cb_serp.toggled.connect(self._on_matrix_changed)
        self.cb_flipx.toggled.connect(self._on_matrix_changed)
        self.cb_flipy.toggled.connect(self._on_matrix_changed)
        self.strip_count.valueChanged.connect(self._on_strip_changed)
        self.strip_reverse.toggled.connect(self._on_strip_changed)
        self.zoom.valueChanged.connect(self._on_preview_zoom_changed)
        self.btn_fit.clicked.connect(self._on_preview_fit)
        self.btn_strip_144.clicked.connect(lambda: self._apply_surface_preset(kind='strip', count=144))
        self.btn_strip_288.clicked.connect(lambda: self._apply_surface_preset(kind='strip', count=288))
        self.btn_matrix_32x32.clicked.connect(lambda: self._apply_surface_preset(kind='cells', width=32, height=32))
        self.btn_matrix_64x32.clicked.connect(lambda: self._apply_surface_preset(kind='cells', width=64, height=32))
        self.btn_matrix_64x64.clicked.connect(lambda: self._apply_surface_preset(kind='cells', width=64, height=64))
        self.btn_matrix_128x64.clicked.connect(lambda: self._apply_surface_preset(kind='cells', width=128, height=64))
        self.btn_mode_era.clicked.connect(self._go_era_journey)
        self.btn_mode_effect.clicked.connect(self._go_effect_picker_path)
        self.btn_mode_modulo.clicked.connect(self._go_full_modulo_path)
        self.btn_mode_reset.clicked.connect(self._reset_studio_mode)
