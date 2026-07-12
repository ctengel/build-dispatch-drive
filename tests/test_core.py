"""Headless core tests — plain asserts, no pytest.
Run: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_core.py
"""

import os
import sys
import math
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import geometry as g
import blocks
import pathfind
import train as train_mod
from world import World
from train import Train
from graph import successors, other_end

DT = 1 / 60


def make_oval():
    """Rectangular loop (1,1)-(8,5) with a passing loop along the top row
    between (2,1) and (7,1), dipping to y=2."""
    w = World()
    for x in range(2, 8):
        w.add_piece((x, 1), g.E, g.W)
        w.add_piece((x, 5), g.E, g.W)
    for y in range(2, 5):
        w.add_piece((1, y), g.N, g.S)
        w.add_piece((8, y), g.N, g.S)
    w.add_piece((1, 1), g.S, g.E)
    w.add_piece((8, 1), g.W, g.S)
    w.add_piece((8, 5), g.N, g.W)
    w.add_piece((1, 5), g.N, g.E)
    # passing loop
    w.add_piece((2, 1), g.SE, g.W)
    w.add_piece((3, 2), g.E, g.NW)
    for x in (4, 5):
        w.add_piece((x, 2), g.E, g.W)
    w.add_piece((6, 2), g.NE, g.W)
    w.add_piece((7, 1), g.E, g.SW)
    blocks.rebuild(w)
    return w


def sim(w, seconds, start=0.0):
    now = start
    for _ in range(int(seconds / DT)):
        train_mod.update_all(w, DT, now)
        now += DT
    return now


def test_geometry():
    assert g.opposite(g.N) == g.S and g.opposite(g.NE) == g.SW
    assert g.valid_pair(g.N, g.S)          # straight
    assert g.valid_pair(g.NE, g.SW)        # diagonal
    assert g.valid_pair(g.E, g.S)          # 90-degree corner
    assert g.valid_pair(g.W, g.SE)         # 45-degree curve
    assert not g.valid_pair(g.N, g.NE)     # hairpin
    assert not g.valid_pair(g.N, g.N)
    assert abs(g.piece_len(g.N, g.S) - 1.0) < 1e-9
    assert abs(g.piece_len(g.NE, g.SW) - math.sqrt(2)) < 1e-9
    # entering from either end traverses the same locus, mirrored
    L = g.piece_len(g.E, g.S)
    pa = g.point_on((0, 0), g.E, g.S, g.E, 0.25 * L)
    pb = g.point_on((0, 0), g.E, g.S, g.S, 0.75 * L)
    assert abs(pa[0] - pb[0]) < 1e-9 and abs(pa[1] - pb[1]) < 1e-9
    # endpoints land on the cell boundary points
    assert g.point_on((3, 4), g.N, g.S, g.N, 0.0) == (3.5, 4.0)
    print("geometry ok")


def test_save_load():
    w = make_oval()
    w.toggle_signal((1, 1), g.S)
    w.toggle_signal((8, 1), g.S)
    w.toggle_platform((4, 1))
    w.toggle_platform((4, 2))
    w.toggle_yard((4, 5))
    w.cycle_switch((2, 1), g.W)
    t = Train(1, ((4, 5), 0, g.W), 0.5)
    t.schedule = [(4, 1)]
    w.trains.append(t)
    w.next_train_id = 2
    path = os.path.join(tempfile.gettempdir(), "ttest_layout.json")
    w.save(path)
    w2 = World()
    warnings = w2.load(path)
    assert not warnings, warnings
    assert w2.to_dict() == w.to_dict()
    assert w2.switches[((2, 1), g.W)] == 1
    print("save/load ok")


def test_pathfind():
    w = make_oval()
    # eastbound from the bottom row to the top platform
    res = pathfind.find_path(w, [((4, 5), 0, g.W)], (4, 1))
    assert res is not None
    cost, path = res
    assert path[-1][0] == (4, 1)
    for a, b in zip(path, path[1:]):
        assert b in successors(w, a), (a, b)
    # unreachable cell
    assert pathfind.find_path(w, [((4, 5), 0, g.W)], (20, 20)) is None
    # direction is respected: westbound start must go the long way around
    res_w = pathfind.find_path(w, [((4, 5), 0, g.E)], (8, 3))
    assert res_w is not None and res_w[0] > 8
    # switch branching: eastbound through (2,1) can reach the passing loop
    res_loop = pathfind.find_path(w, [((1, 1), 0, g.S)], (4, 2))
    assert res_loop is not None
    assert any(a[0] == (3, 2) for a in res_loop[1])
    res_main = pathfind.find_path(w, [((1, 1), 0, g.S)], (4, 1))
    assert res_main is not None
    assert all(a[0][1] != 2 for a in res_main[1])  # stays on y=1
    print("pathfind ok")


