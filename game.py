"""Pure Python game state, usable in tests without opening a window."""

from dataclasses import dataclass, field, replace
from math import ceil, exp, expm1, log1p, sqrt
from random import Random

from settings import (
    AIR_DROP_HEIGHT, ANIMATIONS, ARMED_ANIMATION_ROWS, ATTACK_DURATION, ATTACK_FPS,
    FRAME_COUNT, GRAVITY, GROUND_Y, ITEM_WIDTHS, JUMP_SPEED, MAX_HEALTH, MAX_JUMPS,
    ARROW_SPAWN_PADDING, ARROW_SWAY_AMPLITUDE, ARROW_SWAY_PERIOD, ARROW_TRIGGER_HALF_WIDTH, ARROW_WIDTH, ARROW_X,
    PICKUP_RADIUS, PLAYER_HALF_WIDTH, RUN_SPEED, STAGE_ARROWS, STAGE_BACKGROUNDS,
    STAGE_ENTRY_LEFT_X, STAGE_ENTRY_RIGHT_X, WALK_SPEED, WIDTH,
    ATTACK_HEIGHT_RANGE, ATTACK_RANGE, ENEMY_DEATH_DURATION, ENEMY_DEATH_FPS, ENEMY_IDLE_FPS,
    MOVE_ACCELERATION, MOVE_DECELERATION, RUN_ANIMATION_REFERENCE_SPEED, TURN_DECELERATION,
    AIR_DRAG, GROUND_DRAG, GROUND_FRICTION,
    COLLISION_STEP, CORPSE_HALF_WIDTH, CORPSE_HEIGHT, ENEMY_BODY_HALF_WIDTH, ENEMY_BODY_HEIGHT,
    PLAYER_BODY_HALF_WIDTH, PLAYER_BODY_HEIGHT,
    ENEMY_CHASE_FPS, ENEMY_CHASE_SPEED, ENEMY_DETECTION_RANGE, ENEMY_LOSE_RANGE,
    ENEMY_SCALE, ENEMY_STOP_DISTANCE, FRAME_WIDTH,
    ENEMY_ATTACK_START_RANGE, ENEMY_ATTACK_RANGE, ENEMY_ATTACK_HEIGHT_RANGE,
    ENEMY_ATTACK_FPS, ENEMY_ATTACK_DURATION, ENEMY_ATTACK_HIT_TIME, ENEMY_ATTACK_COOLDOWN,
    PLAYER_HURT_INVULNERABILITY,
    POST_KILL_TURN_DURATION,
    PLAYER_DEATH_FPS, PLAYER_DEATH_FRAMES, PLAYER_DEATH_ROW,
)


@dataclass(frozen=True)
class Item:
    kind: str
    x: float
    foot_y: float = GROUND_Y
    vertical_speed: float = 0.0
    falling: bool = False

    def update(self, dt):
        if not self.falling:
            return self
        y = self.foot_y + self.vertical_speed * dt - 0.5 * GRAVITY * dt * dt
        speed = self.vertical_speed - GRAVITY * dt
        if y <= GROUND_Y + 1e-9:
            return replace(self, foot_y=GROUND_Y, vertical_speed=0.0, falling=False)
        return replace(self, foot_y=y, vertical_speed=speed)


def spawn_items(rng=None, spawn_x=WIDTH / 2, *, stage_number=1):
    rng = rng if rng is not None else Random()
    count = rng.randint(3, 5)
    kinds = list(ITEM_WIDTHS)
    kinds += rng.choices(kinds, k=count - len(kinds))
    rng.shuffle(kinds)
    width = max(ITEM_WIDTHS.values())
    jitter = width / 4
    arrow_clearance = ARROW_WIDTH / 2 + ARROW_SWAY_AMPLITUDE + ARROW_SPAWN_PADDING + width / 2 + jitter
    # Spaced slots keep items apart and leave the player's starting position clear.
    # Reserve full item width and jitter around every displayed arrow, including inactive exits.
    slots = [x for x in range(width, WIDTH - width + 1, 2 * width)
             if abs(x - spawn_x) > PLAYER_HALF_WIDTH + width
             and all(abs(x - ARROW_X[direction]) > arrow_clearance
                     for direction in STAGE_ARROWS[stage_number])]
    positions = rng.sample(slots, count)
    return [Item(kind, x + rng.uniform(-jitter, jitter))
            for kind, x in zip(kinds, positions)]


