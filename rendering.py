"""Rendering helpers; game state remains independent of pico2d."""

from settings import CHARACTER_SCALE, FRAME_HEIGHT, FRAME_WIDTH, GROUND_Y, HEIGHT, WIDTH


def draw_background(image):
    scale = min(WIDTH / image.w, HEIGHT / image.h)
    image.draw(WIDTH / 2, HEIGHT / 2, image.w * scale, image.h * scale)


def draw_character(image, player):
    width = FRAME_WIDTH * CHARACTER_SCALE
    height = FRAME_HEIGHT * CHARACTER_SCALE
    image.clip_composite_draw(
        player.frame * FRAME_WIDTH, image.h - FRAME_HEIGHT, FRAME_WIDTH, FRAME_HEIGHT,
        0, "h" if player.facing < 0 else "", player.x, player.foot_y + height / 2, width, height,
    )
