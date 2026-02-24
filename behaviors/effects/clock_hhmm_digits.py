from __future__ import annotations
from typing import List, Tuple

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

# Shipped effect (included in behaviors/auto_load.py)
SHIPPED = True

# Simple 3x5 font (digits + colon). Each glyph is 3 bits wide, 5 rows.
# Bits: MSB->LSB is x=0..2
_FONT_3X5 = {
    "0": [0b111,0b101,0b101,0b101,0b111],
    "1": [0b010,0b110,0b010,0b010,0b111],
    "2": [0b111,0b001,0b111,0b100,0b111],
    "3": [0b111,0b001,0b111,0b001,0b111],
    "4": [0b101,0b101,0b111,0b001,0b001],
    "5": [0b111,0b100,0b111,0b001,0b111],
    "6": [0b111,0b100,0b111,0b101,0b111],
    "7": [0b111,0b001,0b010,0b010,0b010],
    "8": [0b111,0b101,0b111,0b101,0b111],
    "9": [0b111,0b101,0b111,0b001,0b111],
    ":": [0b000,0b010,0b000,0b010,0b000],
    " ": [0b000,0b000,0b000,0b000,0b000],
}

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

def _parse_rgb(v, default=(255,255,255)) -> RGB:
    try:
        r,g,b = int(v[0])&255, int(v[1])&255, int(v[2])&255
        return (r,g,b)
    except Exception:
        return (int(default[0])&255, int(default[1])&255, int(default[2])&255)

