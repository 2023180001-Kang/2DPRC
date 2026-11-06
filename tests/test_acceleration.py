from math import log1p
from random import Random
import unittest

from game import Controls, Enemy, Player, Stage
from settings import (
    ARROW_X, GROUND_DRAG, GROUND_FRICTION, MOVE_ACCELERATION, PLAYER_HALF_WIDTH,
    RUN_SPEED, STAGE_ENTRY_LEFT_X, WALK_SPEED, WIDTH,
)


class AccelerationTests(unittest.TestCase):
    def test_running_accelerates_continuously_and_caps_at_maximum(self):
        for key, sign in (("right", 1), ("left", -1)):
            player, controls = Player(), Controls({key, "lshift"})
            for elapsed, expected_speed in ((0.1, 180), (0.1, 360), (0.1, 540),
                                            (0.1, 720), (0.1, 900), (0.1, 900)):
                player.update(elapsed, controls)
                self.assertAlmostEqual(player.horizontal_speed, sign * expected_speed)
            self.assertAlmostEqual(player.x, WIDTH / 2 + sign * 315)

    def test_shift_release_brakes_smoothly_to_walk_without_undershooting(self):
        player = Player(horizontal_speed=RUN_SPEED, state="RUN")
        controls = Controls({"right"})
        player.update(0, controls)
        self.assertEqual(player.horizontal_speed, RUN_SPEED)
        player.update(0.08, controls)
        self.assertEqual(player.horizontal_speed, 540)
        self.assertEqual(player.state, "RUN")
        player.update(0.08, controls)
        self.assertEqual((player.horizontal_speed, player.state), (WALK_SPEED, "WALK"))
        player.update(0.1, controls)
        self.assertEqual(player.horizontal_speed, WALK_SPEED)

    def test_direction_release_coasts_to_a_finite_friction_stop(self):
        player = Player(horizontal_speed=RUN_SPEED, state="RUN")
        controls = Controls()
        player.update(0.1, controls)
        self.assertGreater(player.horizontal_speed, 0)
        self.assertLess(player.horizontal_speed, RUN_SPEED)
        self.assertGreater(player.x, WIDTH / 2)
        stop_time = log1p(GROUND_DRAG * RUN_SPEED / GROUND_FRICTION) / GROUND_DRAG
        player.update(stop_time - 0.1 + 1e-8, controls)
        self.assertEqual((player.horizontal_speed, player.state), (0, "IDLE"))
        self.assertAlmostEqual(player.x - WIDTH / 2, (RUN_SPEED - GROUND_FRICTION * stop_time) / GROUND_DRAG)

    def test_reversal_brakes_before_gaining_speed_in_the_new_direction(self):
        player, controls = Player(horizontal_speed=RUN_SPEED), Controls({"left", "rshift"})
        player.update(0.05, controls)
        self.assertEqual(player.horizontal_speed, 600)
        self.assertEqual(player.facing, -1)
        player.update(0.1, controls)
        self.assertAlmostEqual(player.horizontal_speed, 0)
        player.update(0.1, controls)
        self.assertAlmostEqual(player.horizontal_speed, -180)

    def test_acceleration_braking_and_reversal_do_not_depend_on_frame_rate(self):
        sequence = ((0.16, {"right", "lshift"}), (0.12, {"right"}),
                    (0.2, {"left", "rshift"}), (0.08, {"left"}), (0.14, set()))
        reference = Player()
        checkpoints = []
        for duration, held in sequence:
            reference.update(duration, Controls(held))
            checkpoints.append((reference.x, reference.horizontal_speed))
        for steps in (7, 30, 60, 144, 1000):
            player = Player()
            for (duration, held), (x, speed) in zip(sequence, checkpoints):
                for _ in range(steps):
                    player.update(duration / steps, Controls(held))
                    self.assertLessEqual(abs(player.horizontal_speed), RUN_SPEED + 1e-8)
                self.assertAlmostEqual(player.x, x, places=8)
                self.assertAlmostEqual(player.horizontal_speed, speed, places=8)

    def test_walk_run_switch_preserves_gait_phase(self):
        player = Player(state="WALK", horizontal_speed=WALK_SPEED, animation_time=3 / 8)
        player.update(0, Controls({"right", "lshift"}))
        self.assertEqual((player.state, player.frame), ("RUN", 3))
        player.update(0, Controls({"right"}))
        self.assertEqual((player.state, player.frame), ("WALK", 3))

    def test_running_animation_tracks_actual_movement_speed(self):
        slow = Player(state="RUN", horizontal_speed=RUN_SPEED / 2)
        fast = Player(state="RUN", horizontal_speed=RUN_SPEED)
        controls = Controls({"right", "lshift"})
        slow.update(0.1, controls)
        fast.update(0.1, controls)
        self.assertLess(slow.x, fast.x)
        self.assertGreater(slow.animation_time, 0)
        self.assertLess(slow.animation_time, fast.animation_time)
        self.assertEqual(fast.frame, 3)  # 900 px/s plays the run cycle at 30 FPS.

    def test_focus_loss_clears_momentum_instead_of_coasting_offscreen(self):
        player = Player(horizontal_speed=RUN_SPEED, state="RUN")
        player.update(0.1, Controls(focused=False))
        self.assertEqual((player.x, player.horizontal_speed, player.state), (WIDTH / 2, 0, "IDLE"))

    def test_boundary_clears_outward_velocity_and_reversal_restarts_from_zero(self):
        player = Player(x=WIDTH - PLAYER_HALF_WIDTH, horizontal_speed=RUN_SPEED)
        player.update(0.1, Controls({"right", "rshift"}))
        self.assertEqual(player.horizontal_speed, 0)
        self.assertEqual(player.state, "RUN")
        player.update(0.1, Controls({"left", "rshift"}))
        self.assertAlmostEqual(player.horizontal_speed, -MOVE_ACCELERATION * 0.1)
        self.assertLess(player.x, WIDTH - PLAYER_HALF_WIDTH)

    def test_stage_transition_preserves_partial_run_speed_on_ground_and_in_air(self):
        for airborne in (False, True):
            stage = Stage([], enemy=Enemy(state="DEAD"))
            player = Player(x=ARROW_X[1], horizontal_speed=370)
            if airborne:
                player.foot_y += 100
                player.vertical_speed, player.state, player.jump_count = 200, "JUMP", 1
            controls = Controls({"right", "lshift"})
            self.assertTrue(stage.try_transition(player, controls, Random(1)))
            self.assertEqual((player.x, player.horizontal_speed), (STAGE_ENTRY_LEFT_X, 370))
            player.update(0.1, controls)
            self.assertEqual(player.horizontal_speed, 550)
            self.assertAlmostEqual(player.x, STAGE_ENTRY_LEFT_X + (370 + 550) / 2 * 0.1)

    def test_fast_exit_step_preserves_momentum_even_if_it_reaches_the_screen_clamp(self):
        for number, sign, key, x in ((1, 1, "right", WIDTH - PLAYER_HALF_WIDTH - 1),
                                      (2, -1, "left", PLAYER_HALF_WIDTH + 1)):
            stage = Stage([], number=number, enemy=Enemy(state="DEAD"))
            player = Player(x=x, horizontal_speed=sign * RUN_SPEED)
            controls = Controls({key, "lshift"})
            player.update(1 / 60, controls)
            self.assertEqual(player.horizontal_speed, 0)
            self.assertTrue(stage.try_transition(player, controls))
            self.assertEqual(player.horizontal_speed, sign * RUN_SPEED)
            self.assertEqual(player.boundary_speed, 0)
