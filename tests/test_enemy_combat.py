import unittest
from unittest.mock import Mock, patch

from game import Controls, Enemy, Player, Stage
from rendering import draw_enemy
from settings import (
    ARROW_X, ENEMY_ATTACK_COOLDOWN, ENEMY_ATTACK_DURATION, ENEMY_ATTACK_FPS,
    ENEMY_ATTACK_HIT_TIME, GROUND_Y, PLAYER_HURT_INVULNERABILITY,
)


class EnemyCombatTests(unittest.TestCase):
    def test_attack_start_distance_height_and_facing_boundaries(self):
        for direction in (-1, 1):
            for distance, height, attacks in ((90, 80, True), (90.001, 0, False),
                                               (60, 80.001, False), (64, 0, True)):
                with self.subTest(direction=direction, distance=distance, height=height):
                    enemy = Enemy(x=640, facing=-direction)
                    player = Player(x=640 + direction * distance, foot_y=GROUND_Y + height)
                    enemy.update(0, player)
                    self.assertEqual(enemy.state == "ATTACK", attacks)
                    if attacks:
                        self.assertEqual((enemy.facing, enemy.frame, enemy.row), (direction, 0, 2))
                    self.assertEqual(player.health, 100)

    def test_attack_plays_eight_frames_and_hits_only_at_fifth_frame(self):
        enemy, player = Enemy(x=640), Player(x=704)
        enemy.update(0, player)
        for frame in range(8):
            self.assertEqual((enemy.state, enemy.row, enemy.frame), ("ATTACK", 2, frame))
            self.assertEqual(player.health, 100 if frame < 4 else 90)
            enemy.update(1 / ENEMY_ATTACK_FPS, player)
        self.assertEqual(enemy.state, "IDLE")
        self.assertAlmostEqual(enemy.attack_cooldown, ENEMY_ATTACK_COOLDOWN)

    def test_attack_hit_time_is_consistent_at_low_and_high_fps(self):
        for fps in (3, 12, 30, 60, 144):
            enemy, player = Enemy(x=640), Player(x=704)
            stage = Stage([], enemy=enemy)
            stage.update(0, player)
            elapsed = 0
            while elapsed < 0.6 - 1e-9:
                stage.update(1 / fps, player)
                elapsed += 1 / fps
                self.assertEqual(player.health, 90 if elapsed >= ENEMY_ATTACK_HIT_TIME - 1e-9 else 100)

    def test_long_frame_crossing_hit_and_end_damages_only_once(self):
        enemy, player = Enemy(x=640), Player(x=704)
        enemy.update(0, player)
        enemy.update(10, player)
        self.assertEqual((player.health, enemy.state), (90, "IDLE"))
        self.assertAlmostEqual(enemy.attack_cooldown, 0.6)

    def test_attack_freezes_x_and_facing_when_target_moves_behind(self):
        enemy, player = Enemy(x=640), Player(x=704)
        enemy.update(0, player)
        player.x = 576
        enemy.update(ENEMY_ATTACK_HIT_TIME, player)
        self.assertEqual((enemy.x, enemy.facing, enemy.state, player.health), (640, 1, "ATTACK", 100))

    def test_hit_rechecks_forward_distance_and_height_with_boundaries(self):
        for direction in (-1, 1):
            for distance, height, hits in ((100, 80, True), (100.001, 0, False),
                                           (64, 80.001, False), (-1, 0, False)):
                enemy, player = Enemy(x=640), Player(x=640 + direction * 64)
                enemy.update(0, player)
                player.x, player.foot_y = 640 + direction * distance, GROUND_Y + height
                enemy.update(ENEMY_ATTACK_HIT_TIME, player)
                self.assertEqual(player.health, 90 if hits else 100)

    def test_missed_strike_is_spent_even_if_player_returns_later(self):
        enemy, player = Enemy(x=640), Player(x=704)
        enemy.update(0, player)
        player.x = 800
        enemy.update(ENEMY_ATTACK_HIT_TIME, player)
        player.x = 704
        enemy.update(0.1, player)
        self.assertEqual(player.health, 100)
        self.assertTrue(enemy.attack_hit)

    def test_damage_invulnerability_and_zero_health_floor(self):
        player = Player()
        self.assertTrue(player.take_damage())
        self.assertEqual(player.health, 99)
        self.assertFalse(player.take_damage())
        player.update_damage(PLAYER_HURT_INVULNERABILITY - 0.001)
        self.assertFalse(player.take_damage())
        player.update_damage(0.001)
        self.assertTrue(player.take_damage())
        player.update_damage(1)
        self.assertTrue(player.take_damage(1000))
        self.assertEqual(player.health, 0)
        self.assertFalse(player.take_damage())
        self.assertFalse(Player().take_damage(0))

    def test_invulnerable_strike_cannot_damage_later_in_same_attack(self):
        enemy, player = Enemy(x=640), Player(x=704, hurt_time=0.5)
        enemy.update(0, player)
        enemy.update(ENEMY_ATTACK_HIT_TIME, player)
        player.update_damage(1)
        enemy.update(0.1, player)
        self.assertEqual(player.health, 100)

    def test_attack_cooldown_prevents_restart_then_allows_next_attack(self):
        enemy, player = Enemy(x=640), Player(x=704)
        stage = Stage([], enemy=enemy)
        stage.update(0, player)
        stage.update(ENEMY_ATTACK_DURATION, player)
        stage.update(ENEMY_ATTACK_COOLDOWN - 0.001, player)
        self.assertEqual(enemy.state, "IDLE")
        stage.update(0.001, player)
        self.assertEqual((enemy.state, enemy.frame), ("ATTACK", 0))
        stage.update(ENEMY_ATTACK_HIT_TIME, player)
        self.assertEqual(player.health, 80)

    def test_cooldown_allows_following_player_out_of_melee_range(self):
        enemy = Enemy(x=640, attack_cooldown=0.5)
        enemy.update(0.1, Player(x=840))
        self.assertEqual((enemy.state, enemy.x), ("CHASE", 652))
        self.assertAlmostEqual(enemy.attack_cooldown, 0.4)

    def test_counterattack_kills_attacking_enemy_and_cancels_pending_damage(self):
        for weapon in (None, "dagger", "steel_pipe"):
            enemy, player = Enemy(x=704), Player(x=640, weapon=weapon)
            enemy.update(0, player)
            enemy.update(ENEMY_ATTACK_HIT_TIME - 0.001, player)
            player.update(0, Controls(attack_requested=True), enemy)
            self.assertEqual(enemy.state, "DYING")
            enemy.update(1, player)
            self.assertEqual((enemy.state, player.health), ("DEAD", 100))

    def test_dead_and_dying_enemies_never_attack(self):
        for state in ("DYING", "DEAD"):
            enemy, player = Enemy(x=640, state=state), Player(x=704)
            enemy.update(10, player)
            self.assertEqual((enemy.state, player.health), ("DEAD", 100))

    def test_zero_health_target_does_not_trigger_new_attack(self):
        enemy = Enemy(x=640)
        enemy.update(1, Player(x=704, health=0))
        self.assertNotEqual(enemy.state, "ATTACK")
        self.assertLess(enemy.x, 640)  # Make room for the falling body.
        enemy.update(1, Player(x=704, health=0))
        self.assertEqual((enemy.state, enemy.aware), ("IDLE", False))

    def test_attack_keeps_exit_locked_and_uses_upright_body_bounds(self):
        stage = Stage([], enemy=Enemy(x=640, state="ATTACK", animation_time=0.5))
        self.assertEqual(stage.visible_arrows, ())
        self.assertEqual(stage.enemy.collision_bounds, (608, GROUND_Y, 672, GROUND_Y + 136))

    def test_renderer_uses_attack_row_all_frames_and_both_facings(self):
        for direction in (-1, 1):
            for frame in range(8):
                image = Mock(h=1024)
                draw_enemy(image, Enemy(state="ATTACK", facing=direction,
                                       animation_time=frame / ENEMY_ATTACK_FPS))
                args = image.clip_composite_draw.call_args.args
                self.assertEqual(args[:4], (frame * 256, 256, 256, 256))
                self.assertEqual(args[5], "h" if direction < 0 else "")

    def test_off_map_attack_pauses_then_resumes_and_health_persists(self):
        second = Enemy(x=192)
        stage = Stage([], enemy=Enemy(state="DEAD"))
        player, controls = Player(x=ARROW_X[1]), Controls()
        with patch("game.spawn_enemies", return_value=[second]):
            stage.try_transition(player, controls)
        stage.update(0, player)
        stage.update(ENEMY_ATTACK_HIT_TIME / 2, player)
        player.x = ARROW_X[-1]
        stage.try_transition(player, controls)
        before = vars(second).copy()
        stage.update(5, player)
        self.assertEqual(vars(second), before)
        player.x = ARROW_X[1]
        stage.try_transition(player, controls)
        stage.update(ENEMY_ATTACK_HIT_TIME / 2, player)
        self.assertEqual(player.health, 90)
        player.x = ARROW_X[-1]
        immunity = player.hurt_time
        stage.try_transition(player, controls)
        self.assertEqual((player.health, player.hurt_time), (90, immunity))

    def test_three_melee_hits_leave_seventy_hp_and_tenth_hit_is_lethal(self):
        for direction in (-1, 1):
            player = Player(x=640)
            stage = Stage([], enemy=Enemy(x=640 + direction * 64))
            previous_health = player.health
            hits = 0
            for _ in range(900):
                stage.update(1 / 60, player)
                player.update(1 / 60, Controls(), stage.enemy)
                if player.health != previous_health:
                    hits += 1
                    self.assertEqual(player.health, 100 - hits * 10)
                    if hits == 3:
                        self.assertEqual(player.health, 70)
                        self.assertFalse(player.incapacitated)
                    previous_health = player.health
                if player.incapacitated:
                    break
            self.assertEqual((hits, player.health, player.state), (10, 0, "DYING"))
