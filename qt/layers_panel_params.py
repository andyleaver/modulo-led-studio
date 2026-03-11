from __future__ import annotations

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

import copy
import time as _time

from runtime.resolver import set_address
from params.registry import PARAMS
from params.ensure import ensure_params
from behaviors.registry import get_effect

class LayersPanelParamsMixin:
    def _effect_uses(self, effect_key: str):
            try:
                eff = get_effect(str(effect_key or ""))
                uses = list(getattr(eff, "uses", []) or [])
                return [str(k) for k in uses if str(k) in PARAMS]
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
                return []

    def _clear_params_form(self):
            try:
                while self.params_form.rowCount() > 0:
                    self.params_form.removeRow(0)
            except Exception:
                pass
            self._param_widgets = {}

    def _bind_keys_for_param(self, key: str):
            out = []
            for suffix in ("_bind_var", "_bind_layer"):
                bk = f"{key}{suffix}"
                if bk in PARAMS:
                    out.append(bk)
            return out

    def _make_bind_widget(self, bind_key: str, spec: dict):
            ptype = str(spec.get("type") or "string")
            widget = None
            if ptype == "bool":
                widget = QtWidgets.QCheckBox()
                widget.stateChanged.connect(lambda *_args, k=bind_key: self._apply_bind_value(k))
            elif ptype == "int":
                widget = QtWidgets.QSpinBox()
                widget.setRange(int(spec.get("min", -999999)), int(spec.get("max", 999999)))
                widget.setSingleStep(int(spec.get("step", 1) or 1))
                widget.valueChanged.connect(lambda *_args, k=bind_key: self._apply_bind_value(k))
            elif ptype == "enum":
                widget = QtWidgets.QComboBox()
                choices = list(spec.get("choices") or [])
                if "" not in [str(c) for c in choices]:
                    widget.addItem("")
                widget.addItems([str(c) for c in choices])
                widget.currentTextChanged.connect(lambda *_args, k=bind_key: self._apply_bind_value(k))
            else:
                widget = QtWidgets.QLineEdit()
                widget.editingFinished.connect(lambda k=bind_key: self._apply_bind_value(k))
            return widget

    def _make_param_widget(self, key: str, spec: dict):
            ptype = str(spec.get("type") or "float")
            label = str(spec.get("label") or key)
            widget = None
            if ptype == "bool":
                widget = QtWidgets.QCheckBox()
                widget.stateChanged.connect(lambda *_args, k=key: self._apply_param_value(k))
            elif ptype == "int":
                widget = QtWidgets.QSpinBox()
                widget.setRange(int(spec.get("min", -999999)), int(spec.get("max", 999999)))
                widget.setSingleStep(int(spec.get("step", 1) or 1))
                widget.valueChanged.connect(lambda *_args, k=key: self._apply_param_value(k))
            elif ptype == "enum":
                widget = QtWidgets.QComboBox()
                choices = list(spec.get("choices") or [])
                widget.addItems([str(c) for c in choices])
                widget.currentTextChanged.connect(lambda *_args, k=key: self._apply_param_value(k))
            elif ptype == "rgb":
                widget = QtWidgets.QLineEdit()
                widget.setPlaceholderText("r,g,b")
                widget.editingFinished.connect(lambda k=key: self._apply_param_value(k))
            else:
                widget = QtWidgets.QDoubleSpinBox()
                widget.setDecimals(int(spec.get("decimals", 3) or 3))
                widget.setRange(float(spec.get("min", -999999.0)), float(spec.get("max", 999999.0)))
                widget.setSingleStep(float(spec.get("step", 0.05) or 0.05))
                widget.valueChanged.connect(lambda *_args, k=key: self._apply_param_value(k))
            return label, widget

    def _rebuild_params_editor(self, effect_key: str):
            self._clear_params_form()
            uses = self._effect_uses(effect_key)
            if not uses:
                self.grp_params.setVisible(False)
                return
            self.grp_params.setVisible(True)
            for key in uses:
                spec = dict(PARAMS.get(key) or {})
                label, widget = self._make_param_widget(key, spec)
                self._param_widgets[key] = widget
                self.params_form.addRow(label, widget)

                bind_keys = self._bind_keys_for_param(key)
                if bind_keys:
                    row = QtWidgets.QWidget()
                    hlay = QtWidgets.QHBoxLayout(row)
                    try:
                        hlay.setContentsMargins(0, 0, 0, 0)
                    except Exception:
                        pass
                    for bind_key in bind_keys:
                        bspec = dict(PARAMS.get(bind_key) or {})
                        bwidget = self._make_bind_widget(bind_key, bspec)
                        self._param_bind_widgets[bind_key] = bwidget
                        label_txt = "Bind Var" if bind_key.endswith("_bind_var") else "Bind Layer"
                        hlay.addWidget(QtWidgets.QLabel(label_txt))
                        hlay.addWidget(bwidget, 1 if hasattr(bwidget, "setText") else 0)
                    hlay.addStretch(1)
                    self.params_form.addRow("", row)

    def _set_param_widget_value(self, key: str, value):
            widget = self._param_widgets.get(key)
            if widget is None:
                return
            try:
                widget.blockSignals(True)
            except Exception:
                pass
            try:
                if isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QtWidgets.QComboBox):
                    widget.setCurrentText(str(value))
                elif isinstance(widget, QtWidgets.QLineEdit):
                    if isinstance(value, (list, tuple)) and len(value) >= 3:
                        widget.setText(f"{int(value[0])},{int(value[1])},{int(value[2])}")
                    else:
                        widget.setText(str(value))
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            try:
                widget.blockSignals(False)
            except Exception:
                pass

    def _set_bind_widget_value(self, bind_key: str, value):
            widget = self._param_bind_widgets.get(bind_key)
            if widget is None:
                return
            try:
                widget.blockSignals(True)
            except Exception:
                pass
            try:
                if isinstance(widget, QtWidgets.QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QtWidgets.QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QtWidgets.QComboBox):
                    widget.setCurrentText(str(value))
                elif isinstance(widget, QtWidgets.QLineEdit):
                    widget.setText(str(value))
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            try:
                widget.blockSignals(False)
            except Exception:
                pass

    def _load_params_for_layer(self, idx: int, ly: dict):
            effect_key = str(ly.get("behavior") or "solid")
            self._rebuild_params_editor(effect_key)
            params = dict(ly.get("params") or {}) if isinstance(ly.get("params"), dict) else {}
            all_keys = list(self._effect_uses(effect_key))
            for key in self._effect_uses(effect_key):
                all_keys.extend(self._bind_keys_for_param(key))
            params = ensure_params(params, all_keys)
            for key in self._effect_uses(effect_key):
                default = (PARAMS.get(key) or {}).get("default")
                self._set_param_widget_value(key, params.get(key, default))
                for bind_key in self._bind_keys_for_param(key):
                    default_bind = (PARAMS.get(bind_key) or {}).get("default")
                    self._set_bind_widget_value(bind_key, params.get(bind_key, default_bind))

    def _read_param_widget_value(self, key: str):
            widget = self._param_widgets.get(key)
            if widget is None:
                return None
            if isinstance(widget, QtWidgets.QCheckBox):
                return bool(widget.isChecked())
            if isinstance(widget, QtWidgets.QSpinBox):
                return int(widget.value())
            if isinstance(widget, QtWidgets.QDoubleSpinBox):
                return float(widget.value())
            if isinstance(widget, QtWidgets.QComboBox):
                return str(widget.currentText() or "")
            if isinstance(widget, QtWidgets.QLineEdit):
                txt = str(widget.text() or "").strip()
                if "," in txt:
                    parts = [p.strip() for p in txt.split(",")]
                    if len(parts) >= 3:
                        try:
                            return [int(parts[0]), int(parts[1]), int(parts[2])]
                        except Exception:
                            return txt
                return txt
            return None

    def _read_bind_widget_value(self, bind_key: str):
            widget = self._param_bind_widgets.get(bind_key)
            if widget is None:
                return None
            if isinstance(widget, QtWidgets.QCheckBox):
                return bool(widget.isChecked())
            if isinstance(widget, QtWidgets.QSpinBox):
                return int(widget.value())
            if isinstance(widget, QtWidgets.QComboBox):
                return str(widget.currentText() or "")
            if isinstance(widget, QtWidgets.QLineEdit):
                return str(widget.text() or "")
            return None

    def _apply_bind_value(self, bind_key: str):
            idx = self._selected_index()
            if idx < 0:
                return
            value = self._read_bind_widget_value(bind_key)
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_set_address"):
                    pm.guarded_set_address(f"layers[{idx}].params.{bind_key}", value)
                    self._sync_project_from_pm()
                else:
                    pd = self._project_data()
                    pnew = copy.deepcopy(pd) if isinstance(pd, dict) else {}
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].params.{bind_key}", value=value)
                    if isinstance(pnew, dict):
                        self.app_core.project = pnew
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._set_address_inspector(f"layers[{idx}].params.{bind_key}")
            self._request_preview_rebuild(f"layer_bind_{bind_key}")
            self.refresh()

    def _apply_param_value(self, key: str):
            idx = self._selected_index()
            if idx < 0:
                return
            value = self._read_param_widget_value(key)
            pm = self._pm()
            try:
                if pm is not None and hasattr(pm, "guarded_set_address"):
                    pm.guarded_set_address(f"layers[{idx}].params.{key}", value)
                    self._sync_project_from_pm()
                else:
                    pd = self._project_data()
                    pnew = copy.deepcopy(pd) if isinstance(pd, dict) else {}
                    pnew, _ = set_address(project=pnew, address=f"layers[{idx}].params.{key}", value=value)
                    if isinstance(pnew, dict):
                        self.app_core.project = pnew
            except Exception as e:
                _diag_exc(e, "qt/layers_panel.py")
            self._set_address_inspector(f"layers[{idx}].params.{key}")
            self._request_preview_rebuild(f"layer_param_{key}")
            self.refresh()

    def _reload_param_bindings(self):
            try:
                idx = self._selected_index()
                pd = self._project_data()
                layers = pd.get("layers", []) if isinstance(pd, dict) else []
                self.list_param_bindings.clear()

                if idx < 0 or idx >= len(layers):
                    return

                ly = layers[idx]
                if not isinstance(ly, dict):
                    return

                params = ly.get("params") or {}
                if not isinstance(params, dict):
                    return

                for k in sorted(params.keys()):
                    if k.endswith("_bind_var") or k.endswith("_bind_signal") or k.endswith("_bind_time"):
                        addr = f"layers[{idx}].params.{k}"
                        self.list_param_bindings.addItem(addr)

            except Exception:
                pass

    def _on_binding_selected(self, text: str):
            try:
                self.txt_selected_binding.setText(str(text or ""))
            except Exception:
                pass

    def _copy_selected_binding(self):
            try:
                text = str(self.txt_selected_binding.text() or "").strip()
                if not text:
                    return
                app = QtWidgets.QApplication.instance()
                if app:
                    cb = app.clipboard()
                    if cb:
                        cb.setText(text)
            except Exception:
                pass

