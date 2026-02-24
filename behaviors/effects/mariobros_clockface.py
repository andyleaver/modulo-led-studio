from __future__ import annotations

"""Mario Bros clockface (preview-only).

Visual port inspired by the upstream Arduino project the user referenced.
We bundle upstream art/font under its original license in third_party/mariobros_clock.

This effect intentionally redraws the whole scene every frame so UI toggle/state issues
can't leave stale pixels behind.
"""

from typing import List, Tuple
import math

from behaviors.registry import BehaviorDef, register
from behaviors.assets.mariobros_clock_assets import ASSETS, SKY
from behaviors.assets.mariobros_font import get_font
from behaviors.assets.adafruit_gfx_font import draw_text_to_buffer

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
    # Note: this is preview-only (ports the upstream look). Export is intentionally blocked.
    p = params or {}
    st = state if isinstance(state, dict) else {}

    mw, mh = _get_layout_wh(num_leds, p, layout or {})
    buf = [(0, 0, 0)] * (mw * mh)

    # Time source (preview): uses t as seconds since midnight for determinism.
    total_seconds = int(t) % (24 * 3600)
    hh = total_seconds // 3600
    mm = (total_seconds // 60) % 60
    ss = total_seconds % 60

    # Jump behavior (match upstream: Mario jumps when the minute flips)
    jump_on_minute = bool(p.get("jump_on_minute", True))

    # Upstream constants (see third_party/mariobros-clock/mario.h)
    PACE_PX = 3
    JUMP_HEIGHT_PX = 14
    STEP_S = 0.05  # 50ms per step

    # Init state
    if "base_y" not in st:
        st["base_x"] = 23
        st["base_y"] = 40
        st["jumping"] = False
        st["jump_t"] = 0.0
        st["last_min"] = mm

    # Trigger jump exactly once per minute (on the first second)
    if jump_on_minute:
        if ss == 0 and mm != st.get("last_min"):
            st["jumping"] = True
            st["jump_t"] = 0.0
            st["last_min"] = mm

    # --- Background (match upstream placement; no scrolling) ---
    _fill(buf, SKY)

    ground_w = int(ASSETS["GROUND"]["w"])
    ground_h = int(ASSETS["GROUND"]["h"])
    ground_y = mh - ground_h
    for x in range(0, mw, ground_w):
        _blit(buf, mw, mh, "GROUND", x, ground_y, transparent=False)

    _blit(buf, mw, mh, "BUSH", 43, 47)
    _blit(buf, mw, mh, "HILL", 0, 34)
    _blit(buf, mw, mh, "CLOUD1", 0, 21)
    _blit(buf, mw, mh, "CLOUD2", 51, 7)

    # Blocks (hour/minute)
    _blit(buf, mw, mh, "BLOCK", 13, 8)
    _blit(buf, mw, mh, "BLOCK", 32, 8)

    # Text (Adafruit_GFX font port; upstream uses Mario font)
    font = get_font()
    text_color = (0, 0, 0)
    draw_text_to_buffer(buf=buf, mw=mw, mh=mh, font=font, text=str(hh), x=18, y_baseline=30, color=text_color)
    draw_text_to_buffer(buf=buf, mw=mw, mh=mh, font=font, text=f"{mm:02d}", x=36, y_baseline=30, color=text_color)

    # --- Mario (idle + jump only; match upstream) ---
    mx = int(st.get("base_x", 23))
    base_y = int(st.get("base_y", 40))

    y = base_y
    sprite = "MARIO_IDLE"

    if dt <= 0:
        dt = 1.0 / 30.0

    if st.get("jumping"):
        st["jump_t"] = float(st.get("jump_t", 0.0)) + dt

        # Discrete step motion like upstream (3px every 50ms)
        steps = int(st["jump_t"] / STEP_S)
        d = steps * PACE_PX

        if d <= JUMP_HEIGHT_PX:
            y = base_y - d
        else:
            down = d - JUMP_HEIGHT_PX
            y = base_y - max(0, JUMP_HEIGHT_PX - down)

        sprite = "MARIO_JUMP"

        if y >= base_y:
            y = base_y
            st["jumping"] = False

    _blit(buf, mw, mh, sprite, mx, int(y), transparent=True)

    return buf


def _arduino_emit(*, num_leds: int, params: dict, t: float, state=None, layout=None, dt: float = 0.0, audio=None) -> str:
    # Preview-only for now. Exporting this would require:
    # - bitmap/font tables in generated firmware
    # - a lightweight RGB565 blitter + GFX font renderer (or baked sprites)
    raise NotImplementedError("mariobros_clockface is preview-only for now.")


def register_mariobros_clockface():
    return register(
        BehaviorDef(
            "mariobros_clockface",
            title="Mario Bros Clockface (upstream-style)",
            uses=["speed", "brightness"],
            preview_emit=_preview_emit,
            arduino_emit=_arduino_emit,
            capabilities={
                "shape": "matrix",
                "notes": "Preview-only: ports the upstream mariobros-clock look; includes Adafruit_GFX font render and upstream-style minute-jump.",
            },
        )
    )
