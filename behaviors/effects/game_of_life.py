from __future__ import annotations
SHIPPED = True

from typing import Any, Dict, List, Tuple
import random

from behaviors.registry import BehaviorDef, register
from behaviors.stateful_adapter import AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]
USES = ["color", "bg", "density", "life_step_hz", "life_wrap", "life_seed", "life_strip_width", "life_variant"]

def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Intentionally blocked until integrated into exporter targets
    raise RuntimeError("Export not yet supported for Game of Life (preview only for now).")

class GameOfLifeEffect:
    """Conway's Game of Life that works on both matrix and strip.

    - Matrix: uses mw/mh from engine hints when available.
    - Strip: uses a virtual grid width (life_strip_width) to fold the strip into rows.
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 60) or 60)
        mw = int(params.get("_mw", 0) or 0)
        mh = int(params.get("_mh", 0) or 0)

        if mw > 0 and mh > 0:
            w, h = mw, mh
        else:
            w = int(params.get("life_strip_width", 32) or 32)
            if w < 1:
                w = 1
            h = max(1, n // w)
            if h * w < 1:
                w, h = max(1, n), 1

        cells = w * h
        seed = int(params.get("life_seed", 1337) or 0)
        dens = float(params.get("density", 0.2) or 0.0)
        dens = 0.0 if dens < 0.0 else (1.0 if dens > 1.0 else dens)

        rng = random.Random(seed)
        grid = [1 if rng.random() < dens else 0 for _ in range(cells)]

        state["w"] = int(w)
        state["h"] = int(h)
        state["cells"] = int(cells)
        state["grid"] = grid
        state["acc"] = 0.0


    def _rules(self, variant: str) -> tuple[set[int], set[int]]:
        v = (variant or "Conway").strip()
        if v == "HighLife":
            return {3, 6}, {2, 3}          # B36/S23
        if v == "Seeds":
            return {2}, set()              # B2/S
        if v == "DayNight":
            return {3, 6, 7, 8}, {3, 4, 6, 7, 8}  # B3678/S34678
        return {3}, {2, 3}                 # Conway B3/S23

    def _step(self, grid: List[int], w: int, h: int, wrap: bool, birth: set[int], survive: set[int]) -> List[int]:
        def idx(x: int, y: int) -> int:
            return y * w + x

        out = [0] * (w * h)
        for y in range(h):
            for x in range(w):
                n = 0
                # 8 neighbors
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if wrap:
                            nx %= w
                            ny %= h
                        else:
                            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                                continue
                        n += 1 if grid[idx(nx, ny)] else 0

                a = grid[idx(x, y)] != 0
                if a:
                    out[idx(x, y)] = 1 if (n in survive) else 0
                else:
                    out[idx(x, y)] = 1 if (n in birth) else 0
        return out

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio=None) -> None:
        step_hz = int(params.get("life_step_hz", 8) or 8)
        if step_hz < 1:
            step_hz = 1
        step_dt = 1.0 / float(step_hz)

        state["acc"] = float(state.get("acc", 0.0) or 0.0) + float(dt or 0.0)

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        wrap = bool(params.get("life_wrap", True))

        # Avoid huge catch-up spirals on pauses
        max_steps = 8
        steps = 0
        while state["acc"] >= step_dt and steps < max_steps:
            state["acc"] -= step_dt
            g = state.get("grid")
            if not isinstance(g, list) or len(g) != w * h:
                # safety re-init
                self.reset(state, params=params)
                g = state.get("grid")
            birth, survive = self._rules(str(params.get("life_variant", "Conway")))
            state["grid"] = self._step(g, w, h, wrap, birth, survive)
            steps += 1

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        fg = params.get("color", (0, 255, 0))
        bg = params.get("bg", (0, 0, 0))
        fr, fg0, fb = int(fg[0]) & 255, int(fg[1]) & 255, int(fg[2]) & 255
        br, bg0, bb = int(bg[0]) & 255, int(bg[1]) & 255, int(bg[2]) & 255

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        grid = state.get("grid")
        if not isinstance(grid, list):
            grid = [0] * (w * h)

        out: List[RGB] = [(br, bg0, bb)] * n
        cells = min(len(grid), n, w * h)
        for i in range(cells):
            if grid[i]:
                out[i] = (fr, fg0, fb)
        return out

def register_game_of_life():
    effect = GameOfLifeEffect()
    preview_emit, update = make_stateful_hooks(effect, hints=AdapterHints(num_leds=60, mw=0, mh=0, fixed_dt=1/60))
    defn = BehaviorDef(
        "game_of_life",
        title="Game of Life",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
