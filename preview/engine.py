from __future__ import annotations
from dataclasses import dataclass

from .mapping import MatrixMapping, xy_index, logical_dims
from preview.parity import ParityConfig, finalize_pixel
from typing import List, Optional, Sequence, Set, Tuple

from .viewport import Viewport

RGB = Tuple[int,int,int]
RC = Tuple[int,int]

@dataclass
class GridGeom:
    shape: str              # 'strip' or 'cells'
    n: int
    mw: int = 0
    mh: int = 0
    cell: float = 20.0
    gx: float = 0.0
    gy: float = 0.0
    coords: Optional[List[Tuple[float,float,float,float]]] = None

def build_strip_geom(n: int, *, cell: float=18.0, pad: float=2.0, gx: float=0.0, gy: float=0.0) -> GridGeom:
    coords = []
    x = gx
    for _ in range(int(n)):
        coords.append((x, gy, x+cell, gy+cell))
        x += cell + pad
    return GridGeom(shape="strip", n=int(n), cell=cell, gx=gx, gy=gy, coords=coords)

def build_cells_geom(mw: int, mh: int, cell: float, *, gx: float=0.0, gy: float=0.0) -> GridGeom:
    mw = int(mw); mh = int(mh)
    n = mw * mh
    coords = []
    for r in range(mh):
        for c in range(mw):
            x0 = gx + c*cell
            y0 = gy + r*cell
            coords.append((x0, y0, x0+cell, y0+cell))
    return GridGeom(shape="cells", n=n, mw=mw, mh=mh, cell=cell, gx=gx, gy=gy, coords=coords)

def build_cells_geom(mw: int, mh: int, cell: int, *, serpentine: bool=False, flip_x: bool=False, flip_y: bool=False, rotate: int=0) -> GridGeom:
    mw = max(1, int(mw))
    mh = max(1, int(mh))
    cell = max(4, int(cell))

    mapping = MatrixMapping(w=mw, h=mh, serpentine=bool(serpentine), flip_x=bool(flip_x), flip_y=bool(flip_y), rotate=int(rotate or 0))
    lw, lh = logical_dims(mapping)  # dimensions after rotate for visual grid
    n = lw * lh

    coords = [None] * n  # by LED index
    # For each visual cell (x,y in logical space), compute LED index using mapping
    for y in range(lh):
        for x in range(lw):
            idx = xy_index(mapping, x, y)
            x0 = x * cell
            y0 = y * cell
            x1 = x0 + cell
            y1 = y0 + cell
            if 0 <= idx < n:
                coords[idx] = (float(x0), float(y0), float(x1), float(y1))

    # fill any gaps safely (shouldn't happen) with sequential cells
    for i in range(n):
        if coords[i] is None:
            x = i % lw
            y = i // lw
            x0 = x * cell
            y0 = y * cell
            coords[i] = (float(x0), float(y0), float(x0 + cell), float(y0 + cell))

    return GridGeom(n=n, shape="cells", coords=coords, mw=lw, mh=lh)

