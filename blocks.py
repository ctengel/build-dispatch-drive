"""Block signaling: partition track atoms into blocks (flood fill bounded by
signals), per-tick occupancy, and signal aspects.

An atom is (cell, piece_idx). Two atoms join into one block when:
  - same cell, same layer, sharing a direction end (a switch/crossover), or
  - across a cell boundary where their ends meet — unless a signal sits on
    that boundary in either direction.
"""

from geometry import DELTA, opposite
from graph import neighbor


def _find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent, a, b):
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[ra] = rb


def compute(world):
    """atom -> block id (an arbitrary representative atom)."""
    parent = {}
    for cell, ps in world.tracks.items():
        for i in range(len(ps)):
            parent[(cell, i)] = (cell, i)
    for cell, ps in world.tracks.items():
        # in-cell joins: same layer, shared end
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                if ps[i].layer == ps[j].layer and \
                        ({ps[i].a, ps[i].b} & {ps[j].a, ps[j].b}):
                    _union(parent, (cell, i), (cell, j))
        # boundary joins (each boundary is visited from both sides; harmless)
        for i, p in enumerate(ps):
            for e in (p.a, p.b):
                nc = neighbor(cell, e)
                oe = opposite(e)
                if (cell, e) in world.signals or (nc, oe) in world.signals:
                    continue
                for j, q in enumerate(world.pieces(nc)):
                    if oe in (q.a, q.b):
                        _union(parent, (cell, i), (nc, j))
    return {a: _find(parent, a) for a in parent}


def rebuild(world):
    world.blocks = compute(world)


def occupancy(world):
    """block id -> set of train ids whose body covers an atom in the block."""
    occ = {}
    for t in world.trains:
        for atom in t.covered_atoms(world):
            b = world.blocks.get(atom)
            if b is not None:
                occ.setdefault(b, set()).add(t.id)
    return occ


def signal_red(world, occ, key, ignore_train=None):
    """True if the signal at `key` = (cell, exit_dir) shows red: the block(s)
    beyond the boundary are occupied (optionally ignoring one train)."""
    cell, e = key
    nc = neighbor(cell, e)
    oe = opposite(e)
    for j, q in enumerate(world.pieces(nc)):
        if oe in (q.a, q.b):
            occs = occ.get(world.blocks.get((nc, j)), set())
            if ignore_train is not None:
                occs = occs - {ignore_train}
            if occs:
                return True
    return False