@dataclass
class Controls:
    held: set[str] = field(default_factory=set)
    focused: bool = True
    jump_requested: bool = False
    pickup_requested: bool = False
    attack_requested: bool = False

    def set_key(self, key, down):
        if key not in {"left", "right", "lshift", "rshift", "space", "f", "a"}:
            return
        if down and self.focused:
            if key == "space" and key not in self.held:
                self.jump_requested = True
            if key == "f" and key not in self.held:
                self.pickup_requested = True
            if key == "a" and key not in self.held:
                self.attack_requested = True
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
class Enemy:
    x: float = WIDTH / 2
    foot_y: float = GROUND_Y
    facing: int = -1
    state: str = "IDLE"
    animation_time: float = 0.0
    aware: bool = False
    attack_cooldown: float = 0.0
    attack_hit: bool = False

    @property
    def alive(self):
        return self.state in {"IDLE", "CHASE", "ATTACK"}

    @property
    def defeated(self):
        return self.state == "DEAD"

    @property
    def row(self):
        return {"IDLE": 0, "CHASE": 1, "ATTACK": 2}.get(self.state, 3)

    @property
    def collision_bounds(self):
        progress = 1.0 if self.defeated else (
            min(1.0, self.animation_time / ENEMY_DEATH_DURATION) if self.state == "DYING" else 0.0)
        half_width = ENEMY_BODY_HALF_WIDTH + (CORPSE_HALF_WIDTH - ENEMY_BODY_HALF_WIDTH) * progress
        height = ENEMY_BODY_HEIGHT + (CORPSE_HEIGHT - ENEMY_BODY_HEIGHT) * progress
        return self.x - half_width, self.foot_y, self.x + half_width, self.foot_y + height

    @property
    def frame(self):
        if self.defeated:
            return FRAME_COUNT - 1
        if self.state == "ATTACK":
            return min(int(self.animation_time * ENEMY_ATTACK_FPS + 1e-9), FRAME_COUNT - 1)
        if self.alive:
            fps = ENEMY_CHASE_FPS if self.state == "CHASE" else ENEMY_IDLE_FPS
            return int(self.animation_time * fps + 1e-9) % FRAME_COUNT
        return min(int(self.animation_time * ENEMY_DEATH_FPS + 1e-9), FRAME_COUNT - 1)

    def hit(self):
        if not self.alive:
            return False
        self.state, self.animation_time = "DYING", 0.0
        self.aware = False
        return True

    def try_hit(self, player):
        """Resolve one hit per swing throughout the active attack animation."""
        if not player.attacking or player.attack_hit:
            return False
        distance = player.facing * (self.x - player.x)
        if (0 <= distance <= ATTACK_RANGE
                and abs(player.foot_y - self.foot_y) <= ATTACK_HEIGHT_RANGE
                and self.hit()):
            player.attack_hit = True
            player.kill_turn_momentum = player.attack_momentum
            player.kill_turn_time = POST_KILL_TURN_DURATION
            return True
        return False

    def _update_attack(self, dt, player):
        self.animation_time = min(self.animation_time + dt, ENEMY_ATTACK_DURATION)
        # Crossing the hit time triggers once, even if a slow frame skips poses.
        if not self.attack_hit and self.animation_time >= ENEMY_ATTACK_HIT_TIME - 1e-9:
            self.attack_hit = True
            if player is not None:
                distance = self.facing * (player.x - self.x)
                if (0 <= distance <= ENEMY_ATTACK_RANGE
                        and abs(player.foot_y - self.foot_y) <= ENEMY_ATTACK_HEIGHT_RANGE):
                    player.take_damage(source_x=self.x)
        if self.animation_time >= ENEMY_ATTACK_DURATION - 1e-9:
            self.state, self.animation_time = "IDLE", 0.0
            self.attack_cooldown = ENEMY_ATTACK_COOLDOWN

    def update(self, dt, player=None):
        if self.state == "ATTACK":
            self._update_attack(dt, player)
            return
        if self.alive:
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
            previous_state = self.state
            next_state = "IDLE"
            if player is not None:
                dx = player.x - self.x
                distance = abs(dx)
                detection_range = ENEMY_LOSE_RANGE if self.aware else ENEMY_DETECTION_RANGE
                self.aware = distance <= detection_range
                if self.aware and dx != 0:
                    self.facing = 1 if dx > 0 else -1
                if (self.aware and player.health > 0 and self.attack_cooldown <= 1e-9
                        and distance <= ENEMY_ATTACK_START_RANGE
                        and abs(player.foot_y - self.foot_y) <= ENEMY_ATTACK_HEIGHT_RANGE):
                    self.state, self.animation_time, self.attack_hit = "ATTACK", 0.0, False
                    return
                if self.aware and dx != 0:
                    remaining = max(0.0, distance - ENEMY_STOP_DISTANCE)
                    half_width = FRAME_WIDTH * ENEMY_SCALE / 2
                    room = WIDTH - half_width - self.x if self.facing > 0 else self.x - half_width
                    travel = min(ENEMY_CHASE_SPEED * dt, remaining, max(0.0, room))
                    self.x += self.facing * travel
                    if remaining - travel > 1e-9 and room - travel > 1e-9:
                        next_state = "CHASE"
            else:
                self.aware = False
            self.state = next_state
            fps = ENEMY_CHASE_FPS if self.state == "CHASE" else ENEMY_IDLE_FPS
            self.animation_time = ((self.animation_time + dt) % (FRAME_COUNT / fps)
                                   if previous_state == self.state else 0.0)
        elif self.state == "DYING":
            self.animation_time = min(self.animation_time + dt, ENEMY_DEATH_DURATION)
            if self.animation_time >= ENEMY_DEATH_DURATION - 1e-9:
                self.animation_time = ENEMY_DEATH_DURATION
                self.state = "DEAD"


