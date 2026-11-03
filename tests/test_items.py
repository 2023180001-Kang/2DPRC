from random import Random
import unittest

from game import spawn_items
from settings import GROUND_Y, ITEM_WIDTHS, PLAYER_HALF_WIDTH, WIDTH


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

    def test_new_spawns_vary_positions_and_counts(self):
        rng = Random(17)
        layouts = [tuple(spawn_items(rng)) for _ in range(20)]
        self.assertGreater(len(set(layouts)), 1)
        self.assertGreater(len({len(items) for items in layouts}), 1)
