
from __future__ import annotations

from typing import Any, Dict

def _gates(window) -> Dict[str, Any]:
    try:
        app_core = getattr(window, "app_core", None)
        if app_core is None:
            return {}
        fn = getattr(app_core, "get_era_gates", None)
        return dict(fn() if callable(fn) else {})
    except Exception:
        return {}

def _safe_apply(panel, method_name: str):
    try:
        fn = getattr(panel, method_name, None)
        if callable(fn):
            fn()
    except Exception:
        pass

def _set_enabled(obj, enabled: bool):
    try:
        if obj is not None:
            obj.setEnabled(bool(enabled))
    except Exception:
        pass

def apply_ui_gates(window) -> None:
    """Apply fine-grained era gating to the already-created UI.

    Tab visibility is still handled by tab_registry / era tab gating.
    This helper focuses on panel-level enable/disable so the visible UI
    also respects the active historical capability model.
    """
    gates = _gates(window)

    allow_targets = bool(gates.get("allow_targets", True))
    allow_rules = bool(gates.get("allow_rules", True))
    allow_audio = bool(gates.get("allow_audio", True))
    allow_operators = bool(gates.get("allow_operators", True))
    allow_export = bool(gates.get("allow_export", True))
    allow_presets = bool(gates.get("allow_presets", True))
    allow_full_modulo = bool(gates.get("allow_full_modulo", False))
    stop_here_ok = bool(gates.get("stop_here_ok", False))

    # Let each tab apply its own historical gate messaging / per-widget locking.
    _safe_apply(getattr(window, "layout_panel", None), "_apply_surface_gate")
    _safe_apply(getattr(window, "layout_panel", None), "_apply_studio_mode_gate")
    _safe_apply(getattr(window, "targets_tab", None), "_apply_target_gate")
    _safe_apply(getattr(window, "signals_tab", None), "_apply_signal_gate")
    _safe_apply(getattr(window, "rules_tab", None), "_apply_rules_gate")
    _safe_apply(getattr(window, "operators_tab", None), "_apply_operator_gate")
    _safe_apply(getattr(window, "export_tab", None), "_apply_export_gate")
    _safe_apply(getattr(window, "presets_tab", None), "_apply_preset_gate")
    _safe_apply(getattr(window, "playlist_tab", None), "_apply_playlist_gate")
    _safe_apply(getattr(window, "diagnostics_tab", None), "_apply_diagnostics_gate")

    # Fine-grained cross-tab policy:
    # - Signals are only meaningful once rules/audio-style routing exists.
    # - Playlist belongs to the plateau/modulo app models, not early historical eras.
    # - Diagnostics stays visible, but advanced escape-hatch surfaces remain gated
    #   by the diagnostics tab itself.
    _set_enabled(getattr(window, "targets_tab", None), allow_targets)
    _set_enabled(getattr(window, "signals_tab", None), bool(allow_audio or allow_rules))
    _set_enabled(getattr(window, "rules_tab", None), allow_rules)
    _set_enabled(getattr(window, "operators_tab", None), allow_operators)
    _set_enabled(getattr(window, "export_tab", None), allow_export)
    _set_enabled(getattr(window, "presets_tab", None), allow_presets)
    _set_enabled(getattr(window, "playlist_tab", None), bool(stop_here_ok or allow_full_modulo))
