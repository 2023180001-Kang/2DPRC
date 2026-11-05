import unittest
from unittest.mock import Mock

from PIL import Image

from game import Player
from rendering import draw_health
from resources import IMAGE_FILES, ROOT
from settings import HEALTH_BAR_WIDTH, HEIGHT, HUD_MARGIN, WIDTH


class HealthTests(unittest.TestCase):
    def setUp(self):
        with Image.open(ROOT / IMAGE_FILES["health_bar"]) as source:
            self.image = Mock(w=source.width, h=source.height)

    def test_initial_health_draws_one_full_hp_bar_without_hearts(self):
        player = Player()
        self.assertEqual(player.health, 3)
        self.assertEqual(IMAGE_FILES["health_bar"], "hp_preview_100.png")
        self.assertNotIn("Heart.png", IMAGE_FILES.values())
        draw_health(self.image, player)
        self.image.draw.assert_called_once()
        self.image.clip_draw.assert_not_called()

    def test_top_right_position_has_fixed_margin_and_stays_on_screen(self):
        draw_health(self.image, Player())
        x, y, width, height = self.image.draw.call_args.args
        self.assertEqual(x + width / 2, WIDTH - HUD_MARGIN)
        self.assertEqual(y + height / 2, HEIGHT - HUD_MARGIN)
        self.assertGreaterEqual(x - width / 2, 0)
        self.assertGreaterEqual(y - height / 2, 0)

    def test_bar_preserves_source_aspect_ratio(self):
        draw_health(self.image, Player())
        _, _, width, height = self.image.draw.call_args.args
        self.assertEqual(width, HEALTH_BAR_WIDTH)
        self.assertAlmostEqual(width / height, self.image.w / self.image.h)

    def test_position_does_not_follow_player_or_jump(self):
        draw_health(self.image, Player())
        expected = self.image.draw.call_args
        self.image.reset_mock()
        draw_health(self.image, Player(x=100, foot_y=400, state="JUMP"))
        self.assertEqual(self.image.draw.call_args, expected)
