from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any

RGB = Tuple[int, int, int]

def _clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        x = 0.0
    if x < 0.0: x = 0.0
    if x > 1.0: x = 1.0
    return x

def apply_strip_bleed(frame: List[RGB], amount: float, radius: int) -> List[RGB]:
    a = _clamp01(amount)
    if a <= 0.0:
        return frame
    r = int(radius or 1)
    if r < 1:
        return frame
    n = len(frame)
    out: List[RGB] = []
    for i in range(n):
        lo = max(0, i - r)
        hi = min(n - 1, i + r)
        cnt = (hi - lo + 1)
        sr = sg = sb = 0
        for j in range(lo, hi + 1):
            cr, cg, cb = frame[j]
            sr += int(cr); sg += int(cg); sb += int(cb)
        ar = sr / cnt; ag = sg / cnt; ab = sb / cnt
        cr, cg, cb = frame[i]
        nr = int(cr * (1.0 - a) + ar * a) & 255
        ng = int(cg * (1.0 - a) + ag * a) & 255
        nb = int(cb * (1.0 - a) + ab * a) & 255
        out.append((nr, ng, nb))
    return out

def build_matrix_neighbors(layout: Dict[str, Any], radius: int = 1) -> Optional[List[List[int]]]:
    """Build neighbor index lists for matrix/cells layouts.

    Expects layout:
      - shape == 'cells'
      - coords: list of (x,y) integer cell coordinates per LED index
    Returns:
      neighbors[i] = list of indices to average with i (includes i itself)
    """
    if not isinstance(layout, dict):
        return None
    shape = str(layout.get("shape","")).lower().strip()
    if shape != "cells":
        return None
    coords = layout.get("coords")
    if not isinstance(coords, list) or not coords:
        return None
    r = int(radius or 1)
    if r < 1:
        r = 1
    # map position to index
    pos_to_idx: Dict[Tuple[int,int], int] = {}
    for i, xy in enumerate(coords):
        try:
            x, y = int(xy[0]), int(xy[1])
        except Exception:
            continue
        pos_to_idx[(x,y)] = i

    neighbors: List[List[int]] = []
    for i, xy in enumerate(coords):
        try:
            x, y = int(xy[0]), int(xy[1])
        except Exception:
            neighbors.append([i])
            continue
        inds = [i]
        # radius 1 only for now (Phase 7E). If r>1, include manhattan shell up to r.
        for dx in range(-r, r+1):
            for dy in range(-r, r+1):
                if dx == 0 and dy == 0:
                    continue
                # Use manhattan distance to avoid huge blur cost.
                if abs(dx) + abs(dy) > r:
                    continue
                j = pos_to_idx.get((x+dx, y+dy))
                if j is not None:
                    inds.append(j)
        neighbors.append(inds)
    return neighbors

def apply_matrix_bleed(frame: List[RGB], amount: float, neighbors: Optional[List[List[int]]]) -> List[RGB]:
    a = _clamp01(amount)
    if a <= 0.0 or not neighbors or len(neighbors) != len(frame):
        return frame
    out: List[RGB] = []
    for i, inds in enumerate(neighbors):
        sr = sg = sb = 0
        cnt = len(inds) if inds else 1
        for j in inds:
            cr, cg, cb = frame[j]
            sr += int(cr); sg += int(cg); sb += int(cb)
        ar = sr / cnt; ag = sg / cnt; ab = sb / cnt
        cr, cg, cb = frame[i]
        nr = int(cr * (1.0 - a) + ar * a) & 255
        ng = int(cg * (1.0 - a) + ag * a) & 255
        nb = int(cb * (1.0 - a) + ab * a) & 255
        out.append((nr, ng, nb))
    return out

def apply_trail(frame: List[RGB], prev: Optional[List[RGB]], amount: float) -> Tuple[List[RGB], List[RGB]]:
    a = _clamp01(amount)
    if a <= 0.0 or prev is None or len(prev) != len(frame):
        return frame, list(frame)
    out: List[RGB] = []
    for (cr, cg, cb), (pr, pg, pb) in zip(frame, prev):
        nr = int(pr * a + cr * (1.0 - a)) & 255
        ng = int(pg * a + cg * (1.0 - a)) & 255
        nb = int(pb * a + cb * (1.0 - a)) & 255
        out.append((nr, ng, nb))
    return out, out

def apply_postfx(frame: List[RGB], *, layout: Dict[str, Any], postfx: Optional[Dict[str, Any]],
                 prev: Optional[List[RGB]] = None, neighbors: Optional[List[List[int]]] = None) -> Tuple[List[RGB], Optional[List[RGB]]]:
    """Apply post-processing effects to an already-composited frame.

    Phase 7E:
      - Strip bleed (1D) + trails
      - Matrix/cells bleed (neighbor averaging) + trails
    """
    pf = dict(postfx or {})
    bleed_amount = pf.get("bleed_amount", 0.0)
    bleed_radius = pf.get("bleed_radius", 1)
    trail_amount = pf.get("trail_amount", 0.0)

    shape = str((layout or {}).get("shape","")).lower().strip()

    out = frame
    if shape == "strip":
        out = apply_strip_bleed(out, float(bleed_amount or 0.0), int(bleed_radius or 1))
    elif shape == "cells":
        # neighbors must be supplied/cached by caller
        out = apply_matrix_bleed(out, float(bleed_amount or 0.0), neighbors)

    out, new_prev = apply_trail(out, prev, float(trail_amount or 0.0))
    return out, new_prev
