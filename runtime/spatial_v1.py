from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def _safe_bool(x: Any, default: bool = False) -> bool:
    try:
        if isinstance(x, bool):
            return x
        if isinstance(x, (int, float)):
            return bool(int(x))
        if isinstance(x, str):
            return x.strip().lower() in ("1","true","yes","y","on")
    except Exception:
        pass
    return default

def spatial_snapshot(layout: Dict[str, Any], spatial_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a JSON-safe snapshot describing coordinate spaces and transforms.

    This is *data only* (no callables) so it can be persisted and audited.
    """
    lay = layout if isinstance(layout, dict) else {}
    shape = str(lay.get("shape") or "").lower().strip()
    mw = int(lay.get("mw") or 0) if lay.get("mw") is not None else 0
    mh = int(lay.get("mh") or 0) if lay.get("mh") is not None else 0
    n = int(lay.get("num_leds") or lay.get("count") or 0)

    cfg = spatial_cfg if isinstance(spatial_cfg, dict) else {}
    enabled = _safe_bool(cfg.get("enabled", True), True)
    world_scale = _safe_float(cfg.get("world_scale", 1.0), 1.0)
    rotation_deg = _safe_float(cfg.get("rotation_deg", 0.0), 0.0)
    mirror_x = _safe_bool(cfg.get("mirror_x", False), False)
    mirror_y = _safe_bool(cfg.get("mirror_y", False), False)

    origin = cfg.get("origin")
    if isinstance(origin, (list, tuple)) and len(origin) >= 2:
        ox = _safe_float(origin[0], 0.0)
        oy = _safe_float(origin[1], 0.0)
    else:
        ox, oy = 0.0, 0.0

    coords = lay.get("coords")
    has_coords = isinstance(coords, list) and len(coords) == n and n > 0

    bounds = None
    if has_coords:
        try:
            xs = []
            ys = []
            for c in coords:
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    xs.append(int(c[0]))
                    ys.append(int(c[1]))
            if xs and ys:
                bounds = {"min_x": int(min(xs)), "max_x": int(max(xs)), "min_y": int(min(ys)), "max_y": int(max(ys))}
        except Exception:
            bounds = None

    # Named spaces:
    # - led: index space [0..n-1]
    # - layout: integer grid space (strip -> x=index,y=0; cells -> coords / (mw,mh))
    # - world: float space derived from layout by transform (origin/scale/rotation/mirror)
    return {
        "v": 1,
        "enabled": enabled,
        "shape": shape or None,
        "n_leds": n,
        "layout": {
            "mw": mw if mw > 0 else None,
            "mh": mh if mh > 0 else None,
            "has_coords": bool(has_coords),
            "coord_bounds": bounds,
        },
        "world": {
            "origin": [ox, oy],
            "scale": world_scale,
            "rotation_deg": rotation_deg,
            "mirror_x": mirror_x,
            "mirror_y": mirror_y,
        },
    }
