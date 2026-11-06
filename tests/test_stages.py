from math import log1p
from random import Random
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from game import Controls, Enemy, Item, Player, Stage
from rendering import draw_background, draw_stage_arrows
from resources import IMAGE_FILES, ROOT
from settings import (
    ARROW_SPAWN_PADDING, ARROW_SWAY_AMPLITUDE, ARROW_SWAY_PERIOD, ARROW_TRIGGER_HALF_WIDTH,
    ARROW_WIDTH, ARROW_X, GROUND_Y, HEIGHT, ITEM_WIDTHS, PLAYER_HALF_WIDTH, RUN_SPEED,
    GROUND_DRAG, GROUND_FRICTION, STAGE_ARROWS, STAGE_ENTRY_LEFT_X, STAGE_ENTRY_RIGHT_X, WALK_SPEED, WIDTH,
)


class StageTests(unittest.TestCase):
    def setUp(self):
        # Exercise travel after clearing the encounter; gates have their own tests.
        patcher = patch("game.spawn_enemy", side_effect=lambda *args, **kwargs: Enemy(state="DEAD"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_starts_on_first_background_and_only_activates_inside_right_arrow(self):
        for offset, enters in ((-31, False), (-30, True), (0, True), (30, True), (31, False)):
            with self.subTest(offset=offset):
                stage, player = Stage(items=[]), Player(x=ARROW_X[1] + offset)
                self.assertEqual(stage.background_key, "background")
                self.assertEqual(stage.try_transition(player, Controls(), Random(1)), enters)
                self.assertEqual(stage.number, 2 if enters else 1)

    def test_airborne_arrow_overlap_preserves_all_jump_fields(self):
        for number, direction in ((1, 1), (2, -1)):
            for height, speed in ((GROUND_Y + 1, 0), (GROUND_Y + 192, 200),
                                  (GROUND_Y + 384, -200), (GROUND_Y, 1), (GROUND_Y, -1)):
                for used in (1, 2):
                    with self.subTest(stage=number, height=height, speed=speed, used=used):
                        stage = Stage(items=[], number=number, arrow_time=0.4)
                        player = Player(x=ARROW_X[direction], foot_y=height, vertical_speed=speed,
                                        state="JUMP", jump_count=used, animation_time=0.4,
                                        facing=direction, weapon="steel_pipe", health=2)
                        before = vars(player).copy()
                        key = "right" if direction > 0 else "left"
                        controls = Controls(held={key, "rshift", "space", "f"},
                                            jump_requested=True, pickup_requested=True)
                        held = controls.held.copy()
                        self.assertTrue(stage.try_transition(player, controls, Random(1)))
                        entry = STAGE_ENTRY_LEFT_X if direction > 0 else STAGE_ENTRY_RIGHT_X
                        self.assertEqual(vars(player), dict(before, x=entry))
                        self.assertEqual(controls.held, held)
                        self.assertFalse(controls.jump_requested or controls.pickup_requested)
                        self.assertEqual(stage.arrow_time, 0.4)

    def test_second_stage_left_arrow_return_includes_range_boundary(self):
        for offset, returns in ((-31, False), (-30, True), (0, True), (30, True), (31, False)):
            with self.subTest(offset=offset):
                stage = Stage(items=[], number=2)
                player = Player(x=ARROW_X[-1] + offset)
                self.assertEqual(stage.try_transition(player, Controls(), Random(1)), returns)
                self.assertEqual(stage.number, 1 if returns else 2)

    def test_transition_preserves_held_keys_health_and_weapon_but_clears_tap_requests(self):
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
        self.assertEqual((player.state, player.facing, player.animation_time), ("RUN", 1, 0))
        self.assertEqual(controls.held, {"right", "lshift", "f", "space"})
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
                                           ARROW_WIDTH / 2 + ARROW_SWAY_AMPLITUDE + ARROW_SPAWN_PADDING + half)
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

    def test_forward_and_backward_transitions_continue_walking_or_running_until_release(self):
        for number, direction, key in ((1, 1, "right"), (2, -1, "left")):
            for shifts in (set(), {"lshift"}, {"rshift"}, {"lshift", "rshift"}):
                with self.subTest(stage=number, shifts=shifts):
                    stage = Stage(items=[], number=number)
                    speed = RUN_SPEED if shifts else WALK_SPEED
                    player = Player(x=ARROW_X[direction], weapon="dagger", horizontal_speed=direction * speed)
                    held = {key, "f", "space"} | shifts
                    controls = Controls(held=held.copy(), jump_requested=True, pickup_requested=True)
                    self.assertTrue(stage.try_transition(player, controls, Random(1)))
                    start_x = player.x
                    self.assertEqual(controls.held, held)
                    expected_state = "RUN" if shifts else "WALK"
                    self.assertEqual(player.state, expected_state)
                    self.assertEqual(player.horizontal_speed, direction * speed)
                    self.assertFalse(player.pick_up(stage.items, controls))
                    player.update(0.1, controls)
                    self.assertAlmostEqual(player.x, start_x + direction * speed * 0.1)
                    self.assertTrue(player.grounded)
                    self.assertEqual((player.weapon, player.jump_count), ("dagger", 0))
                    controls.set_key(key, False)
                    stopped_x = player.x
                    player.update(1.0, controls)
                    stop_time = log1p(GROUND_DRAG * speed / GROUND_FRICTION) / GROUND_DRAG
                    stop_distance = (speed - GROUND_FRICTION * stop_time) / GROUND_DRAG
                    self.assertAlmostEqual(player.x, stopped_x + direction * stop_distance)
                    self.assertEqual((player.horizontal_speed, player.state), (0, "IDLE"))

    def test_arrow_sway_is_bounded_periodic_and_stays_on_screen(self):
        images = {key: Mock(w=512, h=320) for key in ("arrow_left", "arrow_right")}
        for elapsed, offset in ((0, 0), (ARROW_SWAY_PERIOD / 4, ARROW_SWAY_AMPLITUDE),
                                (ARROW_SWAY_PERIOD * 3 / 4, -ARROW_SWAY_AMPLITUDE),
                                (ARROW_SWAY_PERIOD, 0)):
            draw_stage_arrows(images, 2, elapsed)
            for direction, key in ((-1, "arrow_left"), (1, "arrow_right")):
                x, y, width, height = images[key].draw.call_args.args
                self.assertAlmostEqual(x, ARROW_X[direction] + direction * offset)
                self.assertLessEqual(abs(x - ARROW_X[direction]), ARROW_SWAY_AMPLITUDE)
                self.assertGreaterEqual(x - width / 2, 0)
                self.assertLessEqual(x + width / 2, WIDTH)
                self.assertEqual(y - height / 2, GROUND_Y)

    def test_arrow_clock_uses_elapsed_time_and_does_not_reset_on_transition(self):
        whole, split = Stage(items=[]), Stage(items=[])
        whole.update(2.5)
        for _ in range(25):
            split.update(0.1)
        self.assertAlmostEqual(whole.arrow_time, split.arrow_time)
        self.assertGreaterEqual(whole.arrow_time, 0)
        self.assertLess(whole.arrow_time, ARROW_SWAY_PERIOD)
        before = split.arrow_time
        self.assertTrue(split.try_transition(Player(x=ARROW_X[1]), Controls()))
        self.assertEqual(split.arrow_time, before)

    def test_sway_phase_does_not_move_the_stage_trigger(self):
        for phase in (ARROW_SWAY_PERIOD / 4, ARROW_SWAY_PERIOD * 3 / 4):
            stage = Stage(items=[], arrow_time=phase)
            player = Player(x=ARROW_X[1] - ARROW_TRIGGER_HALF_WIDTH - 1)
            self.assertFalse(stage.try_transition(player, Controls()))
            player.x += 1
            self.assertTrue(stage.try_transition(player, Controls()))
