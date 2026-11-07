from random import Random
import unittest
from unittest.mock import Mock, patch

from game import Controls, Enemy, Item, Player, Stage, spawn_enemy, spawn_items
from rendering import draw_character, draw_enemy, draw_stage_arrows
from settings import ARROW_X, CHARACTER_SCALE, ENEMY_SCALE, FRAME_BOTTOM_PADDING, STAGE_GROUND_Y


class StageGroundTests(unittest.TestCase):
    def player(self, **kwargs):
        return Player(foot_y=70, support_y=70, ground_y=70, **kwargs)

    def test_only_factory_entrance_uses_lower_ground_for_all_spawned_objects(self):
        self.assertEqual(STAGE_GROUND_Y, {1: 140, 2: 140, 3: 140, 4: 140, 5: 70, 6: 140})
        enemy = spawn_enemy(Random(1), stage_number=5)
        items = spawn_items(Random(1), stage_number=5)
        self.assertEqual(enemy.foot_y, 70)
        self.assertTrue(all((item.foot_y, item.ground_y) == (70, 70) for item in items))

    def test_stage_update_binds_player_to_its_ground_before_enemy_tracking(self):
        enemy = Enemy(x=400, foot_y=70, attack_cooldown=1000)
        stage, player = Stage([], number=5, enemy=enemy), Player(x=128)
        stage.update(0.1, player)
        self.assertEqual((player.ground_y, player.foot_y, player.support_y), (70, 70, 70))
        self.assertEqual((enemy.state, enemy.foot_y, enemy.x), ("CHASE", 70, 388))
        player.update(0.1, Controls({"right"}), enemy)
        self.assertTrue(player.grounded)
        self.assertEqual(player.foot_y, 70)

    def test_factory_double_jump_lands_back_on_factory_ground(self):
        player = self.player()
        player.update(0.2, Controls(jump_requested=True))
        self.assertGreater(player.foot_y, 70)
        self.assertEqual(player.jump_count, 1)
        player.update(0.2, Controls(jump_requested=True))
        self.assertEqual(player.jump_count, 2)
        player.update(2, Controls())
        self.assertEqual((player.foot_y, player.support_y, player.jump_count), (70, 70, 0))
        self.assertTrue(player.grounded)

    def test_factory_ground_and_air_drops_land_on_the_same_local_floor(self):
        player = self.player(weapon="dagger")
        items = []
        player.pick_up(items, Controls(pickup_requested=True))
        self.assertEqual(items, [Item("dagger", player.x, foot_y=70, ground_y=70)])
        player.weapon = "steel_pipe"
        player.update(0.2, Controls(jump_requested=True))
        player.pick_up(items, Controls(pickup_requested=True))
        airborne = items[-1]
        self.assertTrue(airborne.falling)
        self.assertEqual(airborne.ground_y, 70)
        self.assertEqual(airborne.update(2), Item("steel_pipe", player.x, foot_y=70, ground_y=70))

    def test_factory_death_falls_to_local_ground(self):
        player = Player(foot_y=270, support_y=70, ground_y=70, vertical_speed=200, health=1)
        player.take_damage(source_x=704)
        player.update(2, Controls())
        self.assertEqual((player.state, player.foot_y, player.support_y), ("DEAD", 70, 70))

    def test_factory_corpse_support_and_walking_off_use_local_ground(self):
        corpse = Enemy(x=640, foot_y=70, state="DEAD")
        player = Player(x=640, foot_y=270, support_y=70, ground_y=70, vertical_speed=-500,
                        state="JUMP", jump_count=1)
        player.update(0.5, Controls(), corpse)
        self.assertEqual((player.foot_y, player.support_y), (110, 110))
        player.update(2, Controls({"right"}), corpse)
        self.assertEqual((player.foot_y, player.support_y), (70, 70))

    def test_grounded_crossings_rebase_feet_in_both_directions(self):
        for number, direction in ((4, 1), (5, -1), (5, 1), (6, -1)):
            ground = STAGE_GROUND_Y[number]
            stage = Stage([], number=number, enemy=Enemy(state="DEAD", foot_y=ground))
            player = Player(x=ARROW_X[direction], foot_y=ground, support_y=ground, ground_y=ground)
            self.assertTrue(stage.try_transition(player, Controls(), Random(number)))
            expected = STAGE_GROUND_Y[number + direction]
            self.assertEqual((player.ground_y, player.foot_y, player.support_y), (expected, expected, expected))
            self.assertTrue(player.grounded)

    def test_airborne_crossings_keep_relative_height_velocity_and_jump_count(self):
        for number, direction in ((4, 1), (5, -1), (5, 1), (6, -1)):
            ground = STAGE_GROUND_Y[number]
            stage = Stage([], number=number, enemy=Enemy(state="DEAD", foot_y=ground))
            player = Player(x=ARROW_X[direction], foot_y=ground + 120, support_y=ground, ground_y=ground,
                            vertical_speed=100, state="JUMP", jump_count=2, animation_time=0.3)
            self.assertTrue(stage.try_transition(player, Controls(), Random(number)))
            expected = STAGE_GROUND_Y[number + direction]
            self.assertEqual((player.ground_y, player.foot_y, player.support_y), (expected, expected + 120, expected))
            self.assertEqual((player.vertical_speed, player.state, player.jump_count, player.animation_time),
                             (100, "JUMP", 2, 0.3))

    def test_factory_revisit_keeps_enemy_and_dropped_item_at_local_floor(self):
        stage = Stage([], number=4, enemy=Enemy(state="DEAD"))
        player, controls = Player(x=ARROW_X[1]), Controls()
        with patch("game.spawn_enemy", wraps=spawn_enemy) as spawn:
            stage.try_transition(player, controls, Random(1))
            enemy = stage.enemy
            player.x = stage.items[0].x
            self.assertTrue(player.pick_up(stage.items, Controls(pickup_requested=True)))
            player.x = ARROW_X[-1]
            self.assertTrue(player.pick_up(stage.items, Controls(pickup_requested=True)))
            self.assertEqual((stage.items[-1].foot_y, stage.items[-1].ground_y), (70, 70))
            saved = stage.items
            stage.try_transition(player, controls)
            player.x = ARROW_X[1]
            stage.try_transition(player, controls)
            self.assertIs(stage.enemy, enemy)
            self.assertIs(stage.items, saved)
            self.assertEqual((player.foot_y, enemy.foot_y), (70, 70))
            spawn.assert_called_once()

    def test_factory_character_enemy_and_arrows_share_visible_ground_anchor(self):
        player = self.player()
        enemy = Enemy(foot_y=70)
        for actor, draw, scale in ((player, draw_character, CHARACTER_SCALE), (enemy, draw_enemy, ENEMY_SCALE)):
            image = Mock(h=1280)
            draw(image, actor)
            args = image.clip_composite_draw.call_args.args
            self.assertAlmostEqual(args[7] - args[9] / 2 + FRAME_BOTTOM_PADDING * scale, 70)
        arrows = {key: Mock(w=512, h=320) for key in ("arrow_left", "arrow_right")}
        draw_stage_arrows(arrows, 5)
        for image in arrows.values():
            _, y, _, height = image.draw.call_args.args
            self.assertEqual(y - height / 2, 70)
