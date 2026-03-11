from __future__ import annotations

from typing import Any

from qt.qt_compat import QtCore, QtWidgets

Qt = QtCore.Qt
QVBoxLayout = QtWidgets.QVBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QFrame = QtWidgets.QFrame
QTextEdit = QtWidgets.QTextEdit
QGroupBox = QtWidgets.QGroupBox
QHBoxLayout = QtWidgets.QHBoxLayout
QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox
QSlider = QtWidgets.QSlider
QSpinBox = QtWidgets.QSpinBox

from qt.era_panel_preview import _WorkbenchPreview

_QFRAME_HLINE = getattr(getattr(QFrame, 'Shape', None), 'HLine', getattr(QFrame, 'HLine', None))
_QFRAME_SUNKEN = getattr(getattr(QFrame, 'Shadow', None), 'Sunken', getattr(QFrame, 'Sunken', None))
_QT_ALIGN_LEFT = getattr(Qt, 'AlignLeft', getattr(getattr(Qt, 'AlignmentFlag', None), 'AlignLeft', None)) or 0
_QT_HORIZONTAL = getattr(Qt, "Horizontal", getattr(getattr(Qt, "Orientation", None), "Horizontal", None)) or 0

def build_era_panel_ui(self: Any) -> None:
    layout = QVBoxLayout(self)

    self.h_title = QLabel("LED Era System")
    self.h_title.setStyleSheet("font-size: 18px; font-weight: 800;")
    layout.addWidget(self.h_title)

    self.h_sub = QLabel(
        "This follows the real history of LED control. "
        "Each era focuses on what a user could actually make LEDs do at the time, without hindsight. "
        "When you reach the effect-picker plateau you can stay there, or continue into the next control model."
    )
    self.h_sub.setWordWrap(True)
    layout.addWidget(self.h_sub)

    self.timeline_bar_group = QGroupBox("Era Timeline")
    tbg = QVBoxLayout(self.timeline_bar_group)

    self.timeline_bar_intro = QLabel(
        "Follow the historical progression of LED control from the first visible LED to the effect-picker plateau and finally Modulo."
    )
    self.timeline_bar_intro.setWordWrap(True)
    tbg.addWidget(self.timeline_bar_intro)

    self.timeline_bar = QLabel("")
    self.timeline_bar.setWordWrap(True)
    self.timeline_bar.setStyleSheet("font-weight: 700;")
    tbg.addWidget(self.timeline_bar)

    layout.addWidget(self.timeline_bar_group)
    self.nav_group = QGroupBox("Era Navigation")
    ng = QHBoxLayout(self.nav_group)

    self.btn_prev_era = QPushButton("← Previous Era")
    ng.addWidget(self.btn_prev_era)

    self.btn_next_era = QPushButton("Next Era →")
    ng.addWidget(self.btn_next_era)

    ng.addStretch(1)
    layout.addWidget(self.nav_group)
    self.lbl_nav_limit = QLabel("")
    self.lbl_nav_limit.setWordWrap(True)
    layout.addWidget(self.lbl_nav_limit)

    self.progress_group = QGroupBox("Era Progress")
    pg = QVBoxLayout(self.progress_group)

    self.progress_summary = QLabel("")
    self.progress_summary.setWordWrap(True)
    pg.addWidget(self.progress_summary)

    self.progress_counts = QLabel("")
    self.progress_counts.setWordWrap(True)
    pg.addWidget(self.progress_counts)

    layout.addWidget(self.progress_group)
    self.context_group = QGroupBox("Era Context")
    cg = QVBoxLayout(self.context_group)

    self.context_text = QLabel("")
    self.context_text.setWordWrap(True)
    cg.addWidget(self.context_text)

    layout.addWidget(self.context_group)
    self.challenge_group = QGroupBox("Era Challenge")
    ch = QVBoxLayout(self.challenge_group)

    self.challenge_summary = QLabel("")
    self.challenge_summary.setWordWrap(True)
    ch.addWidget(self.challenge_summary)

    self.challenge_steps = QLabel("")
    self.challenge_steps.setWordWrap(True)
    ch.addWidget(self.challenge_steps)

    self.challenge_result = QLabel("")
    self.challenge_result.setWordWrap(True)
    ch.addWidget(self.challenge_result)

    layout.addWidget(self.challenge_group)
    self.next_unlock_group = QGroupBox("Next Unlock")
    nu = QVBoxLayout(self.next_unlock_group)

    self.next_unlock_text = QLabel("")
    self.next_unlock_text.setWordWrap(True)
    nu.addWidget(self.next_unlock_text)

    layout.addWidget(self.next_unlock_group)

    self.plateau_group = QGroupBox("Plateau Choice")
    pc = QVBoxLayout(self.plateau_group)

    self.plateau_summary = QLabel("")
    self.plateau_summary.setWordWrap(True)
    pc.addWidget(self.plateau_summary)

    self.plateau_actions = QLabel("")
    self.plateau_actions.setWordWrap(True)
    pc.addWidget(self.plateau_actions)

    plateau_btn_row = QHBoxLayout()
    self.btn_plateau_effect_picker = QPushButton("Use Effect Picker Path")
    plateau_btn_row.addWidget(self.btn_plateau_effect_picker)
    self.btn_plateau_modulo = QPushButton("Unlock Modulo")
    plateau_btn_row.addWidget(self.btn_plateau_modulo)
    plateau_btn_row.addStretch(1)
    pc.addLayout(plateau_btn_row)

    layout.addWidget(self.plateau_group)
    self.capability_group = QGroupBox("Era Capability Limits")
    cl = QVBoxLayout(self.capability_group)

    self.capability_text = QLabel("")
    self.capability_text.setWordWrap(True)
    cl.addWidget(self.capability_text)

    layout.addWidget(self.capability_group)

    # Browse row (read any era without unlocking)
    browse_row = QHBoxLayout()
    browse_row.addWidget(QLabel("Browse:"))
    self.browse_combo = QComboBox()
    self.browse_combo.currentIndexChanged.connect(self._on_browse_changed)
    browse_row.addWidget(self.browse_combo, stretch=1)
    self.btn_jump_active = QPushButton("Jump to current")
    self.btn_jump_active.clicked.connect(self._jump_to_active)
    browse_row.addWidget(self.btn_jump_active)
    layout.addLayout(browse_row)

    sep = QFrame()
    sep.setFrameShape(_QFRAME_HLINE)
    sep.setFrameShadow(_QFRAME_SUNKEN)
    layout.addWidget(sep)

    self.era_title = QLabel("")
    self.era_title.setStyleSheet("font-size: 16px; font-weight: 700;")
    layout.addWidget(self.era_title)

    self.era_meta = QLabel("")
    self.era_meta.setWordWrap(True)
    layout.addWidget(self.era_meta)

    self.era_possible = QLabel("")
    self.era_possible.setWordWrap(True)
    layout.addWidget(self.era_possible)

    # ---- Workbench ----
    self.wb_group = QGroupBox("Era workbench")
    wb = QVBoxLayout(self.wb_group)

    self.wb_preview = _WorkbenchPreview()
    wb.addWidget(self.wb_preview)

    self.wb_hint = QLabel("")
    self.wb_hint.setWordWrap(True)
    wb.addWidget(self.wb_hint)

    # Controls row 1
    row1 = QHBoxLayout()
    self.wb_power = QCheckBox("Power")
    self.wb_power.stateChanged.connect(self._on_wb_changed)
    row1.addWidget(self.wb_power)

    self.wb_mode = QComboBox()
    self.wb_mode.currentIndexChanged.connect(self._on_wb_changed)
    row1.addWidget(self.wb_mode)

    self.wb_color = QComboBox()
    self.wb_color.currentIndexChanged.connect(self._on_wb_changed)
    row1.addWidget(self.wb_color)

    self.wb_pulse_rate = QComboBox()
    self.wb_pulse_rate.currentIndexChanged.connect(self._on_wb_changed)
    row1.addWidget(self.wb_pulse_rate)

    row1.addStretch(1)
    wb.addLayout(row1)

    # Controls row 2 (brightness / sliders)
    row2 = QHBoxLayout()
    self.wb_brightness_label = QLabel("Brightness")
    row2.addWidget(self.wb_brightness_label)
    self.wb_brightness = QSlider(_QT_HORIZONTAL)
    self.wb_brightness.setMinimum(0)
    self.wb_brightness.setMaximum(100)
    self.wb_brightness.setValue(100)
    self.wb_brightness.valueChanged.connect(self._on_wb_changed)
    row2.addWidget(self.wb_brightness, stretch=1)
    wb.addLayout(row2)

    # RGB controls (1993)
    self.rgb_group = QGroupBox("RGB mix")
    rgb = QVBoxLayout(self.rgb_group)
    self.rgb_r = QSlider(_QT_HORIZONTAL); self.rgb_r.setRange(0, 255); self.rgb_r.setValue(255); self.rgb_r.valueChanged.connect(self._on_wb_changed)
    self.rgb_g = QSlider(_QT_HORIZONTAL); self.rgb_g.setRange(0, 255); self.rgb_g.setValue(0); self.rgb_g.valueChanged.connect(self._on_wb_changed)
    self.rgb_b = QSlider(_QT_HORIZONTAL); self.rgb_b.setRange(0, 255); self.rgb_b.setValue(0); self.rgb_b.valueChanged.connect(self._on_wb_changed)
    rgb.addWidget(QLabel("R")); rgb.addWidget(self.rgb_r)
    rgb.addWidget(QLabel("G")); rgb.addWidget(self.rgb_g)
    rgb.addWidget(QLabel("B")); rgb.addWidget(self.rgb_b)
    wb.addWidget(self.rgb_group)

    # White type (1996)
    self.white_group = QGroupBox("White type")
    wg = QHBoxLayout(self.white_group)
    self.wb_white_type = QComboBox()
    self.wb_white_type.currentIndexChanged.connect(self._on_wb_changed)
    wg.addWidget(self.wb_white_type, stretch=1)
    wb.addWidget(self.white_group)

    # Matrix controls (2000s)
    self.matrix_group = QGroupBox("Matrix")
    mg = QHBoxLayout(self.matrix_group)
    self.btn_move = QPushButton("Move dot")
    self.btn_move.clicked.connect(self._on_matrix_move)
    mg.addWidget(self.btn_move)
    self.btn_scroll = QPushButton("Scroll")
    self.btn_scroll.clicked.connect(self._on_matrix_scroll)
    mg.addWidget(self.btn_scroll)
    wb.addWidget(self.matrix_group)

    # Addressable strip controls (2012)
    self.strip_group = QGroupBox("Strip")
    sg = QHBoxLayout(self.strip_group)
    sg.addWidget(QLabel("Index"))
    self.wb_index = QSpinBox()
    self.wb_index.setRange(0, 59)
    self.wb_index.valueChanged.connect(self._on_wb_changed)
    sg.addWidget(self.wb_index)
    wb.addWidget(self.strip_group)

    # Verify row
    vr = QHBoxLayout()
    self.wb_verify = QPushButton("Verify this era")
    self.wb_verify.clicked.connect(self._on_verify)
    vr.addWidget(self.wb_verify)
    self.wb_status = QLabel("")
    self.wb_status.setWordWrap(True)
    vr.addWidget(self.wb_status, stretch=1)
    wb.addLayout(vr)

    layout.addWidget(self.wb_group)

    self.btn_workspace = QPushButton("Use Effect Picker App")
    self.btn_workspace.clicked.connect(self._open_workspace)
    self.btn_workspace.setVisible(False)
    layout.addWidget(self.btn_workspace, alignment=_QT_ALIGN_LEFT)

    self.btn_unlock_modulo = QPushButton("Unlock Full Modulo")
    self.btn_unlock_modulo.clicked.connect(self._on_unlock_modulo)
    self.btn_prev_era.clicked.connect(self._nav_prev_era)
    self.btn_next_era.clicked.connect(self._nav_next_era)

    self.btn_plateau_effect_picker.clicked.connect(self._open_workspace)
    self.btn_plateau_modulo.clicked.connect(self._on_unlock_modulo)
    self.btn_unlock_modulo.setVisible(False)
    layout.addWidget(self.btn_unlock_modulo, alignment=_QT_ALIGN_LEFT)

    self.btn_continue = QPushButton("Continue")
    self.btn_continue.clicked.connect(self._on_continue)
    layout.addWidget(self.btn_continue, alignment=_QT_ALIGN_LEFT)

    self.cap_text = QTextEdit()
    self.cap_text.setReadOnly(True)
    self.cap_text.setVisible(False)
    self.cap_text.setMinimumHeight(220)
    self.cap_text.setStyleSheet("font-family: monospace; font-size: 11px;")
    layout.addWidget(self.cap_text)

    layout.addStretch(1)

