class Viewport:
    def __init__(self, scale=1.0, ox=0.0, oy=0.0):
        self.scale = float(scale)
        self.ox = float(ox)
        self.oy = float(oy)
        self.w = 1
        self.h = 1
        self.clamp()

    def set_size(self, w: int, h: int):
        self.w = max(1, int(w))
        self.h = max(1, int(h))

    def clamp(self):
        if self.scale < 0.2:
            self.scale = 0.2
        if self.scale > 8.0:
            self.scale = 8.0

    def world_to_screen(self, x, y):
        return (x * self.scale + self.ox, y * self.scale + self.oy)

    def screen_to_world(self, x, y):
        return ((x - self.ox) / self.scale, (y - self.oy) / self.scale)

    def zoom_at(self, sx: float, sy: float, factor: float):
        # Zoom around a screen point.
        wx, wy = self.screen_to_world(sx, sy)
        self.scale *= float(factor)
        self.clamp()
        self.ox = float(sx) - wx * self.scale
        self.oy = float(sy) - wy * self.scale

    def zoom_about(self, sx, sy, direction, factor=1.25):
        self.zoom_at(sx, sy, factor if direction > 0 else (1.0 / factor))

    def pan_by(self, dx, dy):
        self.ox += dx
        self.oy += dy

    def center_on(self, wx: float, wy: float):
        # set ox/oy so that world point is at the center of screen
        self.ox = (self.w * 0.5) - (wx * self.scale)
        self.oy = (self.h * 0.5) - (wy * self.scale)
