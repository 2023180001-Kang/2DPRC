import unittest
from unittest.mock import Mock

from PIL import Image

from game import Player
from rendering import draw_health
from resources import ROOT
from settings import HEART_GAP, HEART_SIZE, HEIGHT, HUD_MARGIN, MAX_HEALTH, WIDTH


class HealthTests(unittest.TestCase):
    def test_initial_health_draws_three_red_hearts(self):
        player = Player()
        self.assertEqual(player.health, 3)
        with Image.open(ROOT / "Heart.png") as source:
            image = Mock(w=source.width, h=source.height)
            self.assertEqual(source.convert("RGBA").getchannel("A").getextrema()[0], 0)
        draw_health(image, player)
        self.assertEqual(image.clip_draw.call_count, 3)
        for draw in image.clip_draw.call_args_list:
            self.assertEqual(draw.args[:4], (0, 0, image.w // 2, image.h))

    def test_top_right_positions_have_fixed_margin_and_spacing(self):
        image = Mock(w=1784, h=888)
        draw_health(image, Player())
        positions = [draw.args[4:6] for draw in image.clip_draw.call_args_list]
        self.assertEqual(positions[0], (WIDTH - HUD_MARGIN - HEART_SIZE / 2,
                                       HEIGHT - HUD_MARGIN - HEART_SIZE / 2))
        for index, (x, y) in enumerate(positions):
            self.assertEqual(x, positions[0][0] - index * (HEART_SIZE + HEART_GAP))
            self.assertEqual(y, positions[0][1])
            self.assertGreaterEqual(x - HEART_SIZE / 2, 0)
            self.assertLessEqual(x + HEART_SIZE / 2, WIDTH)
            self.assertGreaterEqual(y - HEART_SIZE / 2, 0)
            self.assertLessEqual(y + HEART_SIZE / 2, HEIGHT)

    def test_health_count_is_clamped_to_three(self):
        for health in (-1, 0, 1, 2, 3, 10):
            with self.subTest(health=health):
                image = Mock(w=1784, h=888)
                draw_health(image, Player(health=health))
                self.assertEqual(image.clip_draw.call_count, max(0, min(health, MAX_HEALTH)))

    def test_position_does_not_follow_player_or_jump(self):
        image = Mock(w=1784, h=888)
        draw_health(image, Player())
        expected = image.clip_draw.call_args_list[:]
        image.reset_mock()
        draw_health(image, Player(x=100, foot_y=400, state="JUMP"))
        self.assertEqual(image.clip_draw.call_args_list, expected)
