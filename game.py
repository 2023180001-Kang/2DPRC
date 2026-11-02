"""Pure Python game state, usable in tests without opening a window."""

from dataclasses import dataclass, field

from settings import FRAME_COUNT, GROUND_Y, IDLE_FPS, WALK_SPEED, WIDTH


@dataclass
class Controls:
    held: set[str] = field(default_factory=set)

    def set_key(self, key, down):
        if key not in {"left", "right", "r"}:
            return
        if down:
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
    animation_time: float = 0.0

    @property
    def frame(self):
        return int(self.animation_time * IDLE_FPS) % FRAME_COUNT

    def update(self, dt, controls):
        self.x += controls.direction * WALK_SPEED * dt
        self.animation_time += dt
