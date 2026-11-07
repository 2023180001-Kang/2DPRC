import unittest
from unittest.mock import Mock, patch

from PIL import Image

from game import Player
from rendering import draw_health
from resources import IMAGE_FILES, ROOT
from settings import HEALTH_BAR_WIDTH, HEALTH_FILL_BOUNDS, HEIGHT, HUD_MARGIN, WIDTH


class HealthTests(unittest.TestCase):
    def setUp(self):
        with Image.open(ROOT / IMAGE_FILES["health_bar"]) as source:
            self.image = Mock(w=source.width, h=source.height)

    def test_initial_health_draws_one_full_hp_bar_without_hearts(self):
        player = Player()
        self.assertEqual(player.health, 100)
        self.assertEqual(IMAGE_FILES["health_bar"], "HoodMan_HP바_투명배경_pico2d.png")
        self.assertNotIn("hp_preview_100.png", IMAGE_FILES.values())
        self.assertNotIn("Heart.png", IMAGE_FILES.values())
        draw_health(self.image, player)
        self.image.draw.assert_called_once()
        self.image.clip_draw.assert_not_called()

    def test_top_left_position_has_fixed_margin_and_stays_on_screen(self):
        draw_health(self.image, Player())
        x, y, width, height = self.image.draw.call_args.args
        self.assertEqual(x - width / 2, HUD_MARGIN)
        self.assertEqual(y + height / 2, HEIGHT - HUD_MARGIN)
        self.assertGreaterEqual(x - width / 2, 0)
        self.assertLessEqual(x + width / 2, WIDTH)
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

    def test_depleted_gauge_matches_health_and_preserves_portrait_and_border(self):
        for health in (100, 90, 70, 50, 10, 0):
            with self.subTest(health=health), patch("rendering.draw_rectangle") as rectangle:
                self.image.reset_mock()
                draw_health(self.image, Player(health=health))
                self.image.draw.assert_called_once()
                if health == 100:
                    rectangle.assert_not_called()
                    continue
                left, top, right, bottom = HEALTH_FILL_BOUNDS
                scale = HEALTH_BAR_WIDTH / self.image.w
                x1, y1, x2, y2, *color = rectangle.call_args.args
                self.assertAlmostEqual(x1, HUD_MARGIN + (left + (right - left) * health / 100) * scale)
                self.assertAlmostEqual(x2, HUD_MARGIN + right * scale)
                self.assertAlmostEqual(y1, HEIGHT - HUD_MARGIN - bottom * scale)
                self.assertAlmostEqual(y2, HEIGHT - HUD_MARGIN - top * scale)
                self.assertEqual(color, [3, 7, 15])
                self.assertEqual(rectangle.call_args.kwargs, {"filled": True})
                self.assertGreaterEqual(x1, HUD_MARGIN + left * scale)

    def test_out_of_range_health_is_clamped_for_drawing(self):
        with patch("rendering.draw_rectangle") as rectangle:
            draw_health(self.image, Player(health=-1))
            empty = rectangle.call_args
            draw_health(self.image, Player(health=0))
            self.assertEqual(rectangle.call_args, empty)
            rectangle.reset_mock()
            draw_health(self.image, Player(health=110))
            rectangle.assert_not_called()
