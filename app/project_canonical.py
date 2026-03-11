from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app.project_manager_diagnostics import project_manager_diag_exc
from app.project_apply import (
    apply_project_root as _apply_project_root,
    apply_project_roots as _apply_project_roots,
    copy_project,
)

# Re-export the shared apply helpers immediately so imports from era/tooling modules
# never depend on this module reaching the bottom before names exist.
apply_project_root = _apply_project_root
apply_project_roots = _apply_project_roots
from app.project_manager_layout import _normalize_layout_keys, _assert_no_legacy_layout_keys
from app.project_manager_targets import (
    _ensure_masks_dict,
    _ensure_zones_groups_dict,
    _sync_zones_groups_into_masks,
    _ensure_referenced_targets_exist,
)
from app.project_manager_layers_state import (
    _ensure_layer_uids,
    _ensure_ui_defaults,
    _ensure_layer_modulotors_normalized,
    _canonicalize_legacy_layer_composition_keys,
    _assert_no_legacy_layer_composition_keys,
    _ensure_layer_effect_behavior_operator_defaults,
)
from app.project_normalize import normalize_project_zones_masks_groups
from app.eras.era_state import ensure_era_in_project
from app.eras.era_enforce import sanitize_project_for_era, enforce_project_against_era, EraViolation
from app.project_validation import validate_project
from app.kernel_layers import ensure_kernel_layers
from runtime.variables import ensure_variables
from runtime.rules import ensure_rules

_diag_exc = project_manager_diag_exc


def canonicalize_project_dict(project: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Return canonical project dict plus change log.

    This is the single authoritative project-truth pipeline for:
    - import/load migration
    - canonical layout/layer/target normalization
    - variables/rules/kernel defaults
    - era state presence
    """
    changes: List[str] = []
    p = copy_project(project)

    try:
        p2 = _normalize_layout_keys(p)
        if p2 != p:
            changes.append("normalized layout keys")
        p = p2
        _assert_no_legacy_layout_keys(p)

        before = json.dumps(p.get("ui", {}), sort_keys=True, default=str)
        _ensure_ui_defaults(p)
        if json.dumps(p.get("ui", {}), sort_keys=True, default=str) != before:
            changes.append("ensured ui defaults")

        before = json.dumps(p.get("masks", {}), sort_keys=True, default=str)
        _ensure_masks_dict(p)
        if json.dumps(p.get("masks", {}), sort_keys=True, default=str) != before:
            changes.append("ensured masks dict")

        before_zg = json.dumps({"zones": p.get("zones"), "groups": p.get("groups")}, sort_keys=True, default=str)
        _ensure_zones_groups_dict(p)
        _sync_zones_groups_into_masks(p)
        _ensure_referenced_targets_exist(p)
        after_zg = json.dumps({"zones": p.get("zones"), "groups": p.get("groups")}, sort_keys=True, default=str)
        if before_zg != after_zg:
            changes.append("normalized targets")

        before_layers = json.dumps(p.get("layers", []), sort_keys=True, default=str)
        _ensure_layer_effect_behavior_operator_defaults(p)
        _ensure_layer_uids(p)
        _ensure_layer_modulotors_normalized(p)
        _canonicalize_legacy_layer_composition_keys(p)
        _assert_no_legacy_layer_composition_keys(p)
        after_layers = json.dumps(p.get("layers", []), sort_keys=True, default=str)
        if before_layers != after_layers:
            changes.append("normalized layers")

        p, normalize_changes = normalize_project_zones_masks_groups(p)
        changes.extend(normalize_changes)

        p, v_changed = ensure_variables(p)
        if v_changed:
            changes.append("ensured variables")

        p, r_changed = ensure_rules(p)
        if r_changed:
            changes.append("ensured rules")

        p, k_changed = ensure_kernel_layers(p)
        if k_changed:
            changes.append("ensured kernel layers")

        before_ui = json.dumps((p.get("ui") or {}), sort_keys=True, default=str)
        p = ensure_era_in_project(p)
        if json.dumps((p.get("ui") or {}), sort_keys=True, default=str) != before_ui:
            changes.append("ensured era state")
    except Exception as error:
        _diag_exc(error, "canonicalize_project_dict")
    # De-duplicate while preserving order so canonical passes are stable and auditable.
    seen = set()
    stable_changes: List[str] = []
    for c in changes:
        cs = str(c)
        if cs not in seen:
            seen.add(cs)
            stable_changes.append(cs)
    return p, stable_changes


def finalize_project_dict(
    project: Dict[str, Any],
    *,
    sanitize_for_era: bool = False,
    enforce_era: bool = False,
    validate: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Canonicalize, optionally era-sanitize/enforce, optionally validate.

    Returns (project, validation_snapshot, changes).
    """
    p, changes = canonicalize_project_dict(project)
    validation = {"ok": True, "errors": [], "warnings": []}

    try:
        if sanitize_for_era:
            p = sanitize_project_for_era(p)
            changes.append("sanitized for era")
        if enforce_era:
            enforce_project_against_era(p)
    except EraViolation:
        raise
    except Exception as error:
        _diag_exc(error, "finalize_project_dict.era")

    if validate:
        try:
            snap = validate_project(p)
            validation = snap if isinstance(snap, dict) else validation
        except Exception as error:
            validation = {"ok": False, "errors": [f"validate_project failed: {error}"], "warnings": []}
    return p, validation, changes


def apply_project_roots(
    project: Dict[str, Any],
    updates: Dict[str, Any],
    *,
    sanitize_for_era: bool = False,
    enforce_era: bool = False,
    validate: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Delegate canonical top-level updates to the single shared apply path."""
    return _apply_project_roots(
        project,
        updates,
        sanitize_for_era=sanitize_for_era,
        enforce_era=enforce_era,
        validate=validate,
    )


def apply_project_root(
    project: Dict[str, Any],
    key: str,
    value: Any,
    *,
    sanitize_for_era: bool = False,
    enforce_era: bool = False,
    validate: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Delegate one-key canonical updates to the single shared apply path."""
    return _apply_project_root(
        project,
        key,
        value,
        sanitize_for_era=sanitize_for_era,
        enforce_era=enforce_era,
        validate=validate,
    )
