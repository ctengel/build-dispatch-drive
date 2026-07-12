"""World data model: sparse grid of track pieces, switches, signals,
platforms, yards, and trains — plus JSON save/load.

Terminology used across the codebase:
  atom          = (cell, piece_index)            a single piece of track
  directed atom = (cell, piece_index, entry_dir) an atom entered from one end
"""

import json
from collections import namedtuple

from geometry import DIR_NAMES, DIR_INDEX, DELTA, opposite, valid_pair

# a < b always (canonical); layer 0 = ground, 1 = bridge/tunnel
Piece = namedtuple("Piece", "a b layer")


class World:
    def __init__(self):
        self.tracks = {}     # (x,y) -> [Piece]
        self.switches = {}   # ((x,y), entry_dir) -> index into candidates(cell, entry_dir)
        self.signals = set() # ((x,y), exit_dir): passed when leaving cell toward exit_dir
        self.platforms = {}  # (x,y) -> name
        self.yards = set()   # {(x,y)}
        self.trains = []
        self.next_train_id = 1
        self.next_platform_no = 1
        self.blocks = {}     # atom -> block id; maintained by blocks.rebuild()

    # ---- queries ----

    def pieces(self, cell):
        return self.tracks.get(cell, [])

    def candidates(self, cell, d):
        """Indices of pieces in `cell` having an end at direction d, in track order."""
        return [i for i, p in enumerate(self.pieces(cell)) if d in (p.a, p.b)]

    def is_switch(self, cell, d):
        return len(self.candidates(cell, d)) >= 2

    def switch_choice(self, cell, d):
        """Piece index currently selected for trains entering `cell` at end d."""
        cand = self.candidates(cell, d)
        if not cand:
            return None
        return cand[self.switches.get((cell, d), 0) % len(cand)]

    def set_switch_for_piece(self, cell, d, piece_idx):
        cand = self.candidates(cell, d)
        if piece_idx in cand and len(cand) >= 2:
            self.switches[(cell, d)] = cand.index(piece_idx)

    def cycle_switch(self, cell, d):
        cand = self.candidates(cell, d)
        if len(cand) >= 2:
            self.switches[(cell, d)] = (self.switches.get((cell, d), 0) + 1) % len(cand)
            return True
        return False

    def switch_entries(self, cell):
        """Direction ends of `cell` that form a facing switch."""
        return [d for d in range(8) if self.is_switch(cell, d)]

    def ends_in_cell(self, cell):
        ends = set()
        for p in self.pieces(cell):
            ends.add(p.a)
            ends.add(p.b)
        return ends

    def occupied_cells(self):
        cells = set()
        for t in self.trains:
            for (c, _i) in t.covered_atoms(self):
                cells.add(c)
        return cells

    # ---- edits ----

    def add_piece(self, cell, a, b, layer=0):
        if a > b:
            a, b = b, a
        if not valid_pair(a, b):
            return False
        p = Piece(a, b, layer)
        lst = self.tracks.setdefault(cell, [])
        if p in lst:
            return False
        lst.append(p)
        return True

    def remove_piece(self, cell, idx):
        lst = self.tracks.get(cell)
        if not lst or not (0 <= idx < len(lst)):
            return None
        p = lst.pop(idx)
        if not lst:
            del self.tracks[cell]
        # candidate lists shifted: drop this cell's switch settings (default back to 0)
        for key in [k for k in self.switches if k[0] == cell]:
            del self.switches[key]
        # signals on ends that no longer exist
        ends = self.ends_in_cell(cell)
        for key in [s for s in self.signals if s[0] == cell and s[1] not in ends]:
            self.signals.discard(key)
        return p

    def toggle_signal(self, cell, d):
        """Place/remove a signal at end d of `cell` (train passes it leaving toward d)."""
        if d not in self.ends_in_cell(cell):
            return False
        key = (cell, d)
        if key in self.signals:
            self.signals.discard(key)
        else:
            self.signals.add(key)
        return True

    def toggle_platform(self, cell):
        if cell in self.platforms:
            del self.platforms[cell]
        else:
            self.platforms[cell] = "P%d" % self.next_platform_no
            self.next_platform_no += 1

    def toggle_yard(self, cell):
        if cell in self.yards:
            self.yards.discard(cell)
        else:
            self.yards.add(cell)

    # ---- save / load ----

    def to_dict(self):
        return {
            "version": 1,
            "track": [{"x": c[0], "y": c[1],
                       "pieces": [{"a": DIR_NAMES[p.a], "b": DIR_NAMES[p.b],
                                   "layer": p.layer} for p in ps]}
                      for c, ps in sorted(self.tracks.items())],
            "switches": [{"x": c[0], "y": c[1], "entry": DIR_NAMES[d], "index": v}
                         for (c, d), v in sorted(self.switches.items())],
            "signals": [{"x": c[0], "y": c[1], "dir": DIR_NAMES[d]}
                        for (c, d) in sorted(self.signals)],
            "platforms": [{"x": c[0], "y": c[1], "name": n}
                          for c, n in sorted(self.platforms.items())],
            "yards": [{"x": c[0], "y": c[1]} for c in sorted(self.yards)],
            "trains": [t.to_dict() for t in self.trains],
        }

    def from_dict(self, data):
        from train import Train
        warnings = []
        self.__init__()
        for rec in data.get("track", []):
            cell = (rec["x"], rec["y"])
            for pr in rec.get("pieces", []):
                a, b = DIR_INDEX.get(pr["a"], -1), DIR_INDEX.get(pr["b"], -1)
                if not self.add_piece(cell, a, b, pr.get("layer", 0)):
                    warnings.append("dropped invalid piece at %s" % (cell,))
        for rec in data.get("switches", []):
            cell, d = (rec["x"], rec["y"]), DIR_INDEX.get(rec["entry"], -1)
            if self.is_switch(cell, d):
                self.switches[(cell, d)] = rec["index"] % len(self.candidates(cell, d))
        for rec in data.get("signals", []):
            cell, d = (rec["x"], rec["y"]), DIR_INDEX.get(rec["dir"], -1)
            if d in self.ends_in_cell(cell):
                self.signals.add((cell, d))
            else:
                warnings.append("dropped signal at %s" % (cell,))
        for rec in data.get("platforms", []):
            self.platforms[(rec["x"], rec["y"])] = rec["name"]
            no = rec["name"][1:]
            if no.isdigit():
                self.next_platform_no = max(self.next_platform_no, int(no) + 1)
        for rec in data.get("yards", []):
            self.yards.add((rec["x"], rec["y"]))
        for rec in data.get("trains", []):
            t = Train.from_dict(rec, self)
            if t is None:
                warnings.append("dropped train %s (invalid position)" % rec.get("id"))
            else:
                self.trains.append(t)
                self.next_train_id = max(self.next_train_id, t.id + 1)
        return warnings

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=1)

    def load(self, path):
        with open(path) as f:
            data = json.load(f)
        warnings = self.from_dict(data)
        import blocks
        blocks.rebuild(self)
        # re-derive AI plans for trains that were en route
        for t in self.trains:
            if t.state in ("running", "dwelling"):
                t.state = "idle"
                if not t.dispatch(self):
                    warnings.append("train %d: no route after load" % t.id)
        return warnings
