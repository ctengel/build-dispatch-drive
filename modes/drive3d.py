"""3D drive mode: the same controls as 2D drive, rendered in perspective.
C toggles cab (first person) / chase (third person); E throws the first
facing switch on the selected train's forward run."""

import math

import pygame

import config as C
from graph import next_driven
from modes.drive import DriveMode
from render3d import Camera3D


class Drive3DMode(DriveMode):
    name = "drive3d"
    hints = ("Up/W power  Down/S brake  Space e-stop  R reverse  G resume  "
             "Tab select  E switch ahead  C cab/chase")

    def __init__(self):
        self.cam = Camera3D(C.WIN_W, C.WIN_H)
        self.view = "chase"      # "cab" | "chase"
        self._chase = None       # smoothed chase-camera position
        self._yaw = 0.0          # last known train heading

    def handle_event(self, game, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_c:
            self.view = "cab" if self.view == "chase" else "chase"
            game.msg("%s view" % self.view)
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_e:
            self._throw_ahead(game)
        elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                         pygame.MOUSEMOTION):
            pass                 # 2D screen picking is meaningless here
        else:
            DriveMode.handle_event(self, game, ev)

    def _throw_ahead(self, game):
        """Cycle the first facing switch on the selected train's forward run."""
        t = game.selected
        if t is None:
            return
        world, datom = game.world, t.path[0]
        for _ in range(40):
            nxt = next_driven(world, datom)
            if nxt is None:
                break
            nc, _ni, ne = nxt
            if world.is_switch(nc, ne):
                world.cycle_switch(nc, ne)
                game.msg("switch ahead thrown")
                return
            datom = nxt
        game.msg("no switch ahead")

    def update(self, game):
        DriveMode.update(self, game)   # throttle keys + 2D camera follow
        cam, world, t = self.cam, game.world, game.selected
        cam.set_size(game.camera.w, game.camera.h)
        if t is None:
            # overview from south of the track centroid, looking north/down
            cells = list(world.tracks) or [(5, 3)]
            cx = sum(c[0] for c in cells) / len(cells) + 0.5
            cy = sum(c[1] for c in cells) / len(cells) + 0.5
            cam.pos = (cx, cy + 8.0, 10.0)
            cam.yaw = -math.pi / 2
            cam.pitch = -0.9
            self._chase = None
            return
        hx, hy = t.head_pos(world)
        bx, by = t.point_at_back(world, 0.6)
        if math.hypot(hx - bx, hy - by) > 1e-6:
            self._yaw = math.atan2(hy - by, hx - bx)
        yaw = self._yaw
        if self.view == "cab":
            cam.pos = (hx - math.cos(yaw) * 0.3,
                       hy - math.sin(yaw) * 0.3, C.CAB_HEIGHT)
            cam.yaw = yaw
            cam.pitch = -0.06
            self._chase = None
        else:
            tgt = (hx - math.cos(yaw) * C.CHASE_BACK,
                   hy - math.sin(yaw) * C.CHASE_BACK, C.CHASE_HEIGHT)
            if self._chase is None:
                self._chase = tgt
            self._chase = tuple(a + (b - a) * 0.1
                                for a, b in zip(self._chase, tgt))
            cam.pos = self._chase
            dx, dy = hx - cam.pos[0], hy - cam.pos[1]
            cam.yaw = math.atan2(dy, dx)
            cam.pitch = math.atan2(0.3 - cam.pos[2],
                                   math.hypot(dx, dy) or 1e-6)
