"""Rendering helpers; game state remains independent of pico2d."""

from math import ceil

from settings import (
    CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_WIDTH,
    HEART_GAP, HEART_SIZE, HEIGHT, HUD_MARGIN, MAX_HEALTH, WIDTH,
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
