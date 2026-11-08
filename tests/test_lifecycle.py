import unittest
from unittest.mock import ANY, Mock, call, patch, sentinel

import main
import pico2d.pico2d as core
import resources
import sdl2

from game import Enemy, Item, Player, Stage
from settings import ARROW_X, STAGE_ENTRY_LEFT_X


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.images = {
            "background": Mock(texture=sentinel.background_texture),
            "character": Mock(texture=sentinel.character_texture),
            "health_bar": Mock(texture=sentinel.health_bar_texture),
            "dagger": Mock(texture=sentinel.dagger_texture),
            "steel_pipe": Mock(texture=sentinel.steel_pipe_texture),
            "second_background": Mock(texture=sentinel.second_background_texture),
            "arrow_left": Mock(texture=sentinel.arrow_left_texture),
            "arrow_right": Mock(texture=sentinel.arrow_right_texture),
            "armed_character": Mock(texture=sentinel.armed_character_texture),
            "right_hand": Mock(texture=sentinel.right_hand_texture),
            "enemy": Mock(texture=sentinel.enemy_texture),
            "city_2_1": Mock(texture=sentinel.city_2_1_texture),
            "city_2_2": Mock(texture=sentinel.city_2_2_texture),
            "factory_3_1": Mock(texture=sentinel.factory_3_1_texture),
            "factory_3_2": Mock(texture=sentinel.factory_3_2_texture),
        }
        self.retained_images = tuple(self.images.values())
        self.textures = {image.texture: image for image in self.retained_images}
        self.order = []
        self.open_canvas = Mock(side_effect=self.open_mock_canvas)
        self.close_canvas = Mock(side_effect=lambda: self.order.append("close"))
        self.hide_lattice = Mock()
        self.clear_canvas = Mock()
        self.update_canvas = Mock()
        self.set_title = Mock()
        self.destroy_texture = Mock(side_effect=self.destroy_mock_texture)
        self.load_images = Mock(return_value=self.images)
        self.poll_events = Mock(return_value=True)
        self.draw_background = Mock()
        self.draw_stage_arrows = Mock()
        self.items = []
        self.spawn_items = Mock(return_value=self.items)
        self.draw_items = Mock()
        self.draw_enemy = Mock()
        self.draw_character = Mock()
        self.draw_held_weapon = Mock()
        self.draw_falling_items = Mock()
        self.draw_pickup_hint = Mock()
        self.draw_health = Mock()
        patches = [
            patch.multiple(
                core, window=sentinel.stale_window, renderer=sentinel.stale_renderer,
                audio_on=True, create=True,
            ),
            patch.multiple(
                main.pico2d, open_canvas=self.open_canvas, close_canvas=self.close_canvas,
                hide_lattice=self.hide_lattice, clear_canvas=self.clear_canvas,
                update_canvas=self.update_canvas, load_image=Mock(),
            ),
            patch.multiple(
                core, SDL_SetWindowTitle=self.set_title,
                SDL_DestroyTexture=self.destroy_texture,
            ),
            patch.object(sdl2, "SDL_DestroyTexture", self.destroy_texture),
            patch.multiple(
                main, load_images=self.load_images, poll_events=self.poll_events,
                draw_background=self.draw_background, draw_character=self.draw_character,
                draw_health=self.draw_health, spawn_items=self.spawn_items,
                draw_items=self.draw_items,
                draw_enemy=self.draw_enemy,
                draw_held_weapon=self.draw_held_weapon,
                draw_falling_items=self.draw_falling_items,
                draw_pickup_hint=self.draw_pickup_hint,
                draw_stage_arrows=self.draw_stage_arrows,
                sleep=Mock(), perf_counter=Mock(side_effect=range(100)),
            ),
            patch("game.spawn_enemies", side_effect=lambda *args, **kwargs: [Enemy(state="DEAD")]),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def assert_core_reset(self):
        self.assertIsNone(core.window)
        self.assertIsNone(core.renderer)
        self.assertIs(core.audio_on, False)

    def open_mock_canvas(self, *args, **kwargs):
        self.assert_core_reset()
        core.window = sentinel.window
        core.renderer = sentinel.renderer
        core.audio_on = True

    def destroy_mock_texture(self, texture):
        image = self.textures[texture]
        self.assertIsNone(image.texture)
        self.assertIs(core.renderer, sentinel.renderer)
        self.order.append("destroy")

    def assert_images_released_before_close(self):
        self.assertEqual(self.order, ["destroy"] * len(self.retained_images) + ["close"])
        self.assertEqual(self.images, {})
        self.assertTrue(all(image.texture is None for image in self.retained_images))
        self.assertEqual(self.destroy_texture.call_count, len(self.retained_images))
        self.close_canvas.assert_called_once_with()
        self.assert_core_reset()

    def test_normal_frame_releases_images_before_closing_canvas(self):
        enemy_image = self.images["enemy"]
        drawing = Mock()
        drawing.attach_mock(self.draw_background, "background")
        drawing.attach_mock(self.draw_stage_arrows, "arrows")
        drawing.attach_mock(self.draw_items, "items")
        drawing.attach_mock(self.draw_enemy, "enemy")
        drawing.attach_mock(self.draw_character, "character")
        drawing.attach_mock(self.draw_held_weapon, "weapon")
        drawing.attach_mock(self.draw_falling_items, "falling_items")
        drawing.attach_mock(self.draw_pickup_hint, "hint")
        drawing.attach_mock(self.draw_health, "health")
        drawing.attach_mock(self.update_canvas, "update")

        result = main.run(frame_limit=1)

        self.assertEqual(result["frames"], 1)
        self.open_canvas.assert_called_once_with(main.WIDTH, main.HEIGHT, sync=True)
        self.hide_lattice.assert_called_once_with()
        self.set_title.assert_called_once()
        window, title = self.set_title.call_args.args
        self.assertIs(window, sentinel.window)
        self.assertIsInstance(title, bytes)
        self.assertTrue(title)
        self.clear_canvas.assert_called_once_with()
        self.draw_background.assert_called_once_with(self.retained_images[0])
        self.spawn_items.assert_called_once_with()
        player = self.draw_character.call_args.args[1]
        self.assertIsInstance(player, main.Player)
        self.assertEqual(player.health, 100)
        self.assertEqual(drawing.mock_calls, [
            call.background(self.retained_images[0]),
            call.arrows(self.images, 1, ANY, directions=(1,)),
            call.items(self.images, self.items),
            call.enemy(enemy_image, ANY),
            call.character(self.retained_images[1], player),
            call.weapon(self.images, player),
            call.falling_items(self.images, self.items),
            call.hint(self.images, self.items, player),
            call.health(self.retained_images[2], player),
            call.update(),
        ])
        self.update_canvas.assert_called_once_with()
        self.assert_images_released_before_close()

    def test_items_spawn_once_after_player_initialization_across_three_frames(self):
        initialization = Mock()
        with patch.object(main, "Player", wraps=main.Player) as player_class:
            initialization.attach_mock(player_class, "player")
            initialization.attach_mock(self.spawn_items, "spawn")

            result = main.run(frame_limit=3)

        self.assertEqual(result["frames"], 3)
        self.assertEqual(initialization.mock_calls, [call.player(), call.spawn()])
        self.assertEqual(self.draw_items.call_args_list, [call(self.images, self.items)] * 3)
        self.assert_images_released_before_close()

    def test_main_loop_draws_every_enemy_in_the_encounter(self):
        stage = Stage([], enemies=[Enemy(x=x, state="DEAD") for x in (300, 600, 900)])
        image = self.images["enemy"]
        with patch.object(main, "Stage", return_value=stage):
            main.run(frame_limit=1)
        self.assertEqual(self.draw_enemy.call_args_list, [call(image, enemy) for enemy in stage.enemies])

    def test_melee_hit_translates_every_world_layer_but_keeps_hud_independent(self):
        stage = Stage([], enemy=Enemy(x=704, state="ATTACK"))
        with patch.object(main, "Stage", return_value=stage):
            main.run(frame_limit=1)
        player = self.draw_health.call_args.args[1]
        self.assertEqual(player.health, 90)
        for draw in (self.draw_background, self.draw_stage_arrows, self.draw_items,
                     self.draw_enemy, self.draw_character, self.draw_held_weapon,
                     self.draw_falling_items, self.draw_pickup_hint):
            self.assertEqual(draw.call_args.kwargs["offset"], main.camera_offset(player))
        self.assertEqual(self.draw_health.call_args.kwargs, {})
        self.assert_images_released_before_close()

    def test_restart_recreates_campaign_and_player_but_reuses_canvas_and_resources(self):
        old_player = Player(health=0, state="DYING", weapon="dagger", hit_test_mode=True,
                            hurt_time=0.5, hit_feedback_time=0.2, jump_count=2)
        old_stage = Stage([Item("dagger", 500)], number=5, enemy=Enemy(state="DEAD"))
        old_stage._items_by_stage[1] = []
        new_player = Player()
        new_stage = Stage([], enemy=Enemy(x=900))
        controls_seen = []

        def restart(controls):
            controls_seen.append(controls)
            for key in ("left", "lshift", "space", "f", "a", "h", "r"):
                controls.set_key(key, True)
            return True

        self.poll_events.side_effect = restart
        with (patch.object(main, "Player", side_effect=[old_player, new_player]) as players,
              patch.object(main, "Stage", side_effect=[old_stage, new_stage]) as stages):
            result = main.run(frame_limit=1)
        self.assertEqual((players.call_count, stages.call_count, self.spawn_items.call_count), (2, 2, 2))
        self.assertEqual(result["stage"], 1)
        self.assertEqual(vars(new_player), vars(Player()))
        self.assertEqual(new_stage.arrow_time, 0)
        self.assertEqual(set(new_stage._items_by_stage), {1})
        self.assertEqual(set(new_stage._enemies_by_stage), {1})
        self.assertTrue(new_stage.enemy.alive)
        controls = controls_seen[0]
        self.assertEqual(controls.held, {"r", "h"})
        for requested in ("jump_requested", "pickup_requested", "attack_requested",
                          "restart_requested", "hit_test_requested"):
            self.assertFalse(getattr(controls, requested))
        self.open_canvas.assert_called_once()
        self.load_images.assert_called_once()
        self.assertTrue(self.set_title.call_args.args[1].endswith(b"OFF"))
        self.assert_images_released_before_close()

    def test_r_restarts_alive_immediately_once_per_fresh_press(self):
        old_player = Player(health=10)
        old_stage = Stage([], enemy=Enemy(x=704, state="ATTACK"))
        tick = -1

        def feed(controls):
            nonlocal tick
            tick += 1
            if tick == 2:
                controls.set_key("r", False)
            controls.set_key("r", True)
            return True

        self.poll_events.side_effect = feed
        with (patch.object(main, "Player", side_effect=[old_player, Player(), Player()]) as players,
              patch.object(main, "Stage", side_effect=[old_stage, Stage([], enemy=Enemy(x=900)),
                                                      Stage([], enemy=Enemy(x=900))])):
            main.run(frame_limit=3)
        self.assertEqual(players.call_count, 3)
        drawn = [call.args[1] for call in self.draw_health.call_args_list]
        self.assertIsNot(drawn[0], old_player)
        self.assertIs(drawn[1], drawn[0])
        self.assertIsNot(drawn[2], drawn[0])
        self.assertEqual(old_player.health, 10)
        self.assertEqual(drawn[0].health, 100)
        self.assertEqual(drawn[2].health, 100)

    def test_h_toggle_precedes_enemy_hit_and_requires_new_press_to_toggle_off(self):
        player = Player(health=10)
        stage = Stage([], enemy=Enemy(x=704, state="ATTACK"))
        modes = []
        tick = -1

        def feed(controls):
            nonlocal tick
            tick += 1
            if tick == 2:
                controls.set_key("h", False)
            controls.set_key("h", True)
            return True

        self.poll_events.side_effect = feed
        self.draw_health.side_effect = lambda image, current: modes.append(current.hit_test_mode)
        with (patch.object(main, "Player", return_value=player),
              patch.object(main, "Stage", return_value=stage)):
            main.run(frame_limit=3)
        self.assertEqual(modes, [True, True, False])
        self.assertEqual(player.health, 0)  # The next attack is lethal after switching OFF.
        self.assertEqual(self.set_title.call_count, 3)
        self.assertTrue(self.set_title.call_args_list[1].args[1].endswith(b"ON"))
        self.assertTrue(self.set_title.call_args_list[2].args[1].endswith(b"OFF"))

    def test_h_cannot_revive_or_enable_test_mode_after_death(self):
        player = Player(health=0, state="DEAD")
        self.poll_events.side_effect = lambda controls: (controls.set_key("h", True) or True)
        with patch.object(main, "Player", return_value=player):
            main.run(frame_limit=1)
        self.assertFalse(player.hit_test_mode)
        self.assertEqual((player.health, player.state), (0, "DEAD"))
        self.set_title.assert_called_once()

    def test_drawing_traceback_retains_image_but_texture_is_released(self):
        def fail_drawing(image):
            raise RuntimeError("mock drawing failure")

        self.draw_background.side_effect = fail_drawing
        retained_error = None
        try:
            main.run(frame_limit=1)
        except RuntimeError as error:
            retained_error = error
        else:
            self.fail("Drawing failure did not propagate")

        self.assertEqual(str(retained_error), "mock drawing failure")
        traceback = retained_error.__traceback__
        retained_image = None
        while traceback is not None:
            if traceback.tb_frame.f_code is fail_drawing.__code__:
                retained_image = traceback.tb_frame.f_locals["image"]
            traceback = traceback.tb_next
        self.assertIs(retained_image, self.retained_images[0])
        self.assertIsNone(retained_image.texture)
        self.assert_images_released_before_close()

    def test_partial_open_failure_still_closes_canvas_and_resets_core(self):
        error = RuntimeError("mock partial canvas initialization failure")

        def partial_open(*args, **kwargs):
            self.assert_core_reset()
            core.window = sentinel.window
            core.audio_on = True
            raise error

        self.open_canvas.side_effect = partial_open
        with self.assertRaises(RuntimeError) as caught:
            main.run(frame_limit=1)

        self.assertIs(caught.exception, error)
        self.close_canvas.assert_called_once_with()
        self.assertEqual(self.order, ["close"])
        self.load_images.assert_not_called()
        self.hide_lattice.assert_not_called()
        self.set_title.assert_not_called()
        self.destroy_texture.assert_not_called()
        self.assert_core_reset()

    def test_null_window_or_renderer_raises_and_closes_canvas(self):
        for window, renderer in (
            (None, sentinel.renderer), (sentinel.window, None), (None, None),
        ):
            with self.subTest(window=window, renderer=renderer):
                self.close_canvas.reset_mock()
                self.order.clear()

                def open_null_canvas(*args, **kwargs):
                    self.assert_core_reset()
                    core.window = window
                    core.renderer = renderer
                    core.audio_on = True

                self.open_canvas.side_effect = open_null_canvas
                with self.assertRaises(RuntimeError):
                    main.run(frame_limit=1)

                self.close_canvas.assert_called_once_with()
                self.assertEqual(self.order, ["close"])
                self.load_images.assert_not_called()
                self.hide_lattice.assert_not_called()
                self.set_title.assert_not_called()
                self.destroy_texture.assert_not_called()
                self.assert_core_reset()

    def test_resource_failure_still_closes_canvas(self):
        error = resources.ResourceError("mock missing image")
        self.load_images.side_effect = error

        with self.assertRaises(resources.ResourceError) as caught:
            main.run(frame_limit=1)

        self.assertIs(caught.exception, error)
        self.close_canvas.assert_called_once_with()
        self.destroy_texture.assert_not_called()
        self.assertEqual(self.order, ["close"])
        self.assert_core_reset()

    def test_missing_or_corrupt_items_and_stage_images_release_previous_textures_before_close(self):
        self.load_images.side_effect = resources.load_images
        textures = list(self.textures)
        for index, name in enumerate(tuple(resources.IMAGE_FILES)[3:], start=3):
            for corrupt in (False, True):
                with self.subTest(item=name, corrupt=corrupt):
                    for texture, image in self.textures.items():
                        image.texture = texture
                    self.order.clear()
                    self.destroy_texture.reset_mock()
                    self.close_canvas.reset_mock()
                    error = OSError("mock item decode failure")
                    main.pico2d.load_image.side_effect = list(self.retained_images[:index]) + (
                        [error] if corrupt else []
                    )
                    with patch.object(
                        resources.Path, "is_file", return_value=True,
                        side_effect=None if corrupt else [True] * index + [False],
                    ):
                        with self.assertRaises(resources.ResourceError) as caught:
                            main.run(frame_limit=1)

                    self.assertIn(str(resources.ROOT / resources.IMAGE_FILES[name]), str(caught.exception))
                    if corrupt:
                        self.assertIs(caught.exception.__cause__, error)
                    self.assertEqual(self.destroy_texture.call_args_list, [
                        call(texture) for texture in textures[:index]
                    ])
                    self.assertEqual(self.order, ["destroy"] * index + ["close"])
                    self.close_canvas.assert_called_once_with()
                    self.spawn_items.assert_not_called()
                    self.assert_core_reset()

    def test_quit_before_first_frame_still_releases_images(self):
        self.poll_events.return_value = False

        result = main.run(frame_limit=1)

        self.assertEqual(result["frames"], 0)
        self.spawn_items.assert_called_once_with()
        self.draw_background.assert_not_called()
        self.draw_stage_arrows.assert_not_called()
        self.draw_items.assert_not_called()
        self.draw_character.assert_not_called()
        self.draw_held_weapon.assert_not_called()
        self.draw_falling_items.assert_not_called()
        self.draw_pickup_hint.assert_not_called()
        self.draw_health.assert_not_called()
        self.assert_images_released_before_close()

    def test_arrow_switches_background_items_and_arrow_visibility_in_main_loop(self):
        player = Player(x=ARROW_X[1], weapon="dagger", health=2)
        self.spawn_items.return_value = []
        second_items = [Item("dagger", 400), Item("steel_pipe", 600), Item("dagger", 800)]
        with (patch.object(main, "Player", return_value=player),
              patch("game.spawn_items", return_value=second_items) as spawn):
            result = main.run(frame_limit=2)
        self.assertEqual(result["stage"], 2)
        spawn.assert_called_once_with(None, spawn_x=STAGE_ENTRY_LEFT_X, stage_number=2)
        self.assertEqual(self.draw_background.call_args_list, [call(self.retained_images[5])] * 2)
        self.assertEqual(self.draw_stage_arrows.call_args_list, [call(self.images, 2, ANY, directions=(-1, 1))] * 2)
        self.assertEqual(self.draw_items.call_args_list, [call(self.images, second_items)] * 2)
        self.assertEqual((player.x, player.health, player.weapon), (STAGE_ENTRY_LEFT_X, 2, "dagger"))
        self.assert_images_released_before_close()


if __name__ == "__main__":
    unittest.main()
