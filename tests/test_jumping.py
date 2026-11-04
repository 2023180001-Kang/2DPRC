import math
import unittest

from game import Controls, Player
from settings import (
    ANIMATIONS, FRAME_COUNT, GRAVITY, GROUND_Y, JUMP_DURATION, JUMP_SPEED, PLAYER_HALF_WIDTH,
    RUN_SPEED, WALK_SPEED, WIDTH,
)


class JumpingTests(unittest.TestCase):
    def test_jump_frames_do_not_wrap(self):
        player = Player(state="JUMP", animation_time=100 * JUMP_DURATION)
        self.assertEqual(player.frame, 7)
        player.state = "WALK"
        player.animation_time = FRAME_COUNT / ANIMATIONS["WALK"][1]
        self.assertEqual(player.frame, 0)

    def test_jump_animation_matches_physical_phase(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(0, controls)
        self.assertEqual((player.row, player.frame), (3, 0))
        player.update(JUMP_DURATION / 2, controls)
        self.assertEqual(player.frame, 4)
        self.assertAlmostEqual(player.animation_time, JUMP_DURATION / 2)
        player.animation_time = 0
        player.update(3 * JUMP_DURATION / 8, controls)
        self.assertEqual(player.frame, 7)
        self.assertAlmostEqual(player.animation_time, 7 * JUMP_DURATION / 8)

    def test_air_direction_and_run_changes_do_not_reset_animation(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(3 * JUMP_DURATION / 8, controls)
        controls.set_key("left", True)
        controls.set_key("lshift", True)
        player.update(0, controls)
        self.assertEqual((player.state, player.frame, player.facing), ("JUMP", 3, -1))

    def test_landing_resets_ground_animation(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(7 * JUMP_DURATION / 8, controls)
        controls.set_key("right", True)
        player.update(JUMP_DURATION / 8, controls)
        self.assertEqual((player.state, player.frame, player.animation_time), ("WALK", 0, 0))

    def test_defaults_and_grounded_requires_floor_and_zero_velocity(self):
        self.assertAlmostEqual(JUMP_SPEED, 480.0 * math.sqrt(2))
        self.assertEqual((GRAVITY, GROUND_Y), (1200.0, 140))
        self.assertAlmostEqual(JUMP_DURATION, 2 * JUMP_SPEED / GRAVITY)
        self.assertAlmostEqual(JUMP_DURATION, 1.131370849898476)
        self.assertEqual(ANIMATIONS["JUMP"], (3, FRAME_COUNT / JUMP_DURATION))
        player = Player()
        self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))
        self.assertTrue(player.grounded)
        for height, speed in ((GROUND_Y + 1, 0), (GROUND_Y, 1), (GROUND_Y, -1)):
            player.foot_y, player.vertical_speed = height, speed
            self.assertFalse(player.grounded)

    def test_space_requests_only_on_fresh_keydown(self):
        controls, player = Controls(), Player()
        self.assertIs(controls.jump_requested, False)
        controls.set_key("space", True)
        self.assertIs(controls.jump_requested, True)
        player.update(0, controls)
        for _ in range(5):
            controls.set_key("space", True)
            self.assertIs(controls.jump_requested, False)
        controls.set_key("space", False)
        controls.set_key("space", True)
        self.assertIs(controls.jump_requested, True)

    def test_quick_tap_survives_keyup_and_launches_once(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        controls.set_key("space", False)
        self.assertTrue(controls.jump_requested)
        elapsed = JUMP_DURATION / 8
        player.update(elapsed, controls)
        self.assertFalse(controls.jump_requested)
        self.assertAlmostEqual(player.foot_y, GROUND_Y + JUMP_SPEED * elapsed - GRAVITY * elapsed ** 2 / 2)
        self.assertAlmostEqual(player.vertical_speed, JUMP_SPEED - GRAVITY * elapsed)
        self.assertEqual(player.state, "JUMP")

    def test_apex_and_exact_flight_time(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        apex_time = JUMP_DURATION / 2
        player.update(apex_time, controls)
        peak_height = player.foot_y - GROUND_Y
        self.assertAlmostEqual(peak_height, JUMP_SPEED ** 2 / (2 * GRAVITY))
        self.assertAlmostEqual(peak_height, 192)
        self.assertAlmostEqual(peak_height / 96, 2)
        self.assertAlmostEqual(player.vertical_speed, 0)
        self.assertFalse(player.grounded)
        self.assertEqual(player.state, "JUMP")
        player.update(apex_time, controls)
        self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))
        self.assertTrue(player.grounded)

    def test_releasing_space_does_not_shorten_jump(self):
        for release in (False, True):
            with self.subTest(release=release):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                player.update(JUMP_DURATION / 8, controls)
                if release:
                    controls.set_key("space", False)
                player.update(3 * JUMP_DURATION / 8, controls)
                self.assertAlmostEqual(player.foot_y, GROUND_Y + 192)
                self.assertAlmostEqual(player.vertical_speed, 0)

    def test_holding_and_repeats_across_landing_require_repress(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(JUMP_DURATION, controls)
        for _ in range(3):
            controls.set_key("space", True)
            player.update(JUMP_DURATION / 8, controls)
            self.assertTrue(player.grounded)
            self.assertFalse(controls.jump_requested)
        controls.set_key("space", False)
        controls.set_key("space", True)
        player.update(JUMP_DURATION / 8, controls)
        self.assertFalse(player.grounded)
        self.assertAlmostEqual(player.vertical_speed, JUMP_SPEED - GRAVITY * JUMP_DURATION / 8)

    def test_exhausted_jump_requests_are_discarded_even_on_landing_update(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        elapsed = JUMP_DURATION / 8
        player.update(elapsed, controls)
        controls.set_key("space", False)
        controls.set_key("space", True)
        player.update(0, controls)
        self.assertEqual(player.jump_count, 2)
        height = player.foot_y
        for dt in (0, 2 * JUMP_DURATION):
            controls.set_key("space", False)
            controls.set_key("space", True)
            player.update(dt, controls)
            self.assertFalse(controls.jump_requested)
            if dt == 0:
                self.assertEqual((player.foot_y, player.vertical_speed, player.jump_count),
                                 (height, JUMP_SPEED, 2))
        self.assertTrue(player.grounded)
        self.assertEqual(player.jump_count, 0)
        controls.set_key("space", False)
        player.update(elapsed, controls)
        self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))

    def test_landing_uses_current_direction_and_run_input(self):
        for keys, state in (((), "IDLE"), (("lshift",), "IDLE"),
                            (("rshift",), "IDLE"), (("left",), "WALK"),
                            (("right", "lshift"), "RUN"), (("left", "rshift"), "RUN"),
                            (("right", "lshift", "rshift"), "RUN"),
                            (("left", "right", "rshift"), "IDLE")):
            with self.subTest(keys=keys):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                player.update(JUMP_DURATION / 2, controls)
                for key in keys:
                    controls.set_key(key, True)
                self.assertIs(controls.running, bool({"lshift", "rshift"}.intersection(keys)))
                player.update(JUMP_DURATION / 2, controls)
                self.assertTrue(player.grounded)
                self.assertEqual(player.state, state)

    def test_zero_dt_launches_and_consumes_without_displacement(self):
        controls, player = Controls(), Player()
        player.update(0, controls)
        self.assertTrue(player.grounded)
        controls.set_key("space", True)
        player.update(0, controls)
        self.assertEqual((player.x, player.foot_y), (WIDTH / 2, GROUND_Y))
        self.assertEqual((player.vertical_speed, player.state), (JUMP_SPEED, "JUMP"))
        self.assertFalse(player.grounded)
        self.assertFalse(controls.jump_requested)

    def test_long_update_clamps_landing_without_tunneling(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(100 * JUMP_DURATION, controls)
        self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))
        self.assertEqual(player.state, "IDLE")
        self.assertTrue(player.grounded)
        self.assertFalse(controls.jump_requested)

    def test_trajectory_is_step_size_independent_before_landing(self):
        elapsed = 3 * JUMP_DURATION / 4
        for steps in (1, 7, 60, 144):
            with self.subTest(steps=steps):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                for _ in range(steps):
                    player.update(elapsed / steps, controls)
                self.assertAlmostEqual(player.foot_y, GROUND_Y + JUMP_SPEED * elapsed - GRAVITY * elapsed ** 2 / 2)
                self.assertAlmostEqual(player.vertical_speed, JUMP_SPEED - GRAVITY * elapsed)
                self.assertEqual(player.state, "JUMP")

    def test_landing_duration_is_step_size_independent(self):
        for steps in (1, 30, 60, 144, 1000):
            with self.subTest(steps=steps):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                player.update(0, controls)
                for step in range(steps):
                    player.update(JUMP_DURATION / steps, controls)
                    if step < steps - 1:
                        self.assertFalse(player.grounded)
                self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))
                self.assertTrue(player.grounded)
                self.assertEqual((player.state, player.frame, player.animation_time), ("IDLE", 0, 0))
                self.assertFalse(controls.jump_requested)

    def test_air_steering_and_run_preserve_jump_state(self):
        elapsed = JUMP_DURATION / 8
        for shift in ("lshift", "rshift"):
            with self.subTest(shift=shift):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                controls.set_key("right", True)
                player.update(elapsed, controls)
                self.assertAlmostEqual(player.x, WIDTH / 2 + WALK_SPEED * elapsed)
                self.assertEqual((player.state, player.facing), ("JUMP", 1))
                controls.set_key("right", False)
                controls.set_key("left", True)
                controls.set_key(shift, True)
                self.assertTrue(controls.running)
                player.update(elapsed, controls)
                self.assertAlmostEqual(player.x, WIDTH / 2 + (WALK_SPEED - RUN_SPEED) * elapsed)
                self.assertEqual((player.state, player.facing), ("JUMP", -1))

    def test_airborne_horizontal_bounds(self):
        for key, edge in (("left", PLAYER_HALF_WIDTH), ("right", WIDTH - PLAYER_HALF_WIDTH)):
            with self.subTest(key=key):
                controls, player = Controls(), Player(x=edge)
                for pressed in (key, "rshift", "space"):
                    controls.set_key(pressed, True)
                player.update(JUMP_DURATION / 4, controls)
                self.assertEqual(player.x, edge)
                self.assertEqual(player.state, "JUMP")

    def test_unfocused_space_is_ignored_and_focus_allows_fresh_press(self):
        controls, player = Controls(focused=False), Player()
        controls.set_key("space", True)
        self.assertFalse(controls.jump_requested)
        self.assertNotIn("space", controls.held)
        player.update(JUMP_DURATION / 8, controls)
        self.assertTrue(player.grounded)
        controls.focused = True
        controls.set_key("space", True)
        player.update(0, controls)
        self.assertEqual(player.vertical_speed, JUMP_SPEED)
