import unittest

from game import Controls, Player
from settings import (
    ANIMATIONS, GRAVITY, GROUND_Y, JUMP_SPEED, PLAYER_HALF_WIDTH,
    RUN_SPEED, WALK_SPEED, WIDTH,
)


class JumpingTests(unittest.TestCase):
    def test_jump_frames_do_not_wrap(self):
        player = Player(state="JUMP", animation_time=100)
        self.assertEqual(player.frame, 7)
        player.state = "WALK"
        self.assertEqual(player.frame, 0)

    def test_jump_animation_matches_physical_phase(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(0, controls)
        self.assertEqual((player.row, player.frame), (3, 0))
        player.update(0.4, controls)
        self.assertEqual(player.frame, 4)
        player.update(0.3, controls)
        self.assertEqual(player.frame, 7)

    def test_air_direction_and_run_changes_do_not_reset_animation(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(0.3, controls)
        controls.set_key("left", True)
        controls.set_key("r", True)
        player.update(0, controls)
        self.assertEqual((player.state, player.frame, player.facing), ("JUMP", 3, -1))

    def test_landing_resets_ground_animation(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(0.7, controls)
        controls.set_key("right", True)
        player.update(0.1, controls)
        self.assertEqual((player.state, player.frame, player.animation_time), ("WALK", 0, 0))

    def test_defaults_and_grounded_requires_floor_and_zero_velocity(self):
        self.assertEqual((JUMP_SPEED, GRAVITY, GROUND_Y), (480.0, 1200.0, 140))
        self.assertEqual(ANIMATIONS["JUMP"], (3, 10))
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
        player.update(0.1, controls)
        self.assertFalse(controls.jump_requested)
        self.assertAlmostEqual(player.foot_y, GROUND_Y + 42)
        self.assertAlmostEqual(player.vertical_speed, 360)
        self.assertEqual(player.state, "JUMP")

    def test_apex_and_exact_flight_time(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(0.4, controls)
        self.assertAlmostEqual(player.foot_y, GROUND_Y + 96)
        self.assertAlmostEqual(player.vertical_speed, 0)
        self.assertFalse(player.grounded)
        self.assertEqual(player.state, "JUMP")
        player.update(0.4, controls)
        self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))
        self.assertTrue(player.grounded)

    def test_releasing_space_does_not_shorten_jump(self):
        for release in (False, True):
            with self.subTest(release=release):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                player.update(0.1, controls)
                if release:
                    controls.set_key("space", False)
                player.update(0.3, controls)
                self.assertAlmostEqual(player.foot_y, GROUND_Y + 96)
                self.assertAlmostEqual(player.vertical_speed, 0)

    def test_holding_and_repeats_across_landing_require_repress(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(0.8, controls)
        for _ in range(3):
            controls.set_key("space", True)
            player.update(0.1, controls)
            self.assertTrue(player.grounded)
            self.assertFalse(controls.jump_requested)
        controls.set_key("space", False)
        controls.set_key("space", True)
        player.update(0.1, controls)
        self.assertFalse(player.grounded)
        self.assertAlmostEqual(player.vertical_speed, 360)

    def test_airborne_requests_are_discarded_even_on_landing_update(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        player.update(0.1, controls)
        for dt in (0, 0.7):
            controls.set_key("space", False)
            controls.set_key("space", True)
            player.update(dt, controls)
            self.assertFalse(controls.jump_requested)
            if dt == 0:
                self.assertAlmostEqual(player.foot_y, GROUND_Y + 42)
                self.assertAlmostEqual(player.vertical_speed, 360)
        self.assertTrue(player.grounded)
        controls.set_key("space", False)
        player.update(0.1, controls)
        self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))

    def test_landing_uses_current_direction_and_run_input(self):
        for keys, state in (((), "IDLE"), (("r",), "IDLE"),
                            (("left",), "WALK"), (("right", "r"), "RUN"),
                            (("left", "right", "r"), "IDLE")):
            with self.subTest(keys=keys):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                player.update(0.4, controls)
                for key in keys:
                    controls.set_key(key, True)
                player.update(0.4, controls)
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
        player.update(100, controls)
        self.assertEqual((player.foot_y, player.vertical_speed), (GROUND_Y, 0))
        self.assertEqual(player.state, "IDLE")
        self.assertTrue(player.grounded)
        self.assertFalse(controls.jump_requested)

    def test_trajectory_is_step_size_independent_before_landing(self):
        for steps in (1, 7, 60, 144):
            with self.subTest(steps=steps):
                controls, player = Controls(), Player()
                controls.set_key("space", True)
                for _ in range(steps):
                    player.update(0.6 / steps, controls)
                self.assertAlmostEqual(player.foot_y, GROUND_Y + 72)
                self.assertAlmostEqual(player.vertical_speed, -240)
                self.assertEqual(player.state, "JUMP")

    def test_air_steering_and_run_preserve_jump_state(self):
        controls, player = Controls(), Player()
        controls.set_key("space", True)
        controls.set_key("right", True)
        player.update(0.1, controls)
        self.assertAlmostEqual(player.x, WIDTH / 2 + WALK_SPEED * 0.1)
        self.assertEqual((player.state, player.facing), ("JUMP", 1))
        controls.set_key("right", False)
        controls.set_key("left", True)
        controls.set_key("r", True)
        player.update(0.1, controls)
        self.assertAlmostEqual(player.x, WIDTH / 2 + (WALK_SPEED - RUN_SPEED) * 0.1)
        self.assertEqual((player.state, player.facing), ("JUMP", -1))

    def test_airborne_horizontal_bounds(self):
        for key, edge in (("left", PLAYER_HALF_WIDTH), ("right", WIDTH - PLAYER_HALF_WIDTH)):
            with self.subTest(key=key):
                controls, player = Controls(), Player(x=edge)
                for pressed in (key, "r", "space"):
                    controls.set_key(pressed, True)
                player.update(0.2, controls)
                self.assertEqual(player.x, edge)
                self.assertEqual(player.state, "JUMP")

    def test_unfocused_space_is_ignored_and_focus_allows_fresh_press(self):
        controls, player = Controls(focused=False), Player()
        controls.set_key("space", True)
        self.assertFalse(controls.jump_requested)
        self.assertNotIn("space", controls.held)
        player.update(0.1, controls)
        self.assertTrue(player.grounded)
        controls.focused = True
        controls.set_key("space", True)
        player.update(0, controls)
        self.assertEqual(player.vertical_speed, JUMP_SPEED)
