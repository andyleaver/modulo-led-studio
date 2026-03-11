from __future__ import annotations

from typing import Dict, Any, List

import os

from app.project_canonical import apply_project_root
from app.project_model import get_surface_spec, get_surface_runtime_snapshot, build_surface_dict, coerce_surface_kind
from .era_state import ensure_era_in_project
from .era_history import get_era


class EraViolation(Exception):
    pass


def _layer_behavior(layer: Dict[str, Any]) -> str:
    try:
        behavior = layer.get("behavior")
        return str(behavior) if behavior is not None else ""
    except Exception:
        return ""


def _canonical_layout_dict(project: Dict[str, Any]) -> Dict[str, Any]:
    try:
        snap = get_surface_runtime_snapshot(project)
        if isinstance(snap, dict) and snap:
            return dict(snap)
    except Exception:
        pass
    project, _validation, _changes = apply_project_root(project, "surface", build_surface_dict())
    snap = get_surface_runtime_snapshot(project)
    return dict(snap) if isinstance(snap, dict) else build_surface_dict()


def sanitize_project_for_era(project: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(project, dict):
        return project
    if os.environ.get("MODULO_ERA_DISABLED", "") == "1":
        return project

    canonical = ensure_era_in_project(project)
    ui = canonical.get("ui") or {}
    era_id = str(ui.get("era_id") or "") if isinstance(ui, dict) else ""
    era = get_era(era_id)
    gates = era.gates

    layers = canonical.get("layers") or []
    if not isinstance(layers, list):
        layers = []
    if len(layers) > int(gates.max_layers):
        layers = layers[: int(gates.max_layers)]

    allowed = set(gates.allowed_effects) if gates.allowed_effects is not None else None
    cleaned_layers: List[Dict[str, Any]] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        cleaned = dict(layer)
        if allowed is not None:
            key = _layer_behavior(cleaned)
            if key and key not in allowed:
                if allowed:
                    first_allowed = sorted(allowed)[0]
                    cleaned["behavior"] = first_allowed
                    cleaned.pop("effect", None)
                else:
                    continue
        if not gates.allow_operators:
            cleaned.pop("operators", None)
        if not gates.allow_full_modulo:
            cleaned.pop("modulotors", None)
        cleaned_layers.append(cleaned)
    canonical, _validation, _changes = apply_project_root(canonical, "layers", cleaned_layers)

    if not gates.allow_rules:
        canonical, _validation, _changes = apply_project_root(canonical, "rules", [])

    if not gates.allow_audio:
        signals = canonical.get("signals")
        if isinstance(signals, dict):
            filtered_signals = {
                key: value for (key, value) in signals.items() if not str(key).startswith("audio")
            }
            canonical, _validation, _changes = apply_project_root(canonical, "signals", filtered_signals)

    if not gates.allow_full_modulo:
        canonical, _validation, _changes = apply_project_root(canonical, "modulotors", [])

    if not gates.allow_targets or not gates.allow_export:
        export_state = canonical.get("export")
        if isinstance(export_state, dict):
            canonical, _validation, _changes = apply_project_root(canonical, "export", {})

    try:
        surface_spec = get_surface_spec(canonical)
    except Exception:
        surface_spec = None
    kind = coerce_surface_kind(getattr(surface_spec, "kind", "") if surface_spec is not None else "", default='strip')
    count = int(getattr(surface_spec, "count", 0) or 0) if surface_spec is not None else 0

    layout = dict(_canonical_layout_dict(canonical) or {})
    mapping = dict(layout.get('mapping') or {}) if isinstance(layout.get('mapping'), dict) else {}
    extras = {}
    for key in ('coords', 'exists_mask'):
        if isinstance(layout.get(key), list):
            extras[key] = list(layout.get(key) or [])
    for key in ('cell_size', 'cell'):
        try:
            value = int(layout.get(key) or 0)
        except Exception:
            value = 0
        if value > 0:
            extras[key] = int(value)
    if not gates.allow_addressable:
        layout = build_surface_dict(kind='strip', count=1, mapping=mapping, cell_size=extras.get('cell_size') or extras.get('cell'), extras=extras)
        canonical, _validation, _changes = apply_project_root(canonical, "surface", layout)
    elif not gates.allow_matrix and kind == "cells":
        collapse = max(1, count)
        layout = build_surface_dict(kind='strip', count=collapse, mapping=mapping, cell_size=extras.get('cell_size') or extras.get('cell'), extras=extras)
        canonical, _validation, _changes = apply_project_root(canonical, "surface", layout)

    return canonical


def validate_project_against_era(project: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(project, dict):
        return ["Project is not a dict"]

    canonical = ensure_era_in_project(project)
    ui = canonical.get("ui") or {}
    era_id = str(ui.get("era_id") or "") if isinstance(ui, dict) else ""
    era = get_era(era_id)
    gates = era.gates

    layers = canonical.get("layers") or []
    if not isinstance(layers, list):
        layers = []

    if len(layers) > int(gates.max_layers):
        errors.append(f"[E_ERA_MAX_LAYERS] Era '{era.title}' allows at most {gates.max_layers} layers (got {len(layers)}).")

    if gates.allowed_effects is not None:
        allowed = set(gates.allowed_effects)
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            key = _layer_behavior(layer)
            if key and key not in allowed:
                errors.append(f"[E_ERA_EFFECT_BLOCKED] Era '{era.title}' does not include behavior '{key}' (layer {index}).")

    if not gates.allow_rules:
        rules_list = canonical.get("rules") or []
        if isinstance(rules_list, list) and rules_list:
            errors.append(f"[E_ERA_RULES_BLOCKED] Era '{era.title}' does not allow rules (found {len(rules_list)} rules).")

    if not gates.allow_operators:
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            operators = layer.get("operators") or []
            if isinstance(operators, list) and operators:
                errors.append(f"[E_ERA_OPERATORS_BLOCKED] Era '{era.title}' does not allow operators (layer {index} has {len(operators)}).")

    if not gates.allow_audio:
        signals = canonical.get("signals") or {}
        if isinstance(signals, dict):
            for key in list(signals.keys()):
                if str(key).startswith("audio"):
                    errors.append(f"[E_ERA_AUDIO_BLOCKED] Era '{era.title}' does not allow audio signals (found '{key}').")
                    break

    try:
        surface_spec = get_surface_spec(canonical)
    except Exception:
        surface_spec = None
    kind = coerce_surface_kind(getattr(surface_spec, "kind", "") if surface_spec is not None else "", default='strip')
    count = int(getattr(surface_spec, "count", 0) or 0) if surface_spec is not None else 0

    if not gates.allow_matrix and kind == "cells":
        errors.append(f"[E_ERA_MATRIX_BLOCKED] Era '{era.title}' does not allow matrix control.")

    if not gates.allow_addressable and count > 1:
        errors.append(f"[E_ERA_ADDRESSABLE_BLOCKED] Era '{era.title}' only allows non-addressable style control.")

    if not gates.allow_targets:
        export_config = canonical.get("export") or {}
        if isinstance(export_config, dict) and export_config.get("target"):
            errors.append(f"[E_ERA_TARGETS_BLOCKED] Era '{era.title}' does not allow target/export configuration.")

    if not gates.allow_export:
        export_config = canonical.get("export") or {}
        if isinstance(export_config, dict) and export_config:
            errors.append(f"[E_ERA_EXPORT_BLOCKED] Era '{era.title}' does not allow export configuration.")

    return errors


def enforce_project_against_era(project: Dict[str, Any]) -> Dict[str, Any]:
    errors = validate_project_against_era(project)
    if errors:
        raise EraViolation("\n".join(errors))
    return project
