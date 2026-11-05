import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch, sentinel

import resources
import sdl2


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.root = resources.ROOT / "mock-resources"
        self.background = Mock(texture=sentinel.background_texture)
        self.character = Mock(texture=sentinel.character_texture)
        self.health_bar = Mock(texture=sentinel.health_bar_texture)
        self.images = {
            "background": self.background,
            "character": self.character,
            "health_bar": self.health_bar,
            "dagger": Mock(texture=sentinel.dagger_texture),
            "steel_pipe": Mock(texture=sentinel.steel_pipe_texture),
            "second_background": Mock(texture=sentinel.second_background_texture),
            "portal": Mock(texture=sentinel.portal_texture),
        }
        loader = patch.object(
            resources.pico2d, "load_image",
            side_effect=list(self.images.values()),
        )
        self.load_image = loader.start()
        self.addCleanup(loader.stop)
        destroy = patch.object(sdl2, "SDL_DestroyTexture")
        self.destroy_texture = destroy.start()
        self.addCleanup(destroy.stop)
        exists = patch.object(resources.Path, "is_file", autospec=True, return_value=True)
        self.is_file = exists.start()
        self.addCleanup(exists.stop)

    def test_default_root_and_image_filenames(self):
        images = resources.load_images()

        self.assertEqual(resources.ROOT, Path(resources.__file__).resolve().parent)
        self.assertEqual(resources.IMAGE_FILES, {
            "background": "newfirststage.png",
            "character": "assets/character.png",
            "health_bar": "hp_preview_100.png",
            "dagger": "dagger_item_pico2d.png",
            "steel_pipe": "steel_pipe_item_pico2d.png",
            "second_background": "firstSecondmap.png",
            "portal": "Hood_Man_Teleport_Pad_512.png",
        })
        self.assertEqual(list(resources.IMAGE_FILES), list(self.images))
        self.assertEqual(images, self.images)
        paths = [resources.ROOT / name for name in resources.IMAGE_FILES.values()]
        self.assertEqual(self.is_file.call_args_list, [call(path) for path in paths])
        self.assertEqual(self.load_image.call_args_list, [call(str(path)) for path in paths])
        self.destroy_texture.assert_not_called()

    def test_explicit_root_accepts_path_and_string(self):
        for root in (self.root, str(self.root)):
            with self.subTest(root=root):
                self.load_image.reset_mock(side_effect=True)
                self.load_image.side_effect = list(self.images.values())
                images = resources.load_images(root)

                self.assertEqual(set(images), set(resources.IMAGE_FILES))
                self.assertEqual(self.load_image.call_args_list, [
                    call(str(self.root / name)) for name in resources.IMAGE_FILES.values()
                ])
                for name, image in self.images.items():
                    self.assertIs(image.texture, getattr(sentinel, name + "_texture"))
                self.destroy_texture.assert_not_called()

    def test_missing_file_error_includes_path(self):
        self.is_file.return_value = False

        with self.assertRaises(resources.ResourceError) as caught:
            resources.load_images(self.root)

        self.assertIn(str(self.root / "newfirststage.png"), str(caught.exception))
        self.load_image.assert_not_called()
        self.destroy_texture.assert_not_called()

    def test_decode_error_includes_path_and_preserves_cause(self):
        error = OSError("mock decode failure")
        self.load_image.side_effect = error

        with self.assertRaises(resources.ResourceError) as caught:
            resources.load_images(self.root)

        self.assertIn(str(self.root / "newfirststage.png"), str(caught.exception))
        self.assertIs(caught.exception.__cause__, error)
        self.destroy_texture.assert_not_called()

    def test_partial_load_missing_file_releases_previous_images(self):
        self.is_file.side_effect = [True, False]

        with patch.object(resources, "release_images", wraps=resources.release_images) as release:
            with self.assertRaises(resources.ResourceError) as caught:
                resources.load_images(self.root)

        self.assertIn(str(self.root / "assets/character.png"), str(caught.exception))
        self.load_image.assert_called_once_with(str(self.root / "newfirststage.png"))
        release.assert_called_once()
        self.assertEqual(release.call_args.args[0], {})
        self.assertIsNone(self.background.texture)
        self.destroy_texture.assert_called_once_with(sentinel.background_texture)

    def test_partial_load_decode_error_releases_previous_images(self):
        error = OSError("mock second image decode failure")
        self.load_image.side_effect = [self.background, error]

        with patch.object(resources, "release_images", wraps=resources.release_images) as release:
            with self.assertRaises(resources.ResourceError) as caught:
                resources.load_images(self.root)

        self.assertIn(str(self.root / "assets/character.png"), str(caught.exception))
        self.assertIs(caught.exception.__cause__, error)
        release.assert_called_once()
        self.assertEqual(release.call_args.args[0], {})
        self.assertIsNone(self.background.texture)
        self.destroy_texture.assert_called_once_with(sentinel.background_texture)

    def test_missing_health_bar_releases_previous_images(self):
        self.is_file.side_effect = [True, True, False]

        with self.assertRaises(resources.ResourceError) as caught:
            resources.load_images(self.root)

        self.assertIn(str(self.root / "hp_preview_100.png"), str(caught.exception))
        self.assertEqual(self.load_image.call_args_list, [
            call(str(self.root / "newfirststage.png")),
            call(str(self.root / "assets/character.png")),
        ])
        self.assertEqual(self.destroy_texture.call_args_list, [
            call(sentinel.background_texture), call(sentinel.character_texture),
        ])
        self.assertIsNone(self.background.texture)
        self.assertIsNone(self.character.texture)

    def test_corrupt_health_bar_releases_previous_images(self):
        error = OSError("mock health bar decode failure")
        self.load_image.side_effect = [self.background, self.character, error]

        with self.assertRaises(resources.ResourceError) as caught:
            resources.load_images(self.root)

        self.assertIn(str(self.root / "hp_preview_100.png"), str(caught.exception))
        self.assertIs(caught.exception.__cause__, error)
        self.load_image.assert_called_with(str(self.root / "hp_preview_100.png"))
        self.assertEqual(self.destroy_texture.call_args_list, [
            call(sentinel.background_texture), call(sentinel.character_texture),
        ])
        self.assertIsNone(self.background.texture)
        self.assertIsNone(self.character.texture)

    def test_missing_or_corrupt_items_and_stage_images_release_previous_images(self):
        originals = [image.texture for image in self.images.values()]
        fixtures = list(self.images.values())
        for index, name in enumerate(("dagger", "steel_pipe", "second_background", "portal"), start=3):
            for corrupt in (False, True):
                with self.subTest(item=name, corrupt=corrupt):
                    for image, texture in zip(fixtures, originals):
                        image.texture = texture
                    self.destroy_texture.reset_mock()
                    self.load_image.reset_mock(side_effect=True)
                    self.is_file.reset_mock()
                    error = OSError("mock item decode failure")
                    self.is_file.side_effect = None if corrupt else [True] * index + [False]
                    self.load_image.side_effect = fixtures[:index] + ([error] if corrupt else [])

                    with self.assertRaises(resources.ResourceError) as caught:
                        resources.load_images(self.root)

                    path = self.root / resources.IMAGE_FILES[name]
                    self.assertIn(str(path), str(caught.exception))
                    if corrupt:
                        self.assertIs(caught.exception.__cause__, error)
                    paths = list(resources.IMAGE_FILES.values())[:index + int(corrupt)]
                    self.assertEqual(self.load_image.call_args_list, [
                        call(str(self.root / filename)) for filename in paths
                    ])
                    self.assertEqual(self.destroy_texture.call_args_list, [
                        call(texture) for texture in originals[:index]
                    ])
                    self.assertTrue(all(image.texture is None for image in fixtures[:index]))
                    for image, texture in zip(fixtures[index:], originals[index:]):
                        self.assertIs(image.texture, texture)

    def test_release_nulls_each_texture_before_destroy_and_clears_images(self):
        images = dict(self.images, already_released=Mock(texture=None))
        originals = {image.texture: image for image in self.images.values()}

        def destroy(texture):
            self.assertIsNone(originals[texture].texture)

        self.destroy_texture.side_effect = destroy
        resources.release_images(images)

        self.assertEqual(images, {})
        self.assertCountEqual(self.destroy_texture.call_args_list, [
            call(texture) for texture in originals
        ])
        self.assertTrue(all(image.texture is None for image in originals.values()))

    def test_release_is_idempotent_even_when_image_is_retained(self):
        images = {"background": self.background}

        resources.release_images(images)
        resources.release_images(images)
        images["retained_background"] = self.background
        resources.release_images(images)

        self.assertEqual(images, {})
        self.assertIsNone(self.background.texture)
        self.destroy_texture.assert_called_once_with(sentinel.background_texture)

    def test_release_empty_images_is_safe(self):
        images = {}

        resources.release_images(images)

        self.assertEqual(images, {})
        self.destroy_texture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
