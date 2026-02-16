# Modulo - Project Normalization
# Purpose: make Zones/Masks/Groups deterministic + safe (beta lock)
# This file intentionally contains no UI code.

from __future__ import annotations
from typing import Any, Dict, List, Set, Tuple, Optional

def _as_int_list(xs) -> List[int]:
    out: List[int] = []
    if xs is None:
        return out
    if isinstance(xs, (list, tuple, set)):
        for v in xs:
            try:
                out.append(int(v))
            except Exception:
                pass
    return out

def _clamp_indices(idx: List[int], n: Optional[int]) -> List[int]:
    if n is None or n <= 0:
        # still dedupe/sort
        return sorted(set(i for i in idx if i >= 0))
    return sorted(set(i for i in idx if 0 <= i < n))

def _layout_count(project: Dict[str, Any]) -> Optional[int]:
    layout = project.get("layout") or {}
    if isinstance(layout, dict):
        try:
            n = int(layout.get("count") or 0)
            return n if n > 0 else None
        except Exception:
            return None
    return None

def normalize_project_zones_masks_groups(project: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Return (new_project, changes) with deterministic Zones/Groups/Masks and safe target_mask."""
    if not isinstance(project, dict):
        return {}, ["project was not a dict; reset to {}"]

    changes: List[str] = []
    p = dict(project)
    n = _layout_count(p)

    zones = p.get("zones") or {}
    if not isinstance(zones, dict):
        zones = {}
        changes.append("zones reset (was not dict)")

    groups = p.get("groups") or {}
    if not isinstance(groups, dict):
        groups = {}
        changes.append("groups reset (was not dict)")

    # Normalize zones
    zones2: Dict[str, Any] = {}
    for name, node in zones.items():
        if not isinstance(name, str) or not name.strip():
            changes.append("dropped zone with invalid name")
            continue
        node = node if isinstance(node, dict) else {}
        idx = _clamp_indices(_as_int_list(node.get("indices")), n)
        node2 = dict(node)
        node2["indices"] = idx
        zones2[name] = node2
        if node.get("indices") != idx:
            changes.append(f"zone '{name}' indices normalized")
    p["zones"] = zones2

    # Normalize groups
    groups2: Dict[str, Any] = {}
    for name, node in groups.items():
        if not isinstance(name, str) or not name.strip():
            changes.append("dropped group with invalid name")
            continue
        node = node if isinstance(node, dict) else {}
        idx = _clamp_indices(_as_int_list(node.get("indices")), n)
        node2 = dict(node)
        node2["indices"] = idx
        groups2[name] = node2
        if node.get("indices") != idx:
            changes.append(f"group '{name}' indices normalized")
    p["groups"] = groups2

    # Ensure masks exists
    masks = p.get("masks") or {}
    if not isinstance(masks, dict):
        masks = {}
        changes.append("masks reset (was not dict)")

    # Sync zones/groups into masks for beta-lock (idempotent)
    # Normalize layer target references against current zones/groups
    layers = p.get('layers')
    if isinstance(layers, list):
        zlen = len(zones2) if isinstance(zones2, list) else 0
        glen = len(groups2) if isinstance(groups2, list) else 0
        new_layers = []
        changed_any = False
        for L in layers:
            if not isinstance(L, dict):
                new_layers.append(L)
                continue
            tk = str(L.get('target_kind', 'all') or 'all').lower().strip()
            tr = L.get('target_ref', 0)
            try:
                tr_i = int(tr)
            except Exception:
                tr_i = 0
            ok = True
            if tk == 'zone':
                ok = (0 <= tr_i < zlen)
            elif tk == 'group':
                ok = (0 <= tr_i < glen)
            elif tk == 'all':
                ok = True
            else:
                # unknown target kind -> coerce to all
                ok = False
            if not ok:
                L2 = dict(L)
                L2['target_kind'] = 'all'
                L2['target_ref'] = 0
                new_layers.append(L2)
                changed_any = True
            else:
                if tr_i != tr:
                    L2 = dict(L)
                    L2['target_ref'] = tr_i
                    new_layers.append(L2)
                    changed_any = True
                else:
                    new_layers.append(L)
        if changed_any:
            p['layers'] = new_layers
            changes.append('normalized layer target_kind/target_ref refs')
    
    masks2 = dict(masks)
    for zname, znode in zones2.items():
        key = f"zone:{zname}"
        want = {"type": "indices", "indices": list(znode.get("indices") or [])}
        if masks2.get(key) != want:
            masks2[key] = want
            changes.append(f"synced mask '{key}' from zones")
    for gname, gnode in groups2.items():
        key = f"group:{gname}"
        want = {"type": "indices", "indices": list(gnode.get("indices") or [])}
        if masks2.get(key) != want:
            masks2[key] = want
            changes.append(f"synced mask '{key}' from groups")
    p["masks"] = masks2

    # Canonicalize target_mask storage:
    # - single source of truth is project['ui']['target_mask']
    # - top-level project['target_mask'] is migrated then removed
    ui = p.get('ui')
    if not isinstance(ui, dict):
        ui = {}
        p['ui'] = ui
    
    if 'target_mask' in p and ui.get('target_mask') is None:
        if isinstance(p.get('target_mask'), str):
            ui2 = dict(ui)
            ui2['target_mask'] = p.get('target_mask')
            p['ui'] = ui2
            ui = ui2
            changes.append('migrated top-level target_mask -> ui.target_mask')
    if 'target_mask' in p:
        try:
            del p['target_mask']
            changes.append('removed deprecated top-level target_mask')
        except Exception:
            pass
    
    tgt = ui.get('target_mask')
    if tgt is not None and (not isinstance(tgt, str) or tgt not in masks2):
        ui2 = dict(ui)
        ui2['target_mask'] = None
        p['ui'] = ui2
        changes.append('cleared invalid ui.target_mask')
    

    # : target mask migration + cleanup (authoritative: project['ui']['target_mask'])
    try:
        if isinstance(project, dict):
            ui = project.setdefault('ui', {}) if isinstance(project.get('ui', {}), dict) else {}
            if not isinstance(ui, dict):
                ui = {}
                project['ui'] = ui
            # migrate deprecated top-level target_mask -> ui.target_mask (only if ui has none)
            if (not ui.get('target_mask')) and ('target_mask' in project):
                tm = project.get('target_mask')
                if tm is not None and str(tm).strip():
                    ui['target_mask'] = str(tm)
            # remove deprecated top-level field always (we only want one source of truth)
            if 'target_mask' in project:
                try: del project['target_mask']
                except Exception: pass
            # if ui.target_mask points at missing mask, clear it
            tm = ui.get('target_mask')
            if tm is not None and str(tm).strip():
                tm = str(tm)
                masks = project.get('masks') if isinstance(project.get('masks'), dict) else {}
                if not isinstance(masks, dict) or tm not in masks:
                    ui['target_mask'] = ''
    except Exception:
        pass


    # : operators stack normalization (Phase 1 Structure)
    # Contract: layer['operators'] is a list of {'type': str, 'params': dict}
    # Policy: operators[0].type mirrors layer['behavior'] (or 'effect') for compatibility.
    try:
        layers = p.get('layers') or []
        if isinstance(layers, list):
            layers2 = []
            for L in layers:
                if not isinstance(L, dict):
                    layers2.append(L)
                    continue
                beh = str(L.get('behavior') or L.get('effect') or 'solid')
                ops = L.get('operators')
                if not isinstance(ops, list):
                    ops = []
                clean = []
                for op in ops:
                    if not isinstance(op, dict):
                        continue
                    t = str(op.get('type') or '').strip()
                    if not t:
                        continue
                    params = op.get('params')
                    if not isinstance(params, dict):
                        params = {}

                    # Preserve operator metadata used by preview/UI/export (do not strip it).
                    # Always include 'enabled' for deterministic semantics.
                    # Missing key warnings in diagnostics are not acceptable.
                    try:
                        op_clean = {'type': t, 'params': params, 'enabled': bool(op.get('enabled', True))}
                    except Exception:
                        op_clean = {'type': t, 'params': params, 'enabled': True}
                    try:
                        tk = op.get('target_kind')
                        if tk is not None and str(tk).strip():
                            op_clean['target_kind'] = str(tk)
                    except Exception:
                        pass
                    try:
                        tkey = op.get('target_key')
                        if tkey is not None and str(tkey).strip():
                            op_clean['target_key'] = str(tkey)
                    except Exception:
                        pass

                    clean.append(op_clean)
                if not clean:
                    clean = [{'type': beh, 'params': {}, 'enabled': True}]
                else:
                    if str(clean[0].get('type') or '') != beh:
                        # operators[0] mirrors the behavior key for compatibility.
                        # Keep enabled=True so the schema is uniform.
                        clean[0] = {
                            'type': beh,
                            'params': dict(clean[0].get('params') or {}),
                            'enabled': True,
                        }
                L2 = dict(L)
                L2['operators'] = clean
                layers2.append(L2)
            p['layers'] = layers2
    except Exception:
        pass

    return p, changes
