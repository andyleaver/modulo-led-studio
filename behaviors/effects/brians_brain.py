from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple
import random

from behaviors.registry import BehaviorDef, register
from behaviors.stateful_adapter import AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]

USES = [
    "color",               # alive
    "brain_dying_color",   # dying
    "bg",                  # dead
    "density",
    "brain_step_hz",
    "brain_wrap",
    "brain_seed",
    "brain_strip_width",
]

def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Intentionally blocked until integrated into exporter targets
    raise RuntimeError("Export not yet supported for Brian's Brain (preview only for now).")


class BriansBrainEffect:
    """Brian's Brain (autonomous cellular automaton) for both matrix and strip.

    State encoding per cell:
      0 = dead
      1 = alive
      2 = dying

    Rules:
      - alive -> dying
      - dying -> dead
      - dead -> alive if exactly 2 alive neighbors
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 60) or 60)
        mw = int(params.get("_mw", 0) or 0)
        mh = int(params.get("_mh", 0) or 0)

        if mw > 0 and mh > 0:
            w, h = mw, mh
        else:
            w = int(params.get("brain_strip_width", 32) or 32)
            if w < 1:
                w = 1
            h = max(1, n // w)
            if h * w < 1:
                w, h = max(1, n), 1

        cells = w * h
        seed = int(params.get("brain_seed", 42) or 0)
        dens_raw = params.get("density", None)
        dens = float(dens_raw) if dens_raw is not None else 0.15
        # If density is 0 or missing, choose a sensible non-blank default.
        if dens <= 0.0:
            dens = 0.15
        dens = 0.0 if dens < 0.0 else (1.0 if dens > 1.0 else dens)

        rng = random.Random(seed)
        # Start with only alive/dead (no dying) for clarity
        grid = [1 if rng.random() < dens else 0 for _ in range(cells)]
        # Force at least one alive cell so the effect never appears blank.
        if cells > 0 and 1 not in grid:
            grid[cells // 2] = 1

        state["w"] = int(w)
        state["h"] = int(h)
        state["cells"] = int(cells)
        state["grid"] = grid
        state["acc"] = 0.0

    def _step(self, grid: List[int], w: int, h: int, wrap: bool) -> List[int]:
        def idx(x: int, y: int) -> int:
            return y * w + x

        out = [0] * (w * h)

        for y in range(h):
            for x in range(w):
                cur = grid[idx(x, y)]
                if cur == 1:
                    out[idx(x, y)] = 2  # alive -> dying
                    continue
                if cur == 2:
                    out[idx(x, y)] = 0  # dying -> dead
                    continue

                # dead: count alive neighbors (state == 1)
                alive_n = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx = x + dx
                        ny = y + dy
                        if wrap:
                            nx %= w
                            ny %= h
                        else:
                            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                                continue
                        if grid[idx(nx, ny)] == 1:
                            alive_n += 1
                out[idx(x, y)] = 1 if alive_n == 2 else 0

        return out

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio=None) -> None:
        step_hz = int(params.get("brain_step_hz", 12) or 12)
        if step_hz < 1:
            step_hz = 1
        step_dt = 1.0 / float(step_hz)

        state["acc"] = float(state.get("acc", 0.0) or 0.0) + float(dt or 0.0)

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        wrap = bool(params.get("brain_wrap", True))

        max_steps = 8
        steps = 0
        while state["acc"] >= step_dt and steps < max_steps:
            state["acc"] -= step_dt
            g = state.get("grid")
            if not isinstance(g, list) or len(g) != w * h:
                self.reset(state, params=params)
                g = state.get("grid")
            state["grid"] = self._step(g, w, h, wrap)
            steps += 1

    def render(
        self,
        *,
        num_leds: int,
        params: Dict[str, Any],
        t: float,
        state: Dict[str, Any],
    ) -> List[RGB]:
        alive_c = params.get("color", (0, 255, 255))
        dying_c = params.get("brain_dying_color", (0, 0, 255))
        bg = params.get("bg", (0, 0, 0))

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        g = state.get("grid")
        out: List[RGB] = [bg] * int(max(1, num_leds))

        if not isinstance(g, list):
            return out

        cells = min(len(out), w * h, len(g))
        for i in range(cells):
            v = g[i]
            if v == 1:
                out[i] = alive_c
            elif v == 2:
                out[i] = dying_c
            else:
                out[i] = bg
        return out


def register_brians_brain():
    effect = BriansBrainEffect()
    preview_emit, update = make_stateful_hooks(
        effect,
        hints=AdapterHints(num_leds=60, mw=0, mh=0, fixed_dt=1/60),
    )
    defn = BehaviorDef(
        "brians_brain",
        title="Brian's Brain",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
