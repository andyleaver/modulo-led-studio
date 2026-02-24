from __future__ import annotations
from typing import List, Tuple, Dict, Any
import math

from behaviors.registry import BehaviorDef, register

RGB = Tuple[int, int, int]

# Shipped effect (included in behaviors/auto_load.py)
SHIPPED = True

# This effect is designed for matrix/cells layouts. It will still emit something
# on strips, but tile rendering is best with a 2D layout.

# --- tiny 8x8 tile + sprite assets -------------------------------------------------
# Palette indices:
#   0 = transparent / sky
#   1 = brick
#   2 = question
#   3 = sprite
#   4 = grass
# Note: these are intentionally simple "Mario-clock-style" vibes, not exact art.

# 8x8 tiles: each row is a byte, MSB->LSB is x=0..7
TILE_BRICK = [
    0b11111111,
    0b10101010,
    0b11111111,
    0b01010101,
    0b11111111,
    0b10101010,
    0b11111111,
    0b01010101,
]
TILE_QUESTION = [
    0b00111100,
    0b01000010,
    0b00000100,
    0b00001000,
    0b00001000,
    0b00000000,
    0b00001000,
    0b00000000,
]
TILE_GRASS = [
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b11111111,
    0b10101010,
    0b11111111,
    0b00000000,
]

# 8x8 sprite (simple "runner" silhouette)
SPRITE = [
    0b00011000,
    0b00111100,
    0b01111110,
    0b00111100,
    0b00011000,
    0b00100100,
    0b01000010,
    0b10000001,
]

def _clamp01(x: float) -> float:
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x

def _apply_brightness(rgb: RGB, br: float) -> RGB:
    br = _clamp01(br)
    return (int(rgb[0]*br)&255, int(rgb[1]*br)&255, int(rgb[2]*br)&255)

def _get_layout_wh(num_leds: int, params: dict, layout: dict | None) -> Tuple[int,int]:
    # Preview engine injects these for compatibility.
    mw = int((params or {}).get("_mw") or 0)
    mh = int((params or {}).get("_mh") or 0)
    if mw > 0 and mh > 0 and mw*mh <= max(1, int(num_leds))*4:
        return mw, mh
    if layout and int(layout.get("mw") or 0) > 0 and int(layout.get("mh") or 0) > 0:
        return int(layout["mw"]), int(layout["mh"])
    # fallback: treat as strip
    return max(1, int(num_leds)), 1

def _tile_bit(tile_rows: List[int], x: int, y: int) -> int:
    if x < 0 or y < 0 or x > 7 or y > 7:
        return 0
    row = tile_rows[y] & 0xFF
    return 1 if (row & (1 << (7-x))) else 0


# --- optional user assets ---------------------------------------------------------
# The effect supports overriding tile/sprite assets via layer params (stored in the .json project file).
#
# Params supported (all optional):
#   tilemap_tiles: dict[str, list[int]]         # each tile is 8 rows of 0..255 bits (MSB->LSB)
#   tilemap_map:   list[str]                    # rows of tile chars, e.g. "..BBQQ.."
#   tilemap_legend: dict[str, str]              # mapping from char -> tile key (defaults: B=brick, Q=question, G=grass, .=sky)
#   sprite_frames: list[list[int]]              # list of 8x8 bit rows (0..255) for animation
#
# If not provided, built-in tiles/sprite are used.
#
def _safe_bitrows8(x) -> List[int] | None:
    try:
        if isinstance(x, list) and len(x) == 8:
            out = []
            for r in x:
                if isinstance(r, bool):
                    return None
                if isinstance(r, (int, float)):
                    out.append(int(r) & 0xFF)
                elif isinstance(r, str):
                    rr = r.strip()
                    if rr.startswith("0b"):
                        out.append(int(rr, 2) & 0xFF)
                    elif rr.isdigit():
                        out.append(int(rr) & 0xFF)
                    else:
                        return None
                else:
                    return None
            return out
    except Exception:
        return None
    return None

