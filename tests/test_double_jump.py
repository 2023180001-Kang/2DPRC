import unittest

from game import Controls, Item, Player
from settings import GRAVITY, GROUND_Y, JUMP_DURATION, JUMP_SPEED, MAX_JUMPS, RUN_SPEED


def press_space(controls):
    controls.set_key("space", False)
    controls.set_key("space", True)


class DoubleJumpTests(unittest.TestCase):
    def test_default_counter_and_two_jump_limit(self):
        player = Player()
        self.assertIs(type(player.jump_count), int)
        self.assertEqual(player.jump_count, 0)
        self.assertEqual(MAX_JUMPS, 2)

    def test_second_launch_during_ascent_or_fall_resets_velocity_at_current_height(self):
        for elapsed in (JUMP_DURATION / 4, 3 * JUMP_DURATION / 4):
            with self.subTest(elapsed=elapsed):
                controls, player = Controls(), Player()
                press_space(controls)
                player.update(elapsed, controls)
                height, speed = player.foot_y, player.vertical_speed
                self.assertAlmostEqual(speed, JUMP_SPEED - GRAVITY * elapsed)
                press_space(controls)
                player.update(0, controls)
                self.assertEqual((player.foot_y, player.vertical_speed), (height, JUMP_SPEED))
                self.assertEqual((player.jump_count, player.state), (2, "JUMP"))
                self.assertFalse(controls.jump_requested)
                dt = JUMP_DURATION / 8
                player.update(dt, controls)
                self.assertAlmostEqual(player.foot_y, height + JUMP_SPEED * dt - GRAVITY * dt ** 2 / 2)
                self.assertAlmostEqual(player.vertical_speed, JUMP_SPEED - GRAVITY * dt)

    def test_third_request_is_ignored_and_consumed(self):
        controls, player = Controls(), Player()
        for _ in range(2):
            press_space(controls)
            player.update(JUMP_DURATION / 8, controls)
        height, speed = player.foot_y, player.vertical_speed
        press_space(controls)
        player.update(0, controls)
        self.assertEqual((player.foot_y, player.vertical_speed, player.jump_count), (height, speed, 2))
        self.assertFalse(controls.jump_requested)
        player.update(JUMP_DURATION / 8, controls)
        self.assertAlmostEqual(player.vertical_speed, speed - GRAVITY * JUMP_DURATION / 8)

    def test_holding_and_repeated_keydown_do_not_launch_after_landing(self):
        controls, player = Controls(), Player()
        for _ in range(2):
            press_space(controls)
            player.update(JUMP_DURATION / 8, controls)
        player.update(2 * JUMP_DURATION, controls)
        for _ in range(3):
            controls.set_key("space", True)
            player.update(JUMP_DURATION / 8, controls)
            self.assertEqual((player.foot_y, player.vertical_speed, player.jump_count), (GROUND_Y, 0, 0))
            self.assertFalse(controls.jump_requested)

    def test_landing_resets_count_and_allows_another_pair(self):
        controls, player = Controls(), Player()
        for _ in range(2):
            for count in (1, 2):
                press_space(controls)
                player.update(JUMP_DURATION / 8, controls)
                self.assertEqual(player.jump_count, count)
            player.update(2 * JUMP_DURATION, controls)
            self.assertTrue(player.grounded)
            self.assertEqual(player.jump_count, 0)

    def test_second_launch_at_first_apex_reaches_384_above_floor(self):
        controls, player = Controls(), Player()
        for height in (192, 384):
            press_space(controls)
            player.update(JUMP_DURATION / 2, controls)
            self.assertAlmostEqual(player.foot_y - GROUND_Y, height)
            self.assertAlmostEqual(player.vertical_speed, 0)
            self.assertFalse(player.grounded)
        self.assertEqual(player.jump_count, 2)

    def test_second_launch_resets_velocity_derived_animation_clock(self):
        controls, player = Controls(), Player()
        press_space(controls)
        player.update(3 * JUMP_DURATION / 4, controls)
        self.assertEqual((player.state, player.frame), ("JUMP", 6))
        press_space(controls)
        player.update(0, controls)
        self.assertEqual((player.state, player.row, player.frame, player.animation_time), ("JUMP", 3, 0, 0))
        player.animation_time = 100
        player.update(JUMP_DURATION / 8, controls)
        self.assertAlmostEqual(player.animation_time, JUMP_DURATION / 8)
        self.assertEqual(player.frame, 1)

    def test_shift_steering_weapon_persistence_and_ground_only_pickup(self):
        for shift in ("lshift", "rshift"):
            with self.subTest(shift=shift):
                controls, player = Controls(), Player(weapon="dagger", horizontal_speed=-RUN_SPEED)
                controls.set_key("left", True)
                controls.set_key(shift, True)
                start_x = player.x
                for _ in range(2):
                    press_space(controls)
                    player.update(JUMP_DURATION / 8, controls)
                    self.assertEqual((player.state, player.facing, player.weapon), ("JUMP", -1, "dagger"))
                    items = [Item("steel_pipe", player.x, player.foot_y)]
                    self.assertIsNone(player.pickup_target(items))
                    self.assertFalse(player.pick_up(items, controls))
                    self.assertFalse(controls.pickup_requested)
                    self.assertEqual(len(items), 1)
                self.assertAlmostEqual(player.x, start_x - RUN_SPEED * JUMP_DURATION / 4)
                controls.set_key("left", False)
                player.update(2 * JUMP_DURATION, controls)
                items = [Item("steel_pipe", player.x)]
                self.assertEqual(player.weapon, "dagger")
                self.assertFalse(player.pick_up(items, controls))
                controls.set_key("f", False)
                controls.set_key("f", True)
                self.assertTrue(player.pick_up(items, controls))
                self.assertEqual(player.weapon, "steel_pipe")

    def test_split_time_invariance_around_fixed_second_launch(self):
        before, after = 3 * JUMP_DURATION / 4, JUMP_DURATION / 4
        for steps in (1, 7, 60, 144):
            with self.subTest(steps=steps):
                controls, player = Controls(), Player()
                for duration in (before, after):
                    press_space(controls)
                    for _ in range(steps):
                        player.update(duration / steps, controls)
                height = GROUND_Y + JUMP_SPEED * before - GRAVITY * before ** 2 / 2
                self.assertAlmostEqual(player.foot_y, height + JUMP_SPEED * after - GRAVITY * after ** 2 / 2)
                self.assertAlmostEqual(player.vertical_speed, JUMP_SPEED - GRAVITY * after)
                self.assertAlmostEqual(player.animation_time, after)
                self.assertEqual((player.jump_count, player.state, player.frame), (2, "JUMP", 2))

    def test_long_update_after_second_launch_clamps_and_resets(self):
        controls, player = Controls(), Player()
        press_space(controls)
        player.update(JUMP_DURATION / 2, controls)
        press_space(controls)
        player.update(100 * JUMP_DURATION, controls)
        self.assertEqual((player.foot_y, player.vertical_speed, player.jump_count), (GROUND_Y, 0, 0))
        self.assertEqual((player.state, player.frame, player.animation_time), ("IDLE", 0, 0))
        self.assertTrue(player.grounded)
        self.assertFalse(controls.jump_requested)

    def test_initial_airborne_zero_counter_cannot_ghost_jump(self):
        for speed in (-JUMP_SPEED / 2, 0, JUMP_SPEED / 2):
            with self.subTest(speed=speed):
                controls = Controls()
                player = Player(foot_y=GROUND_Y + 50, vertical_speed=speed)
                press_space(controls)
                player.update(0, controls)
                self.assertEqual((player.foot_y, player.vertical_speed, player.jump_count), (GROUND_Y + 50, speed, 0))
                self.assertEqual(player.state, "JUMP")
                self.assertFalse(controls.jump_requested)
