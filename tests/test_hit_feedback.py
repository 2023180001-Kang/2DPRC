import unittest
from unittest.mock import Mock, patch

from game import Controls, Enemy, Item, Player, Stage
from rendering import (
    camera_offset, draw_background, draw_character, draw_enemy, draw_falling_items,
    draw_health, draw_held_weapon, draw_items, draw_pickup_hint, draw_stage_arrows,
)
from settings import (
    ARROW_X, CAMERA_SHAKE_AMPLITUDE, CAMERA_SHAKE_DURATION, ENEMY_ATTACK_HIT_TIME,
    HEALTH_SHAKE_AMPLITUDE, HEALTH_SHAKE_DURATION, HEIGHT, WIDTH,
)


class HitFeedbackTests(unittest.TestCase):
    def test_only_successful_damage_starts_feedback_including_lethal_hit(self):
        player = Player()
        self.assertEqual(camera_offset(player), (0, 0))
        self.assertFalse(player.take_damage(0))
        self.assertEqual(player.hit_feedback_time, 0)
        self.assertTrue(player.take_damage(10))
        player.update_damage(0.05)
        remaining = player.hit_feedback_time
        self.assertFalse(player.take_damage(10))
        self.assertEqual(player.hit_feedback_time, remaining)
        player.update_damage(1)
        self.assertTrue(player.take_damage(100))
        self.assertTrue(player.incapacitated)
        self.assertNotEqual(camera_offset(player), (0, 0))
        self.assertFalse(player.take_damage(10))

    def test_miss_and_invulnerability_do_not_start_feedback(self):
        for invulnerable in (False, True):
            player = Player(x=704, hurt_time=0.5 if invulnerable else 0)
            enemy = Enemy(x=640)
            enemy.update(0, player)
            if not invulnerable:
                player.x = 800
            enemy.update(ENEMY_ATTACK_HIT_TIME, player)
            self.assertEqual((player.health, player.hit_feedback_time), (100, 0))

    def test_offsets_decay_reverse_and_end_exactly_without_moving_world_state(self):
        player = Player(x=640, weapon="dagger")
        player.take_damage(10)
        position = (player.x, player.foot_y, player.horizontal_speed, player.weapon)
        offsets = []
        for _ in range(60):
            offsets.append(camera_offset(player))
            player.update_damage(1 / 120)
        self.assertTrue(any(x < 0 for x, _ in offsets))
        self.assertTrue(any(x > 0 for x, _ in offsets))
        self.assertTrue(any(abs(y) > 0.1 for _, y in offsets))
        for index, (x, y) in enumerate(offsets):
            envelope = CAMERA_SHAKE_AMPLITUDE * max(0, 1 - index / 120 / CAMERA_SHAKE_DURATION) ** 2
            self.assertLessEqual(abs(x), envelope + 1e-9)
            self.assertLessEqual(abs(y), envelope + 1e-9)
        self.assertEqual(camera_offset(player), (0, 0))
        self.assertEqual((player.x, player.foot_y, player.horizontal_speed, player.weapon), position)

    def test_feedback_has_same_offsets_for_same_elapsed_time_at_different_fps(self):
        offsets = []
        for steps in (1, 3, 12, 30, 144):
            player = Player()
            player.take_damage(10)
            for _ in range(steps):
                player.update_damage(0.125 / steps)
            offsets.append(camera_offset(player))
        for x, y in offsets:
            self.assertAlmostEqual(x, offsets[0][0])
            self.assertAlmostEqual(y, offsets[0][1])

    def test_health_frame_and_depleted_fill_move_together_and_return_to_margin(self):
        image = Mock(w=2129, h=404)
        player = Player(health=70)
        with patch("rendering.draw_rectangle") as rectangle:
            draw_health(image, player)
            resting_bar = image.draw.call_args.args
            resting_fill = rectangle.call_args.args
            player.take_damage(10)
            # Compare the same health ratio before/after activating feedback.
            player.health = 70
            draw_health(image, player)
            shaking_bar = image.draw.call_args.args
            shaking_fill = rectangle.call_args.args
            dx, dy = shaking_bar[0] - resting_bar[0], shaking_bar[1] - resting_bar[1]
            self.assertEqual(dx, HEALTH_SHAKE_AMPLITUDE)
            self.assertLess(dx, camera_offset(player)[0])
            for index, delta in enumerate((dx, dy, dx, dy)):
                self.assertAlmostEqual(shaking_fill[index] - resting_fill[index], delta)
            x, y, width, height = shaking_bar
            self.assertGreaterEqual(x - width / 2, 0)
            self.assertLessEqual(y + height / 2, HEIGHT)
            player.update_damage(HEALTH_SHAKE_DURATION)
            draw_health(image, player)
            self.assertEqual(image.draw.call_args.args, resting_bar)
            self.assertEqual(rectangle.call_args.args, resting_fill)
            player.update_damage(1)
            self.assertEqual(camera_offset(player), (0, 0))

    def test_background_covers_canvas_throughout_shake(self):
        for size in ((1280, 720), (1672, 941), (300, 1000)):
            image = Mock(w=size[0], h=size[1])
            player = Player()
            player.take_damage(10)
            for _ in range(40):
                draw_background(image, offset=camera_offset(player))
                x, y, width, height = image.draw.call_args.args
                self.assertLessEqual(x - width / 2, 0)
                self.assertGreaterEqual(x + width / 2, WIDTH)
                self.assertLessEqual(y - height / 2, 0)
                self.assertGreaterEqual(y + height / 2, HEIGHT)
                player.update_damage(1 / 120)

    def test_world_layers_share_translation_including_weapon_hand_and_f_hint(self):
        image = Mock(w=2048, h=1280)
        images = {key: image for key in ("arrow_right", "dagger", "right_hand")}
        player = Player(x=640, weapon="dagger")
        item = Item("dagger", 640)
        offset = (4, -2)
        cases = [
            (lambda **kw: draw_character(image, player, **kw), image.clip_composite_draw, (6, 7)),
            (lambda **kw: draw_enemy(image, Enemy(), **kw), image.clip_composite_draw, (6, 7)),
            (lambda **kw: draw_stage_arrows(images, 1, **kw), image.draw, (0, 1)),
            (lambda **kw: draw_items(images, [item], **kw), image.draw, (0, 1)),
            (lambda **kw: draw_falling_items(images, [Item("dagger", 640, falling=True)], **kw), image.draw, (0, 1)),
            (lambda **kw: draw_held_weapon(images, player, **kw), image.composite_draw, (2, 3)),
            (lambda **kw: draw_held_weapon(images, player, **kw), image.clip_composite_draw, (6, 7)),
        ]
        for draw, method, indices in cases:
            draw()
            baseline = method.call_args.args
            draw(offset=offset)
            translated = method.call_args.args
            for index, delta in zip(indices, offset):
                self.assertAlmostEqual(translated[index] - baseline[index], delta)
        with patch("rendering.draw_rectangle") as rectangle:
            draw_pickup_hint(images, [item], player)
            baseline = [call.args for call in rectangle.call_args_list]
            rectangle.reset_mock()
            draw_pickup_hint(images, [item], player, offset=offset)
            for before, after in zip(baseline, rectangle.call_args_list):
                for index, delta in enumerate(offset * 2):
                    self.assertAlmostEqual(after.args[index] - before[index], delta)

    def test_stage_transition_preserves_feedback_without_triggering_exit_from_visual_offset(self):
        player = Player(x=ARROW_X[1] - 31)
        stage = Stage([], enemy=Enemy(state="DEAD"))
        player.take_damage(10)
        self.assertGreater(player.x + camera_offset(player)[0], ARROW_X[1] - 30)
        self.assertFalse(stage.try_transition(player, Controls()))
        player.x = ARROW_X[1]
        before = camera_offset(player)
        self.assertTrue(stage.try_transition(player, Controls()))
        self.assertEqual(camera_offset(player), before)
        stage.update(1, player)
        self.assertEqual(player.hit_feedback_time, 0)