def _load_user_assets(params: dict) -> dict:
    p = params or {}
    tiles = None
    ttiles = p.get("tilemap_tiles")
    if isinstance(ttiles, dict):
        tmp = {}
        for k,v in ttiles.items():
            br = _safe_bitrows8(v)
            if br is not None:
                tmp[str(k)] = br
        if tmp:
            tiles = tmp

    tmap = None
    raw_map = p.get("tilemap_map")
    if isinstance(raw_map, list) and raw_map and all(isinstance(r, str) for r in raw_map):
        # Normalize to equal width by padding with '.'
        w = max(len(r) for r in raw_map)
        tmap = [r.ljust(w, ".") for r in raw_map]

    legend = {"B":"brick","Q":"question","G":"grass",".":"sky"," ":"sky"}
    raw_leg = p.get("tilemap_legend")
    if isinstance(raw_leg, dict):
        for ch, name in raw_leg.items():
            if isinstance(ch, str) and ch:
                legend[ch[0]] = str(name)

    frames = None
    raw_frames = p.get("sprite_frames")
    if isinstance(raw_frames, list):
        tmpf=[]
        for fr in raw_frames:
            br=_safe_bitrows8(fr)
            if br is not None:
                tmpf.append(br)
        if tmpf:
            frames=tmpf

    return {"tiles": tiles, "map": tmap, "legend": legend, "frames": frames}

