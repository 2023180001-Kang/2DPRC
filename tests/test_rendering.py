import unittest
from unittest.mock import Mock

from game import Player
from rendering import draw_background, draw_character
from settings import CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, FRAME_WIDTH, HEIGHT, WIDTH


class RenderingTests(unittest.TestCase):
    def test_background_preserves_aspect_ratio(self):
        image = Mock(w=2048, h=683)
        draw_background(image)
        x, y, width, height = image.draw.call_args.args
        self.assertEqual((x, y), (WIDTH / 2, HEIGHT / 2))
        self.assertAlmostEqual(width / height, image.w / image.h)
        self.assertLessEqual(width, WIDTH)
        self.assertLessEqual(height, HEIGHT)

    def test_all_frames_clip_inside_sheet(self):
        image = Mock(h=FRAME_HEIGHT * 3)
        for state, row in (("IDLE", 0), ("WALK", 1), ("RUN", 2)):
            for frame in range(8):
                player = Player(state=state)
                fps = {"IDLE": 6, "WALK": 8, "RUN": 12}[state]
                player.animation_time = frame / fps
                draw_character(image, player)
                args = image.clip_composite_draw.call_args.args
                self.assertEqual(args[:4], (frame * FRAME_WIDTH, (2 - row) * FRAME_HEIGHT,
                                            FRAME_WIDTH, FRAME_HEIGHT))

    def test_clip_draw_has_explicit_destination_size(self):
        image = Mock(h=768)
        draw_character(image, Player())
        self.assertEqual(image.clip_composite_draw.call_args.args[8:],
                         (FRAME_WIDTH * CHARACTER_SCALE, FRAME_HEIGHT * CHARACTER_SCALE))

    def test_facing_controls_horizontal_flip(self):
        image = Mock(h=768)
        for facing, flip in ((1, ""), (-1, "h")):
            draw_character(image, Player(facing=facing))
            self.assertEqual(image.clip_composite_draw.call_args.args[5], flip)

    def test_foot_anchor_matches_frame_padding(self):
        image = Mock(h=768)
        player = Player()
        draw_character(image, player)
        center_y = image.clip_composite_draw.call_args.args[7]
        drawn_bottom = center_y - FRAME_HEIGHT * CHARACTER_SCALE / 2
        self.assertAlmostEqual(drawn_bottom + FRAME_BOTTOM_PADDING * CHARACTER_SCALE,
                               player.foot_y)
