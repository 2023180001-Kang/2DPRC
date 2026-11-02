"""Rendering helpers; game state remains independent of pico2d."""

from settings import HEIGHT, WIDTH


def draw_background(image):
    scale = min(WIDTH / image.w, HEIGHT / image.h)
    image.draw(WIDTH / 2, HEIGHT / 2, image.w * scale, image.h * scale)
