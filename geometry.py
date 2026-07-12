"""Direction algebra and track-piece geometry.

A cell is a unit square; track pieces connect two of its 8 direction ends
(edge midpoints for cardinals, corners for diagonals). Each piece has one
precomputed polyline that serves both rendering and train positioning.
All coordinates are in cell units (floats), y grows downward.
"""

import math

N, NE, E, SE, S, SW, W, NW = range(8)
DIR_NAMES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
DIR_INDEX = {n: i for i, n in enumerate(DIR_NAMES)}
DELTA = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
# local coordinates of each direction end within the unit cell
END_POINT = [(0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (1.0, 1.0),
             (0.5, 1.0), (0.0, 1.0), (0.0, 0.5), (0.0, 0.0)]


def opposite(d):
    return (d + 4) % 8


def valid_pair(a, b):
    """Straights (sep 4), 45-degree curves (sep 3/5), 90-degree corners (sep 2/6)."""
    if not (0 <= a < 8 and 0 <= b < 8) or a == b:
        return False
    return ((b - a) % 8) in (2, 3, 4, 5, 6)


CURVE_SAMPLES = 8


def _build_polyline(a, b):
    p0, p2 = END_POINT[a], END_POINT[b]
    c = (0.5, 0.5)
    if (b - a) % 8 == 4:
        return [p0, c, p2]
    pts = []
    for i in range(CURVE_SAMPLES + 1):
        t = i / CURVE_SAMPLES
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


class PieceGeom:
    __slots__ = ("pts", "cum", "length")

    def __init__(self, pts):
        self.pts = pts
        cum = [0.0]
        for i in range(len(pts) - 1):
            cum.append(cum[-1] + math.hypot(pts[i + 1][0] - pts[i][0],
                                            pts[i + 1][1] - pts[i][1]))
        self.cum = cum
        self.length = cum[-1]

    def point_at(self, s):
        """Local (x, y) at arc length s from pts[0], clamped to the piece."""
        s = max(0.0, min(self.length, s))
        pts, cum = self.pts, self.cum
        for i in range(len(cum) - 1):
            if s <= cum[i + 1] or i == len(cum) - 2:
                seg = cum[i + 1] - cum[i]
                t = 0.0 if seg == 0 else (s - cum[i]) / seg
                return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
        return pts[-1]


# GEOM[(a, b, entry)] -> PieceGeom oriented so s=0 is at `entry`
GEOM = {}
for _a in range(8):
    for _b in range(_a + 1, 8):
        if valid_pair(_a, _b):
            _pl = _build_polyline(_a, _b)
            GEOM[(_a, _b, _a)] = PieceGeom(_pl)
            GEOM[(_a, _b, _b)] = PieceGeom(list(reversed(_pl)))


def piece_len(a, b):
    return GEOM[(a, b, a)].length


def point_on(cell, a, b, entry, s):
    """World position at arc length s into piece (a,b) of `cell`, entered at `entry`."""
    x, y = GEOM[(a, b, entry)].point_at(s)
    return cell[0] + x, cell[1] + y


def end_point(cell, d):
    """World position of direction end `d` of `cell`."""
    ex, ey = END_POINT[d]
    return cell[0] + ex, cell[1] + ey
