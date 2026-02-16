from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from .schema import CURRENT_SCHEMA_VERSION
from .project import Project, Layout, Layer, ModulotorSpec, PixelGroup, Zone
from params.purpose_contract import ensure as ensure_purpose, clamp as clamp_purpose

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
                # legacy/invalid: keep name only
                dd = {'name': name}
            out.append(dd)
        return out
    return []

def save_project(path: Path, project: Project) -> None:
    data = asdict(project)
    data["schema_version"] = CURRENT_SCHEMA_VERSION
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
    base.enabled = bool(ld.get('enabled', True))
    mods = _mk_mods(ld.get("modulotors", []))

    # schema v2: per-layer params dict exists
    params = ld.get("params", None)
    if not isinstance(params, dict):
        params = dict(base.params)

    ensure_purpose(params)
    clamp_purpose(params)

    return Layer(
        uid=str(ld.get("uid", ld.get("__uid", ""))) or "",
        name=str(ld.get("name", base.name)),
        behavior=str(ld.get("behavior", base.behavior)),
        opacity=float(ld.get("opacity", base.opacity)),
        blend_mode=str(ld.get("blend_mode", getattr(base,'blend_mode','over'))),
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


# ---------------- schema migrations ----------------

def _migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """v1 -> v2 migration:
    - Layers may have 'color', 'brightness', 'speed', etc at top-level (older builds).
    - v2 stores these under layer['params'] dict.
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for i, ld in enumerate(layers):
        if not isinstance(ld, dict):
            continue
        params = ld.get("params")
        if not isinstance(params, dict):
            params = {}
        # lift known keys into params if present
        for k in ("color","brightness","speed","width","softness","direction","density"):
            if k in ld and k not in params:
                params[k] = ld.get(k)
        # ensure required keys exist (defaults handled later)
        ld2 = dict(ld)
        ld2.pop("color", None)
        ld2.pop("brightness", None)
        ld2.pop("speed", None)
        ld2.pop("width", None)
        ld2.pop("softness", None)
        ld2.pop("direction", None)
        ld2.pop("density", None)
        ld2["params"] = params
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 2
    return data2

def _migrate_v2_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
    """v2 -> v3 migration:
    - adds layer['blend_mode'] with default 'over' if missing
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for ld in layers:
        if not isinstance(ld, dict):
            continue
        ld2 = dict(ld)
        if "blend_mode" not in ld2:
            ld2["blend_mode"] = "over"
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 3
    return data2

def _migrate_v3_to_v4(data: Dict[str, Any]) -> Dict[str, Any]:
    """v3 -> v4 migration:
    - adds top-level groups/zones arrays if missing
    """
    data2 = dict(data)
    if "groups" not in data2 or not isinstance(data2.get("groups"), list):
        data2["groups"] = []
    if "zones" not in data2 or not isinstance(data2.get("zones"), list):
        data2["zones"] = []
    data2["schema_version"] = 4
    return data2

def _migrate_v4_to_v5(data: Dict[str, Any]) -> Dict[str, Any]:
    """v4 -> v5 migration:
    - adds per-layer target_kind/target_ref (default all/0)
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for ld in layers:
        if not isinstance(ld, dict):
            continue
        ld2 = dict(ld)
        if "target_kind" not in ld2:
            ld2["target_kind"] = "all"
        if "target_ref" not in ld2:
            ld2["target_ref"] = 0
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 5
    return data2

def _migrate_v5_to_v6(data: Dict[str, Any]) -> Dict[str, Any]:
    """v5 -> v6 migration:
    - ensures per-modulotor 'bias' exists (default 0.0)
    """
    layers = data.get("layers", []) or []
    new_layers = []
    for ld in layers:
        if not isinstance(ld, dict):
            continue
        ld2 = dict(ld)
        mods = ld2.get("modulotors", []) or []
        new_mods = []
        for md in mods:
            if not isinstance(md, dict):
                new_mods.append(md)
                continue
            md2 = dict(md)
            if "bias" not in md2:
                md2["bias"] = 0.0
            new_mods.append(md2)
        ld2["modulotors"] = new_mods
        new_layers.append(ld2)
    data2 = dict(data)
    data2["layers"] = new_layers
    data2["schema_version"] = 6
    return data2

def _migrate_v6_to_v7(data: Dict[str, Any]) -> Dict[str, Any]:
    """v6 -> v7 migration:
    - add matrix mapping defaults to layout (serpentine/flip/rotate)
    """
    d = dict(data)
    layout = dict(d.get("layout", {}) or {})
    layout.setdefault("matrix_serpentine", False)
    layout.setdefault("matrix_flip_x", False)
    layout.setdefault("matrix_flip_y", False)
    layout.setdefault("matrix_rotate", 0)
    d["layout"] = layout
    d["schema_version"] = 7
    return d

def _migrate_v7_to_v8(data: Dict[str, Any]) -> Dict[str, Any]:
    """v7 -> v8 migration:
    - add layer.enabled default True
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    for L in layers:
        if isinstance(L, dict):
            L.setdefault("enabled", True)
    d["layers"] = layers
    d["schema_version"] = 8
    return d

def _migrate_v8_to_v9(data: Dict[str, Any]) -> Dict[str, Any]:
    """v8 -> v9 migration:
    - add modulotor.enabled default True (per layer)
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    for L in layers:
        if isinstance(L, dict):
            mods = list(L.get("modulotors", []) or [])
            for m in mods:
                if isinstance(m, dict):
                    m.setdefault("enabled", True)
            L["modulotors"] = mods
    d["layers"] = layers
    d["schema_version"] = 9
    return d

def _migrate_v9_to_v10(data: Dict[str, Any]) -> Dict[str, Any]:
    """v9 -> v10 migration:
    - modulotor.curve default 'linear'
    - modulotor.kind default 'audio'
    - for kind='lfo': add freq default 1.0, phase default 0.0
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    for L in layers:
        if isinstance(L, dict):
            mods = list(L.get("modulotors", []) or [])
            for m in mods:
                if isinstance(m, dict):
                    m.setdefault("curve", "linear")
                    m.setdefault("kind", "audio")
                    m.setdefault("freq", 1.0)
                    m.setdefault("phase", 0.0)
            L["modulotors"] = mods
    d["layers"] = layers
    d["schema_version"] = 10
    return d

def _migrate_v10_to_v11(data: Dict[str, Any]) -> Dict[str, Any]:
    """v10 -> v11 migration:
    - add export_audio config with safe defaults
    """
    d = dict(data)
    d.setdefault("export_audio", {
        "use_spectrum_shield": True,
        "reset_pin": 5,
        "strobe_pin": 4,
        "left_pin": "A0",
        "right_pin": "A1",
    })
    d["schema_version"] = 11
    return d

def _migrate_v11_to_v12(data: Dict[str, Any]) -> Dict[str, Any]:
    """v11 -> v12 migration:
    - add preview_audio config with safe defaults
    """
    d = dict(data)
    d.setdefault("preview_audio", {
        "mode": "sim",
        "port": "",
        "baud": 115200,
        "gain": 1.0,
        "smoothing": 0.20,
        "meter": "mono",
    })
    d["schema_version"] = 12
    return d

def _migrate_v12_to_v13(data: Dict[str, Any]) -> Dict[str, Any]:
    """v12 -> v13 migration:
    - add preview_audio.autoconnect default False
    """
    d = dict(data)
    pa = dict(d.get("preview_audio") or {})
    pa.setdefault("autoconnect", False)
    d["preview_audio"] = pa
    d["schema_version"] = 13
    return d


def _migrate_v13_to_v14(data: Dict[str, Any]) -> Dict[str, Any]:
    """v13 -> v14 migration:
    - add postfx config with safe defaults (disabled)
    - ensure export_audio and preview_audio exist (defensive for older files)
    """
    d = dict(data)
    d.setdefault("export_audio", {
        "use_spectrum_shield": True,
        "reset_pin": 5,
        "strobe_pin": 4,
        "left_pin": "A0",
        "right_pin": "A1",
    })
    d.setdefault("preview_audio", {
        "mode": "sim",
        "port": "",
        "baud": 115200,
        "gain": 1.0,
        "smoothing": 0.20,
        "meter": "mono",
        "autoconnect": False,
    })
    d.setdefault("postfx", {
        "bleed_amount": 0.0,
        "bleed_radius": 1,
        "trail_amount": 0.0,
    })
    d["schema_version"] = 14
    return d


def _migrate_v14_to_v15(data: Dict[str, Any]) -> Dict[str, Any]:
    """v14 -> v15 migration:
    - add per-layer variables and rules arrays (default empty)
    """
    d = dict(data)
    layers = list(d.get("layers", []) or [])
    new_layers = []
    for L in layers:
        if not isinstance(L, dict):
            continue
        L2 = dict(L)
        if "variables" not in L2 or not isinstance(L2.get("variables"), list):
            L2["variables"] = []
        if "rules" not in L2 or not isinstance(L2.get("rules"), list):
            L2["rules"] = []
        new_layers.append(L2)
    d["layers"] = new_layers
    d["schema_version"] = 15
    return d

def migrate_to_current(data: Dict[str, Any]) -> Dict[str, Any]:
    v = int(data.get("schema_version", 1))
    # Chain migrations in order
    if v == 1 and CURRENT_SCHEMA_VERSION >= 2:
        data = _migrate_v1_to_v2(data)
        v = 2
    if v == 2 and CURRENT_SCHEMA_VERSION >= 3:
        data = _migrate_v2_to_v3(data)
        v = 3
    if v == 3 and CURRENT_SCHEMA_VERSION >= 4:
        data = _migrate_v3_to_v4(data)
        v = 4
    if v == 4 and CURRENT_SCHEMA_VERSION >= 5:
        data = _migrate_v4_to_v5(data)
        v = 5
    if v == 5 and CURRENT_SCHEMA_VERSION >= 6:
        data = _migrate_v5_to_v6(data)
        v = 6
    if v == 6 and CURRENT_SCHEMA_VERSION >= 7:
        data = _migrate_v6_to_v7(data)
        v = 7
    if v == 7 and CURRENT_SCHEMA_VERSION >= 8:
        data = _migrate_v7_to_v8(data)
        v = 8
    if v == 8 and CURRENT_SCHEMA_VERSION >= 9:
        data = _migrate_v8_to_v9(data)
        v = 9
    if v == 9 and CURRENT_SCHEMA_VERSION >= 10:
        data = _migrate_v9_to_v10(data)
        v = 10
    if v == 10 and CURRENT_SCHEMA_VERSION >= 11:
        data = _migrate_v10_to_v11(data)
        v = 11
    if v == 11 and CURRENT_SCHEMA_VERSION >= 12:
        data = _migrate_v11_to_v12(data)
        v = 12
    if v == 12 and CURRENT_SCHEMA_VERSION >= 13:
        data = _migrate_v12_to_v13(data)
        v = 13
    if v == 13 and CURRENT_SCHEMA_VERSION >= 14:
        data = _migrate_v13_to_v14(data)
        v = 14
    if v == 14 and CURRENT_SCHEMA_VERSION >= 15:
        data = _migrate_v14_to_v15(data)
        v = 15
    # If unknown newer version, we still try to load best-effort
    return data

# ---------------- load ----------------

def load_project(path: Path) -> Project:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = migrate_to_current(raw)

    layout = _mk_layout(raw.get("layout", {}))
    layers_d = raw.get("layers", []) or []
    layers = [_mk_layer(ld, i) for i, ld in enumerate(layers_d)] if layers_d else [Layer()]

    groups_d = _normalize_named_dict(raw.get("groups", []))
    groups = [_mk_group(gd, i) for i, gd in enumerate(groups_d)]
    zones_d = _normalize_named_dict(raw.get("zones", []))
    zones = [_mk_zone(zd, i) for i, zd in enumerate(zones_d)]

    active = int(raw.get("active_layer", 0))
    if active < 0: active = 0
    if active >= len(layers): active = len(layers)-1
    rules = raw.get('rules', [])
    if not isinstance(rules, list):
        rules = []
    return Project(layout=layout, layers=layers, active_layer=active, groups=groups, zones=zones,
                   export_audio=raw.get('export_audio'), preview_audio=raw.get('preview_audio'), postfx=raw.get('postfx'),
                   rules=rules)