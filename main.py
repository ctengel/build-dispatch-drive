"""Dispatch & Drive — a 2D train game.

Modes: 1 build, 2 operate/dispatch, 3 drive, 4 drive in 3D. F5 saves
the layout, F9
loads it (layout.json by default); Shift+F5/F9 prompt for a filename.
Run: python main.py [file.json]
"""

import os
import sys


def parse_argv(argv):
    """First non-flag argument is the save file, if any."""
    files = [a for a in argv[1:] if not a.startswith("-")]
    return files[0] if files else None


class Game:
    def __init__(self, headless=False, save_path=None):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        global pygame
        import pygame
        pygame.init()
        import blocks
        import config as C
        import render
        import render3d
        import train as train_mod
        from camera import Camera
        from world import World
        from modes.build import BuildMode
        from modes.operate import OperateMode
        from modes.drive import DriveMode
        from modes.drive3d import Drive3DMode
        self._blocks, self._render, self._train_mod, self._C = \
            blocks, render, train_mod, C
        self._render3d = render3d
        self.save_path = save_path or C.SAVE_FILE
        self.screen = pygame.display.set_mode((C.WIN_W, C.WIN_H),
                                              pygame.RESIZABLE)
        pygame.display.set_caption("Dispatch & Drive")
        self._fullscreen = False
        self._windowed_size = (C.WIN_W, C.WIN_H)
        self.camera = Camera(C.WIN_W, C.WIN_H)
        self.world = World()
        blocks.rebuild(self.world)
        self.build = BuildMode()
        self.operate = OperateMode()
        self.drive = DriveMode()
        self.drive3d = Drive3DMode()
        self.mode = "build"
        self.selected = None
        self.occ = {}
        self.time = 0.0
        self.messages = []
        self.running = True
        self._panning = False
        self.prompt = None       # None | "save" | "load"
        self.prompt_text = ""

    # ---- helpers ----

    def mode_obj(self):
        return {"build": self.build, "operate": self.operate,
                "drive": self.drive, "drive3d": self.drive3d}[self.mode]

    def mode_hints(self):
        if self.prompt is not None:
            return "type a filename   Enter confirm   Esc cancel"
        return self.mode_obj().hints + \
            "   |   1/2/3/4 mode  F5 save  F9 load  Shift+F5/F9 save/load as" \
            "  F11 fullscreen  +/- zoom"

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

    def toggle_fullscreen(self):
        if self._fullscreen:
            self.screen = pygame.display.set_mode(self._windowed_size,
                                                  pygame.RESIZABLE)
        else:
            self._windowed_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self._fullscreen = not self._fullscreen
        self.camera.w, self.camera.h = self.screen.get_size()

    def save(self, path=None):
        path = path or self.save_path
        try:
            self.world.save(path)
            self.save_path = path
            self.msg("saved to " + path)
        except OSError as e:
            self.msg("save failed: %s" % e)

    def load(self, path=None):
        path = path or self.save_path
        if not os.path.exists(path):
            self.msg("no save file (%s)" % path)
            return
        try:
            warnings = self.world.load(path)
        except (OSError, ValueError, KeyError) as e:
            self.msg("load failed: %s" % e)
            return
        self.save_path = path
        self.selected = None
        for wmsg in warnings[:3]:
            self.msg(wmsg)
        self.msg("loaded " + path)

    def open_prompt(self, kind):
        self.prompt, self.prompt_text = kind, ""
        pygame.key.start_text_input()

    def close_prompt(self):
        self.prompt = None
        pygame.key.stop_text_input()

    def confirm_prompt(self):
        name, kind = self.prompt_text.strip(), self.prompt
        self.close_prompt()
        if not name:
            self.msg("cancelled (empty filename)")
            return
        if not os.path.splitext(name)[1]:
            name += ".json"
        (self.save if kind == "save" else self.load)(name)

    # ---- main loop pieces ----

    def step(self, dt, events):
        for ev in events:
            if ev.type == pygame.QUIT:
                self.running = False
            elif self.prompt is not None:
                if ev.type == pygame.TEXTINPUT:
                    self.prompt_text += ev.text
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    self.close_prompt()
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_BACKSPACE:
                    self.prompt_text = self.prompt_text[:-1]
                elif ev.type == pygame.KEYDOWN and ev.key in (
                        pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.confirm_prompt()
            elif ev.type == pygame.KEYDOWN and ev.key in (
                    pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.mode = {pygame.K_1: "build", pygame.K_2: "operate",
                             pygame.K_3: "drive",
                             pygame.K_4: "drive3d"}[ev.key]
                if self.selected is not None:
                    self.selected.throttle = 0
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F5:
                if ev.mod & pygame.KMOD_SHIFT:
                    self.open_prompt("save")
                else:
                    self.save()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9:
                if ev.mod & pygame.KMOD_SHIFT:
                    self.open_prompt("load")
                else:
                    self.load()
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.selected = None
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                self.toggle_fullscreen()
            elif ev.type == pygame.KEYDOWN and ev.key in (
                    pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.camera.zoom_at(self.camera.w / 2, self.camera.h / 2, 1.25)
            elif ev.type == pygame.KEYDOWN and ev.key in (
                    pygame.K_MINUS, pygame.K_KP_MINUS):
                self.camera.zoom_at(self.camera.w / 2, self.camera.h / 2,
                                    1 / 1.25)
            elif ev.type == pygame.KEYDOWN and ev.key in (
                    pygame.K_0, pygame.K_KP0):
                self.camera.zoom_at(self.camera.w / 2, self.camera.h / 2,
                                    self._C.SCALE_START / self.camera.scale)
            elif ev.type == pygame.VIDEORESIZE and not self._fullscreen:
                self.screen = pygame.display.set_mode((ev.w, ev.h),
                                                      pygame.RESIZABLE)
                self.camera.w, self.camera.h = self.screen.get_size()
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
        if self.prompt is not None:
            pass
        elif self.mode not in ("drive", "drive3d"):
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
            self.mode_obj().update(self)

        self.time += dt
        self.occ = self._train_mod.update_all(self.world, dt, self.time)
        self.messages = [(m, e) for m, e in self.messages if e > self.time]
        if self.selected is not None and self.selected not in self.world.trains:
            self.selected = None

    def draw(self):
        if self.mode == "drive3d":
            self._render3d.draw_world(self.screen, self, self.drive3d)
        else:
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
    game = Game(headless="--headless" in sys.argv,
                save_path=parse_argv(sys.argv))
    if "--demo" in sys.argv:
        import demo
        demo.build(game.world)
        game.mode = "operate"
        game.msg("demo layout - select train #2 and press G")
    elif parse_argv(sys.argv) and os.path.exists(game.save_path):
        game.load()
    game.run()
