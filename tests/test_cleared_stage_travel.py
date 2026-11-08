from random import Random
import unittest
from unittest.mock import patch

from game import Controls, Enemy, Player, Stage, spawn_enemies
from settings import (
    ARROW_X, CORPSE_HEIGHT, ENEMY_DEATH_DURATION, RUN_SPEED, STAGE_BACKGROUNDS,
    STAGE_ENTRY_LEFT_X, STAGE_ENTRY_RIGHT_X, STAGE_GROUND_Y,
)


class ClearedStageTravelTests(unittest.TestCase):
    def walk_to_exit(self, stage, player, direction, fps, running):
        controls = Controls(held={"right" if direction > 0 else "left"}
                            | ({"lshift"} if running else set()))
        for _ in range(fps * 2):
            stage.update(1 / fps, player)
            player.update(1 / fps, controls, stage.collision_enemies)
            if stage.try_transition(player, controls):
                return True
        return False

    def test_reenter_partial_next_map_by_walking_past_cleared_exit_bodies(self):
        for number in range(1, 6):
            for fps in (30, 60, 144):
                for running in (False, True):
                    with self.subTest(stage=number, fps=fps, running=running):
                        ground = STAGE_GROUND_Y[number]
                        bodies = [Enemy(x=1200, foot_y=ground, state="DEAD") for _ in range(6)]
                        stage = Stage([], number=number, enemies=bodies)
                        player = Player(x=ARROW_X[1], health=70, weapon="dagger")
                        controls = Controls()
                        self.assertTrue(stage.try_transition(player, controls, Random(1)))
                        remaining = stage.enemies
                        remaining[0].hit()
                        stage.update(ENEMY_DEATH_DURATION)
                        snapshot = [vars(enemy).copy() for enemy in remaining]
                        self.assertEqual(sum(enemy.alive for enemy in remaining), 5)
                        self.assertFalse(stage.cleared)
                        self.assertNotIn(1, stage.visible_arrows)
                        player.x = ARROW_X[-1]
                        self.assertTrue(stage.try_transition(player, controls))
                        self.assertEqual(player.x, STAGE_ENTRY_RIGHT_X)
                        self.assertIn(number, stage.cleared_stages)
                        self.assertIs(stage.enemies, bodies)
                        with patch("game.spawn_enemies", wraps=spawn_enemies) as spawns:
                            self.assertTrue(self.walk_to_exit(stage, player, 1, fps, running))
                            spawns.assert_not_called()
                        self.assertEqual(stage.number, number + 1)
                        self.assertIs(stage.enemies, remaining)
                        self.assertEqual([vars(enemy) for enemy in remaining], snapshot)
                        self.assertEqual((player.health, player.weapon), (70, "dagger"))
                        self.assertNotIn(1, stage.visible_arrows)
                        self.assertEqual(player.foot_y, STAGE_GROUND_Y[number + 1])

    def test_cleared_map_left_exit_is_walkable_even_with_bodies_at_the_edge(self):
        for number in range(2, 7):
            ground = STAGE_GROUND_Y[number]
            stage = Stage([], number=number, enemies=[Enemy(x=80, foot_y=ground, state="DEAD") for _ in range(6)])
            player = Player(x=STAGE_ENTRY_LEFT_X)
            player.set_ground_y(ground)
            self.assertTrue(self.walk_to_exit(stage, player, -1, 60, False))
            self.assertEqual(stage.number, number - 1)
            self.assertIn(number, stage.cleared_stages)

    def test_uncleared_map_keeps_live_and_dead_body_collisions_and_forward_lock(self):
        bodies = [Enemy(x=600, state="DEAD")] + [Enemy(x=1000 + index * 20) for index in range(5)]
        stage = Stage([], enemies=bodies)
        self.assertIs(stage.collision_enemies, bodies)
        player = Player(x=400, horizontal_speed=RUN_SPEED)
        player.update(0.5, Controls(held={"right", "lshift"}), stage.collision_enemies)
        self.assertEqual(player.x, 506)
        player.x = ARROW_X[1]
        self.assertFalse(stage.try_transition(player, Controls()))
        self.assertNotIn(1, stage.cleared_stages)

    def test_last_dying_enemy_keeps_collisions_until_full_animation_completes(self):
        stage = Stage([], enemies=[Enemy(state="DEAD") for _ in range(5)] + [Enemy()])
        stage.enemies[-1].hit()
        stage.update(ENEMY_DEATH_DURATION - 0.001)
        self.assertTrue(stage.collision_enemies)
        self.assertEqual(stage.cleared_stages, set())
        stage.update(0.001)
        self.assertEqual(stage.collision_enemies, ())
        self.assertEqual(stage.cleared_stages, {1})
        self.assertEqual(len(stage.enemies), 6)

    def test_clear_removes_corpse_support_without_leaving_player_floating(self):
        for number in STAGE_BACKGROUNDS:
            ground = STAGE_GROUND_Y[number]
            stage = Stage([], number=number,
                          enemies=[Enemy(x=640, foot_y=ground, state="DEAD") for _ in range(6)])
            player = Player(ground_y=ground, foot_y=ground + CORPSE_HEIGHT,
                            support_y=ground + CORPSE_HEIGHT)
            player.update(0, Controls(), stage.collision_enemies)
            self.assertEqual(player.support_y, ground)
            self.assertEqual(player.jump_count, 1)
            self.assertFalse(player.grounded)
            player.update(0.5, Controls(), stage.collision_enemies)
            self.assertEqual((player.foot_y, player.jump_count), (ground, 0))

    def test_clear_history_is_kept_across_maps_and_new_game_has_no_clears(self):
        stage, player = Stage([], enemies=[Enemy(state="DEAD") for _ in range(6)]), Player(x=ARROW_X[1])
        stage.try_transition(player, Controls())
        self.assertEqual(stage.cleared_stages, {1})
        for enemy in stage.enemies:
            enemy.hit()
        stage.update(ENEMY_DEATH_DURATION)
        self.assertEqual(stage.cleared_stages, {1, 2})
        player.x = ARROW_X[-1]
        stage.try_transition(player, Controls())
        self.assertTrue(stage.cleared)
        self.assertEqual(stage.cleared_stages, {1, 2})
        fresh = Stage([])
        self.assertEqual(fresh.cleared_stages, set())
        self.assertNotIn(1, fresh.visible_arrows)


if __name__ == "__main__":
    unittest.main()
