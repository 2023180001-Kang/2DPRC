import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from PIL import Image

from game import Controls, Enemy, Item, Player, Stage
from rendering import draw_character, draw_held_weapon, draw_pickup_hint
from resources import ROOT
from settings import (
    ARROW_X, CHARACTER_SOURCE, ENEMY_ATTACK_HIT_TIME, FRAME_BOTTOM_PADDING,
    GROUND_Y, PLAYER_DEATH_FPS, PLAYER_DEATH_FRAMES,
)
from tools.prepare_character import prepare


class PlayerDeathTests(unittest.TestCase):
    def lethal(self, facing=1, front=True, **kwargs):
        player = Player(x=640, facing=facing, health=1, **kwargs)
        self.assertTrue(player.take_damage(source_x=640 + facing * (64 if front else -64)))
        return player

    def test_new_sheet_preserves_source_and_aligns_each_death_cell(self):
        source = ROOT / CHARACTER_SOURCE
        digest = hashlib.sha256(source.read_bytes()).digest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "character.png"
            prepare(output=output)
            self.assertEqual(output.read_bytes(), (ROOT / "assets/character.png").read_bytes())
            self.assertFalse(output.with_name("character_right_hand.png").exists())
            with Image.open(source) as original, Image.open(output) as aligned:
                self.assertEqual(aligned.size, (2048, 1280))
                visible = original.getchannel("A").point(lambda value: value if value >= 128 else 0)
                self.assertEqual(visible.histogram(), aligned.getchannel("A").histogram())
                for column in range(8):
                    bounds = aligned.crop((column * 256, 1024, (column + 1) * 256, 1280)).getbbox()
                    self.assertEqual(bounds[3], 256 - FRAME_BOTTOM_PADDING)
                    self.assertLessEqual(abs((bounds[0] + bounds[2]) / 2 - 128), 0.5)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), digest)

    def test_front_and_rear_lethal_hits_select_separate_clips_in_both_facings(self):
        for facing in (-1, 1):
            for front, kind in ((True, "BACKWARD"), (False, "FORWARD")):
                player = self.lethal(facing, front)
                self.assertEqual((player.health, player.state, player.death_kind, player.facing),
                                 (0, "DYING", kind, facing))
        self.assertFalse(set(PLAYER_DEATH_FRAMES["BACKWARD"]) & set(PLAYER_DEATH_FRAMES["FORWARD"]))

    def test_actual_enemy_attack_passes_its_position_to_the_lethal_hit(self):
        for facing in (-1, 1):
            for front, kind in ((True, "BACKWARD"), (False, "FORWARD")):
                player = Player(x=640, facing=facing, health=1)
                enemy = Enemy(x=640 + facing * (64 if front else -64))
                stage = Stage([], enemy=enemy)
                stage.update(0, player)
                stage.update(ENEMY_ATTACK_HIT_TIME, player)
                self.assertEqual((player.health, player.death_kind, player.state), (0, kind, "DYING"))

    def test_unknown_or_same_position_damage_defaults_to_backward(self):
        for source in (None, 640):
            player = Player(x=640, facing=-1, health=1)
            player.take_damage(source_x=source)
            self.assertEqual(player.death_kind, "BACKWARD")

    def test_nonlethal_or_invulnerable_hits_do_not_start_or_change_death(self):
        player = Player(x=640, horizontal_speed=900, state="RUN", weapon="dagger", attack_time=0.2)
        player.take_damage(source_x=576)
        self.assertEqual((player.health, player.state, player.horizontal_speed, player.attack_time),
                         (2, "RUN", 900, 0.2))
        self.assertFalse(player.take_damage(10, source_x=704))
        self.assertEqual(player.health, 2)

    def test_each_clip_plays_only_its_frames_then_holds_its_own_last_frame(self):
        for front, expected in ((True, (0, 1, 2, 3, 4)), (False, (5, 6, 7))):
            player = self.lethal(front=front)
            for frame in expected:
                self.assertEqual((player.state, player.row, player.frame), ("DYING", 4, frame))
                player.update(1 / PLAYER_DEATH_FPS, Controls())
            self.assertEqual((player.state, player.frame), ("DEAD", expected[-1]))
            player.update(100, Controls())
            self.assertEqual((player.state, player.frame), ("DEAD", expected[-1]))

    def test_death_completion_does_not_depend_on_update_partition(self):
        for front, frame in ((True, 4), (False, 7)):
            for steps in (1, 2, 30, 60, 144):
                player = self.lethal(front=front)
                for _ in range(steps):
                    player.update(1 / steps, Controls())
                self.assertEqual((player.state, player.frame, player.health), ("DEAD", frame, 0))

    def test_death_cancels_attack_horizontal_speed_and_ignores_movement_actions(self):
        for weapon in (None, "dagger", "steel_pipe"):
            player = self.lethal(weapon=weapon, horizontal_speed=900, attack_time=0.2)
            enemy = Enemy(x=704)
            controls = Controls({"left", "rshift", "a", "f", "space"},
                                jump_requested=True, attack_requested=True, pickup_requested=True)
            for _ in range(60):
                player.update(1 / 60, controls, enemy)
            self.assertEqual((player.x, player.facing, player.horizontal_speed, player.state), (640, 1, 0, "DEAD"))
            self.assertFalse(player.attacking)
            self.assertFalse(controls.jump_requested or controls.attack_requested or controls.pickup_requested)
            self.assertEqual(enemy.state, "IDLE")

    def test_airborne_death_stops_rising_and_falls_to_ground_without_resetting_clip(self):
        player = self.lethal(front=False, foot_y=GROUND_Y + 300, vertical_speed=400,
                             state="JUMP", jump_count=2)
        self.assertEqual(player.vertical_speed, 0)
        player.update(0.4, Controls({"right", "lshift"}, jump_requested=True))
        self.assertEqual((player.frame, player.state), (7, "DYING"))
        self.assertGreater(player.foot_y, GROUND_Y)
        player.update(1, Controls())
        self.assertEqual((player.x, player.foot_y, player.vertical_speed, player.state), (640, GROUND_Y, 0, "DEAD"))

    def test_rehits_and_focus_changes_do_not_restart_or_redirect_death(self):
        player = self.lethal(front=False)
        player.update(0.2, Controls())
        before = (player.death_kind, player.death_time, player.facing)
        self.assertFalse(player.take_damage(source_x=704))
        player.update(0, Controls(focused=False))
        self.assertEqual((player.death_kind, player.death_time, player.facing), before)

    def test_dead_player_cannot_pick_up_swap_drop_or_show_f_hint(self):
        for weapon in (None, "dagger", "steel_pipe"):
            player = self.lethal(weapon=weapon)
            items = [Item("dagger", player.x)]
            controls = Controls(pickup_requested=True)
            self.assertIsNone(player.pickup_target(items))
            self.assertFalse(player.pick_up(items, controls))
            self.assertEqual((player.weapon, items), (weapon, [Item("dagger", 640)]))
            self.assertIsNone(draw_pickup_hint({}, items, player))
            draw_held_weapon({}, player)  # No texture lookup or weapon/hand overlay.

    def test_death_blocks_even_an_unlocked_exit_without_mutating_map_or_position(self):
        for number, direction in ((1, 1), (2, -1)):
            stage = Stage([], number=number, enemy=Enemy(state="DEAD"))
            player = self.lethal()
            player.x = ARROW_X[direction]
            self.assertFalse(stage.try_transition(player, Controls()))
            self.assertEqual((stage.number, player.x, player.state), (number, ARROW_X[direction], "DYING"))

    def test_renderer_selects_new_sheet_last_row_and_keeps_facing_for_both_clips(self):
        for front in (True, False):
            for facing in (-1, 1):
                player = self.lethal(facing, front, weapon="steel_pipe")
                image = Mock(h=1280)
                self.assertEqual(player.character_key, "character")
                draw_character(image, player)
                args = image.clip_composite_draw.call_args.args
                self.assertEqual(args[:4], (player.frame * 256, 0, 256, 256))
                self.assertEqual(args[5], "h" if facing < 0 else "")

    def test_zero_health_fixture_starts_death_on_first_update(self):
        player = Player(health=0, weapon="dagger", horizontal_speed=900)
        player.update(1, Controls({"right", "lshift"}))
        self.assertEqual((player.state, player.x, player.horizontal_speed, player.frame), ("DEAD", 640, 0, 4))
