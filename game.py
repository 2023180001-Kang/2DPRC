"""Pure Python game state, usable in tests without opening a window."""

from dataclasses import dataclass

from settings import FRAME_COUNT, GROUND_Y, IDLE_FPS, WIDTH


@dataclass
class Player:
    x: float = WIDTH / 2
    foot_y: float = GROUND_Y
    state: str = "IDLE"
    animation_time: float = 0.0

    @property
    def frame(self):
        return int(self.animation_time * IDLE_FPS) % FRAME_COUNT

    def update(self, dt):
        self.animation_time += dt
