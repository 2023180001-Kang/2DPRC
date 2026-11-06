from math import sqrt
from random import Random
import unittest
from unittest.mock import Mock, patch

from game import Controls, Enemy, Item, Player, Stage
from rendering import draw_falling_items, draw_items, draw_pickup_hint
from settings import AIR_DROP_HEIGHT, ARROW_X, GRAVITY, GROUND_Y, ITEM_WIDTHS


class FallingItemTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("game.spawn_enemy", side_effect=lambda *args, **kwargs: Enemy(state="DEAD"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_air_drop_in_both_maps_and_directions_while_rising_or_falling(self):
        for number in (1, 2):
            for kind in ITEM_WIDTHS:
                for facing in (-1, 1):
                    for speed in (-200, 0, 200):
                        with self.subTest(map=number, kind=kind, facing=facing, speed=speed):
                            player = Player(foot_y=GROUND_Y + 120, state="JUMP", jump_count=2,
                                            vertical_speed=speed, facing=facing, weapon=kind)
                            stage = Stage(items=[Item("dagger", player.x)], number=number)
                            controls = Controls(pickup_requested=True)
                            self.assertTrue(player.pick_up(stage.items, controls))
                            self.assertIsNone(player.weapon)
                            self.assertFalse(controls.pickup_requested)
                            self.assertEqual(stage.items[-1], Item(kind, player.x,
                                             player.foot_y + AIR_DROP_HEIGHT, falling=True))
                            self.assertEqual((player.jump_count, player.vertical_speed), (2, speed))
                            self.assertEqual(len(stage.items), 2)

    def test_fall_accelerates_downward_and_is_time_partition_invariant(self):
        original = Item("steel_pipe", 500, GROUND_Y + 300, falling=True)
        whole = original.update(0.4)
        split = original
        for _ in range(40):
            split = split.update(0.01)
        self.assertAlmostEqual(whole.foot_y, GROUND_Y + 300 - GRAVITY * 0.4 ** 2 / 2)
        self.assertAlmostEqual(whole.vertical_speed, -GRAVITY * 0.4)
        self.assertAlmostEqual(split.foot_y, whole.foot_y)
        self.assertAlmostEqual(split.vertical_speed, whole.vertical_speed)
        self.assertEqual(whole.x, original.x)
        self.assertGreater(original.update(0.1).foot_y, original.update(0.2).foot_y)
        self.assertGreater(original.update(0.1).vertical_speed, original.update(0.2).vertical_speed)

    def test_zero_time_exact_landing_and_long_frame_do_not_penetrate_floor(self):
        item = Item("dagger", 400, GROUND_Y + 192, falling=True)
        self.assertEqual(item.update(0), item)
        fall_time = sqrt(2 * 192 / GRAVITY)
        for dt in (fall_time, 10):
            with self.subTest(dt=dt):
                landed = item.update(dt)
                self.assertEqual(landed, Item("dagger", 400))
                self.assertIs(landed.update(1), landed)

    def test_each_falling_item_updates_without_moving_resting_items_or_respawning(self):
        resting = Item("steel_pipe", 200)
        stage = Stage(items=[resting, Item("dagger", 400, GROUND_Y + 10, falling=True),
                             Item("steel_pipe", 600, GROUND_Y + 300, falling=True)])
        original_list = stage.items
        stage.update(0.2)
        self.assertIs(stage.items, original_list)
        self.assertIs(stage.items[0], resting)
        self.assertFalse(stage.items[1].falling)
        self.assertTrue(stage.items[2].falling)
        self.assertEqual(len(stage.items), 3)

    def test_landed_drop_can_be_picked_up_but_falling_drop_has_no_hint(self):
        player = Player()
        stage = Stage(items=[Item("dagger", player.x, GROUND_Y + 10, falling=True)])
        images = {"dagger": Mock(w=880, h=200)}
        with patch("rendering.draw_rectangle") as rectangle:
            self.assertIsNone(draw_pickup_hint(images, stage.items, player))
            rectangle.assert_not_called()
            self.assertFalse(player.pick_up(stage.items, Controls(pickup_requested=True)))
            stage.update(1)
            self.assertIs(draw_pickup_hint(images, stage.items, player), stage.items[0])
        self.assertTrue(player.pick_up(stage.items, Controls(pickup_requested=True)))
        self.assertEqual((player.weapon, stage.items), ("dagger", []))

    def test_near_falling_item_does_not_hide_a_pickable_ground_target(self):
        player = Player(weapon="dagger")
        falling = Item("dagger", player.x, GROUND_Y + 1, falling=True)
        stage = Stage(items=[falling, Item("steel_pipe", player.x + 20)])
        self.assertEqual(player.pickup_target(stage.items), 1)
        self.assertTrue(player.pick_up(stage.items, Controls(pickup_requested=True)))
        self.assertEqual(player.weapon, "steel_pipe")
        self.assertIn(falling, stage.items)

    def test_repeated_f_does_not_duplicate_drop_or_auto_pick_up_on_landing(self):
        player = Player(weapon="dagger", foot_y=GROUND_Y + 192, state="JUMP")
        controls, stage = Controls(), Stage(items=[])
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(stage.items, controls))
        for _ in range(3):
            controls.set_key("f", True)
            self.assertFalse(player.pick_up(stage.items, controls))
            self.assertEqual(len(stage.items), 1)
        stage.update(2)
        player.update(2, controls)
        self.assertFalse(player.pick_up(stage.items, controls))
        self.assertIsNone(player.weapon)
        controls.set_key("f", False)
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(stage.items, controls))
        self.assertEqual((player.weapon, stage.items), ("dagger", []))

    def test_airborne_empty_hand_request_is_consumed_without_pickup_after_landing(self):
        player = Player(foot_y=GROUND_Y + 10, state="JUMP")
        stage = Stage(items=[Item("dagger", player.x)])
        controls = Controls(pickup_requested=True)
        self.assertFalse(player.pick_up(stage.items, controls))
        self.assertFalse(controls.pickup_requested)
        player.update(1, controls)
        self.assertFalse(player.pick_up(stage.items, controls))
        self.assertIsNone(player.weapon)

    def test_drop_falls_independently_of_player_movement_or_focus(self):
        player = Player(weapon="steel_pipe", foot_y=GROUND_Y + 192, state="JUMP")
        stage = Stage(items=[])
        controls = Controls(pickup_requested=True, held={"right", "lshift"})
        player.pick_up(stage.items, controls)
        start_x, start_y = stage.items[0].x, stage.items[0].foot_y
        player.update(0.2, controls)
        controls.held.clear()
        controls.focused = False
        stage.update(0.2)
        self.assertGreater(player.x, start_x)
        self.assertEqual(stage.items[0].x, start_x)
        self.assertLess(stage.items[0].foot_y, start_y)

    def test_return_restores_old_map_falling_items_and_resumes_their_fall(self):
        old_items = [Item("dagger", ARROW_X[1], GROUND_Y + 200, falling=True)]
        stage = Stage(items=old_items)
        self.assertTrue(stage.try_transition(Player(x=ARROW_X[1]), Controls(), Random(1)))
        self.assertTrue(all(not item.falling and item.foot_y == GROUND_Y for item in stage.items))
        self.assertIsNot(stage.items, old_items)
        self.assertIn(len(stage.items), (3, 4, 5))
        stage.update(0.2)
        self.assertEqual(old_items[0].foot_y, GROUND_Y + 200)
        self.assertTrue(stage.try_transition(Player(x=ARROW_X[-1]), Controls()))
        self.assertIs(stage.items, old_items)
        stage.update(0.2)
        self.assertLess(old_items[0].foot_y, GROUND_Y + 200)

    def test_resting_and_falling_renderers_draw_each_item_once_at_its_height(self):
        images = {kind: Mock(w=880, h=200) for kind in ITEM_WIDTHS}
        items = [Item("dagger", 300), Item("steel_pipe", 500, GROUND_Y + 120, falling=True)]
        draw_items(images, items)
        images["dagger"].draw.assert_called_once()
        images["steel_pipe"].draw.assert_not_called()
        draw_falling_items(images, items)
        images["dagger"].draw.assert_called_once()
        images["steel_pipe"].draw.assert_called_once()
        x, y, width, height = images["steel_pipe"].draw.call_args.args
        self.assertEqual((x, y - height / 2), (500, GROUND_Y + 120))
        self.assertEqual(width, ITEM_WIDTHS["steel_pipe"])
        self.assertAlmostEqual(width / height, 880 / 200)
