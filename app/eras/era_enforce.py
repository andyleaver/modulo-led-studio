from __future__ import annotations

from typing import Dict, Any, List, Tuple

from .era_history import get_era


class EraViolation(Exception):
    """Raised when a project violates the active era gates.

    This is intentionally a hard-fail for correctness and historical truth.
    """
    pass


def _layer_behavior(layer: Dict[str, Any]) -> str:
    try:
        b = layer.get("behavior") or layer.get("effect")
        return str(b) if b is not None else ""
    except Exception:
        return ""


def validate_project_against_era(project: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(project, dict):
        return ["Project is not a dict"]

    ui = project.get("ui") or {}
    era_id = ""
    if isinstance(ui, dict):
        era_id = str(ui.get("era_id") or "")
    era = get_era(era_id)

    gates = era.gates
    layers = project.get("layers") or []
    if not isinstance(layers, list):
        layers = []

    # Max layers
    if len(layers) > int(gates.max_layers):
        errors.append(f"[E_ERA_MAX_LAYERS] Era '{era.title}' allows at most {gates.max_layers} layers (got {len(layers)}).")

    # Allowed effects filter
    if gates.allowed_effects is not None:
        allowed = set(gates.allowed_effects)
        for i, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            key = _layer_behavior(layer)
            if key and key not in allowed:
                errors.append(f"[E_ERA_EFFECT_BLOCKED] Era '{era.title}' does not include behavior '{key}' (layer {i}).")

    # Rules
    if not gates.allow_rules:
        rv6 = project.get("rules_v6") or []
        if isinstance(rv6, list) and len(rv6) > 0:
            errors.append(f"[E_ERA_RULES_BLOCKED] Era '{era.title}' does not allow rules_v6 (found {len(rv6)} rules).")

    # Operators
    if not gates.allow_operators:
        for i, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            ops = layer.get("operators") or []
            if isinstance(ops, list) and len(ops) > 0:
                errors.append(f"[E_ERA_OPERATORS_BLOCKED] Era '{era.title}' does not allow operators (layer {i} has {len(ops)}).")

    # Audio
    if not gates.allow_audio:
        sigs = project.get("signals") or {}
        if isinstance(sigs, dict):
            # crude: any audio.* refs should be blocked; we fail if any audio keys exist
            for k in list(sigs.keys()):
                if str(k).startswith("audio"):
                    errors.append(f"[E_ERA_AUDIO_BLOCKED] Era '{era.title}' does not allow audio signals (found '{k}').")
                    break

    # Matrix layouts
    if not gates.allow_matrix:
        layout = project.get("layout") or {}
        if isinstance(layout, dict):
            if (layout.get("type") == "matrix") or (layout.get("width") and layout.get("height")):
                errors.append(f"[E_ERA_MATRIX_BLOCKED] Era '{era.title}' does not allow matrix layouts.")

    return errors


def enforce_project_against_era(project: Dict[str, Any]) -> None:
    errs = validate_project_against_era(project)
    if errs:
        raise EraViolation("\n".join(errs))
