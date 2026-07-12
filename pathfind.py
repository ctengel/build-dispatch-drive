"""Dijkstra over directed atoms. Goal = any directed atom in the target cell.
No mid-route reversal: edges follow graph.successors only."""

import heapq

from graph import successors
from geometry import piece_len


def find_path(world, starts, goal_cell):
    """Cheapest path from any of `starts` (directed atoms) to `goal_cell`.

    Returns (cost, [directed atoms from start to goal inclusive]) or None.
    """
    dist = {}
    parent = {}
    heap = []
    for s in starts:
        cell, idx, _e = s
        ps = world.pieces(cell)
        if 0 <= idx < len(ps):
            dist[s] = 0.0
            parent[s] = None
            heapq.heappush(heap, (0.0, s))
    while heap:
        d, cur = heapq.heappop(heap)
        if d > dist.get(cur, float("inf")):
            continue
        if cur[0] == goal_cell:
            path = []
            n = cur
            while n is not None:
                path.append(n)
                n = parent[n]
            path.reverse()
            return d, path
        for nxt in successors(world, cur):
            p = world.tracks[nxt[0]][nxt[1]]
            nd = d + piece_len(p.a, p.b)
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                parent[nxt] = cur
                heapq.heappush(heap, (nd, nxt))
    return None
