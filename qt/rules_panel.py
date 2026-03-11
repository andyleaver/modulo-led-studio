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

from app.project_canonical import apply_project_root

class RulesPanel(QtWidgets.QWidget):
    """Rules panel.

    Keeps canonical JSON editing but adds helper tools so users can
    quickly start building rule structures without losing raw access.
    """

    def __init__(self, app_core):
        super().__init__()
        self.app_core = app_core

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        helpers = QtWidgets.QGroupBox("Rule Helpers")
        hlay = QtWidgets.QHBoxLayout(helpers)

        self.btn_add_rule = QtWidgets.QPushButton("Add Rule Template")
        self.btn_add_layer_rule = QtWidgets.QPushButton("Add Layer Opacity Rule")
        self.btn_remove_rule = QtWidgets.QPushButton("Remove Last Rule")

        hlay.addWidget(self.btn_add_rule)
        hlay.addWidget(self.btn_add_layer_rule)
        hlay.addWidget(self.btn_remove_rule)
        hlay.addStretch(1)
        outer.addWidget(helpers)

        quick = QtWidgets.QGroupBox("Signal → Layer Helper")
        qlay = QtWidgets.QHBoxLayout(quick)
        self.txt_signal = QtWidgets.QLineEdit()
        self.txt_signal.setPlaceholderText("signal key (e.g. audio.energy)")
        self.txt_signal.setText("audio.energy")
        qlay.addWidget(self.txt_signal, 2)

        self.cmb_op = QtWidgets.QComboBox()
        self.cmb_op.addItems([">", ">=", "<", "<=", "=="])
        qlay.addWidget(self.cmb_op, 0)

        self.spn_threshold = QtWidgets.QDoubleSpinBox()
        self.spn_threshold.setRange(-999999.0, 999999.0)
        self.spn_threshold.setDecimals(4)
        self.spn_threshold.setSingleStep(0.05)
        self.spn_threshold.setValue(0.2)
        qlay.addWidget(self.spn_threshold, 0)

        self.spn_layer = QtWidgets.QSpinBox()
        self.spn_layer.setRange(0, 999)
        self.spn_layer.setValue(0)
        qlay.addWidget(self.spn_layer, 0)

        self.spn_opacity = QtWidgets.QDoubleSpinBox()
        self.spn_opacity.setRange(0.0, 1.0)
        self.spn_opacity.setDecimals(3)
        self.spn_opacity.setSingleStep(0.05)
        self.spn_opacity.setValue(1.0)
        qlay.addWidget(self.spn_opacity, 0)

        self.btn_insert_signal_layer_rule = QtWidgets.QPushButton("Insert Rule")
        qlay.addWidget(self.btn_insert_signal_layer_rule, 0)
        outer.addWidget(quick)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Rules"))
        top.addStretch(1)

        self.btn_reload = QtWidgets.QPushButton("Reload")
        self.btn_apply = QtWidgets.QPushButton("Apply")

        top.addWidget(self.btn_reload)
        top.addWidget(self.btn_apply)
        outer.addLayout(top)

        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        outer.addWidget(self.editor, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        note = QtWidgets.QLabel(
            "Rules are edited as canonical JSON. Helpers insert valid templates, "
            "but all rule capabilities remain directly editable."
        )
        note.setWordWrap(True)
        outer.addWidget(note)

        self.btn_reload.clicked.connect(self._reload)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_add_rule.clicked.connect(self._add_rule_template)
        self.btn_add_layer_rule.clicked.connect(self._add_layer_opacity_rule_template)
        self.btn_remove_rule.clicked.connect(self._remove_rule)
        self.btn_insert_signal_layer_rule.clicked.connect(self._insert_signal_layer_rule)

        self._reload()

    def _project(self):
        try:
            return getattr(self.app_core, "project", {}) or {}
        except Exception:
            return {}

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

        try:
            fn = getattr(self.app_core, "rebuild_preview", None)
            if callable(fn):
                fn("rules_panel_apply")
        except Exception:
            pass

    def _reload(self):
        try:
            pd = self._project()
            rules = pd.get("rules", []) or []
        except Exception:
            rules = []

        try:
            self.editor.setPlainText(json.dumps(rules, indent=2))
            self.status.setText(f"{len(rules)} rules loaded")
        except Exception:
            self.editor.setPlainText(str(rules))
            self.status.setText("Rules loaded")

    def _apply(self):
        try:
            data = json.loads(self.editor.toPlainText() or "[]")
            if not isinstance(data, list):
                raise ValueError("rules must be a JSON list.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Invalid Rules JSON", str(e))
            return

        project = dict(self._project())
        project, _snap, _changes = apply_project_root(project, "rules", data)
        self._set_project(project)

        QtWidgets.QMessageBox.information(
            self,
            "Rules Updated",
            f"Applied {len(data)} rules."
        )
        self._reload()

    def _load_editor_rules(self):
        try:
            data = json.loads(self.editor.toPlainText() or "[]")
            if not isinstance(data, list):
                return []
            return data
        except Exception:
            return []

    def _add_rule_template(self):
        data = self._load_editor_rules()
        data.append({
            "when": {
                "signal": "time",
                "op": ">",
                "value": 0.5
            },
            "then": {
                "set": {
                    "vars.number.example": 1
                }
            }
        })
        self.editor.setPlainText(json.dumps(data, indent=2))

    def _add_layer_opacity_rule_template(self):
        data = self._load_editor_rules()
        data.append({
            "when": {
                "signal": "audio.energy",
                "op": ">",
                "value": 0.2
            },
            "then": {
                "set": {
                    "layers[0].opacity": 1.0
                }
            }
        })
        self.editor.setPlainText(json.dumps(data, indent=2))

    def _insert_signal_layer_rule(self):
        data = self._load_editor_rules()
        signal_key = str(self.txt_signal.text() or "").strip() or "audio.energy"
        op = str(self.cmb_op.currentText() or ">").strip() or ">"
        threshold = float(self.spn_threshold.value())
        layer_idx = int(self.spn_layer.value())
        opacity = float(self.spn_opacity.value())
        data.append({
            "when": {
                "signal": signal_key,
                "op": op,
                "value": threshold
            },
            "then": {
                "set": {
                    f"layers[{layer_idx}].opacity": opacity
                }
            }
        })
        self.editor.setPlainText(json.dumps(data, indent=2))

    def _remove_rule(self):
        try:
            data = self._load_editor_rules()
            if data:
                data.pop()
                self.editor.setPlainText(json.dumps(data, indent=2))
        except Exception:
            pass
