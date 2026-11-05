from random import Random
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from game import Controls, Item, Player, Stage
from rendering import draw_background, draw_portal
from resources import IMAGE_FILES, ROOT
from settings import (
    CHARACTER_SCALE, FRAME_HEIGHT, FRAME_WIDTH, GROUND_Y, HEIGHT, ITEM_WIDTHS,
    PLAYER_HALF_WIDTH, PORTAL_TRIGGER_HALF_WIDTH, PORTAL_WIDTH, PORTAL_X,
    SECOND_STAGE_SPAWN_X, WIDTH,
)


class StageTests(unittest.TestCase):
    def test_starts_on_first_background_and_only_activates_inside_portal(self):
        for offset, enters in ((-31, False), (-30, True), (0, True), (30, True), (31, False)):
            with self.subTest(offset=offset):
                stage, player = Stage(items=[]), Player(x=PORTAL_X + offset)
                self.assertEqual(stage.background_key, "background")
                self.assertEqual(stage.enter_portal(player, Controls(), Random(1)), enters)
                self.assertEqual(stage.number, 2 if enters else 1)

    def test_airborne_portal_overlap_waits_until_player_lands(self):
        for height, speed in ((GROUND_Y + 1, 0), (GROUND_Y, 1), (GROUND_Y, -1)):
            with self.subTest(height=height, speed=speed):
                stage = Stage(items=[])
                player = Player(x=PORTAL_X, foot_y=height, vertical_speed=speed)
                self.assertFalse(stage.enter_portal(player, Controls()))
                player.update(3, Controls())
                self.assertTrue(stage.enter_portal(player, Controls()))

    def test_transition_preserves_health_and_weapon_but_resets_motion_and_inputs(self):
        stage = Stage(items=[Item("dagger", 300)])
        player = Player(x=PORTAL_X, weapon="steel_pipe", health=2, jump_count=2,
                        state="RUN", facing=-1, animation_time=0.7)
        controls = Controls(held={"right", "lshift", "f", "space"},
                            jump_requested=True, pickup_requested=True)
        self.assertTrue(stage.enter_portal(player, controls, Random(1)))
        self.assertEqual(stage.background_key, "second_background")
        self.assertEqual((player.health, player.weapon), (2, "steel_pipe"))
        self.assertEqual((player.x, player.foot_y, player.vertical_speed, player.jump_count),
                         (SECOND_STAGE_SPAWN_X, GROUND_Y, 0, 0))
        self.assertEqual((player.state, player.facing, player.animation_time), ("IDLE", 1, 0))
        self.assertEqual(controls.held, set())
        self.assertFalse(controls.pickup_requested or controls.jump_requested)

    def test_second_stage_spawns_new_three_to_five_items_with_clear_entry(self):
        layouts, counts = set(), set()
        for seed in range(200):
            with self.subTest(seed=seed):
                old_items = [Item("steel_pipe", 1000)]
                stage = Stage(items=old_items)
                self.assertTrue(stage.enter_portal(Player(x=PORTAL_X), Controls(), Random(seed)))
                self.assertIsNot(stage.items, old_items)
                self.assertEqual(old_items, [Item("steel_pipe", 1000)])
                self.assertIn(len(stage.items), (3, 4, 5))
                self.assertEqual({item.kind for item in stage.items}, set(ITEM_WIDTHS))
                for item in stage.items:
                    self.assertEqual(item.foot_y, GROUND_Y)
                    half = ITEM_WIDTHS[item.kind] / 2
                    self.assertGreaterEqual(item.x - half, 0)
                    self.assertLessEqual(item.x + half, WIDTH)
                    self.assertGreater(abs(item.x - SECOND_STAGE_SPAWN_X), PLAYER_HALF_WIDTH + half)
                ordered = sorted(stage.items, key=lambda item: item.x)
                for left, right in zip(ordered, ordered[1:]):
                    self.assertGreater(right.x - left.x,
                                       (ITEM_WIDTHS[left.kind] + ITEM_WIDTHS[right.kind]) / 2)
                layouts.add(tuple(stage.items))
                counts.add(len(stage.items))
        self.assertEqual(counts, {3, 4, 5})
        self.assertGreater(len(layouts), 1)

    def test_second_stage_does_not_reenter_or_respawn_at_either_edge(self):
        stage, player, controls = Stage(items=[]), Player(x=PORTAL_X), Controls()
        with patch("game.spawn_items", return_value=[Item("dagger", 500)]) as spawn:
            self.assertTrue(stage.enter_portal(player, controls))
            original = stage.items[:]
            for x in (PLAYER_HALF_WIDTH, PORTAL_X, WIDTH - PLAYER_HALF_WIDTH):
                player.x = x
                self.assertFalse(stage.enter_portal(player, controls))
                self.assertEqual(stage.items, original)
            spawn.assert_called_once()

    def test_second_stage_items_can_be_picked_up_and_dropped(self):
        stage, player, controls = Stage(items=[]), Player(x=PORTAL_X), Controls()
        stage.enter_portal(player, controls, Random(1))
        original_count = len(stage.items)
        item = stage.items[0]
        player.x = item.x
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(stage.items, controls))
        self.assertEqual(player.weapon, item.kind)
        self.assertEqual(len(stage.items), original_count - 1)
        player.x = SECOND_STAGE_SPAWN_X
        controls.set_key("f", False)
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(stage.items, controls))
        self.assertIsNone(player.weapon)
        self.assertEqual(len(stage.items), original_count)

    def test_portal_size_matches_character_and_fits_right_sidewalk(self):
        with Image.open(ROOT / IMAGE_FILES["portal"]) as source:
            self.assertEqual(source.size, (512, 272))
            image = Mock(w=source.width, h=source.height)
        draw_portal(image, 1)
        x, y, width, height = image.draw.call_args.args
        self.assertEqual((x, width), (PORTAL_X, PORTAL_WIDTH))
        self.assertAlmostEqual(height, 76.5)
        self.assertAlmostEqual(width / height, image.w / image.h)
        self.assertEqual(y - height / 2, GROUND_Y)
        self.assertEqual(x + width / 2, WIDTH - 16)
        self.assertGreaterEqual(x - width / 2, 0)
        self.assertLessEqual(y + height / 2, HEIGHT)
        self.assertLessEqual(PORTAL_X - PORTAL_TRIGGER_HALF_WIDTH, WIDTH - PLAYER_HALF_WIDTH)
        with Image.open(ROOT / "assets/character.png") as source:
            bounds = source.crop((0, 0, FRAME_WIDTH, FRAME_HEIGHT)).getbbox()
        self.assertGreater(width, (bounds[2] - bounds[0]) * CHARACTER_SCALE)
        self.assertLess(height, (bounds[3] - bounds[1]) * CHARACTER_SCALE)
        image.reset_mock()
        draw_portal(image, 2)
        image.draw.assert_not_called()

    def test_second_background_uses_same_canvas_scale_and_sidewalk(self):
        with Image.open(ROOT / IMAGE_FILES["second_background"]) as source:
            self.assertEqual(source.size, (1672, 941))
            image = Mock(w=source.width, h=source.height)
        draw_background(image)
        x, y, width, height = image.draw.call_args.args
        self.assertEqual((x, y), (WIDTH / 2, HEIGHT / 2))
        self.assertGreaterEqual(width, WIDTH)
        self.assertGreaterEqual(height, HEIGHT)
        self.assertEqual(Player().foot_y, GROUND_Y)
