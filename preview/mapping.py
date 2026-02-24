from __future__ import annotations
from dataclasses import dataclass

@dataclass
class MatrixMapping:
    w: int
    h: int
    serpentine: bool = False
    flip_x: bool = False
    flip_y: bool = False
    rotate: int = 0  # 0/90/180/270

def xy_index(mapping: MatrixMapping, x: int, y: int) -> int:
    """Match Arduino XY() logic used in export template."""
    w = max(1, int(mapping.w))
    h = max(1, int(mapping.h))
    rot = int(mapping.rotate or 0)
    rot = rot if rot in (0, 90, 180, 270) else 0

    # rotate
    xx, yy = int(x), int(y)
    if rot == 90:
        xx = (h - 1 - int(y))
        yy = int(x)
        w2, h2 = h, w
    elif rot == 180:
        xx = (w - 1 - int(x))
        yy = (h - 1 - int(y))
        w2, h2 = w, h
    elif rot == 270:
        xx = int(y)
        yy = (w - 1 - int(x))
        w2, h2 = h, w
    else:
        w2, h2 = w, h

    # flips operate in rotated space (matches export order)
    if mapping.flip_x:
        xx = (w2 - 1 - xx)
    if mapping.flip_y:
        yy = (h2 - 1 - yy)

    # clamp
    if xx < 0: xx = 0
    if yy < 0: yy = 0
    if xx >= w2: xx = w2 - 1
    if yy >= h2: yy = h2 - 1

    # serpentine rows
    if mapping.serpentine and (yy & 1):
        return int(yy * w2 + (w2 - 1 - xx))
    return int(yy * w2 + xx)

def logical_dims(mapping: MatrixMapping):
    """Dimensions after rotate (used for preview grid drawing)."""
    w = max(1, int(mapping.w))
    h = max(1, int(mapping.h))
    rot = int(mapping.rotate or 0)
    rot = rot if rot in (0, 90, 180, 270) else 0
    if rot in (90, 270):
        return h, w
    return w, h
