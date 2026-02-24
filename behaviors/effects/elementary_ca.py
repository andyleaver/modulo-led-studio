from __future__ import annotations

SHIPPED = True

from typing import Any, Dict, List, Tuple
import random

from behaviors.registry import BehaviorDef, register
from behaviors.stateful_adapter import AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]

USES = [
    "color",
    "bg",
    "ca_rule",
    "ca_step_hz",
    "ca_wrap",
    "ca_seed",
    "ca_strip_width",
]


def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Intentionally blocked until integrated into exporter targets
    raise RuntimeError("Export not yet supported for Elementary CA (preview only for now).")


class ElementaryCAEffect:
    """Elementary cellular automaton (Rule 0..255).

    - Strip: uses width = num_leds (or ca_strip_width fold when you want a 2D history look).
      In strip mode without a real matrix, we render the *current row* across the LEDs.
    - Matrix: keeps a scrolling history: each step produces a new row at y=0 and pushes
      older rows down.
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 60) or 60)
        mw = int(params.get("_mw", 0) or 0)
        mh = int(params.get("_mh", 0) or 0)

        if mw > 0 and mh > 0:
            w, h = mw, mh
            matrix_mode = True
        else:
            # For strip we allow an optional fold width; default is "just a 1D row".
            w = int(params.get("ca_strip_width", 0) or 0)
            if w <= 0:
                w = n
                h = 1
            else:
                w = max(1, w)
                h = max(1, n // w)
                if h * w < 1:
                    w, h = max(1, n), 1
            matrix_mode = (h > 1)

        cells = w * h
        rule = int(params.get("ca_rule", 30) or 30) & 255
        seed = int(params.get("ca_seed", 1) or 0)
        rng = random.Random(seed)

        # Current row
        row = [0] * w
        # Seed: single 1 in center for classic look; if seed != 0, add slight randomness.
        row[w // 2] = 1
        if seed != 0:
            # deterministic sprinkle
            for i in range(w):
                if rng.random() < 0.02:
                    row[i] ^= 1

        if matrix_mode:
            grid = [0] * cells
            # Put the initial row at the top.
            for x in range(w):
                grid[x] = row[x]
        else:
            grid = None

        state["w"] = int(w)
        state["h"] = int(h)
        state["cells"] = int(cells)
        state["rule"] = int(rule)
        state["row"] = row
        state["grid"] = grid
        state["matrix_mode"] = bool(matrix_mode)
        state["acc"] = 0.0

    def _next_row(self, row: List[int], rule: int, wrap: bool) -> List[int]:
        w = len(row)
        out = [0] * w
        for x in range(w):
            l = row[(x - 1) % w] if wrap else (row[x - 1] if x - 1 >= 0 else 0)
            c = row[x]
            r = row[(x + 1) % w] if wrap else (row[x + 1] if x + 1 < w else 0)
            pattern = (l << 2) | (c << 1) | r
            out[x] = 1 if (rule >> pattern) & 1 else 0
        return out

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio=None) -> None:
        step_hz = int(params.get("ca_step_hz", 20) or 20)
        if step_hz < 1:
            step_hz = 1
        step_dt = 1.0 / float(step_hz)

        state["acc"] = float(state.get("acc", 0.0) or 0.0) + float(dt or 0.0)
        wrap = bool(params.get("ca_wrap", True))
        rule = int(params.get("ca_rule", state.get("rule", 30)) or 30) & 255
        state["rule"] = int(rule)

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        row = state.get("row")
        if not isinstance(row, list) or len(row) != w:
            self.reset(state, params=params)
            row = state.get("row")

        matrix_mode = bool(state.get("matrix_mode", False))
        grid = state.get("grid")
        if matrix_mode and (not isinstance(grid, list) or len(grid) != w * h):
            self.reset(state, params=params)
            grid = state.get("grid")

        # Avoid huge catch-up on pauses.
        max_steps = 32
        steps = 0
        while state["acc"] >= step_dt and steps < max_steps:
            state["acc"] -= step_dt
            row = self._next_row(row, rule, wrap)

            if matrix_mode and isinstance(grid, list):
                # Scroll existing rows down by 1
                for y in range(h - 1, 0, -1):
                    dst = y * w
                    src = (y - 1) * w
                    grid[dst:dst + w] = grid[src:src + w]
                # Insert new row at top
                grid[0:w] = row
            steps += 1

        state["row"] = row
        if matrix_mode:
            state["grid"] = grid

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)
        fg = params.get("color", (0, 255, 255))
        bg = params.get("bg", (0, 0, 0))
        fr, fg0, fb = int(fg[0]) & 255, int(fg[1]) & 255, int(fg[2]) & 255
        br, bg0, bb = int(bg[0]) & 255, int(bg[1]) & 255, int(bg[2]) & 255

        out: List[RGB] = [(br, bg0, bb)] * n
        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        matrix_mode = bool(state.get("matrix_mode", False))

        if matrix_mode and isinstance(state.get("grid"), list):
            g = state["grid"]
            cells = min(len(g), n, w * h)
            for i in range(cells):
                if g[i]:
                    out[i] = (fr, fg0, fb)
            return out

        # Strip / 1-row mode: render current row across LEDs.
        row = state.get("row")
        if not isinstance(row, list):
            row = [0] * w
        cells = min(len(row), n)
        for i in range(cells):
            if row[i]:
                out[i] = (fr, fg0, fb)
        return out


def register_elementary_ca():
    effect = ElementaryCAEffect()
    preview_emit, update = make_stateful_hooks(effect, hints=AdapterHints(num_leds=60, mw=0, mh=0, fixed_dt=1 / 60))
    defn = BehaviorDef(
        "elementary_ca",
        title="Elementary CA",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
