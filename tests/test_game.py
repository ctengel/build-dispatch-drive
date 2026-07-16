"""Headless integration test: exercises the full Game loop with synthetic
input events — build-mode painting, save/load, operate-mode dispatch,
drive-mode control.
Run: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_game.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from main import Game, parse_argv

DT = 1 / 60


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod)


def txt(s):
    return pygame.event.Event(pygame.TEXTINPUT, text=s)


def mouse(game, type_, wx, wy, button=1):
    pos = game.camera.world_to_screen(wx, wy)
    if type_ == pygame.MOUSEMOTION:
        return pygame.event.Event(type_, pos=pos, rel=(0, 0), buttons=(1, 0, 0))
    return pygame.event.Event(type_, pos=pos, button=button)


def run(game, seconds, events=()):
    game.step(DT, list(events))
    for _ in range(int(seconds / DT) - 1):
        game.step(DT, [])
    game.draw()


def drag(game, points):
    """Simulate a left-button drag through world points."""
    evs = [mouse(game, pygame.MOUSEBUTTONDOWN, *points[0])]
    evs += [mouse(game, pygame.MOUSEMOTION, *p) for p in points[1:]]
    evs += [mouse(game, pygame.MOUSEBUTTONUP, *points[-1])]
    game.step(DT, evs)


def main():
    # --- CLI parsing ---
    assert parse_argv(["main.py"]) is None
    assert parse_argv(["main.py", "--headless", "a.json"]) == "a.json"
    assert Game(headless=True, save_path="a.json").save_path == "a.json"

    game = Game(headless=True)
    game.camera.cx, game.camera.cy = 8.0, 4.0
    game.camera.scale = 40.0

    # --- build mode: paint a straight line and a loop back ---
    assert game.mode == "build"
    drag(game, [(2.5, 3.5)] + [(x + 0.5, 3.5) for x in range(3, 13)])
    assert all(game.world.pieces((x, 3)) for x in range(2, 13)), "row not laid"
    # a parallel row and connect with diagonals to form a loop
    drag(game, [(2.5, 6.5)] + [(x + 0.5, 6.5) for x in range(3, 13)])
    # connectors curve into the rows because the turns happen mid-drag
    drag(game, [(3.5, 3.5), (2.5, 3.5), (1.5, 4.5), (1.5, 5.5),
                (2.5, 6.5), (3.5, 6.5)])
    drag(game, [(11.5, 3.5), (12.5, 3.5), (13.5, 4.5), (13.5, 5.5),
                (12.5, 6.5), (11.5, 6.5)])
    n_cells = len(game.world.tracks)
    assert n_cells >= 24, n_cells

    # platform + signal via events
    game.step(DT, [key(pygame.K_p), mouse(game, pygame.MOUSEBUTTONDOWN, 6.5, 3.5),
                   mouse(game, pygame.MOUSEBUTTONUP, 6.5, 3.5)])
    assert (6, 3) in game.world.platforms
    game.step(DT, [key(pygame.K_s), mouse(game, pygame.MOUSEBUTTONDOWN, 8.95, 3.5),
                   mouse(game, pygame.MOUSEBUTTONUP, 8.95, 3.5)])
    assert game.world.signals, "signal not placed"

    # --- save / load round trip through the UI keys ---
    assert game.save_path == game._C.SAVE_FILE
    game.step(DT, [key(pygame.K_F5)])
    assert os.path.exists("layout.json")
    before = game.world.to_dict()
    game.step(DT, [key(pygame.K_F9)])
    assert game.world.to_dict() == before

    # --- save as / load from via the filename prompt ---
    base = os.path.join(tempfile.gettempdir(), "ttest_game_layout")
    if os.path.exists(base + ".json"):
        os.remove(base + ".json")
    game.step(DT, [key(pygame.K_F5, mod=pygame.KMOD_SHIFT)])
    assert game.prompt == "save"
    game.step(DT, [key(pygame.K_2)])            # swallowed while prompt open
    assert game.mode == "build" and game.prompt == "save"
    game.draw()                                  # prompt overlay renders
    game.step(DT, [txt(base + "x"), key(pygame.K_BACKSPACE)])
    assert game.prompt_text == base
    game.step(DT, [key(pygame.K_RETURN)])
    assert game.prompt is None
    assert os.path.exists(base + ".json"), "extension not auto-appended"
    assert game.save_path == base + ".json"
    # plain F5 now targets the new current file
    os.remove(base + ".json")
    game.step(DT, [key(pygame.K_F5)])
    assert os.path.exists(base + ".json")
    # Esc cancels without touching save_path
    game.step(DT, [key(pygame.K_F9, mod=pygame.KMOD_SHIFT)])
    assert game.prompt == "load"
    game.step(DT, [key(pygame.K_ESCAPE)])
    assert game.prompt is None and game.save_path == base + ".json"
    # loading a nonexistent file leaves save_path unchanged
    game.step(DT, [key(pygame.K_F9, mod=pygame.KMOD_SHIFT)])
    game.step(DT, [txt("no_such_file"), key(pygame.K_RETURN)])
    assert game.save_path == base + ".json"
    assert game.world.to_dict() == before
    # empty filename + Enter cancels
    game.step(DT, [key(pygame.K_F5, mod=pygame.KMOD_SHIFT)])
    game.step(DT, [key(pygame.K_RETURN)])
    assert game.prompt is None and game.save_path == base + ".json"
    # load back through the prompt
    game.step(DT, [key(pygame.K_F9, mod=pygame.KMOD_SHIFT)])
    game.step(DT, [txt(base + ".json"), key(pygame.K_RETURN)])
    assert game.world.to_dict() == before
    os.remove(base + ".json")
    game.save_path = game._C.SAVE_FILE

    # --- operate mode: spawn, schedule, dispatch ---
    game.step(DT, [key(pygame.K_2)])
    assert game.mode == "operate"
    game.step(DT, [mouse(game, pygame.MOUSEBUTTONDOWN, 3.5, 6.5),
                   mouse(game, pygame.MOUSEBUTTONUP, 3.5, 6.5)])
    t = game.selected
    assert t is not None and t in game.world.trains
    game.step(DT, [mouse(game, pygame.MOUSEBUTTONDOWN, 6.5, 3.5),
                   mouse(game, pygame.MOUSEBUTTONUP, 6.5, 3.5)])
    assert t.schedule == [(6, 3)]
    run(game, 1, [key(pygame.K_g)])
    assert t.state == "running", t.state
    run(game, 30)
    assert t.state == "done", (t.state, t.path[0])
    assert t.path[0][0] == (6, 3)

    # --- drive mode: take over and roll ---
    game.step(DT, [key(pygame.K_3)])
    start = t.head_pos(game.world)
    pressed = {k: 0 for k in range(512)}

    class FakeKeys(dict):
        def __getitem__(self, k):
            return k == pygame.K_UP

    real_get_pressed = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: FakeKeys()
    try:
        run(game, 1)  # short: the row dead-ends a few cells ahead
    finally:
        pygame.key.get_pressed = real_get_pressed
    assert t.state == "driven" and t.speed > 0, (t.state, t.speed)
    assert t.head_pos(game.world) != start
    # e-stop and reverse
    run(game, 2, [key(pygame.K_SPACE)])
    assert t.speed == 0.0
    heading_before = t.path[0][2]
    game.step(DT, [key(pygame.K_r)])
    assert t.path[0][2] != heading_before

    # --- keyboard zoom: + / - / 0 ---
    game.step(DT, [key(pygame.K_1)])  # leave drive mode
    center = game.camera.screen_to_world(game.camera.w / 2, game.camera.h / 2)
    scale0 = game.camera.scale
    game.step(DT, [key(pygame.K_EQUALS)])
    assert game.camera.scale > scale0, game.camera.scale
    game.step(DT, [key(pygame.K_MINUS), key(pygame.K_MINUS)])
    assert game.camera.scale < scale0, game.camera.scale
    game.step(DT, [key(pygame.K_0)])
    assert game.camera.scale == game._C.SCALE_START
    after = game.camera.screen_to_world(game.camera.w / 2, game.camera.h / 2)
    assert abs(after[0] - center[0]) < 1e-6 and abs(after[1] - center[1]) < 1e-6

    # --- window resize updates screen and camera ---
    game.step(DT, [pygame.event.Event(pygame.VIDEORESIZE, w=1600, h=1000)])
    assert game.screen.get_size() == (1600, 1000), game.screen.get_size()
    assert (game.camera.w, game.camera.h) == (1600, 1000)

    # --- fullscreen toggle keeps camera in sync, restores windowed size ---
    game.step(DT, [key(pygame.K_F11)])
    assert game._fullscreen
    assert (game.camera.w, game.camera.h) == game.screen.get_size()
    game.draw()  # HUD renders at the fullscreen size
    game.step(DT, [key(pygame.K_F11)])
    assert not game._fullscreen
    assert game.screen.get_size() == (1600, 1000), game.screen.get_size()
    assert (game.camera.w, game.camera.h) == (1600, 1000)

    game.draw()
    print("INTEGRATION TEST PASSED (%d track cells, %d trains)"
          % (len(game.world.tracks), len(game.world.trains)))


if __name__ == "__main__":
    main()
