"""Rendering helpers; game state remains independent of pico2d."""

from math import ceil

from pico2d import draw_rectangle

from settings import (
    CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_WIDTH,
    GROUND_Y, HEALTH_BAR_WIDTH, HEIGHT, HUD_MARGIN, ITEM_WIDTHS, PICKUP_HINT_GAP, PICKUP_HINT_SIZE,
    PORTAL_WIDTH, PORTAL_X, WEAPON_HAND_OFFSETS, WIDTH,
)


def draw_background(image):
    scale = max(WIDTH / image.w, HEIGHT / image.h)
    image.draw(WIDTH / 2, HEIGHT / 2, ceil(image.w * scale), ceil(image.h * scale))


def draw_portal(image, stage_number):
    if stage_number != 1:
        return
    height = PORTAL_WIDTH * image.h / image.w
    image.draw(PORTAL_X, GROUND_Y + height / 2, PORTAL_WIDTH, height)


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
    image.draw(WIDTH - HUD_MARGIN - HEALTH_BAR_WIDTH / 2,
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
    hand_x, hand_y = WEAPON_HAND_OFFSETS[player.state][player.frame]
    # Place the grip at 20% of the source width on the hand, mirrored with the body.
    x = player.x + player.facing * (hand_x * CHARACTER_SCALE + width * 0.3)
    y = player.foot_y + hand_y * CHARACTER_SCALE
    image.composite_draw(0, "h" if player.facing < 0 else "", x, y, width, height)