def spawn_enemy(rng=None, spawn_x=WIDTH / 2, *, stage_number=1):
    rng = rng if rng is not None else Random()
    clearance = ARROW_WIDTH / 2 + ARROW_SWAY_AMPLITUDE + ARROW_SPAWN_PADDING + PLAYER_HALF_WIDTH
    positions = [x for x in range(240, WIDTH - 239, 40)
                 if abs(x - spawn_x) > 2 * PLAYER_HALF_WIDTH
                 and all(abs(x - ARROW_X[direction]) > clearance
                         for direction in STAGE_ARROWS[stage_number])]
    x = rng.choice(positions)
    return Enemy(x=x, facing=-1 if x > spawn_x else 1)


def _integrate_speed(speed, target, acceleration, dt):
    """Integrate the ramp and any remaining constant-speed time exactly."""
    difference = target - speed
    if abs(difference) <= 1e-9:
        return target, target * dt
    ramp_time = min(dt, abs(difference) / acceleration)
    signed_acceleration = acceleration if difference > 0 else -acceleration
    next_speed = speed + signed_acceleration * ramp_time
    if dt >= abs(difference) / acceleration:
        next_speed = target
    distance = speed * ramp_time + 0.5 * signed_acceleration * ramp_time ** 2
    return next_speed, distance + target * (dt - ramp_time)


def _integrate_friction(speed, dt, grounded):
    """Integrate unpowered motion without crossing zero or depending on FPS."""
    if speed == 0 or dt == 0:
        return speed, 0.0
    if not grounded:
        decay = expm1(-AIR_DRAG * dt)
        return speed * exp(-AIR_DRAG * dt), -speed * decay / AIR_DRAG
    magnitude = abs(speed)
    stop_time = log1p(GROUND_DRAG * magnitude / GROUND_FRICTION) / GROUND_DRAG
    elapsed = min(dt, stop_time)
    terminal_offset = GROUND_FRICTION / GROUND_DRAG
    decay = expm1(-GROUND_DRAG * elapsed)
    next_magnitude = max(0.0, magnitude + (magnitude + terminal_offset) * decay)
    if dt >= stop_time or next_magnitude < 1e-9:
        next_magnitude = 0.0
    distance = (-(magnitude + terminal_offset) * decay - GROUND_FRICTION * elapsed) / GROUND_DRAG
    sign = 1 if speed > 0 else -1
    return sign * next_magnitude, sign * max(0.0, distance)


