"""Operate/dispatch mode: place trains, build one-shot schedules, dispatch."""

import math

import pygame

from modes import common


class OperateMode:
    name = "operate"
    hints = ("click track: place train / add stop   click train: select   "
             "G dispatch  C clear stops  Tab next train  Del remove  Esc deselect")

    def handle_event(self, game, ev):
        w = game.world
        if ev.type == pygame.KEYDOWN:
            t = game.selected
            if ev.key == pygame.K_TAB:
                common.cycle_selection(game)
            elif ev.key in (pygame.K_g, pygame.K_RETURN):
                self._dispatch(game)
            elif ev.key == pygame.K_c and t is not None:
                t.schedule = []
                t.schedule_index = 0
                t.plan = []
                if t.state in ("running", "dwelling", "done"):
                    t.state = "idle"
                game.msg("schedule cleared")
            elif ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE) and t is not None:
                if t.speed == 0:
                    w.trains.remove(t)
                    game.selected = None
                    game.msg("train #%d removed" % t.id)
                else:
                    game.msg("stop the train first")
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            wpos = game.camera.screen_to_world(*ev.pos)
            cell = (math.floor(wpos[0]), math.floor(wpos[1]))
            hit = common.pick_train(w, wpos)
            if hit is not None:
                game.selected = hit
                game.msg("train #%d selected" % hit.id)
            elif game.selected is not None:
                if w.pieces(cell):
                    game.selected.schedule.append(cell)
                    game.msg("stop %d: %s" % (len(game.selected.schedule), cell))
                else:
                    game.msg("no track there")
            else:
                game.selected = common.spawn_train(game, cell, wpos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            wpos = game.camera.screen_to_world(*ev.pos)
            common.cycle_switch_at(game, wpos)

    def _dispatch(self, game):
        t = game.selected
        if t is None:
            game.msg("select a train first")
            return
        if t.state in ("running", "dwelling"):
            game.msg("train #%d already en route" % t.id)
            return
        if t.state in ("done", "driven"):
            t.state = "idle"
        if t.schedule_index >= len(t.schedule):
            game.msg("no stops queued - click track cells to add stops")
            return
        if t.dispatch(game.world):
            game.msg("train #%d dispatched (%d stops)"
                     % (t.id, len(t.schedule) - t.schedule_index))
        else:
            game.msg("train #%d: no route to %s"
                     % (t.id, t.schedule[t.schedule_index]))

    def draw_overlay(self, game, surf):
        pass
