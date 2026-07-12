"""Drive mode: direct control of one train — throttle, brake, reverse."""

import pygame

from modes import common


class DriveMode:
    name = "drive"
    hints = ("Up/W power  Down/S brake  Space e-stop  R reverse (stopped)  "
             "G resume schedule  Tab/click select")

    def handle_event(self, game, ev):
        if ev.type == pygame.KEYDOWN:
            t = game.selected
            if ev.key == pygame.K_TAB:
                common.cycle_selection(game)
            elif t is None:
                return
            elif ev.key == pygame.K_SPACE:
                t.take_control()
                t.speed = 0.0
                game.msg("emergency stop")
            elif ev.key == pygame.K_r:
                if t.speed > 0:
                    game.msg("stop before reversing")
                else:
                    t.take_control()
                    t.reverse(game.world)
                    game.msg("reversed")
            elif ev.key in (pygame.K_g, pygame.K_RETURN):
                if t.schedule_index < len(t.schedule):
                    if t.dispatch(game.world):
                        game.msg("train #%d resumes its schedule" % t.id)
                    else:
                        game.msg("no route")
                else:
                    game.msg("no stops queued")
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            wpos = game.camera.screen_to_world(*ev.pos)
            hit = common.pick_train(game.world, wpos)
            if hit is not None:
                game.selected = hit
                game.msg("train #%d selected" % hit.id)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
            wpos = game.camera.screen_to_world(*ev.pos)
            common.cycle_switch_at(game, wpos)

    def update(self, game):
        """Per-frame held-key throttle; called from Game.step."""
        t = game.selected
        if t is None:
            return
        keys = pygame.key.get_pressed()
        power = keys[pygame.K_UP] or keys[pygame.K_w]
        brake = keys[pygame.K_DOWN] or keys[pygame.K_s]
        if power or brake:
            if t.state != "driven":
                t.take_control()
            t.throttle = 1 if power else -1
        elif t.state == "driven":
            t.throttle = 0
        game.camera.follow(*t.head_pos(game.world))

    def draw_overlay(self, game, surf):
        pass
