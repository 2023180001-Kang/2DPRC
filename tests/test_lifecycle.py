import unittest
from unittest.mock import Mock, call, patch, sentinel

import main
import pico2d.pico2d as core
import resources
import sdl2


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.images = {
            "background": Mock(texture=sentinel.background_texture),
            "character": Mock(texture=sentinel.character_texture),
            "heart": Mock(texture=sentinel.heart_texture),
        }
        self.retained_images = tuple(self.images.values())
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
        self.draw_character = Mock()
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
                draw_health=self.draw_health,
                sleep=Mock(), perf_counter=Mock(side_effect=range(100)),
            ),
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
        image = {
            sentinel.background_texture: self.retained_images[0],
            sentinel.character_texture: self.retained_images[1],
            sentinel.heart_texture: self.retained_images[2],
        }[texture]
        self.assertIsNone(image.texture)
        self.assertIs(core.renderer, sentinel.renderer)
        self.order.append("destroy")

    def assert_images_released_before_close(self):
        self.assertEqual(self.order, ["destroy", "destroy", "destroy", "close"])
        self.assertEqual(self.images, {})
        self.assertTrue(all(image.texture is None for image in self.retained_images))
        self.assertEqual(self.destroy_texture.call_count, 3)
        self.close_canvas.assert_called_once_with()
        self.assert_core_reset()

    def test_normal_frame_releases_images_before_closing_canvas(self):
        drawing = Mock()
        drawing.attach_mock(self.draw_character, "character")
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
        player = self.draw_character.call_args.args[1]
        self.assertIsInstance(player, main.Player)
        self.assertEqual(player.health, 3)
        self.assertEqual(drawing.mock_calls, [
            call.character(self.retained_images[1], player),
            call.health(self.retained_images[2], player),
            call.update(),
        ])
        self.update_canvas.assert_called_once_with()
        self.assert_images_released_before_close()

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

    def test_quit_before_first_frame_still_releases_images(self):
        self.poll_events.return_value = False

        result = main.run(frame_limit=1)

        self.assertEqual(result["frames"], 0)
        self.draw_background.assert_not_called()
        self.draw_character.assert_not_called()
        self.draw_health.assert_not_called()
        self.assert_images_released_before_close()


if __name__ == "__main__":
    unittest.main()
