import unittest

from game import Controls, Item, Player
from settings import AIR_DROP_HEIGHT, GROUND_Y, JUMP_DURATION, PICKUP_RADIUS


class PickupTests(unittest.TestCase):
    def test_defaults_and_walking_without_input_do_not_pick_up(self):
        controls, player = Controls(), Player()
        self.assertEqual(PICKUP_RADIUS, 56.0)
        self.assertIsNone(player.weapon)
        self.assertIs(controls.pickup_requested, False)
        items = [Item("dagger", player.x + 30)]
        controls.set_key("right", True)
        player.update(0.1, controls)
        self.assertIs(player.pick_up(items, controls), False)
        self.assertIsNone(player.weapon)

    def test_fresh_press_picks_up_and_consumes_request(self):
        controls, player = Controls(), Player()
        items = [Item("dagger", player.x)]
        controls.set_key("f", True)
        self.assertIs(controls.pickup_requested, True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertIs(controls.pickup_requested, False)
        self.assertEqual(player.weapon, "dagger")
        self.assertEqual(items, [])

    def test_quick_tap_survives_release_and_is_used_once(self):
        controls, player = Controls(), Player()
        items = [Item("dagger", player.x), Item("steel_pipe", player.x)]
        controls.set_key("f", True)
        controls.set_key("f", False)
        self.assertIs(controls.pickup_requested, True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertIs(player.pick_up(items, controls), False)
        self.assertEqual((player.weapon, items), ("dagger", [Item("steel_pipe", player.x)]))

    def test_holding_and_repeat_require_release_before_next_pickup(self):
        controls, player = Controls(), Player()
        items = [Item("dagger", player.x), Item("steel_pipe", player.x)]
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)
        for _ in range(3):
            controls.set_key("f", True)
            self.assertIs(controls.pickup_requested, False)
            self.assertIs(player.pick_up(items, controls), False)
        self.assertEqual(player.weapon, "dagger")
        controls.set_key("f", False)
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertEqual(player.weapon, "steel_pipe")

    def test_unfocused_press_is_ignored(self):
        controls, player = Controls(focused=False), Player()
        items = [Item("dagger", player.x)]
        controls.set_key("f", True)
        self.assertIs(controls.pickup_requested, False)
        self.assertNotIn("f", controls.held)
        self.assertIs(player.pick_up(items, controls), False)
        controls.focused = True
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)

    def test_inclusive_radius_uses_two_dimensional_centers(self):
        for dx, dy, expected in ((56, 0, True), (-56, 0, True), (0, 56, True),
                                 (30, 40, True), (40, 40, False),
                                 (56.001, 0, False), (0, 56.001, False)):
            with self.subTest(dx=dx, dy=dy):
                controls, player = Controls(), Player()
                item = Item("dagger", player.x + dx, player.foot_y + dy)
                items = [item]
                controls.set_key("f", True)
                self.assertIs(player.pick_up(items, controls), expected)
                self.assertEqual(items, [] if expected else [item])
                self.assertEqual(player.weapon, "dagger" if expected else None)
                self.assertIs(controls.pickup_requested, False)

    def test_nearest_item_uses_both_coordinates_not_list_order(self):
        controls, player = Controls(), Player()
        farther = Item("dagger", player.x + 1, GROUND_Y + 50)
        nearest = Item("steel_pipe", player.x + 20)
        items = [farther, nearest, Item("dagger", player.x + 55)]
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertEqual(player.weapon, "steel_pipe")
        self.assertEqual(items, [farther, Item("dagger", player.x + 55)])

    def test_equal_distance_selects_first_index(self):
        controls, player = Controls(), Player()
        first = Item("dagger", player.x + 30, GROUND_Y + 40)
        second = Item("steel_pipe", player.x - 50)
        items = [first, second]
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertEqual((player.weapon, items), ("dagger", [second]))

    def test_empty_list_consumes_request_without_queueing(self):
        controls, player = Controls(), Player()
        items = []
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), False)
        self.assertIs(controls.pickup_requested, False)
        items.append(Item("dagger", player.x))
        self.assertIs(player.pick_up(items, controls), False)
        self.assertIsNone(player.weapon)
        self.assertEqual(len(items), 1)

    def test_out_of_range_request_is_consumed_before_later_approach(self):
        controls, player = Controls(), Player()
        item = Item("dagger", player.x + 100)
        items = [item]
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), False)
        self.assertIs(controls.pickup_requested, False)
        controls.set_key("right", True)
        player.update(0.5, controls)
        self.assertLess(abs(item.x - player.x), PICKUP_RADIUS)
        self.assertIs(player.pick_up(items, controls), False)
        self.assertEqual(items, [item])
        self.assertIsNone(player.weapon)

    def test_only_grounded_players_pick_up_and_air_requests_do_not_queue(self):
        for height, speed in ((GROUND_Y + 1, 0), (GROUND_Y, 1), (GROUND_Y, -1)):
            with self.subTest(height=height, speed=speed):
                controls = Controls()
                player = Player(foot_y=height, vertical_speed=speed)
                items = [Item("dagger", player.x)]
                controls.set_key("f", True)
                self.assertIs(player.pick_up(items, controls), False)
                self.assertIs(controls.pickup_requested, False)
                player.update(JUMP_DURATION, controls)
                self.assertTrue(player.grounded)
                self.assertIs(player.pick_up(items, controls), False)
                self.assertIsNone(player.weapon)
                self.assertEqual(items, [Item("dagger", player.x)])

    def test_swap_appends_old_weapon_at_feet_and_conserves_count(self):
        controls, player = Controls(), Player()
        untouched = Item("steel_pipe", player.x + 300)
        items = [Item("dagger", player.x), Item("steel_pipe", player.x + 40, GROUND_Y + 10), untouched]
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertEqual(len(items) + int(player.weapon is not None), 3)
        player.x += 10
        controls.set_key("f", False)
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertIs(controls.pickup_requested, False)
        self.assertEqual(player.weapon, "steel_pipe")
        self.assertEqual(items, [untouched, Item("dagger", player.x, GROUND_Y)])
        self.assertEqual(len(items) + int(player.weapon is not None), 3)

    def test_weapon_persists_through_running_jumping_and_landing(self):
        controls, player = Controls(), Player()
        items = [Item("dagger", player.x)]
        controls.set_key("f", True)
        self.assertIs(player.pick_up(items, controls), True)
        controls.set_key("f", False)
        for key in ("right", "lshift"):
            controls.set_key(key, True)
        player.update(0.1, controls)
        self.assertEqual((player.state, player.weapon), ("RUN", "dagger"))
        controls.set_key("space", True)
        player.update(JUMP_DURATION / 2, controls)
        self.assertEqual((player.state, player.weapon), ("JUMP", "dagger"))
        player.update(JUMP_DURATION / 2, controls)
        self.assertTrue(player.grounded)
        self.assertEqual((player.weapon, items), ("dagger", []))

    def test_same_frame_pickup_before_update_allows_jump(self):
        controls, player = Controls(), Player()
        items = [Item("steel_pipe", player.x)]
        for key in ("space", "f"):
            controls.set_key(key, True)
        self.assertIs(player.pick_up(items, controls), True)
        self.assertIs(controls.jump_requested, True)
        player.update(0, controls)
        self.assertFalse(player.grounded)
        self.assertEqual((player.state, player.weapon, items), ("JUMP", "steel_pipe", []))

    def test_no_pickup_target_drops_each_weapon_at_feet_and_conserves_items(self):
        for weapon in ("dagger", "steel_pipe"):
            for has_distant_item in (False, True):
                with self.subTest(weapon=weapon, distant=has_distant_item):
                    player, controls = Player(weapon=weapon), Controls()
                    items = [Item("dagger", player.x + PICKUP_RADIUS + 0.001)] if has_distant_item else []
                    original = items[:]
                    controls.set_key("f", True)
                    self.assertTrue(player.pick_up(items, controls))
                    self.assertIsNone(player.weapon)
                    self.assertEqual(items, original + [Item(weapon, player.x, GROUND_Y)])
                    self.assertFalse(controls.pickup_requested)

    def test_target_at_range_boundary_swaps_instead_of_only_dropping(self):
        player, controls = Player(weapon="dagger"), Controls()
        items = [Item("steel_pipe", player.x + PICKUP_RADIUS)]
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(items, controls))
        self.assertEqual(player.weapon, "steel_pipe")
        self.assertEqual(items, [Item("dagger", player.x)])

    def test_drop_requires_release_before_repickup_and_does_not_repeat(self):
        player, controls, items = Player(weapon="steel_pipe"), Controls(), []
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(items, controls))
        for _ in range(3):
            controls.set_key("f", True)
            self.assertFalse(player.pick_up(items, controls))
            self.assertIsNone(player.weapon)
            self.assertEqual(items, [Item("steel_pipe", player.x)])
        controls.set_key("f", False)
        controls.set_key("f", True)
        self.assertTrue(player.pick_up(items, controls))
        self.assertEqual((player.weapon, items), ("steel_pipe", []))

    def test_airborne_f_drops_immediately_and_does_not_queue_repickup(self):
        player, controls, items = Player(weapon="dagger"), Controls(), []
        controls.set_key("space", True)
        player.update(JUMP_DURATION / 4, controls)
        controls.set_key("f", True)
        drop_y = player.foot_y + AIR_DROP_HEIGHT
        self.assertTrue(player.pick_up(items, controls))
        self.assertFalse(controls.pickup_requested)
        player.update(JUMP_DURATION, controls)
        self.assertFalse(player.pick_up(items, controls))
        self.assertIsNone(player.weapon)
        self.assertEqual(items, [Item("dagger", player.x, drop_y, falling=True)])

    def test_no_request_or_unfocused_f_does_not_drop_held_weapon(self):
        player, controls, items = Player(weapon="dagger"), Controls(focused=False), []
        self.assertFalse(player.pick_up(items, controls))
        controls.set_key("f", True)
        self.assertFalse(player.pick_up(items, controls))
        self.assertEqual((player.weapon, items), ("dagger", []))

    def test_same_frame_drop_and_jump_leaves_item_on_ground(self):
        player, controls, items = Player(weapon="dagger"), Controls(), []
        for key in ("f", "space"):
            controls.set_key(key, True)
        self.assertTrue(player.pick_up(items, controls))
        player.update(0.1, controls)
        self.assertFalse(player.grounded)
        self.assertIsNone(player.weapon)
        self.assertEqual(items, [Item("dagger", player.x, GROUND_Y)])
