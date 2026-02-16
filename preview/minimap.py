from __future__ import annotations
from dataclasses import dataclass

from .viewport import Viewport
from .engine import GridGeom

@dataclass
class MinimapRect:
    x0: int
    y0: int
    x1: int
    y1: int

def compute_minimap_rect(canvas_w: int, canvas_h: int, pad: int = 10, size: int = 160) -> MinimapRect:
    x1 = canvas_w - pad
    y1 = canvas_h - pad
    x0 = max(pad, x1 - size)
    y0 = max(pad, y1 - size)
    return MinimapRect(x0, y0, x1, y1)

def world_bounds(geom: GridGeom):
    xs = []
    ys = []
    if geom.coords:
        for x0,y0,x1,y1 in geom.coords:
            xs.extend([x0,x1])
            ys.extend([y0,y1])
    if not xs: xs=[0.0,1.0]
    if not ys: ys=[0.0,1.0]
    return (min(xs), min(ys), max(xs), max(ys))

def world_to_minimap(mini: MinimapRect, wx: float, wy: float, bounds):
    bx0,by0,bx1,by1 = bounds
    bw = max(1e-6, bx1-bx0)
    bh = max(1e-6, by1-by0)
    u = (wx-bx0)/bw
    v = (wy-by0)/bh
    x = mini.x0 + u*(mini.x1-mini.x0)
    y = mini.y0 + v*(mini.y1-mini.y0)
    return x,y

def viewport_to_minimap_rect(vp: Viewport, geom: GridGeom, mini: MinimapRect):
    bounds = world_bounds(geom)
    bx0,by0,bx1,by1 = bounds
    w_tl = vp.screen_to_world(0,0)
    w_br = vp.screen_to_world(vp.w, vp.h)
    wx0, wy0 = w_tl
    wx1, wy1 = w_br
    wx0 = max(bx0, min(bx1, wx0))
    wx1 = max(bx0, min(bx1, wx1))
    wy0 = max(by0, min(by1, wy0))
    wy1 = max(by0, min(by1, wy1))
    x0,y0 = world_to_minimap(mini, wx0, wy0, bounds)
    x1,y1 = world_to_minimap(mini, wx1, wy1, bounds)
    rx0, rx1 = (x0,x1) if x0<=x1 else (x1,x0)
    ry0, ry1 = (y0,y1) if y0<=y1 else (y1,y0)
    return (int(rx0), int(ry0), int(rx1), int(ry1)), bounds

def point_in_minimap(x: int, y: int, mini: MinimapRect) -> bool:
    return mini.x0 <= x <= mini.x1 and mini.y0 <= y <= mini.y1

def minimap_to_world(mini: MinimapRect, x: float, y: float, bounds):
    bx0,by0,bx1,by1 = bounds
    u = (x - mini.x0) / max(1e-6, (mini.x1-mini.x0))
    v = (y - mini.y0) / max(1e-6, (mini.y1-mini.y0))
    wx = bx0 + u*(bx1-bx0)
    wy = by0 + v*(by1-by0)
    return wx, wy
