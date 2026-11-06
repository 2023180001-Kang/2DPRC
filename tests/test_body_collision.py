from random import Random
import unittest

from game import Controls, Enemy, Player, Stage
from settings import (
    ARROW_X, CORPSE_HALF_WIDTH, CORPSE_HEIGHT, ENEMY_BODY_HALF_WIDTH, GROUND_Y,
    JUMP_SPEED, PLAYER_BODY_HALF_WIDTH, RUN_SPEED, STAGE_ENTRY_LEFT_X,
)


class BodyCollisionTests(unittest.TestCase):
    def test_live_enemy_blocks_both_sides_and_does_not_move_or_damage_player(self):
        for side, key in ((-1, "right"), (1, "left")):
            enemy = Enemy(x=640)
            player = Player(x=640 + side * 200, horizontal_speed=-side * RUN_SPEED)
            controls = Controls({key, "lshift"})
            for _ in range(5):
                player.update(0.5, controls, enemy)
                self.assertEqual(player.x, 640 + side * (ENEMY_BODY_HALF_WIDTH + PLAYER_BODY_HALF_WIDTH))
                self.assertEqual(player.horizontal_speed, 0)
            self.assertEqual((enemy.x, enemy.state, player.health), (640, "IDLE", 3))

    def test_live_and_dying_enemies_cannot_be_bypassed_by_a_high_jump(self):
        for state in ("IDLE", "DYING"):
            enemy = Enemy(x=640, state=state, animation_time=0.5)
            player = Player(x=440, foot_y=GROUND_Y + 350, vertical_speed=100,
                            state="JUMP", jump_count=2, horizontal_speed=RUN_SPEED)
            player.update(0.4, Controls({"right", "rshift"}), enemy)
            self.assertAlmostEqual(player.x, enemy.collision_bounds[0] - PLAYER_BODY_HALF_WIDTH)
            self.assertEqual(player.horizontal_speed, 0)

    def test_contact_attack_still_hits_once_with_unarmed_dagger_and_pipe(self):
        for weapon in (None, "dagger", "steel_pipe"):
            enemy = Enemy(x=640)
            player = Player(x=640 - ENEMY_BODY_HALF_WIDTH - PLAYER_BODY_HALF_WIDTH, weapon=weapon)
            controls = Controls({"right", "lshift"}, attack_requested=True)
            self.assertTrue(player.update(0.1, controls, enemy))
            self.assertEqual(player.attack_time, 0)
            self.assertTrue(Stage([], enemy=enemy).hit_enemy(player))
            self.assertFalse(player.update(0.1, controls, enemy))
            self.assertAlmostEqual(player.attack_time, 0.1)
            self.assertEqual(enemy.state, "DYING")

    def test_death_width_expands_and_resolves_overlap_to_the_same_side(self):
        enemy = Enemy(x=640)
        player = Player(x=584)
        enemy.hit()
        previous_x = player.x
        for _ in range(4):
            enemy.update(0.25)
            player.update(0, Controls(), enemy)
            self.assertLess(player.x, previous_x)
            self.assertAlmostEqual(player.x, enemy.collision_bounds[0] - PLAYER_BODY_HALF_WIDTH)
            previous_x = player.x
        self.assertEqual((enemy.state, player.x), ("DEAD", 546))

    def test_corpse_blocks_ground_running_from_both_sides_without_auto_stepping(self):
        corpse = Enemy(x=640, state="DEAD")
        for side, key in ((-1, "right"), (1, "left")):
            player = Player(x=640 + side * 200, horizontal_speed=-side * RUN_SPEED)
            for _ in range(3):
                player.update(0.5, Controls({key, "lshift"}), corpse)
                self.assertEqual(player.x, 640 + side * (CORPSE_HALF_WIDTH + PLAYER_BODY_HALF_WIDTH))
                self.assertEqual((player.foot_y, player.horizontal_speed), (GROUND_Y, 0))

    def test_sliding_momentum_cannot_push_through_a_corpse(self):
        corpse = Enemy(x=640, state="DEAD")
        player = Player(x=520, horizontal_speed=RUN_SPEED)
        player.update(1, Controls(), corpse)
        self.assertEqual((player.x, player.horizontal_speed, player.boundary_speed), (546, 0, 0))

    def test_fast_fall_lands_on_corpse_and_remains_supported(self):
        corpse = Enemy(x=640, state="DEAD")
        player = Player(x=640, foot_y=GROUND_Y + 200, vertical_speed=-500, state="JUMP", jump_count=2)
        player.update(1, Controls(), corpse)
        self.assertEqual((player.foot_y, player.vertical_speed, player.jump_count),
                         (GROUND_Y + CORPSE_HEIGHT, 0, 0))
        self.assertTrue(player.grounded)
        player.update(1, Controls(), corpse)
        self.assertEqual(player.foot_y, GROUND_Y + CORPSE_HEIGHT)

    def test_jumping_from_contact_can_clear_a_completed_corpse(self):
        corpse = Enemy(x=640, state="DEAD")
        player = Player(x=546)
        controls = Controls({"right", "lshift"}, jump_requested=True)
        for _ in range(90):
            player.update(1 / 60, controls, corpse)
            if abs(player.x - corpse.x) < CORPSE_HALF_WIDTH + PLAYER_BODY_HALF_WIDTH - 1e-7:
                self.assertGreaterEqual(player.foot_y, GROUND_Y + CORPSE_HEIGHT - 1e-7)
        self.assertGreater(player.x, 734)
        self.assertEqual((player.foot_y, player.support_y), (GROUND_Y, GROUND_Y))

    def test_high_airborne_motion_can_cross_only_the_corpse(self):
        corpse = Enemy(x=640, state="DEAD")
        player = Player(x=400, foot_y=GROUND_Y + 200, horizontal_speed=RUN_SPEED, state="JUMP", jump_count=1)
        player.update(0.5, Controls({"right", "lshift"}), corpse)
        self.assertGreater(player.x, 734)
        self.assertGreater(player.foot_y, GROUND_Y + CORPSE_HEIGHT)

    def test_jump_and_double_jump_work_from_corpse_top_then_reset_on_landing(self):
        corpse = Enemy(x=640, state="DEAD")
        player = Player(x=640, foot_y=GROUND_Y + CORPSE_HEIGHT, support_y=GROUND_Y + CORPSE_HEIGHT)
        player.update(0, Controls(jump_requested=True), corpse)
        self.assertEqual((player.vertical_speed, player.jump_count), (JUMP_SPEED, 1))
        player.update(0.1, Controls(), corpse)
        player.update(0, Controls(jump_requested=True), corpse)
        self.assertEqual((player.vertical_speed, player.jump_count), (JUMP_SPEED, 2))
        player.update(2, Controls(), corpse)
        self.assertEqual((player.foot_y, player.jump_count), (GROUND_Y + CORPSE_HEIGHT, 0))

    def test_walking_off_corpse_starts_falling_and_allows_one_air_jump(self):
        corpse = Enemy(x=640, state="DEAD")
        player = Player(x=720, foot_y=GROUND_Y + CORPSE_HEIGHT, support_y=GROUND_Y + CORPSE_HEIGHT,
                        horizontal_speed=180)
        controls = Controls({"right"})
        for _ in range(30):
            player.update(1 / 60, controls, corpse)
            if not player.grounded:
                break
        self.assertFalse(player.grounded)
        self.assertEqual((player.support_y, player.jump_count), (GROUND_Y, 1))
        player.update(0, Controls(jump_requested=True), corpse)
        self.assertEqual(player.jump_count, 2)
        player.update(0, Controls(jump_requested=True), corpse)
        self.assertEqual(player.jump_count, 2)
        player.update(2, controls, corpse)
        self.assertEqual((player.foot_y, player.jump_count), (GROUND_Y, 0))

    def test_friction_on_corpse_uses_ground_resistance(self):
        corpse = Enemy(x=640, state="DEAD")
        player = Player(x=640, foot_y=180, support_y=180, horizontal_speed=50)
        reference = Player(**vars(player))
        reference.update(0.5, Controls())
        player.update(0.5, Controls(), corpse)
        self.assertAlmostEqual(player.x, reference.x, places=8)
        self.assertEqual((player.horizontal_speed, player.foot_y), (0, 180))

    def test_initial_overlap_is_resolved_without_climbing_or_switching_sides(self):
        for state in ("IDLE", "DYING", "DEAD"):
            for facing in (-1, 1):
                enemy = Enemy(x=640, state=state)
                player = Player(x=640, facing=facing)
                player.update(0, Controls(), enemy)
                left, _, right, _ = enemy.collision_bounds
                self.assertEqual(player.x, left - PLAYER_BODY_HALF_WIDTH if facing > 0 else right + PLAYER_BODY_HALF_WIDTH)
                self.assertEqual(player.foot_y, GROUND_Y)

    def test_collision_is_not_skipped_at_low_or_high_frame_rates(self):
        for state in ("IDLE", "DYING", "DEAD"):
            for fps in (2, 30, 60, 144):
                enemy = Enemy(x=640, state=state, animation_time=0.4)
                player = Player(x=400, horizontal_speed=RUN_SPEED)
                controls = Controls({"right", "lshift"})
                for _ in range(fps):
                    player.update(1 / fps, controls, enemy)
                self.assertAlmostEqual(player.x, enemy.collision_bounds[0] - PLAYER_BODY_HALF_WIDTH)
                self.assertEqual(player.horizontal_speed, 0)

    def test_transition_clears_old_support_and_revisited_corpse_is_still_solid(self):
        corpse = Enemy(x=640, state="DEAD")
        stage = Stage([], enemy=corpse)
        player = Player(x=ARROW_X[1], foot_y=180, support_y=180, horizontal_speed=370)
        self.assertTrue(stage.try_transition(player, Controls({"right", "lshift"}), Random(1)))
        self.assertEqual((player.x, player.foot_y, player.support_y, player.horizontal_speed),
                         (STAGE_ENTRY_LEFT_X, GROUND_Y, GROUND_Y, 370))
        player.x = ARROW_X[-1]
        self.assertTrue(stage.try_transition(player, Controls()))
        self.assertIs(stage.enemy, corpse)
        player.horizontal_speed = -RUN_SPEED
        player.update(1, Controls({"left", "lshift"}), stage.enemy)
        self.assertEqual(player.x, 734)
