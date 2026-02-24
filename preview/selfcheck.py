"""Lightweight preview selfchecks (Phase 1)."""

from __future__ import annotations
from typing import Iterable, Optional


def check_selection_bounds(geom, selection: Optional[Iterable[int]]) -> Optional[str]:
    if selection is None:
        return None
    try:
        n = len(getattr(geom, "coords", []) or [])
    except Exception:
        return None
    for idx in selection:
        try:
            i = int(idx)
        except Exception:
            return f"selection index not int-like: {idx!r}"
        if i < 0 or i >= n:
            return f"selection index out of range: {i} (0..{max(0,n-1)})"
    return None

def check_viewport_roundtrip(vp, samples=5) -> Optional[str]:
    """Validate vp.world_to_screen and vp.screen_to_world are consistent."""
    if vp is None:
        return None
    if not hasattr(vp, "world_to_screen") or not hasattr(vp, "screen_to_world"):
        return "viewport missing world_to_screen/screen_to_world"
    try:
        pts = [(0.0, 0.0), (10.0, 10.0), (100.0, 50.0)]
        import random as _r
        for _ in range(max(0, int(samples))):
            pts.append((_r.uniform(-200, 200), _r.uniform(-200, 200)))
        for (wx, wy) in pts:
            sx, sy = vp.world_to_screen(wx, wy)
            wx2, wy2 = vp.screen_to_world(sx, sy)
            if abs(wx2 - wx) > 1e-6 or abs(wy2 - wy) > 1e-6:
                return f"viewport roundtrip mismatch: ({wx:.3f},{wy:.3f}) -> ({sx:.3f},{sy:.3f}) -> ({wx2:.3f},{wy2:.3f})"
    except Exception as e:
        return f"viewport roundtrip threw: {type(e).__name__}: {e}"
    return None
