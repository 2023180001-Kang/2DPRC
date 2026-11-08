from random import Random
import unittest

from game import Controls, Enemy, Player, Stage, spawn_enemies
from settings import (
    ARROW_X, ATTACK_DURATION, ENEMY_ATTACK_HIT_TIME, ENEMY_BODY_HALF_WIDTH,
    ENEMY_DEATH_DURATION, ENEMY_ENTRY_SPACING, FRAME_WIDTH, ENEMY_SCALE,
    PLAYER_BODY_HALF_WIDTH, RUN_SPEED, STAGE_BACKGROUNDS, STAGE_GROUND_Y, WIDTH,
)


class EnemyGroupTests(unittest.TestCase):
    def test_each_stage_spawns_three_per_edge_with_ground_spacing_and_inward_facing(self):
        for number in STAGE_BACKGROUNDS:
            for entry in (128, WIDTH / 2, WIDTH - 128):
                enemies = spawn_enemies(Random(1), spawn_x=entry, stage_number=number)
                self.assertEqual(len(enemies), 6)
                self.assertEqual(len({id(enemy) for enemy in enemies}), 6)
                for side in (-1, 1):
                    group = [enemy for enemy in enemies if (enemy.x < 0) == (side < 0)]
                    self.assertEqual(len(group), 3)
                    for index, enemy in enumerate(group):
                        edge_distance = FRAME_WIDTH * ENEMY_SCALE / 2 + index * ENEMY_ENTRY_SPACING
                        self.assertEqual(enemy.x, -edge_distance if side < 0 else WIDTH + edge_distance)
                        self.assertEqual((enemy.facing, enemy.foot_y), (-side, STAGE_GROUND_Y[number]))
                        self.assertTrue(enemy.relentless)

    def test_all_six_enemies_approach_and_attack_in_every_stage(self):
        for number in STAGE_BACKGROUNDS:
            for fps in (30, 60, 144):
                with self.subTest(stage=number, fps=fps):
                    stage = Stage([], number=number)
                    player = Player(hit_test_mode=True)
                    attacked = set()
                    for _ in range(16 * fps):
                        stage.update(1 / fps, player)
                        player.update(1 / fps, Controls(), stage.enemies)
                        for index, enemy in enumerate(stage.enemies):
                            if enemy.state == "ATTACK" and enemy.attack_hit:
                                attacked.add(index)
                                enemy.hit()  # Make room for the next attacker in each queue.
                    self.assertEqual(attacked, set(range(6)))
                    self.assertTrue(stage.cleared)
                    self.assertEqual(player.health, 100)
                    self.assertEqual(player.foot_y, STAGE_GROUND_Y[number])

    def test_far_targets_are_pursued_and_crossing_the_enemy_reverses_facing(self):
        for side in (-1, 1):
            enemy = spawn_enemies()[0 if side < 0 else 3]
            player = Player(x=WIDTH - 128 if side < 0 else 128)
            before = enemy.x
            enemy.update(0.5, player)
            self.assertEqual(enemy.state, "CHASE")
            self.assertGreater(-side * (enemy.x - before), 0)
            enemy.x = WIDTH / 2
            player.x = enemy.x + side * 300
            enemy.update(0.1, player)
            self.assertEqual(enemy.facing, side)

    def test_live_enemies_queue_without_stacking_even_on_long_steps(self):
        for fps in (2, 30, 144):
            stage, player = Stage([]), Player(hit_test_mode=True)
            for _ in range(12 * fps):
                stage.update(1 / fps, player)
                ordered = sorted(stage.enemies, key=lambda enemy: enemy.x)
                for left, right in zip(ordered, ordered[1:]):
                    self.assertGreaterEqual(right.x - left.x, 2 * ENEMY_BODY_HALF_WIDTH + 8 - 1e-7)

    def test_simultaneous_attackers_share_one_player_invulnerability_timer(self):
        enemies = [Enemy(x=576, facing=1, state="ATTACK"),
                   Enemy(x=704, facing=-1, state="ATTACK")]
        stage, player = Stage([], enemies=enemies), Player()
        stage.update(ENEMY_ATTACK_HIT_TIME, player)
        self.assertEqual(player.health, 90)
        self.assertTrue(all(enemy.attack_hit for enemy in enemies))
        stage.update(0.01, player)
        self.assertEqual(player.health, 90)

    def test_player_hits_nearest_forward_enemy_once_per_swing(self):
        enemies = [Enemy(x=735), Enemy(x=710), Enemy(x=576)]
        player = Player()
        controls = Controls(attack_requested=True)
        player.update(0, controls, enemies)
        self.assertEqual([enemy.state for enemy in enemies], ["IDLE", "DYING", "IDLE"])
        player.update(0.1, controls, enemies)
        self.assertEqual(sum(enemy.state == "DYING" for enemy in enemies), 1)
        player.update(ATTACK_DURATION, controls, enemies)
        controls.attack_requested = True
        player.facing = -1
        player.update(0, controls, enemies)
        self.assertEqual(enemies[2].state, "DYING")

    def test_multiple_bodies_block_both_directions_of_high_speed_motion(self):
        for side in (-1, 1):
            for fps in (2, 30, 144):
                enemies = [Enemy(x=x) for x in (340, 940)]
                player = Player(horizontal_speed=side * RUN_SPEED)
                controls = Controls(held={"right" if side > 0 else "left", "lshift"})
                for _ in range(fps):
                    player.update(1 / fps, controls, enemies)
                    self.assertGreaterEqual(player.x, 340 + ENEMY_BODY_HALF_WIDTH + PLAYER_BODY_HALF_WIDTH)
                    self.assertLessEqual(player.x, 940 - ENEMY_BODY_HALF_WIDTH - PLAYER_BODY_HALF_WIDTH)

    def test_support_on_one_corpse_survives_other_bodies_and_walking_off_falls(self):
        bodies = [Enemy(x=300, state="DEAD"), Enemy(x=900, state="DEAD")]
        player = Player(x=300, foot_y=180, support_y=180)
        player.update(0.1, Controls(), bodies)
        self.assertEqual((player.foot_y, player.support_y, player.grounded), (180, 180, True))
        player.update(0.8, Controls(held={"right"}), bodies)
        self.assertLess(player.foot_y, 180)
        player.update(0.2, Controls(), bodies)
        self.assertEqual((player.foot_y, player.support_y), (140, 140))

    def test_forward_gate_waits_for_all_six_full_death_animations(self):
        for number in STAGE_BACKGROUNDS:
            stage = Stage([], number=number)
            for enemy in stage.enemies[:-1]:
                enemy.hit()
            stage.update(ENEMY_DEATH_DURATION)
            self.assertNotIn(1, stage.visible_arrows)
            stage.enemies[-1].hit()
            stage.update(ENEMY_DEATH_DURATION - 0.001)
            self.assertFalse(stage.try_transition(Player(x=ARROW_X[1]), Controls()))
            stage.update(0.001)
            self.assertIn(1, stage.visible_arrows)
            self.assertEqual(stage.try_transition(Player(x=ARROW_X[1]), Controls()), number < 6)
            if number < 6:
                self.assertEqual(len(stage.enemies), 6)

    def test_all_campaign_lists_survive_round_trip_and_off_map_attack_pauses(self):
        stage, player, controls = Stage([]), Player(), Controls()
        saved = {}
        for number in STAGE_BACKGROUNDS:
            saved[number] = stage.enemies
            for enemy in stage.enemies:
                enemy.hit()
            stage.update(ENEMY_DEATH_DURATION)
            if number < 6:
                player.x = ARROW_X[1]
                self.assertTrue(stage.try_transition(player, controls))
        saved[6][0].state, saved[6][0].animation_time = "ATTACK", 0.1
        for number in range(5, 0, -1):
            player.x = ARROW_X[-1]
            self.assertTrue(stage.try_transition(player, controls))
            self.assertIs(stage.enemies, saved[number])
            stage.update(1)
        self.assertEqual(saved[6][0].animation_time, 0.1)
        for number in range(2, 7):
            player.x = ARROW_X[1]
            self.assertTrue(stage.try_transition(player, controls))
            self.assertIs(stage.enemies, saved[number])
        self.assertEqual(stage.enemies[0].animation_time, 0.1)

    def test_player_death_stops_all_attacks_without_teleporting_offscreen_enemies(self):
        stage, player = Stage([]), Player(health=0)
        before = [enemy.x for enemy in stage.enemies]
        stage.update(0.1, player)
        self.assertEqual([enemy.x for enemy in stage.enemies], before)
        self.assertTrue(all(enemy.state == "IDLE" for enemy in stage.enemies))


if __name__ == "__main__":
    unittest.main()
