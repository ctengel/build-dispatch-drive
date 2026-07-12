"""Dispatch & Drive — a 2D train game.

Modes: 1 build, 2 operate/dispatch, 3 drive. F5 saves the layout to
layout.json, F9 loads it. Run: python main.py
"""

import os
import sys


class Game:
    def __init__(self, headless=False):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        global pygame
        import pygame
        pygame.init()
        import blocks
        import config as C
        import render
        import train as train_mod
        from camera import Camera
        from world import World
        from modes.build import BuildMode
        from modes.operate import OperateMode
        from modes.drive import DriveMode
        self._blocks, self._render, self._train_mod, self._C = \
            blocks, render, train_mod, C
        self.screen = pygame.display.set_mode((C.WIN_W, C.WIN_H))
        pygame.display.set_caption("Dispatch & Drive")
        self.camera = Camera(C.WIN_W, C.WIN_H)
        self.world = World()
        blocks.rebuild(self.world)
        self.build = BuildMode()
        self.operate = OperateMode()
        self.drive = DriveMode()
        self.mode = "build"
        self.selected = None
        self.occ = {}
        self.time = 0.0
        self.messages = []
        self.running = True
        self._panning = False

    # ---- helpers ----

    def mode_obj(self):
        return {"build": self.build, "operate": self.operate,
                "drive": self.drive}[self.mode]

    def mode_hints(self):
        return self.mode_obj().hints + "   |   1/2/3 mode  F5 save  F9 load"

    def msg(self, s):
        self.messages.append((s, self.time + 2.5))
        self.messages = self.messages[-4:]

    def after_edit(self, cells, repath=True):
        """Rebuild blocks after a layout edit; reroute trains whose plan
        crosses an edited cell (their piece indices may have shifted)."""
        self._blocks.rebuild(self.world)
        if not repath:
            return
        for t in self.world.trains:
            if t.state in ("running", "dwelling") and \
                    any(a[0] in cells for a in t.plan):
                t.plan = []
                if not t.dispatch(self.world):
                    t.state = "idle"
                    self.msg("train #%d lost its route" % t.id)

    def save(self):
        try:
            self.world.save(self._C.SAVE_FILE)
            self.msg("saved to " + self._C.SAVE_FILE)
        except OSError as e:
            self.msg("save failed: %s" % e)

    def load(self):
        if not os.path.exists(self._C.SAVE_FILE):
            self.msg("no save file (%s)" % self._C.SAVE_FILE)
            return
        try:
            warnings = self.world.load(self._C.SAVE_FILE)
        except (OSError, ValueError, KeyError) as e:
            self.msg("load failed: %s" % e)
            return
        self.selected = None
        for wmsg in warnings[:3]:
            self.msg(wmsg)
        self.msg("loaded " + self._C.SAVE_FILE)

    # ---- main loop pieces ----

    def step(self, dt, events):
        for ev in events:
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN and ev.key in (
                    pygame.K_1, pygame.K_2, pygame.K_3):
                self.mode = {pygame.K_1: "build", pygame.K_2: "operate",
                             pygame.K_3: "drive"}[ev.key]
                if self.selected is not None:
                    self.selected.throttle = 0
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F5:
                self.save()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9:
                self.load()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.selected = None
            elif ev.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                self.camera.zoom_at(mx, my, 1.1 ** ev.y)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 2:
                self._panning = True
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 2:
                self._panning = False
            elif ev.type == pygame.MOUSEMOTION and self._panning:
                self.camera.pan_pixels(*ev.rel)
            else:
                self.mode_obj().handle_event(self, ev)

        keys = pygame.key.get_pressed()
        if self.mode != "drive":
            pan = 500 * dt
            if keys[pygame.K_LEFT]:
                self.camera.pan_pixels(pan, 0)
            if keys[pygame.K_RIGHT]:
                self.camera.pan_pixels(-pan, 0)
            if keys[pygame.K_UP]:
                self.camera.pan_pixels(0, pan)
            if keys[pygame.K_DOWN]:
                self.camera.pan_pixels(0, -pan)
        else:
            self.drive.update(self)

        self.time += dt
        self.occ = self._train_mod.update_all(self.world, dt, self.time)
        self.messages = [(m, e) for m, e in self.messages if e > self.time]
        if self.selected is not None and self.selected not in self.world.trains:
            self.selected = None

    def draw(self):
        self._render.draw_world(self.screen, self)
        self.mode_obj().draw_overlay(self, self.screen)
        self._render.draw_hud(self.screen, self)
        pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            dt = min(clock.tick(self._C.FPS) / 1000.0, 0.1)
            self.step(dt, pygame.event.get())
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    game = Game(headless="--headless" in sys.argv)
    if "--demo" in sys.argv:
        import demo
        demo.build(game.world)
        game.mode = "operate"
        game.msg("demo layout - select train #2 and press G")
    game.run()
