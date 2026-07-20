"""Software 3D renderer for the drive view (mode 4). Pure pygame:
perspective projection, near-plane clipping, painter-sorted flat-shaded
faces. Coordinates: grid cell (x, y) stays (x, y); the third component h
is height above the map plane.

Train cars are drawn from a mesh: a list of (verts, color) faces, verts
in car-local coordinates (+x forward, +y right, +h up, origin at the
car's center on the ground) wound counter-clockwise seen from outside.
`box_mesh` builds the default rectangular prism; a future model loader
(OBJ etc.) only needs to emit the same face-list structure from
`car_mesh` to replace the boxes with real models.
"""

import math

import pygame

import blocks
import config as C
from geometry import GEOM, DELTA, end_point, point_on
from render import text

NEAR = 0.05          # near clip plane, cells
BALLAST_HW = 0.16    # ballast ribbon half-width
RAIL_OFF = 0.07      # rail offset from the track centerline
RAIL_W = 0.045       # rail width (world units, scaled by depth)

# unit vector pointing toward the light (up and a little north-west)
_LIGHT = (-0.30, -0.40, 0.87)


class Camera3D:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.pos = (0.0, 0.0, 1.5)   # (x, y, h)
        self.yaw = 0.0               # heading in the map plane, atan2(dy, dx)
        self.pitch = 0.0             # > 0 looks up
        self.fov = math.radians(C.FOV_DEG)

    def set_size(self, w, h):
        self.w, self.h = w, h

    def begin(self):
        """Cache per-frame trig and focal length."""
        self._cy, self._sy = math.cos(self.yaw), math.sin(self.yaw)
        self._cp, self._sp = math.cos(self.pitch), math.sin(self.pitch)
        self._f = (self.w / 2) / math.tan(self.fov / 2)

    def to_cam(self, p):
        """World (x, y, h) -> camera space (right, up, depth)."""
        dx, dy, dh = p[0] - self.pos[0], p[1] - self.pos[1], p[2] - self.pos[2]
        fwd = dx * self._cy + dy * self._sy
        r = -dx * self._sy + dy * self._cy
        return (r,
                dh * self._cp - fwd * self._sp,
                fwd * self._cp + dh * self._sp)

    def project(self, cp):
        return (self.w / 2 + self._f * cp[0] / cp[2],
                self.h / 2 - self._f * cp[1] / cp[2])


# ---- near-plane clipping (camera space) ----

def clip_poly(pts):
    out = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if a[2] >= NEAR:
            out.append(a)
        if (a[2] >= NEAR) != (b[2] >= NEAR):
            t = (NEAR - a[2]) / (b[2] - a[2])
            out.append((a[0] + (b[0] - a[0]) * t,
                        a[1] + (b[1] - a[1]) * t, NEAR))
    return out


def clip_seg(a, b):
    if a[2] < NEAR and b[2] < NEAR:
        return None
    if a[2] >= NEAR and b[2] >= NEAR:
        return a, b
    t = (NEAR - a[2]) / (b[2] - a[2])
    m = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, NEAR)
    return (a, m) if a[2] >= NEAR else (m, b)


# ---- meshes ----

def box_mesh(length, width, height, color):
    """Rectangular prism on the ground, centered at the origin, +x forward."""
    x0, x1 = -length / 2, length / 2
    y0, y1 = -width / 2, width / 2
    h = height
    return [
        ([(x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h)], color),   # roof
        ([(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)], color),   # front
        ([(x0, y1, 0), (x0, y0, 0), (x0, y0, h), (x0, y1, h)], color),   # back
        ([(x1, y1, 0), (x0, y1, 0), (x0, y1, h), (x1, y1, h)], color),   # right
        ([(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (x0, y0, h)], color),   # left
    ]


def car_mesh(train, k, length):
    """Mesh for car k of `train`. This is the seam for real 3D models:
    return any face list in car-local coordinates instead of a box."""
    if k == 0:
        color = {"driven": C.COL_TRAIN_HEAD_DRIVEN,
                 "running": C.COL_TRAIN_HEAD_AI,
                 "dwelling": C.COL_TRAIN_HEAD_AI}.get(train.state,
                                                      C.COL_TRAIN_HEAD_IDLE)
        return box_mesh(length, C.CAR_W, C.CAR_H + 0.06, color)
    return box_mesh(length, C.CAR_W, C.CAR_H, C.COL_TRAIN_BODY)


def _shade(color, n):
    mag = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) or 1.0
    d = (n[0] * _LIGHT[0] + n[1] * _LIGHT[1] + n[2] * _LIGHT[2]) / mag
    k = 0.60 + 0.40 * max(0.0, d)
    return tuple(min(255, int(c * k)) for c in color)


