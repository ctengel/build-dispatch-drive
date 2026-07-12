# Dispatch & Drive

A 2D top-down train game in Python (pygame-ce). Lay track on a grid, place
signals and platforms, dispatch scheduled trains, or take the controls
yourself.

```
pip install pygame-ce
python main.py          # empty world
python main.py --demo   # small demo layout with two trains
```

## Modes (keys 1 / 2 / 3)

### 1 — Build
Lay out the railway. The simulation keeps running while you build.

| Key / action | Effect |
|---|---|
| `T` + **drag** | Paint track through cells; turn mid-drag to lay curves. Branches laid into an existing cell create a switch. |
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

## Signals
Automatic block signals: signals divide the track into blocks, and a signal
shows red while the block beyond it is occupied. Scheduled trains brake for
red signals and continue when they clear. A *driven* train that passes a red
is force-stopped and flagged **SIGNAL PASSED AT DANGER**.

## Everywhere
`F5` save layout + trains to `layout.json` · `F9` load ·
mouse wheel zoom · middle-drag or arrow keys pan.

## Tests
```
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_core.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_game.py
```
