from __future__ import annotations
from typing import List, Tuple

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

# Shipped effect (included in behaviors/auto_load.py)
SHIPPED = True

def _get_layout_wh(num_leds: int, params: dict, layout: dict | None) -> tuple[int,int]:
    mw = int((params or {}).get("_mw") or 0)
    mh = int((params or {}).get("_mh") or 0)
    if mw > 0 and mh > 0:
        return mw, mh
    if layout and int(layout.get("mw") or 0) > 0 and int(layout.get("mh") or 0) > 0:
        return int(layout["mw"]), int(layout["mh"])
    return max(1, int(num_leds)), 1

def _clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None, layout=None, dt: float = 0.0, audio=None) -> List[RGB]:
    n = max(1, int(num_leds))
    mw, mh = _get_layout_wh(n, params or {}, layout or {})

    p = params or {}
    br = float(p.get("brightness", 1.0) or 1.0)
    br = _clamp01(br)
    color = p.get("color", [255,255,255])
    try:
        r,g,b = int(color[0])&255, int(color[1])&255, int(color[2])&255
    except Exception:
        r,g,b = 255,255,255
    r = int(r*br)&255; g=int(g*br)&255; b=int(b*br)&255

    # Determine current second: prefer injected clock (preview / wifi+ntp), else fall back to t.
    sec = None
    try:
        if isinstance(audio, dict):
            clk = audio.get("clock")
            if isinstance(clk, dict) and "second" in clk:
                sec = int(clk.get("second") or 0) % 60
    except Exception:
        sec = None
    if sec is None:
        sec = int(t) % 60

    y = int(p.get("row", 0) or 0)
    if mh > 0:
        y = max(0, min(mh-1, y))
    x = 0
    if mw > 0:
        x = sec % mw

    # Optional "trail" of previous seconds
    trail = int(p.get("trail", 0) or 0)
    trail = max(0, min(60, trail))

    out: List[RGB] = [(0,0,0)] * n

    # Matrix addressing: assume row-major XY mapping by preview mapping; if strip, linear.
    # We only write indices that exist.
    def set_xy(xx: int, yy: int, rgb: RGB):
        i = yy*mw + xx
        if 0 <= i < n:
            out[i] = rgb

    if mh <= 1:
        # Strip fallback: show dot moving along strip length
        i = sec % n
        out[i] = (r,g,b)
        for k in range(1, trail+1):
            out[(i-k) % n] = (max(0,r - k*8), max(0,g - k*8), max(0,b - k*8))
        return out

    set_xy(x, y, (r,g,b))
    for k in range(1, trail+1):
        set_xy((x-k) % mw, y, (max(0,r - k*10), max(0,g - k*10), max(0,b - k*10)))
    return out

def _arduino_emit(*, params: dict, layout=None, capabilities=None) -> str:
    # This effect is intended mainly as a visual NTP/time sanity indicator.
    # It relies on 'second' being available; on firmware, map it to millis() modulo 60 unless
    # an RTC/NTP source is wired by the target.
    return """// clock_seconds_dot: simple seconds sweep indicator
// NOTE: On firmware, this uses millis() unless the target provides a real clock.
// Params: color (RGB), brightness (0..1), row (y), trail (0..60)

uint8_t __csd_sec_from_millis() {
  return (uint8_t)((millis() / 1000UL) % 60UL);
}

void effect_clock_seconds_dot(float t) {
  const float BR = BRIGHTNESS; // modulo global brightness
  // layer params (if present in generated code, they will override these defaults)
  uint8_t row = 0;
  uint8_t trail = 0;
  uint8_t sec = __csd_sec_from_millis();
  uint16_t x = (uint16_t)(sec % (uint16_t)MATRIX_W);
  uint16_t y = (uint16_t)(row % (uint16_t)MATRIX_H);

  // dim background (do nothing, leaving previous layers)
  CRGB c = CRGB(COLOR_R, COLOR_G, COLOR_B);
  c.nscale8_video((uint8_t)(BR * 255.0f));

  set_xy_or_linear(x, y, c);
  for (uint8_t k=1; k<=trail; k++) {
    uint16_t xx = (uint16_t)((x + MATRIX_W - k) % MATRIX_W);
    CRGB cc = c;
    cc.nscale8_video((uint8_t)max(0, 255 - (int)k*40));
    set_xy_or_linear(xx, y, cc);
  }
}
"""

def register_clock_seconds_dot():
    return register(BehaviorDef(
        "clock_seconds_dot",
        title="Clock Seconds Dot (NTP sanity)",
        uses=["brightness", "color", "speed"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
        capabilities={
            "shape": "matrix",
            "notes": "Single pixel sweeps across top row each second (uses injected clock if available).",
        },
    ))
