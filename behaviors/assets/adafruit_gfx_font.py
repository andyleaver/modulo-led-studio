from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional


@dataclass(frozen=True)
class Glyph:
    bitmapOffset: int
    width: int
    height: int
    xAdvance: int
    xOffset: int
    yOffset: int


@dataclass(frozen=True)
class GFXFont:
    bitmaps: bytes
    glyphs: Dict[int, Glyph]  # map from ord(char) -> Glyph
    first: int
    last: int
    yAdvance: int


_HEX_BYTE_RE = re.compile(r"0x([0-9A-Fa-f]{1,2})")


def _extract_array_bytes(text: str, array_name: str) -> bytes:
    # Example: const uint8_t Super_Mario_Bros__24pt7bBitmaps[] PROGMEM = { ... };
    m = re.search(rf"{re.escape(array_name)}\s*\[\s*\]\s*PROGMEM\s*=\s*\{{(.*?)\}};", text, re.S)
    if not m:
        raise ValueError(f"Could not find bitmap array '{array_name}'")
    body = m.group(1)
    vals = [int(h, 16) for h in _HEX_BYTE_RE.findall(body)]
    return bytes(vals)


def _extract_glyphs(text: str, array_name: str) -> Dict[int, Glyph]:
    # Example: const GFXglyph Super_Mario_Bros__24pt7bGlyphs[] PROGMEM = { {offset,w,h,xAdv,xOff,yOff}, ... };
    m = re.search(rf"{re.escape(array_name)}\s*\[\s*\]\s*PROGMEM\s*=\s*\{{(.*?)\}};", text, re.S)
    if not m:
        raise ValueError(f"Could not find glyph array '{array_name}'")
    body = m.group(1)

    # Pull each {...} group
    entries = re.findall(r"\{\s*([^}]+?)\s*\}", body, re.S)
    glyphs: Dict[int, Glyph] = {}
    for i, ent in enumerate(entries):
        # remove comments
        ent = re.sub(r"/\*.*?\*/", "", ent, flags=re.S)
        ent = re.sub(r"//.*", "", ent)
        nums = [x.strip() for x in ent.split(',') if x.strip()]
        if len(nums) < 6:
            continue
        try:
            vals = [int(n, 0) for n in nums[:6]]
        except Exception:
            continue
        g = Glyph(*vals)
        glyphs[i] = g
    return glyphs


def load_gfx_font_from_header(header_path: str | Path, font_struct_name: Optional[str] = None) -> GFXFont:
    """Load an Adafruit_GFX GFXfont from a .h file.

    Returns a GFXFont with glyphs mapped by character code.

    Notes:
    - We assume the header defines: <Name>Bitmaps, <Name>Glyphs, and a GFXfont <Name>.
    - If font_struct_name is omitted, we auto-detect the first 'const GFXfont <name> PROGMEM = {' occurrence.
    """
    p = Path(header_path)
    text = p.read_text(encoding='utf-8', errors='ignore')

    if font_struct_name is None:
        m = re.search(r"const\s+GFXfont\s+(\w+)\s+PROGMEM\s*=\s*\{", text)
        if not m:
            raise ValueError("Could not detect GFXfont struct name")
        font_struct_name = m.group(1)

    # Deduce array names
    # Common pattern: <StructName>Bitmaps / <StructName>Glyphs
    bmp_name = font_struct_name + "Bitmaps"
    gly_name = font_struct_name + "Glyphs"

    bitmaps = _extract_array_bytes(text, bmp_name)
    glyph_entries = _extract_glyphs(text, gly_name)

    # Now read font struct init to get first,last,yAdvance
    # { (uint8_t*)Bitmaps, (GFXglyph*)Glyphs, 0x20, 0x7E, 45 };
    m = re.search(rf"const\s+GFXfont\s+{re.escape(font_struct_name)}\s+PROGMEM\s*=\s*\{{(.*?)\}};", text, re.S)
    if not m:
        raise ValueError(f"Could not find GFXfont struct '{font_struct_name}'")
    init = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
    init = re.sub(r"//.*", "", init)
    nums = [x.strip() for x in init.split(',') if x.strip()]
    if len(nums) < 5:
        raise ValueError("Unexpected GFXfont struct init")

    try:
        first = int(nums[2], 0)
        last = int(nums[3], 0)
        yAdvance = int(nums[4], 0)
    except Exception as e:
        raise ValueError("Failed parsing first/last/yAdvance") from e

    # Map glyph indices to character code
    glyphs: Dict[int, Glyph] = {}
    for code in range(first, last + 1):
        idx = code - first
        g = glyph_entries.get(idx)
        if g:
            glyphs[code] = g

    return GFXFont(bitmaps=bitmaps, glyphs=glyphs, first=first, last=last, yAdvance=yAdvance)


def draw_text_to_buffer(
    *,
    buf: List[Tuple[int, int, int]],
    mw: int,
    mh: int,
    font: GFXFont,
    text: str,
    x: int,
    y_baseline: int,
    color: Tuple[int, int, int],
    bg: Tuple[int, int, int] | None = None,
) -> None:
    """Draw text to a row-major RGB buffer.

    - x,y_baseline matches Adafruit_GFX: y is the baseline (not the top).
    - If bg is provided, pixels that are 0 in glyph are not drawn (still transparent); bg is not used to fill.
      (We keep this API so we can extend later.)
    """

    cursor_x = int(x)
    cursor_y = int(y_baseline)

    for ch in text:
        code = ord(ch)
        g = font.glyphs.get(code)
        if g is None:
            cursor_x += font.yAdvance // 2
            continue

        w, h = g.width, g.height
        if w <= 0 or h <= 0:
            cursor_x += g.xAdvance
            continue

        # Each row in the bitmap is packed MSB-first across bytes
        bo = g.bitmapOffset
        bit_index = 0
        for yy in range(h):
            for xx in range(w):
                byte = font.bitmaps[bo + (bit_index // 8)]
                mask = 0x80 >> (bit_index % 8)
                on = (byte & mask) != 0
                bit_index += 1
                if not on:
                    continue

                px = cursor_x + g.xOffset + xx
                py = cursor_y + g.yOffset + yy
                if 0 <= px < mw and 0 <= py < mh:
                    buf[py * mw + px] = color

        cursor_x += g.xAdvance
