import unittest
from unittest.mock import Mock

from PIL import Image

from game import Player
from rendering import draw_background, draw_character
from resources import IMAGE_FILES, ROOT
from settings import (
    ANIMATIONS, CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_ROWS,
    FRAME_WIDTH, HEIGHT, WIDTH,
)


class RenderingTests(unittest.TestCase):
    def test_new_stage_fills_720p_canvas_and_sets_sidewalk_height(self):
        self.assertEqual((WIDTH, HEIGHT), (1280, 720))
        with Image.open(ROOT / IMAGE_FILES["background"]) as background:
            image = Mock(w=background.width, h=background.height)
        draw_background(image)
        x, y, width, height = image.draw.call_args.args
        self.assertEqual((x, y), (640, 360))
        self.assertAlmostEqual(width, WIDTH, delta=1)
        self.assertAlmostEqual(height, HEIGHT, delta=1)
        self.assertEqual(Player().foot_y, 140)

    def test_background_covers_canvas_preserving_aspect_ratio(self):
        image = Mock(w=2048, h=683)
        draw_background(image)
        x, y, width, height = image.draw.call_args.args
        self.assertEqual((x, y), (WIDTH / 2, HEIGHT / 2))
        self.assertAlmostEqual(width / image.w, height / image.h,
                               delta=1 / min(image.w, image.h))
        self.assertGreaterEqual(width, WIDTH)
        self.assertGreaterEqual(height, HEIGHT)

    def test_all_frames_clip_inside_sheet(self):
        image = Mock(h=FRAME_HEIGHT * FRAME_ROWS)
        for state, (row, fps) in ANIMATIONS.items():
            for frame in range(8):
                player = Player(state=state)
                player.animation_time = frame / fps
                draw_character(image, player)
                args = image.clip_composite_draw.call_args.args
                self.assertEqual(args[:4], (frame * FRAME_WIDTH, (FRAME_ROWS - 1 - row) * FRAME_HEIGHT,
                                            FRAME_WIDTH, FRAME_HEIGHT))

    def test_clip_draw_has_explicit_destination_size(self):
        image = Mock(h=FRAME_HEIGHT * FRAME_ROWS)
        draw_character(image, Player())
        self.assertEqual(image.clip_composite_draw.call_args.args[8:],
                         (FRAME_WIDTH * CHARACTER_SCALE, FRAME_HEIGHT * CHARACTER_SCALE))

    def test_facing_controls_horizontal_flip(self):
        image = Mock(h=FRAME_HEIGHT * FRAME_ROWS)
        for facing, flip in ((1, ""), (-1, "h")):
            draw_character(image, Player(facing=facing))
            self.assertEqual(image.clip_composite_draw.call_args.args[5], flip)

    def test_foot_anchor_matches_frame_padding(self):
        image = Mock(h=FRAME_HEIGHT * FRAME_ROWS)
        player = Player()
        draw_character(image, player)
        center_y = image.clip_composite_draw.call_args.args[7]
        drawn_bottom = center_y - FRAME_HEIGHT * CHARACTER_SCALE / 2
        self.assertAlmostEqual(drawn_bottom + FRAME_BOTTOM_PADDING * CHARACTER_SCALE,
                               player.foot_y)
