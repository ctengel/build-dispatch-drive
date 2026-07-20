# Dispatch & Drive

A 2D top-down train game in Python (pygame-ce). Lay track on a grid, place
signals and platforms, dispatch scheduled trains, or take the controls
yourself.

```
python3 -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
pip install pygame-ce
python main.py             # empty world
python main.py --demo      # small demo layout with two trains
python main.py mymap.json  # use mymap.json as the save file (loads it if it exists)
```

The venv isn't optional on macOS (or most Linux distros): the Homebrew/system
Python is "externally managed" and refuses a bare `pip install`.

## Modes (keys 1 / 2 / 3 / 4)

### 1 — Build
Lay out the railway. The simulation keeps running while you build.

| Key / action | Effect |
|---|---|
| `T` + **drag** | Paint track through cells; drag at ~45° to lay diagonals, turn mid-drag to lay curves. Branches laid into an existing cell create a switch. |
| `T` + **Shift+drag** | Rubber-band one straight run from the start cell, snapped to the nearest of the 8 directions (ghost preview); commits on release |
| `B` | Toggle bridge/tunnel layer — layered track crosses ground track in the same cell without connecting |
| `S` + click | Place/remove a signal at the nearest track end (it faces trains leaving the cell in that direction) |
| `P` / `Y` + click | Toggle a platform / yard on a track cell |
| `W` + click (or right-click any mode) | Throw the nearest switch |
| `X` + click/drag | Delete track (topmost layer first), then platforms/yards |

Note: separate drags don't auto-connect at an angle — to join a new line to
an existing one with a curve, start the drag a couple of cells back *on* the
existing line and turn mid-drag.

### 2 — Operate / Dispatch
Click empty track to place a train (it is selected automatically). With a
train selected, click track cells to append numbered schedule stops, then
press `G` to dispatch. The train pathfinds stop to stop (reversing at stops
when that is shorter), waits 2 s at each intermediate stop, and holds at the
final stop awaiting new orders (one-shot schedule).

`Tab` cycle trains · `C` clear schedule · `Del` remove stopped train ·
`Esc` deselect (so the next click places a new train).

### 3 — Drive
Select a train (`Tab`/click) and take over: `Up`/`W` power, `Down`/`S` brake,
`Space` emergency stop, `R` reverse (when stopped), `G` hand back to the
dispatcher to resume its schedule. The camera follows your train.

### 4 — Drive (3D)
The same controls as Drive, rendered in perspective from the selected
train (same world, same save file). `C` toggles between the cab (first
person) and chase (third person) camera; `E` throws the first facing
switch ahead of the train. With no train selected you get an overview
of the layout — `Tab` to select one. Trains are plain rectangular
prisms for now; the mesh format documented in `render3d.py` is the
hook for loading real 3D models later.

## Signals
Automatic block signals: signals divide the track into blocks, and a signal
shows red while the block beyond it is occupied. Scheduled trains brake for
red signals and continue when they clear. A *driven* train that passes a red
is force-stopped and flagged **SIGNAL PASSED AT DANGER**.

## Everywhere
`F5` save layout + trains to the current file (`layout.json` unless one was
given on the command line) · `F9` load · `Shift+F5`/`Shift+F9` save as /
load from a typed filename (`.json` is appended if you give no extension) ·
mouse wheel or `+`/`-` zoom (`0` resets) · middle-drag or arrow keys pan ·
`F11` fullscreen · the window is resizable, and the HUD text scales up
with the window height.

On Mac keyboards the function keys default to media keys, so hold **Fn**
(e.g. Fn+F11) or enable "Use F1, F2, etc. keys as standard function keys"
in System Settings → Keyboard; macOS may also grab F11 itself for Show
Desktop.

## Tests
```
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_core.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_game.py
```
