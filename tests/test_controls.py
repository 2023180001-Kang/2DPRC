import itertools
import unittest

from game import Controls, Player
from settings import ANIMATIONS, WALK_SPEED


class InputTests(unittest.TestCase):
    def test_initial_idle(self):
        player = Player()
        self.assertEqual((player.state, player.facing, player.frame), ("IDLE", 1, 0))

    def test_every_key_combination(self):
        for left, right, lshift, rshift in itertools.product((False, True), repeat=4):
            with self.subTest(left=left, right=right, lshift=lshift, rshift=rshift):
                controls = Controls()
                for key, down in (("left", left), ("right", right),
                                  ("lshift", lshift), ("rshift", rshift)):
                    controls.set_key(key, down)
                direction = int(right) - int(left)
                run = lshift or rshift
                state = ("RUN" if run else "WALK") if direction else "IDLE"
                player = Player()
                player.update(0, controls)
                self.assertEqual(controls.direction, direction)
                self.assertIs(controls.running, run)
                self.assertEqual(player.state, state)

    def test_repeated_key_down_is_idempotent(self):
        for key in ("right", "lshift", "rshift"):
            with self.subTest(key=key):
                controls = Controls()
                for _ in range(100):
                    controls.set_key(key, True)
                self.assertEqual(controls.held, {key})
                self.assertEqual(controls.direction, int(key == "right"))
                self.assertIs(controls.running, key != "right")
                controls.set_key(key, False)
                controls.set_key(key, False)
                self.assertEqual(controls.held, set())
                self.assertIs(controls.running, False)

    def test_release_missing_key_is_safe(self):
        controls = Controls()
        controls.set_key("left", False)
        self.assertEqual(controls.held, set())

    def test_unsupported_keys_are_ignored(self):
        controls = Controls()
        for key in ("up", "down", "z", "r", None):
            controls.set_key(key, True)
        self.assertEqual(controls.held, set())

    def test_keys_are_rejected_without_focus(self):
        controls = Controls(focused=False)
        for key in ("right", "lshift", "rshift"):
            controls.set_key(key, True)
        self.assertEqual(controls.direction, 0)
        self.assertFalse(controls.held)
        self.assertIs(controls.running, False)

    def test_run_key_order_does_not_matter(self):
        for shift, direction in itertools.product(("lshift", "rshift"), ("left", "right")):
            for keys in ((shift, direction), (direction, shift)):
                with self.subTest(keys=keys):
                    controls, player = Controls(), Player()
                    for key in keys:
                        controls.set_key(key, True)
                        player.update(0, controls)
                    self.assertEqual(player.state, "RUN")

    def test_releasing_run_returns_to_walk(self):
        for shift in ("lshift", "rshift"):
            with self.subTest(shift=shift):
                controls, player = Controls({"right", shift}), Player()
                player.update(0, controls)
                controls.set_key(shift, False)
                player.update(0, controls)
                self.assertIs(controls.running, False)
                self.assertEqual((player.state, player.facing), ("WALK", 1))

    def test_both_shifts_run_until_last_release_in_either_order(self):
        for first, last in (("lshift", "rshift"), ("rshift", "lshift")):
            with self.subTest(first=first):
                controls, player = Controls({"right", first, last}), Player()
                player.update(0, controls)
                self.assertEqual(player.state, "RUN")
                controls.set_key(first, False)
                player.update(0, controls)
                self.assertIs(controls.running, True)
                self.assertEqual((player.state, player.facing), ("RUN", 1))
                controls.set_key(last, False)
                player.update(0, controls)
                self.assertIs(controls.running, False)
                self.assertEqual((player.state, player.facing), ("WALK", 1))

    def test_r_is_ignored_with_and_without_direction(self):
        for held in (set(), {"right"}):
            with self.subTest(held=held):
                controls, player = Controls(held.copy()), Player()
                controls.set_key("r", True)
                player.update(0, controls)
                self.assertEqual(controls.held, held)
                self.assertIs(controls.running, False)
                self.assertEqual(player.state, "WALK" if held else "IDLE")
                controls.set_key("r", False)
                self.assertEqual(controls.held, held)

    def test_releasing_direction_returns_to_idle(self):
        controls, player = Controls({"left", "lshift"}), Player()
        player.update(0, controls)
        controls.set_key("left", False)
        player.update(0, controls)
        self.assertEqual((player.state, player.facing), ("IDLE", -1))

    def test_opposed_directions_preserve_facing(self):
        controls, player = Controls({"left"}), Player()
        player.update(0, controls)
        controls.set_key("right", True)
        player.update(0, controls)
        self.assertEqual((player.state, player.facing), ("IDLE", -1))

    def test_releasing_one_direction_resumes_remaining_input(self):
        controls, player = Controls({"left", "right", "rshift"}), Player()
        player.update(0, controls)
        controls.set_key("left", False)
        player.update(0, controls)
        self.assertEqual((player.state, player.facing), ("RUN", 1))

    def test_state_change_resets_animation(self):
        controls, player = Controls(), Player()
        player.update(0.5, controls)
        self.assertEqual(player.frame, 3)
        controls.set_key("right", True)
        player.update(0.1, controls)
        self.assertEqual((player.state, player.frame, player.animation_time), ("WALK", 0, 0))

    def test_unchanged_state_does_not_reset_animation(self):
        controls, player = Controls({"right"}), Player(horizontal_speed=WALK_SPEED)
        player.update(0, controls)
        player.update(0.25, controls)
        self.assertEqual(player.frame, 2)

    def test_direction_change_keeps_same_state_animation(self):
        controls, player = Controls({"right"}), Player(horizontal_speed=WALK_SPEED)
        player.update(0, controls)
        player.update(0.25, controls)
        controls.held = {"left"}
        player.update(0, controls)
        self.assertEqual((player.state, player.frame, player.facing), ("WALK", 2, -1))

    def test_animation_rows_and_rates(self):
        for state, (row, fps) in ANIMATIONS.items():
            with self.subTest(state=state):
                player = Player(state=state, animation_time=3 / fps)
                self.assertEqual((player.row, player.frame), (row, 3))


if __name__ == "__main__":
    unittest.main()
