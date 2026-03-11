from __future__ import annotations

from typing import List, Optional

from app.eras.era_registry import Era, EraGates, EraWorkbench, ERAS

def get_eras() -> List[Era]:
    return list(ERAS)

def get_historical_eras() -> List[Era]:
    return [e for e in get_eras() if str(getattr(e.gates, "phase_kind", "historical") or "historical") == "historical"]

def get_plateau_era() -> Era:
    for e in get_eras():
        if str(getattr(e.gates, "phase_kind", "") or "") == "plateau":
            return e
    return get_eras()[-2]

def get_modulo_era() -> Era:
    for e in get_eras():
        if str(getattr(e.gates, "phase_kind", "") or "") == "modulo":
            return e
    return get_eras()[-1]

def get_phase_note(era: Era) -> str:
    kind = str(getattr(era.gates, "phase_kind", "historical") or "historical")
    if kind == "historical":
        return "Historical control era"
    if kind == "plateau":
        return "Modern effect-picker plateau"
    if kind == "modulo":
        return "Modulo appears — no artificial ceiling"
    return "Era phase"

def get_era(era_id: str) -> Era:
    for e in get_eras():
        if e.era_id == era_id:
            return e
    return get_eras()[0]

def get_default_era_id() -> str:
    return get_eras()[0].era_id

def _studio_tools_for_gate(g: EraGates) -> List[str]:
    model = str(getattr(g, "control_model", "") or "").strip().lower()
    tools: List[str] = ["era_panel", "era_workbench"]

    if model in {"indicator", "indicator_colour", "alert_pattern", "rgb_mix", "white_lighting"}:
        tools += ["single_scene_controls"]

    if model in {"array_control", "addressable_pixels", "effect_picker", "full_modulo"}:
        tools += ["surface_layout", "effect_library"]

    if model in {"addressable_pixels", "effect_picker", "full_modulo"}:
        tools += ["layer_stack"]

    if model in {"effect_picker", "full_modulo"}:
        tools += ["playlist"]

    if bool(getattr(g, "allow_matrix", False)):
        tools += ["matrix_tools"]

    if bool(getattr(g, "allow_addressable", False)):
        tools += ["pixel_controls"]

    if bool(getattr(g, "allow_presets", False)):
        tools += ["preset_browser"]

    if bool(getattr(g, "allow_targets", False)):
        tools += ["target_setup"]

    if bool(getattr(g, "allow_export", False)):
        tools += ["export_panel"]

    if bool(getattr(g, "allow_rules", False)):
        tools += ["rules_editor", "signal_routing"]

    if bool(getattr(g, "allow_operators", False)):
        tools += ["operators_panel"]

    if bool(getattr(g, "allow_audio", False)):
        tools += ["audio_signals"]

    if bool(getattr(g, "allow_full_modulo", False)):
        tools += ["modulotors", "resolver_inspector", "triage", "variables_panel", "diagnostics_panel"]

    seen = set()
    out: List[str] = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

def get_studio_tools_for_era(era: Era) -> List[str]:
    return _studio_tools_for_gate(era.gates)

def get_workbench_for_era(era: Era) -> Optional[EraWorkbench]:
    return getattr(era, "workbench", None)
