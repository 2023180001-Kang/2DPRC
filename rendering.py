"""Rendering helpers; game state remains independent of pico2d."""

from math import ceil, cos, radians, sin, tau

from pico2d import draw_rectangle

from settings import (
    ARROW_SWAY_AMPLITUDE, ARROW_SWAY_PERIOD, ARROW_WIDTH, ARROW_X,
    CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_WIDTH, STAGE_GROUND_Y,
    HEALTH_BAR_WIDTH, HEIGHT, HUD_MARGIN, ITEM_WIDTHS, PICKUP_HINT_GAP, PICKUP_HINT_SIZE,
    STAGE_ARROWS, WEAPON_ATTACK_ANGLES, WEAPON_CARRY_ANGLE, WEAPON_GRIPS, WEAPON_HAND_OFFSETS, WIDTH,
    ENEMY_SCALE, HEALTH_FILL_BOUNDS, MAX_HEALTH,
    CAMERA_SHAKE_DURATION, CAMERA_SHAKE_AMPLITUDE,
    HEALTH_SHAKE_DURATION, HEALTH_SHAKE_AMPLITUDE, HIT_SHAKE_FREQUENCY,
)


def _hit_shake_offset(player, duration, amplitude):
    if player.hit_feedback_time <= 1e-9:
        return (0.0, 0.0)
    elapsed = max(CAMERA_SHAKE_DURATION, HEALTH_SHAKE_DURATION) - player.hit_feedback_time
    if elapsed >= duration - 1e-9:
        return (0.0, 0.0)
    strength = amplitude * (1 - elapsed / duration) ** 2
    phase = tau * HIT_SHAKE_FREQUENCY * elapsed
    return (strength * cos(phase), strength * 0.6 * sin(phase * 1.3))


def camera_offset(player):
    """Render-only translation: never move hitboxes, items or exit triggers."""
    return _hit_shake_offset(player, CAMERA_SHAKE_DURATION, CAMERA_SHAKE_AMPLITUDE)


def draw_background(image, *, offset=(0.0, 0.0)):
    scale = max(WIDTH / image.w, HEIGHT / image.h)
    # Overscan during shake prevents exposed canvas edges, preserving aspect ratio.
    if offset != (0.0, 0.0):
        scale = max(scale, (WIDTH + 2 * abs(offset[0])) / image.w,
                    (HEIGHT + 2 * abs(offset[1])) / image.h)
    image.draw(WIDTH / 2 + offset[0], HEIGHT / 2 + offset[1],
               ceil(image.w * scale), ceil(image.h * scale))


def draw_stage_arrows(images, stage_number, elapsed=0.0, *, directions=None, offset=(0.0, 0.0)):
    sway = ARROW_SWAY_AMPLITUDE * sin(tau * elapsed / ARROW_SWAY_PERIOD)
    for direction in STAGE_ARROWS[stage_number] if directions is None else directions:
        image = images["arrow_right" if direction > 0 else "arrow_left"]
        height = ARROW_WIDTH * image.h / image.w
        image.draw(ARROW_X[direction] + direction * sway + offset[0],
                   STAGE_GROUND_Y[stage_number] + height / 2 + offset[1], ARROW_WIDTH, height)


def draw_character(image, player, *, offset=(0.0, 0.0)):
    width = FRAME_WIDTH * CHARACTER_SCALE
    height = FRAME_HEIGHT * CHARACTER_SCALE
    center_y = player.foot_y + height / 2 - FRAME_BOTTOM_PADDING * CHARACTER_SCALE
    image.clip_composite_draw(
        player.frame * FRAME_WIDTH, image.h - (player.row + 1) * FRAME_HEIGHT,
        FRAME_WIDTH, FRAME_HEIGHT,
        0, "h" if player.facing < 0 else "", player.x + offset[0], center_y + offset[1], width, height,
    )


def draw_enemy(image, enemy, *, offset=(0.0, 0.0)):
    width, height = FRAME_WIDTH * ENEMY_SCALE, FRAME_HEIGHT * ENEMY_SCALE
    image.clip_composite_draw(
        enemy.frame * FRAME_WIDTH, image.h - (enemy.row + 1) * FRAME_HEIGHT,
        FRAME_WIDTH, FRAME_HEIGHT, 0, "h" if enemy.facing < 0 else "",
        enemy.x + offset[0], enemy.foot_y + height / 2 - FRAME_BOTTOM_PADDING * ENEMY_SCALE + offset[1], width, height,
    )


