from __future__ import annotations

SHIPPED = True

from typing import Any, Dict, List, Tuple
import random

from behaviors.registry import BehaviorDef, register
from behaviors.stateful_adapter import AdapterHints, make_stateful_hooks

RGB = Tuple[int, int, int]

# Uses common color/bg plus ant-specific controls.
USES = [
    "color",
    "bg",
    "ant_color",
    "ant_step_hz",
    "ant_wrap",
    "ant_seed",
    "ant_strip_width",
]


def _arduino_emit(*, layout: dict, params: dict) -> str:
    # Intentionally blocked until integrated into exporter targets
    raise RuntimeError("Export not yet supported for Langton's Ant (preview only for now).")


class LangtonsAntEffect:
    """Langton's Ant that works on both matrix and strip.

    - Matrix: uses mw/mh from engine hints when available.
    - Strip: folds into a virtual grid width (ant_strip_width).
    """

    def reset(self, state: Dict[str, Any], *, params: Dict[str, Any]) -> None:
        n = int(params.get("_num_leds", 60) or 60)
        mw = int(params.get("_mw", 0) or 0)
        mh = int(params.get("_mh", 0) or 0)

        if mw > 0 and mh > 0:
            w, h = mw, mh
        else:
            w = int(params.get("ant_strip_width", 32) or 32)
            if w < 1:
                w = 1
            h = max(1, n // w)
            if h * w < 1:
                w, h = max(1, n), 1

        cells = w * h
        seed = int(params.get("ant_seed", 1) or 0)
        rng = random.Random(seed)

        # 0 = white, 1 = black
        grid = [0] * cells

        # Start near center with deterministic jitter for variety.
        cx, cy = w // 2, h // 2
        cx = int(max(0, min(w - 1, cx + rng.randint(-2, 2))))
        cy = int(max(0, min(h - 1, cy + rng.randint(-2, 2))))
        d = rng.randint(0, 3)  # 0=up,1=right,2=down,3=left

        state["w"] = int(w)
        state["h"] = int(h)
        state["cells"] = int(cells)
        state["grid"] = grid
        state["x"] = int(cx)
        state["y"] = int(cy)
        state["d"] = int(d)
        state["acc"] = 0.0

    def tick(self, state: Dict[str, Any], *, params: Dict[str, Any], dt: float, t: float, audio=None) -> None:
        step_hz = int(params.get("ant_step_hz", 30) or 30)
        if step_hz < 1:
            step_hz = 1
        step_dt = 1.0 / float(step_hz)

        state["acc"] = float(state.get("acc", 0.0) or 0.0) + float(dt or 0.0)
        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        wrap = bool(params.get("ant_wrap", True))

        g = state.get("grid")
        if not isinstance(g, list) or len(g) != w * h:
            self.reset(state, params=params)
            g = state.get("grid")

        x = int(state.get("x", 0) or 0)
        y = int(state.get("y", 0) or 0)
        d = int(state.get("d", 0) or 0)

        # Avoid huge catch-up on pauses.
        max_steps = 64
        steps = 0
        while state["acc"] >= step_dt and steps < max_steps:
            state["acc"] -= step_dt
            idx = y * w + x
            cell = 1 if g[idx] else 0

            # Turn: white -> right, black -> left (classic Langton).
            if cell == 0:
                d = (d + 1) & 3
            else:
                d = (d + 3) & 3

            # Flip cell
            g[idx] = 0 if cell else 1

            # Move forward
            if d == 0:
                y -= 1
            elif d == 1:
                x += 1
            elif d == 2:
                y += 1
            else:
                x -= 1

            if wrap:
                x %= w
                y %= h
            else:
                # Clamp and "bounce" by reversing direction on edge.
                if x < 0:
                    x = 0
                    d = 1
                elif x >= w:
                    x = w - 1
                    d = 3
                if y < 0:
                    y = 0
                    d = 2
                elif y >= h:
                    y = h - 1
                    d = 0

            steps += 1

        state["x"], state["y"], state["d"] = int(x), int(y), int(d)
        state["grid"] = g

    def render(self, *, num_leds: int, params: Dict[str, Any], t: float, state: Dict[str, Any]) -> List[RGB]:
        n = int(num_leds)

        fg = params.get("color", (0, 255, 0))
        bg = params.get("bg", (0, 0, 0))
        ac = params.get("ant_color", (255, 0, 0))

        fr, fg0, fb = int(fg[0]) & 255, int(fg[1]) & 255, int(fg[2]) & 255
        br, bg0, bb = int(bg[0]) & 255, int(bg[1]) & 255, int(bg[2]) & 255
        ar, ag, ab = int(ac[0]) & 255, int(ac[1]) & 255, int(ac[2]) & 255

        w = int(state.get("w", 1) or 1)
        h = int(state.get("h", 1) or 1)
        g = state.get("grid")
        if not isinstance(g, list):
            g = [0] * (w * h)

        out: List[RGB] = [(br, bg0, bb)] * n
        cells = min(len(g), n, w * h)
        for i in range(cells):
            if g[i]:
                out[i] = (fr, fg0, fb)

        x = int(state.get("x", 0) or 0)
        y = int(state.get("y", 0) or 0)
        idx = y * w + x
        if 0 <= idx < n:
            out[idx] = (ar, ag, ab)
        return out


def register_langtons_ant():
    effect = LangtonsAntEffect()
    preview_emit, update = make_stateful_hooks(
        effect,
        hints=AdapterHints(num_leds=60, mw=0, mh=0, fixed_dt=1 / 60),
    )
    defn = BehaviorDef(
        "langtons_ant",
        title="Langton's Ant",
        uses=USES,
        preview_emit=preview_emit,
        arduino_emit=_arduino_emit,
    )
    defn.stateful = True
    defn.update = update
    register(defn)
