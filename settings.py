from math import sqrt

WIDTH = 1280
HEIGHT = 720
TARGET_FPS = 60
FRAME_WIDTH = 256
FRAME_HEIGHT = 256
FRAME_COUNT = 8
FRAME_ROWS = 4  # Living locomotion rows; the player sheet adds one death row.
CHARACTER_FRAME_ROWS = 5
CHARACTER_SOURCE = "HoodMan_NewSheet_2048x1280.png"
ARMED_CHARACTER_SOURCE = "HoodMan_Weaponless_5States_2048x1280.png"
ARMED_FRAME_ROWS = 5
ARMED_ANIMATION_ROWS = {"IDLE": 0, "WALK": 1, "RUN": 2, "ATTACK": 3, "JUMP": 4}
ATTACK_FPS = 16
ATTACK_DURATION = FRAME_COUNT / ATTACK_FPS
FRAME_BOTTOM_PADDING = 12
CHARACTER_SCALE = 0.6
PLAYER_HALF_WIDTH = FRAME_WIDTH * CHARACTER_SCALE / 2
# Feet rest on the chapter maps' sidewalk just above the curb at 720p.
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
RUN_SPEED = WALK_SPEED * 5
MOVE_ACCELERATION = 1800.0
MOVE_DECELERATION = 4500.0
TURN_DECELERATION = 6000.0
POST_KILL_TURN_DURATION = 0.5
RUN_ANIMATION_REFERENCE_SPEED = 360.0
GROUND_FRICTION = 900.0  # Constant sliding resistance, pixels/s^2.
GROUND_DRAG = 4.0  # Speed-proportional ground resistance, 1/s.
AIR_DRAG = 0.8  # Weaker resistance while airborne, 1/s.
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
# Right-hand offsets from the centered character's feet, before facing flip.
# In the right-facing sheet, the near-side right fist is normally left of the body.
WEAPON_HAND_OFFSETS = {
    "IDLE": ((-25, 61), (-28, 65), (-25, 90), (-25, 103), (-24, 110), (-25, 61), (-24, 60), (-26, 60)),
    "WALK": ((-15, 77), (-16, 75), (0, 77), (5, 81), (-4, 77), (-4, 78), (-35, 75), (-28, 78)),
    "RUN": ((-23, 77), (-20, 80), (-52, 83), (-45, 92), (-45, 86), (-36, 84), (-31, 74), (-24, 78)),
    "ATTACK": ((16, 71), (-11, 79), (48, 103), (68, 126), (74, 108), (35, 93), (9, 76), (15, 70)),
    "JUMP": ((18, 68), (-48, 73), (-52, 87), (-47, 81), (-52, 74), (-40, 67), (7, 46), (9, 48)),
}
# Lean the weapon tip 20 degrees forward from vertical, mirrored with facing.
WEAPON_CARRY_ANGLE = 70
WEAPON_ATTACK_ANGLES = (90, 120, 65, 20, -10, 40, 75, 90)
# Grip coordinates in the original item's image, normalized from bottom-left.
WEAPON_GRIPS = {"dagger": (0.20, 0.50), "steel_pipe": (0.90, 0.35)}
ENEMY_SOURCE = "hood_man_enemy_pico2d_2048x1024.png"
ENEMY_SCALE = 0.6
ENEMY_IDLE_FPS = 6
ENEMY_DEATH_FPS = 8
ENEMY_DEATH_DURATION = FRAME_COUNT / ENEMY_DEATH_FPS
ATTACK_RANGE = 100.0
ATTACK_HEIGHT_RANGE = 80.0
PLAYER_BODY_HALF_WIDTH = 24.0
PLAYER_BODY_HEIGHT = 128.0
ENEMY_BODY_HALF_WIDTH = 32.0
ENEMY_BODY_HEIGHT = 136.0
CORPSE_HALF_WIDTH = 70.0
CORPSE_HEIGHT = 40.0
COLLISION_STEP = 1 / 120
ENEMY_DETECTION_RANGE = 420.0
ENEMY_LOSE_RANGE = 560.0
ENEMY_CHASE_SPEED = 120.0
ENEMY_CHASE_FPS = 8
ENEMY_STOP_DISTANCE = ENEMY_BODY_HALF_WIDTH + PLAYER_BODY_HALF_WIDTH + 8.0
ENEMY_ATTACK_START_RANGE = 90.0
ENEMY_ATTACK_RANGE = 100.0
ENEMY_ATTACK_HEIGHT_RANGE = 80.0
ENEMY_ATTACK_FPS = 12
ENEMY_ATTACK_DURATION = FRAME_COUNT / ENEMY_ATTACK_FPS
ENEMY_ATTACK_HIT_TIME = 4 / ENEMY_ATTACK_FPS
ENEMY_ATTACK_COOLDOWN = 0.6
PLAYER_HURT_INVULNERABILITY = 0.8
# Blue gauge bounds in the original HP artwork, measured from the top-left.
HEALTH_FILL_BOUNDS = (420, 145, 1988, 234)
PLAYER_DEATH_ROW = 4
PLAYER_DEATH_FPS = 8
PLAYER_DEATH_FRAMES = {"BACKWARD": (0, 1, 2, 3, 4), "FORWARD": (5, 6, 7)}
