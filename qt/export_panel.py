from __future__ import annotations

# --- diagnostics helper (no silent failure) ---
try:
    from runtime.diagnostics import GLOBAL_DIAGS as _DIAGS
except Exception:  # pragma: no cover
    _DIAGS = None

def _diag_exc(e: Exception, where: str):
    try:
        if _DIAGS is not None:
            _DIAGS.exception(e, domain="UI", code="QT_UI_EXCEPTION", summary=where)
    except Exception:
        pass
try:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore
except Exception:
    from qt.qt_compat import QtCore, QtWidgets  # type: ignore

import json

class ExportPanel(QtWidgets.QWidget):
    """Export panel.

    Provides a stable UI surface for target selection plus honest export
    diagnostics / gating, without pretending features exist that are not yet
    surfaced in a richer exporter UI.
    """

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core
        self._targets = []

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        hdr = QtWidgets.QLabel("Export")
        try:
            f = hdr.font()
            f.setPointSize(max(10, f.pointSize() + 2))
            hdr.setFont(f)
        except Exception as e:
            _diag_exc(e, "qt/export_panel.py")
        outer.addWidget(hdr)

        target_box = QtWidgets.QGroupBox("Target")
        tlay = QtWidgets.QVBoxLayout(target_box)
        tlay.setContentsMargins(8, 8, 8, 8)
        tlay.setSpacing(6)

        row = QtWidgets.QHBoxLayout()
        self.cmb_target = QtWidgets.QComboBox()
        row.addWidget(self.cmb_target, 1)
        self.btn_refresh_targets = QtWidgets.QPushButton("Refresh Targets")
        row.addWidget(self.btn_refresh_targets, 0)
        self.btn_use_target = QtWidgets.QPushButton("Use Selected Target")
        row.addWidget(self.btn_use_target, 0)
        tlay.addLayout(row)

        self.lbl_target = QtWidgets.QLabel("")
        self.lbl_target.setWordWrap(True)
        tlay.addWidget(self.lbl_target)

        outer.addWidget(target_box, 0)

        self.btn_run = QtWidgets.QPushButton("Run Export Analysis")
        self.btn_run.clicked.connect(self._run)
        outer.addWidget(self.btn_run)

        self.out = QtWidgets.QPlainTextEdit()
        self.out.setReadOnly(True)
        outer.addWidget(self.out, 1)

        hint = QtWidgets.QLabel(
            "This panel gives direct access to export diagnostics now. It should remain honest "
            "about target readiness, project blockers, and preview-only behavior."
        )
        try:
            hint.setWordWrap(True)
        except Exception as e:
            _diag_exc(e, "qt/export_panel.py")
        outer.addWidget(hint)

        self.btn_refresh_targets.clicked.connect(self._reload_targets)
        self.btn_use_target.clicked.connect(self._apply_selected_target)
        self.cmb_target.currentIndexChanged.connect(self._update_target_label)

        self._reload_targets()

    def _project(self) -> dict:
        p = getattr(self.app_core, "project", None)
        return p if isinstance(p, dict) else {}

    def _set_project(self, project: dict) -> None:
        try:
            setattr(self.app_core, "project", project)
        except Exception:
            try:
                self.app_core._project = project
            except Exception:
                pass
        try:
            pm = getattr(self.app_core, "pm", None)
            if pm is not None:
                try:
                    pm.project = project
                except Exception:
                    pass
                try:
                    pm.dirty = True
                except Exception:
                    pass
                try:
                    pm._notify()
                except Exception:
                    pass
        except Exception:
            pass

    def _current_target_id(self) -> str:
        try:
            p = self._project()
            exp = p.get("export") or {}
            return str(exp.get("target_id") or "").strip()
        except Exception:
            return ""

    def _reload_targets(self):
        try:
            from export.targets.registry import list_targets
            self._targets = list_targets() or []
        except Exception as e:
            _diag_exc(e, "qt/export_panel.py.list_targets")
            self._targets = []

        current = self._current_target_id()
        self.cmb_target.blockSignals(True)
        self.cmb_target.clear()
        idx_to_select = -1
        for i, meta in enumerate(self._targets):
            tid = str(meta.get("id") or "")
            name = str(meta.get("name") or tid)
            level = str(meta.get("support_level") or "experimental")
            label = f"{name} [{level}]"
            self.cmb_target.addItem(label, tid)
            if current and tid == current:
                idx_to_select = i
        if idx_to_select >= 0:
            self.cmb_target.setCurrentIndex(idx_to_select)
        elif self.cmb_target.count() > 0:
            self.cmb_target.setCurrentIndex(0)
        self.cmb_target.blockSignals(False)
        self._update_target_label()

    def _selected_target_id(self) -> str:
        try:
            return str(self.cmb_target.currentData() or "").strip()
        except Exception:
            return ""

    def _selected_target_meta(self) -> dict:
        tid = self._selected_target_id()
        for meta in self._targets:
            if str(meta.get("id") or "") == tid:
                return meta
        return {}

    def _update_target_label(self):
        meta = self._selected_target_meta()
        if not meta:
            self.lbl_target.setText("No export target selected.")
            return
        name = str(meta.get("name") or meta.get("id") or "")
        tid = str(meta.get("id") or "")
        level = str(meta.get("support_level") or "experimental")
        emitter = str(meta.get("emitter_module") or "")
        self.lbl_target.setText(
            f"Selected target: {name} ({tid})\n"
            f"Support level: {level}\n"
            f"Emitter: {emitter}"
        )

    def _apply_selected_target(self):
        tid = self._selected_target_id()
        if not tid:
            QtWidgets.QMessageBox.warning(self, "No Target", "Please select an export target first.")
            return
        from app.project_canonical import apply_project_root

        project = dict(self._project())
        export_config = dict(project.get("export") or {})
        export_config["target_id"] = tid
        project, _validation, _changes = apply_project_root(project, "export", export_config)
        self._set_project(project)
        QtWidgets.QMessageBox.information(self, "Target Selected", f"Project export target set to {tid}.")

    def _behavior_summary(self, project: dict) -> str:
        try:
            from export.export_eligibility import get_eligibility, ExportStatus
        except Exception:
            return "Behavior export summary unavailable."

        counts = {"exportable": 0, "preview-only": 0, "blocked": 0}
        details = []
        for i, layer in enumerate(project.get("layers") or []):
            if not isinstance(layer, dict):
                continue
            key = str(layer.get("behavior") or "").strip()
            if not key:
                continue
            elig = get_eligibility(key)
            st = str(getattr(elig, "status", "") or "")
            if st in counts:
                counts[st] += 1
            reason = str(getattr(elig, "reason", "") or "")
            if reason:
                details.append(f"- layer {i}: {key} -> {st} ({reason})")
            else:
                details.append(f"- layer {i}: {key} -> {st}")
        out = [
            "Behavior export eligibility:",
            f"- exportable: {counts['exportable']}",
            f"- preview-only: {counts['preview-only']}",
            f"- blocked: {counts['blocked']}",
        ]
        if details:
            out.append("")
            out.extend(details)
        return "\n".join(out)

    def _run(self):
        project = self._project()
        target_meta = self._selected_target_meta()

        parts = []

        try:
            from app.project_diagnostics import diagnose_project
            diag = diagnose_project(project)
            parts.append("Project diagnostics:")
            parts.append(json.dumps(diag, indent=2))
        except Exception as e:
            _diag_exc(e, "qt/export_panel.py.diagnose_project")

        parts.append("")
        parts.append(self._behavior_summary(project))

        if target_meta:
            try:
                from export.gating import gate_project_for_target
                gate = gate_project_for_target(project, target_meta)
                parts.append("")
                parts.append("Target gating:")
                parts.append(json.dumps({
                    "ok": bool(getattr(gate, "ok", False)),
                    "warnings": list(getattr(gate, "warnings", []) or []),
                    "errors": list(getattr(gate, "errors", []) or []),
                    "suggestions": list(getattr(gate, "suggestions", []) or []),
                }, indent=2))
            except Exception as e:
                _diag_exc(e, "qt/export_panel.py.gate_project_for_target")
                parts.append("")
                parts.append(f"Target gating failed: {e}")
        else:
            parts.append("")
            parts.append("No export target selected.")

        self.out.setPlainText("\n".join(parts).strip())
