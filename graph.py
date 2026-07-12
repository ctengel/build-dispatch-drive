"""Directed-atom graph over the track network.

A directed atom (cell, piece_idx, entry_dir) is traversed by entering the
piece at entry_dir and leaving at its other end. Successors are the pieces
in the neighboring cell that have a matching end (layer is intentionally
ignored across cell boundaries — bridges ramp down at their ends).
"""

from geometry import DELTA, opposite


def other_end(piece, e):
    return piece.b if e == piece.a else piece.a


def exit_dir(world, datom):
    cell, idx, entry = datom
    return other_end(world.tracks[cell][idx], entry)


def neighbor(cell, d):
    return (cell[0] + DELTA[d][0], cell[1] + DELTA[d][1])


def successors(world, datom):
    """All directed atoms reachable from `datom` (every switch branch)."""
    ex = exit_dir(world, datom)
    nc = neighbor(datom[0], ex)
    ne = opposite(ex)
    return [(nc, j, ne) for j, p in enumerate(world.pieces(nc)) if ne in (p.a, p.b)]


def next_driven(world, datom):
    """The single continuation a physically rolling train takes: the sole
    successor, or the one selected by the facing switch. None at a dead end."""
    succs = successors(world, datom)
    if not succs:
        return None
    if len(succs) == 1:
        return succs[0]
    nc, _, ne = succs[0]
    choice = world.switch_choice(nc, ne)
    return (nc, choice, ne)


def flip(world, datom):
    """Same atom, entered from the other end."""
    cell, idx, entry = datom
    return (cell, idx, other_end(world.tracks[cell][idx], entry))
