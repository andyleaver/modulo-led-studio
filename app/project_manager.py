from __future__ import annotations
from pathlib import Path
import json
from app.eras.era_state import ensure_era_in_project

import uuid
import os

from app.json_sanitize import sanitize_for_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

DEFAULT_PROJECT = {
  'schema_version': 6,
  'name': 'Stress Test Project',
  'time_v1': {
    'mode': 'SIM_FIXED_DT',
    'fixed_dt': 0.0166666667,
    'paused': False,
    'seed': 1,
  },
  'spatial_v1': {
    'enabled': True,
    'world_scale': 1.0,
    'origin': [0.0, 0.0],
    'rotation_deg': 0.0,
    'mirror_x': False,
    'mirror_y': False,
    'use_layout_coords': True,
  },
  'layout': {
    'shape': 'strip',
    'type': 'strip',
    'count': 60,
    'num_leds': 60,
    'led_pin': 6
  },
  'ui': {
    'target_mask': None
  },
  'zones': [],
  'groups': [],
  'masks': {

  },
  'signals': {

  },
  'variables': [],
  'rules_v6': [],
  'layers': [
    {
      'id': 0,
      'uid': 'L0',
      'name': 'Sparkle Base',
      'enabled': True,
      'effect': 'sparkle',
      'behavior': 'sparkle',
      'opacity': 0.4,
      'blend_mode': 'over',
      'blend': 'over',
      'params': {
        'density': 0.35,
        'brightness': 0.85,
        'color': (255, 255, 255)
      },
      'modulotors': [
        {
          'enabled': True,
          'source': 'energy',
          'amount': 0.55,
          'target': 'density',
          'mode': 'add',
          'rate_hz': 0.5,
          'phase': 0.0
        }
      ],
      'operators': [
        {
          'type': 'sparkle',
          'enabled': True,
          'params': {

          }
        }
      ]
    },
    {
      'id': 1,
      'uid': 'L1',
      'name': 'Rainbow',
      'enabled': True,
      'effect': 'rainbow',
      'behavior': 'rainbow',
      'opacity': 0.3,
      'blend_mode': 'over',
      'blend': 'over',
      'params': {
        'speed': 1.1,
        'brightness': 0.9
      },
      'modulotors': [
        {
          'enabled': True,
          'source': 'lfo',
          'amount': 0.35,
          'target': 'speed',
          'mode': 'add',
          'rate_hz': 0.18,
          'phase': 0.25
        }
      ],
      'operators': [
        {
          'type': 'rainbow',
          'enabled': True,
          'params': {

          }
        }
      ]
    },
    {
      'id': 2,
      'uid': 'L2',
      'name': 'Wipe Pulse',
      'enabled': True,
      'effect': 'wipe',
      'behavior': 'wipe',
      'opacity': 0.35,
      'blend_mode': 'add',
      'blend': 'add',
      'params': {
        'speed': 1.2,
        'brightness': 0.9,
        'softness': 0.35,
        'color': (0, 160, 255)
      },
      'modulotors': [
        {
          'enabled': True,
          'source': 'mono3',
          'amount': 0.45,
          'target': 'brightness',
          'mode': 'add',
          'rate_hz': 0.5,
          'phase': 0.0
        }
      ],
      'operators': [
        {
          'type': 'wipe',
          'enabled': True,
          'params': {

          }
        }
      ]
    },
    {
      'id': 3,
      'uid': 'L3',
      'name': 'Lightning',
      'enabled': True,
      'effect': 'lightning',
      'behavior': 'lightning',
      'opacity': 0.45,
      'blend_mode': 'add',
      'blend': 'add',
      'params': {
        'speed': 1.4,
        'brightness': 1.0,
        'density': 0.22,
        'softness': 0.3,
        'color': (255, 255, 255)
      },
      'modulotors': [
        {
          'enabled': True,
          'source': 'energy',
          'amount': 0.35,
          'target': 'density',
          'mode': 'add',
          'rate_hz': 0.5,
          'phase': 0.0
        }
      ],
      'operators': [
        {
          'type': 'lightning',
          'enabled': True,
          'params': {

          }
        }
      ]
    },
    {
      'id': 4,
      'uid': 'L4',
      'name': 'Pulse',
      'enabled': True,
      'effect': 'pulse',
      'behavior': 'pulse',
      'opacity': 0.4,
      'blend_mode': 'add',
      'blend': 'add',
      'params': {
        'speed': 1.0,
        'brightness': 0.9,
        'color': (255, 0, 120)
      },
      'modulotors': [
        {
          'enabled': True,
          'source': 'mono0',
          'amount': 0.55,
          'target': 'brightness',
          'mode': 'add',
          'rate_hz': 0.5,
          'phase': 0.0
        }
      ],
      'operators': [
        {
          'type': 'pulse',
          'enabled': True,
          'params': {

          }
        }
      ]
    }
  ],
  'operators': []
}


