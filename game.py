"""Pure Python game state, usable in tests without opening a window."""

from dataclasses import dataclass, field
from random import Random

from settings import (
    ANIMATIONS, FRAME_COUNT, GRAVITY, GROUND_Y, ITEM_WIDTHS, JUMP_SPEED, MAX_HEALTH, MAX_JUMPS,
    PICKUP_RADIUS, PLAYER_HALF_WIDTH, RUN_SPEED, WALK_SPEED, WIDTH,
)


@dataclass(frozen=True)
class Item:
    kind: str
    x: float
    foot_y: float = GROUND_Y


def spawn_items(rng=None):
    rng = rng if rng is not None else Random()
    count = rng.randint(3, 5)
    kinds = list(ITEM_WIDTHS)
    kinds += rng.choices(kinds, k=count - len(kinds))
    rng.shuffle(kinds)
    width = max(ITEM_WIDTHS.values())
    # Spaced slots keep items apart and leave the player's starting position clear.
    slots = [x for x in range(width, WIDTH - width + 1, 2 * width)
             if abs(x - WIDTH / 2) > PLAYER_HALF_WIDTH + width]
    positions = rng.sample(slots, count)
    return [Item(kind, x + rng.uniform(-width / 4, width / 4))
            for kind, x in zip(kinds, positions)]


@dataclass
class Controls:
    held: set[str] = field(default_factory=set)
    focused: bool = True
    jump_requested: bool = False
    pickup_requested: bool = False

    def set_key(self, key, down):
        if key not in {"left", "right", "lshift", "rshift", "space", "f"}:
            return
        if down and self.focused:
            if key == "space" and key not in self.held:
                self.jump_requested = True
            if key == "f" and key not in self.held:
                self.pickup_requested = True
            self.held.add(key)
        else:
            self.held.discard(key)

    @property
    def direction(self):
        return int("right" in self.held) - int("left" in self.held)

    @property
    def running(self):
        return bool(self.held & {"lshift", "rshift"})


@dataclass
class Player:
    x: float = WIDTH / 2
    foot_y: float = GROUND_Y
    state: str = "IDLE"
    facing: int = 1
    animation_time: float = 0.0
    vertical_speed: float = 0.0
    health: int = MAX_HEALTH
    weapon: str | None = None
    jump_count: int = 0

    @property
    def grounded(self):
        return self.foot_y <= GROUND_Y and self.vertical_speed == 0.0

    @property
    def frame(self):
        frame = int(self.animation_time * ANIMATIONS[self.state][1] + 1e-9)
        return min(frame, FRAME_COUNT - 1) if self.state == "JUMP" else frame % FRAME_COUNT

    @property
    def row(self):
        return ANIMATIONS[self.state][0]

    def pick_up(self, items, controls):
        requested = controls.pickup_requested
        controls.pickup_requested = False
        if not requested or not self.grounded or not items:
            return False
        distance, index = min(
            ((item.x - self.x) ** 2 + (item.foot_y - self.foot_y) ** 2, index)
            for index, item in enumerate(items)
        )
        if distance > PICKUP_RADIUS ** 2:
            return False
        previous = self.weapon
        self.weapon = items.pop(index).kind
        if previous is not None:
            items.append(Item(previous, self.x))
        return True

    def update(self, dt, controls):
        if controls.jump_requested and (self.grounded or 0 < self.jump_count < MAX_JUMPS):
            self.jump_count = 1 if self.grounded else self.jump_count + 1
            self.vertical_speed = JUMP_SPEED
        controls.jump_requested = False

        if not self.grounded:
            self.foot_y += self.vertical_speed * dt - 0.5 * GRAVITY * dt * dt
            self.vertical_speed -= GRAVITY * dt
            # Exact integration still leaves subpixel rounding at the landing time.
            if self.foot_y <= GROUND_Y + 1e-9 and self.vertical_speed <= 0:
                self.foot_y = GROUND_Y
                self.vertical_speed = 0.0
                self.jump_count = 0

        if controls.direction:
            self.facing = controls.direction
        speed = RUN_SPEED if controls.running else WALK_SPEED
        self.x += controls.direction * speed * dt
        self.x = max(PLAYER_HALF_WIDTH, min(WIDTH - PLAYER_HALF_WIDTH, self.x))
        next_state = "WALK" if controls.direction else "IDLE"
        if controls.direction and controls.running:
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
