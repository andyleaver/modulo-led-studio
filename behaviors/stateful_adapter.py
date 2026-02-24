"""StatefulEffect adapter

Goal: make Arduino-faithful ports easy.

- Deterministic, fixed-tick updates (driven by SimClock in PreviewEngine)
- Render is side-effect free
- State must remain JSON-serialisable

This module provides a small class-based contract and an adapter that turns a
StatefulEffect into a BehaviorDef-compatible (preview_emit, update) pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

RGB = Tuple[int, int, int]


class StatefulEffect(Protocol):
    """Contract for Arduino-faithful, deterministic stateful effects."""

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        """Initialise/clear all state. Must be deterministic given params."""

    def tick(
        self,
        state: Dict[str, Any],
        *,
        params: Dict[str, Any],
        dt: float,
        t: float,
        audio: Optional[dict] = None,
    ) -> None:
        """Advance state by dt seconds at absolute time t seconds."""

    def render(
        self,
        *,
        num_leds: int,
        params: Dict[str, Any],
        t: float,
        state: Dict[str, Any],
    ) -> List[RGB]:
        """Render current state to an RGB list. Must not mutate state."""


@dataclass
class AdapterHints:
    """Engine-provided hints injected into params for init/tick."""

    num_leds: int
    mw: int = 0
    mh: int = 0
    fixed_dt: float = 1.0 / 60.0


def inject_hints(params: Dict[str, Any], hints: AdapterHints) -> Dict[str, Any]:
    """Return a shallow-copied params dict that includes engine hints."""

    p = dict(params or {})
    # IMPORTANT: PreviewEngine injects live values every frame.
    # The adapter must NEVER overwrite those (or we can trigger perpetual resets
    # when layout LED count != adapter default hints).
    p.setdefault("_num_leds", int(hints.num_leds))
    p.setdefault("_mw", int(hints.mw))
    p.setdefault("_mh", int(hints.mh))
    p.setdefault("_fixed_dt", float(hints.fixed_dt))
    return p


def make_stateful_hooks(effect: StatefulEffect, *, hints: AdapterHints):
    """Create BehaviorDef-style hooks for a class-based StatefulEffect."""

    def _ensure(state: Dict[str, Any], params: Dict[str, Any]):
        # We keep a cheap guard to re-init if LED count changes.
        n = int(params.get("_num_leds", hints.num_leds) or hints.num_leds)
        if not isinstance(state, dict):
            raise TypeError("state must be a dict for stateful effects")
        # IMPORTANT: many effect.reset(...) implementations (Arduino-faithful ports)
        # call state.clear() internally. That would wipe any adapter guard keys we set
        # before reset, causing a perpetual re-init loop ("static" effects).
        #
        # Therefore we:
        #   1) clear state
        #   2) call effect.reset(...)
        #   3) then write adapter guard keys AFTER reset
        if int(state.get("_n", 0) or 0) != n or not bool(state.get("_init", False)):
            state.clear()
            effect.reset(state, params=params)
            # Guard keys (written last so reset() can't wipe them)
            state["_n"] = int(state.get("_n", n) or n)
            state["_init"] = True

    def preview_emit(*, num_leds: int, params: dict, t: float, state=None):
        n = max(1, int(num_leds))
        st = state if isinstance(state, dict) else {}
        p = inject_hints(params or {}, AdapterHints(num_leds=n, mw=hints.mw, mh=hints.mh, fixed_dt=hints.fixed_dt))
        _ensure(st, p)
        return effect.render(num_leds=n, params=p, t=float(t), state=st)

    def update(*, state: dict, params: dict, dt: float, t: float, audio=None):
        p = inject_hints(params or {}, hints)
        _ensure(state, p)
        effect.tick(state, params=p, dt=float(dt or 0.0), t=float(t), audio=audio)

    return preview_emit, update
