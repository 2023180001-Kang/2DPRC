import math
import unittest
from unittest.mock import Mock

from game import Controls, Player
from rendering import draw_held_weapon
from settings import (
    ANIMATIONS, CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_COUNT, FRAME_HEIGHT, GRAVITY,
    GROUND_Y, HEIGHT, ITEM_WIDTHS, JUMP_DURATION, JUMP_SPEED, MAX_JUMPS,
    PLAYER_HALF_WIDTH, WEAPON_GRIPS, WEAPON_HAND_OFFSETS, WIDTH,
)


class HeldWeaponTests(unittest.TestCase):
    def test_unarmed_player_draws_no_weapon(self):
        images = {kind: Mock(w=900, h=300) for kind in ITEM_WIDTHS}
        images["right_hand"] = Mock(h=1280)
        draw_held_weapon(images, Player())
        for image in images.values():
            image.composite_draw.assert_not_called()

    def test_both_weapons_follow_each_pose_and_facing(self):
        images = {kind: Mock(w=900, h=300) for kind in ITEM_WIDTHS}
        images["right_hand"] = Mock(h=1280)
        for kind, width in ITEM_WIDTHS.items():
            for state, (_, fps) in ANIMATIONS.items():
                for frame in range(FRAME_COUNT):
                    for facing in (-1, 1):
                        with self.subTest(kind=kind, state=state, frame=frame, facing=facing):
                            image = images[kind]
                            image.reset_mock()
                            player = Player(x=400, foot_y=230, state=state, facing=facing,
                                            animation_time=frame / fps, weapon=kind)
                            draw_held_weapon(images, player)
                            image.composite_draw.assert_called_once()
                            angle, flip, x, y, w, h = image.composite_draw.call_args.args
                            hand_x, hand_y = WEAPON_HAND_OFFSETS[state][frame]
                            expected_flip = (facing < 0) != (kind == "steel_pipe")
                            self.assertAlmostEqual(angle, facing * math.pi / 2)
                            self.assertEqual(flip, "h" if expected_flip else "")
                            grip_x, grip_y = WEAPON_GRIPS[kind]
                            local_x = (grip_x - 0.5) * w * (-1 if flip else 1)
                            local_y = (grip_y - 0.5) * h
                            # Transform the source grip through the draw command:
                            # it must coincide with the right fist in world space.
                            self.assertAlmostEqual(x + math.cos(angle) * local_x - math.sin(angle) * local_y,
                                                   player.x + facing * hand_x * CHARACTER_SCALE)
                            self.assertAlmostEqual(y + math.sin(angle) * local_x + math.cos(angle) * local_y,
                                                   player.foot_y + hand_y * CHARACTER_SCALE)
                            self.assertEqual(w, width)
                            self.assertAlmostEqual(w / h, image.w / image.h)

    def test_held_weapons_fit_at_edges_and_jump_height(self):
        images = {kind: Mock(w=900, h=300) for kind in ITEM_WIDTHS}
        images["right_hand"] = Mock(h=1280)
        peak = MAX_JUMPS * JUMP_SPEED ** 2 / (2 * GRAVITY)
        self.assertLessEqual(GROUND_Y + peak +
                             (FRAME_HEIGHT - FRAME_BOTTOM_PADDING) * CHARACTER_SCALE, HEIGHT)
        for kind in ITEM_WIDTHS:
            for state, (_, fps) in ANIMATIONS.items():
                for frame in range(FRAME_COUNT):
                    for facing, x in ((-1, PLAYER_HALF_WIDTH), (1, WIDTH - PLAYER_HALF_WIDTH)):
                        player = Player(x=x, foot_y=GROUND_Y + peak, state=state, facing=facing,
                                        animation_time=frame / fps, weapon=kind)
                        draw_held_weapon(images, player)
                        angle, _, center_x, center_y, width, height = images[kind].composite_draw.call_args.args
                        half_x = (abs(math.cos(angle)) * width + abs(math.sin(angle)) * height) / 2
                        half_y = (abs(math.sin(angle)) * width + abs(math.cos(angle)) * height) / 2
                        self.assertGreaterEqual(center_x - half_x, 0)
                        self.assertLessEqual(center_x + half_x, WIDTH)
                        self.assertGreater(center_y - half_y, player.foot_y)
                        self.assertLessEqual(center_y + half_y, HEIGHT)

    def test_rendering_does_not_change_equipment_or_player_position(self):
        player = Player(x=400, foot_y=200, weapon="steel_pipe")
        original = vars(player).copy()
        draw_held_weapon({"steel_pipe": Mock(w=900, h=300), "right_hand": Mock(h=1280)}, player)
        self.assertEqual(vars(player), original)

    def test_double_jump_keeps_weapon_and_restarts_hand_pose_at_current_height(self):
        for kind in ITEM_WIDTHS:
            with self.subTest(kind=kind):
                controls, player = Controls(), Player(weapon=kind)
                controls.set_key("space", True)
                player.update(JUMP_DURATION / 2, controls)
                height = player.foot_y
                controls.set_key("space", False)
                controls.set_key("space", True)
                player.update(0, controls)
                self.assertEqual((player.weapon, player.frame, player.jump_count), (kind, 0, 2))
                image = Mock(w=900, h=300)
                draw_held_weapon({kind: image, "right_hand": Mock(h=1280)}, player)
                _, _, x, y, width, image_height = image.composite_draw.call_args.args
                hand_x, hand_y = WEAPON_HAND_OFFSETS["JUMP"][0]
                grip_x, grip_y = WEAPON_GRIPS[kind]
                if kind == "steel_pipe":
                    grip_x = 1 - grip_x
                self.assertAlmostEqual(x, player.x + hand_x * CHARACTER_SCALE - (0.5 - grip_y) * image_height)
                self.assertAlmostEqual(y, height + hand_y * CHARACTER_SCALE + (0.5 - grip_x) * width)
                player.update(JUMP_DURATION / 2, controls)
                self.assertAlmostEqual(player.foot_y - GROUND_Y, 384)
                self.assertEqual(player.weapon, kind)

    def test_fist_foreground_is_drawn_after_the_weapon_with_the_same_pose(self):
        calls = Mock()
        images = {"dagger": Mock(w=680, h=260), "right_hand": Mock(h=1280)}
        calls.attach_mock(images["dagger"].composite_draw, "weapon")
        calls.attach_mock(images["right_hand"].clip_composite_draw, "fist")
        player = Player(weapon="dagger", attack_time=0.2, facing=-1)
        draw_held_weapon(images, player)
        self.assertEqual([call[0] for call in calls.mock_calls], ["weapon", "fist"])
        self.assertEqual(images["right_hand"].clip_composite_draw.call_args.args[:2], (3 * 256, 256))
