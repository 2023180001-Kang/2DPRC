import unittest
from unittest.mock import Mock

from game import Player
from rendering import draw_held_weapon
from settings import (
    ANIMATIONS, CHARACTER_SCALE, FRAME_COUNT, GROUND_Y, HEIGHT, ITEM_WIDTHS,
    PLAYER_HALF_WIDTH, WEAPON_HAND_OFFSETS, WIDTH,
)


class HeldWeaponTests(unittest.TestCase):
    def test_unarmed_player_draws_no_weapon(self):
        images = {kind: Mock(w=900, h=300) for kind in ITEM_WIDTHS}
        draw_held_weapon(images, Player())
        for image in images.values():
            image.composite_draw.assert_not_called()

    def test_both_weapons_follow_each_pose_and_facing(self):
        images = {kind: Mock(w=900, h=300) for kind in ITEM_WIDTHS}
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
                            self.assertEqual((angle, flip), (0, "h" if facing < 0 else ""))
                            self.assertAlmostEqual(x, player.x + facing *
                                                   (hand_x * CHARACTER_SCALE + width * 0.3))
                            self.assertAlmostEqual(y, player.foot_y + hand_y * CHARACTER_SCALE)
                            self.assertEqual(w, width)
                            self.assertAlmostEqual(w / h, image.w / image.h)

    def test_held_weapons_fit_at_edges_and_jump_height(self):
        images = {kind: Mock(w=900, h=300) for kind in ITEM_WIDTHS}
        for kind in ITEM_WIDTHS:
            for state, (_, fps) in ANIMATIONS.items():
                for frame in range(FRAME_COUNT):
                    for facing, x in ((-1, PLAYER_HALF_WIDTH), (1, WIDTH - PLAYER_HALF_WIDTH)):
                        player = Player(x=x, foot_y=GROUND_Y + 192, state=state, facing=facing,
                                        animation_time=frame / fps, weapon=kind)
                        draw_held_weapon(images, player)
                        _, _, center_x, center_y, width, height = images[kind].composite_draw.call_args.args
                        self.assertGreaterEqual(center_x - width / 2, 0)
                        self.assertLessEqual(center_x + width / 2, WIDTH)
                        self.assertGreater(center_y - height / 2, player.foot_y)
                        self.assertLessEqual(center_y + height / 2, HEIGHT)

    def test_rendering_does_not_change_equipment_or_player_position(self):
        player = Player(x=400, foot_y=200, weapon="steel_pipe")
        original = vars(player).copy()
        draw_held_weapon({"steel_pipe": Mock(w=900, h=300)}, player)
        self.assertEqual(vars(player), original)
