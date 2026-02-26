from __future__ import annotations

"""
Spawner v1 (engine primitive)

This is NOT an effect.

It provides a small, auditable way to spawn simulation entities (starting with
ParticleSystemV1) from rules, signals, or other engine systems.

Design goals:
- LED-first: no GPIO/peripherals assumptions.
- Deterministic: uses the engine time/seed model via ParticleSystemV1 RNG.
- Serializable: keeps only JSON-safe state under project["particle_systems_v1"].
- Safe: never crash the engine if misconfigured.

Integration:
- Registers:
  - a derived-signal provider that steps particle systems each frame
  - a Rules V6 custom action: "spawn_particles_v1"
"""

from typing import Any, Dict, Optional, Tuple
import json as _json
import hashlib as _hashlib

from runtime.extensions_v1 import register_signal_provider, register_rule_action
from runtime.particles_v1 import ParticleSystemV1, PointEmitter, LineEmitter, AreaEmitter

# Cache of live systems to avoid rebuilding objects every frame.
# Keyed by (id(project), system_name)
_SYS_CACHE: Dict[Tuple[int, str], Dict[str, Any]] = {}


def _stable_hash(obj: Any) -> str:
    try:
        s = _json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except Exception:
        s = repr(obj)
    return _hashlib.sha1(s.encode("utf-8")).hexdigest()


