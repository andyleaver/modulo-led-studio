from __future__ import annotations

from app.project_apply import apply_project_root, replace_project_root
import uuid
from app.eras.era_state import ensure_era_in_project
from app.project_manager_diagnostics import project_manager_diag_exc
_pm_diag_exc = project_manager_diag_exc
def _ensure_layer_uids(p: dict) -> dict:
  try:
    layers = p.get("layers")
    if not isinstance(layers, list):
      return p
    for i, ld in enumerate(layers):
      if not isinstance(ld, dict):
        continue
      uid = ld.get("uid") or ld.get("__uid")
      if not isinstance(uid, str) or not uid.strip():
        uid = uuid.uuid4().hex
      ld["uid"] = uid
      ld["__uid"] = uid
    return p
  except Exception as e:
    _pm_diag_exc(e, "return")
    return p
def _ensure_ui_defaults(p: dict) -> dict:
  try:
    p2 = dict(p or {})
    ui = p2.get("ui")
    if not isinstance(ui, dict):
      p2 = replace_project_root(p2, "ui", {})
      ui = p2["ui"]
    layers = p.get("layers")
    if not isinstance(layers, list):
      layers = []
    sel = ui.get("selected_layer", None)
    try:
      sel = int(sel) if sel is not None else (-1 if not layers else 0)
    except Exception:
      sel = -1 if not layers else 0
    if layers:
      sel = max(0, min(sel, len(layers) - 1))
    else:
      sel = -1
    ui["selected_layer"] = int(sel)
    # Era system defaults (idempotent)
    try:
      ensure_era_in_project(p2)
    except Exception as e:
      from runtime.diagnostics import GLOBAL_DIAGS
      GLOBAL_DIAGS.exception(e, domain="PROJECT", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"app/project_manager.py"})
      pass
    return p2
  except Exception:
    p2 = dict(p or {})
    try:
      ensure_era_in_project(p2)
    except Exception as e:
      from runtime.diagnostics import GLOBAL_DIAGS
      GLOBAL_DIAGS.exception(e, domain="PROJECT", code="SWALLOWED_EXCEPTION", summary="swallowed exception", details={"file":"app/project_manager.py"})
      pass
    return p2
def _ensure_layer_modulotors_normalized(p: dict) -> None:
  """Normalize layer modulotors storage to a single canonical field.
  Canonical: layer['modulotors'] as a list[dict]
  Legacy: layer['params']['_mods'] is migration-only and is removed here.
  This enforces the no-closed-doors promise: modulation authored in UI must be
  consumed by preview, audit, diagnostics, and export consistently.
  """
  layers = p.get("layers")
  if not isinstance(layers, list):
    return
  for ld in layers:
    if not isinstance(ld, dict):
      continue
    legacy_mods = None
    params = ld.get("params")
    if isinstance(params, dict):
      lm = params.get("_mods")
      if isinstance(lm, list):
        legacy_mods = lm
    mods = ld.get("modulotors")
    if isinstance(mods, list):
      ld["modulotors"] = [m for m in mods if isinstance(m, dict)]
    elif legacy_mods is not None:
      ld["modulotors"] = [m for m in legacy_mods if isinstance(m, dict)]
    else:
      ld.setdefault("modulotors", [])
    if isinstance(params, dict) and "_mods" in params:
      params2 = dict(params)
      params2.pop("_mods", None)
      ld["params"] = params2
def _canonicalize_legacy_layer_composition_keys(p: dict) -> None:
  """Canonicalize and remove legacy layer composition keys.
  Canonical layer composition fields:
    - layer['opacity'] (0..1 float)
    - layer['enabled'] (bool)
    - layer['blend_mode'] (str)
    - layer['order'] (int)
  Legacy sources migrated (then removed):
    - layer['blend'] shadow key
    - layer['params']['layer_opacity'|'layer_enabled'|'layer_blend_mode'|'layer_order']
    - flattened keys injected onto the layer dict like 'params.layer_opacity'
  """
  try:
    layers = p.get("layers")
    if not isinstance(layers, list):
      return
    for i, ld in enumerate(layers):
      if not isinstance(ld, dict):
        continue
      # blend -> blend_mode (shadow key)
      if "blend" in ld and "blend_mode" not in ld:
        try:
          ld["blend_mode"] = ld.get("blend")
        except Exception:
          pass
      if "blend" in ld:
        try:
          del ld["blend"]
        except Exception:
          pass
      params = ld.get("params")
      if not isinstance(params, dict):
        params = None
      # Migrate from legacy params.* keys
      def _take_param(key: str):
        if params is not None and key in params:
          v = params.get(key)
          try:
            del params[key]
          except Exception:
            pass
          return v
        return None
      # Migrate from flattened keys on layer dict
      def _take_flat(key: str):
        if key in ld:
          v = ld.get(key)
          try:
            del ld[key]
          except Exception:
            pass
          return v
        return None
      # opacity
      if "opacity" not in ld:
        v = _take_param("layer_opacity")
        if v is None:
          v = _take_flat("params.layer_opacity")
        if v is not None:
          try:
            f = float(v)
            if f < 0.0: f = 0.0
            if f > 1.0: f = 1.0
            ld["opacity"] = f
          except Exception:
            pass
      else:
        # still remove legacy duplicates if present
        _take_param("layer_opacity")
        _take_flat("params.layer_opacity")
      # enabled
      if "enabled" not in ld:
        v = _take_param("layer_enabled")
        if v is None:
          v = _take_flat("params.layer_enabled")
        if v is not None:
          try:
            ld["enabled"] = bool(int(v)) if isinstance(v, (int, float, str)) else bool(v)
          except Exception:
            ld["enabled"] = bool(v)
      else:
        _take_param("layer_enabled")
        _take_flat("params.layer_enabled")
      # blend_mode
      if "blend_mode" not in ld:
        v = _take_param("layer_blend_mode")
        if v is None:
          v = _take_flat("params.layer_blend_mode")
        if v is not None:
          try:
            ld["blend_mode"] = str(v)
          except Exception:
            pass
      else:
        _take_param("layer_blend_mode")
        _take_flat("params.layer_blend_mode")
      # order
      if "order" not in ld:
        v = _take_param("layer_order")
        if v is None:
          v = _take_flat("params.layer_order")
        if v is not None:
          try:
            ld["order"] = int(v)
          except Exception:
            pass
      else:
        _take_param("layer_order")
        _take_flat("params.layer_order")
      # Enforce canonical composition fields on every layer so downstream readers
      # never need to guess or fall back to shadow locations.
      try:
        if "opacity" not in ld:
          ld["opacity"] = 1.0
        else:
          f = float(ld.get("opacity", 1.0))
          if f < 0.0: f = 0.0
          if f > 1.0: f = 1.0
          ld["opacity"] = f
      except Exception:
        ld["opacity"] = 1.0
      if "enabled" not in ld:
        ld["enabled"] = True
      else:
        try:
          ld["enabled"] = bool(int(ld.get("enabled"))) if isinstance(ld.get("enabled"), (int, float, str)) else bool(ld.get("enabled"))
        except Exception:
          ld["enabled"] = bool(ld.get("enabled"))
      try:
        bm = str(ld.get("blend_mode") or "over").strip().lower()
      except Exception:
        bm = "over"
      if bm == "normal":
        bm = "over"
      if bm not in ("over", "add", "max", "multiply", "screen"):
        bm = "over"
      ld["blend_mode"] = bm
      try:
        ld["order"] = int(ld.get("order", i) if ld.get("order", None) is not None else i)
      except Exception:
        ld["order"] = i
      # If params dict is now empty, keep it (do not delete) to avoid breaking code that assumes dict.
      if params is not None:
        ld["params"] = params
  except Exception:
    return
