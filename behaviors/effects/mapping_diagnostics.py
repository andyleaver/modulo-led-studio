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
    br = _clamp01(float(p.get("brightness", 1.0) or 1.0))
    marker = int(p.get("marker", 4) or 4)
    marker = max(1, min(16, marker))

    panel_w = int(p.get("panel_w", 0) or 0)
    panel_h = int(p.get("panel_h", 0) or 0)

    # Base gradient (X -> Red, Y -> Green, Blue constant)
    out: List[RGB] = [(0,0,0)] * n
    if mh <= 1:
        for i in range(n):
            rr = int(255 * (i / max(1, n-1)))
            gg = 0
            bb = 32
            out[i] = (int(rr*br)&255, int(gg*br)&255, int(bb*br)&255)
        return out

    def set_xy(xx: int, yy: int, rgb: RGB):
        i = yy*mw + xx
        if 0 <= i < n:
            out[i] = rgb

    for y in range(mh):
        gy = 0 if mh <= 1 else (y / max(1, mh-1))
        for x in range(mw):
            gx = 0 if mw <= 1 else (x / max(1, mw-1))
            rr = int(255 * gx)
            gg = int(255 * gy)
            bb = 32
            out[y*mw + x] = (int(rr*br)&255, int(gg*br)&255, int(bb*br)&255)

    # Panel boundary grid (if panel dims provided)
    if panel_w > 0 and panel_h > 0:
        # Use bright yellow grid lines
        grid_rgb = (int(255*br)&255, int(255*br)&255, 0)
        for x in range(mw):
            if x % panel_w == 0:
                for y in range(mh):
                    set_xy(x, y, grid_rgb)
        for y in range(mh):
            if y % panel_h == 0:
                for x in range(mw):
                    set_xy(x, y, grid_rgb)

    # Corner markers (very obvious)
    tl = (int(255*br)&255, 0, 0)             # red
    tr = (0, int(255*br)&255, 0)             # green
    bl = (0, 0, int(255*br)&255)             # blue
    brc = (int(255*br)&255, int(255*br)&255, int(255*br)&255)  # white

    for yy in range(marker):
        for xx in range(marker):
            set_xy(xx, yy, tl)
            set_xy(mw-1-xx, yy, tr)
            set_xy(xx, mh-1-yy, bl)
            set_xy(mw-1-xx, mh-1-yy, brc)

    # Center crosshair (thin) for quick rotate/flip sanity
    cx = mw // 2
    cy = mh // 2
    cross = (int(255*br)&255, 0, int(255*br)&255)  # magenta
    for x in range(mw):
        set_xy(x, cy, cross)
    for y in range(mh):
        set_xy(cx, y, cross)

    return out

def _arduino_emit(*, params: dict, layout=None, capabilities=None) -> str:
    return r"""// mapping_diagnostics: matrix mapping sanity pattern
// - Gradient: X->Red, Y->Green, Blue constant
// - Corner markers: TL red, TR green, BL blue, BR white
// - Center crosshair: magenta
// - Optional panel grid lines if panel_w/panel_h provided
//
// Params: brightness (0..1), marker (int), panel_w (int), panel_h (int)

void effect_mapping_diagnostics(float t) {
  const float BR = BRIGHTNESS;
  uint8_t marker = 4;
  uint16_t panel_w = 0;
  uint16_t panel_h = 0;

  // Gradient fill
  for (uint16_t y=0; y<MATRIX_H; y++) {
    for (uint16_t x=0; x<MATRIX_W; x++) {
      uint8_t rr = (uint8_t)((x * 255UL) / (MATRIX_W <= 1 ? 1 : (MATRIX_W - 1)));
      uint8_t gg = (uint8_t)((y * 255UL) / (MATRIX_H <= 1 ? 1 : (MATRIX_H - 1)));
      uint8_t bb = 32;
      CRGB c = CRGB(rr, gg, bb);
      c.nscale8_video((uint8_t)(BR * 255.0f));
      set_xy_or_linear(x, y, c);
    }
  }

  // Optional panel grid lines (yellow)
  if (panel_w > 0 && panel_h > 0) {
    CRGB grid = CRGB(255,255,0);
    grid.nscale8_video((uint8_t)(BR * 255.0f));
    for (uint16_t x=0; x<MATRIX_W; x++) {
      if ((x % panel_w) == 0) {
        for (uint16_t y=0; y<MATRIX_H; y++) set_xy_or_linear(x, y, grid);
      }
    }
    for (uint16_t y=0; y<MATRIX_H; y++) {
      if ((y % panel_h) == 0) {
        for (uint16_t x=0; x<MATRIX_W; x++) set_xy_or_linear(x, y, grid);
      }
    }
  }

  // Corner markers
  for (uint8_t yy=0; yy<marker; yy++) {
    for (uint8_t xx=0; xx<marker; xx++) {
      set_xy_or_linear(xx, yy, CRGB(255,0,0)); // TL red
      set_xy_or_linear((uint16_t)(MATRIX_W-1-xx), yy, CRGB(0,255,0)); // TR green
      set_xy_or_linear(xx, (uint16_t)(MATRIX_H-1-yy), CRGB(0,0,255)); // BL blue
      set_xy_or_linear((uint16_t)(MATRIX_W-1-xx), (uint16_t)(MATRIX_H-1-yy), CRGB(255,255,255)); // BR white
    }
  }

  // Center crosshair (magenta)
  uint16_t cx = MATRIX_W / 2;
  uint16_t cy = MATRIX_H / 2;
  for (uint16_t x=0; x<MATRIX_W; x++) set_xy_or_linear(x, cy, CRGB(255,0,255));
  for (uint16_t y=0; y<MATRIX_H; y++) set_xy_or_linear(cx, y, CRGB(255,0,255));
}
"""

def register_mapping_diagnostics():
    return register(BehaviorDef(
        "mapping_diagnostics",
        title="Mapping Diagnostics (Corners + Gradients)",
        uses=["brightness", "speed"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
        capabilities={
            "shape": "matrix",
            "notes": "Corner markers + gradients + optional panel grid lines. Use to validate rotate/flip/panel order fast.",
        },
    ))
