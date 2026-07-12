"""Helpers shared by the interaction modes."""

import math

from geometry import END_POINT, piece_len
from train import Train


def nearest_end(world, cell, wpos, ends=None):
    """Direction end of `cell` (restricted to `ends` if given) closest to the
    world-space point wpos, or None."""
    if ends is None:
        ends = world.ends_in_cell(cell)
    best, best_d = None, float("inf")
    for d in ends:
        ex, ey = END_POINT[d]
        dist = math.hypot(cell[0] + ex - wpos[0], cell[1] + ey - wpos[1])
        if dist < best_d:
            best, best_d = d, dist
    return best


def pick_train(world, wpos, radius=0.45):
    """Train whose body passes within `radius` cells of wpos, or None."""
    best, best_d = None, radius
    for t in world.trains:
        steps = max(4, int(t.length / 0.3))
        for k in range(steps + 1):
            px, py = t.point_at_back(world, t.length * k / steps)
            d = math.hypot(px - wpos[0], py - wpos[1])
            if d < best_d:
                best, best_d = t, d
    return best


def nearest_piece(world, cell, wpos):
    """Index of the piece in `cell` whose midpoint is closest to wpos."""
    from geometry import point_on
    best, best_d = None, float("inf")
    for i, p in enumerate(world.pieces(cell)):
        mx, my = point_on(cell, p.a, p.b, p.a, piece_len(p.a, p.b) / 2)
        d = math.hypot(mx - wpos[0], my - wpos[1])
        if d < best_d:
            best, best_d = i, d
    return best


def spawn_train(game, cell, wpos):
    world = game.world
    if not world.pieces(cell):
        game.msg("no track here")
        return None
    if cell in world.occupied_cells():
        game.msg("cell occupied by a train")
        return None
    idx = nearest_piece(world, cell, wpos)
    p = world.pieces(cell)[idx]
    t = Train(world.next_train_id, (cell, idx, p.a), piece_len(p.a, p.b) / 2)
    world.next_train_id += 1
    world.trains.append(t)
    game.msg("train #%d placed" % t.id)
    return t


def cycle_switch_at(game, wpos):
    cell = (math.floor(wpos[0]), math.floor(wpos[1]))
    entries = game.world.switch_entries(cell)
    if not entries:
        return False
    d = nearest_end(game.world, cell, wpos, ends=entries)
    game.world.cycle_switch(cell, d)
    game.msg("switch thrown")
    return True


def cycle_selection(game):
    trains = game.world.trains
    if not trains:
        game.selected = None
        return
    if game.selected in trains:
        i = (trains.index(game.selected) + 1) % len(trains)
    else:
        i = 0
    game.selected = trains[i]