@dataclass
class Stage:
    items: list[Item]
    number: int = 1
    arrow_time: float = 0.0
    enemy: Enemy | None = None
    _items_by_stage: dict[int, list[Item]] = field(default_factory=dict, init=False, repr=False)
    _enemies_by_stage: dict[int, Enemy] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        self._items_by_stage[self.number] = self.items
        if self.enemy is None:
            spawn_x = WIDTH / 2 if self.number == 1 else STAGE_ENTRY_LEFT_X
            self.enemy = spawn_enemy(spawn_x=spawn_x, stage_number=self.number)
        self._enemies_by_stage[self.number] = self.enemy

    @property
    def background_key(self):
        return STAGE_BACKGROUNDS[self.number]

    @property
    def visible_arrows(self):
        return tuple(direction for direction in STAGE_ARROWS[self.number]
                     if direction < 0 or self.enemy.defeated)

    def hit_enemy(self, player):
        return self.enemy.try_hit(player)

    def update(self, dt, player=None):
        self.arrow_time = (self.arrow_time + dt) % ARROW_SWAY_PERIOD
        for index, item in enumerate(self.items):
            self.items[index] = item.update(dt)
        if player is not None:
            player.update_damage(dt)
        self.enemy.update(dt, player)

    def try_transition(self, player, controls, rng=None):
        if player.incapacitated:
            return False
        direction = next((direction for direction in self.visible_arrows
                          if abs(player.x - ARROW_X[direction]) <= ARROW_TRIGGER_HALF_WIDTH), 0)
        destination = self.number + direction
        if not direction or destination not in STAGE_BACKGROUNDS:
            return False
        entry_x = STAGE_ENTRY_LEFT_X if direction > 0 else STAGE_ENTRY_RIGHT_X
        was_grounded = player.grounded
        if destination not in self._items_by_stage:
            self._items_by_stage[destination] = spawn_items(rng, spawn_x=entry_x, stage_number=destination)
            self._enemies_by_stage[destination] = spawn_enemy(rng, spawn_x=entry_x, stage_number=destination)
        self._items_by_stage[self.number] = self.items
        self._enemies_by_stage[self.number] = self.enemy
        self.number = destination
        self.items = self._items_by_stage[destination]
        self.enemy = self._enemies_by_stage[destination]
        player.x = entry_x
        player.support_y = GROUND_Y
        # A fast step may reach the screen clamp and the exit together. Keep
        # that step's momentum when it is a valid transition, not a wall stop.
        if player.boundary_speed:
            player.horizontal_speed = player.boundary_speed
            player.boundary_speed = 0.0
        controls.jump_requested = controls.pickup_requested = controls.attack_requested = False
        # Airborne transitions move only x; preserve the entire ongoing jump.
        if was_grounded:
            player.foot_y = GROUND_Y
            player.vertical_speed = 0.0
            player.jump_count = 0
            player.state = "IDLE"
            player.animation_time = 0.0
            player.facing = direction
            player.update(0.0, controls)
        return True


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
    attack_time: float | None = None
    attack_hit: bool = False
    horizontal_speed: float = 0.0
    boundary_speed: float = 0.0
    support_y: float = GROUND_Y
    hurt_time: float = 0.0
    death_kind: str = "BACKWARD"
    death_time: float = 0.0
    attack_momentum: float = 0.0
    kill_turn_momentum: float = 0.0
    kill_turn_time: float = 0.0

    @property
    def incapacitated(self):
        return self.health <= 0

    @property
    def death_duration(self):
        return len(PLAYER_DEATH_FRAMES[self.death_kind]) / PLAYER_DEATH_FPS

    def _start_death(self, source_x=None):
        self.death_kind = ("FORWARD" if source_x is not None
                           and self.facing * (source_x - self.x) < 0 else "BACKWARD")
        self.state, self.death_time = "DYING", 0.0
        self.attack_time = None
        self.horizontal_speed = self.boundary_speed = 0.0
        self.vertical_speed = min(0.0, self.vertical_speed)
        self.support_y = GROUND_Y

    def _update_death(self, dt):
        if self.foot_y > GROUND_Y:
            self.foot_y += self.vertical_speed * dt - 0.5 * GRAVITY * dt * dt
            self.vertical_speed -= GRAVITY * dt
        if self.foot_y <= GROUND_Y:
            self.foot_y, self.vertical_speed = GROUND_Y, 0.0
        self.death_time = min(self.death_time + dt, self.death_duration)
        if self.death_time >= self.death_duration - 1e-9 and self.foot_y == GROUND_Y:
            self.death_time, self.state = self.death_duration, "DEAD"

    def take_damage(self, amount=1, *, source_x=None):
        if self.health <= 0 or self.hurt_time > 1e-9 or amount <= 0:
            return False
        self.health = max(0, self.health - amount)
        self.hurt_time = PLAYER_HURT_INVULNERABILITY
        if self.incapacitated:
            self._start_death(source_x)
        return True

    def update_damage(self, dt):
        self.hurt_time = max(0.0, self.hurt_time - dt)

    @property
    def grounded(self):
        return self.foot_y <= self.support_y and self.vertical_speed == 0.0

    @property
    def frame(self):
        if self.incapacitated:
            frames = PLAYER_DEATH_FRAMES[self.death_kind]
            return frames[min(int(self.death_time * PLAYER_DEATH_FPS + 1e-9), len(frames) - 1)]
        if self.attacking:
            return min(int(self.attack_time * ATTACK_FPS + 1e-9), FRAME_COUNT - 1)
        frame = int(self.animation_time * ANIMATIONS[self.state][1] + 1e-9)
        return min(frame, FRAME_COUNT - 1) if self.state == "JUMP" else frame % FRAME_COUNT

    @property
    def row(self):
        if self.incapacitated:
            return PLAYER_DEATH_ROW
        if self.weapon is not None or self.attacking:
            return ARMED_ANIMATION_ROWS[self.display_state]
        return ANIMATIONS[self.state][0]

    @property
    def attacking(self):
        return self.attack_time is not None and not self.incapacitated

    @property
    def display_state(self):
        if self.incapacitated:
            return "DEAD" if self.state == "DEAD" else "DYING"
        return "ATTACK" if self.attacking else self.state

    @property
    def character_key(self):
        if self.incapacitated:
            return "character"
        return "armed_character" if self.weapon is not None or self.attacking else "character"

    def pickup_target(self, items):
        """Share the ground/range/nearest-item rule with the interaction hint."""
        if self.incapacitated or not self.grounded:
            return None
        distance, index = min(
            (((item.x - self.x) ** 2 + (item.foot_y - self.foot_y) ** 2, index)
             for index, item in enumerate(items) if not item.falling),
            default=(float("inf"), None),
        )
        return index if distance <= PICKUP_RADIUS ** 2 else None

    def pick_up(self, items, controls):
        """Pick up/swap on the ground, or drop a held weapon on the ground or in the air."""
        requested = controls.pickup_requested
        controls.pickup_requested = False
        if self.incapacitated or not requested:
            return False
        index = self.pickup_target(items)
        previous = self.weapon
        if index is None and previous is None:
            return False
        self.weapon = items.pop(index).kind if index is not None else None
        self.attack_time = None
        if previous is not None:
            if self.grounded:
                items.append(Item(previous, self.x))
            else:
                items.append(Item(previous, self.x, self.foot_y + AIR_DROP_HEIGHT, falling=True))
        return True

    def move_horizontally(self, dt, controls, air_time=0.0):
        self.boundary_speed = 0.0
        if not controls.focused:
            self.horizontal_speed = 0.0
            self.attack_momentum = self.kill_turn_momentum = self.kill_turn_time = 0.0
            return 0.0, False
        target = controls.direction * (RUN_SPEED if controls.running else WALK_SPEED)
        if self.kill_turn_time > 0 and target * self.kill_turn_momentum < 0:
            # A kill may leave the player pressed against an expanding body.
            # Turn once at the attack's speed, rather than accelerating from 0.
            speed = max(abs(self.kill_turn_momentum), abs(self.horizontal_speed))
            self.horizontal_speed = controls.direction * min(speed, abs(target))
            self.kill_turn_momentum = self.kill_turn_time = 0.0
        distance = travel = 0.0
        if target == 0:
            # Keep momentum in the air, then apply floor friction only for the
            # portion of this frame after landing. Both integrals are exact.
            self.horizontal_speed, air_distance = _integrate_friction(self.horizontal_speed, air_time, False)
            self.horizontal_speed, ground_distance = _integrate_friction(self.horizontal_speed, dt - air_time, True)
            distance = air_distance + ground_distance
            travel = abs(air_distance) + abs(ground_distance)
        else:
            # Active direction input supplies traction/braking toward its target.
            if self.horizontal_speed * target < 0:
                brake_time = min(dt, abs(self.horizontal_speed) / TURN_DECELERATION)
                self.horizontal_speed, distance = _integrate_speed(
                    self.horizontal_speed, 0.0, TURN_DECELERATION, brake_time)
                travel = abs(distance)
                dt -= brake_time
            rate = MOVE_DECELERATION if abs(target) < abs(self.horizontal_speed) else MOVE_ACCELERATION
            self.horizontal_speed, remaining_distance = _integrate_speed(self.horizontal_speed, target, rate, dt)
            distance += remaining_distance
            travel += abs(remaining_distance)
        if self.attacking and not self.attack_hit and abs(self.horizontal_speed) > abs(self.attack_momentum):
            self.attack_momentum = self.horizontal_speed
        self.x = max(PLAYER_HALF_WIDTH, min(WIDTH - PLAYER_HALF_WIDTH, self.x + distance))
        blocked = ((self.x <= PLAYER_HALF_WIDTH and self.horizontal_speed < 0)
                   or (self.x >= WIDTH - PLAYER_HALF_WIDTH and self.horizontal_speed > 0))
        if blocked:
            self.boundary_speed = self.horizontal_speed
            self.horizontal_speed = 0.0
        return travel, blocked

    def _prepare_support(self, obstacle):
        left, _, right, top = obstacle.collision_bounds
        on_top = (left - PLAYER_BODY_HALF_WIDTH < self.x < right + PLAYER_BODY_HALF_WIDTH
                  and abs(self.foot_y - top) <= 1e-7 and self.vertical_speed == 0)
        was_supported = self.grounded and self.support_y > GROUND_Y
        self.support_y = top if on_top else GROUND_Y
        if was_supported and not on_top and self.foot_y > GROUND_Y:
            self.jump_count = max(1, self.jump_count)

    def _resolve_enemy_collision(self, obstacle, old_x, old_y, direction):
        left, bottom, right, top = obstacle.collision_bounds
        left -= PLAYER_BODY_HALF_WIDTH
        right += PLAYER_BODY_HALF_WIDTH
        overlaps = left + 1e-8 < self.x < right - 1e-8
        landed = (overlaps and self.vertical_speed <= 0
                  and old_y >= top - 1e-8 and self.foot_y <= top + 1e-8)
        if landed:
            self.foot_y, self.vertical_speed, self.jump_count = top, 0.0, 0
            self.support_y = top
        # Every body has finite height: sufficiently high jumps pass above it.
        blocks_side = (min(old_y, self.foot_y) < top - 1e-8
                       and max(old_y, self.foot_y) + PLAYER_BODY_HEIGHT > bottom + 1e-8)
        blocked = False
        if blocks_side:
            if old_x <= left + 1e-8 and self.x > left:
                self.x, blocked = left, True
            elif old_x >= right - 1e-8 and self.x < right:
                self.x, blocked = right, True
            elif left < self.x < right:
                self.x = left if old_x < obstacle.x or (old_x == obstacle.x and self.facing > 0) else right
                blocked = True
            elif abs(self.x - left) <= 1e-8 and direction > 0:
                blocked = True
            elif abs(self.x - right) <= 1e-8 and direction < 0:
                blocked = True
        if blocked and self.horizontal_speed * (self.x - obstacle.x) > 0:
            # Depenetration while escaping is not an impact into the body.
            blocked = False
        if blocked:
            self.horizontal_speed = self.boundary_speed = 0.0
        if self.support_y > GROUND_Y and not (
                left < self.x < right and abs(self.foot_y - top) <= 1e-7
                and self.vertical_speed == 0):
            was_grounded = self.grounded
            self.support_y = GROUND_Y
            if was_grounded:
                self.jump_count = max(1, self.jump_count)
        return landed, blocked

    def update(self, dt, controls, obstacle=None):
        if self.incapacitated:
            controls.jump_requested = controls.pickup_requested = controls.attack_requested = False
            if self.state not in {"DYING", "DEAD"}:
                self._start_death()
            self._update_death(dt)
            return False
        self.kill_turn_time = max(0.0, self.kill_turn_time - dt)
        if self.kill_turn_time <= 1e-9:
            self.kill_turn_momentum = self.kill_turn_time = 0.0
        attack_started = False
        if self.attack_time is not None:
            self.attack_time += dt
            if self.attack_time >= ATTACK_DURATION - 1e-9:
                self.attack_time = None
            # Requests made during an attack cannot queue or restart it.
        elif controls.attack_requested:
            self.attack_time = 0.0
            self.attack_hit = False
            self.attack_momentum = self.horizontal_speed
            attack_started = True
        controls.attack_requested = False

        if obstacle is None:
            self._update_motion(dt, controls)
        else:
            steps = max(1, ceil(dt / COLLISION_STEP))
            step = dt / steps
            boundary_speed = 0.0
            for _ in range(steps):
                self._prepare_support(obstacle)
                old_x, old_y = self.x, self.foot_y
                old_state, old_animation_time = self.state, self.animation_time
                self._update_motion(step, controls)
                if abs(self.boundary_speed) > abs(boundary_speed):
                    boundary_speed = self.boundary_speed
                direction = controls.direction if controls.focused else 0
                landed, body_blocked = self._resolve_enemy_collision(obstacle, old_x, old_y, direction)
                # Check every movement substep: running/jumping can enter and
                # leave the attack range between two rendered frames.
                obstacle.try_hit(self)
                if landed or (self.state != "JUMP" and not self.grounded):
                    self._update_motion(0, controls)
                if body_blocked and self.grounded:
                    # Input still supplies acceleration into the contact each
                    # substep, but a stationary body displays a continuous idle.
                    self.state = "IDLE"
                    duration = FRAME_COUNT / ANIMATIONS["IDLE"][1]
                    self.animation_time = (old_animation_time + step) % duration if old_state == "IDLE" else 0.0
            if self.x in (PLAYER_HALF_WIDTH, WIDTH - PLAYER_HALF_WIDTH):
                self.boundary_speed = boundary_speed
        return attack_started

    def _update_motion(self, dt, controls):
        if controls.jump_requested and (self.grounded or 0 < self.jump_count < MAX_JUMPS):
            self.jump_count = 1 if self.grounded else self.jump_count + 1
            self.vertical_speed = JUMP_SPEED
        controls.jump_requested = False

        air_time = 0.0
        if not self.grounded:
            height = max(0.0, self.foot_y - self.support_y)
            landing_time = (self.vertical_speed + sqrt(self.vertical_speed ** 2 + 2 * GRAVITY * height)) / GRAVITY
            air_time = min(dt, landing_time)
            self.foot_y += self.vertical_speed * dt - 0.5 * GRAVITY * dt * dt
            self.vertical_speed -= GRAVITY * dt
            # Exact integration still leaves subpixel rounding at the landing time.
            if self.foot_y <= self.support_y + 1e-9 and self.vertical_speed <= 0:
                self.foot_y = self.support_y
                self.vertical_speed = 0.0
                self.jump_count = 0

        direction = controls.direction if controls.focused else 0
        if direction:
            self.facing = direction
        travel, blocked = self.move_horizontally(dt, controls, air_time)
        moving = bool(direction) or abs(self.horizontal_speed) > 1e-9
        next_state = "WALK" if moving else "IDLE"
        if (direction and controls.running) or abs(self.horizontal_speed) > WALK_SPEED + 1e-9:
            next_state = "RUN"
        if not self.grounded:
            next_state = "JUMP"
        continuing = next_state == self.state or {next_state, self.state} <= {"WALK", "RUN"}
        if next_state != self.state:
            # Preserve the gait cycle instead of snapping to frame zero when
            # Shift changes the locomotion row during acceleration/braking.
            phase = self.animation_time * ANIMATIONS[self.state][1] / FRAME_COUNT if continuing else 0.0
            self.state = next_state
            self.animation_time = phase * FRAME_COUNT / ANIMATIONS[next_state][1]
        if next_state != "JUMP" and continuing:
            duration = FRAME_COUNT / ANIMATIONS[self.state][1]
            elapsed = dt
            if next_state in {"WALK", "RUN"} and not blocked:
                elapsed = travel / (RUN_ANIMATION_REFERENCE_SPEED if next_state == "RUN" else WALK_SPEED)
            self.animation_time = (self.animation_time + elapsed) % duration
        if next_state == "JUMP":
            # Keep the pose aligned with the physical arc, including long frames.
            self.animation_time = (JUMP_SPEED - self.vertical_speed) / GRAVITY
