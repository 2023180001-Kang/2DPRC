from math import ceil
import unittest

from game import Controls, Enemy, Player, Stage
from settings import PLAYER_BODY_HALF_WIDTH, RUN_SPEED, WALK_SPEED


class KillReversalTests(unittest.TestCase):
    def running_hit(self, direction=1, weapon=None, fps=60, speed=RUN_SPEED):
        enemy = Enemy(x=640 + direction * 100)
        player = Player(x=640, state="RUN", facing=direction, weapon=weapon,
                        horizontal_speed=direction * speed)
        key = "right" if direction > 0 else "left"
        controls = Controls(held={key, "lshift"}, attack_requested=True)
        player.update(1 / fps, controls, enemy)
        self.assertEqual(enemy.state, "DYING")
        return player, enemy, controls

    def test_turn_after_kill_and_body_contact_keeps_running_speed(self):
        for direction in (-1, 1):
            for weapon in (None, "dagger", "steel_pipe"):
                for fps in (30, 60, 144):
                    with self.subTest(direction=direction, weapon=weapon, fps=fps):
                        player, enemy, controls = self.running_hit(direction, weapon, fps)
                        stage = Stage([], enemy=enemy)
                        for _ in range(ceil(0.1 * fps)):
                            stage.update(1 / fps, player)
                            player.update(1 / fps, controls, enemy)
                        self.assertEqual(player.horizontal_speed, 0)
                        before = player.x
                        controls.held = {"left" if direction > 0 else "right", "lshift"}
                        stage.update(1 / fps, player)
                        player.update(1 / fps, controls, enemy)
                        self.assertEqual(player.horizontal_speed, -direction * RUN_SPEED)
                        self.assertGreater(-direction * (player.x - before), 0)

    def test_overlap_correction_does_not_erase_velocity_away_from_expanding_body(self):
        for side in (-1, 1):
            enemy = Enemy(x=640, state="DYING", animation_time=0.5)
            left, _, right, _ = enemy.collision_bounds
            edge = left - PLAYER_BODY_HALF_WIDTH if side < 0 else right + PLAYER_BODY_HALF_WIDTH
            player = Player(x=edge - side * 8, horizontal_speed=side * RUN_SPEED)
            key = "left" if side < 0 else "right"
            player.update(1 / 240, Controls({key, "rshift"}), enemy)
            self.assertEqual((player.horizontal_speed, player.state), (side * RUN_SPEED, "RUN"))
            self.assertGreaterEqual(side * (player.x - edge), 0)

    def test_immediate_reversal_preserves_partial_speed_without_boosting_to_max(self):
        for direction in (-1, 1):
            player, enemy, controls = self.running_hit(direction, speed=400)
            momentum = abs(player.horizontal_speed)
            controls.held = {"left" if direction > 0 else "right", "lshift"}
            player.update(0, controls, enemy)
            self.assertEqual(player.horizontal_speed, -direction * momentum)

    def test_shift_release_caps_the_reversal_at_walking_speed(self):
        player, enemy, controls = self.running_hit()
        controls.held = {"left"}
        player.update(1 / 60, controls, enemy)
        self.assertEqual(player.horizontal_speed, -WALK_SPEED)

    def test_fast_turn_is_consumed_and_does_not_change_later_normal_reversal(self):
        player, enemy, controls = self.running_hit()
        controls.held = {"left", "lshift"}
        player.update(0, controls, enemy)
        self.assertEqual(player.horizontal_speed, -RUN_SPEED)
        # Move clear before turning back toward the obstacle.
        player.x = 500
        controls.held = {"right", "lshift"}
        player.update(0.05, controls, enemy)
        self.assertAlmostEqual(player.horizontal_speed, -600)

    def test_expired_kill_momentum_does_not_restore_speed_later(self):
        player, enemy, controls = self.running_hit()
        player.update(0.6, controls, enemy)
        self.assertEqual(player.horizontal_speed, 0)
        controls.held = {"left", "lshift"}
        player.update(0.1, controls, enemy)
        self.assertAlmostEqual(player.horizontal_speed, -180)

    def test_focus_loss_discards_kill_momentum(self):
        player, enemy, controls = self.running_hit()
        controls.focused = False
        player.update(0, controls, enemy)
        controls.focused, controls.held = True, {"left", "rshift"}
        player.update(0.1, controls, enemy)
        self.assertAlmostEqual(player.horizontal_speed, -180)

    def test_missed_attack_keeps_normal_braking_on_reversal(self):
        player, enemy = Player(horizontal_speed=RUN_SPEED), Enemy(x=950)
        player.update(0, Controls({"right", "lshift"}, attack_requested=True), enemy)
        player.update(0.05, Controls({"left", "lshift"}), enemy)
        self.assertEqual((enemy.state, player.horizontal_speed), ("IDLE", 600))

    def test_stationary_kill_does_not_grant_free_running_speed(self):
        player, enemy = Player(), Enemy(x=710)
        player.update(0, Controls(attack_requested=True), enemy)
        self.assertEqual(enemy.state, "DYING")
        player.update(0.1, Controls({"left", "lshift"}), enemy)
        self.assertAlmostEqual(player.horizontal_speed, -180)