def draw_health(image, player):
    """Keep the portrait/frame and empty the blue gauge from right to left."""
    dx, dy = _hit_shake_offset(player, HEALTH_SHAKE_DURATION, HEALTH_SHAKE_AMPLITUDE)
    height = HEALTH_BAR_WIDTH * image.h / image.w
    image.draw(HUD_MARGIN + HEALTH_BAR_WIDTH / 2 + dx,
               HEIGHT - HUD_MARGIN - height / 2 + dy, HEALTH_BAR_WIDTH, height)
    ratio = max(0.0, min(1.0, player.health / MAX_HEALTH))
    if ratio < 1.0:
        left, top, right, bottom = HEALTH_FILL_BOUNDS
        scale = HEALTH_BAR_WIDTH / image.w
        draw_rectangle(HUD_MARGIN + (left + (right - left) * ratio) * scale + dx,
                       HEIGHT - HUD_MARGIN - bottom * scale + dy,
                       HUD_MARGIN + right * scale + dx, HEIGHT - HUD_MARGIN - top * scale + dy,
                       3, 7, 15, filled=True)


def _draw_item(image, item, offset):
    width = ITEM_WIDTHS[item.kind]
    height = width * image.h / image.w
    image.draw(item.x + offset[0], item.foot_y + height / 2 + offset[1], width, height)


def draw_items(images, items, *, offset=(0.0, 0.0)):
    for item in items:
        if not item.falling:
            _draw_item(images[item.kind], item, offset)


def draw_falling_items(images, items, *, offset=(0.0, 0.0)):
    for item in items:
        if item.falling:
            _draw_item(images[item.kind], item, offset)


def draw_pickup_hint(images, items, player, *, offset=(0.0, 0.0)):
    index = player.pickup_target(items)
    if index is None:
        return None
    item = items[index]
    image = images[item.kind]
    half = PICKUP_HINT_SIZE / 2
    x = max(half, min(item.x, WIDTH - half)) + offset[0]
    top = item.foot_y + ITEM_WIDTHS[item.kind] * image.h / image.w
    y = min(top + PICKUP_HINT_GAP + half, HEIGHT - half) + offset[1]
    # A small pixel-art F avoids an external font dependency.
    for left, bottom, right, upper in ((-4, -6, -2, 6), (-4, 4, 4, 6), (-4, -1, 3, 1)):
        draw_rectangle(x + left, y + bottom, x + right, y + upper,
                       255, 245, 210, filled=True)
    return item


def draw_held_weapon(images, player, *, offset=(0.0, 0.0)):
    if player.weapon is None or player.incapacitated:
        return
    image = images[player.weapon]
    width = ITEM_WIDTHS[player.weapon]
    height = width * image.h / image.w
    hand_x, hand_y = WEAPON_HAND_OFFSETS[player.display_state][player.frame]
    angle = radians(WEAPON_ATTACK_ANGLES[player.frame] if player.attacking else WEAPON_CARRY_ANGLE)
    grip_x, grip_y = WEAPON_GRIPS[player.weapon]
    if player.weapon == "steel_pipe":
        grip_x = 1 - grip_x
    # Rotate the center around the actual handle point, keeping the grip in
    # the right fist even when the art's handle is off-center vertically.
    dx, dy = (0.5 - grip_x) * width, (0.5 - grip_y) * height
    x = player.x + player.facing * (hand_x * CHARACTER_SCALE + cos(angle) * dx - sin(angle) * dy)
    y = player.foot_y + hand_y * CHARACTER_SCALE + sin(angle) * dx + cos(angle) * dy
    half_extent = (abs(cos(angle)) * width + abs(sin(angle)) * height) / 2
    x = max(half_extent, min(WIDTH - half_extent, x))
    flip = (player.facing < 0) != (player.weapon == "steel_pipe")
    image.composite_draw(angle * player.facing, "h" if flip else "", x + offset[0], y + offset[1], width, height)
    # The opaque fist and finger outline fully hide the grip underneath the
    # hand while leaving the exposed weapon in front of the body.
    draw_character(images["right_hand"], player, offset=offset)
