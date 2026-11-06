import math
import unittest
from unittest.mock import Mock, patch

from game import Controls, Enemy, Item, Player, Stage
from rendering import draw_character, draw_held_weapon
from settings import (
    ANIMATIONS, ARMED_ANIMATION_ROWS, ARROW_X, ATTACK_DURATION, ATTACK_FPS,
    CHARACTER_SCALE, FRAME_COUNT, FRAME_HEIGHT, GROUND_Y, JUMP_DURATION, RUN_SPEED,
    WEAPON_GRIPS, WEAPON_HAND_OFFSETS, WIDTH,
)


class AttackTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("game.spawn_enemy", side_effect=lambda *args, **kwargs: Enemy(state="DEAD"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tap(self, controls, key="a"):
        controls.set_key(key, False)
        controls.set_key(key, True)
        controls.set_key(key, False)

    def test_pickup_swap_and_drop_select_the_correct_sheet_and_jump_row(self):
        player, controls = Player(), Controls()
        self.assertEqual(player.character_key, "character")
        items = [Item("dagger", player.x), Item("steel_pipe", player.x)]
        for weapon in ("dagger", "steel_pipe"):
            self.tap(controls, "f")
            player.pick_up(items, controls)
            self.assertEqual((player.weapon, player.character_key), (weapon, "armed_character"))
            for state, row in ARMED_ANIMATION_ROWS.items():
                player.state = "IDLE" if state == "ATTACK" else state
                player.attack_time = 0 if state == "ATTACK" else None
                self.assertEqual(player.row, row)
        player.state, player.attack_time = "IDLE", None
        player.x -= 200
        self.tap(controls, "f")
        player.pick_up(items, controls)
        self.assertEqual((player.weapon, player.character_key), (None, "character"))
        player.state = "JUMP"
        self.assertEqual(player.row, 3)

    def test_single_attack_shows_all_eight_frames_then_returns_to_locomotion(self):
        for weapon in ("dagger", "steel_pipe"):
            player, controls = Player(weapon=weapon), Controls(held={"left"})
            self.tap(controls)
            player.update(0, controls)
            self.assertEqual((player.display_state, player.frame), ("ATTACK", 0))
            for frame in range(1, FRAME_COUNT):
                player.update(1 / ATTACK_FPS, controls)
                self.assertEqual((player.row, player.frame), (3, frame))
            player.update(1 / ATTACK_FPS, controls)
            self.assertFalse(player.attacking)
            self.assertEqual((player.display_state, player.row, player.facing), ("WALK", 1, -1))

    def test_hold_repeat_and_mid_attack_tap_do_not_restart_or_queue(self):
        player, controls = Player(weapon="dagger"), Controls()
        controls.set_key("a", True)
        player.update(0, controls)
        player.update(0.2, controls)
        self.tap(controls)
        player.update(0.1, controls)
        self.assertAlmostEqual(player.attack_time, 0.3)
        controls.set_key("a", True)
        player.update(0.2, controls)
        player.update(1, controls)
        controls.set_key("a", True)
        player.update(0, controls)
        self.assertFalse(player.attacking)
        self.tap(controls)
        player.update(0, controls)
        self.assertTrue(player.attacking)

    def test_unarmed_a_uses_attack_sheet_then_returns_without_equipping_a_weapon(self):
        player, controls = Player(), Controls()
        self.tap(controls)
        player.update(0, controls)
        self.assertEqual((player.character_key, player.row, player.frame), ("armed_character", 3, 0))
        self.assertIsNone(player.weapon)
        player.update(ATTACK_DURATION, controls)
        self.assertEqual((player.character_key, player.display_state), ("character", "IDLE"))
        self.assertIsNone(player.weapon)

    def test_unfocused_attack_does_not_queue(self):
        player, controls = Player(), Controls(focused=False)
        self.tap(controls)
        player.update(0, controls)
        self.assertFalse(player.attacking)
        self.assertFalse(controls.attack_requested)
        controls.focused = True
        player.update(0, controls)
        self.assertFalse(player.attacking)

    def test_attack_preserves_running_and_double_jump_physics(self):
        player = Player(weapon="steel_pipe")
        reference = Player(weapon="steel_pipe")
        controls, reference_controls = Controls(held={"right", "rshift"}), Controls(held={"right", "rshift"})
        for key in ("space", "a"):
            self.tap(controls, key)
        self.tap(reference_controls, "space")
        player.update(0.1, controls)
        reference.update(0.1, reference_controls)
        self.assertEqual(player.x, WIDTH / 2 + RUN_SPEED * 0.1)
        self.assertEqual((player.x, player.foot_y, player.vertical_speed),
                         (reference.x, reference.foot_y, reference.vertical_speed))
        self.assertEqual((player.display_state, player.state, player.jump_count), ("ATTACK", "JUMP", 1))
        self.tap(controls, "space")
        player.update(0.1, controls)
        self.assertEqual(player.jump_count, 2)
        player.update(ATTACK_DURATION, controls)
        self.assertEqual((player.display_state, player.row), ("JUMP", 4))
        player.update(2 * JUMP_DURATION, controls)
        self.assertEqual((player.foot_y, player.jump_count), (GROUND_Y, 0))

    def test_swapping_ground_dropping_and_air_dropping_cancel_attack(self):
        for action in ("swap", "drop", "air_drop"):
            player, controls = Player(weapon="dagger", attack_time=0.2), Controls()
            items = [Item("steel_pipe", player.x)] if action == "swap" else []
            if action == "air_drop":
                self.tap(controls, "space")
                player.update(0.1, controls)
            self.tap(controls, "f")
            self.assertTrue(player.pick_up(items, controls))
            self.assertIsNone(player.attack_time)
            self.assertEqual(player.weapon, "steel_pipe" if action == "swap" else None)
            self.assertEqual(len(items) + int(player.weapon is not None), 2 if action == "swap" else 1)

    def test_attack_survives_both_stage_transitions_with_pending_request_consumed(self):
        for stage_number, direction in ((1, 1), (2, -1)):
            for airborne in (False, True):
                player = Player(x=ARROW_X[direction], weapon="dagger", attack_time=0.2)
                if airborne:
                    player.foot_y, player.vertical_speed, player.state, player.jump_count = GROUND_Y + 100, 200, "JUMP", 1
                controls = Controls(held={"a"}, attack_requested=True)
                self.assertTrue(Stage([], number=stage_number).try_transition(player, controls))
                self.assertEqual((player.attack_time, player.row, player.frame), (0.2, 3, 3))
                self.assertFalse(controls.attack_requested)
                self.assertIn("a", controls.held)

    def test_attack_and_jump_clip_to_the_correct_armed_sheet_rows(self):
        image = Mock(h=1280)
        for state, row in ARMED_ANIMATION_ROWS.items():
            for frame in range(FRAME_COUNT):
                player = Player(weapon="dagger", state="IDLE" if state == "ATTACK" else state)
                if state == "ATTACK":
                    player.attack_time = frame / ATTACK_FPS
                else:
                    player.animation_time = frame / ANIMATIONS[state][1]
                draw_character(image, player)
                self.assertEqual(image.clip_composite_draw.call_args.args[:4],
                                 (frame * 256, (4 - row) * FRAME_HEIGHT, 256, 256))

    def test_attack_weapon_sweep_is_mirrored_and_stays_inside_screen(self):
        for weapon in ("dagger", "steel_pipe"):
            image = Mock(w=900, h=300)
            images = {weapon: image, "right_hand": Mock(h=1280)}
            for frame in range(FRAME_COUNT):
                centers = []
                for facing in (-1, 1):
                    player = Player(weapon=weapon, attack_time=frame / ATTACK_FPS, facing=facing)
                    draw_held_weapon(images, player)
                    angle, flip, x, y, width, height = image.composite_draw.call_args.args
                    grip_x, grip_y = WEAPON_GRIPS[weapon]
                    local_x = (grip_x - 0.5) * width * (-1 if flip else 1)
                    local_y = (grip_y - 0.5) * height
                    hand_x, hand_y = WEAPON_HAND_OFFSETS["ATTACK"][frame]
                    self.assertAlmostEqual(x + math.cos(angle) * local_x - math.sin(angle) * local_y,
                                           player.x + facing * hand_x * CHARACTER_SCALE)
                    self.assertAlmostEqual(y + math.sin(angle) * local_x + math.cos(angle) * local_y,
                                           player.foot_y + hand_y * CHARACTER_SCALE)
                    centers.append((angle, x, y, flip))
                self.assertAlmostEqual(centers[0][0], -centers[1][0])
                self.assertAlmostEqual(centers[0][1] + centers[1][1], WIDTH)
                self.assertEqual(centers[0][2], centers[1][2])
                self.assertNotEqual(centers[0][3], centers[1][3])
                for facing, edge in ((-1, 76.8), (1, WIDTH - 76.8)):
                    player.x, player.facing = edge, facing
                    draw_held_weapon(images, player)
                    angle, _, x, y, width, height = image.composite_draw.call_args.args
                    extent = (abs(math.cos(angle)) * width + abs(math.sin(angle)) * height) / 2
                    self.assertGreaterEqual(x - extent, 0)
                    self.assertLessEqual(x + extent, WIDTH)
