from __future__ import annotations

"""Particle pair counting (v1)

Reusable spatial-hash helper for particle/agent proximity/collision style rules.

This is intentionally small and deterministic:
- Inputs are plain lists of dicts with x/y floats.
- Uses grid hashing with cell size = radius.
- Counts unique unordered pairs within radius, optionally capped by max_pairs checked.

Returned counters can be published as events/signals by callers.
"""

from typing import List, Dict, Tuple
import math


def count_pairs_within_radius_v1(
    parts: List[Dict],
    radius: float,
    max_pairs_checked: int = 2000,
    mode: str = "both",
) -> Tuple[int, int]:
    """Return (near_count, collision_count).

    mode:
      - 'near' counts near only
      - 'collision' counts collision only
      - 'both' counts both (same threshold)
    """
    try:
        r = float(radius)
    except Exception:
        r = 0.0
    if r <= 0.0 or len(parts) < 2:
        return 0, 0

    mode = str(mode or "both").lower().strip()
    r2 = r * r

    cell = r
    if cell <= 0.0:
        cell = 1.0

    grid: Dict[Tuple[int, int], List[int]] = {}
    for idx_p, p in enumerate(parts):
        try:
            x0 = float(p.get("x", 0.0) or 0.0)
            y0 = float(p.get("y", 0.0) or 0.0)
        except Exception:
            x0, y0 = 0.0, 0.0
        cx = int(math.floor(x0 / cell))
        cy = int(math.floor(y0 / cell))
        grid.setdefault((cx, cy), []).append(idx_p)

    checked = 0
    near = 0
    coll = 0

    # Compare within cell and neighbor cells
    for (cx, cy), lst in grid.items():
        for nx in (cx - 1, cx, cx + 1):
            for ny in (cy - 1, cy, cy + 1):
                lst2 = grid.get((nx, ny))
                if not lst2:
                    continue
                for ai in lst:
                    ax = float(parts[ai].get("x", 0.0) or 0.0)
                    ay = float(parts[ai].get("y", 0.0) or 0.0)
                    for bi in lst2:
                        if bi <= ai:
                            continue
                        checked += 1
                        if max_pairs_checked > 0 and checked > max_pairs_checked:
                            return near, coll
                        bx = float(parts[bi].get("x", 0.0) or 0.0)
                        by = float(parts[bi].get("y", 0.0) or 0.0)
                        dx = ax - bx
                        dy = ay - by
                        if (dx * dx + dy * dy) <= r2:
                            if mode in ("near", "both"):
                                near += 1
                            if mode in ("collision", "both"):
                                coll += 1
    return near, coll