def _normalize_layout_keys(p: dict) -> dict:
  try:
    lay = dict((p or {}).get("layout") or {})
    # Back-compat: normalize legacy 'matrix' to canonical 'cells'.
    try:
      if str(lay.get('shape') or '').lower().strip() == 'matrix':
        lay['shape'] = 'cells'
      if str(lay.get('type') or '').lower().strip() == 'matrix':
        lay['type'] = 'cells'
    except Exception:
      pass
    # Infer layout shape if matrix dimensions are present but shape/type is missing or set to strip.
    # Canonical matrix shape in Modulo is 'cells' (Qt UI + preview engine).
    try:
      w = int(lay.get('w') or lay.get('matrix_w') or lay.get('width') or 0)
      h = int(lay.get('h') or lay.get('matrix_h') or lay.get('height') or 0)
      cnt = int(lay.get('count') or lay.get('num_leds') or 0)
      shape = str(lay.get('shape', lay.get('type', '')) or '').lower().strip()
      # Back-compat: accept legacy 'matrix' and normalize to 'cells'.
      if shape == 'matrix':
        shape = 'cells'
      if w > 1 and h > 1 and (cnt == 0 or cnt == w * h):
        if shape in ('', 'strip', 'line'):
          lay['shape'] = 'cells'
          lay['type'] = 'cells'
          lay['matrix_w'] = w
          lay['matrix_h'] = h
          lay['count'] = w * h
          lay['num_leds'] = w * h
    except Exception:
      pass
    # migrate old matrix_* keys to canonical keys used by Qt mapping UI + preview
    if "serpentine" not in lay and "matrix_serpentine" in lay:
      lay["serpentine"] = bool(lay.get("matrix_serpentine"))
    if "flip_x" not in lay and "matrix_flip_x" in lay:
      lay["flip_x"] = bool(lay.get("matrix_flip_x"))
    if "flip_y" not in lay and "matrix_flip_y" in lay:
      lay["flip_y"] = bool(lay.get("matrix_flip_y"))
    if "rotate" not in lay and "matrix_rotate" in lay:
      lay["rotate"] = int(lay.get("matrix_rotate") or 0)
    p2 = dict(p or {})
    p2["layout"] = lay
    return p2
  except Exception:
    return p



def _ensure_layer_uids(p: dict) -> dict:
  try:
    layers = p.get("layers")
    if not isinstance(layers, list):
      return p
    for ld in layers:
      if not isinstance(ld, dict):
        continue
      uid = ld.get("uid") or ld.get("__uid")
      if not isinstance(uid, str) or not uid.strip():
        uid = uuid.uuid4().hex
      ld["uid"] = uid
      ld["__uid"] = uid
    return p
  except Exception:
    return p

def _ensure_ui_defaults(p: dict) -> dict:
  try:
    ui = p.get("ui")
    if not isinstance(ui, dict):
      p["ui"] = {"selected_layer": 0}
      ui = p["ui"]
    if "selected_layer" not in ui:
      ui["selected_layer"] = 0
    # Era system defaults (idempotent)
    try:
      ensure_era_in_project(p)
    except Exception:
      pass
    return p
  except Exception:
    try:
      ensure_era_in_project(p)
    except Exception:
      pass
    return p