# ---- draw-list helpers ----

def _add_poly(items, cam, wpts, color):
    cpts = [cam.to_cam(p) for p in wpts]
    if all(p[2] < NEAR for p in cpts):
        return
    items.append((sum(p[2] for p in cpts) / len(cpts), "poly", cpts, color))


def _add_line(items, cam, a, b, color, wwidth):
    ca, cb = cam.to_cam(a), cam.to_cam(b)
    if ca[2] < NEAR and cb[2] < NEAR:
        return
    items.append(((ca[2] + cb[2]) / 2, "line", (ca, cb), (color, wwidth)))


def _add_disc(items, cam, p, color, wr, outline=None):
    cp = cam.to_cam(p)
    if cp[2] < NEAR:
        return
    items.append((cp[2], "disc", cp, (color, wr, outline)))


def _add_mesh(items, cam, mesh, x, y, yaw):
    """Place a local-space mesh at (x, y) rotated by yaw; backface-cull
    and flat-shade each face."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    for verts, color in mesh:
        wv = [(x + vx * cy - vy * sy, y + vx * sy + vy * cy, vh)
              for vx, vy, vh in verts]
        ax, ay, az = (wv[1][0] - wv[0][0], wv[1][1] - wv[0][1],
                      wv[1][2] - wv[0][2])
        bx, by, bz = (wv[2][0] - wv[0][0], wv[2][1] - wv[0][1],
                      wv[2][2] - wv[0][2])
        n = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
        c = (sum(v[0] for v in wv) / len(wv), sum(v[1] for v in wv) / len(wv),
             sum(v[2] for v in wv) / len(wv))
        view = (c[0] - cam.pos[0], c[1] - cam.pos[1], c[2] - cam.pos[2])
        if n[0] * view[0] + n[1] * view[1] + n[2] * view[2] >= 0:
            continue
        _add_poly(items, cam, wv, _shade(color, n))


def _draw_items(surf, cam, items):
    items.sort(key=lambda it: -it[0])
    for depth, kind, geo, extra in items:
        if kind == "poly":
            pts = clip_poly(geo)
            if len(pts) >= 3:
                pygame.draw.polygon(surf, extra, [cam.project(p) for p in pts])
        elif kind == "line":
            seg = clip_seg(*geo)
            if seg is not None:
                color, wwidth = extra
                pygame.draw.line(surf, color, cam.project(seg[0]),
                                 cam.project(seg[1]),
                                 max(1, int(cam._f * wwidth / depth)))
        else:  # disc
            color, wr, outline = extra
            r = cam._f * wr / depth
            if r >= 1:
                px, py = cam.project(geo)
                pygame.draw.circle(surf, color, (px, py), r)
                if outline is not None:
                    pygame.draw.circle(surf, outline, (px, py), r, 1)


# ---- scene ----

def draw_world(surf, game, mode):
    cam, world = mode.cam, game.world
    cam.set_size(*surf.get_size())
    cam.begin()

    # sky above the horizon, ground below
    w, h = cam.w, cam.h
    horizon = max(0, min(h, int(h / 2 + cam._f * math.tan(cam.pitch))))
    surf.fill(C.COL_SKY, (0, 0, w, horizon))
    surf.fill(C.COL_GROUND, (0, horizon, w, h - horizon))

    r2 = C.DRAW_RADIUS_3D ** 2

    def near_cell(cell):
        dx, dy = cell[0] + 0.5 - cam.pos[0], cell[1] + 0.5 - cam.pos[1]
        return dx * dx + dy * dy <= r2

    ground, raised = [], []

    for cell in world.yards:
        if near_cell(cell):
            x, y = cell
            _add_poly(ground, cam, [(x, y, 0), (x + 1, y, 0),
                                    (x + 1, y + 1, 0), (x, y + 1, 0)],
                      C.COL_YARD)

    # track: ballast ribbon + two rails per polyline segment
    for cell, ps in world.tracks.items():
        if not near_cell(cell):
            continue
        for p in ps:
            bal = C.COL_BALLAST if p.layer == 0 else C.COL_BRIDGE_EDGE
            rail = C.COL_TRACK_RAIL if p.layer == 0 else C.COL_TRACK_BRIDGE
            pts = [(cell[0] + gx, cell[1] + gy)
                   for gx, gy in GEOM[(p.a, p.b, p.a)].pts]
            for i in range(len(pts) - 1):
                (x0, y0), (x1, y1) = pts[i], pts[i + 1]
                dx, dy = x1 - x0, y1 - y0
                seg = math.hypot(dx, dy) or 1.0
                ox, oy = -dy / seg * BALLAST_HW, dx / seg * BALLAST_HW
                _add_poly(ground, cam,
                          [(x0 + ox, y0 + oy, 0), (x1 + ox, y1 + oy, 0),
                           (x1 - ox, y1 - oy, 0), (x0 - ox, y0 - oy, 0)], bal)
                rx, ry = -dy / seg * RAIL_OFF, dx / seg * RAIL_OFF
                _add_line(ground, cam, (x0 + rx, y0 + ry, 0.02),
                          (x1 + rx, y1 + ry, 0.02), rail, RAIL_W)
                _add_line(ground, cam, (x0 - rx, y0 - ry, 0.02),
                          (x1 - rx, y1 - ry, 0.02), rail, RAIL_W)

    # active switch branches (same marks as the 2D view)
    for cell, ps in world.tracks.items():
        if not near_cell(cell):
            continue
        for d in world.switch_entries(cell):
            p = ps[world.switch_choice(cell, d)]
            s0 = point_on(cell, p.a, p.b, d, 0.04)
            s1 = point_on(cell, p.a, p.b, d, 0.34)
            _add_line(ground, cam, (s0[0], s0[1], 0.03), (s1[0], s1[1], 0.03),
                      C.COL_SWITCH_ACTIVE, 0.06)

    # platforms: low prisms filling their cell
    for cell in world.platforms:
        if near_cell(cell):
            _add_mesh(raised, cam, box_mesh(1.0, 1.0, 0.15, C.COL_PLATFORM),
                      cell[0] + 0.5, cell[1] + 0.5, 0.0)

    # signals: post + colored head, offset to the right of travel
    for (cell, d) in world.signals:
        if not near_cell(cell):
            continue
        ex, ey = end_point(cell, d)
        dx, dy = DELTA[d]
        n = math.hypot(dx, dy)
        px, py = ex - dy / n * 0.22, ey + dx / n * 0.22
        red = blocks.signal_red(world, game.occ, (cell, d))
        _add_line(raised, cam, (px, py, 0), (px, py, 0.55),
                  C.COL_SIGNAL_POST, 0.05)
        _add_disc(raised, cam, (px, py, 0.6),
                  C.COL_SIGNAL_RED if red else C.COL_SIGNAL_GREEN, 0.09,
                  outline=C.COL_SIGNAL_POST)

    # trains: three cars, positions/yaw sampled along the body polyline
    for t in world.trains:
        hx, hy = t.head_pos(world)
        if (hx - cam.pos[0]) ** 2 + (hy - cam.pos[1]) ** 2 > r2:
            continue
        car = t.length / 3.0
        for k in range(3):
            f = t.point_at_back(world, k * car + 0.06)
            b = t.point_at_back(world, (k + 1) * car - 0.06)
            clen = math.hypot(f[0] - b[0], f[1] - b[1])
            if clen < 1e-6:
                continue
            yaw = math.atan2(f[1] - b[1], f[0] - b[0])
            _add_mesh(raised, cam, car_mesh(t, k, clen),
                      (f[0] + b[0]) / 2, (f[1] + b[1]) / 2, yaw)

    _draw_items(surf, cam, ground)
    _draw_items(surf, cam, raised)

    # screen-space markers: train labels, selection ring, SPAD ring
    for t in world.trains:
        hx, hy = t.head_pos(world)
        if (hx - cam.pos[0]) ** 2 + (hy - cam.pos[1]) ** 2 > r2:
            continue
        cp = cam.to_cam((hx, hy, C.CAR_H + 0.3))
        if cp[2] < NEAR:
            continue
        px, py = cam.project(cp)
        if t is game.selected and mode.view != "cab":
            pygame.draw.circle(surf, C.COL_TRAIN_SELECTED, (px, py),
                               max(6, int(cam._f * 0.3 / cp[2])), 2)
        if t.spad:
            pygame.draw.circle(surf, C.COL_SPAD, (px, py),
                               max(8, int(cam._f * 0.4 / cp[2])), 2)
        if not (mode.view == "cab" and t is game.selected):
            size = max(0, min(28, int(cam._f * 0.28 / cp[2])))
            if size >= 11:
                text(surf, "#%d" % t.id, (px + 6, py - size), C.COL_HUD_TXT,
                     size)

    ui = max(1.0, cam.h / C.WIN_H)
    label = "%s view" % mode.view.upper() if game.selected is not None \
        else "OVERVIEW - Tab to select a train"
    text(surf, label, (10, int(44 * ui)), C.COL_HUD_DIM, int(22 * ui))
