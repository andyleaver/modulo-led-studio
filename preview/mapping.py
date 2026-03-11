from __future__ import annotations
from dataclasses import dataclass

from core.surface_compat import normalize_surface_mapping

@dataclass
class MatrixMapping:
    w: int
    h: int
    serpentine: bool = False
    flip_x: bool = False
    flip_y: bool = False
    rotate: int = 0
    origin: str = "top_left"

def xy_index(*args, **kwargs) -> int:
    """Compatibility XY index resolver.

    Supported call styles:
      - xy_index(MatrixMapping, x, y)  (preview path)
      - xy_index(x, y, w, h, serpentine=..., flip_x=..., flip_y=..., rotate=..., origin=...) (parity probe path)
    """
    if len(args) >= 3 and isinstance(args[0], MatrixMapping):
        mapping = args[0]
        x = int(args[1])
        y = int(args[2])
        return _xy_index_mapping(mapping, x, y)

    if len(args) >= 4:
        x = int(args[0]); y = int(args[1]); w = int(args[2]); h = int(args[3])
        mapping_cfg = normalize_surface_mapping(kwargs)
        mm = MatrixMapping(
            w=w,
            h=h,
            serpentine=mapping_cfg["serpentine"],
            flip_x=mapping_cfg["flip_x"],
            flip_y=mapping_cfg["flip_y"],
            rotate=mapping_cfg["rotate"],
            origin=mapping_cfg["origin"],
        )
        return _xy_index_mapping(mm, x, y)

    raise TypeError("xy_index expects (MatrixMapping,x,y) or (x,y,w,h,...)")

def _xy_index_mapping(mapping: MatrixMapping, x: int, y: int) -> int:
    """Match Arduino XY() logic used in export template."""
    mapping_cfg = normalize_surface_mapping({
        "serpentine": getattr(mapping, "serpentine", False),
        "flip_x": getattr(mapping, "flip_x", False),
        "flip_y": getattr(mapping, "flip_y", False),
        "rotate": getattr(mapping, "rotate", 0),
        "origin": getattr(mapping, "origin", "top_left"),
    })
    w = max(1, int(mapping.w))
    h = max(1, int(mapping.h))
    rot = int(mapping_cfg["rotate"] or 0)

    # origin in unrotated space
    xx, yy = int(x), int(y)
    o = str(mapping_cfg["origin"] or 'top_left').lower()
    if 'right' in o:
        xx = (w - 1 - xx)
    if 'bottom' in o:
        yy = (h - 1 - yy)

    # rotate
    if rot == 90:
        xx, yy = (h - 1 - yy), xx
        w2, h2 = h, w
    elif rot == 180:
        xx, yy = (w - 1 - xx), (h - 1 - yy)
        w2, h2 = w, h
    elif rot == 270:
        xx, yy = yy, (w - 1 - xx)
        w2, h2 = h, w
    else:
        w2, h2 = w, h

    # flips operate in rotated space (matches export order)
    if mapping_cfg["flip_x"]:
        xx = (w2 - 1 - xx)
    if mapping_cfg["flip_y"]:
        yy = (h2 - 1 - yy)

    # clamp
    if xx < 0: xx = 0
    if yy < 0: yy = 0
    if xx >= w2: xx = w2 - 1
    if yy >= h2: yy = h2 - 1

    # serpentine rows
    if mapping_cfg["serpentine"] and (yy & 1):
        return int(yy * w2 + (w2 - 1 - xx))
    return int(yy * w2 + xx)

def logical_dims(mapping: MatrixMapping):
    """Dimensions after rotate (used for preview grid drawing)."""
    w = max(1, int(mapping.w))
    h = max(1, int(mapping.h))
    mapping_cfg = normalize_surface_mapping({
        "rotate": getattr(mapping, "rotate", 0),
    })
    rot = int(mapping_cfg["rotate"] or 0)
    if rot in (90, 270):
        return h, w
    return w, h