def _read_clock(audio: dict | None, t: float) -> tuple[int,int,int]:
    # Prefer injected clock dict (preview). Firmware may not provide it; fall back to t.
    h = m = s = None
    try:
        if isinstance(audio, dict):
            clk = audio.get("clock")
            if isinstance(clk, dict):
                if "hour" in clk:   h = int(clk.get("hour") or 0)
                if "minute" in clk: m = int(clk.get("minute") or 0)
                if "second" in clk: s = int(clk.get("second") or 0)
    except Exception:
        pass
    if h is None or m is None:
        # Deterministic fallback: treat t as seconds since 00:00.
        total = int(t) % (24*3600)
        h = (total // 3600) % 24
        m = (total // 60) % 60
        s = total % 60
    if s is None:
        s = int(t) % 60
    return h%24, m%60, s%60

def _draw_glyph(out: List[RGB], mw: int, mh: int, gx: int, gy: int, glyph_rows, col: RGB, scale: int = 1):
    if mw <= 0 or mh <= 0:
        return
    scale = max(1, int(scale))
    for ry, row_bits in enumerate(glyph_rows):
        for rx in range(3):
            if (row_bits >> (2 - rx)) & 1:
                for sy in range(scale):
                    for sx in range(scale):
                        x = gx + rx*scale + sx
                        y = gy + ry*scale + sy
                        if 0 <= x < mw and 0 <= y < mh:
                            out[y*mw + x] = col

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None, layout=None, dt: float = 0.0, audio=None) -> List[RGB]:
    n = max(1, int(num_leds))
    mw, mh = _get_layout_wh(n, params, layout)
    out = [(0,0,0)] * n

    p = params or {}
    color = _parse_rgb(p.get("color", (255,255,255)), default=(255,255,255))
    br = _clamp01(float(p.get("brightness", 1.0) or 1.0))
    col = (int(color[0]*br)&255, int(color[1]*br)&255, int(color[2]*br)&255)

    x = int(p.get("x", 1) or 1)
    y = int(p.get("y", 1) or 1)
    scale = int(p.get("scale", 2) or 2)

    use_24h = int(p.get("use_24h", 1) or 1) != 0
    blink_colon = int(p.get("blink_colon", 1) or 1) != 0
    pad_hours = int(p.get("pad_hours", 1) or 1) != 0  # 09:41 vs 9:41

    h,m,s = _read_clock(audio if isinstance(audio, dict) else None, t)
    if not use_24h:
        hh = h % 12
        if hh == 0: hh = 12
        h = hh

    hs = f"{h:02d}" if pad_hours else str(int(h))
    ms = f"{m:02d}"
    colon = ":" if (not blink_colon or (s % 2 == 0)) else " "

    text = (hs + colon + ms)[:5]

    # Auto-anchor right if requested
    anchor = str(p.get("anchor", "left")).lower().strip()
    if anchor in ("right","top_right","tr"):
        # width = 3*scale per glyph + 1*scale spacing between glyphs
        glyph_w = 3*scale
        spacing = scale
        total_w = len(text)*glyph_w + (len(text)-1)*spacing
        x = max(0, mw - total_w - int(p.get("margin", 1) or 1))

    cx = x
    for ch in text:
        glyph = _FONT_3X5.get(ch, _FONT_3X5[" "])
        _draw_glyph(out, mw, mh, cx, y, glyph, col, scale=scale)
        cx += 3*scale + scale

    return out

def _arduino_emit(*, params: dict, layout=None, capabilities=None) -> str:
    # Export implementation mirrors preview: 3x5 digits drawn into matrix using set_xy_or_linear().
    # Firmware clock source: millis() fallback; targets may replace with real clock if they provide one.
    return r"""// clock_hhmm_digits: HH:MM overlay using a 3x5 font (scaled)
// Params (if wired by exporter): COLOR_R/G/B, BRIGHTNESS, DIGIT_SCALE, DIGIT_X, DIGIT_Y, PAD_HOURS, BLINK_COLON

static const uint8_t __hhmm_font_3x5[11][5] = {
  /*0*/ {0b111,0b101,0b101,0b101,0b111},
  /*1*/ {0b010,0b110,0b010,0b010,0b111},
  /*2*/ {0b111,0b001,0b111,0b100,0b111},
  /*3*/ {0b111,0b001,0b111,0b001,0b111},
  /*4*/ {0b101,0b101,0b111,0b001,0b001},
  /*5*/ {0b111,0b100,0b111,0b001,0b111},
  /*6*/ {0b111,0b100,0b111,0b101,0b111},
  /*7*/ {0b111,0b001,0b010,0b010,0b010},
  /*8*/ {0b111,0b101,0b111,0b101,0b111},
  /*9*/ {0b111,0b101,0b111,0b001,0b111},
  /*:*/ {0b000,0b010,0b000,0b010,0b000},
};

static inline void __hhmm_draw_glyph(int gx, int gy, uint8_t glyph_idx, CRGB col, uint8_t scale) {
  if (scale < 1) scale = 1;
  if (glyph_idx > 10) glyph_idx = 10;
  for (int ry=0; ry<5; ry++) {
    uint8_t row = __hhmm_font_3x5[glyph_idx][ry];
    for (int rx=0; rx<3; rx++) {
      if ((row >> (2-rx)) & 1) {
        for (int sy=0; sy<scale; sy++) {
          for (int sx=0; sx<scale; sx++) {
            int x = gx + rx*scale + sx;
            int y = gy + ry*scale + sy;
            set_xy_or_linear((uint16_t)x, (uint16_t)y, col);
          }
        }
      }
    }
  }
}

static inline void __hhmm_time_from_millis(uint8_t* hh, uint8_t* mm, uint8_t* ss) {
  uint32_t sec = (uint32_t)(millis() / 1000UL);
  *ss = (uint8_t)(sec % 60UL);
  uint32_t min = sec / 60UL;
  *mm = (uint8_t)(min % 60UL);
  uint32_t hr = (min / 60UL) % 24UL;
  *hh = (uint8_t)hr;
}

void effect_clock_hhmm_digits(float t) {
  (void)t;
  uint8_t hh, mm, ss;
  __hhmm_time_from_millis(&hh, &mm, &ss);

  // Default params (exporter may override via generated defines)
  uint8_t scale = 2;
  int x0 = 1;
  int y0 = 1;
  bool pad_hours = true;
  bool blink_colon = true;

  #ifdef DIGIT_SCALE
    scale = (uint8_t)DIGIT_SCALE;
  #endif
  #ifdef DIGIT_X
    x0 = (int)DIGIT_X;
  #endif
  #ifdef DIGIT_Y
    y0 = (int)DIGIT_Y;
  #endif
  #ifdef PAD_HOURS
    pad_hours = (PAD_HOURS != 0);
  #endif
  #ifdef BLINK_COLON
    blink_colon = (BLINK_COLON != 0);
  #endif

  uint8_t h1 = (uint8_t)(hh / 10);
  uint8_t h2 = (uint8_t)(hh % 10);
  uint8_t m1 = (uint8_t)(mm / 10);
  uint8_t m2 = (uint8_t)(mm % 10);

  // color + brightness
  float br = BRIGHTNESS;
  CRGB col = CRGB(COLOR_R, COLOR_G, COLOR_B);
  col.nscale8_video((uint8_t)(br * 255.0f));

  int cx = x0;
  // hours
  if (pad_hours || h1 != 0) {
    __hhmm_draw_glyph(cx, y0, h1, col, scale);
    cx += 3*scale + scale;
  }
  __hhmm_draw_glyph(cx, y0, h2, col, scale);
  cx += 3*scale + scale;

  // colon
  bool show_colon = (!blink_colon) || ((ss % 2) == 0);
  if (show_colon) {
    __hhmm_draw_glyph(cx, y0, 10, col, scale);
  }
  cx += 3*scale + scale;

  // minutes
  __hhmm_draw_glyph(cx, y0, m1, col, scale);
  cx += 3*scale + scale;
  __hhmm_draw_glyph(cx, y0, m2, col, scale);
}
"""

def register_clock_hhmm_digits():
    # Preview-only overlay. Export eligibility system will mark it unsupported because arduino_emit is a stub.
    return register(BehaviorDef(
        "clock_hhmm_digits",
        title="Clock HH:MM Digits (3x5)",
        uses=["brightness", "color", "speed"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
    ))
