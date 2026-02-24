from __future__ import annotations
"""State container + helpers for stateful effects (games, simulations).

Design goals:
- Per-layer state must be *JSON-serialisable* (dict/list/num/bool/str only).
- Deterministic simulation is driven by :class:`preview.sim_clock.SimClock`.
- Effects should advance their state in ``BehaviorDef.update(...)`` (fixed tick),
  and only *render* in ``preview_emit(...)``.

This module intentionally keeps the contract small and dependency-free.
"""

class EffectState(dict):
    """Mutable per-layer state persisted across frames.

    Compatibility:
    Many older preview_emit implementations assume ``state`` starts as ``None``
    and initialise required keys on first call. When the engine persists state
    as a dict-like object, those effects may skip their init branch and then
    directly index missing keys (e.g. ``state['phase']``), which raises a
    KeyError and results in a BLANK audit frame.

    To keep shipped effects deterministic without per-effect rewrites, we
    provide a conservative ``__missing__`` default for numeric keys.
    """

    def __missing__(self, key):
        # Default missing numeric-like state to 0.0. This is safe for the
        # majority of effects that accumulate phases/counters.
        v = 0.0
        try:
            dict.__setitem__(self, key, v)
        except Exception:
            pass
        return v


from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import random

@dataclass
class EffectContext:
    """Runtime context passed to stateful effects during preview.

    Minimal contract to keep stateful demo effects working.
    """
    layout: Dict[str, Any] = field(default_factory=dict)
    dt: float = 0.016
    t: float = 0.0
    audio: Optional[Dict[str, Any]] = None


def rng_load(state: Dict[str, Any], *, seed: int, key: str = "rng") -> random.Random:
    """Return a deterministic RNG reconstructed from JSON-safe state.

    Stores/restores the RNG's internal state via ``random.Random.getstate()``.
    The state is stored in ``state[f"{key}_state"]``.

    Never stores the Random instance itself inside ``state``.
    """
    seed = int(seed) & 0xFFFFFFFF
    seed_key = f"{key}_seed"
    st_key = f"{key}_state"
    rng = random.Random()
    try:
        if int(state.get(seed_key, -1)) != seed or st_key not in state:
            rng.seed(seed)
            state[seed_key] = seed
            state[st_key] = rng.getstate()
        else:
            rng.setstate(state[st_key])
    except Exception:
        rng.seed(seed)
        state[seed_key] = seed
        state[st_key] = rng.getstate()
    return rng


def rng_save(state: Dict[str, Any], rng: random.Random, *, key: str = "rng") -> None:
    """Persist RNG internal state back into the JSON-safe ``state``."""
    st_key = f"{key}_state"
    try:
        state[st_key] = rng.getstate()
    except Exception:
        # If something goes wrong, do not poison state.
        pass

def schema_defaults(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Build a defaults dict from a state schema definition."""
    fields = (schema or {}).get("fields", {}) or {}
    out: Dict[str, Any] = {}
    for k, spec in fields.items():
        if isinstance(spec, dict) and "default" in spec:
            # Make a shallow copy for lists/dicts to avoid shared mutation
            v = spec.get("default")
            if isinstance(v, (dict, list)):
                out[k] = v.copy() if isinstance(v, dict) else list(v)
            else:
                out[k] = v
        else:
            out[k] = None
    return out
