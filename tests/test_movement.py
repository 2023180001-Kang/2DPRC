from math import log1p
import unittest

from game import Controls, Player
from settings import (
    ANIMATIONS, FRAME_COUNT, GROUND_DRAG, GROUND_FRICTION, GROUND_Y, MOVE_ACCELERATION, MOVE_DECELERATION,
    PLAYER_HALF_WIDTH, RUN_SPEED, WALK_SPEED, WIDTH,
)


class MovementTests(unittest.TestCase):
    def test_walking_speed_in_both_directions(self):
        for key, sign in (("left", -1), ("right", 1)):
            with self.subTest(key=key):
                player = Player(horizontal_speed=sign * WALK_SPEED)
                player.update(1, Controls({key}))
                self.assertAlmostEqual(player.x, WIDTH / 2 + sign * WALK_SPEED)

    def test_running_speed_in_both_directions(self):
        self.assertEqual(RUN_SPEED, 360.0 * 2.5)
        for key, sign in (("left", -1), ("right", 1)):
            for shifts in ({"lshift"}, {"rshift"}, {"lshift", "rshift"}):
                with self.subTest(key=key, shifts=shifts):
                    player = Player(horizontal_speed=sign * RUN_SPEED)
                    player.update(0.1, Controls({key} | shifts))
                    self.assertAlmostEqual(player.x, WIDTH / 2 + sign * RUN_SPEED * 0.1)

    def test_release_run_decelerates_only_after_last_shift(self):
        for shifts in (("lshift",), ("rshift",), ("lshift", "rshift"), ("rshift", "lshift")):
            with self.subTest(shifts=shifts):
                player, controls = Player(horizontal_speed=RUN_SPEED), Controls({"right", *shifts})
                for shift in shifts:
                    controls.set_key(shift, False)
                    player.update(0.05, controls)
                    expected_speed = RUN_SPEED if controls.running else RUN_SPEED - MOVE_DECELERATION * 0.05
                    self.assertAlmostEqual(player.horizontal_speed, expected_speed)
                self.assertGreater(player.horizontal_speed, WALK_SPEED)
                player.update(0.2, controls)
                self.assertEqual(player.horizontal_speed, WALK_SPEED)

    def test_step_size_independence(self):
        for held in ({"left"}, {"right"}, {"left", "lshift"}, {"right", "lshift"},
                     {"left", "rshift"}, {"right", "rshift"}):
            reference = Player()
            reference.update(0.4, Controls(held))
            for steps in (1, 30, 60, 144, 1000):
                with self.subTest(held=held, steps=steps):
                    player, controls = Player(), Controls(held)
                    for _ in range(steps):
                        player.update(0.4 / steps, controls)
                    self.assertAlmostEqual(player.x, reference.x, places=8)
                    self.assertAlmostEqual(player.horizontal_speed, reference.horizontal_speed, places=8)

    def test_idle_and_run_only_never_move(self):
        for held in (set(), {"lshift"}, {"rshift"}, {"lshift", "rshift"},
                     {"left", "right"}, {"left", "right", "lshift", "rshift"}):
            with self.subTest(held=held):
                player = Player()
                player.update(100, Controls(held))
                self.assertEqual(player.x, WIDTH / 2)
                self.assertEqual(player.state, "IDLE")

    def test_release_direction_brakes_to_a_stop_without_teleporting(self):
        player, controls = Player(), Controls({"left", "lshift"})
        player.update(0.25, controls)
        stopped = player.x
        speed = player.horizontal_speed
        controls.set_key("left", False)
        player.update(0, controls)
        self.assertEqual(player.horizontal_speed, speed)
        player.update(1, controls)
        stop_time = log1p(GROUND_DRAG * abs(speed) / GROUND_FRICTION) / GROUND_DRAG
        stop_distance = (abs(speed) - GROUND_FRICTION * stop_time) / GROUND_DRAG
        self.assertAlmostEqual(player.x, stopped - stop_distance)
        self.assertEqual((player.horizontal_speed, player.state), (0, "IDLE"))

    def test_foot_height_never_changes(self):
        player = Player()
        for held in (set(), {"left"}, {"right", "rshift"}, {"lshift"}, {"rshift"}):
            player.update(1, Controls(held))
            self.assertEqual(player.foot_y, GROUND_Y)

    def test_left_boundary_contains_full_frame(self):
        player = Player()
        player.update(100, Controls({"left", "lshift"}))
        self.assertEqual(player.x, PLAYER_HALF_WIDTH)
        self.assertGreaterEqual(player.x - PLAYER_HALF_WIDTH, 0)
        self.assertEqual(player.state, "RUN")
        self.assertEqual(player.horizontal_speed, 0)

    def test_right_boundary_contains_full_frame(self):
        player = Player()
        player.update(100, Controls({"right"}))
        self.assertEqual(player.x, WIDTH - PLAYER_HALF_WIDTH)
        self.assertLessEqual(player.x + PLAYER_HALF_WIDTH, WIDTH)
        self.assertEqual(player.state, "WALK")

    def test_repeated_boundary_input_does_not_wrap(self):
        player, controls = Player(), Controls({"right", "rshift"})
        for _ in range(100):
            player.update(1, controls)
            self.assertLessEqual(player.x, WIDTH - PLAYER_HALF_WIDTH)
        self.assertEqual(player.x, WIDTH - PLAYER_HALF_WIDTH)

    def test_reverse_input_leaves_boundary(self):
        player = Player(x=PLAYER_HALF_WIDTH)
        player.update(0.1, Controls({"right"}))
        ramp_time = WALK_SPEED / MOVE_ACCELERATION
        self.assertAlmostEqual(player.x, PLAYER_HALF_WIDTH + WALK_SPEED * (0.1 - ramp_time / 2))

    def test_zero_time_changes_state_without_moving(self):
        player = Player()
        player.update(0, Controls({"left", "lshift"}))
        self.assertEqual((player.x, player.state, player.facing), (WIDTH / 2, "RUN", -1))

    def test_animation_time_is_bounded_after_long_update(self):
        for state, (_, fps) in ANIMATIONS.items():
            held = set() if state == "IDLE" else {"right"}
            if state == "RUN":
                held.add("rshift")
            player = Player(state=state)
            player.update(10000.25, Controls(held))
            self.assertGreaterEqual(player.animation_time, 0)
            self.assertLess(player.animation_time, FRAME_COUNT / fps)
            self.assertIn(player.frame, range(FRAME_COUNT))
