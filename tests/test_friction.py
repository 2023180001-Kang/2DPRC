from math import exp, log1p, sqrt
import unittest

from game import Controls, Player
from settings import AIR_DRAG, GRAVITY, GROUND_DRAG, GROUND_FRICTION, GROUND_Y, RUN_SPEED


class FrictionTests(unittest.TestCase):
    def test_ground_friction_slows_faster_at_high_speed_and_eases_near_a_stop(self):
        fast, slow = Player(horizontal_speed=900), Player(horizontal_speed=300)
        fast.update(0.05, Controls())
        slow.update(0.05, Controls())
        self.assertGreater(900 - fast.horizontal_speed, 300 - slow.horizontal_speed)
        previous_drop = 900 - fast.horizontal_speed
        previous_speed = fast.horizontal_speed
        fast.update(0.05, Controls())
        self.assertLess(previous_speed - fast.horizontal_speed, previous_drop)

    def test_top_speed_slides_about_134_pixels_and_stops_in_about_point_four_seconds(self):
        for sign in (-1, 1):
            player = Player(horizontal_speed=sign * RUN_SPEED)
            start = player.x
            player.update(0.4, Controls())
            self.assertGreater(sign * player.horizontal_speed, 0)
            self.assertLess(abs(player.horizontal_speed), 3)
            player.update(0.01, Controls())
            self.assertEqual((player.horizontal_speed, player.state), (0, "IDLE"))
            stop_time = log1p(GROUND_DRAG * RUN_SPEED / GROUND_FRICTION) / GROUND_DRAG
            distance = (RUN_SPEED - GROUND_FRICTION * stop_time) / GROUND_DRAG
            self.assertAlmostEqual(sign * (player.x - start), distance)
            self.assertGreater(distance, 134)
            self.assertLess(distance, 135)

    def test_friction_never_accelerates_or_reverses_unpowered_motion(self):
        for speed in (-900, -180, -0.01, 0, 0.01, 180, 900):
            for duration in (0, 0.001, 0.05, 0.2, 10):
                with self.subTest(speed=speed, duration=duration):
                    player = Player(horizontal_speed=speed)
                    player.update(duration, Controls())
                    self.assertLessEqual(abs(player.horizontal_speed), abs(speed))
                    self.assertGreaterEqual(player.horizontal_speed * speed, 0)
                    self.assertGreaterEqual((player.x - 640) * speed, -1e-9)

    def test_ground_stop_is_independent_of_frame_splits(self):
        reference = Player(horizontal_speed=RUN_SPEED)
        reference.update(0.5, Controls())
        for steps in (7, 30, 60, 144, 1000):
            player = Player(horizontal_speed=RUN_SPEED)
            for _ in range(steps):
                player.update(0.5 / steps, Controls())
            self.assertAlmostEqual(player.x, reference.x, places=8)
            self.assertEqual(player.horizontal_speed, 0)

    def test_air_drag_is_weaker_than_floor_friction(self):
        ground = Player(x=200, horizontal_speed=RUN_SPEED)
        air = Player(x=200, foot_y=GROUND_Y + 1000, horizontal_speed=RUN_SPEED)
        ground.update(0.2, Controls())
        air.update(0.2, Controls())
        self.assertGreater(air.horizontal_speed, ground.horizontal_speed)
        self.assertAlmostEqual(air.horizontal_speed, RUN_SPEED * exp(-AIR_DRAG * 0.2))
        self.assertGreater(air.x, ground.x)

    def test_jump_launch_uses_air_drag_from_the_first_frame(self):
        player = Player(horizontal_speed=600)
        player.update(0.1, Controls(jump_requested=True))
        self.assertFalse(player.grounded)
        self.assertAlmostEqual(player.horizontal_speed, 600 * exp(-AIR_DRAG * 0.1))

    def test_landing_splits_air_drag_and_ground_friction_at_actual_touchdown(self):
        height, vertical_speed, speed = 100, -150, 500
        landing_time = (vertical_speed + sqrt(vertical_speed ** 2 + 2 * GRAVITY * height)) / GRAVITY
        whole = Player(x=400, foot_y=GROUND_Y + height, vertical_speed=vertical_speed, horizontal_speed=speed)
        whole.update(0.6, Controls())
        split = Player(x=400, foot_y=GROUND_Y + height, vertical_speed=vertical_speed, horizontal_speed=speed)
        split.update(landing_time, Controls())
        self.assertAlmostEqual(split.horizontal_speed, speed * exp(-AIR_DRAG * landing_time))
        split.update(0.6 - landing_time, Controls())
        self.assertAlmostEqual(whole.x, split.x, places=8)
        self.assertEqual(whole.horizontal_speed, 0)
        for steps in (30, 60, 144):
            player = Player(x=400, foot_y=GROUND_Y + height, vertical_speed=vertical_speed, horizontal_speed=speed)
            for _ in range(steps):
                player.update(0.6 / steps, Controls())
            self.assertAlmostEqual(player.x, whole.x, places=8)
            self.assertEqual(player.horizontal_speed, 0)

    def test_opposed_keys_apply_friction_and_input_can_resume_mid_slide(self):
        player = Player(horizontal_speed=RUN_SPEED)
        controls = Controls({"left", "right", "lshift"})
        player.update(0.1, controls)
        speed = player.horizontal_speed
        self.assertGreater(speed, 0)
        self.assertLess(speed, RUN_SPEED)
        controls.set_key("left", False)
        player.update(0, controls)
        self.assertEqual(player.horizontal_speed, speed)
        player.update(0.05, controls)
        self.assertGreater(player.horizontal_speed, speed)