def _preview_emit(*, num_leds: int, params: dict, t: float, state=None, layout=None, dt: float = 0.0, audio=None) -> List[RGB]:
    n = max(1, int(num_leds))
    mw, mh = _get_layout_wh(n, params or {}, layout or {})

    assets = _load_user_assets(params or {})
    user_tiles = assets.get('tiles') or {}
    user_map = assets.get('map')
    legend = assets.get('legend') or {}
    user_frames = assets.get('frames')

    # Controls
    speed = float((params or {}).get('speed', 1.0))
    br = float((params or {}).get('brightness', 1.0))

    # Jump controls
    jump_period_s = float((params or {}).get('jump_period_s', 0.0))  # periodic trigger; 0 disables
    jump_height = float((params or {}).get('jump_height', 8.0))
    jump_duration_s = float((params or {}).get('jump_duration_s', 0.45))

    # One-shot jump trigger (useful with Rules V6 set_layer_param).
    # Treat as an edge: triggers only on 0->1 transitions.
    try:
        if state is None or not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}
    try:
        _jn = float((params or {}).get('jump_now', 0.0) or 0.0)
    except Exception:
        _jn = 0.0
    _jn_on = bool(_jn > 0.5)
    if _jn_on and (not bool(state.get('jump_now_prev', False))):
        state['jump_t0'] = float(t)
    state['jump_now_prev'] = _jn_on


    # Clock-driven triggers (preview-only unless firmware provides a clock)
    jump_on_minute = bool(int((params or {}).get('jump_on_minute', 0) or 0))
    jump_on_second = bool(int((params or {}).get('jump_on_second', 0) or 0))
    clock_source = str((params or {}).get('clock_source', 'local') or 'local').lower().strip()  # reserved

    # Optional user tint for sprite. Default: red-ish.
    sprite_col = (params or {}).get("color", (220, 40, 40))
    if not (isinstance(sprite_col, (list, tuple)) and len(sprite_col) == 3):
        sprite_col = (220, 40, 40)

    # Palette (sky, brick, question, sprite, grass)
    sky = (6, 10, 22)
    brick = (120, 40, 18)
    question = (200, 140, 20)
    grass = (10, 70, 18)
    sprite_rgb = tuple(int(x) & 255 for x in sprite_col)

    sky = _apply_brightness(sky, br)
    brick = _apply_brightness(brick, br)
    question = _apply_brightness(question, br)
    grass = _apply_brightness(grass, br)
    sprite_rgb = _apply_brightness(sprite_rgb, br)

    # Tile size fixed 8 for parity with Arduino emitter
    ts = 8


    # Resolve tile assets (built-in unless overridden)
    TILE_BRICK_U = user_tiles.get("brick", TILE_BRICK)
    TILE_QUESTION_U = user_tiles.get("question", TILE_QUESTION)
    TILE_GRASS_U = user_tiles.get("grass", TILE_GRASS)
    
    # Background scroll (pixels)
    scroll = int((t * 12.0 * max(0.0, speed)) % max(1, mw))

    # Simple level: sky everywhere, grass band at bottom, bricks/questions sprinkled
    out = [sky] * n

    def set_xy(x: int, y: int, col: RGB):
        if x < 0 or y < 0 or x >= mw or y >= mh:
            return
        i = y * mw + x
        if 0 <= i < n:
            out[i] = col




    # If a user tilemap is provided, render it instead of the procedural background.
    if user_map:
        map_h = len(user_map)
        map_w = max(1, max(len(r) for r in user_map))
        tileset = {
            "brick": TILE_BRICK_U,
            "question": TILE_QUESTION_U,
            "grass": TILE_GRASS_U,
        }
        for y in range(mh):
            ty = (y // ts) % map_h
            row = user_map[ty]
            for x in range(mw):
                tx = ((x + scroll) // ts) % map_w
                ch = row[tx] if tx < len(row) else "."
                tkey = legend.get(ch, "sky")
                tile = tileset.get(tkey)
                if tile is None:
                    continue
                if _tile_bit(tile, (x + scroll) % ts, y % ts):
                    if tkey == "brick":
                        set_xy(x, y, brick)
                    elif tkey == "question":
                        set_xy(x, y, question)
                    else:
                        set_xy(x, y, grass)
    else:
        # Draw background tiles
        for y in range(mh):
            for x in range(mw):
                # grass band near bottom
                if y >= mh - ts:
                    if _tile_bit(TILE_GRASS_U, x % ts, y % ts):
                        set_xy(x, y, grass)
                    continue
    
                # parallax-ish: only tile on some rows
                tx = ((x + scroll) // ts)
                ty = (y // ts)
    
                tile_kind = 0
                if ty % 3 == 1 and tx % 7 in (2,3):
                    tile_kind = 1  # brick
                if ty % 5 == 2 and tx % 11 == 5:
                    tile_kind = 2  # question
    
                if tile_kind == 1:
                    if _tile_bit(TILE_BRICK_U, (x + scroll) % ts, y % ts):
                        set_xy(x, y, brick)
                elif tile_kind == 2:
                    if _tile_bit(TILE_QUESTION_U, (x + scroll) % ts, y % ts):
                        set_xy(x, y, question)
    
    # Sprite bob (runs along ground)
    ground_y = mh - ts - 8
    bob = int(2.0 * math.sin(t * 6.0 * max(0.0, speed)))
    sx = int((mw * 0.25) + (mw * 0.15) * math.sin(t * 1.4 * max(0.0, speed)))
    sy = max(0, min(mh - 8, ground_y + bob))

    # Periodic jump trigger (simulated clock tick)

    # Clock-driven triggers (preview-only unless firmware provides a clock).
    # If available, ctx.audio['clock'] contains hour/minute/second and *_changed flags.
    try:
        _clk = (audio or {}).get('clock') or {}
    except Exception:
        _clk = {}
    if jump_on_minute and bool(_clk.get('minute_changed')):
        # Debounce using minute value if present
        _m = _clk.get('minute')
        if _m is None or int(state.get('jump_last_minute', -1)) != int(_m):
            state['jump_last_minute'] = int(_m) if _m is not None else int(state.get('jump_last_minute', -1))
            state['jump_t0'] = float(t)
    if jump_on_second and bool(_clk.get('second_changed')):
        _s = _clk.get('second')
        if _s is None or int(state.get('jump_last_second', -1)) != int(_s):
            state['jump_last_second'] = int(_s) if _s is not None else int(state.get('jump_last_second', -1))
            state['jump_t0'] = float(t)

    if jump_period_s > 0.0:
        tick = int((t / max(0.001, jump_period_s)))
        last_tick = int(state.get("jump_last_tick", -1))
        if tick != last_tick:
            state["jump_last_tick"] = tick
            state["jump_t0"] = float(t)

    # Apply jump arc whenever a jump_t0 exists (periodic, clock, or jump_now edge).
    jt0 = float(state.get("jump_t0", -9999.0))
    age = float(t) - jt0
    if 0.0 <= age <= max(0.01, jump_duration_s):
        # Simple parabolic jump arc (0..1..0)
        u = age / max(0.01, jump_duration_s)
        arc = 4.0 * u * (1.0 - u)
        sy = int(sy - (jump_height * arc))
        sy = max(0, min(mh - 8, sy))

    # Resolve sprite frame
    sprite_bits = SPRITE
    if user_frames:
        try:
            fi = int((t * 6.0 * max(0.0, speed))) % max(1, len(user_frames))
            sprite_bits = user_frames[fi]
        except Exception:
            sprite_bits = user_frames[0]
    
    for py in range(8):
        for px in range(8):
            if _tile_bit(sprite_bits, px, py):
                set_xy(sx + px, sy + py, sprite_rgb)

    # If strip (mh==1), compress the 2D out buffer down to strip pixels by sampling.
    if mh == 1 and mw == n:
        return out
    # Otherwise, ensure length n (in case mw*mh != n).
    return out[:n] + [sky] * max(0, n - len(out))

def _arduino_emit(*, layout: dict, params: dict) -> str:
    # We rely on the global matrix helpers emitted by the exporter when MATRIX_WIDTH is defined.
    # For non-matrix layouts, we fall back to linear indexing.
    n = int(layout.get("num_leds") or 0)
    if n <= 0:
        n = 1

    speed = float((params or {}).get("speed", 1.0))
    br = float((params or {}).get("brightness", 1.0))
    col = (params or {}).get("color", (220, 40, 40))
    if not (isinstance(col, (list, tuple)) and len(col) == 3):
        col = (220, 40, 40)

    # Clamp brightness in code
    br = 0.0 if br < 0.0 else (1.0 if br > 1.0 else br)
    speed = 0.0 if speed < 0.0 else speed

    r, g, b = [int(x) & 255 for x in col]

    assets = _load_user_assets(params or {})
    tiles = assets.get("tiles") or {}
    frames = assets.get("frames") or [SPRITE]
    user_map = assets.get("map")
    legend = assets.get("legend") or {}

    tile_brick = tiles.get("brick", TILE_BRICK)
    tile_question = tiles.get("question", TILE_QUESTION)
    tile_grass = tiles.get("grass", TILE_GRASS)

    tile_brick_hex = ", ".join([f"0x{int(v)&0xFF:02X}" for v in tile_brick])
    tile_question_hex = ", ".join([f"0x{int(v)&0xFF:02X}" for v in tile_question])
    tile_grass_hex = ", ".join([f"0x{int(v)&0xFF:02X}" for v in tile_grass])

    # Sprite frames (8x8). If multiple frames, we emit a pointer table.
    sprite_frames_hex = []
    for fr in frames:
        sprite_frames_hex.append(", ".join([f"0x{int(v)&0xFF:02X}" for v in fr]))
    sprite_frames_block = "\n".join([f"  {{{h}}}," for h in sprite_frames_hex])



    # Optional tilemap (stored in params as list[str])
    tilemap_def = ""
    tilemap_flag = 0
    tilemap_w = 0
    tilemap_h = 0
    tilemap_flat = ""
    if user_map:
        try:
            tilemap_h = len(user_map)
            tilemap_w = max(1, max(len(r) for r in user_map))
            # normalize rows
            norm = [r.ljust(tilemap_w, ".") for r in user_map]
            flat = "".join(norm)
            # escape for C string literal chunks
            tilemap_flat = flat.replace("\\", "\\\\").replace('"', '\"')
            tilemap_flag = 1
            tilemap_def = f"""#define TILEMAP_HAS_USERMAP 1
static const uint16_t TILEMAP_W = {tilemap_w};
static const uint16_t TILEMAP_H = {tilemap_h};
static const char TILEMAP_CHARS[] PROGMEM = \"{tilemap_flat}\";
"""
        except Exception:
            tilemap_def = "#define TILEMAP_HAS_USERMAP 0\n"
            tilemap_flag = 0
    if not tilemap_def:
        tilemap_def = "#define TILEMAP_HAS_USERMAP 0\n"

    return f"""

// --- tilemap_sprite (Mario-clock-style) ------------------------------------------
// Params baked at export time (you can edit and re-export to change):
//   speed={speed:.3f}
//   brightness={br:.3f}
//   jump_period_s={jump_period_s:.3f}
//   jump_height={jump_height:.3f}
//   jump_duration_s={jump_duration_s:.3f}
//   sprite_color=({r},{g},{b})

{tilemap_def}
static const uint8_t TILE_BRICK[8] PROGMEM = {{
  {tile_brick_hex}
}};
static const uint8_t TILE_QUESTION[8] PROGMEM = {{
  {tile_question_hex}
}};
static const uint8_t TILE_GRASS[8] PROGMEM = {{
  {tile_grass_hex}
}};
/* sprite frames */
#define SPRITE_FRAME_COUNT {len(sprite_frames_hex)}
static const uint8_t SPRITE_FRAMES[SPRITE_FRAME_COUNT][8] PROGMEM = {{
{sprite_frames_block}
}};


static inline uint8_t tile_bit_P(const uint8_t* tile, uint8_t x, uint8_t y) {{
  if (x > 7 || y > 7) return 0;
  uint8_t row = pgm_read_byte(&tile[y]);
  return (row & (1 << (7 - x))) ? 1 : 0;
}}

static inline CRGB apply_br(CRGB c, float br) {{
  if (br < 0) br = 0;
  if (br > 1) br = 1;
  return CRGB((uint8_t)(c.r * br), (uint8_t)(c.g * br), (uint8_t)(c.b * br));
}}

static inline void set_xy_or_linear(uint16_t x, uint16_t y, CRGB c) {{
#ifdef MATRIX_WIDTH
  if (x >= MATRIX_WIDTH || y >= MATRIX_HEIGHT) return;
  uint16_t i = modulo_xy(x, y);
  MODULA_LED(i) = c;
#else
  // Strip fallback: map x to index
  uint16_t i = (uint16_t)(x % (uint16_t){n});
  leds[i] = c;
#endif
}}

void loop() {{
  static uint32_t t0 = millis();
  uint32_t now = millis();
  float t = (now - t0) * 0.001f;

  // Periodic jump trigger (simulated clock tick)
  const uint32_t JUMP_PERIOD_MS = (uint32_t)({jump_period_s:.3f}f * 1000.0f);
  const float JUMP_H = {jump_height:.3f}f;
  const float JUMP_D = {jump_duration_s:.3f}f;
  static uint32_t jump_last_ms = 0;
  static uint32_t jump_start_ms = 0;
  if (JUMP_PERIOD_MS > 0) {{
    if ((now - jump_last_ms) >= JUMP_PERIOD_MS) {{
      // keep phase stable even if frame rate jitters
      jump_last_ms = (jump_last_ms == 0) ? now : (jump_last_ms + JUMP_PERIOD_MS);
      jump_start_ms = now;
    }}
  }}


  const float SPEED = {speed:.6f}f;
  const float BR = {br:.6f}f;

  CRGB sky = apply_br(CRGB(6,10,22), BR);
  CRGB brick = apply_br(CRGB(120,40,18), BR);
  CRGB qbox = apply_br(CRGB(200,140,20), BR);
  CRGB grass = apply_br(CRGB(10,70,18), BR);
  CRGB spr = apply_br(CRGB({r},{g},{b}), BR);

#ifdef MATRIX_WIDTH
  const uint16_t mw = (uint16_t)MATRIX_WIDTH;
  const uint16_t mh = (uint16_t)MATRIX_HEIGHT;
#else
  const uint16_t mw = (uint16_t){n};
  const uint16_t mh = 1;
#endif

  // background
  for (uint16_t i=0; i<(uint16_t){n}; i++) {{
    leds[i] = sky;
  }}

  const uint8_t TS = 8;
  uint16_t scroll = 0;
  if (mw > 0) {{
    scroll = (uint16_t)fmodf(t * 12.0f * SPEED, (float)mw);
  }}

  // tiles
  for (uint16_t y=0; y<mh; y++) {{
    for (uint16_t x=0; x<mw; x++) {{
      // grass band at bottom
      if (y >= (mh > TS ? (mh - TS) : 0)) {{
        if (tile_bit_P(TILE_GRASS, (uint8_t)(x & 7), (uint8_t)(y & 7))) {{
          set_xy_or_linear(x, y, grass);
        }}
        continue;
      }}

      uint16_t tx = (uint16_t)((x + scroll) / TS);
      uint16_t ty = (uint16_t)(y / TS);

      #if TILEMAP_HAS_USERMAP
      uint16_t mtx = (uint16_t)(((x + scroll) / TS) % TILEMAP_W);
      uint16_t mty = (uint16_t)(((y) / TS) % TILEMAP_H);
      char ch = (char)pgm_read_byte(&TILEMAP_CHARS[(uint32_t)mty * (uint32_t)TILEMAP_W + (uint32_t)mtx]);
      const uint8_t* tile = NULL;
      uint8_t kind = 0;
      if (ch == 'B') {{ tile = TILE_BRICK; kind = 1; }}
      else if (ch == 'Q') {{ tile = TILE_QUESTION; kind = 2; }}
      else if (ch == 'G') {{ tile = TILE_GRASS; kind = 3; }}

      uint8_t px = (uint8_t)((x + scroll) & 7);
      uint8_t py = (uint8_t)(y & 7);
      if (tile && tile_bit_P(tile, px, py)) {{
        if (kind == 1) set_xy_or_linear(x, y, brick);
        else if (kind == 2) set_xy_or_linear(x, y, qbox);
        else set_xy_or_linear(x, y, grass);
      }}
#else
      uint16_t tx = (uint16_t)((x + scroll) / TS);
      uint16_t ty = (uint16_t)(y / TS);

      uint8_t tile_kind = 0;
      if ((ty % 3) == 1 && ((tx % 7) == 2 || (tx % 7) == 3)) tile_kind = 1;
      if ((ty % 5) == 2 && (tx % 11) == 5) tile_kind = 2;

      uint8_t px = (uint8_t)((x + scroll) & 7);
      uint8_t py = (uint8_t)(y & 7);

      if (tile_kind == 1) {{
        if (tile_bit_P(TILE_BRICK, px, py)) set_xy_or_linear(x, y, brick);
      }} else if (tile_kind == 2) {{
        if (tile_bit_P(TILE_QUESTION, px, py)) set_xy_or_linear(x, y, qbox);
      }}
#endif
    }}
  }}

// sprite
int16_t ground = (int16_t)mh - (int16_t)TS - 8;
float bobf = 2.0f * sinf(t * 6.0f * SPEED);
int16_t bob = (int16_t)bobf;
int16_t sx = (int16_t)((float)mw * 0.25f + (float)mw * 0.15f * sinf(t * 1.4f * SPEED));
int16_t sy = ground + bob;
if (sy < 0) sy = 0;
if (sy > (int16_t)mh - 8) sy = (int16_t)mh - 8;

// apply jump arc
if (JUMP_PERIOD_MS > 0 && jump_start_ms > 0) {{
  float age = (now - jump_start_ms) * 0.001f;
  if (age >= 0.0f && age <= (JUMP_D > 0.01f ? JUMP_D : 0.01f)) {{
    float u = age / (JUMP_D > 0.01f ? JUMP_D : 0.01f);
    float arc = 4.0f * u * (1.0f - u);
    sy = (int16_t)(sy - (int16_t)(JUMP_H * arc));
    if (sy < 0) sy = 0;
  }}
}}


uint8_t fi = 0;
if (SPRITE_FRAME_COUNT > 1) {{
  fi = (uint8_t)((uint32_t)(t * 8.0f * SPEED) % (uint32_t)SPRITE_FRAME_COUNT);
  }}

for (uint8_t py=0; py<8; py++) {{
  for (uint8_t px=0; px<8; px++) {{
    if (tile_bit_P(SPRITE_FRAMES[fi], px, py)) {{
      int16_t dx = sx + (int16_t)px;
      int16_t dy = sy + (int16_t)py;
      if (dx >= 0 && dy >= 0) {{
        set_xy_or_linear((uint16_t)dx, (uint16_t)dy, spr);
      }}
    }}
  }}
}}

  modulo_led_show();
  delay(1);
}}
"""

def register_tilemap_sprite():
    return register(BehaviorDef(
        "tilemap_sprite",
        title="Tilemap + Sprite (Mario-clock style)",
        uses=["speed", "brightness", "color"],
        preview_emit=_preview_emit,
        arduino_emit=_arduino_emit,
        capabilities={
            "shape": "matrix",
            "notes": "Simple 8x8 tilemap background with an 8x8 sprite. Best on cells/matrix layouts.",
        },
    ))