def draw(
    canvas,
    geom: GridGeom,
    leds: Sequence[RGB],
    vp: Viewport,
    *,
    selection: Optional[Sequence[int]] = None,
    selected_cells: Optional[Set[RC]] = None,
    selected_indices: Optional[Set[int]] = None,
):
    """Render the preview.

    Notes:
      - Cells layouts use (row,col) selection via selected_cells.
      - Strip layouts use index-based selection via selected_indices.
    """
    selected_cells = selected_cells or set()
    selected_indices = selected_indices or set()
    if selection is not None:
        try:
            selected_indices = set(selection)
        except Exception:
            pass
    canvas.delete("all")
    w = max(1, canvas.winfo_width())
    h = max(1, canvas.winfo_height())
    canvas.create_rectangle(0, 0, w, h, fill="#000000", outline="")
    cfg = ParityConfig()
    # Subtle crosshair so users can tell the preview is alive even when all pixels are black
    canvas.create_line(0, h//2, w, h//2, fill="#101010")
    canvas.create_line(w//2, 0, w//2, h, fill="#101010")
    if not geom.coords:
        return
    margin = 50
    for idx, (x0,y0,x1,y1) in enumerate(geom.coords):
        sx0, sy0 = vp.world_to_screen(x0, y0)
        sx1, sy1 = vp.world_to_screen(x1, y1)
        if sx1 < -margin or sy1 < -margin or sx0 > w+margin or sy0 > h+margin:
            continue

        # Selection truth: selection is always authoritative by LED index.
        if idx in selected_indices:
            sel = True
        elif geom.shape == "cells":
            row = idx // max(1, geom.mw)
            col = idx % max(1, geom.mw)
            sel = (row, col) in selected_cells
        else:
            sel = False

        r,g,b = leds[idx] if idx < len(leds) else (0,0,0)
        r, g, b = finalize_pixel((int(r)&255, int(g)&255, int(b)&255), cfg)
        
        fill = f"#{r:02x}{g:02x}{b:02x}"
        fill_sel = fill
        if sel:
            # Lighten selected cells for strong visibility
            r2 = min(255, int(r + (255 - r) * 0.35))
            g2 = min(255, int(g + (255 - g) * 0.35))
            b2 = min(255, int(b + (255 - b) * 0.35))
            fill_sel = f"#{r2:02x}{g2:02x}{b2:02x}"

        outline = "#44aaff" if sel else "#606060"
        lw = 2 if sel else 1
        canvas.create_rectangle(sx0, sy0, sx1, sy1, fill=fill_sel if sel else fill, outline=outline, width=lw)


def apply_modulotors(params: dict, modulotors: list, audio: dict, t: float) -> dict:
    """Apply modulotors in list order. Each mod may be disabled.
    Supports:
      - kind='audio' (source from AudioSim)
      - kind='lfo'   (sine LFO with freq Hz and phase 0..1)
    Curves:
      - linear, invert, abs, pow2, pow3
    """
    out = dict(params or {})
    for m in (modulotors or []):
        if not isinstance(m, dict):
            continue
        if not bool(m.get("enabled", True)):
            continue
        target = m.get("target")
        if not target:
            continue

        kind = (m.get("kind", "audio") or "audio").lower()
        curve = (m.get("curve", "linear") or "linear").lower()
        amount = float(m.get("amount", 0.0) or 0.0)
        bias = float(m.get("bias", 0.0) or 0.0)

        if kind == "lfo":
            freq = float(m.get("freq", 1.0) or 1.0)
            phase = float(m.get("phase", 0.0) or 0.0)
            # sine 0..1
            v = 0.5 + 0.5 * math.sin(2.0 * math.pi * (freq * float(t) + phase))
        else:
            src = m.get("source", "energy")
            v = float(audio.get(src, 0.0) if isinstance(audio, dict) else 0.0)
            v = max(0.0, min(1.0, v))

        v = _curve_apply(v, curve)

        base = out.get(target, 0.0)
        try:
            basef = float(base)
        except Exception:
            continue

        mod = (v - 0.5) * 2.0 * amount + bias
        out[target] = clamp_to_param_range(str(target), basef + mod)
    return out


def clamp_to_param_range(key: str, value: float):
    """Clamp a numeric value to the PARAMS registry min/max and coerce int params."""
    try:
        from params.registry import PARAMS
    except Exception:
        return value
    meta = PARAMS.get(key, {})
    t = meta.get("type", "float")
    mn = meta.get("min", None)
    mx = meta.get("max", None)
    v = float(value)
    if mn is not None:
        v = max(float(mn), v)
    if mx is not None:
        v = min(float(mx), v)
    if t == "int":
        v = int(round(v))
    return v


def _curve_apply(v: float, curve: str) -> float:
    v = max(0.0, min(1.0, float(v)))
    c = (curve or "linear").lower()
    if c == "invert":
        return 1.0 - v
    if c == "abs":
        return abs((v - 0.5) * 2.0)  # 0 at mid, 1 at ends
    if c == "pow2":
        return v * v
    if c == "pow3":
        return v * v * v
    return v