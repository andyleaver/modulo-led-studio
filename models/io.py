from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from .schema import CURRENT_SCHEMA_VERSION
from .project import Project, Layout, Layer, ModulotorSpec, PixelGroup, Zone
from params.purpose_contract import ensure as ensure_purpose, clamp as clamp_purpose
from app.project_canonical import canonicalize_project_dict

def _normalize_named_dict(obj):
    """Accept either list[dict] or dict[name->dict]. Return list[dict].

    This keeps loader tolerant to schema evolutions where targets are stored as mapping.
    """
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        out = []
        for name, d in obj.items():
            if isinstance(d, dict):
                dd = dict(d)
                dd.setdefault('name', name)
            else:
                # invalid legacy form: keep name only
                dd = {'name': name}
            out.append(dd)
        return out
    return []

def _plainify(obj: Any) -> Any:
    """Recursively convert model/save objects into JSON-safe plain containers."""
    if isinstance(obj, dict):
        return {k: _plainify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plainify(v) for v in obj]
    if isinstance(obj, tuple):
        return [_plainify(v) for v in obj]
    if hasattr(obj, '__dict__') and not isinstance(obj, type):
        return {k: _plainify(v) for k, v in vars(obj).items() if not str(k).startswith('_')}
    return obj

def _strip_private_keys(obj):
    """Recursively remove dict keys that start with '_' (runtime/private cache keys)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            out[k] = _strip_private_keys(v)
        return out
    if isinstance(obj, list):
        return [_strip_private_keys(x) for x in obj]
    return obj

def save_project(path: Path, project: Project) -> None:
    # Authoritative save shape is canonical project dict, not legacy top-level active_layer.
    if hasattr(project, "to_dict"):
        data = project.to_dict()
    else:
        data = asdict(project)
        data.pop("active_layer", None)
        layers = data.get("layers") or []
        if not isinstance(layers, list):
            layers = []
            data["layers"] = layers
        ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
        ui = dict(ui)
        try:
            selected = int(ui.get("selected_layer", -1 if not layers else 0))
        except Exception:
            selected = -1 if not layers else 0
        selected = -1 if not layers else max(0, min(selected, len(layers) - 1))
        ui["selected_layer"] = int(selected)
        data["ui"] = ui
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    data = _strip_private_keys(_plainify(data))
    data, _changes = canonicalize_project_dict(data)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

def _mk_layout(d: dict) -> Layout:
    base = Layout()
    return Layout(**{k: d.get(k, getattr(base, k)) for k in base.__dict__.keys()})

def _mk_mods(mods_d) -> list[ModulotorSpec]:
    mods = []
    for md in (mods_d or []):
        try:
            mods.append(ModulotorSpec(**md))
        except Exception:
            mods.append(ModulotorSpec())
    while len(mods) < 3:
        mods.append(ModulotorSpec())
    return mods[:3]

def _mk_layer(ld: dict, idx: int) -> Layer:
    base = Layer(name=f"Layer {idx+1}")
    # IMPORTANT: enabled must be passed into the Layer dataclass constructor.
    # Older builds set base.enabled but then forgot to include it in the returned Layer(...),
    # causing all loaded projects to have enabled=True regardless of UI toggles.
    base.enabled = bool(ld.get('enabled', True))
    mods = _mk_mods(ld.get("modulotors", []))

    # schema 2: per-layer params dict exists
    params = ld.get("params", None)
    if not isinstance(params, dict):
        params = dict(base.params)
    else:
        params = dict(params)

    # Canonical load path: legacy layer.effect must already have been migrated into layer.behavior
    # before model hydration reaches this point. Do not resurrect layer identity from shadow keys here.
    ensure_purpose(params)
    clamp_purpose(params)

    uid = str(ld.get("uid", ld.get("__uid", ""))) or f"layer_{idx}"
    behavior = str(ld.get("behavior") or base.behavior)

    return Layer(
        uid=uid,
        name=str(ld.get("name", base.name)),
        behavior=behavior,
        enabled=bool(ld.get('enabled', base.enabled)),
        opacity=float(ld.get("opacity", base.opacity)),
        blend_mode=str(ld.get("blend_mode", getattr(base,'blend_mode','over'))),
        # Composition door: layer.order (higher draws later/on top)
        order=int(ld.get("order", getattr(base, 'order', idx))),
        target_kind=str(ld.get("target_kind", getattr(base,'target_kind','all'))),
        target_ref=int(ld.get("target_ref", getattr(base,'target_ref',0))),
        variables=(ld.get('variables') if isinstance(ld.get('variables'), list) else []),
        rules=(ld.get('rules') if isinstance(ld.get('rules'), list) else []),
        operators=(ld.get('operators') if isinstance(ld.get('operators'), list) else []),
        params=params,
        modulotors=mods,
    )

def _mk_group(gd: dict, idx: int = 0) -> PixelGroup:
    """Build a PixelGroup from a dict. Tolerant to schema variants."""
    if not isinstance(gd, dict):
        gd = {}
    name = gd.get("name") or gd.get("id") or f"group_{idx}"
    name = str(name)
    indices = gd.get("indices", [])
    if not isinstance(indices, list):
        indices = []
    cleaned = []
    for x in indices:
        if isinstance(x, bool):
            continue
        if isinstance(x, (int, float)):
            cleaned.append(int(x))
        elif isinstance(x, str) and x.strip().isdigit():
            cleaned.append(int(x.strip()))
    return PixelGroup(name=name, indices=cleaned)

def _mk_zone(zd: dict, idx: int = 0) -> Zone:
    if not isinstance(zd, dict):
        return Zone(name=f"zone_{idx}", start=0, end=-1)
    name = zd.get('name') or zd.get('id') or zd.get('key') or f"zone_{idx}"
    start = int(zd.get('start', 0) or 0)
    end = int(zd.get('end', 0) or 0)
    return Zone(name=name, start=start, end=end)

from .schema_migrations import migrate_to_current

# ---------------- load ----------------

def load_project(path: Path) -> Project:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = migrate_to_current(raw)
    raw, _changes = canonicalize_project_dict(raw)

    # After schema migration + canonicalization, live load must hydrate from the
    # canonical root only. Any surviving raw root "layout" payload is migration
    # residue and must not participate in normal model hydration.
    surface = raw.get("surface") if isinstance(raw.get("surface"), dict) else {}
    layout = _mk_layout(surface)
    layers_d = raw.get("layers", []) or []
    # Startup/authoring contract: allow truly empty projects.
    # Historically we injected a default Layer() when no layers were present.
    # That creates an implicit solid-red layer (Layer.params default color),
    # which masks preview wiring/opacity diagnostics and violates the
    # "start clean" policy.
    layers = [_mk_layer(ld, i) for i, ld in enumerate(layers_d)] if layers_d else []

    groups_d = _normalize_named_dict(raw.get("groups", []))
    groups = [_mk_group(gd, i) for i, gd in enumerate(groups_d)]
    zones_d = _normalize_named_dict(raw.get("zones", []))
    zones = [_mk_zone(zd, i) for i, zd in enumerate(zones_d)]

    ui = raw.get("ui") if isinstance(raw.get("ui"), dict) else {}
    if "selected_layer" in ui:
        try:
            active = int(ui.get("selected_layer", -1))
        except Exception:
            active = -1
    else:
        active = -1 if not layers else 0
    # Canonical model selection uses ui.selected_layer only; legacy active_layer is migration/read-compat.
    if len(layers) == 0:
        active = -1
    else:
        if active < 0:
            active = 0
        elif active >= len(layers):
            active = len(layers) - 1
    rules = raw.get('rules', [])
    if not isinstance(rules, list):
        rules = []
    ui = raw.get('ui') if isinstance(raw.get('ui'), dict) else {}
    ui = dict(ui)
    ui['selected_layer'] = int(-1 if not layers else active)
    audio = raw.get('audio') if isinstance(raw.get('audio'), dict) else {}
    variables = raw.get('variables') if isinstance(raw.get('variables'), dict) else {}
    number = variables.get('number') if isinstance(variables.get('number'), dict) else {}
    toggle = variables.get('toggle') if isinstance(variables.get('toggle'), dict) else {}
    masks = raw.get('masks') if isinstance(raw.get('masks'), dict) else {}
    proj = Project(layers=layers, groups=groups, zones=zones,
                   export_audio=raw.get('export_audio'), preview_audio=raw.get('preview_audio'), postfx=raw.get('postfx'),
                   ui=ui, audio=dict(audio), variables={'number': dict(number), 'toggle': dict(toggle)}, masks=dict(masks),
                   rules=rules)
    proj.surface = layout
    return proj
