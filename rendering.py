"""Rendering helpers; game state remains independent of pico2d."""

from settings import CHARACTER_SCALE, FRAME_HEIGHT, FRAME_WIDTH, GROUND_Y, HEIGHT, WIDTH


def draw_background(image):
    scale = min(WIDTH / image.w, HEIGHT / image.h)
    image.draw(WIDTH / 2, HEIGHT / 2, image.w * scale, image.h * scale)


def draw_character(image):
    width = FRAME_WIDTH * CHARACTER_SCALE
    height = FRAME_HEIGHT * CHARACTER_SCALE
    image.clip_composite_draw(
        0, image.h - FRAME_HEIGHT, FRAME_WIDTH, FRAME_HEIGHT,
        0, "", WIDTH / 2, GROUND_Y + height / 2, width, height,
    )
