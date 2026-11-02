"""Pure Python game state, usable in tests without opening a window."""

from dataclasses import dataclass, field

from settings import (
    ANIMATIONS, FRAME_COUNT, GRAVITY, GROUND_Y, JUMP_SPEED, PLAYER_HALF_WIDTH,
    RUN_SPEED, WALK_SPEED, WIDTH,
)


@dataclass
class Controls:
    held: set[str] = field(default_factory=set)
    focused: bool = True
    jump_requested: bool = False

    def set_key(self, key, down):
        if key not in {"left", "right", "r", "space"}:
            return
        if down and self.focused:
            if key == "space" and key not in self.held:
                self.jump_requested = True
            self.held.add(key)
        else:
            self.held.discard(key)

    @property
    def direction(self):
        return int("right" in self.held) - int("left" in self.held)


@dataclass
class Player:
    x: float = WIDTH / 2
    foot_y: float = GROUND_Y
    state: str = "IDLE"
    facing: int = 1
    animation_time: float = 0.0
    vertical_speed: float = 0.0

    @property
    def grounded(self):
        return self.foot_y <= GROUND_Y and self.vertical_speed == 0.0

    @property
    def frame(self):
        frame = int(self.animation_time * ANIMATIONS[self.state][1])
        return min(frame, FRAME_COUNT - 1) if self.state == "JUMP" else frame % FRAME_COUNT

    @property
    def row(self):
        return ANIMATIONS[self.state][0]

    def update(self, dt, controls):
        if controls.jump_requested and self.grounded:
            self.vertical_speed = JUMP_SPEED
        controls.jump_requested = False

        if not self.grounded:
            self.foot_y += self.vertical_speed * dt - 0.5 * GRAVITY * dt * dt
            self.vertical_speed -= GRAVITY * dt
            # Exact integration still leaves subpixel rounding at the landing time.
            if self.foot_y <= GROUND_Y + 1e-9 and self.vertical_speed <= 0:
                self.foot_y = GROUND_Y
                self.vertical_speed = 0.0

        if controls.direction:
            self.facing = controls.direction
        speed = RUN_SPEED if "r" in controls.held else WALK_SPEED
        self.x += controls.direction * speed * dt
        self.x = max(PLAYER_HALF_WIDTH, min(WIDTH - PLAYER_HALF_WIDTH, self.x))
        next_state = "WALK" if controls.direction else "IDLE"
        if controls.direction and "r" in controls.held:
            next_state = "RUN"
        if not self.grounded:
            next_state = "JUMP"
        if next_state != self.state:
            self.state = next_state
            self.animation_time = 0.0
        elif next_state != "JUMP":
            duration = FRAME_COUNT / ANIMATIONS[self.state][1]
            self.animation_time = (self.animation_time + dt) % duration
        if next_state == "JUMP":
            # Keep the pose aligned with the physical arc, including long frames.
            self.animation_time = (JUMP_SPEED - self.vertical_speed) / GRAVITY
