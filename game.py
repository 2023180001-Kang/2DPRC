"""Pure Python game state, usable in tests without opening a window."""

from dataclasses import dataclass, field

from settings import ANIMATIONS, FRAME_COUNT, GROUND_Y, RUN_SPEED, WALK_SPEED, WIDTH


@dataclass
class Controls:
    held: set[str] = field(default_factory=set)
    focused: bool = True

    def set_key(self, key, down):
        if key not in {"left", "right", "r"}:
            return
        if down and self.focused:
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

    @property
    def frame(self):
        return int(self.animation_time * ANIMATIONS[self.state][1]) % FRAME_COUNT

    @property
    def row(self):
        return ANIMATIONS[self.state][0]

    def update(self, dt, controls):
        if controls.direction:
            self.facing = controls.direction
        speed = RUN_SPEED if "r" in controls.held else WALK_SPEED
        self.x += controls.direction * speed * dt
        next_state = "WALK" if controls.direction else "IDLE"
        if controls.direction and "r" in controls.held:
            next_state = "RUN"
        if next_state != self.state:
            self.state = next_state
            self.animation_time = 0.0
        else:
            self.animation_time += dt
