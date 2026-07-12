"""Global constants: physics, colors, sizes, timing."""

# --- physics (units: cells, seconds) ---
ACCEL = 3.0          # acceleration, cells/s^2
BRAKE = 5.0          # service braking, cells/s^2
FRICTION = 0.4       # coasting deceleration for driven trains
VMAX_AI = 6.0        # top speed of scheduled trains
VMAX_DRIVE = 9.0     # top speed under manual control
TRAIN_LENGTH = 2.2   # cells
DWELL_TIME = 2.0     # seconds stopped at an intermediate schedule stop
STOP_MARGIN = 0.12   # stop this far short of a red signal / stop point
ARRIVE_EPS = 0.16    # distance considered "arrived" (must exceed STOP_MARGIN)

# --- camera ---
SCALE_MIN = 8.0      # px per cell
SCALE_MAX = 96.0
SCALE_START = 40.0

# --- window ---
WIN_W, WIN_H = 1280, 800
FPS = 60

SAVE_FILE = "layout.json"

# --- colors ---
COL_BG = (24, 26, 30)
COL_GRID = (40, 43, 48)
COL_GRID_MAJOR = (52, 56, 62)
COL_TRACK_CASING = (70, 74, 80)
COL_TRACK_RAIL = (150, 155, 162)
COL_TRACK_BRIDGE = (205, 210, 218)
COL_BRIDGE_EDGE = (110, 100, 60)
COL_SWITCH_ACTIVE = (240, 240, 130)
COL_PLATFORM = (60, 90, 120)
COL_PLATFORM_TXT = (170, 200, 230)
COL_YARD = (80, 70, 45)
COL_SIGNAL_RED = (230, 60, 50)
COL_SIGNAL_GREEN = (70, 210, 90)
COL_SIGNAL_POST = (130, 130, 130)
COL_TRAIN_BODY = (90, 140, 220)
COL_TRAIN_HEAD_AI = (80, 210, 120)
COL_TRAIN_HEAD_DRIVEN = (250, 160, 60)
COL_TRAIN_HEAD_IDLE = (180, 180, 190)
COL_TRAIN_SELECTED = (255, 255, 255)
COL_GHOST = (120, 200, 255)
COL_STOP_BADGE = (250, 200, 70)
COL_HUD_BG = (14, 15, 18)
COL_HUD_TXT = (210, 214, 220)
COL_HUD_DIM = (130, 134, 140)
COL_MSG = (255, 230, 140)
COL_SPAD = (255, 70, 60)
