from __future__ import annotations

from app.project_apply import replace_project_root, replace_project_roots
from app.project_manager_diagnostics import project_manager_diag_exc
_pm_diag_exc = project_manager_diag_exc
def _ensure_masks_dict(p: dict) -> dict:
  try:
    if "masks" in p and not isinstance(p.get("masks"), dict):
      p2 = dict(p or {})
      p2 = replace_project_root(p2, "masks", {})
      return p2
    return p
  except Exception as e:
    _pm_diag_exc(e, "return")
    return p
def _ensure_zones_groups_dict(p: dict) -> dict:
  """Allow old list-style zones/groups and normalize to dict-style used by Qt UI."""
  try:
    p2 = dict(p or {})
    changed = False
    z = p2.get("zones")
    if isinstance(z, list):
      z2 = {}
      for i, item in enumerate(z):
        if isinstance(item, dict):
          name = item.get("name") or item.get("id") or f"zone_{i}"
          d = dict(item)
          d.pop("name", None)
          d.pop("id", None)
          z2[str(name)] = d
      p2 = replace_project_root(p2, "zones", z2)
      changed = True
    g = p2.get("groups")
    if isinstance(g, list):
      g2 = {}
      for i, item in enumerate(g):
        if isinstance(item, dict):
          name = item.get("name") or item.get("id") or f"group_{i}"
          d = dict(item)
          d.pop("name", None)
          d.pop("id", None)
          g2[str(name)] = d
      p2 = replace_project_root(p2, "groups", g2)
      changed = True
    return p2 if changed else p
  except Exception as e:
    _pm_diag_exc(e, "return")
    return p
def _sync_zones_groups_into_masks(p: dict) -> dict:
  """Legacy no-op (kept for call-site stability).
  Historically, Modulo mirrored zones/groups into `masks` using prefixed keys like
  `zone:NAME` and `group:NAME`. That created invalid mask entries and key
  collisions (e.g. `group:group_diag`), and it made diagnostics/validation noisy.
  Current rule:
  - `p['masks']` contains ONLY true mask definitions (mask-only namespace).
  - Zones/groups are resolved via their own dictionaries when referenced as
    targets (target_kind=zone/group) or via `zone:` / `group:` prefixes at
    resolve-time (without persisting those aliases into `masks`).
  This function now performs a deterministic cleanup of legacy synthetic mask
  entries if present.
  """
  try:
    return _cleanup_legacy_mask_namespace(p)
  except Exception as e:
    _pm_diag_exc(e, "return")
    return p
def _cleanup_legacy_mask_namespace(p: dict) -> dict:
  """Remove legacy synthetic mask keys and shadowing duplicates.
  Removes:
  - Any mask key containing ':' (e.g. 'group:foo', 'zone:bar', 'mask:baz').
    These belong to target references, not stored mask keys.
  - Any mask key that exactly matches a group key and has identical indices
    (shadowing duplicate), because groups are referenced as `group:<name>`.
  """
  masks = p.get("masks")
  if not isinstance(masks, dict):
    return p
  masks = dict(masks)
  groups = p.get("groups") or {}
  if not isinstance(groups, dict):
    groups = {}
  # 1) Remove any prefixed keys living inside masks.
  bad_keys = [k for k in masks.keys() if isinstance(k, str) and (":" in k)]
  for k in bad_keys:
    try:
      masks.pop(k, None)
    except Exception as e:
      from runtime.diagnostics import GLOBAL_DIAGS
      GLOBAL_DIAGS.exception(e, domain="PROJECT", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"app/project_manager.py"})
      pass
  # 2) Remove shadowing duplicates where masks['groupname'] duplicates groups['groupname'] indices.
  for gk, gv in list(groups.items()):
    if not isinstance(gk, str):
      continue
    mv = masks.get(gk)
    if not isinstance(mv, dict):
      continue
    if not isinstance(gv, dict):
      continue
    mi = mv.get("indices")
    gi = gv.get("indices")
    if isinstance(mi, list) and isinstance(gi, list):
      try:
        mi2 = [int(x) for x in mi]
        gi2 = [int(x) for x in gi]
      except Exception:
        continue
      if mi2 == gi2:
        try:
          masks.pop(gk, None)
        except Exception as e:
          from runtime.diagnostics import GLOBAL_DIAGS
          GLOBAL_DIAGS.exception(e, domain="PROJECT", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"app/project_manager.py"})
          pass
  p2 = dict(p or {})
  p2 = replace_project_root(p2, "masks", masks)
  return p2
def _ensure_referenced_targets_exist(p: dict) -> None:
  """Create minimal placeholder targets that are referenced by operators.
  Diagnostics can flag missing targets, but a missing target should never
  hard-break preview or autosave. Geometry truth must come from the canonical
  surface model, not raw layout aliases.
  """
  try:
    layers = p.get('layers')
    if not isinstance(layers, list):
      return
    w = 0
    h = 0
    try:
      from app.project_model import get_surface_spec
      spec = get_surface_spec(p)
      if spec is not None and str(getattr(spec, 'kind', '') or '').strip().lower() == 'cells':
        w = int(getattr(spec, 'width', 0) or 0)
        h = int(getattr(spec, 'height', 0) or 0)
    except Exception:
      w = 0
      h = 0
    p2 = dict(p or {})
    groups = dict(p2.get('groups') or {})
    zones = dict(p2.get('zones') or {})
    masks = dict(p2.get('masks') or {})
    def diag_indices():
      if w > 0 and h > 0:
        n = min(w, h)
        return [i * (w + 1) for i in range(n)]
      return []
    def corners_indices():
      if w > 0 and h > 0:
        return [0, w - 1, (h - 1) * w, (h * w) - 1]
      return []
    def zone_top_def():
      if w > 0 and h > 0:
        return {'start': 0, 'end': w - 1, 'indices': []}
      return {'start': 0, 'end': -1, 'indices': []}
    def zone_bottom_def():
      if w > 0 and h > 0:
        return {'start': (h - 1) * w, 'end': (h * w) - 1, 'indices': []}
      return {'start': 0, 'end': -1, 'indices': []}
    # Scan operator references
    for li, L in enumerate(layers):
      ops = L.get('operators') if isinstance(L, dict) else None
      if not isinstance(ops, list):
        continue
      for oi, op in enumerate(ops):
        if not isinstance(op, dict):
          continue
        kind = op.get('target_kind')
        key = op.get('target_key')
        if kind == 'group' and key and key not in groups:
          # Prefer any existing synthetic mask representation
          m = masks.get(f'group:{key}') or masks.get(key)
          idx = m.get('indices') if isinstance(m, dict) else None
          if isinstance(idx, list) and idx:
            groups[key] = {'indices': [int(x) for x in idx]}
          elif key == 'group_diag':
            di = diag_indices()
            groups[key] = {'indices': di} if di else {'indices': []}
          elif key == 'group_corners':
            ci = corners_indices()
            groups[key] = {'indices': ci} if ci else {'indices': []}
          else:
            groups[key] = {'indices': []}
        if kind == 'zone' and key and key not in zones:
          if key == 'zone_top':
            zones[key] = zone_top_def()
          elif key == 'zone_bottom':
            zones[key] = zone_bottom_def()
          else:
            zones[key] = {'start': 0, 'end': -1, 'indices': []}
    # Re-sync after creating any missing entities
    p2 = replace_project_roots(p2, {'groups': groups, 'zones': zones, 'masks': masks})
    p2 = _sync_zones_groups_into_masks(p2)
    p.clear(); p.update(p2)
  except Exception as e:
    _pm_diag_exc(e, "return")
    return
