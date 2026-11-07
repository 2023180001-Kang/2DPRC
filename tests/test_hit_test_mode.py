import unittest

from game import Controls, Enemy, Player, Stage
from rendering import camera_offset
from settings import PLAYER_HURT_INVULNERABILITY


class HitTestModeTests(unittest.TestCase):
    def test_repeated_enemy_hits_keep_low_hp_and_replay_feedback_then_off_restores_death(self):
        for side in (-1, 1):
            player = Player(health=10, hit_test_mode=True)
            stage = Stage([], enemy=Enemy(x=640 + side * 64))
            hits = 0
            for _ in range(1000):
                before = player.hit_feedback_time
                stage.update(1 / 60, player)
                player.update(1 / 60, Controls(), stage.enemy)
                self.assertEqual(player.health, 10)
                self.assertFalse(player.incapacitated)
                if before <= 1e-9 and player.hit_feedback_time > 1e-9:
                    hits += 1
                    self.assertNotEqual(camera_offset(player), (0, 0))
                if hits == 12:
                    break
            self.assertEqual(hits, 12)
            self.assertTrue(stage.enemy.alive)
            player.hit_test_mode = False
            for _ in range(120):
                stage.update(1 / 60, player)
                if player.incapacitated:
                    break
            self.assertEqual((player.health, player.state), (0, "DYING"))

    def test_test_mode_preserves_normal_hurt_cooldown_and_invalid_hit_rules(self):
        player = Player(health=37, hit_test_mode=True)
        self.assertFalse(player.take_damage(0))
        self.assertEqual(player.hit_feedback_time, 0)
        self.assertTrue(player.take_damage(1000))
        self.assertEqual(player.health, 37)
        player.update_damage(0.1)
        remaining = player.hit_feedback_time
        self.assertFalse(player.take_damage(10))
        self.assertEqual(player.hit_feedback_time, remaining)
        player.update_damage(PLAYER_HURT_INVULNERABILITY)
        self.assertTrue(player.take_damage(10))
        self.assertEqual(player.health, 37)
        self.assertFalse(Player(health=0, hit_test_mode=True).take_damage(10))
