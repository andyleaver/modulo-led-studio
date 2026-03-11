from __future__ import annotations

import os

from qt.layout_panel_common import diag_exc as _diag_exc


def era_gates(app_core):
    try:
        fn = getattr(app_core, 'get_era_gates', None)
        return dict(fn() if callable(fn) else {})
    except Exception:
        return {}


class LayoutPanelModesMixin:
    def _apply_studio_mode_gate(self):
        gates = era_gates(self.app_core)
        phase_kind = str(gates.get('phase_kind') or 'historical').strip().lower()
        control_model = str(gates.get('control_model') or '').strip().lower()
        allow_full_modulo = bool(gates.get('allow_full_modulo', False))
        stop_here_ok = bool(gates.get('stop_here_ok', False))
        effect_enabled = bool(phase_kind == 'plateau' or control_model == 'effect_picker' or stop_here_ok)
        modulo_enabled = bool(phase_kind == 'modulo' or allow_full_modulo)
        bypass = str(os.environ.get('MODULO_BYPASS_ERA', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        try:
            mode_lower = str(getattr(self.controller, '_load_studio_mode', lambda: 'full_modulo')() or 'full_modulo').strip().lower()
        except Exception:
            mode_lower = 'full_modulo'
        try:
            self.btn_mode_era.setEnabled(True)
            self.btn_mode_effect.setEnabled(effect_enabled)
            self.btn_mode_modulo.setEnabled(modulo_enabled)
            self.btn_mode_reset.setEnabled(modulo_enabled or effect_enabled)
            show_era_controls = not (bypass or mode_lower == 'full_modulo')
            self.mode_group.setVisible(show_era_controls)
            self.grp_surface_gate.setVisible(show_era_controls)
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.mode_gate')
        if phase_kind == 'historical':
            msg = 'Historical mode gate: stay on the Era journey. Effect Picker and Full Modulo remain locked until their historical phases are reached.'
        elif phase_kind == 'plateau':
            msg = 'Historical mode gate: the modern effect-picker plateau is now available. You can stay here, or explicitly unlock Modulo from the plateau choice.'
        else:
            msg = 'Historical mode gate: Modulo is now historically available in this journey.'
        self.lbl_mode_gate.setText(msg)

    def _set_mode_status(self, text: str):
        self.lbl_mode_status.setText(str(text))

    def _set_tab_by_prefix(self, prefix: str) -> bool:
        tabs = getattr(self.controller, 'tabs', None)
        if tabs is None:
            return False
        for i in range(tabs.count()):
            label = str(tabs.tabText(i) or '')
            if label.startswith(prefix):
                tabs.setCurrentIndex(i)
                return True
        return False

    def _go_era_journey(self):
        opened = False
        try:
            fn = getattr(self.controller, '_open_era_onboarding', None)
            if callable(fn):
                fn(); opened = True
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.mode_era')
        self._set_mode_status('Mode Status: opening Era journey / historical onboarding.' if opened else 'Mode Status: Era journey entry point is staged from Surface. Use the Era onboarding window when available.')

    def _reset_studio_mode(self):
        try:
            fn = getattr(self.controller, '_apply_studio_mode', None)
            if callable(fn):
                fn('full_modulo')
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.mode_reset')
        self._set_tab_by_prefix('1. Surface')
        self._set_mode_status('Mode Status: Full studio restored. All main workflow tabs are visible again.')

    def _go_effect_picker_path(self):
        gates = era_gates(self.app_core)
        phase_kind = str(gates.get('phase_kind') or 'historical').strip().lower()
        control_model = str(gates.get('control_model') or '').strip().lower()
        stop_here_ok = bool(gates.get('stop_here_ok', False))
        if not (phase_kind == 'plateau' or control_model == 'effect_picker' or stop_here_ok):
            self._set_mode_status('Mode Status: Effect Picker remains historically locked until the plateau era.')
            return
        applied = False
        try:
            fn = getattr(self.controller, '_apply_studio_mode', None)
            if callable(fn):
                fn('effect_picker'); applied = True
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.mode_effect_picker')
        self._set_tab_by_prefix('4. Behaviors')
        self._set_mode_status('Mode Status: Effect Picker path active. Studio is narrowed to the simpler effects/presets/export flow.' if applied else 'Mode Status: Effect Picker path starts at Behaviors, then usually Presets / Playlist / Export.')

    def _go_full_modulo_path(self):
        gates = era_gates(self.app_core)
        phase_kind = str(gates.get('phase_kind') or 'historical').strip().lower()
        allow_full_modulo = bool(gates.get('allow_full_modulo', False))
        if not (phase_kind == 'modulo' or allow_full_modulo):
            self._set_mode_status('Mode Status: Full Modulo remains historically locked until the Modulo era is explicitly unlocked.')
            return
        applied = False
        try:
            fn = getattr(self.controller, '_apply_studio_mode', None)
            if callable(fn):
                fn('full_modulo'); applied = True
        except Exception as exc:
            _diag_exc(exc, 'qt/layout_panel.py.mode_full_modulo')
        self._set_tab_by_prefix('2. Targets')
        self._set_mode_status('Mode Status: Full Modulo path active. Full studio workflow is visible.' if applied else 'Mode Status: Full Modulo path continues Surface → Targets → Layers → Signals / Variables → Rules → Operators.')

    def _apply_surface_gate(self):
        gates = era_gates(self.app_core)
        allow_matrix = bool(gates.get('allow_matrix', True))
        allow_addressable = bool(gates.get('allow_addressable', True))
        model = str(gates.get('control_model') or '').strip().lower()
        try:
            self.layout_combo.model().item(1).setEnabled(bool(allow_matrix))
        except Exception:
            pass
        self.btn_matrix_32x32.setEnabled(bool(allow_matrix))
        self.btn_matrix_64x32.setEnabled(bool(allow_matrix))
        self.btn_matrix_64x64.setEnabled(bool(allow_matrix))
        self.btn_matrix_128x64.setEnabled(bool(allow_matrix))
        self.matrix_box.setEnabled(bool(allow_matrix))
        self.btn_strip_144.setEnabled(bool(allow_addressable))
        self.btn_strip_288.setEnabled(bool(allow_addressable))
        self.lbl_surface_gate.setText(f"Historical surface gate: control model = {model or 'full_modulo'} · matrix {'enabled' if allow_matrix else 'locked'} · addressable helpers {'enabled' if allow_addressable else 'locked'}.")
