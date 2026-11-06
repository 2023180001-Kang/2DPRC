from math import sqrt

WIDTH = 1280
HEIGHT = 720
TARGET_FPS = 60
FRAME_WIDTH = 256
FRAME_HEIGHT = 256
FRAME_COUNT = 8
FRAME_ROWS = 4
CHARACTER_SOURCE = "MainCharacter_pico2d_2048x1024.png"
ARMED_CHARACTER_SOURCE = "HoodMan_Weaponless_5States_2048x1280.png"
ARMED_FRAME_ROWS = 5
ARMED_ANIMATION_ROWS = {"IDLE": 0, "WALK": 1, "RUN": 2, "ATTACK": 3, "JUMP": 4}
ATTACK_FPS = 16
ATTACK_DURATION = FRAME_COUNT / ATTACK_FPS
FRAME_BOTTOM_PADDING = 12
CHARACTER_SCALE = 0.6
PLAYER_HALF_WIDTH = FRAME_WIDTH * CHARACTER_SCALE / 2
# Feet rest on the sidewalk just above the curb in newfirststage.png at 720p.
GROUND_Y = 140
ARROW_WIDTH = 80
ARROW_X = {-1: 16 + ARROW_WIDTH / 2, 1: WIDTH - 16 - ARROW_WIDTH / 2}
ARROW_SWAY_AMPLITUDE = 6.0
ARROW_SWAY_PERIOD = 1.2
ARROW_SPAWN_PADDING = 16
ARROW_TRIGGER_HALF_WIDTH = 30
STAGE_BACKGROUNDS = {1: "background", 2: "second_background"}
STAGE_ARROWS = {1: (1,), 2: (-1, 1)}
STAGE_ENTRY_LEFT_X = 128.0
STAGE_ENTRY_RIGHT_X = WIDTH - STAGE_ENTRY_LEFT_X
WALK_SPEED = 180.0
RUN_SPEED = WALK_SPEED * 8
JUMP_SPEED = 480.0 * sqrt(2.0)
GRAVITY = 1200.0
JUMP_DURATION = 2 * JUMP_SPEED / GRAVITY
MAX_JUMPS = 2
ANIMATIONS = {
    "IDLE": (0, 6), "WALK": (1, 8), "RUN": (2, 12), "JUMP": (3, FRAME_COUNT / JUMP_DURATION),
}
MAX_HEALTH = 3
HEALTH_BAR_WIDTH = 320
HUD_MARGIN = 16
ITEM_WIDTHS = {"dagger": 44, "steel_pipe": 64}
AIR_DROP_HEIGHT = 32.0
PICKUP_RADIUS = 56.0
PICKUP_HINT_SIZE = 22  # Layout area keeps the F at its original position without a keycap.
PICKUP_HINT_GAP = 10
# Hand offsets in source pixels from the centered character's feet, before facing flip.
WEAPON_HAND_OFFSETS = {
    "IDLE": ((27, 68), (27, 71), (36, 91), (37, 103), (36, 109), (27, 68), (28, 68), (28, 68)),
    "WALK": ((-15, 77), (-16, 75), (0, 77), (5, 81), (-4, 77), (-4, 78), (-35, 75), (-28, 78)),
    "RUN": ((23, 90), (21, 89), (-52, 83), (45, 91), (33, 86), (24, 88), (22, 85), (23, 90)),
    "ATTACK": ((16, 71), (-11, 79), (48, 103), (68, 126), (74, 108), (35, 93), (9, 76), (15, 70)),
    "JUMP": ((18, 68), (-48, 73), (-52, 87), (41, 101), (30, 69), (-40, 67), (7, 46), (9, 48)),
}
WEAPON_ATTACK_ANGLES = (65, 100, 35, 0, -25, -45, 25, 65)
