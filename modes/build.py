"""Build mode: paint track by dragging through cells; place signals,
platforms, yards; toggle bridge layer; throw switches; delete."""

import math

import pygame

import config as C
from geometry import DELTA, opposite, valid_pair
from modes import common

DIR_FROM_DELTA = {DELTA[d]: d for d in range(8)}

TOOL_KEYS = {
    pygame.K_t: "track",
    pygame.K_x: "delete",
    pygame.K_s: "signal",
    pygame.K_p: "platform",
    pygame.K_y: "yard",
    pygame.K_w: "switch",
}


class BuildMode:
    name = "build"
    hints = ("T track  X delete  S signal  P platform  Y yard  W switch  "
             "B bridge layer  drag to paint  right-click throw switch")

    def __init__(self):
        self.tool = "track"
        self.bridge = False
        self.painting = False
        self.moved = False
        self.last_cell = None
        self.entry = None        # direction the paint path entered last_cell from
        self.edited = set()
        self.done_cells = set()  # per-drag guard for delete/platform/yard

    # ---- events ----

    def handle_event(self, game, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key in TOOL_KEYS:
                self.tool = TOOL_KEYS[ev.key]
                game.msg("tool: " + self.tool)
            elif ev.key == pygame.K_b:
                self.bridge = not self.bridge
                game.msg("laying %s track" % ("BRIDGE/TUNNEL" if self.bridge
                                              else "ground"))
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            wpos = game.camera.screen_to_world(*ev.pos)
            cell = (math.floor(wpos[0]), math.floor(wpos[1]))
            if self.tool == "track":
                self.painting = True
                self.moved = False
                self.last_cell = cell
                self.entry = None
            elif self.tool == "delete":
                self.painting = True
                self.done_cells = set()
                self._delete_at(game, cell)
            elif self.tool == "signal":
                self._toggle_signal(game, cell, wpos)
            elif self.tool == "platform":
                self._toggle_flag(game, cell, "platform")
            elif self.tool == "yard":
                self._toggle_flag(game, cell, "yard")
            elif self.tool == "switch":
                if not common.cycle_switch_at(game, wpos):
                    game.msg("no switch here")
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            wpos = game.camera.screen_to_world(*ev.pos)
            if not common.cycle_switch_at(game, wpos):
                game.msg("no switch here")
        elif ev.type == pygame.MOUSEMOTION and self.painting:
            wpos = game.camera.screen_to_world(*ev.pos)
            cell = (math.floor(wpos[0]), math.floor(wpos[1]))
            if self.tool == "track":
                self._paint_to(game, cell)
            elif self.tool == "delete":
                self._delete_at(game, cell)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.painting:
            if self.tool == "track" and self.moved and self.entry is not None:
                # cap the run with a straight so it ends inside the final cell
                self._lay(game, self.last_cell, self.entry, opposite(self.entry))
            self.painting = False
            if self.edited:
                game.after_edit(self.edited)
                self.edited = set()

    # ---- track painting ----

    def _paint_to(self, game, target):
        guard = 0
        while self.last_cell != target and guard < 256:
            guard += 1
            cx, cy = self.last_cell
            dx = (target[0] > cx) - (target[0] < cx)
            dy = (target[1] > cy) - (target[1] < cy)
            d = DIR_FROM_DELTA[(dx, dy)]
            self._lay(game, self.last_cell, self.entry, d)
            self.last_cell = (cx + dx, cy + dy)
            self.entry = opposite(d)
            self.moved = True

    def _lay(self, game, cell, entry, exit_d):
        a = entry if entry is not None else opposite(exit_d)
        lo, hi = min(a, exit_d), max(a, exit_d)
        if not valid_pair(lo, hi):
            game.msg("turn too sharp")
            return
        if cell in game.world.occupied_cells():
            game.msg("train in the way")
            return
        if game.world.add_piece(cell, lo, hi, 1 if self.bridge else 0):
            self.edited.add(cell)

    # ---- other tools ----

    def _delete_at(self, game, cell):
        if cell in self.done_cells:
            return
        self.done_cells.add(cell)
        w = game.world
        if cell in w.occupied_cells():
            game.msg("train in the way")
            return
        ps = w.pieces(cell)
        if ps:
            idx = max((i for i, p in enumerate(ps) if p.layer == 1),
                      default=len(ps) - 1)
            w.remove_piece(cell, idx)
            self.edited.add(cell)
        elif cell in w.platforms:
            del w.platforms[cell]
        elif cell in w.yards:
            w.yards.discard(cell)

    def _toggle_signal(self, game, cell, wpos):
        w = game.world
        if not w.pieces(cell):
            game.msg("no track for a signal")
            return
        d = common.nearest_end(w, cell, wpos)
        w.toggle_signal(cell, d)
        game.after_edit(set(), repath=False)
        game.msg("signal %s" % ("placed" if (cell, d) in w.signals else "removed"))

    def _toggle_flag(self, game, cell, kind):
        w = game.world
        if not w.pieces(cell):
            game.msg("place %ss on track" % kind)
            return
        if kind == "platform":
            w.toggle_platform(cell)
        else:
            w.toggle_yard(cell)

    # ---- overlay ----

    def draw_overlay(self, game, surf):
        mx, my = pygame.mouse.get_pos()
        cam = game.camera
        cell = cam.cell_at(mx, my)
        sx, sy = cam.world_to_screen(cell[0], cell[1])
        s = int(cam.scale)
        pygame.draw.rect(surf, C.COL_GHOST, (sx, sy, s + 1, s + 1), 1)
