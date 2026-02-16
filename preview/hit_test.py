from __future__ import annotations
from typing import Optional, Tuple

from .engine import Geometry

def hit_test(geom: Geometry, wx: float, wy: float) -> Optional[int]:
    """Return LED index at world point, or None."""
    if geom.shape == "strip":
        # strip: points list are at y=0; treat as small radius around each point
        best = None
        best_d2 = None
        for i, (x,y) in enumerate(geom.points):
            dx = wx - x
            dy = wy - y
            d2 = dx*dx + dy*dy
            if best is None or d2 < best_d2:
                best = i
                best_d2 = d2
        if best is None:
            return None
        # accept if within radius ~ half spacing
        if geom.points and len(geom.points) >= 2:
            sx = geom.points[1][0] - geom.points[0][0]
            r2 = (abs(sx)*0.6)**2
        else:
            r2 = (10.0)**2
        return best if best_d2 is not None and best_d2 <= r2 else None

    if geom.shape == "cells":
        # cells: rects is list of (x0,y0,x1,y1)
        for i, (x0,y0,x1,y1) in enumerate(geom.rects or []):
            if wx >= x0 and wx <= x1 and wy >= y0 and wy <= y1:
                return i
        return None

    return None
