from __future__ import annotations

import copy
import time

from app.project_canonical import apply_project_root
from typing import Any, Dict, List, Optional

from qt.qt_compat import QtWidgets  # type: ignore

class PresetsTab(QtWidgets.QWidget):
    """Presets/Scenes tab.

    Presets capture current project state so users can quickly build reusable
    scenes and feed them into playlists.
    """

    def __init__(self, app_core, controller=None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller
        self._presets: List[Dict[str, Any]] = []

        root = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel("Presets store reusable setups. Save combinations of layers, targeting, rules, and behaviors here.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.grp_preset_gate = QtWidgets.QGroupBox("Historical Preset Gate")
        pg = QtWidgets.QVBoxLayout(self.grp_preset_gate)
        self.lbl_preset_gate = QtWidgets.QLabel("")
        self.lbl_preset_gate.setWordWrap(True)
        pg.addWidget(self.lbl_preset_gate)
        root.addWidget(self.grp_preset_gate)

        self.grp_effect_picker = QtWidgets.QGroupBox("Effect Picker Path")
        ep = QtWidgets.QVBoxLayout(self.grp_effect_picker)

        self.lbl_effect_picker = QtWidgets.QLabel(
            "In the simple path, save reusable looks here before building a playlist or exporting."
        )
        self.lbl_effect_picker.setWordWrap(True)
        ep.addWidget(self.lbl_effect_picker)

        row = QtWidgets.QHBoxLayout()
        self.btn_presets_to_playlist = QtWidgets.QPushButton("Go To Playlist")
        row.addWidget(self.btn_presets_to_playlist)
        self.btn_presets_unlock = QtWidgets.QPushButton("Unlock Full Modulo")
        row.addWidget(self.btn_presets_unlock)
        row.addStretch(1)
        ep.addLayout(row)

        root.addWidget(self.grp_effect_picker)
        self.btn_presets_to_playlist.clicked.connect(self._goto_playlist_tab)
        self.btn_presets_unlock.clicked.connect(self._unlock_full_modulo)
        stage = QtWidgets.QLabel("Save reusable project states for later recall and show building.")
        stage.setStyleSheet("font-weight:600;")
        root.addWidget(stage)
        summary = QtWidgets.QLabel("Workflow Summary: save stable project states here after configuring the surface, targets, layers, behaviors, rules, and operators.")
        summary.setWordWrap(True)
        root.addWidget(summary)
        quick = QtWidgets.QLabel("Quick Tip: Presets capture the current project state so you can reload, duplicate, and reuse complete setups.")
        quick.setWordWrap(True)
        root.addWidget(quick)
        workflow = QtWidgets.QLabel("Preset Workflow: build the project, save the current state here, then load or duplicate presets for reuse and playlists.")
        workflow.setWordWrap(True)
        root.addWidget(workflow)
        next_step = QtWidgets.QLabel("Next: go to Playlist to sequence saved presets into a running show, or return to earlier tabs to refine the project.")
        next_step.setWordWrap(True)
        root.addWidget(next_step)
        reminder = QtWidgets.QLabel("Before you continue: presets capture the current project state. Return to earlier tabs first if the setup is not ready to save.")
        reminder.setWordWrap(True)
        root.addWidget(reminder)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Presets"))
        hdr.addStretch(1)
        root.addLayout(hdr)

        row = QtWidgets.QHBoxLayout()
        self.txt_name = QtWidgets.QLineEdit()
        self.txt_name.setPlaceholderText("Preset name…")
        row.addWidget(self.txt_name, 2)
        self.btn_save = QtWidgets.QPushButton("Save Current")
        self.btn_save.clicked.connect(self._save_current)
        row.addWidget(self.btn_save, 0)
        self.btn_overwrite = QtWidgets.QPushButton("Overwrite Selected")
        self.btn_overwrite.clicked.connect(self._overwrite_selected)
        row.addWidget(self.btn_overwrite, 0)
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        row.addWidget(self.btn_refresh, 0)
        root.addLayout(row)

        body = QtWidgets.QHBoxLayout()
        root.addLayout(body, 1)
        self.list = QtWidgets.QListWidget()
        self.list.currentRowChanged.connect(self._select)
        body.addWidget(self.list, 2)

        right = QtWidgets.QVBoxLayout()
        body.addLayout(right, 3)
        self.lbl = QtWidgets.QLabel("—")
        self.lbl.setWordWrap(True)
        right.addWidget(self.lbl)

        btns = QtWidgets.QHBoxLayout()
        self.btn_load = QtWidgets.QPushButton("Load")
        self.btn_load.clicked.connect(self._load)
        btns.addWidget(self.btn_load)
        self.btn_duplicate = QtWidgets.QPushButton("Duplicate")
        self.btn_duplicate.clicked.connect(self._duplicate)
        btns.addWidget(self.btn_duplicate)
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_delete.clicked.connect(self._delete)
        btns.addWidget(self.btn_delete)
        btns.addStretch(1)
        right.addLayout(btns)

        right.addStretch(1)

        self.refresh()

    def _current_project_copy(self) -> dict:
        try:
            proj = getattr(self.app_core, "project")
            if not isinstance(proj, dict):
                proj = {}
        except Exception:
            proj = {}
        proj2 = copy.deepcopy(proj)
        try:
            ui = proj2.get("ui") if isinstance(proj2.get("ui"), dict) else {}
            ui["apply_era_template_on_boot"] = False
            proj2, _, _ = apply_project_root(proj2, "ui", ui)
        except Exception:
            pass
        return False
        return proj2

    def _save_named_project(self, name: str, project: dict):
        from app.presets_store import load_presets, save_presets
        presets = load_presets()
        out = [p for p in presets if str(p.get("name")) != name]
        out.append({"name": name, "project": project, "ts": time.time()})
        save_presets(out)

    def refresh(self):
        try:
            from app.presets_store import load_presets
            self._presets = load_presets()
        except Exception:
            self._presets = []

        self.list.blockSignals(True)
        self.list.clear()
        for p in self._presets:
            name = str(p.get("name") or "")
            ts = float(p.get("ts") or 0.0)
            s = name
            if ts > 0:
                s += "  " + time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
            try:
                from app.export_gate import analyze_project_export_issues
                proj = p.get("project") if isinstance(p, dict) else None
                issues = analyze_project_export_issues(proj) if isinstance(proj, dict) else []
                if issues:
                    s = "⚠ " + s
            except Exception:
                pass
            self.list.addItem(s)
        self.list.blockSignals(False)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        else:
            self._select(-1)

    def _project_summary(self, proj: dict) -> str:
        if not isinstance(proj, dict):
            return "Preset: —"
        layers = len(proj.get("layers") or [])
        rules = len(proj.get("rules") or [])
        zones = len(proj.get("zones") or [])
        groups = len(proj.get("groups") or [])
        masks = len(proj.get("masks") or {})
        return (
            f"Preset: {proj.get('name', '(embedded project)')}\n"
            f"Layers: {layers}\nRules: {rules}\nZones: {zones}\nGroups: {groups}\nMasks: {masks}"
        )

    def _select(self, idx: int):
        ok = (0 <= idx < len(self._presets))
        self.btn_load.setEnabled(ok)
        self.btn_delete.setEnabled(ok)
        self.btn_duplicate.setEnabled(ok)
        self.btn_overwrite.setEnabled(ok)
        if not ok:
            self.lbl.setText("—")
            return
        p = self._presets[idx]
        proj = p.get("project") if isinstance(p, dict) else {}
        details = self._project_summary(proj if isinstance(proj, dict) else {})
        nm = str(p.get("name") or "")
        self.lbl.setText(f"{details}\nSaved as: {nm}")

    def _save_current(self):
        nm = (self.txt_name.text() or "").strip()
        if not nm:
            nm = time.strftime("Preset %Y-%m-%d %H:%M", time.localtime())
        try:
            self._save_named_project(nm, self._current_project_copy())
        except Exception as e:
            try:
                from runtime.diagnostics import GLOBAL_DIAGS
                GLOBAL_DIAGS.exception(e, domain="UI", code="PRESET_SAVE_FAIL", summary="Preset save failed")
            except Exception:
                pass
        self.txt_name.setText("")
        self.refresh()

    def _overwrite_selected(self):
        idx = int(self.list.currentRow())
        if idx < 0 or idx >= len(self._presets):
            return
        nm = str(self._presets[idx].get("name") or "").strip()
        if not nm:
            return
        try:
            self._save_named_project(nm, self._current_project_copy())
            QtWidgets.QMessageBox.information(self, "Preset Updated", f"Overwrote preset '{nm}'.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Preset Update Failed", str(e))
        self.refresh()

    def _load(self):
        idx = int(self.list.currentRow())
        if idx < 0 or idx >= len(self._presets):
            return
        proj = self._presets[idx].get("project")
        if not isinstance(proj, dict):
            return
        try:
            setattr(self.app_core, "project", copy.deepcopy(proj))
        except Exception:
            return

        try:
            from app.export_gate import analyze_project_export_issues, format_export_issues, log_export_issues_diag
            target_id = None
            try:
                fn = getattr(self.app_core, 'get_export_target_id', None)
                target_id = fn() if callable(fn) else None
            except Exception:
                target_id = None
            issues = analyze_project_export_issues(getattr(self.app_core, 'project', {}) or {}, target_id=target_id)
            if issues:
                log_export_issues_diag(issues, where='presets.load', target_id=target_id)
                msg = format_export_issues(issues)
                QtWidgets.QMessageBox.warning(self, 'Preset is not fully exportable', msg)
        except Exception:
            pass

    def _duplicate(self):
        idx = int(self.list.currentRow())
        if idx < 0 or idx >= len(self._presets):
            return
        entry = self._presets[idx]
        nm = str(entry.get("name") or "").strip()
        proj = entry.get("project")
        if not nm or not isinstance(proj, dict):
            return
        new_name = f"{nm} Copy"
        try:
            self._save_named_project(new_name, copy.deepcopy(proj))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Preset Duplicate Failed", str(e))
        self.refresh()

    def _delete(self):
        idx = int(self.list.currentRow())
        if idx < 0 or idx >= len(self._presets):
            return
        nm = str(self._presets[idx].get("name"))
        try:
            from app.presets_store import load_presets, save_presets
            presets = [p for p in load_presets() if str(p.get("name")) != nm]
            save_presets(presets)
        except Exception:
            pass
        self.refresh()

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

    def _goto_playlist_tab(self):
        self._goto_tab_by_prefix("Preview")

    def _unlock_full_modulo(self):
        try:
            if self.controller and hasattr(self.controller, "_apply_studio_mode"):
                self.controller._apply_studio_mode("full_modulo")
        except Exception:
            pass

    def _preset_gates(self):
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            return dict(fn() if callable(fn) else {})
        except Exception:
            return {}

    def _apply_preset_gate(self):
        gates = self._preset_gates()
        allow_presets = bool(gates.get("allow_presets", True))
        model = str(gates.get("control_model") or "").strip().lower()
        try:
            self.lbl_preset_gate.setText(
                f"Historical preset gate: control model = {model or 'full_modulo'} · "
                f"presets {'enabled' if allow_presets else 'locked'}."
            )
        except Exception:
            pass
        widgets = [
            getattr(self, "panel", None),
            getattr(self, "grp_effect_picker", None),
            getattr(self, "btn_presets_to_playlist", None),
            getattr(self, "btn_presets_unlock", None),
        ]
        for w in widgets:
            try:
                if w is not None:
                    w.setEnabled(bool(allow_presets))
            except Exception:
                pass
