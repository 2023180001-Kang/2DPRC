import unittest
from unittest.mock import Mock, patch

from game import Controls, Item, Player
from rendering import draw_pickup_hint
from settings import GROUND_Y, PICKUP_HINT_GAP, PICKUP_HINT_SIZE, PICKUP_RADIUS


class PickupHintTests(unittest.TestCase):
    def setUp(self):
        self.images = {"dagger": Mock(w=880, h=200), "steel_pipe": Mock(w=1280, h=200)}
        patcher = patch("rendering.draw_rectangle")
        self.rectangle = patcher.start()
        self.addCleanup(patcher.stop)

    def test_hint_matches_actual_nearest_target_with_ties_and_range_boundary(self):
        player = Player()
        for items in ([Item("dagger", player.x + PICKUP_RADIUS)],
                      [Item("dagger", player.x + 1, GROUND_Y + 50), Item("steel_pipe", player.x + 20)],
                      [Item("dagger", player.x - 30), Item("steel_pipe", player.x + 30)]):
            with self.subTest(items=items):
                target = draw_pickup_hint(self.images, items, player)
                self.assertIs(target, items[player.pickup_target(items)])
                controls = Controls(pickup_requested=True)
                player.pick_up(items, controls)
                self.assertEqual(player.weapon, target.kind)

    def test_no_hint_without_a_pickable_target_or_in_air(self):
        for player, items in ((Player(), []),
                              (Player(), [Item("dagger", Player().x + PICKUP_RADIUS + 0.001)]),
                              (Player(foot_y=GROUND_Y + 1), [Item("dagger", Player().x)]),
                              (Player(vertical_speed=1), [Item("dagger", Player().x)])):
            with self.subTest(player=player, items=items):
                self.assertIsNone(draw_pickup_hint(self.images, items, player))
                self.rectangle.assert_not_called()

    def test_small_keycap_is_above_item_and_rendering_does_not_change_state(self):
        player = Player(weapon="steel_pipe")
        items = [Item("dagger", player.x + 40)]
        original = items[:]
        target = draw_pickup_hint(self.images, items, player)
        left, bottom, right, top = self.rectangle.call_args_list[0].args[:4]
        self.assertEqual((left + right) / 2, target.x)
        self.assertEqual((right - left, top - bottom), (PICKUP_HINT_SIZE, PICKUP_HINT_SIZE))
        self.assertEqual(bottom, GROUND_Y + 10 + PICKUP_HINT_GAP)
        self.assertEqual(items, original)
        self.assertEqual(player.weapon, "steel_pipe")

    def test_hint_disappears_on_pickup_and_reappears_after_drop(self):
        player, controls = Player(), Controls(pickup_requested=True)
        items = [Item("dagger", player.x)]
        self.assertIsNotNone(draw_pickup_hint(self.images, items, player))
        player.pick_up(items, controls)
        self.assertIsNone(draw_pickup_hint(self.images, items, player))
        controls.pickup_requested = True
        player.pick_up(items, controls)
        self.assertIs(draw_pickup_hint(self.images, items, player), items[0])
        player.x += PICKUP_RADIUS + 1
        self.assertIsNone(draw_pickup_hint(self.images, items, player))
