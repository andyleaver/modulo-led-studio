from __future__ import annotations

from typing import Any, Dict, List, Optional

from qt.qt_compat import QtCore, QtWidgets  # type: ignore

class PlaylistTab(QtWidgets.QWidget):
    """Playlist tab (preview-time scheduling).

    Real workflow:
    - choose presets
    - assign durations
    - order entries
    - start / stop playback
    """

    def __init__(self, app_core, controller=None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app_core = app_core
        self.controller = controller

        root = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel("Playlists sequence multiple presets into a running show.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.grp_playlist_gate = QtWidgets.QGroupBox("Historical Playlist Gate")
        pg = QtWidgets.QVBoxLayout(self.grp_playlist_gate)
        self.lbl_playlist_gate = QtWidgets.QLabel("")
        self.lbl_playlist_gate.setWordWrap(True)
        pg.addWidget(self.lbl_playlist_gate)
        root.addWidget(self.grp_playlist_gate)

        self.grp_simple_show = QtWidgets.QGroupBox("Simple Show Path")
        sp = QtWidgets.QVBoxLayout(self.grp_simple_show)

        self.lbl_simple_show = QtWidgets.QLabel(
            "In Effect Picker mode, Playlist is the optional show-building step between Presets and Export."
        )
        self.lbl_simple_show.setWordWrap(True)
        sp.addWidget(self.lbl_simple_show)

        row = QtWidgets.QHBoxLayout()
        self.btn_playlist_to_export = QtWidgets.QPushButton("Go To Export")
        row.addWidget(self.btn_playlist_to_export)
        self.btn_playlist_unlock = QtWidgets.QPushButton("Unlock Full Modulo")
        row.addWidget(self.btn_playlist_unlock)
        row.addStretch(1)
        sp.addLayout(row)

        root.addWidget(self.grp_simple_show)
        self.btn_playlist_to_export.clicked.connect(self._goto_export_tab)
        self.btn_playlist_unlock.clicked.connect(self._unlock_full_modulo)
        stage = QtWidgets.QLabel("Sequence presets into a timed show without changing the underlying project structure.")
        stage.setStyleSheet("font-weight:600;")
        root.addWidget(stage)
        summary = QtWidgets.QLabel("Workflow Summary: playlists reuse presets to sequence a show after the project structure is already built.")
        summary.setWordWrap(True)
        root.addWidget(summary)
        quick = QtWidgets.QLabel("Quick Tip: Playlists sequence saved presets over time to build a show without changing the underlying project structure.")
        quick.setWordWrap(True)
        root.addWidget(quick)
        workflow = QtWidgets.QLabel("Playlist Workflow: choose presets, set durations, order entries, then start playback to run a show sequence.")
        workflow.setWordWrap(True)
        root.addWidget(workflow)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        hdr = QtWidgets.QHBoxLayout()
        hdr.addWidget(QtWidgets.QLabel("Playlist"))
        hdr.addStretch(1)
        root.addLayout(hdr)

        top = QtWidgets.QHBoxLayout()
        self.cmb_preset = QtWidgets.QComboBox()
        top.addWidget(self.cmb_preset, 2)

        self.spn_dur = QtWidgets.QDoubleSpinBox()
        self.spn_dur.setRange(0.5, 3600.0)
        self.spn_dur.setValue(10.0)
        self.spn_dur.setSuffix(" s")
        top.addWidget(self.spn_dur, 0)

        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_add.clicked.connect(self._add)
        top.addWidget(self.btn_add, 0)

        self.btn_remove = QtWidgets.QPushButton("Remove")
        self.btn_remove.clicked.connect(self._remove)
        top.addWidget(self.btn_remove, 0)
        root.addLayout(top)

        self.list = QtWidgets.QListWidget()
        root.addWidget(self.list, 1)

        edit_row = QtWidgets.QHBoxLayout()
        self.btn_up = QtWidgets.QPushButton("Move Up")
        self.btn_up.clicked.connect(self._move_up)
        edit_row.addWidget(self.btn_up)

        self.btn_down = QtWidgets.QPushButton("Move Down")
        self.btn_down.clicked.connect(self._move_down)
        edit_row.addWidget(self.btn_down)

        self.btn_dup = QtWidgets.QPushButton("Duplicate")
        self.btn_dup.clicked.connect(self._duplicate)
        edit_row.addWidget(self.btn_dup)

        self.btn_clear = QtWidgets.QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear)
        edit_row.addWidget(self.btn_clear)

        edit_row.addStretch(1)
        root.addLayout(edit_row)

        controls = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("Refresh presets")
        self.btn_refresh.clicked.connect(self.refresh_presets)
        controls.addWidget(self.btn_refresh)

        self.btn_load_now = QtWidgets.QPushButton("Load Preset Now")
        self.btn_load_now.clicked.connect(self._load_selected_preset_now)
        controls.addWidget(self.btn_load_now)

        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_start.clicked.connect(self._start)
        controls.addWidget(self.btn_start)

        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_stop.clicked.connect(self._stop)
        controls.addWidget(self.btn_stop)
        controls.addStretch(1)
        root.addLayout(controls)
        helper = QtWidgets.QLabel("Load Preset Now: preview the selected preset in the current project before adding it to the playlist.")
        helper.setWordWrap(True)
        root.addWidget(helper)
        next_step = QtWidgets.QLabel("Next: use Diagnostics to verify the show state, then Export when the project is ready for hardware output.")
        next_step.setWordWrap(True)
        root.addWidget(next_step)
        reminder = QtWidgets.QLabel("Before you continue: playlists sequence saved presets, they do not replace the underlying project workflow.")
        reminder.setWordWrap(True)
        root.addWidget(reminder)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self._entries: List[Dict[str, Any]] = []
        self.list.currentRowChanged.connect(self._update_buttons)
        self.refresh_presets()
        self._update_buttons()

    def _load_selected_preset_now(self):
        nm = str(self.cmb_preset.currentText() or "").strip()
        if not nm:
            return
        try:
            from app.presets_store import load_presets
            proj = None
            for p in load_presets() or []:
                if isinstance(p, dict) and str(p.get("name") or "").strip() == nm:
                    proj = p.get("project")
                    break
            if not isinstance(proj, dict):
                return
            setattr(self.app_core, "project", dict(proj))
            try:
                fn = getattr(self.app_core, "rebuild_preview", None)
                if callable(fn):
                    fn("playlist_load_selected_preset_now")
            except Exception:
                pass
            QtWidgets.QMessageBox.information(self, "Preset Loaded", f"Loaded preset '{nm}' into the current project.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Preset Load Failed", str(e))

    def _check_preset_export(self, preset_name: str) -> str:
        try:
            from app.presets_store import load_presets
            proj = None
            for p in load_presets() or []:
                if isinstance(p, dict) and str(p.get("name") or "") == preset_name:
                    proj = p.get("project")
                    break
            if not isinstance(proj, dict):
                return ""
            from app.export_gate import analyze_project_export_issues, format_export_issues
            target_id = None
            try:
                fn = getattr(self.app_core, "get_export_target_id", None)
                target_id = fn() if callable(fn) else None
            except Exception:
                target_id = None
            issues = analyze_project_export_issues(proj, target_id=target_id)
            return format_export_issues(issues) if issues else ""
        except Exception:
            return ""

    def refresh_presets(self):
        names: List[str] = []
        try:
            from app.presets_store import load_presets
            names = [str(p.get("name")) for p in load_presets() if isinstance(p, dict) and str(p.get("name") or "").strip()]
        except Exception:
            names = []
        self.cmb_preset.blockSignals(True)
        self.cmb_preset.clear()
        self.cmb_preset.addItems(names)
        self.cmb_preset.blockSignals(False)
        self.status.setText(f"{len(names)} presets available")

    def _render_entries(self):
        self.list.blockSignals(True)
        self.list.clear()
        total = 0.0
        for e in self._entries:
            nm = str(e.get("name"))
            dur = float(e.get("duration_s") or 0.0)
            total += dur
            warn = bool(e.get("export_warn"))
            mark = " ⚠" if warn else ""
            self.list.addItem(f"{nm}{mark} — {dur:.1f}s")
        self.list.blockSignals(False)
        self.status.setText(f"{len(self._entries)} playlist entries · total {total:.1f}s")
        self._update_buttons()

    def _push_to_core(self):
        try:
            fn = getattr(self.app_core, "configure_playlist", None)
            if callable(fn):
                fn(self._entries)
        except Exception:
            pass
        return False

    def _selected_index(self) -> int:
        return int(self.list.currentRow())

    def _update_buttons(self):
        idx = self._selected_index()
        n = len(self._entries)
        has = 0 <= idx < n
        self.btn_remove.setEnabled(has)
        self.btn_up.setEnabled(has and idx > 0)
        self.btn_down.setEnabled(has and idx >= 0 and idx < n - 1)
        self.btn_dup.setEnabled(has)
        self.btn_clear.setEnabled(n > 0)

    def _add(self):
        nm = str(self.cmb_preset.currentText() or "").strip()
        if not nm:
            return
        dur = float(self.spn_dur.value())
        warn_txt = self._check_preset_export(nm)
        entry = {"name": nm, "duration_s": dur}
        if warn_txt:
            entry["export_warn"] = True
            QtWidgets.QMessageBox.warning(self, "Preset is not fully exportable", warn_txt)
        self._entries.append(entry)
        self._render_entries()
        self._push_to_core()
        if self.list.count() > 0:
            self.list.setCurrentRow(self.list.count() - 1)

    def _remove(self):
        idx = self._selected_index()
        if idx < 0 or idx >= len(self._entries):
            return
        self._entries.pop(idx)
        self._render_entries()
        self._push_to_core()
        if self.list.count() > 0:
            self.list.setCurrentRow(min(idx, self.list.count() - 1))

    def _move_up(self):
        idx = self._selected_index()
        if idx <= 0 or idx >= len(self._entries):
            return
        self._entries[idx - 1], self._entries[idx] = self._entries[idx], self._entries[idx - 1]
        self._render_entries()
        self._push_to_core()
        self.list.setCurrentRow(idx - 1)

    def _move_down(self):
        idx = self._selected_index()
        if idx < 0 or idx >= len(self._entries) - 1:
            return
        self._entries[idx + 1], self._entries[idx] = self._entries[idx], self._entries[idx + 1]
        self._render_entries()
        self._push_to_core()
        self.list.setCurrentRow(idx + 1)

    def _duplicate(self):
        idx = self._selected_index()
        if idx < 0 or idx >= len(self._entries):
            return
        self._entries.insert(idx + 1, dict(self._entries[idx]))
        self._render_entries()
        self._push_to_core()
        self.list.setCurrentRow(idx + 1)

    def _clear(self):
        self._entries = []
        self._render_entries()
        self._push_to_core()

    def _start(self):
        try:
            for e in list(self._entries or []):
                nm = str(e.get("name") or "").strip()
                if not nm:
                    continue
                warn_txt = self._check_preset_export(nm)
                if warn_txt:
                    QtWidgets.QMessageBox.warning(self, "Playlist contains non-exportable presets", warn_txt)
                    break
        except Exception:
            pass
        try:
            fn = getattr(self.app_core, "start_playlist", None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _stop(self):
        try:
            fn = getattr(self.app_core, "stop_playlist", None)
            if callable(fn):
                fn()
        except Exception:
            pass

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

    def _goto_export_tab(self):
        self._goto_tab_by_prefix("Export")

    def _unlock_full_modulo(self):
        try:
            if self.controller and hasattr(self.controller, "_apply_studio_mode"):
                self.controller._apply_studio_mode("full_modulo")
        except Exception:
            pass

    def _playlist_gates(self):
        try:
            fn = getattr(self.app_core, "get_era_gates", None)
            return dict(fn() if callable(fn) else {})
        except Exception:
            return {}

    def _apply_playlist_gate(self):
        gates = self._playlist_gates()
        allow_presets = bool(gates.get("allow_presets", True))
        phase_kind = str(gates.get("phase_kind") or "historical").strip().lower()
        enabled = bool(allow_presets or phase_kind in ("plateau", "modulo"))
        model = str(gates.get("control_model") or "").strip().lower()
        try:
            self.lbl_playlist_gate.setText(
                f"Historical playlist gate: control model = {model or 'full_modulo'} · "
                f"playlist {'enabled' if enabled else 'locked'}."
            )
        except Exception:
            pass
        widgets = [
            getattr(self, "panel", None),
            getattr(self, "grp_simple_show", None),
            getattr(self, "btn_playlist_to_export", None),
            getattr(self, "btn_playlist_unlock", None),
        ]
        for w in widgets:
            try:
                if w is not None:
                    w.setEnabled(bool(enabled))
            except Exception:
                pass
