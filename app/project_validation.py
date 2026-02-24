from __future__ import annotations

"""Project validation for Zones / Groups / Masks (Phase A lock).

This module is intentionally UI-agnostic and exporter-agnostic.
It provides a *single* authoritative validator that can be used by:
- Qt UI (Validate button)
- Export gate
- Selftests

Beta contract:
- Validation must be deterministic.
- Canonical target mask is project['ui']['target_mask'].
- If validation fails, project is structurally unsafe.
"""

from typing import Any, Dict, List, Optional

from app.masks_resolver import resolve_mask_to_indices


def _layout_count(project: Dict[str, Any]) -> Optional[int]:
    try:
        layout = (project or {}).get("layout") or {}
        if isinstance(layout, dict) and "count" in layout:
            n = int(layout.get("count") or 0)
            return n if n > 0 else None
    except Exception:
        return None
    return None


def _validate_index_list(name: str, idx: Any, *, n: Optional[int]) -> Optional[str]:
    if idx is None:
        return f"{name}: missing indices"
    if not isinstance(idx, (list, tuple, set)):
        return f"{name}: indices must be a list"
    out: List[int] = []
    try:
        for x in idx:
            out.append(int(x))
    except Exception:
        return f"{name}: indices contain non-integers"
    if n is not None:
        for v in out:
            if v < 0 or v >= n:
                return f"{name}: out-of-range index {v} (layout count {n})"
    return None


def validate_project(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return validation snapshot: {'ok': bool, 'errors': [...], 'warnings': [...]}"""
    p = project if isinstance(project, dict) else {}
    errors: List[str] = []
    warnings: List[str] = []
    n = _layout_count(p)

    zones = p.get("zones") or {}
    if zones and not isinstance(zones, dict):
        errors.append("zones: must be a dict of name -> {indices:[...]}")
        zones = {}
    if isinstance(zones, dict):
        for zn in sorted(zones.keys(), key=lambda s: str(s).lower()):
            node = zones.get(zn) or {}
            if not isinstance(node, dict):
                errors.append(f"zone '{zn}': must be a dict")
                continue
            err = _validate_index_list(f"zone '{zn}'", node.get("indices"), n=n)
            if err:
                errors.append(err)

    groups = p.get("groups") or {}
    if groups and not isinstance(groups, dict):
        errors.append("groups: must be a dict of name -> {indices:[...]}")
        groups = {}
    if isinstance(groups, dict):
        for gn in sorted(groups.keys(), key=lambda s: str(s).lower()):
            node = groups.get(gn) or {}
            if not isinstance(node, dict):
                errors.append(f"group '{gn}': must be a dict")
                continue
            err = _validate_index_list(f"group '{gn}'", node.get("indices"), n=n)
            if err:
                errors.append(err)

    masks = p.get("masks") or {}
    if masks and not isinstance(masks, dict):
        errors.append("masks: must be a dict of name -> mask node")
        masks = {}

    if isinstance(masks, dict):
        for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
            try:
                resolve_mask_to_indices(p, str(mk), n=n)
            except Exception as e:
                errors.append(f"mask '{mk}': {e}")
        # Mask key namespace sanity:
        # Mask *definitions* must not use other namespaces like 'group:' or 'zone:'.
        # Those prefixes are for *references* (e.g. group:foo) and are resolved by the resolver.
        groups2 = p.get('groups') or {}
        if not isinstance(groups2, dict):
            groups2 = {}
        for mk in list(masks.keys()):
            if not isinstance(mk, str):
                continue
            if ':' in mk:
                errors.append(f"mask '{mk}': invalid key namespace '" + mk.split(':',1)[0] + ":' (mask keys must not use other namespaces)")
                if mk.startswith('group:'):
                    gn = mk.split(':',1)[1]
                    if gn in groups2:
                        errors.append(f"mask '{mk}': shadows group '{gn}' (remove this mask alias; groups are referenced as group:{gn})")

    # Canonical target mask: project['ui']['target_mask']
    ui = p.get("ui") or {}
    if not isinstance(ui, dict):
        ui = {}
    tm = ui.get("target_mask")
    if tm is not None and str(tm).strip():
        tm = str(tm)
        if not isinstance(masks, dict) or tm not in masks:
            errors.append(f"ui.target_mask '{tm}' does not exist in masks")
        else:
            try:
                resolve_mask_to_indices(p, tm, n=n)
            except Exception as e:
                errors.append(f"ui.target_mask '{tm}' failed to resolve: {e}")

    # Deprecated: top-level target_mask (should be migrated/removed by normalizer)
    if isinstance(p, dict) and "target_mask" in p:
        warnings.append("Deprecated: top-level target_mask present; normalizer should migrate/remove it")


    # Layer target refs (zone/group) sanity (warnings; normalizer coerces to 'all' if invalid)
    layers = p.get("layers") if isinstance(p, dict) else None
    if isinstance(layers, list):
        zkeys = list(zones.keys()) if isinstance(zones, dict) else []
        gkeys = list(groups.keys()) if isinstance(groups, dict) else []
        zlen = len(zkeys)
        glen = len(gkeys)
        for idx, L in enumerate(layers):
            if not isinstance(L, dict):
                continue
            # Operators schema sanity ()
            ops = L.get('operators')
            if ops is not None and not isinstance(ops, list):
                errors.append(f"Layer[{idx}] operators: must be a list")
            elif isinstance(ops, list):
                for oi, op in enumerate(ops):
                    if not isinstance(op, dict):
                        errors.append(f"Layer[{idx}] operators[{oi}]: must be a dict")
                        continue
                    if not str(op.get('type') or '').strip():
                        errors.append(f"Layer[{idx}] operators[{oi}].type: missing")
                    params = op.get('params')
                    if params is not None and not isinstance(params, dict):
                        errors.append(f"Layer[{idx}] operators[{oi}].params: must be a dict")

            tk = str(L.get("target_kind", "all") or "all").lower().strip()
            tr = L.get("target_ref", 0)
            try:
                tr_i = int(tr)
            except Exception:
                tr_i = 0
            if tk == "zone" and not (0 <= tr_i < zlen):
                warnings.append(f"Layer[{idx}] target_ref out of range for zone; will be normalized")
            if tk == "group" and not (0 <= tr_i < glen):
                warnings.append(f"Layer[{idx}] target_ref out of range for group; will be normalized")
            if tk not in ("all", "zone", "group"):
                warnings.append(f"Layer[{idx}] unknown target_kind '{tk}'; will be normalized")


    ok = (len(errors) == 0)
    return {"ok": ok, "errors": errors, "warnings": warnings}