def _assert_no_legacy_layer_composition_keys(p: dict) -> None:
  """Ensure legacy layer composition keys do not survive normalization.
  This is a hard safety rail to prevent SPLIT behavior (preview/export/UI disagreement).
  Legacy keys must be migrated + removed by `_canonicalize_legacy_layer_composition_keys`.
  """
  try:
    layers = p.get("layers")
    if not isinstance(layers, list):
      return
    bad = []
    for i, ld in enumerate(layers):
      if not isinstance(ld, dict):
        continue
      # shadow key
      if "blend" in ld:
        bad.append((i, "blend"))
        try: del ld["blend"]
        except Exception: pass
      # flattened injected keys
      for k in list(ld.keys()):
        if isinstance(k, str) and k.startswith("params.layer_"):
          bad.append((i, k))
          try: del ld[k]
          except Exception: pass
      params = ld.get("params")
      if isinstance(params, dict):
        for k in ("layer_opacity","layer_enabled","layer_blend_mode","layer_order"):
          if k in params:
            bad.append((i, f"params.{k}"))
            try: del params[k]
            except Exception: pass
        ld["params"] = params
    if bad:
      try:
        from runtime.diagnostics import GLOBAL_DIAGS
        GLOBAL_DIAGS.warn(
          domain="PROJECT",
          code="LEGACY_LAYER_KEYS_SURVIVED_NORMALIZE",
          summary="Legacy layer composition keys survived normalization and were removed",
          details={"count": len(bad), "keys": bad[:50]},
        )
      except Exception:
        pass
  except Exception:
    return
def _ensure_layer_effect_behavior_operator_defaults(p: dict) -> None:
  """Back-compat: collapse any legacy per-layer effect shadow into canonical behavior.
  Runtime identity must live on layer['behavior'] only; layer['effect'] is removed.
  Also ensures operators exist with a canonical first operator type.
  """
  try:
    layers = p.get("layers")
    if not isinstance(layers, list):
      return
    for i, ld in enumerate(layers):
      if not isinstance(ld, dict):
        continue
      effect = ld.get("effect")
      behavior = ld.get("behavior")
      if (behavior is None or str(behavior).strip() == ""):
        if isinstance(effect, str) and effect.strip():
          ld["behavior"] = effect.strip()
        elif isinstance(effect, dict):
          eff_id = str(effect.get("id") or effect.get("key") or "").strip()
          if eff_id:
            ld["behavior"] = eff_id
          eff_params = effect.get("params")
          if isinstance(eff_params, dict):
            merged = dict(eff_params)
            merged.update(ld.get("params") if isinstance(ld.get("params"), dict) else {})
            ld["params"] = merged
      ld.pop("effect", None)
      behavior_id = str(ld.get("behavior") or "solid").strip() or "solid"
      # Ensure operators exist from canonical behavior only.
      ops = ld.get("operators")
      if not isinstance(ops, list) or len(ops) == 0:
        op = {
          "type": behavior_id,
          "enabled": True,
          "params": ld.get("params") if isinstance(ld.get("params"), dict) else {},
        }
        ld["operators"] = [op]
      else:
        # If first operator type is missing/blank, set it from canonical behavior only.
        op0 = ops[0] if len(ops) > 0 and isinstance(ops[0], dict) else None
        if op0 is not None and (op0.get("type") in (None, "")):
          op0["type"] = behavior_id
          ops[0] = op0
          ld["operators"] = ops
      layers[i] = ld
    p["layers"] = layers
  except Exception as e:
    _pm_diag_exc(e, "return")
    return
