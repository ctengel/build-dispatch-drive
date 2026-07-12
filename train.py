"""Train kinematics, path following, one-shot schedule execution, and
signal interaction (AI braking curves, SPAD force-stop for driven trains)."""

import math
from collections import deque

import blocks
import pathfind
from config import (ACCEL, BRAKE, FRICTION, VMAX_AI, VMAX_DRIVE,
                    TRAIN_LENGTH, DWELL_TIME, STOP_MARGIN, ARRIVE_EPS)
from geometry import DIR_NAMES, DIR_INDEX, piece_len, point_on
from graph import other_end, exit_dir, next_driven, successors, flip


class Train:
    def __init__(self, tid, datom, offset=0.0):
        self.id = tid
        # path[0] is the atom under the head; older atoms behind it carry the body
        self.path = deque([datom])
        self.offset = offset      # distance traveled into path[0]'s piece
        self.speed = 0.0          # cells/s, always >= 0; heading lives in the atoms
        self.length = TRAIN_LENGTH
        self.plan = []            # directed atoms strictly ahead (AI route)
        self.schedule = []        # ordered stop cells [(x,y), ...]
        self.schedule_index = 0
        self.state = "idle"       # idle | running | dwelling | done | driven
        self.dwell_until = 0.0
        self.spad = False
        self.throttle = 0         # -1 brake / 0 coast / +1 power (driven only)
        self.note = ""            # transient HUD info set by the sim

    # ---- geometry along the body ----

    def _head_piece_len(self, world):
        c, i, _e = self.path[0]
        p = world.tracks[c][i]
        return piece_len(p.a, p.b)

    def head_pos(self, world):
        c, i, e = self.path[0]
        p = world.tracks[c][i]
        return point_on(c, p.a, p.b, e, self.offset)

    def point_at_back(self, world, s_back):
        """World position s_back cells behind the head, along the path."""
        s = self.offset - s_back
        for k, (c, i, e) in enumerate(self.path):
            p = world.tracks[c][i]
            plen = piece_len(p.a, p.b)
            if k > 0:
                s += plen
            if s >= 0 or k == len(self.path) - 1:
                return point_on(c, p.a, p.b, e, max(0.0, s))
        return self.head_pos(world)

    def covered_atoms(self, world):
        """Atoms under the body: head plus history until `length` is covered."""
        out = []
        covered = self.offset
        for k, (c, i, _e) in enumerate(self.path):
            out.append((c, i))
            if k > 0:
                p = world.tracks[c][i]
                covered += piece_len(p.a, p.b)
            if covered >= self.length:
                break
        return out

    def _trim_path(self, world):
        covered = self.offset
        keep = 1
        for (c, i, _e) in list(self.path)[1:]:
            if covered >= self.length + 0.5:
                break
            p = world.tracks[c][i]
            covered += piece_len(p.a, p.b)
            keep += 1
        while len(self.path) > keep:
            self.path.pop()

    # ---- reversal (standstill only) ----

    def reversed_start(self, world):
        """Head datom the train would have after reversing (no mutation).
        Returns (datom, new_offset, atoms_kept)."""
        r = self.length - self.offset
        k = 0
        atoms = list(self.path)
        # find the atom containing the tail and the tail's distance t from its entry
        if r <= 0:
            t = self.offset - self.length
        else:
            t = 0.0
            for k in range(1, len(atoms)):
                c, i, _e = atoms[k]
                p = world.tracks[c][i]
                plen = piece_len(p.a, p.b)
                if r <= plen:
                    t = plen - r
                    break
                r -= plen
            else:
                k = len(atoms) - 1
                t = 0.0
        tail = atoms[k]
        c, i, _e = tail
        p = world.tracks[c][i]
        new_head = flip(world, tail)
        return new_head, piece_len(p.a, p.b) - t, k + 1

    def reverse(self, world):
        if self.speed > 0:
            return False
        new_head, new_offset, kept = self.reversed_start(world)
        old = list(self.path)[:kept]
        self.path = deque(flip(world, a) for a in reversed(old))
        self.offset = new_offset
        self.plan = []
        return True

    # ---- scheduling ----

    def dispatch(self, world):
        """Route to the current schedule stop; tries both headings. Returns True
        if a route was found (state becomes running)."""
        if not self.schedule or self.schedule_index >= len(self.schedule):
            return False
        goal = self.schedule[self.schedule_index]
        fwd = pathfind.find_path(world, [self.path[0]], goal)
        if self.speed > 0:
            rev = None  # a moving train may only re-route forward
        else:
            rev_head, _off, _kept = self.reversed_start(world)
            rev = pathfind.find_path(world, [rev_head], goal)
        if fwd is None and rev is None:
            self.state = "idle"
            self.note = "no route"
            return False
        if fwd is None or (rev is not None and rev[0] < fwd[0]):
            self.reverse(world)
            path = rev[1]
        else:
            path = fwd[1]
        self.plan = path[1:]
        self.state = "running"
        self.spad = False
        self.note = ""
        return True

    def take_control(self):
        self.state = "driven"
        self.plan = []
        self.throttle = 0

    def release_control(self):
        if self.state == "driven":
            self.state = "idle"
            self.throttle = 0

    # ---- per-tick update ----

    def _stop_distance(self, world, occ):
        """(distance, is_stop_point) to the nearest constraint: the next red
        signal boundary (is_stop_point=False) or the midpoint of the final
        planned atom, i.e. the schedule stop (is_stop_point=True)."""
        c, i, e = self.path[0]
        p = world.tracks[c][i]
        dist = piece_len(p.a, p.b) - self.offset
        if not self.plan:
            return piece_len(p.a, p.b) * 0.5 - self.offset, True
        prev = self.path[0]
        for k, nxt in enumerate(self.plan):
            pc, pi, pe = prev
            pp = world.tracks[pc][pi]
            ex = other_end(pp, pe)
            if (pc, ex) in world.signals and \
                    blocks.signal_red(world, occ, (pc, ex), ignore_train=self.id):
                return dist, False  # stop before this boundary
            nc, ni, _ne = nxt
            np_ = world.tracks[nc][ni]
            nlen = piece_len(np_.a, np_.b)
            if k == len(self.plan) - 1:
                return dist + nlen * 0.5, True
            dist += nlen
            prev = nxt
        return dist, True

    def update(self, dt, world, occ, now):
        if self.state == "dwelling":
            if now >= self.dwell_until:
                self.dispatch(world)
            return

        if self.state == "driven":
            if self.throttle > 0:
                self.speed = min(VMAX_DRIVE, self.speed + ACCEL * dt)
            elif self.throttle < 0:
                self.speed = max(0.0, self.speed - BRAKE * dt)
            else:
                self.speed = max(0.0, self.speed - FRICTION * dt)
        elif self.state == "running":
            dist, at_stop = self._stop_distance(world, occ)
            if at_stop and dist <= ARRIVE_EPS and self.speed <= 0.6:
                self.speed = 0.0
                self._arrive(now)
                return
            v_allow = math.sqrt(max(0.0, 2.0 * BRAKE * (dist - STOP_MARGIN)))
            if self.speed > v_allow:
                self.speed = max(v_allow, self.speed - BRAKE * dt)
            else:
                self.speed = min(v_allow, VMAX_AI, self.speed + ACCEL * dt)
        else:  # idle / done: bleed off any residual speed
            self.speed = max(0.0, self.speed - BRAKE * dt)

        if self.speed > 0:
            self._advance(dt, world, occ)
        self._trim_path(world)

    def _arrive(self, now):
        self.schedule_index += 1
        if self.schedule_index >= len(self.schedule):
            self.state = "done"
        else:
            self.state = "dwelling"
            self.dwell_until = now + DWELL_TIME

    def _advance(self, dt, world, occ):
        self.offset += self.speed * dt
        guard = 0
        while guard < 64:
            guard += 1
            c, i, e = self.path[0]
            p = world.tracks[c][i]
            plen = piece_len(p.a, p.b)
            if self.offset < plen:
                break
            ex = other_end(p, e)
            red = (c, ex) in world.signals and \
                blocks.signal_red(world, occ, (c, ex), ignore_train=self.id)
            if self.state == "running":
                if not self.plan or red:
                    # braking should prevent this; hard guard against overshoot
                    self.offset = plen - 1e-4
                    self.speed = 0.0
                    break
                nxt = self.plan.pop(0)
                nc, ni, ne = nxt
                if world.is_switch(nc, ne):
                    world.set_switch_for_piece(nc, ne, ni)
            else:  # driven (or coasting idle)
                nxt = next_driven(world, self.path[0])
                if nxt is None:
                    self.offset = plen - 1e-4
                    self.speed = 0.0
                    self.note = "end of track"
                    break
                if red and self.state == "driven":
                    # pass the signal, then force-stop and flag
                    self.spad = True
                    self.speed = 0.0
                    self.throttle = 0
            self.offset -= plen
            self.path.appendleft(nxt)
            if self.spad and self.speed == 0.0:
                break

    # ---- serialization ----

    def to_dict(self):
        c, i, e = self.path[0]
        return {"id": self.id, "x": c[0], "y": c[1], "piece": i,
                "entry": DIR_NAMES[e], "offset": round(self.offset, 4),
                "speed": round(self.speed, 4), "length": self.length,
                "state": self.state, "spad": self.spad,
                "schedule": [list(s) for s in self.schedule],
                "schedule_index": self.schedule_index}

    @staticmethod
    def from_dict(rec, world):
        cell = (rec["x"], rec["y"])
        idx = rec.get("piece", 0)
        entry = DIR_INDEX.get(rec.get("entry", ""), -1)
        ps = world.pieces(cell)
        if not (0 <= idx < len(ps)) or entry not in (ps[idx].a, ps[idx].b):
            return None
        t = Train(rec["id"], (cell, idx, entry), rec.get("offset", 0.0))
        t.speed = rec.get("speed", 0.0)
        t.length = rec.get("length", TRAIN_LENGTH)
        t.state = rec.get("state", "idle")
        t.spad = rec.get("spad", False)
        t.schedule = [tuple(s) for s in rec.get("schedule", [])]
        t.schedule_index = rec.get("schedule_index", 0)
        if t.state == "driven":
            t.state = "idle"
        return t


def update_all(world, dt, now):
    """Advance every train one tick; returns the occupancy map used."""
    occ = blocks.occupancy(world)
    for t in world.trains:
        t.update(dt, world, occ, now)
    return occ
