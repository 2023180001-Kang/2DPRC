from random import Random
import unittest
from unittest.mock import Mock

from PIL import Image

from game import Item, spawn_items
from rendering import draw_items
from resources import IMAGE_FILES, ROOT
from settings import (
    CHARACTER_SCALE, FRAME_COUNT, FRAME_HEIGHT, FRAME_ROWS, FRAME_WIDTH,
    GROUND_Y, ITEM_WIDTHS, PLAYER_HALF_WIDTH, PORTAL_SPAWN_PADDING, PORTAL_WIDTH, PORTAL_X,
    SECOND_STAGE_SPAWN_X, WIDTH,
)


class ItemTests(unittest.TestCase):
    def test_count_and_both_types_over_many_seeds(self):
        counts = set()
        for seed in range(200):
            with self.subTest(seed=seed):
                items = spawn_items(Random(seed))
                self.assertIn(len(items), (3, 4, 5))
                self.assertEqual({item.kind for item in items}, set(ITEM_WIDTHS))
                counts.add(len(items))
        self.assertEqual(counts, {3, 4, 5})

    def test_floor_bounds_spacing_and_clear_start(self):
        for seed in range(100):
            with self.subTest(seed=seed):
                items = sorted(spawn_items(Random(seed)), key=lambda item: item.x)
                for item in items:
                    half_width = ITEM_WIDTHS[item.kind] / 2
                    self.assertEqual(item.foot_y, GROUND_Y)
                    self.assertGreaterEqual(item.x - half_width, 0)
                    self.assertLessEqual(item.x + half_width, WIDTH)
                    self.assertGreater(abs(item.x - WIDTH / 2), PLAYER_HALF_WIDTH + half_width)
                for left, right in zip(items, items[1:]):
                    self.assertGreater(right.x - left.x,
                                       (ITEM_WIDTHS[left.kind] + ITEM_WIDTHS[right.kind]) / 2)

    def test_seed_reproduces_layout(self):
        self.assertEqual(spawn_items(Random(17)), spawn_items(Random(17)))

    def test_first_map_items_keep_their_full_width_outside_portal_and_padding(self):
        counts = set()
        for seed in range(500):
            with self.subTest(seed=seed):
                items = spawn_items(Random(seed))
                self.assertIn(len(items), (3, 4, 5))
                self.assertEqual({item.kind for item in items}, set(ITEM_WIDTHS))
                for item in items:
                    self.assertGreater(abs(item.x - PORTAL_X),
                                       PORTAL_WIDTH / 2 + PORTAL_SPAWN_PADDING + ITEM_WIDTHS[item.kind] / 2)
                counts.add(len(items))
        self.assertEqual(counts, {3, 4, 5})

    def test_second_map_can_spawn_in_right_area_without_a_portal(self):
        used_right_area = False
        for seed in range(100):
            items = spawn_items(Random(seed), spawn_x=SECOND_STAGE_SPAWN_X, stage_number=2)
            self.assertIn(len(items), (3, 4, 5))
            used_right_area |= any(abs(item.x - PORTAL_X) < PORTAL_WIDTH / 2 for item in items)
        self.assertTrue(used_right_area)

    def test_new_spawns_vary_positions_and_counts(self):
        rng = Random(17)
        layouts = [tuple(spawn_items(rng)) for _ in range(20)]
        self.assertGreater(len(set(layouts)), 1)
        self.assertGreater(len({len(items) for items in layouts}), 1)

    def test_rendering_uses_correct_image_aspect_ratio_and_floor(self):
        for kind, width in ITEM_WIDTHS.items():
            with self.subTest(kind=kind):
                with Image.open(ROOT / IMAGE_FILES[kind]) as source:
                    image = Mock(w=source.width, h=source.height)
                    self.assertEqual(source.convert("RGBA").getchannel("A").getextrema()[0], 0)
                item = Item(kind, 200)
                draw_items({kind: image}, [item])
                image.draw.assert_called_once()
                x, y, drawn_width, height = image.draw.call_args.args
                self.assertEqual((x, drawn_width), (item.x, width))
                self.assertAlmostEqual(drawn_width / height, image.w / image.h)
                self.assertAlmostEqual(y - height / 2, GROUND_Y)

    def test_items_are_smaller_than_visible_character_in_every_pose(self):
        sizes = []
        with Image.open(ROOT / "assets/character.png") as sheet:
            for row in range(FRAME_ROWS):
                for frame in range(FRAME_COUNT):
                    bounds = sheet.crop((frame * FRAME_WIDTH, row * FRAME_HEIGHT,
                                         (frame + 1) * FRAME_WIDTH, (row + 1) * FRAME_HEIGHT)).getbbox()
                    sizes.append(min(bounds[2] - bounds[0], bounds[3] - bounds[1]) * CHARACTER_SCALE)
        for kind, width in ITEM_WIDTHS.items():
            with self.subTest(kind=kind), Image.open(ROOT / IMAGE_FILES[kind]) as source:
                height = width * source.height / source.width
                self.assertLess(max(width, height), min(sizes))

    def test_repeated_rendering_does_not_move_or_respawn_items(self):
        items = spawn_items(Random(17))
        original = tuple(items)
        images = {kind: Mock(w=900, h=300) for kind in ITEM_WIDTHS}
        draw_items(images, items)
        calls = {kind: image.draw.call_args_list[:] for kind, image in images.items()}
        for image in images.values():
            image.reset_mock()
        draw_items(images, items)
        self.assertEqual(tuple(items), original)
        for kind, image in images.items():
            self.assertEqual(image.draw.call_args_list, calls[kind])
