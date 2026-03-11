from __future__ import annotations

from typing import Optional

from .engine import Geometry


def hit_test(geom: Geometry, wx: float, wy: float) -> Optional[int]:
    """Return LED index at world point, or None."""
    for i, rect in enumerate(geom.coords or []):
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        if x0 <= wx <= x1 and y0 <= wy <= y1:
            return i
    return None