def _ensure_masks_dict(p: dict) -> dict:
  try:
    if "masks" in p and not isinstance(p.get("masks"), dict):
      p["masks"] = {}
    return p
  except Exception:
    return p



def _ensure_zones_groups_dict(p: dict) -> dict:
  """Allow old list-style zones/groups and normalize to dict-style used by Qt UI."""
  try:
    # zones
    z = p.get("zones")
    if isinstance(z, list):
      z2 = {}
      for i, item in enumerate(z):
        if isinstance(item, dict):
          name = item.get("name") or item.get("id") or f"zone_{i}"
          d = dict(item)
          d.pop("name", None)
          d.pop("id", None)
          z2[str(name)] = d
      p["zones"] = z2
    # groups
    g = p.get("groups")
    if isinstance(g, list):
      g2 = {}
      for i, item in enumerate(g):
        if isinstance(item, dict):
          name = item.get("name") or item.get("id") or f"group_{i}"
          d = dict(item)
          d.pop("name", None)
          d.pop("id", None)
          g2[str(name)] = d
      p["groups"] = g2
    return p
  except Exception:
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
  except Exception:
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
  groups = p.get("groups") or {}
  if not isinstance(groups, dict):
    groups = {}

  # 1) Remove any prefixed keys living inside masks.
  bad_keys = [k for k in masks.keys() if isinstance(k, str) and (":" in k)]
  for k in bad_keys:
    try:
      masks.pop(k, None)
    except Exception:
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
        except Exception:
          pass

  p["masks"] = masks
  return p



def _ensure_referenced_targets_exist(p: dict) -> None:
  """Create minimal placeholder targets that are referenced by operators.

  Diagnostics can flag missing targets, but a missing target should never
  hard-break preview or autosave. For demo...
  """
  try:
    layers = p.get('layers')
    if not isinstance(layers, list):
      return
    layout = p.get('layout') if isinstance(p.get('layout'), dict) else {}
    w = int(layout.get('matrix_w') or 0)
    h = int(layout.get('matrix_h') or 0)

    groups = p.setdefault('groups', {})
    zones = p.setdefault('zones', {})
    masks = p.setdefault('masks', {})

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
    _sync_zones_groups_into_masks(p)
  except Exception:
    return



def _ensure_layer_modulotors_normalized(p: dict) -> None:
  """Normalize layer modulotors storage to a single canonical field.

  Canonical: layer['modulotors'] as a list[dict]
  Legacy: layer['params']['_mods'] (kept, but mirrored into modulotors)

  This enforces the no-closed-doors promise: modulation authored in UI must be
  consumed by preview, audit, diagnostics, and export consistently.
  """
  layers = p.get("layers")
  if not isinstance(layers, list):
    return
  for ld in layers:
    if not isinstance(ld, dict):
      continue
    # Gather legacy mods
    legacy_mods = None
    params = ld.get("params")
    if isinstance(params, dict):
      lm = params.get("_mods")
      if isinstance(lm, list):
        legacy_mods = lm
    # Canonical mods
    mods = ld.get("modulotors")
    if isinstance(mods, list):
      # ensure list of dicts
      ld["modulotors"] = [m for m in mods if isinstance(m, dict)]
    elif legacy_mods is not None:
      ld["modulotors"] = [m for m in legacy_mods if isinstance(m, dict)]
    else:
      # ensure field exists for consistent consumers
      ld.setdefault("modulotors", [])


