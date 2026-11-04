from math import sqrt

WIDTH = 1280
HEIGHT = 720
TARGET_FPS = 60
FRAME_WIDTH = 256
FRAME_HEIGHT = 256
FRAME_COUNT = 8
FRAME_ROWS = 4
CHARACTER_SOURCE = "MainCharacter_pico2d_2048x1024.png"
FRAME_BOTTOM_PADDING = 12
CHARACTER_SCALE = 0.6
PLAYER_HALF_WIDTH = FRAME_WIDTH * CHARACTER_SCALE / 2
# Feet rest on the sidewalk just above the curb in newfirststage.png at 720p.
GROUND_Y = 140
WALK_SPEED = 180.0
RUN_SPEED = 320.0
JUMP_SPEED = 480.0 * sqrt(2.0)
GRAVITY = 1200.0
JUMP_DURATION = 2 * JUMP_SPEED / GRAVITY
MAX_JUMPS = 2
ANIMATIONS = {
    "IDLE": (0, 6), "WALK": (1, 8), "RUN": (2, 12), "JUMP": (3, FRAME_COUNT / JUMP_DURATION),
}
MAX_HEALTH = 3
HEART_SIZE = 44
HEART_GAP = 8
HUD_MARGIN = 16
ITEM_WIDTHS = {"dagger": 44, "steel_pipe": 64}
PICKUP_RADIUS = 56.0
# Hand offsets in source pixels from the centered character's feet, before facing flip.
WEAPON_HAND_OFFSETS = {
    "IDLE": ((24, 72),) * FRAME_COUNT,
    "WALK": ((24, 72), (26, 72), (24, 74), (22, 76), (24, 74), (26, 72), (24, 72), (22, 74)),
    "RUN": ((26, 90), (24, 92), (34, 102), (36, 100), (26, 90), (24, 92), (32, 100), (28, 96)),
    "JUMP": ((26, 54), (-36, 64), (-40, 76), (-48, 80), (-42, 68), (-40, 68), (24, 76), (24, 76)),
}
