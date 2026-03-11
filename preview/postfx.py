from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any
from core.surface_compat import canonical_surface_config, get_surface_kind_value

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

def build_surface_neighbors(surface: Dict[str, Any], radius: int = 1) -> Optional[List[List[int]]]:
    """Build neighbor index lists for canonical surface snapshots.

    Expects surface:
      - surface.kind == 'cells'
      - coords: list of (x,y) integer cell coordinates per LED index
    Returns:
      neighbors[i] = list of indices to average with i (includes i itself)
    """
    surface_cfg = canonical_surface_config(surface)
    if not isinstance(surface_cfg, dict):
        return None
    if get_surface_kind_value(surface_cfg, default="strip") != "cells":
        return None
    coords = surface_cfg.get("coords")
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

def apply_trail(frame: List[RGB], prev: Optional[List[RGB]], amount: float) -> Tuple[List[RGB], Optional[List[RGB]]]:
    """Temporal trail blend.

    Audit contracts:
      - When trail_amount == 0, output must be identical frame-to-frame (no history accumulation).
      - When trail toggles from OFF->ON, the first ON frame must NOT mix with older OFF history.
      - When ON, decay should preserve previous brightness without dimming current frame.

    Implementation (when ON): out = max(curr, prev * a) per channel.
    """
    a = _clamp01(amount)

    # Trail OFF: do not change the frame and do NOT accumulate/update history.
    if a <= 0.0:
        return frame, None

    # Trail ON but no valid history yet: initialize history to current frame.
    if prev is None or len(prev) != len(frame):
        return frame, list(frame)

    out: List[RGB] = []
    for (cr, cg, cb), (pr, pg, pb) in zip(frame, prev):
        nr = max(int(cr) & 255, int(pr * a) & 255)
        ng = max(int(cg) & 255, int(pg * a) & 255)
        nb = max(int(cb) & 255, int(pb * a) & 255)
        out.append((nr, ng, nb))

    # Persist trail state as the post-trail output.
    return out, out

def ensure_surface_coords(surface: dict):
    try:
        surface_cfg = canonical_surface_config(surface)
        if get_surface_kind_value(surface_cfg, default='strip') != 'cells':
            return
        coords = surface_cfg.get('coords')
        # Canonical dims keys are width/height; legacy mw/mh/matrix_w/matrix_h are import-only.
        w = int(surface_cfg.get('width') or 0)
        h = int(surface_cfg.get('height') or 0)
        if w <= 0 or h <= 0:
            return
        if not (isinstance(coords, list) and coords and isinstance(coords[0], (list, tuple))):
            surface['coords'] = [(x,y) for y in range(h) for x in range(w)]
    except Exception:
        return

# Compatibility wrappers for older layout-named callers.
def build_matrix_neighbors(layout: Dict[str, Any], radius: int = 1) -> Optional[List[List[int]]]:
    return build_surface_neighbors(layout, radius)

def _ensure_coords(layout: dict):
    return ensure_surface_coords(layout)

def apply_postfx(frame: List[RGB], *, surface: Optional[Dict[str, Any]] = None, layout: Optional[Dict[str, Any]] = None, postfx: Optional[Dict[str, Any]] = None,
                 prev: Optional[List[RGB]] = None, neighbors: Optional[List[List[int]]] = None) -> Tuple[List[RGB], Optional[List[RGB]]]:
    """Apply post-processing effects to an already-composited frame.

    Phase 7E:
      - Strip bleed (1D) + trails
      - Cells bleed (neighbor averaging) + trails

    Canonical live geometry flows through ``surface``. ``layout`` remains
    a compatibility alias only for older call sites.
    """
    surface_cfg = canonical_surface_config(surface)
    pf = dict(postfx or {})
    bleed_amount = pf.get("bleed_amount", 0.0)
    bleed_radius = pf.get("bleed_radius", 1)
    trail_amount = pf.get("trail_amount", 0.0)

    kind = get_surface_kind_value(surface_cfg, default="strip")

    out = frame
    if kind == "strip":
        out = apply_strip_bleed(out, float(bleed_amount or 0.0), int(bleed_radius or 1))
    elif kind == "cells":
        # neighbors must be supplied/cached by caller
        if neighbors is None:
            neighbors = build_surface_neighbors(surface_cfg, int(bleed_radius or 1))
        out = apply_matrix_bleed(out, float(bleed_amount or 0.0), neighbors)

    out, new_prev = apply_trail(out, prev, float(trail_amount or 0.0))
    return out, new_prev
