import hashlib
from pathlib import Path
from random import Random
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from game import Controls, Enemy, Player, Stage, spawn_enemy
from rendering import draw_enemy, draw_stage_arrows
from resources import ROOT
from settings import (
    ARROW_SPAWN_PADDING, ARROW_SWAY_AMPLITUDE, ARROW_WIDTH, ARROW_X,
    ATTACK_DURATION, ATTACK_HEIGHT_RANGE, ATTACK_RANGE, ENEMY_DEATH_DURATION,
    ENEMY_DEATH_FPS, ENEMY_SCALE, ENEMY_SOURCE, FRAME_BOTTOM_PADDING, GROUND_Y,
    PLAYER_HALF_WIDTH, RUN_SPEED, STAGE_ARROWS, STAGE_BACKGROUNDS, STAGE_ENTRY_LEFT_X, WIDTH,
)
from tools.prepare_character import prepare


class EnemyTests(unittest.TestCase):
    def attack(self, stage, player, controls, dt=0):
        player.update(dt, controls)
        return stage.hit_enemy(player)

    def test_one_random_enemy_per_map_with_clear_entry_arrows_and_screen_bounds(self):
        for number, entry in ((1, WIDTH / 2), (2, STAGE_ENTRY_LEFT_X)):
            positions = set()
            for seed in range(500):
                enemy = spawn_enemy(Random(seed), spawn_x=entry, stage_number=number)
                positions.add(enemy.x)
                self.assertEqual((enemy.state, enemy.foot_y), ("IDLE", GROUND_Y))
                self.assertGreater(abs(enemy.x - entry), 2 * PLAYER_HALF_WIDTH)
                self.assertGreaterEqual(enemy.x - 128 * ENEMY_SCALE, 0)
                self.assertLessEqual(enemy.x + 128 * ENEMY_SCALE, WIDTH)
                for direction in STAGE_ARROWS[number]:
                    self.assertGreater(abs(enemy.x - ARROW_X[direction]),
                                       ARROW_WIDTH / 2 + ARROW_SWAY_AMPLITUDE + ARROW_SPAWN_PADDING + PLAYER_HALF_WIDTH)
            self.assertGreater(len(positions), 1)

    def test_stage_defaults_to_one_live_enemy_and_no_forward_arrow(self):
        for number, arrows in ((1, ()), (2, (-1,))):
            stage = Stage([], number=number)
            self.assertIsInstance(stage.enemy, Enemy)
            self.assertEqual(stage.enemy.state, "IDLE")
            self.assertEqual(stage.visible_arrows, arrows)

    def test_idle_enemy_never_moves_or_attacks(self):
        enemy = Enemy(x=400, facing=1)
        frames = set()
        for _ in range(100):
            enemy.update(0.1)
            frames.add(enemy.frame)
            self.assertEqual((enemy.x, enemy.foot_y, enemy.facing, enemy.state, enemy.row),
                             (400, GROUND_Y, 1, "IDLE", 0))
        self.assertEqual(frames, set(range(8)))

    def test_fresh_a_is_one_hit_for_unarmed_and_both_weapons_in_both_directions(self):
        for weapon in (None, "dagger", "steel_pipe"):
            for facing in (-1, 1):
                stage = Stage([], enemy=Enemy(x=600 + facing * 70))
                player = Player(x=600, weapon=weapon, facing=facing)
                controls = Controls()
                controls.set_key("a", True)
                self.assertTrue(self.attack(stage, player, controls))
                self.assertEqual((stage.enemy.state, stage.enemy.frame), ("DYING", 0))
                self.assertEqual(stage.visible_arrows, ())
                self.assertEqual(player.health, 100)

    def test_attack_distance_direction_and_height_boundaries(self):
        for dx, height, hits in ((0, 0, True), (ATTACK_RANGE, 0, True),
                                 (ATTACK_RANGE + 0.001, 0, False), (-0.001, 0, False),
                                 (50, ATTACK_HEIGHT_RANGE, True), (50, ATTACK_HEIGHT_RANGE + 0.001, False)):
            for facing in (-1, 1):
                with self.subTest(dx=dx, height=height, facing=facing):
                    stage = Stage([], enemy=Enemy(x=600 + facing * dx))
                    player = Player(x=600, facing=facing, foot_y=GROUND_Y + height)
                    self.assertEqual(self.attack(stage, player, Controls(attack_requested=True)), hits)

    def test_running_attack_hits_after_entering_range_during_the_swing(self):
        for weapon in (None, "dagger", "steel_pipe"):
            for facing in (-1, 1):
                for fps in (30, 60, 144):
                    with self.subTest(weapon=weapon, facing=facing, fps=fps):
                        enemy = Enemy(x=640 + facing * 140)
                        player = Player(x=640, facing=facing, weapon=weapon,
                                        horizontal_speed=facing * RUN_SPEED)
                        direction = "right" if facing > 0 else "left"
                        controls = Controls(held={direction, "lshift"}, attack_requested=True)
                        self.assertTrue(player.update(1 / fps, controls, enemy))
                        self.assertEqual(enemy.state, "IDLE")
                        for _ in range(fps // 10 + 1):
                            player.update(1 / fps, controls, enemy)
                        self.assertEqual(enemy.state, "DYING")
                        self.assertTrue(player.attacking)
                        stage = Stage([], enemy=enemy)
                        self.assertEqual(stage.visible_arrows, ())
                        stage.update(ENEMY_DEATH_DURATION)
                        self.assertEqual((enemy.state, stage.visible_arrows), ("DEAD", (1,)))

    def test_running_attack_checks_path_even_when_final_position_is_above_enemy(self):
        enemy = Enemy(x=750)
        player = Player(x=640, horizontal_speed=RUN_SPEED)
        controls = Controls(held={"right", "lshift"}, attack_requested=True, jump_requested=True)
        player.update(0.25, controls, enemy)
        self.assertGreater(player.foot_y - GROUND_Y, ATTACK_HEIGHT_RANGE)
        self.assertEqual(enemy.state, "DYING")

    def test_held_attack_cannot_hit_after_the_swing_has_ended(self):
        stage = Stage([], enemy=Enemy(x=850))
        player, controls = Player(x=600), Controls()
        controls.set_key("a", True)
        self.assertFalse(self.attack(stage, player, controls))
        self.assertFalse(self.attack(stage, player, controls, 0.1))
        controls.set_key("a", True)
        self.assertFalse(self.attack(stage, player, controls, ATTACK_DURATION))
        player.x = 800
        self.assertFalse(self.attack(stage, player, controls, 0.1))
        self.assertEqual(stage.enemy.state, "IDLE")
        controls.set_key("a", False)
        controls.set_key("a", True)
        self.assertTrue(self.attack(stage, player, controls))

    def test_active_attack_can_hit_later_but_only_one_enemy_once(self):
        stage = Stage([], enemy=Enemy(x=850))
        player = Player(x=600)
        controls = Controls(attack_requested=True)
        self.assertFalse(self.attack(stage, player, controls))
        player.x = 800
        self.assertTrue(self.attack(stage, player, controls, 0.1))
        stage.update(0.2)
        self.assertFalse(stage.hit_enemy(player))
        self.assertAlmostEqual(stage.enemy.animation_time, 0.2)
        stage.enemy = Enemy(x=850)
        self.assertFalse(stage.hit_enemy(player))
        player.update(ATTACK_DURATION, controls)
        controls.attack_requested = True
        self.assertTrue(self.attack(stage, player, controls))

    def test_no_attack_cannot_hit_and_rehits_do_not_restart_fall(self):
        stage, player = Stage([], enemy=Enemy(x=650)), Player(x=600)
        self.assertFalse(stage.hit_enemy(player))
        self.assertTrue(self.attack(stage, player, Controls(attack_requested=True)))
        stage.update(0.4)
        before = vars(stage.enemy).copy()
        self.assertFalse(stage.hit_enemy(player))
        self.assertEqual(vars(stage.enemy), before)

    def test_death_plays_eight_frames_and_unlocks_only_after_full_duration(self):
        stage = Stage([], enemy=Enemy(x=500))
        stage.enemy.hit()
        for frame in range(8):
            self.assertEqual((stage.enemy.row, stage.enemy.frame), (3, frame))
            self.assertEqual(stage.visible_arrows, ())
            stage.update(1 / ENEMY_DEATH_FPS)
        self.assertTrue(stage.enemy.defeated)
        self.assertEqual(stage.visible_arrows, (1,))
        stage.update(100)
        self.assertEqual((stage.enemy.state, stage.enemy.frame), ("DEAD", 7))

    def test_locked_exit_does_not_spawn_or_mutate_player_input_or_map(self):
        for enemy_state in ("IDLE", "DYING"):
            for airborne in (False, True):
                stage = Stage([], enemy=Enemy(state=enemy_state, animation_time=0.9))
                player = Player(x=ARROW_X[1], foot_y=GROUND_Y + (100 if airborne else 0))
                controls = Controls(held={"right", "lshift", "a"}, attack_requested=True)
                player_before = vars(player).copy()
                controls_before = dict(vars(controls), held=controls.held.copy())
                with patch("game.spawn_items") as items, patch("game.spawn_enemy") as enemies:
                    self.assertFalse(stage.try_transition(player, controls))
                    items.assert_not_called()
                    enemies.assert_not_called()
                self.assertEqual(vars(player), player_before)
                self.assertEqual(vars(controls), controls_before)
                self.assertEqual(stage.number, 1)

    def test_waiting_at_exit_unlocks_on_completion_not_on_last_frame_start(self):
        stage = Stage([], enemy=Enemy(state="DYING"))
        player, controls = Player(x=ARROW_X[1]), Controls()
        stage.update(ENEMY_DEATH_DURATION - 0.000001)
        self.assertEqual(stage.enemy.frame, 7)
        self.assertFalse(stage.try_transition(player, controls))
        stage.update(0.000001)
        self.assertTrue(stage.try_transition(player, controls, Random(1)))
        self.assertEqual((stage.number, stage.enemy.state, stage.visible_arrows), (2, "IDLE", (-1,)))

    def test_round_trip_preserves_enemy_identity_and_never_respawns(self):
        first = Enemy(x=400, state="DEAD")
        stage, controls = Stage([], enemy=first), Controls()
        player = Player(x=ARROW_X[1])
        with patch("game.spawn_enemy", wraps=spawn_enemy) as spawn:
            self.assertTrue(stage.try_transition(player, controls, Random(2)))
            second = stage.enemy
            player.x = ARROW_X[-1]
            self.assertTrue(stage.try_transition(player, controls))
            self.assertIs(stage.enemy, first)
            self.assertEqual(stage.visible_arrows, (1,))
            player.x = ARROW_X[1]
            self.assertTrue(stage.try_transition(player, controls))
            self.assertIs(stage.enemy, second)
            spawn.assert_called_once()

    def test_second_map_can_return_during_fall_and_resumes_it_when_revisited(self):
        stage = Stage([], enemy=Enemy(state="DEAD"))
        player, controls = Player(x=ARROW_X[1]), Controls()
        stage.try_transition(player, controls)
        stage.enemy.hit()
        stage.update(0.25)
        second = stage.enemy
        player.x = ARROW_X[-1]
        self.assertTrue(stage.try_transition(player, controls))
        stage.update(10)
        self.assertEqual((second.state, second.animation_time), ("DYING", 0.25))
        player.x = ARROW_X[1]
        stage.try_transition(player, controls)
        stage.update(0.75)
        self.assertTrue(stage.enemy.defeated)

    def test_last_map_right_arrow_appears_after_defeat_but_has_no_destination(self):
        stage = Stage([], number=max(STAGE_BACKGROUNDS))
        self.assertEqual(stage.visible_arrows, (-1,))
        stage.enemy.hit()
        stage.update(ENEMY_DEATH_DURATION)
        self.assertEqual(stage.visible_arrows, (-1, 1))
        self.assertFalse(stage.try_transition(Player(x=ARROW_X[1]), Controls()))
        self.assertEqual(stage.number, max(STAGE_BACKGROUNDS))

    def test_renderer_uses_only_the_same_unlocked_arrow_directions_as_transition(self):
        images = {key: Mock(w=512, h=320) for key in ("arrow_left", "arrow_right")}
        stage = Stage([])
        draw_stage_arrows(images, 1, directions=stage.visible_arrows)
        images["arrow_right"].draw.assert_not_called()
        stage.enemy.hit()
        stage.update(0.5)
        draw_stage_arrows(images, 1, directions=stage.visible_arrows)
        images["arrow_right"].draw.assert_not_called()
        stage.update(0.5)
        draw_stage_arrows(images, 1, directions=stage.visible_arrows)
        images["arrow_right"].draw.assert_called_once()

    def test_enemy_rendering_selects_idle_and_death_rows_with_ground_anchor(self):
        image = Mock(h=1024)
        for state, elapsed, row in (("IDLE", 0.2, 0), ("DYING", 0.4, 3), ("DEAD", 1, 3)):
            for facing in (-1, 1):
                enemy = Enemy(x=500, facing=facing, state=state, animation_time=elapsed)
                draw_enemy(image, enemy)
                args = image.clip_composite_draw.call_args.args
                self.assertEqual(args[:4], (enemy.frame * 256, (3 - row) * 256, 256, 256))
                self.assertEqual(args[5], "h" if facing < 0 else "")
                self.assertAlmostEqual(args[7] - args[9] / 2 + FRAME_BOTTOM_PADDING * ENEMY_SCALE, GROUND_Y)

    def test_enemy_sheet_generation_preserves_source_and_has_grounded_frames(self):
        source = ROOT / ENEMY_SOURCE
        original_hash = hashlib.sha256(source.read_bytes()).digest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "enemy.png"
            prepare(source, output, rows=4)
            self.assertEqual(output.read_bytes(), (ROOT / "assets/enemy.png").read_bytes())
            with Image.open(output) as sheet:
                self.assertEqual(sheet.size, (2048, 1024))
                for row in (0, 3):
                    for frame in range(8):
                        bounds = sheet.crop((frame * 256, row * 256, (frame + 1) * 256, (row + 1) * 256)).getbbox()
                        self.assertEqual(bounds[3], 256 - FRAME_BOTTOM_PADDING)
                        self.assertLessEqual(abs((bounds[0] + bounds[2]) / 2 - 128), 0.5)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original_hash)
