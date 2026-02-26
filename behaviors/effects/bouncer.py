from __future__ import annotations
"""Bouncer (stateful demo).

A single dot moves along the strip and bounces at the ends. This is a minimal proof
that fixed-tick update + per-layer state works deterministically.

Params used:
- color (rgb)
- speed (float)  : units = LEDs per second (approx)
- width (int)    : dot width
- bg (rgb)       : background color
"""

from behaviors.registry import BehaviorDef, register

USES = ["color", "speed", "width", "bg", "opacity"]

def update(*, state, params: dict, dt: float, t: float, audio: dict):
    n = int(state.get("n", 0) or 0)
    # n is set by preview_emit on first call
    if n <= 0:
        return
    pos = float(state.get("pos", 0.0) or 0.0)
    vel = float(state.get("vel", 1.0) or 1.0)

    speed = float(params.get("speed", 6.0) or 6.0)
    # allow negative speed to reverse initial direction
    if speed < 0.0:
        vel = -abs(vel)
        speed = abs(speed)
    else:
        vel = abs(vel) if vel >= 0 else -abs(vel)

    pos += vel * speed * float(dt)

    # bounce
    if pos < 0.0:
        pos = 0.0
        vel = abs(vel)
    if pos > (n - 1):
        pos = float(n - 1)
        vel = -abs(vel)

    state["pos"] = pos
    state["vel"] = vel

def preview_emit(*, num_leds: int, params: dict, t: float, state=None):
    n = int(num_leds)
    if state is not None:
        state["n"] = n
        if "pos" not in state:
            state["pos"] = 0.0
            state["vel"] = 1.0

    bg = params.get("bg", (0, 0, 0))
    bgr, bgg, bgb = int(bg[0]), int(bg[1]), int(bg[2])
    out = [(bgr, bgg, bgb)] * n

    color = params.get("color", (255, 255, 255))
    r, g, b = int(color[0]), int(color[1]), int(color[2])

    width = int(params.get("width", 1) or 1)
    if width < 1:
        width = 1
    if width > n:
        width = n

    pos = 0.0
    if state is not None:
        pos = float(state.get("pos", 0.0) or 0.0)

    center = int(round(pos))
    half = max(0, width // 2)
    for i in range(center - half, center - half + width):
        if 0 <= i < n:
            out[i] = (r, g, b)
    return out

def arduino_emit(*, layer_var: str, params: dict, t_expr: str) -> str:
    # Export parity note:
    # Stateful export will be implemented once the Arduino runtime gets an effect-state tick loop.
    # For now, provide a minimal placeholder that still satisfies contracts.
    return "// bouncer: stateful export TODO\n"

register(BehaviorDef(
    "bouncer",
    title="Bouncer (Demo)",
    preview_emit=preview_emit,
    arduino_emit=arduino_emit,
    uses=USES,
    update=update,
    stateful=True,
))
