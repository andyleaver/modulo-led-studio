from __future__ import annotations

"""Project diagnostics (read-only).

UI-agnostic helper used by the Qt "Zones/Masks" panel to surface structural
problems without mutating data.

 scope: *empty*, *invalid*, and *dangling* references for Zones / Groups / Masks.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from app.masks_resolver import resolve_mask_to_indices
from app.project_validation import validate_project


def _layout_count(project: Dict[str, Any]) -> Optional[int]:
    try:
        layout = (project or {}).get("layout") or {}
        if isinstance(layout, dict) and "count" in layout:
            n = int(layout.get("count") or 0)
            return n if n > 0 else None
    except Exception:
        return None
    return None


def _collect_mask_refs(node: Any, out: Set[str]) -> None:
    """Collect string mask references used inside a mask node."""
    try:
        if isinstance(node, str):
            out.add(node)
            return
        if isinstance(node, dict):
            a = node.get("a")
            b = node.get("b")
            if a is not None:
                _collect_mask_refs(a, out)
            if b is not None:
                _collect_mask_refs(b, out)
            return
        # lists/tuples/sets are indices (not refs)
    except Exception:
        return


def diagnose_project(project: Dict[str, Any]) -> Dict[str, List[str]]:
    """Return {'invalid': [...], 'dangling': [...], 'empty': [...]}."""
    p = project if isinstance(project, dict) else {}
    n = _layout_count(p)

    invalid: List[str] = []
    dangling: List[str] = []
    empty: List[str] = []

    # ---- invalid (validator is authoritative) ----
    snap = validate_project(p)
    for e in (snap.get("errors") or []):
        invalid.append(str(e))
    for w in (snap.get("warnings") or []):
        # warnings are still "invalid-ish" for beta visibility
        invalid.append(str(w))

    zones = p.get("zones") or {}
    if isinstance(zones, dict):
        for k in sorted(zones.keys(), key=lambda s: str(s).lower()):
            node = zones.get(k) or {}
            if isinstance(node, dict):
                idx = node.get("indices")
                has_range = (node.get('start') is not None and node.get('end') is not None)
                if (not has_range) and isinstance(idx, list) and len(idx) == 0:
                    empty.append(f"zone '{k}': empty indices")

    groups = p.get("groups") or {}
    if isinstance(groups, dict):
        for k in sorted(groups.keys(), key=lambda s: str(s).lower()):
            node = groups.get(k) or {}
            if isinstance(node, dict):
                idx = node.get("indices")
                if isinstance(idx, list) and len(idx) == 0:
                    empty.append(f"group '{k}': empty indices")

    masks = p.get("masks") or {}
    if isinstance(masks, dict):
        # ---- mask namespace invariants (A1) ----
        # Stored masks must be true mask defs only. Any ':' belongs to a target reference
        # (e.g. zone:NAME / group:NAME) and must not be persisted as a mask key.
        for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
            try:
                if isinstance(mk, str) and ":" in mk:
                    invalid.append(f"mask '{mk}': invalid key (contains ':')")
            except Exception:
                pass

        # Warn if a mask key shadows a group key (ambiguous authoring intent).
        groups = p.get("groups") or {}
        if isinstance(groups, dict):
            for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
                try:
                    if isinstance(mk, str) and mk in groups:
                        invalid.append(
                            f"mask '{mk}': shadows group '{mk}' (use group:{mk} when targeting)"
                        )
                except Exception:
                    pass

        # Empty masks (resolve ok but selects nothing)
        for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
            try:
                s = resolve_mask_to_indices(p, str(mk), n=n)
                if len(s) == 0:
                    empty.append(f"mask '{mk}': resolves to empty")
            except Exception as e:
                invalid.append(f"mask '{mk}': {e}")

        # Dangling refs inside composed masks
        all_keys = set(str(k) for k in masks.keys())
        for mk in sorted(masks.keys(), key=lambda s: str(s).lower()):
            refs: Set[str] = set()
            _collect_mask_refs(masks.get(mk), refs)
            for r in sorted(refs):
                if r not in all_keys:
                    dangling.append(f"mask '{mk}': references missing mask '{r}'")

    # Dangling UI target mask key
    ui = p.get("ui") or {}
    if isinstance(ui, dict):
        tm = ui.get("target_mask")
        if tm is not None and str(tm).strip():
            tm = str(tm)
            if not isinstance(masks, dict) or tm not in (masks or {}):
                dangling.append(f"ui.target_mask '{tm}': missing")

    # Dangling layer targets (zone/group index points past current list)
    layers = p.get("layers")
    if isinstance(layers, list):
        zkeys = sorted(list(zones.keys())) if isinstance(zones, dict) else []
        gkeys = sorted(list(groups.keys())) if isinstance(groups, dict) else []
        for i, L in enumerate(layers):
            if not isinstance(L, dict):
                continue
            tk = str(L.get("target_kind", "all") or "all").lower().strip()
            try:
                tr = int(L.get("target_ref", 0) or 0)
            except Exception:
                tr = 0
            if tk == "zone" and not (0 <= tr < len(zkeys)):
                dangling.append(f"Layer[{i}] target_kind=zone target_ref={tr}: out of range (zones={len(zkeys)})")
            if tk == "group" and not (0 <= tr < len(gkeys)):
                dangling.append(f"Layer[{i}] target_kind=group target_ref={tr}: out of range (groups={len(gkeys)})")


    # ---- namespace invariants (A1) ----
    # Names must be simple keys (no ":"), non-empty, and unique across zones/masks/groups.
    def _bad_key(k: str) -> bool:
        return (not k) or (k.strip() != k) or (":" in k)

    zks = list(zones.keys()) if isinstance(zones, dict) else []
    gks = list(groups.keys()) if isinstance(groups, dict) else []
    mks = list(masks.keys()) if isinstance(masks, dict) else []

    for k in sorted(set(zks)):
        if _bad_key(str(k)):
            invalid.append(f"zone key '{k}': invalid (no colon, no leading/trailing spaces, non-empty)")
    for k in sorted(set(gks)):
        if _bad_key(str(k)):
            invalid.append(f"group key '{k}': invalid (no colon, no leading/trailing spaces, non-empty)")
    for k in sorted(set(mks)):
        if _bad_key(str(k)):
            invalid.append(f"mask key '{k}': invalid (no colon, no leading/trailing spaces, non-empty)")

    collisions: Set[str] = set(zks) & set(gks) | set(zks) & set(mks) | set(gks) & set(mks)
    for k in sorted(collisions):
        invalid.append(f"entity key '{k}': collision across zones/masks/groups (must be unique)")

    # ---- operator target key sanity (A1) ----
    # Any operator with target_kind+target_key must point at an existing entity.
    if isinstance(layers, list):
        for li, L in enumerate(layers):
            if not isinstance(L, dict):
                continue
            ops = L.get("operators")
            if not isinstance(ops, list):
                continue
            for oi, op in enumerate(ops):
                if not isinstance(op, dict):
                    continue
                tk = op.get("target_kind")
                tkey = op.get("target_key")
                if tk is None or tkey is None:
                    continue
                tk_s = str(tk).lower().strip()
                tkey_s = str(tkey)
                if tk_s == "mask" and (not isinstance(masks, dict) or tkey_s not in masks):
                    dangling.append(f"Layer[{li}].Op[{oi}] target=mask:{tkey_s}: missing")
                if tk_s == "group" and (not isinstance(groups, dict) or tkey_s not in groups):
                    dangling.append(f"Layer[{li}].Op[{oi}] target=group:{tkey_s}: missing")
                if tk_s == "zone" and (not isinstance(zones, dict) or tkey_s not in zones):
                    dangling.append(f"Layer[{li}].Op[{oi}] target=zone:{tkey_s}: missing")
    return {"invalid": invalid, "dangling": dangling, "empty": empty}


def diagnostics_text(project: Dict[str, Any]) -> str:
    """Human-readable multiline diagnostics."""
    d = diagnose_project(project)
    lines: List[str] = []

    def emit(section: str, items: List[str]) -> None:
        if not items:
            return
        lines.append(section)
        for s in items:
            lines.append(f"  - {s}")
        lines.append("")

    emit("INVALID", d.get("invalid") or [])
    emit("DANGLING", d.get("dangling") or [])
    emit("EMPTY", d.get("empty") or [])

    if not lines:
        return "OK — no empty/invalid/dangling issues detected."

    # trim trailing blank
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)