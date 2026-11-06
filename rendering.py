"""Rendering helpers; game state remains independent of pico2d."""

from math import ceil, cos, radians, sin, tau

from pico2d import draw_rectangle

from settings import (
    ARROW_SWAY_AMPLITUDE, ARROW_SWAY_PERIOD, ARROW_WIDTH, ARROW_X,
    CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_WIDTH, GROUND_Y,
    HEALTH_BAR_WIDTH, HEIGHT, HUD_MARGIN, ITEM_WIDTHS, PICKUP_HINT_GAP, PICKUP_HINT_SIZE,
    STAGE_ARROWS, WEAPON_ATTACK_ANGLES, WEAPON_HAND_OFFSETS, WIDTH,
)


def draw_background(image):
    scale = max(WIDTH / image.w, HEIGHT / image.h)
    image.draw(WIDTH / 2, HEIGHT / 2, ceil(image.w * scale), ceil(image.h * scale))


def draw_stage_arrows(images, stage_number, elapsed=0.0):
    offset = ARROW_SWAY_AMPLITUDE * sin(tau * elapsed / ARROW_SWAY_PERIOD)
    for direction in STAGE_ARROWS[stage_number]:
        image = images["arrow_right" if direction > 0 else "arrow_left"]
        height = ARROW_WIDTH * image.h / image.w
        image.draw(ARROW_X[direction] + direction * offset,
                   GROUND_Y + height / 2, ARROW_WIDTH, height)


def draw_character(image, player):
    width = FRAME_WIDTH * CHARACTER_SCALE
    height = FRAME_HEIGHT * CHARACTER_SCALE
    center_y = player.foot_y + height / 2 - FRAME_BOTTOM_PADDING * CHARACTER_SCALE
    image.clip_composite_draw(
        player.frame * FRAME_WIDTH, image.h - (player.row + 1) * FRAME_HEIGHT,
        FRAME_WIDTH, FRAME_HEIGHT,
        0, "h" if player.facing < 0 else "", player.x, center_y, width, height,
    )


def draw_health(image, player):
    """Draw the supplied 100% HP artwork; damage and healing are not implemented yet."""
    height = HEALTH_BAR_WIDTH * image.h / image.w
    image.draw(HUD_MARGIN + HEALTH_BAR_WIDTH / 2,
               HEIGHT - HUD_MARGIN - height / 2, HEALTH_BAR_WIDTH, height)


def _draw_item(image, item):
    width = ITEM_WIDTHS[item.kind]
    height = width * image.h / image.w
    image.draw(item.x, item.foot_y + height / 2, width, height)


def draw_items(images, items):
    for item in items:
        if not item.falling:
            _draw_item(images[item.kind], item)


def draw_falling_items(images, items):
    for item in items:
        if item.falling:
            _draw_item(images[item.kind], item)


def draw_pickup_hint(images, items, player):
    index = player.pickup_target(items)
    if index is None:
        return None
    item = items[index]
    image = images[item.kind]
    half = PICKUP_HINT_SIZE / 2
    x = max(half, min(item.x, WIDTH - half))
    top = item.foot_y + ITEM_WIDTHS[item.kind] * image.h / image.w
    y = min(top + PICKUP_HINT_GAP + half, HEIGHT - half)
    # A small pixel-art F avoids an external font dependency.
    for left, bottom, right, upper in ((-4, -6, -2, 6), (-4, 4, 4, 6), (-4, -1, 3, 1)):
        draw_rectangle(x + left, y + bottom, x + right, y + upper,
                       255, 245, 210, filled=True)
    return item


def draw_held_weapon(images, player):
    if player.weapon is None:
        return
    image = images[player.weapon]
    width = ITEM_WIDTHS[player.weapon]
    height = width * image.h / image.w
    hand_x, hand_y = WEAPON_HAND_OFFSETS[player.display_state][player.frame]
    angle = radians(WEAPON_ATTACK_ANGLES[player.frame] if player.attacking else 0)
    # Rotate about the hand's grip, rather than the image center. The pipe's
    # handle is on its right in the source, opposite to the dagger's handle.
    x = player.x + player.facing * (hand_x * CHARACTER_SCALE + cos(angle) * width * 0.3)
    y = player.foot_y + hand_y * CHARACTER_SCALE + sin(angle) * width * 0.3
    half_extent = (abs(cos(angle)) * width + abs(sin(angle)) * height) / 2
    x = max(half_extent, min(WIDTH - half_extent, x))
    flip = (player.facing < 0) != (player.weapon == "steel_pipe")
    image.composite_draw(angle * player.facing, "h" if flip else "", x, y, width, height)
