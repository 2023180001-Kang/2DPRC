import unittest
from unittest.mock import Mock, patch

from game import Controls, Enemy, Player, Stage
from rendering import draw_enemy
from settings import (
    ARROW_X, ENEMY_BODY_HALF_WIDTH, ENEMY_CHASE_FPS, ENEMY_DEATH_DURATION,
    ENEMY_DETECTION_RANGE, ENEMY_LOSE_RANGE, ENEMY_STOP_DISTANCE, GROUND_Y,
    PLAYER_BODY_HALF_WIDTH, RUN_SPEED,
)


class EnemyAITests(unittest.TestCase):
    def test_detection_boundary_in_both_directions_including_behind_and_airborne(self):
        for facing in (-1, 1):
            for height in (0, 384):
                for distance, detected in ((420, True), (420.001, False)):
                    with self.subTest(facing=facing, height=height, distance=distance):
                        enemy = Enemy(x=640, facing=-facing)
                        player = Player(x=640 + facing * distance, foot_y=GROUND_Y + height)
                        enemy.update(0.1, player)
                        self.assertEqual(enemy.aware, detected)
                        self.assertEqual(enemy.state, "CHASE" if detected else "IDLE")
                        self.assertAlmostEqual(enemy.x, 640 + (facing * 12 if detected else 0))
                        self.assertEqual(enemy.foot_y, GROUND_Y)
                        if detected:
                            self.assertEqual(enemy.facing, facing)

    def test_detection_hysteresis_loss_and_reacquisition(self):
        enemy, player = Enemy(x=640), Player(x=1060)
        enemy.update(0, player)
        self.assertTrue(enemy.aware)
        for distance in (ENEMY_DETECTION_RANGE + 1, ENEMY_LOSE_RANGE):
            player.x = enemy.x - distance
            enemy.update(0, player)
            self.assertTrue(enemy.aware)
            self.assertEqual((enemy.state, enemy.facing), ("CHASE", -1))
        player.x = enemy.x - ENEMY_LOSE_RANGE - 0.001
        enemy.update(0.1, player)
        self.assertEqual((enemy.aware, enemy.state, enemy.x), (False, "IDLE", 640))
        player.x = enemy.x - 500
        enemy.update(0.1, player)
        self.assertFalse(enemy.aware)
        player.x = enemy.x - 420
        enemy.update(0.1, player)
        self.assertEqual((enemy.aware, enemy.state, enemy.x), (True, "CHASE", 628))

    def test_chase_speed_is_time_based_in_both_directions(self):
        for direction in (-1, 1):
            for steps in (1, 2, 30, 60, 144, 1000):
                enemy, player = Enemy(x=640), Player(x=640 + direction * 400)
                for _ in range(steps):
                    enemy.update(1 / steps, player)
                self.assertAlmostEqual(enemy.x, 640 + direction * 120)
                self.assertEqual((enemy.state, enemy.row), ("CHASE", 1))

    def test_arrival_stops_without_crossing_or_pushing_player_even_with_long_frames(self):
        for direction in (-1, 1):
            for dt in (0.5, 10, 100):
                enemy, player = Enemy(x=640), Player(x=640 + direction * 100)
                before = vars(player).copy()
                enemy.update(dt, player)
                self.assertAlmostEqual(abs(enemy.x - player.x), 64)
                self.assertEqual((enemy.state, enemy.aware), ("IDLE", True))
                self.assertEqual(vars(player), before)
                x = enemy.x
                enemy.update(100, player)
                self.assertEqual(enemy.x, x)

    def test_contact_and_equal_x_do_not_push_either_body_away(self):
        for distance in (0, 56, ENEMY_STOP_DISTANCE):
            enemy, player = Enemy(x=640, attack_cooldown=1000), Player(x=640 + distance)
            enemy.update(1, player)
            self.assertEqual((enemy.x, player.x, enemy.state), (640, 640 + distance, "IDLE"))

    def test_moving_away_resumes_chase_and_crossing_over_reverses_facing(self):
        enemy, player = Enemy(x=640, attack_cooldown=1000), Player(x=704)
        enemy.update(0.1, player)
        self.assertEqual(enemy.state, "IDLE")
        player.x = 804
        enemy.update(0.1, player)
        self.assertEqual((enemy.x, enemy.facing, enemy.state), (652, 1, "CHASE"))
        player.x, player.foot_y = 452, GROUND_Y + 300
        enemy.update(0.1, player)
        self.assertEqual((enemy.x, enemy.facing, enemy.state, enemy.foot_y), (640, -1, "CHASE", GROUND_Y))

    def test_chase_remains_inside_full_sprite_screen_bounds(self):
        for enemy_x, target_x, edge in ((80, -100, 76.8), (1200, 1380, 1203.2)):
            enemy = Enemy(x=enemy_x)
            enemy.update(10, Player(x=target_x))
            self.assertAlmostEqual(enemy.x, edge)
            self.assertEqual(enemy.state, "IDLE")

    def test_chase_animation_loops_all_frames_then_idle_animation_continues(self):
        enemy, player = Enemy(x=400, attack_cooldown=1000), Player(x=800)
        enemy.update(0, player)
        frames = set()
        for _ in range(8):
            frames.add(enemy.frame)
            self.assertEqual(enemy.row, 1)
            enemy.update(1 / ENEMY_CHASE_FPS, player)
        self.assertEqual(frames, set(range(8)))
        enemy.update(10, player)
        self.assertEqual((enemy.state, enemy.row, enemy.frame), ("IDLE", 0, 0))
        enemy.update(1 / 6, player)
        self.assertEqual(enemy.frame, 1)

    def test_renderer_uses_walk_row_and_facing_for_chase(self):
        for facing in (-1, 1):
            image = Mock(h=1024)
            enemy = Enemy(state="CHASE", animation_time=0.375, facing=facing)
            draw_enemy(image, enemy)
            args = image.clip_composite_draw.call_args.args
            self.assertEqual(args[:4], (3 * 256, 512, 256, 256))
            self.assertEqual(args[5], "h" if facing < 0 else "")

    def test_live_enemy_can_be_killed_by_each_weapon_and_stays_in_place(self):
        for weapon in (None, "dagger", "steel_pipe"):
            for facing in (-1, 1):
                enemy = Enemy(x=640 + facing * 85)
                player = Player(x=640, facing=facing, weapon=weapon)
                stage = Stage([], enemy=enemy)
                stage.update(0.1, player)
                self.assertEqual(enemy.state, "ATTACK")
                player.update(0, Controls(attack_requested=True), enemy)
                self.assertEqual((enemy.state, enemy.aware), ("DYING", False))
                x = enemy.x
                stage.update(ENEMY_DEATH_DURATION - 0.001, Player(x=300))
                self.assertEqual((enemy.x, stage.visible_arrows), (x, ()))
                stage.update(0.001, player)
                self.assertEqual((enemy.state, enemy.x, stage.visible_arrows), ("DEAD", x, (1,)))
                stage.update(10, player)
                self.assertEqual(enemy.x, x)

    def test_dynamic_chase_and_player_run_do_not_overlap_on_the_ground(self):
        for direction in (-1, 1):
            for fps in (2, 30, 60, 144):
                enemy = Enemy(x=640 + direction * 300, attack_cooldown=1000)
                player = Player(x=640, horizontal_speed=direction * RUN_SPEED)
                stage = Stage([], enemy=enemy)
                controls = Controls(held={"right" if direction > 0 else "left", "lshift"})
                for _ in range(fps * 2):
                    stage.update(1 / fps, player)
                    player.update(1 / fps, controls, enemy)
                    self.assertGreaterEqual(direction * (enemy.x - player.x),
                                            ENEMY_BODY_HALF_WIDTH + PLAYER_BODY_HALF_WIDTH - 1e-7)
                    self.assertEqual(player.health, 100)
                self.assertEqual(player.state, "IDLE")

    def test_contact_during_cooldown_has_no_passive_damage(self):
        enemy, player = Enemy(x=700, attack_cooldown=1000), Player(x=640)
        for _ in range(600):
            enemy.update(1 / 60, player)
            self.assertEqual((enemy.state, enemy.row, player.health), ("IDLE", 0, 100))

    def test_only_current_map_chases_and_round_trip_preserves_enemy_state(self):
        first = Enemy(x=800, state="DEAD")
        second = Enemy(x=400)
        stage, controls = Stage([], enemy=first), Controls()
        player = Player(x=ARROW_X[1])
        with patch("game.spawn_enemies", return_value=[second]) as spawn:
            self.assertTrue(stage.try_transition(player, controls))
            stage.update(0.2, player)
            self.assertTrue(second.aware)
            self.assertEqual(second.state, "CHASE")
            player.x = ARROW_X[-1]
            self.assertTrue(stage.try_transition(player, controls))
            before = vars(second).copy()
            stage.update(5, player)
            self.assertEqual(vars(second), before)
            player.x = ARROW_X[1]
            self.assertTrue(stage.try_transition(player, controls))
            self.assertIs(stage.enemy, second)
            self.assertEqual(vars(second), before)
            stage.update(0.1, player)
            self.assertNotEqual(second.x, before["x"])
            spawn.assert_called_once()

    def test_stage_without_target_keeps_idle_animation_compatible(self):
        stage = Stage([], enemy=Enemy(x=400))
        stage.update(0.5)
        self.assertEqual((stage.enemy.x, stage.enemy.state, stage.enemy.frame), (400, "IDLE", 3))
