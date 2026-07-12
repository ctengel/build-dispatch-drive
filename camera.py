"""Pan/zoom transform between world cell coordinates and screen pixels."""

from config import SCALE_MIN, SCALE_MAX, SCALE_START


class Camera:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.scale = SCALE_START     # pixels per cell
        self.cx, self.cy = 5.0, 3.0  # world point at screen center

    def world_to_screen(self, wx, wy):
        return (int((wx - self.cx) * self.scale + self.w / 2),
                int((wy - self.cy) * self.scale + self.h / 2))

    def screen_to_world(self, sx, sy):
        return ((sx - self.w / 2) / self.scale + self.cx,
                (sy - self.h / 2) / self.scale + self.cy)

    def cell_at(self, sx, sy):
        wx, wy = self.screen_to_world(sx, sy)
        import math
        return (math.floor(wx), math.floor(wy))

    def pan_pixels(self, dx, dy):
        self.cx -= dx / self.scale
        self.cy -= dy / self.scale

    def zoom_at(self, sx, sy, factor):
        wx, wy = self.screen_to_world(sx, sy)
        self.scale = max(SCALE_MIN, min(SCALE_MAX, self.scale * factor))
        # keep the point under the cursor fixed
        self.cx = wx - (sx - self.w / 2) / self.scale
        self.cy = wy - (sy - self.h / 2) / self.scale

    def follow(self, wx, wy, k=0.08):
        self.cx += (wx - self.cx) * k
        self.cy += (wy - self.cy) * k

    def visible_cells(self):
        x0, y0 = self.screen_to_world(0, 0)
        x1, y1 = self.screen_to_world(self.w, self.h)
        import math
        return (math.floor(x0) - 1, math.floor(y0) - 1,
                math.ceil(x1) + 1, math.ceil(y1) + 1)
