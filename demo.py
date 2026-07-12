"""A small demo layout: oval main line with a passing loop, two platforms,
signals, a yard, a bridge crossing, and two trains ready to dispatch."""

import blocks
import geometry as g
from train import Train


def build(world):
    for x in range(2, 8):
        world.add_piece((x, 1), g.E, g.W)
        world.add_piece((x, 5), g.E, g.W)
    for y in range(2, 5):
        world.add_piece((1, y), g.N, g.S)
        world.add_piece((8, y), g.N, g.S)
    world.add_piece((1, 1), g.S, g.E)
    world.add_piece((8, 1), g.W, g.S)
    world.add_piece((8, 5), g.N, g.W)
    world.add_piece((1, 5), g.N, g.E)
    # passing loop along the top
    world.add_piece((2, 1), g.SE, g.W)
    world.add_piece((3, 2), g.E, g.NW)
    for x in (4, 5):
        world.add_piece((x, 2), g.E, g.W)
    world.add_piece((6, 2), g.NE, g.W)
    world.add_piece((7, 1), g.E, g.SW)
    # a bridge crossing the layout vertically at x=5
    for y in range(0, 7):
        world.add_piece((5, y), g.N, g.S, layer=1 if y in (1, 2, 5) else 0)
    world.toggle_signal((1, 1), g.S)
    world.toggle_signal((8, 1), g.S)
    world.toggle_signal((8, 2), g.N)
    world.toggle_signal((1, 2), g.N)
    world.toggle_platform((4, 1))
    world.toggle_platform((4, 2))
    world.toggle_yard((2, 5))
    blocks.rebuild(world)
    # park train 1 on the branch line so it doesn't block train 2's route
    t1 = Train(1, ((5, 3), 0, g.N), 0.5)
    t2 = Train(2, ((6, 5), 0, g.W), 0.5)
    t2.schedule = [(4, 1), (2, 5)]
    world.trains.extend([t1, t2])
    world.next_train_id = 3
