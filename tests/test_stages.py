from random import Random
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from game import Controls, Item, Player, Stage
from rendering import draw_background, draw_stage_arrows
from resources import IMAGE_FILES, ROOT
from settings import (
    ARROW_SPAWN_PADDING, ARROW_TRIGGER_HALF_WIDTH, ARROW_WIDTH, ARROW_X, GROUND_Y,
    HEIGHT, ITEM_WIDTHS, PLAYER_HALF_WIDTH, STAGE_ARROWS, STAGE_ENTRY_LEFT_X, STAGE_ENTRY_RIGHT_X, WIDTH,
)


class StageTests(unittest.TestCase):
    def test_starts_on_first_background_and_only_activates_inside_right_arrow(self):
        for offset, enters in ((-31, False), (-30, True), (0, True), (30, True), (31, False)):
            with self.subTest(offset=offset):
                stage, player = Stage(items=[]), Player(x=ARROW_X[1] + offset)
                self.assertEqual(stage.background_key, "background")
                self.assertEqual(stage.try_transition(player, Controls(), Random(1)), enters)
                self.assertEqual(stage.number, 2 if enters else 1)

    def test_airborne_arrow_overlap_waits_until_player_lands(self):
        for number, direction in ((1, 1), (2, -1)):
            for height, speed in ((GROUND_Y + 1, 0), (GROUND_Y, 1), (GROUND_Y, -1)):
                with self.subTest(stage=number, height=height, speed=speed):
                    stage = Stage(items=[], number=number)
                    player = Player(x=ARROW_X[direction], foot_y=height, vertical_speed=speed)
                    self.assertFalse(stage.try_transition(player, Controls()))
                    player.update(3, Controls())
                    self.assertTrue(stage.try_transition(player, Controls()))

    def test_second_stage_left_arrow_return_includes_range_boundary(self):
        for offset, returns in ((-31, False), (-30, True), (0, True), (30, True), (31, False)):
            with self.subTest(offset=offset):
                stage = Stage(items=[], number=2)
                player = Player(x=ARROW_X[-1] + offset)
                self.assertEqual(stage.try_transition(player, Controls(), Random(1)), returns)
                self.assertEqual(stage.number, 1 if returns else 2)

    def test_transition_preserves_health_and_weapon_but_resets_motion_and_inputs(self):
        stage = Stage(items=[Item("dagger", 300)])
        player = Player(x=ARROW_X[1], weapon="steel_pipe", health=2, jump_count=2,
                        state="RUN", facing=-1, animation_time=0.7)
        controls = Controls(held={"right", "lshift", "f", "space"},
                            jump_requested=True, pickup_requested=True)
        self.assertTrue(stage.try_transition(player, controls, Random(1)))
        self.assertEqual(stage.background_key, "second_background")
        self.assertEqual((player.health, player.weapon), (2, "steel_pipe"))
        self.assertEqual((player.x, player.foot_y, player.vertical_speed, player.jump_count),
                         (STAGE_ENTRY_LEFT_X, GROUND_Y, 0, 0))
        self.assertEqual((player.state, player.facing, player.animation_time), ("IDLE", 1, 0))
        self.assertEqual(controls.held, set())
        self.assertFalse(controls.pickup_requested or controls.jump_requested)

    def test_second_stage_spawns_new_three_to_five_items_with_clear_entry(self):
        layouts, counts = set(), set()
        for seed in range(200):
            with self.subTest(seed=seed):
                old_items = [Item("steel_pipe", 1000)]
                stage = Stage(items=old_items)
                self.assertTrue(stage.try_transition(Player(x=ARROW_X[1]), Controls(), Random(seed)))
                self.assertIsNot(stage.items, old_items)
                self.assertEqual(old_items, [Item("steel_pipe", 1000)])
                self.assertIn(len(stage.items), (3, 4, 5))
                self.assertEqual({item.kind for item in stage.items}, set(ITEM_WIDTHS))
                for item in stage.items:
                    self.assertEqual(item.foot_y, GROUND_Y)
                    half = ITEM_WIDTHS[item.kind] / 2
                    self.assertGreaterEqual(item.x - half, 0)
                    self.assertLessEqual(item.x + half, WIDTH)
                    self.assertGreater(abs(item.x - STAGE_ENTRY_LEFT_X), PLAYER_HALF_WIDTH + half)
                    for direction in STAGE_ARROWS[2]:
                        self.assertGreater(abs(item.x - ARROW_X[direction]),
                                           ARROW_WIDTH / 2 + ARROW_SPAWN_PADDING + half)
                ordered = sorted(stage.items, key=lambda item: item.x)
                for left, right in zip(ordered, ordered[1:]):
                    self.assertGreater(right.x - left.x,
                                       (ITEM_WIDTHS[left.kind] + ITEM_WIDTHS[right.kind]) / 2)
                layouts.add(tuple(stage.items))
                counts.add(len(stage.items))
        self.assertEqual(counts, {3, 4, 5})
        self.assertGreater(len(layouts), 1)

    def test_second_stage_right_arrow_is_displayed_but_does_nothing(self):
        items = [Item("dagger", 500)]
        stage = Stage(items=items, number=2)
        player = Player(x=WIDTH - PLAYER_HALF_WIDTH, weapon="steel_pipe", health=2,
                        state="RUN", animation_time=0.7)
        controls = Controls(held={"right", "lshift"}, pickup_requested=True)
        original_player = vars(player).copy()
        original_controls = vars(controls).copy()
        with patch("game.spawn_items") as spawn:
            for _ in range(10):
                self.assertFalse(stage.try_transition(player, controls))
            spawn.assert_not_called()
        self.assertEqual(stage.number, 2)
        self.assertIs(stage.items, items)
        self.assertEqual(vars(player), original_player)
        self.assertEqual(vars(controls), original_controls)

    def test_first_stage_left_edge_has_no_exit(self):
        stage = Stage(items=[])
        self.assertFalse(stage.try_transition(Player(x=ARROW_X[-1]), Controls()))
        self.assertEqual(stage.number, 1)

    def test_return_and_revisit_preserve_pickups_drops_and_spawn_once(self):
        player, controls = Player(weapon="steel_pipe", health=2), Controls()
        first_items = [Item("dagger", 400)]
        second_items = [Item("dagger", 500), Item("steel_pipe", 700), Item("dagger", 900)]
        stage = Stage(items=first_items)
        player.x = ARROW_X[1]
        with patch("game.spawn_items", return_value=second_items) as spawn:
            self.assertTrue(stage.try_transition(player, controls))
            player.x = 500
            self.assertTrue(player.pick_up(stage.items, Controls(pickup_requested=True)))
            second_snapshot = stage.items[:]
            player.x = ARROW_X[-1]
            self.assertTrue(stage.try_transition(player, controls))
            self.assertEqual((stage.number, stage.background_key), (1, "background"))
            self.assertEqual((player.x, player.facing), (STAGE_ENTRY_RIGHT_X, -1))
            self.assertIs(stage.items, first_items)
            self.assertEqual((player.weapon, player.health), ("dagger", 2))
            self.assertFalse(stage.try_transition(player, controls))
            player.x = ARROW_X[1]
            self.assertTrue(stage.try_transition(player, controls))
            self.assertIs(stage.items, second_items)
            self.assertEqual(stage.items, second_snapshot)
            spawn.assert_called_once()

    def test_arrival_positions_do_not_immediately_bounce_back(self):
        stage, player, controls = Stage(items=[]), Player(x=ARROW_X[1]), Controls()
        self.assertTrue(stage.try_transition(player, controls))
        self.assertEqual(player.x, STAGE_ENTRY_LEFT_X)
        self.assertFalse(stage.try_transition(player, controls))
        player.x = ARROW_X[-1]
        self.assertTrue(stage.try_transition(player, controls))
        self.assertEqual(player.x, STAGE_ENTRY_RIGHT_X)
        self.assertFalse(stage.try_transition(player, controls))

    def test_second_stage_items_can_be_picked_up_and_dropped(self):
        stage, player, controls = Stage(items=[]), Player(x=ARROW_X[1]), Controls()
        stage.try_transition(player, controls, Random(1))
        original_count = len(stage.items)
        item = stage.items[0]
        player.x = item.x
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(stage.items, controls))
        self.assertEqual(player.weapon, item.kind)
        self.assertEqual(len(stage.items), original_count - 1)
        player.x = STAGE_ENTRY_LEFT_X
        controls.set_key("f", False)
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(stage.items, controls))
        self.assertIsNone(player.weapon)
        self.assertEqual(len(stage.items), original_count)

    def test_first_stage_only_right_arrow_second_stage_both_and_portal_not_loaded(self):
        images = {}
        for key in ("arrow_left", "arrow_right"):
            with Image.open(ROOT / IMAGE_FILES[key]) as source:
                self.assertEqual(source.size, (512, 320))
                images[key] = Mock(w=source.width, h=source.height)
        self.assertNotIn("Hood_Man_Teleport_Pad_512.png", IMAGE_FILES.values())
        draw_stage_arrows(images, 1)
        images["arrow_left"].draw.assert_not_called()
        images["arrow_right"].draw.assert_called_once()
        for image in images.values():
            image.reset_mock()
        draw_stage_arrows(images, 2)
        for direction, key in ((-1, "arrow_left"), (1, "arrow_right")):
            image = images[key]
            image.draw.assert_called_once()
            x, y, width, height = image.draw.call_args.args
            self.assertEqual((x, width, height), (ARROW_X[direction], ARROW_WIDTH, 50))
            self.assertEqual(y - height / 2, GROUND_Y)
            self.assertGreaterEqual(x - width / 2, 0)
            self.assertLessEqual(x + width / 2, WIDTH)
            self.assertLessEqual(y + height / 2, HEIGHT)
        self.assertLessEqual(ARROW_X[1] - ARROW_TRIGGER_HALF_WIDTH, WIDTH - PLAYER_HALF_WIDTH)
        self.assertGreaterEqual(ARROW_X[-1] + ARROW_TRIGGER_HALF_WIDTH, PLAYER_HALF_WIDTH)

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