def test_blocks():
    w = make_oval()
    assert len(set(w.blocks.values())) == 1
    w.toggle_signal((1, 1), g.S)
    w.toggle_signal((8, 1), g.S)
    blocks.rebuild(w)
    assert len(set(w.blocks.values())) == 2
    # bridge layer isolates crossing track that shares an end
    w2 = World()
    w2.add_piece((0, 0), g.N, g.S, layer=0)
    w2.add_piece((0, 0), g.N, g.E, layer=1)
    blocks.rebuild(w2)
    assert len(set(w2.blocks.values())) == 2
    w3 = World()
    w3.add_piece((0, 0), g.N, g.S, layer=0)
    w3.add_piece((0, 0), g.N, g.E, layer=0)
    blocks.rebuild(w3)
    assert len(set(w3.blocks.values())) == 1
    print("blocks ok")


def test_signal_aspects():
    w = make_oval()
    w.toggle_signal((1, 1), g.S)
    w.toggle_signal((8, 1), g.S)
    w.toggle_signal((1, 2), g.N)
    blocks.rebuild(w)
    # park a train on the right column (lower block)
    parked = Train(1, ((8, 3), 0, g.N), 0.5)
    w.trains.append(parked)
    occ = blocks.occupancy(w)
    assert blocks.signal_red(w, occ, ((1, 1), g.S))
    assert blocks.signal_red(w, occ, ((8, 1), g.S))
    assert not blocks.signal_red(w, occ, ((1, 2), g.N))
    # a train ignores its own occupancy
    assert not blocks.signal_red(w, occ, ((8, 1), g.S), ignore_train=1)
    print("signal aspects ok")


def test_schedule_run():
    w = make_oval()
    t = Train(1, ((4, 5), 0, g.W), 0.5)
    t.schedule = [(8, 3), (4, 1)]
    w.trains.append(t)
    assert t.dispatch(w)
    assert t.state == "running"
    sim(w, 40)
    assert t.state == "done", t.state
    assert t.path[0][0] == (4, 1), t.path[0]
    assert t.schedule_index == 2
    assert t.speed == 0.0
    print("schedule run ok (one-shot ends done)")


def test_red_signal_holds_train():
    w = make_oval()
    w.toggle_signal((1, 1), g.S)
    w.toggle_signal((8, 1), g.S)
    w.toggle_signal((8, 2), g.N)   # faces trains climbing the right column
    blocks.rebuild(w)
    parked = Train(1, ((6, 1), 0, g.W), 0.5)
    w.trains.append(parked)
    t = Train(2, ((6, 5), 0, g.W), 0.5)  # eastbound route is clearly shorter
    t.schedule = [(4, 1)]
    w.trains.append(t)
    assert t.dispatch(w)
    assert any(a[0] == (8, 2) for a in t.plan), "expected route via right column"
    now = sim(w, 30)
    assert t.state == "running" and t.speed == 0.0, (t.state, t.speed)
    assert t.path[0][0] == (8, 2), t.path[0]     # held at the signal
    # block clears -> train proceeds and arrives
    w.trains.remove(parked)
    sim(w, 30, start=now)
    assert t.state == "done" and t.path[0][0] == (4, 1)
    print("red signal holds train ok")


def test_spad():
    w = make_oval()
    w.toggle_signal((1, 1), g.S)
    w.toggle_signal((8, 1), g.S)
    w.toggle_signal((8, 2), g.N)
    blocks.rebuild(w)
    parked = Train(1, ((6, 1), 0, g.W), 0.5)
    w.trains.append(parked)
    t = Train(2, ((8, 4), 0, g.S), 0.5)  # on right column heading north
    w.trains.append(t)
    t.take_control()
    t.throttle = 1
    for i in range(int(20 / DT)):
        t.throttle = 1
        train_mod.update_all(w, DT, i * DT)
        if t.spad:
            break
    assert t.spad, "driven train should be flagged after passing the red"
    assert t.speed == 0.0
    assert t.path[0][0] == (8, 1)  # forced stop just past the signal
    print("spad ok")


def test_reverse():
    w = make_oval()
    t = Train(1, ((4, 5), 0, g.W), 0.8)
    w.trains.append(t)
    head_before = t.head_pos(w)
    assert t.reverse(w)
    head_after = t.head_pos(w)
    # new head is at the old tail: length behind, clamped to spawn history
    assert head_after != head_before
    c, i, e = t.path[0]
    assert c == (4, 5) and e == g.E  # flipped heading
    assert t.reverse(w)  # reversing twice is allowed while stopped
    print("reverse ok")


def main():
    test_geometry()
    test_save_load()
    test_pathfind()
    test_blocks()
    test_signal_aspects()
    test_schedule_run()
    test_red_signal_holds_train()
    test_spad()
    test_reverse()
    print("ALL CORE TESTS PASSED")


if __name__ == "__main__":
    main()