def _ensure_layer_effect_behavior_operator_defaults(p: dict) -> None:
  """Back-compat: older projects store per-layer effect as `effect` with params at layer level.

  Newer runtime expects:
    - layer['behavior'] to be present
    - layer['operators'] list with at least one operator dict
  We migrate conservatively without deleting user data.
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
      if (behavior is None or str(behavior).strip() == "") and isinstance(effect, str) and effect.strip():
        ld["behavior"] = effect.strip()

      # Ensure operators exist
      ops = ld.get("operators")
      if not isinstance(ops, list) or len(ops) == 0:
        b = ld.get("behavior") or effect or "solid"
        op = {
          "type": b,
          "enabled": True,
          "params": ld.get("params") if isinstance(ld.get("params"), dict) else {},
        }
        ld["operators"] = [op]
      else:
        # If first operator type is missing/blank, set from behavior/effect
        op0 = ops[0] if len(ops) > 0 and isinstance(ops[0], dict) else None
        if op0 is not None and (op0.get("type") in (None, "")):
          b = ld.get("behavior") or effect or "solid"
          op0["type"] = b
          ops[0] = op0
          ld["operators"] = ops

      layers[i] = ld
    p["layers"] = layers
  except Exception:
    return


def migrate_project_dict(p: dict) -> dict:
  """Best-effort migration for loaded project dicts.

  Conservative: never deletes data; only normalizes missing structural defaults.
  """
  if not isinstance(p, dict):
    return json.loads(json.dumps(DEFAULT_PROJECT))
  p2 = _normalize_layout_keys(p)
  _ensure_ui_defaults(p2)
  _ensure_masks_dict(p2)
  _ensure_zones_groups_dict(p2)
  _sync_zones_groups_into_masks(p2)
  _ensure_referenced_targets_exist(p2)
  _ensure_demo_gain_targets(p2)

  _ensure_layer_effect_behavior_operator_defaults(p2)
  _ensure_layer_uids(p2)
  _ensure_layer_modulotors_normalized(p2)
  return p2


def _ensure_demo_gain_targets(p: dict) -> None:
  """Wire missing gain operator targets in the built-in demo project.

  The demo is intended to showcase targeting (masks/zones/groups) out of the box.
  If a user has an older autosave of the demo with missing target_kind/target_key
  on its gain operators, we restore those defaults deterministically.

  This is intentionally *very* narrow in scope to avoid mutating user projects.
  """
  name = (p.get("name") or "")
  # The built-in demo has historically used different names across builds.
  # Keep this check very narrow, but accept the known canonical demo name.
  if not (name.startswith("Demo:") or name == "Complex Matrix Diagnostics Demo"):
    return

  layers = p.get("layers")
  if not isinstance(layers, list) or len(layers) < 1:
    return

  # Demo convention: L0 is Sparkle with 2 gain operators in slots 1 and 2.
  l0 = layers[0]
  if not isinstance(l0, dict):
    return
  ops = l0.get("operators")
  if not isinstance(ops, list) or len(ops) < 3:
    return

  # Only apply if both targets are missing; otherwise assume the user edited them.
  def _missing_target(op: dict) -> bool:
    return (op.get("target_kind") in (None, "") and op.get("target_key") in (None, ""))

  op1 = ops[1] if isinstance(ops[1], dict) else None
  op2 = ops[2] if isinstance(ops[2], dict) else None
  if not op1 or not op2:
    return
  if op1.get("type") != "gain" or op2.get("type") != "gain":
    return
  if not (_missing_target(op1) and _missing_target(op2)):
    return

  masks = p.get("masks")
  zones = p.get("zones")
  if not isinstance(masks, dict) or not isinstance(zones, dict):
    return
  if "mask_center" not in masks or "zone_top" not in zones:
    return

  op1["target_kind"] = "mask"
  op1["target_key"] = "mask_center"
  op2["target_kind"] = "zone"
  op2["target_key"] = "zone_top"

class ProjectManager:
    def __init__(self):
        # Start from defaults. (Autosave/restore is hard-disabled for release stability.)
        self.project: dict = json.loads(json.dumps(DEFAULT_PROJECT))

        loaded = False

        # First-run UX: start with a deterministic demo that exercises state + rules.
        # (Avoid loading legacy Mario showcase projects by default.)
        if not loaded:
            try:
                from app.showcases.red_hat_runner import build_red_hat_runner_project
                self.project = migrate_project_dict(build_red_hat_runner_project())
            except Exception:
                # If the demo can't be built for any reason, fall back to DEFAULT_PROJECT.
                pass

        self.path: Path | None = None
        self.dirty: bool = False
        self._listeners = []  # callables(pm)
        self.root_dir = str(ROOT)

    def add_listener(self, fn):
        try:
            self._listeners.append(fn)
        except Exception:
            pass

    def _notify(self):
        for fn in list(self._listeners):
            try:
                fn(self)
            except Exception:
                pass

    def get(self) -> dict:
        return self.project

    def set(self, p: dict):
        self.project = migrate_project_dict(p)
        self.dirty = True
        self._notify()

    def mark_clean(self):
        self.dirty = False
        self._notify()

    def display_path(self) -> str:
        return str(self.path) if self.path else "(not saved yet)"

    
    def _apply_export_defaults_from_target(self):
        """Normalize default export config to match selected target pack defaults.

        This keeps the default project export-truthful even as targets/capabilities evolve.
        """
        try:
            from export.targets.registry import resolve_target_meta, resolve_requested_backends, resolve_requested_hw, resolve_requested_audio_hw
            project = self.project or {}
            export_cfg = (project.get("export") or {})
            tid = export_cfg.get("target_id") or export_cfg.get("target") or "arduino_uno_fastled_msgeq7"
            target_meta = resolve_target_meta(str(tid))
            # backends
            sel = resolve_requested_backends(project, target_meta)
            export_cfg["target_id"] = str(target_meta.get("id") or tid)
            export_cfg["led_backend"] = sel.get("led_backend")
            export_cfg["audio_backend"] = sel.get("audio_backend")
            # hw
            export_cfg["hw"] = resolve_requested_hw(project, target_meta)
            export_cfg["audio_hw"] = resolve_requested_audio_hw(project, target_meta)
            project["export"] = export_cfg
            self.project = project
        except Exception:
            pass


    def new(self):
        self._apply_export_defaults_from_target()
        self.path = None
        self.dirty = True
        self._notify()

    def load(self, path: Path):
        self.project = migrate_project_dict(json.loads(path.read_text(encoding="utf-8")))
        self.path = path
        self.dirty = False
        self._notify()

    def save(self, path: Path | None = None):
        if path is not None:
            self.path = path
        if self.path is None:
            self.path = OUT / "project.json"
        clean, _issues = sanitize_for_json(self.project)
        self.path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
        # Keep in-memory project as migrated/original; the written file is guaranteed JSON-safe.
        self.dirty = False
        self._notify()
        return self.path

    # ---- convenience loaders (fixtures & demos) ----
    def load_project_dict(self, d: dict):
        """Replace current project with provided dict."""
        if not isinstance(d, dict):
            return
        self.project = migrate_project_dict(d)
        self.dirty = True
        self._notify()

    def load_fixture(self, filename: str):
        """Load a fixture project JSON from fixtures/projects/<filename>."""
        try:
            from models.io import load_project
            path = ROOT / "fixtures" / "projects" / filename
            proj = load_project(path)
            self.project = proj.to_dict()
            self.dirty = True
            self._notify()
        except Exception:
            # keep current project on failure
            return

    def apply_audio_preset(self, preset_filename: str):
        """Load fixtures/audio_presets/<preset_filename> and apply its audio_routes."""
        try:
            preset_path = ROOT / "fixtures" / "audio_presets" / preset_filename
            data = json.loads(preset_path.read_text(encoding="utf-8"))
            routes = data.get("audio_routes") or []
            if not isinstance(self.project, dict):
                return
            self.project["audio_routes"] = routes
            self.project["audio_preset_name"] = data.get("name", preset_filename)
            self.dirty = True
            self._notify()
        except Exception:
            return


# ---- guarded layer helpers (single source of truth) ----
def is_layer_locked(self, idx: int) -> bool:
    try:
        layers = (self.project.get("layers") or [])
        if 0 <= idx < len(layers):
            return bool((layers[idx] or {}).get("locked", False))
    except Exception:
        pass
    return False

def guarded_update_layer(self, idx: int, updater, *, reason: str = "modify"):
    """Apply updater(layer_dict) if layer is not locked. Returns True if applied."""
    try:
        if self.is_layer_locked(idx):
            return False
        layers = (self.project.get("layers") or [])
        if not (0 <= idx < len(layers)):
            return False
        layer = layers[idx] or {}
        updater(layer)
        layers[idx] = layer
        self.project["layers"] = layers
        self.dirty = True
        self._notify()
        return True
    except Exception:
        return False

def guarded_set_layer_param(self, idx: int, name: str, value) -> bool:
    def _u(layer):
        params = dict(layer.get("params") or {})
        params[name] = value
        layer["params"] = params
    return self.guarded_update_layer(idx, _u, reason="set_param")

def guarded_set_layer_effect(self, idx: int, effect_key: str, params: dict | None = None) -> bool:
    def _u(layer):
        # Canonical schema key is 'behavior'. Keep 'effect' as a legacy alias for any
        # remaining UI code paths, but Preview/Export only read 'behavior'.
        layer["behavior"] = effect_key
        layer["effect"] = effect_key
        if params is not None:
            layer["params"] = dict(params)
    return self.guarded_update_layer(idx, _u, reason="set_effect")

def guarded_toggle_layer_enabled(self, idx: int) -> bool:
    def _u(layer):
        layer["enabled"] = not bool(layer.get("enabled", True))
    return self.guarded_update_layer(idx, _u, reason="toggle_enabled")


def guarded_remove_layer(self, idx: int) -> bool:
    try:
        if self.is_layer_locked(idx):
            return False
        layers = (self.project.get("layers") or [])
        if not (0 <= idx < len(layers)):
            return False
        layers.pop(idx)
        self.project["layers"] = layers
        # clear selection if it pointed past end
        sel = self.project.get("ui", {}).get("selected_layer", None)
        try:
            if sel is not None and int(sel) >= len(layers):
                self.project.setdefault("ui", {})["selected_layer"] = max(0, len(layers)-1) if layers else None
        except Exception:
            pass
        self.dirty = True
        self._notify()
        return True
    except Exception:
        return False

def guarded_move_layer(self, idx: int, delta: int) -> bool:
    try:
        if self.is_layer_locked(idx):
            return False
        layers = (self.project.get("layers") or [])
        j = idx + int(delta)
        if not (0 <= idx < len(layers)) or not (0 <= j < len(layers)):
            return False
        layers[idx], layers[j] = layers[j], layers[idx]
        self.project["layers"] = layers
        self.dirty = True
        self._notify()
        return True
    except Exception:
        return False

def guarded_add_layer(self, layer_dict: dict, *, idx: int | None = None) -> bool:
    """Insert new layer. If idx is provided, insertion happens at idx; if that slot is locked, returns False."""
    try:
        layers = (self.project.get("layers") or [])
        if idx is None:
            layers.append(dict(layer_dict))
        else:
            if 0 <= idx < len(layers) and self.is_layer_locked(idx):
                return False
            if idx < 0:
                idx = 0
            if idx > len(layers):
                idx = len(layers)
            layers.insert(idx, dict(layer_dict))
        self.project["layers"] = layers
        self.dirty = True
        self._notify()
        return True
    except Exception:
        return False

def guarded_fix_visible(self, idx: int, visible_mask: list[bool]) -> bool:
    def _u(layer):
        layer["visible"] = list(bool(x) for x in visible_mask)
    return self.guarded_update_layer(idx, _u, reason="fix_visible")


# Bind guarded helpers onto ProjectManager (keeps UI code simple and consistent)
ProjectManager.is_layer_locked = is_layer_locked
ProjectManager.guarded_update_layer = guarded_update_layer
ProjectManager.guarded_set_layer_param = guarded_set_layer_param
ProjectManager.guarded_set_layer_effect = guarded_set_layer_effect
ProjectManager.guarded_toggle_layer_enabled = guarded_toggle_layer_enabled
ProjectManager.guarded_remove_layer = guarded_remove_layer
ProjectManager.guarded_move_layer = guarded_move_layer
ProjectManager.guarded_add_layer = guarded_add_layer
ProjectManager.guarded_fix_visible = guarded_fix_visible
