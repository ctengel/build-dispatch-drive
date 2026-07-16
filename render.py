"""All drawing: grid, track, signals, platforms, yards, trains, HUD.
Primitive shapes only — no asset files."""

import math

import pygame

import blocks
import config as C
from geometry import GEOM, DELTA, END_POINT, piece_len, point_on, end_point

_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def text(surf, s, pos, color, size=20, center=False):
    img = font(size).render(s, True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def _piece_points(cam, cell, p):
    geom = GEOM[(p.a, p.b, p.a)]
    return [cam.world_to_screen(cell[0] + x, cell[1] + y) for x, y in geom.pts]


def draw_grid(surf, cam):
    x0, y0, x1, y1 = cam.visible_cells()
    if cam.scale < 12:
        return
    for x in range(x0, x1 + 1):
        sx, _ = cam.world_to_screen(x, 0)
        col = C.COL_GRID_MAJOR if x % 5 == 0 else C.COL_GRID
        pygame.draw.line(surf, col, (sx, 0), (sx, cam.h))
    for y in range(y0, y1 + 1):
        _, sy = cam.world_to_screen(0, y)
        col = C.COL_GRID_MAJOR if y % 5 == 0 else C.COL_GRID
        pygame.draw.line(surf, col, (0, sy), (cam.w, sy))


def draw_world(surf, game):
    cam, world = game.camera, game.world
    surf.fill(C.COL_BG)
    draw_grid(surf, cam)
    x0, y0, x1, y1 = cam.visible_cells()

    def visible(cell):
        return x0 <= cell[0] <= x1 and y0 <= cell[1] <= y1

    # platforms / yards under everything
    for cell, name in world.platforms.items():
        if not visible(cell):
            continue
        sx, sy = cam.world_to_screen(cell[0], cell[1])
        s = int(cam.scale)
        pygame.draw.rect(surf, C.COL_PLATFORM, (sx, sy, s + 1, s + 1))
    for cell in world.yards:
        if not visible(cell):
            continue
        sx, sy = cam.world_to_screen(cell[0], cell[1])
        s = int(cam.scale)
        pygame.draw.rect(surf, C.COL_YARD, (sx, sy, s + 1, s + 1))
        for k in range(0, 2 * s, max(6, s // 3)):
            pygame.draw.line(surf, C.COL_BG,
                             (sx + max(0, k - s), sy + min(k, s)),
                             (sx + min(k, s), sy + max(0, k - s)))

    casing = max(2, int(cam.scale * 0.22))
    rail = max(1, int(cam.scale * 0.10))
    # ground track, then bridge track on top
    for layer in (0, 1):
        for cell, ps in world.tracks.items():
            if not visible(cell):
                continue
            for p in ps:
                if p.layer != layer:
                    continue
                pts = _piece_points(cam, cell, p)
                if layer == 0:
                    pygame.draw.lines(surf, C.COL_TRACK_CASING, False, pts, casing)
                    pygame.draw.lines(surf, C.COL_TRACK_RAIL, False, pts, rail)
                else:
                    pygame.draw.lines(surf, C.COL_BRIDGE_EDGE, False, pts, casing + 2)
                    pygame.draw.lines(surf, C.COL_TRACK_BRIDGE, False, pts, rail)
                    # portal ticks at both ends
                    for d in (p.a, p.b):
                        ex, ey = cam.world_to_screen(*end_point(cell, d))
                        pygame.draw.circle(surf, C.COL_BRIDGE_EDGE, (ex, ey),
                                           max(2, int(cam.scale * 0.08)))

    # active switch branches
    for cell, ps in world.tracks.items():
        if not visible(cell):
            continue
        for d in world.switch_entries(cell):
            idx = world.switch_choice(cell, d)
            p = ps[idx]
            s0 = point_on(cell, p.a, p.b, d, 0.04)
            s1 = point_on(cell, p.a, p.b, d, 0.34)
            pygame.draw.line(surf, C.COL_SWITCH_ACTIVE,
                             cam.world_to_screen(*s0), cam.world_to_screen(*s1),
                             max(2, rail + 1))

    # platform labels above the track
    if cam.scale >= 22:
        for cell, name in world.platforms.items():
            if visible(cell):
                sx, sy = cam.world_to_screen(cell[0] + 0.5, cell[1] + 0.82)
                text(surf, name, (sx, sy), C.COL_PLATFORM_TXT,
                     max(14, int(cam.scale * 0.4)), center=True)

    # signals
    for (cell, d) in world.signals:
        if not visible(cell):
            continue
        ex, ey = end_point(cell, d)
        dx, dy = DELTA[d]
        n = math.hypot(dx, dy)
        rx, ry = -dy / n, dx / n     # right-hand side of travel
        px, py = cam.world_to_screen(ex + rx * 0.22, ey + ry * 0.22)
        bx, by = cam.world_to_screen(ex, ey)
        red = blocks.signal_red(game.world, game.occ, (cell, d))
        r = max(3, int(cam.scale * 0.11))
        pygame.draw.line(surf, C.COL_SIGNAL_POST, (bx, by), (px, py))
        pygame.draw.circle(surf, C.COL_SIGNAL_RED if red else C.COL_SIGNAL_GREEN,
                           (px, py), r)
        pygame.draw.circle(surf, C.COL_SIGNAL_POST, (px, py), r, 1)

    # schedule stop badges for the selected train
    sel = game.selected
    if sel is not None and sel.schedule:
        for k, cell in enumerate(sel.schedule):
            sx, sy = cam.world_to_screen(cell[0] + 0.5, cell[1] + 0.5)
            done = k < sel.schedule_index
            col = C.COL_HUD_DIM if done else C.COL_STOP_BADGE
            pygame.draw.circle(surf, col, (sx, sy - int(cam.scale * 0.55)), 9)
            text(surf, str(k + 1), (sx, sy - int(cam.scale * 0.55)),
                 (20, 20, 20), 16, center=True)

    # trains: three cars sampled along the body polyline
    for t in world.trains:
        car = t.length / 3.0
        width = max(3, int(cam.scale * 0.26))
        for k in range(3):
            s0, s1 = k * car + 0.06, (k + 1) * car - 0.06
            p0 = cam.world_to_screen(*t.point_at_back(world, s0))
            p1 = cam.world_to_screen(*t.point_at_back(world, s1))
            if k == 0:
                col = {"driven": C.COL_TRAIN_HEAD_DRIVEN,
                       "running": C.COL_TRAIN_HEAD_AI,
                       "dwelling": C.COL_TRAIN_HEAD_AI}.get(t.state,
                                                            C.COL_TRAIN_HEAD_IDLE)
            else:
                col = C.COL_TRAIN_BODY
            pygame.draw.line(surf, col, p0, p1, width)
        hx, hy = cam.world_to_screen(*t.head_pos(world))
        if t is sel:
            pygame.draw.circle(surf, C.COL_TRAIN_SELECTED, (hx, hy),
                               max(6, int(cam.scale * 0.4)), 2)
        if t.spad:
            pygame.draw.circle(surf, C.COL_SPAD, (hx, hy),
                               max(8, int(cam.scale * 0.5)), 2)
        if cam.scale >= 14:
            text(surf, "#%d" % t.id, (hx + 8, hy - 22), C.COL_HUD_TXT, 16)


def draw_hud(surf, game):
    cam = game.camera
    ui = max(1.0, cam.h / C.WIN_H)   # HUD scale-up on larger windows
    pygame.draw.rect(surf, C.COL_HUD_BG, (0, 0, cam.w, int(38 * ui)))
    pygame.draw.rect(surf, C.COL_HUD_BG,
                     (0, cam.h - int(34 * ui), cam.w, int(34 * ui)))
    left = "[%s]" % game.mode.upper()
    if game.mode == "build":
        left += "  tool: %s%s" % (game.build.tool,
                                  "  (BRIDGE layer)" if game.build.bridge else "")
    t = game.selected
    if t is not None:
        info = "  |  train #%d  %s  %.1f c/s" % (t.id, t.state, t.speed)
        if t.state in ("running", "dwelling") and t.schedule_index < len(t.schedule):
            info += "  next stop %s" % (t.schedule[t.schedule_index],)
        if t.note:
            info += "  [%s]" % t.note
        left += info
    text(surf, left, (10, int(9 * ui)), C.COL_HUD_TXT, int(26 * ui))
    hints = game.mode_hints()
    size = int(24 * ui)
    while size > 14 and font(size).size(hints)[0] > cam.w - 20:
        size -= 1
    text(surf, hints, (10, cam.h - int(26 * ui)), C.COL_HUD_DIM, size)

    # transient messages, newest at the top
    y = int(50 * ui)
    for msg, expiry in game.messages:
        text(surf, msg, (cam.w // 2, y), C.COL_MSG, int(28 * ui), center=True)
        y += int(30 * ui)
    # SPAD banner
    for t in game.world.trains:
        if t.spad and (game.time * 2) % 1 < 0.6:
            text(surf, "SIGNAL PASSED AT DANGER - train #%d" % t.id,
                 (cam.w // 2, cam.h // 2 - 120), C.COL_SPAD, int(38 * ui),
                 center=True)