def _ensure_project_map(project: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(project, dict):
        return {}
    m = project.get("particle_systems_v1")
    if not isinstance(m, dict):
        m = {}
        project["particle_systems_v1"] = m
    return m


def _get_or_build_system(project: Dict[str, Any], name: str, layout: Dict[str, Any]) -> Optional[ParticleSystemV1]:
    if not isinstance(project, dict) or not isinstance(name, str) or not name:
        return None
    name = name.strip()
    systems = _ensure_project_map(project)
    cfg = systems.get(name)
    if not isinstance(cfg, dict):
        # Create minimal default
        cfg = {
            "state": {
                "max_particles": 4096,
                "wrap_edges": True,
                "friction": 0.10,
                "bounds": [0.0, 0.0, float((layout or {}).get("mw") or 1), float((layout or {}).get("mh") or 1)],
                "seed": 0,
                "particles": [],
                "modules": [],
            }
        }
        systems[name] = cfg

    state = cfg.get("state")
    if not isinstance(state, dict):
        state = {"particles": []}
        cfg["state"] = state

    sys_key = (id(project), name)
    h = _stable_hash(cfg)
    entry = _SYS_CACHE.get(sys_key)

    if entry and entry.get("hash") == h and isinstance(entry.get("sys"), ParticleSystemV1):
        ps: ParticleSystemV1 = entry["sys"]
        # keep bounds aligned with layout changes
        try:
            ps.set_bounds_from_layout(layout or {})
        except Exception:
            pass
        return ps

    # Build a new ParticleSystemV1 from serialized state
    try:
        ps = ParticleSystemV1.from_dict(state)
    except Exception:
        ps = ParticleSystemV1()

    try:
        ps.set_bounds_from_layout(layout or {})
    except Exception:
        pass

    # Compile modules from config
    ps.modules = []
    for m in (state.get("modules") or []):
        try:
            if not isinstance(m, dict):
                continue
            t = str(m.get("type") or "").strip().lower()
            if t == "gravity":
                gx = float(m.get("gx", 0.0))
                gy = float(m.get("gy", 0.0))
                from runtime.particles_v1 import module_constant_gravity
                ps.add_module(module_constant_gravity(gx, gy))
            elif t == "radial":
                x = float(m.get("x", 0.0))
                y = float(m.get("y", 0.0))
                strength = float(m.get("strength", 20.0))
                repel = bool(m.get("repel", False))
                from runtime.particles_v1 import module_radial_attractor
                ps.add_module(module_radial_attractor(x, y, strength=strength, repel=repel))
            elif t == "field":
                # Field advection expects a VectorField instance in cache.
                # Users can create it via their own code/plugins; we keep this as a hook.
                # No-op if missing.
                pass
        except Exception:
            continue

    _SYS_CACHE[sys_key] = {"hash": h, "sys": ps}
    return ps


def _save_back(project: Dict[str, Any], name: str, ps: ParticleSystemV1) -> None:
    try:
        systems = _ensure_project_map(project)
        cfg = systems.get(name) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        cfg["state"] = ps.to_dict()
        systems[name] = cfg
    except Exception:
        return


# ---- Derived-signal provider: step particle systems --------------------------------

def _signals_provider(ctx: Dict[str, Any]) -> Dict[str, Any]:
    project = ctx.get("project")
    layout = ctx.get("layout") or {}
    dt = float(ctx.get("dt") or 0.0)
    t = float(ctx.get("t") or 0.0)

    if not isinstance(project, dict):
        return {}

    systems = project.get("particle_systems_v1")
    if not isinstance(systems, dict) or not systems:
        return {}

    # Derive a small set of signals and advance systems
    out: Dict[str, Any] = {}
    total = 0

    # Provide existing derived signals as numeric context to modules
    # (Best-effort; modules may ignore)
    derived = ctx.get("derived") or {}
    sigs: Dict[str, float] = {}
    if isinstance(derived, dict):
        for k, v in derived.items():
            try:
                sigs[str(k)] = float(v)
            except Exception:
                continue

    for name in list(systems.keys()):
        ps = _get_or_build_system(project, name, layout)
        if ps is None:
            continue
        if dt > 0:
            try:
                ps.step(dt=dt, t=t, signals=sigs)
            except Exception:
                pass
        try:
            n = int(len(ps.particles))
        except Exception:
            n = 0
        total += n
        out[f"particles.{name}.count"] = n

        # Save back serialized state periodically (every frame is OK; it's small)
        _save_back(project, name, ps)

    out["particles.total"] = int(total)
    return out


# ---- Rules V6 custom action --------------------------------------------------------

def _rule_spawn_particles_v1(ctx: Dict[str, Any]) -> Dict[str, Any]:
    project = ctx.get("project")
    signals = ctx.get("signals") or {}
    action = ctx.get("action") or {}
    if not isinstance(project, dict):
        return {"errors": ["spawn_particles_v1: project not dict"]}

    name = str(action.get("system") or "default").strip()
    layout = (ctx.get("project") or {}).get("layout") if isinstance(ctx.get("project"), dict) else None
    # Prefer ctx layout if supplied
    layout = ctx.get("layout") or layout or {}
    ps = _get_or_build_system(project, name, layout)
    if ps is None:
        return {"errors": ["spawn_particles_v1: could not create system"]}

    emitter_type = str(action.get("emitter") or "point").strip().lower()
    count = int(action.get("count") or 1)

    # Position helpers: accept direct x/y or derive from occupancy/activity-like signals.
    def _f(key: str, default: float = 0.0) -> float:
        try:
            return float(action.get(key, default))
        except Exception:
            return float(default)

    mw = float((layout or {}).get("mw") or 1.0)
    mh = float((layout or {}).get("mh") or 1.0)
    x = _f("x", mw * 0.5)
    y = _f("y", mh * 0.5)

    speed = _f("speed", 0.0)
    life = _f("life", 2.0)
    spread = _f("spread", 6.28318530718)

    # color accepts either [r,g,b] or single int 0..255 -> grayscale
    col = action.get("color", [255, 255, 255])
    if isinstance(col, (int, float)):
        c = int(col)
        col = [c, c, c]
    if not (isinstance(col, (list, tuple)) and len(col) >= 3):
        col = [255, 255, 255]
    color = (int(col[0]), int(col[1]), int(col[2]))

    if emitter_type == "line":
        x0 = _f("x0", mw * 0.25); y0 = _f("y0", mh * 0.5)
        x1 = _f("x1", mw * 0.75); y1 = _f("y1", mh * 0.5)
        emitter = LineEmitter(x0, y0, x1, y1, speed=speed, spread=spread, life=life, color=color)
    elif emitter_type == "area":
        x0 = _f("x0", mw * 0.25); y0 = _f("y0", mh * 0.25)
        x1 = _f("x1", mw * 0.75); y1 = _f("y1", mh * 0.75)
        emitter = AreaEmitter(x0, y0, x1, y1, speed=speed, spread=spread, life=life, color=color)
    else:
        emitter = PointEmitter(x, y, speed=speed, spread=spread, life=life, color=color)

    spawned = 0
    try:
        spawned = emitter.emit(ps, count=count)
    except Exception:
        spawned = 0

    _save_back(project, name, ps)
    return {"variables": {}, "project_mutations": {"particle_systems_v1": project.get("particle_systems_v1")}, "spawned": int(spawned)}


def install() -> None:
    """Install spawner hooks. Safe to call multiple times."""
    try:
        register_signal_provider("spawner_v1", _signals_provider)
    except Exception:
        pass
    try:
        register_rule_action("spawn_particles_v1", _rule_spawn_particles_v1)
    except Exception:
        pass


# Install on import (engine-first, no UI)
install()
