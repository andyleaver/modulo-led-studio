from __future__ import annotations

"""Red Hat Runner (stateful, preview-only).

Purpose: demonstrate Modulo's core idea (state + rules + layered thinking)
without leaning on "pick an effect".

- Uses a small sprite set derived from the user's 2D-Game assets.
- Exposes a "jump_now" param so Rules v6 can trigger jumps on events
  (clock minute changes, audio thresholds, button toggles, etc.).

Export is intentionally blocked for now (sprite tables + blitter would need
firmware support in the exporter).
"""

from typing import List, Tuple

from behaviors.registry import BehaviorDef, register
from behaviors.assets.red_hat_assets import ASSETS, SKY

RGB = Tuple[int, int, int]

SHIPPED = True


def _get_layout_wh(num_leds: int, params: dict, layout: dict) -> Tuple[int, int]:
    mw = int((layout or {}).get("mw") or (layout or {}).get("width") or (params or {}).get("mw") or 64)
    mh = int((layout or {}).get("mh") or (layout or {}).get("height") or (params or {}).get("mh") or max(1, num_leds // max(1, mw)))
    return max(1, mw), max(1, mh)


def _fill(buf: List[RGB], color: RGB):
    for i in range(len(buf)):
        buf[i] = color


def _blit(buf: List[RGB], mw: int, mh: int, asset_name: str, x0: int, y0: int, *, transparent: bool = True):
    a = ASSETS[asset_name]
    w = int(a["w"])
    h = int(a["h"])
    pix: List[RGB] = a["pix"]  # row-major
    for y in range(h):
        yy = y0 + y
        if yy < 0 or yy >= mh:
            continue
        row_off = y * w
        out_off = yy * mw
        for x in range(w):
            xx = x0 + x
            if xx < 0 or xx >= mw:
                continue
            c = pix[row_off + x]
            if transparent and c == SKY:
                continue
            buf[out_off + xx] = c


def _preview_emit(*, num_leds: int, params: dict, t: float, state=None, layout=None, dt: float = 0.0, audio=None):
    p = params or {}
    st = state if isinstance(state, dict) else {}

    mw, mh = _get_layout_wh(num_leds, p, layout or {})
    buf: List[RGB] = [(0, 0, 0)] * (mw * mh)

    if dt <= 0:
        dt = 1.0 / 30.0

    # --- init state ---
    if "x" not in st:
        st["x"] = 10.0
        st["y"] = float(mh - 8 - 24)  # ground height 8, sprite 24
        st["vy"] = 0.0
        st["mode"] = "run"  # run | jump | dead
        st["frame"] = 0
        st["anim_t"] = 0.0
        st["scroll"] = 0.0
        st["speed"] = 18.0  # px/sec background scroll
        st["cooldown"] = 0.0
        st["obstacles"] = [mw + 10, mw + 35]

    ground_h = 8
    sprite_w = ASSETS["RUN1"]["w"]
    sprite_h = ASSETS["RUN1"]["h"]
    ground_y = mh - ground_h
    base_y = float(ground_y - sprite_h)

    # external controls
    jump_now = int(p.get("jump_now", 0))
    gravity = float(p.get("gravity", 140.0))
    jump_v = float(p.get("jump_v", -70.0))

    # optional audio boost (if present)
    boost = 0.0
    if audio is not None:
        try:
            boost = float(getattr(audio, "energy", 0.0))
        except Exception:
            boost = 0.0

    speed = float(st.get("speed", 18.0))
    speed *= 1.0 + min(1.5, max(0.0, boost)) * 0.35

    # update timers
    st["cooldown"] = max(0.0, float(st.get("cooldown", 0.0)) - dt)

    # jump trigger (edge-like behaviour: any nonzero jump_now while grounded and not cooling down)
    grounded = st["y"] >= base_y - 0.01
    if jump_now and grounded and st["cooldown"] <= 0.0 and st.get("mode") != "dead":
        st["vy"] = jump_v
        st["mode"] = "jump"
        st["cooldown"] = 0.25

    # physics
    if st.get("mode") != "dead":
        st["vy"] = float(st.get("vy", 0.0)) + gravity * dt
        st["y"] = float(st.get("y", base_y)) + float(st.get("vy", 0.0)) * dt
        if st["y"] >= base_y:
            st["y"] = base_y
            st["vy"] = 0.0
            st["mode"] = "run"

    # scroll obstacles
    st["scroll"] = float(st.get("scroll", 0.0)) + speed * dt
    dx = speed * dt
    new_obs = []
    for ox in st.get("obstacles", []):
        ox2 = float(ox) - dx
        if ox2 < -8:
            ox2 = mw + 10
        new_obs.append(ox2)
    st["obstacles"] = new_obs

    # collision check (very simple AABB)
    if st.get("mode") != "dead":
        px0 = float(st.get("x", 10.0))
        py0 = float(st.get("y", base_y))
        px1 = px0 + sprite_w
        py1 = py0 + sprite_h
        for ox in st.get("obstacles", []):
            bx0 = float(ox)
            by0 = float(ground_y - 8)
            bx1 = bx0 + 8
            by1 = by0 + 8
            if (px0 < bx1 and px1 > bx0 and py0 < by1 and py1 > by0):
                st["mode"] = "dead"
                break

    # animate
    st["anim_t"] = float(st.get("anim_t", 0.0)) + dt
    if st["anim_t"] >= 0.12:
        st["anim_t"] = 0.0
        st["frame"] = (int(st.get("frame", 0)) + 1) % 2

    # --- render ---
    _fill(buf, (20, 40, 90))

    # ground tiling
    gw = ASSETS["GROUND"]["w"]
    gx_off = -int(st.get("scroll", 0.0)) % gw
    for x in range(-gw + gx_off, mw + gw, gw):
        _blit(buf, mw, mh, "GROUND", x, ground_y, transparent=False)

    # obstacles
    for ox in st.get("obstacles", []):
        _blit(buf, mw, mh, "OBST", int(ox), ground_y - 8, transparent=False)

    # player sprite
    mode = st.get("mode")
    if mode == "dead":
        spr = "DEAD"
    elif mode == "jump":
        spr = "JUMP"
    else:
        spr = "RUN1" if int(st.get("frame", 0)) == 0 else "RUN2"

    _blit(buf, mw, mh, spr, int(st.get("x", 10)), int(st.get("y", base_y)), transparent=True)

    return buf


def _arduino_emit(*, num_leds: int, params: dict, t: float, state=None, layout=None, dt: float = 0.0, audio=None) -> str:
    raise NotImplementedError("red_hat_runner is preview-only for now.")


def register_red_hat_runner():
    return register(
        BehaviorDef(
            "red_hat_runner",
            title="Red Hat Runner",
            uses=["speed", "brightness"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "shape": "matrix",
                "notes": "Stateful demo: jump is driven by rules via jump_now param; includes simple collision -> dead state.",
            },
        )
    )
