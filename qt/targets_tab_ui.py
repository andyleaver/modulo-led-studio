from __future__ import annotations

from qt.qt_compat import QtCore, QtWidgets  # type: ignore
from qt.target_mask_panel import TargetMaskPanel


class TargetsTabUiMixin:
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        step = QtWidgets.QLabel("Targets / Zones"); step.setStyleSheet("font-weight:600;")
        root.addWidget(step)
        root.setContentsMargins(8, 8, 8, 8); root.setSpacing(8)

        texts = [
            "Targeting defines where behaviors apply on the surface. Zones, masks, and groups can all be applied to layers. Use masks, zones, and groups to define spatial targets, then use the mask selector as a global preview filter.",
            "Define zones, masks, and logical target groups on the surface.",
            "Quick Tip: Targets let you control specific LED regions using zones, groups, and masks.",
            "Define spatial areas and masks before building the layer stack.",
            "Targets Workflow: Create zones / masks / groups → assign them to layers → preview results.",
            "Quick Targets Guide: Zone = area, Mask = pixel filter, Group = reusable target set.",
            "Targeting Tips: Zones define areas, Masks filter pixels, Groups combine targets for reuse.",
            "Full Modulo keeps the raw JSON structures reachable, but this panel now includes helper actions so targeting does not feel like hidden internals.",
            "Next: go to Layers to build the composition stack that will use these targets.",
            "Surface defines the LED layout that these targets operate on.",
        ]
        for text in texts:
            lbl = QtWidgets.QLabel(text); lbl.setWordWrap(True); root.addWidget(lbl)

        self.summary = QtWidgets.QLabel("")
        try: self.summary.setStyleSheet("font-weight: 600;")
        except Exception: pass
        root.addWidget(self.summary)

        self.grp_target_gate = QtWidgets.QGroupBox("Historical Target Gate")
        tg = QtWidgets.QVBoxLayout(self.grp_target_gate)
        self.lbl_target_gate = QtWidgets.QLabel(""); self.lbl_target_gate.setWordWrap(True); tg.addWidget(self.lbl_target_gate)
        root.addWidget(self.grp_target_gate)

        self.mask_panel = TargetMaskPanel(self.controller); root.addWidget(self.mask_panel, 0)

        zone_helpers = QtWidgets.QGroupBox("Zone Helpers")
        zhlay = QtWidgets.QHBoxLayout(zone_helpers)
        self.txt_zone_name = QtWidgets.QLineEdit(); self.txt_zone_name.setPlaceholderText("zone name"); zhlay.addWidget(self.txt_zone_name, 1)
        self.txt_zone_rect = QtWidgets.QLineEdit(); self.txt_zone_rect.setPlaceholderText("rect x,y,w,h"); zhlay.addWidget(self.txt_zone_rect, 1)
        self.btn_add_zone_rect = QtWidgets.QPushButton("Add Rect Zone"); zhlay.addWidget(self.btn_add_zone_rect, 0)
        root.addWidget(zone_helpers, 0)

        helpers = QtWidgets.QGroupBox("Targeting Helpers")
        hlay = QtWidgets.QVBoxLayout(helpers); hlay.setContentsMargins(8, 8, 8, 8); hlay.setSpacing(6)
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_add_mask = QtWidgets.QPushButton("Add Mask")
        self.btn_add_zone = QtWidgets.QPushButton("Add Zone")
        self.btn_add_group = QtWidgets.QPushButton("Add Group")
        self.btn_apply_mask_layer = QtWidgets.QPushButton("Apply Mask To Selected Layer")
        self.btn_apply_zone_layer = QtWidgets.QPushButton("Apply Zone To Selected Layer")
        self.btn_apply_group_layer = QtWidgets.QPushButton("Apply Group To Selected Layer")
        for w in (self.btn_add_mask,self.btn_add_zone,self.btn_add_group,self.btn_apply_mask_layer,self.btn_apply_zone_layer,self.btn_apply_group_layer):
            btn_row.addWidget(w)
        btn_row.addStretch(1); hlay.addLayout(btn_row)

        pick_row = QtWidgets.QHBoxLayout()
        self.cmb_apply_mask = QtWidgets.QComboBox(); self.cmb_apply_mask.setMinimumWidth(180); self.cmb_apply_mask.setToolTip("Choose which mask to apply to the selected layer")
        pick_row.addWidget(QtWidgets.QLabel("Mask")); pick_row.addWidget(self.cmb_apply_mask,1)
        self.cmb_apply_zone = QtWidgets.QComboBox(); self.cmb_apply_zone.setMinimumWidth(180); self.cmb_apply_zone.setToolTip("Choose which zone to apply to the selected layer")
        pick_row.addWidget(QtWidgets.QLabel("Zone")); pick_row.addWidget(self.cmb_apply_zone,1)
        self.cmb_apply_group = QtWidgets.QComboBox(); self.cmb_apply_group.setMinimumWidth(180); self.cmb_apply_group.setToolTip("Choose which group to apply to the selected layer")
        pick_row.addWidget(QtWidgets.QLabel("Group")); pick_row.addWidget(self.cmb_apply_group,1)
        hlay.addLayout(pick_row)
        root.addWidget(helpers,0)

        actions = QtWidgets.QHBoxLayout()
        self.btn_reload = QtWidgets.QPushButton("Reload"); self.btn_apply = QtWidgets.QPushButton("Apply"); self.btn_apply.setToolTip("Apply masks / zones / groups JSON into the current project.")
        actions.addWidget(self.btn_reload); actions.addWidget(self.btn_apply); actions.addStretch(1)
        root.addLayout(actions)

        split = QtWidgets.QSplitter(); split.setOrientation(QtCore.Qt.Orientation.Vertical); root.addWidget(split,1)
        self.txt_masks = self._make_editor("Masks (dict)")
        self.txt_zones = self._make_editor("Zones (list)")
        self.txt_groups = self._make_editor("Groups (list)")
        split.addWidget(self.txt_masks["box"]); split.addWidget(self.txt_zones["box"]); split.addWidget(self.txt_groups["box"])

        self.btn_reload.clicked.connect(self.refresh)
        self.btn_apply.clicked.connect(self.apply)
        self.btn_add_mask.clicked.connect(self._add_mask_template)
        self.btn_add_zone.clicked.connect(self._add_zone_template)
        self.btn_add_group.clicked.connect(self._add_group_template)
        self.btn_add_zone_rect.clicked.connect(self._add_rect_zone_from_fields)
        self.btn_apply_mask_layer.clicked.connect(self._apply_mask_to_selected_layer)
        self.btn_apply_zone_layer.clicked.connect(self._apply_zone_to_selected_layer)
        self.btn_apply_group_layer.clicked.connect(self._apply_group_to_selected_layer)

        self._apply_target_gate(); self.refresh()
