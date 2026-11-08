from random import Random
import unittest
from unittest.mock import patch

from PIL import Image

from game import Controls, Enemy, Item, Player, Stage, spawn_enemy, spawn_enemies, spawn_items
from resources import IMAGE_FILES, ROOT
from settings import (
    ARROW_SPAWN_PADDING, ARROW_SWAY_AMPLITUDE, ARROW_WIDTH, ARROW_X,
    ENEMY_DEATH_DURATION, GROUND_Y, ITEM_WIDTHS, PLAYER_HALF_WIDTH,
    STAGE_ARROWS, STAGE_BACKGROUNDS, STAGE_ENTRY_LEFT_X, STAGE_GROUND_Y,
)


class StageProgressionTests(unittest.TestCase):
    def test_six_backgrounds_are_connected_in_the_requested_order(self):
        self.assertEqual(tuple(STAGE_BACKGROUNDS), (1, 2, 3, 4, 5, 6))
        self.assertEqual([IMAGE_FILES[key] for key in STAGE_BACKGROUNDS.values()], [
            "chapter1-1 map.png", "chapter1-2 map.png",
            "hoodman_city_stage_2_1_1672x941.png", "hoodman_city_stage_2_2_1672x941.png",
            "hoodman_factory_stage_3_1_1672x941.png", "hoodman_factory_stage_3_2_1672x941.png",
        ])
        for key in STAGE_BACKGROUNDS.values():
            with Image.open(ROOT / IMAGE_FILES[key]) as image:
                self.assertEqual(image.size, (1672, 941))

    def test_all_maps_lock_forward_until_full_death_and_allow_return(self):
        for number in STAGE_BACKGROUNDS:
            enemy = Enemy(x=640)
            stage = Stage([], number=number, enemy=enemy)
            player = Player(x=ARROW_X[1])
            controls = Controls()
            self.assertNotIn(1, stage.visible_arrows)
            self.assertFalse(stage.try_transition(player, controls))
            self.assertEqual(-1 in stage.visible_arrows, number > 1)
            enemy.hit()
            stage.update(ENEMY_DEATH_DURATION - 0.001)
            self.assertEqual(enemy.frame, 7)
            self.assertNotIn(1, stage.visible_arrows)
            self.assertFalse(stage.try_transition(player, controls))
            stage.update(0.001)
            self.assertIn(1, stage.visible_arrows)
            transitioned = stage.try_transition(player, controls, Random(number))
            self.assertEqual(transitioned, number < 6)
            self.assertEqual(stage.number, number + 1 if number < 6 else 6)
            if number < 6:
                self.assertEqual((stage.enemy.state, len(stage._enemies_by_stage)), ("IDLE", 2))
                self.assertNotIn(1, stage.visible_arrows)

    def test_all_six_maps_keep_items_out_of_hidden_and_visible_arrow_sweep(self):
        counts = set()
        for number in STAGE_BACKGROUNDS:
            entry = 640 if number == 1 else STAGE_ENTRY_LEFT_X
            for seed in range(500):
                items = spawn_items(Random(seed), spawn_x=entry, stage_number=number)
                self.assertIn(len(items), (3, 4, 5))
                self.assertEqual({item.kind for item in items}, {"dagger", "steel_pipe"})
                counts.add(len(items))
                for item in items:
                    self.assertGreater(abs(item.x - entry), PLAYER_HALF_WIDTH + ITEM_WIDTHS[item.kind] / 2)
                    for direction in STAGE_ARROWS[number]:
                        clearance = (ARROW_WIDTH / 2 + ARROW_SWAY_AMPLITUDE + ARROW_SPAWN_PADDING
                                     + ITEM_WIDTHS[item.kind] / 2)
                        self.assertGreater(abs(item.x - ARROW_X[direction]), clearance)
        self.assertEqual(counts, {3, 4, 5})

    def test_each_map_spawns_one_enemy_clear_of_entry_and_both_arrows(self):
        for number in STAGE_BACKGROUNDS:
            entry = 640 if number == 1 else STAGE_ENTRY_LEFT_X
            for seed in range(100):
                enemy = spawn_enemy(Random(seed), spawn_x=entry, stage_number=number)
                self.assertEqual((enemy.state, enemy.foot_y), ("IDLE", STAGE_GROUND_Y[number]))
                self.assertGreater(abs(enemy.x - entry), 2 * PLAYER_HALF_WIDTH)
                for direction in STAGE_ARROWS[number]:
                    self.assertGreater(abs(enemy.x - ARROW_X[direction]),
                                       ARROW_WIDTH / 2 + ARROW_SWAY_AMPLITUDE + ARROW_SPAWN_PADDING + PLAYER_HALF_WIDTH)

    def test_complete_campaign_and_round_trip_preserve_all_enemy_and_item_instances(self):
        first = Enemy(x=640)
        stage = Stage([Item("dagger", 400)], enemy=first)
        player, controls = Player(weapon="steel_pipe", health=2), Controls()
        enemies, items = {1: first}, {1: stage.items}
        with (patch("game.spawn_enemies", wraps=spawn_enemies) as enemy_spawn,
              patch("game.spawn_items", wraps=spawn_items) as item_spawn):
            for number in range(1, 7):
                self.assertEqual(stage.number, number)
                for enemy in stage.enemies:
                    enemy.hit()
                stage.update(ENEMY_DEATH_DURATION)
                # A dropped weapon on a visited map must survive round trips.
                stage.items.append(Item("steel_pipe", 700))
                enemies[number], items[number] = stage.enemy, stage.items
                if number < 6:
                    player.x = ARROW_X[1]
                    self.assertTrue(stage.try_transition(player, controls, Random(number)))
            for expected in range(5, 0, -1):
                player.x = ARROW_X[-1]
                self.assertTrue(stage.try_transition(player, controls))
                self.assertEqual(stage.number, expected)
                self.assertIs(stage.enemy, enemies[expected])
                self.assertIs(stage.items, items[expected])
            for expected in range(2, 7):
                player.x = ARROW_X[1]
                self.assertTrue(stage.try_transition(player, controls))
                self.assertEqual(stage.number, expected)
                self.assertIs(stage.enemy, enemies[expected])
                self.assertIs(stage.items, items[expected])
                self.assertIn(Item("steel_pipe", 700), stage.items)
            self.assertEqual((enemy_spawn.call_count, item_spawn.call_count), (5, 5))
        self.assertEqual((player.health, player.weapon), (2, "steel_pipe"))
        self.assertEqual((len(stage._enemies_by_stage), len(stage._items_by_stage)), (6, 6))

    def test_return_is_available_before_defeating_each_later_stage(self):
        for number in range(2, 7):
            stage = Stage([], number=number)
            current = stage.enemies
            self.assertTrue(all(enemy.state == "IDLE" for enemy in current))
            self.assertTrue(stage.try_transition(Player(x=ARROW_X[-1]), Controls(), Random(number)))
            self.assertEqual(stage.number, number - 1)
            self.assertIs(stage._enemies_by_stage[number], current)

    def test_dead_player_cannot_advance_in_any_cleared_stage(self):
        for number in STAGE_BACKGROUNDS:
            stage = Stage([], number=number, enemy=Enemy(state="DEAD"))
            self.assertFalse(stage.try_transition(Player(x=ARROW_X[1], health=0), Controls()))
            self.assertEqual(stage.number, number)
