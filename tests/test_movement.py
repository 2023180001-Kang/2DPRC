import unittest

from game import Controls, Player
from settings import ANIMATIONS, FRAME_COUNT, GROUND_Y, PLAYER_HALF_WIDTH, RUN_SPEED, WALK_SPEED, WIDTH


class MovementTests(unittest.TestCase):
    def test_walking_speed_in_both_directions(self):
        for key, sign in (("left", -1), ("right", 1)):
            with self.subTest(key=key):
                player = Player()
                player.update(1, Controls({key}))
                self.assertAlmostEqual(player.x, WIDTH / 2 + sign * WALK_SPEED)

    def test_running_speed_in_both_directions(self):
        self.assertGreater(RUN_SPEED, WALK_SPEED)
        for key, sign in (("left", -1), ("right", 1)):
            with self.subTest(key=key):
                player = Player()
                player.update(1, Controls({key, "r"}))
                self.assertAlmostEqual(player.x, WIDTH / 2 + sign * RUN_SPEED)

    def test_release_run_changes_distance_immediately(self):
        player, controls = Player(), Controls({"right", "r"})
        player.update(0.25, controls)
        controls.set_key("r", False)
        player.update(0.25, controls)
        self.assertAlmostEqual(player.x - WIDTH / 2, (RUN_SPEED + WALK_SPEED) / 4)

    def test_step_size_independence(self):
        for held in ({"left"}, {"right"}, {"left", "r"}, {"right", "r"}):
            reference = Player()
            reference.update(1, Controls(held))
            for steps in (1, 30, 60, 144, 1000):
                with self.subTest(held=held, steps=steps):
                    player, controls = Player(), Controls(held)
                    for _ in range(steps):
                        player.update(1 / steps, controls)
                    self.assertAlmostEqual(player.x, reference.x, places=8)

    def test_idle_and_run_only_never_move(self):
        for held in (set(), {"r"}, {"left", "right"}, {"left", "right", "r"}):
            player = Player()
            player.update(100, Controls(held))
            self.assertEqual(player.x, WIDTH / 2)

    def test_release_direction_stops_immediately(self):
        player, controls = Player(), Controls({"left", "r"})
        player.update(0.25, controls)
        stopped = player.x
        controls.set_key("left", False)
        player.update(1, controls)
        self.assertEqual(player.x, stopped)

    def test_foot_height_never_changes(self):
        player = Player()
        for held in (set(), {"left"}, {"right", "r"}, {"r"}):
            player.update(1, Controls(held))
            self.assertEqual(player.foot_y, GROUND_Y)

    def test_left_boundary_contains_full_frame(self):
        player = Player()
        player.update(100, Controls({"left", "r"}))
        self.assertEqual(player.x, PLAYER_HALF_WIDTH)
        self.assertGreaterEqual(player.x - PLAYER_HALF_WIDTH, 0)
        self.assertEqual(player.state, "RUN")

    def test_right_boundary_contains_full_frame(self):
        player = Player()
        player.update(100, Controls({"right"}))
        self.assertEqual(player.x, WIDTH - PLAYER_HALF_WIDTH)
        self.assertLessEqual(player.x + PLAYER_HALF_WIDTH, WIDTH)
        self.assertEqual(player.state, "WALK")

    def test_repeated_boundary_input_does_not_wrap(self):
        player, controls = Player(), Controls({"right", "r"})
        for _ in range(100):
            player.update(1, controls)
            self.assertLessEqual(player.x, WIDTH - PLAYER_HALF_WIDTH)
        self.assertEqual(player.x, WIDTH - PLAYER_HALF_WIDTH)

    def test_reverse_input_leaves_boundary(self):
        player = Player(x=PLAYER_HALF_WIDTH)
        player.update(0.1, Controls({"right"}))
        self.assertAlmostEqual(player.x, PLAYER_HALF_WIDTH + WALK_SPEED / 10)

    def test_zero_time_changes_state_without_moving(self):
        player = Player()
        player.update(0, Controls({"left", "r"}))
        self.assertEqual((player.x, player.state, player.facing), (WIDTH / 2, "RUN", -1))

    def test_animation_time_is_bounded_after_long_update(self):
        for state, (_, fps) in ANIMATIONS.items():
            held = set() if state == "IDLE" else {"right"}
            if state == "RUN":
                held.add("r")
            player = Player(state=state)
            player.update(10000.25, Controls(held))
            self.assertGreaterEqual(player.animation_time, 0)
            self.assertLess(player.animation_time, FRAME_COUNT / fps)
            self.assertIn(player.frame, range(FRAME_COUNT))
