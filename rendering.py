"""Rendering helpers; game state remains independent of pico2d."""

from math import ceil

from settings import (
    CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_WIDTH,
    HEART_GAP, HEART_SIZE, HEIGHT, HUD_MARGIN, ITEM_WIDTHS, MAX_HEALTH, WEAPON_HAND_OFFSETS, WIDTH,
)


def draw_background(image):
    scale = max(WIDTH / image.w, HEIGHT / image.h)
    image.draw(WIDTH / 2, HEIGHT / 2, ceil(image.w * scale), ceil(image.h * scale))


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
    health = max(0, min(player.health, MAX_HEALTH))
    for index in range(health):
        x = WIDTH - HUD_MARGIN - HEART_SIZE / 2 - index * (HEART_SIZE + HEART_GAP)
        y = HEIGHT - HUD_MARGIN - HEART_SIZE / 2
        image.clip_draw(0, 0, image.w // 2, image.h, x, y, HEART_SIZE, HEART_SIZE)


def draw_items(images, items):
    for item in items:
        image = images[item.kind]
        width = ITEM_WIDTHS[item.kind]
        height = width * image.h / image.w
        image.draw(item.x, item.foot_y + height / 2, width, height)


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
