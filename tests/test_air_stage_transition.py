from random import Random
import unittest
from unittest.mock import patch

from game import Controls, Enemy, Item, Player, Stage
from settings import (
    ARROW_X, GRAVITY, GROUND_Y, JUMP_DURATION, JUMP_SPEED,
    STAGE_BACKGROUNDS, STAGE_ENTRY_LEFT_X, STAGE_ENTRY_RIGHT_X,
)


class AirStageTransitionTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("game.spawn_enemies", side_effect=lambda *args, **kwargs: [Enemy(state="DEAD")])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_jump_after_transition_matches_uninterrupted_trajectory_and_landing(self):
        for number, direction, key in ((1, 1, "right"), (2, -1, "left")):
            for speed in (-200, 0, 200):
                with self.subTest(stage=number, speed=speed):
                    controls = Controls(held={key, "lshift", "space"})
                    player = Player(x=ARROW_X[direction], foot_y=GROUND_Y + 192,
                                    vertical_speed=speed, state="JUMP", jump_count=2,
                                    animation_time=(JUMP_SPEED - speed) / GRAVITY,
                                    weapon="dagger", facing=direction)
                    reference = Player(**vars(player))
                    stage = Stage(items=[], number=number)
                    self.assertTrue(stage.try_transition(player, controls, Random(1)))
                    reference.x = STAGE_ENTRY_LEFT_X if direction > 0 else STAGE_ENTRY_RIGHT_X
                    for _ in range(20):
                        player.update(0.05, controls)
                        reference.update(0.05, controls)
                        self.assertEqual(vars(player), vars(reference))
                        self.assertEqual((player.frame, player.row), (reference.frame, reference.row))
                    self.assertTrue(player.grounded)
                    self.assertEqual((player.foot_y, player.vertical_speed, player.jump_count), (GROUND_Y, 0, 0))

    def test_remaining_double_jump_survives_transfer_without_extra_jump_or_hold_repeat(self):
        for number, direction in ((1, 1), (2, -1)):
            for used in (1, 2):
                with self.subTest(stage=number, used=used):
                    player = Player(x=ARROW_X[direction])
                    controls = Controls()
                    for _ in range(used):
                        controls.set_key("space", False)
                        controls.set_key("space", True)
                        player.update(0.1, controls)
                    speed = player.vertical_speed
                    self.assertTrue(Stage(items=[], number=number).try_transition(player, controls))
                    controls.set_key("space", True)
                    player.update(0, controls)
                    self.assertEqual((player.jump_count, player.vertical_speed), (used, speed))
                    controls.set_key("space", False)
                    controls.set_key("space", True)
                    player.update(0, controls)
                    self.assertEqual(player.jump_count, 2)
                    self.assertEqual(player.vertical_speed, JUMP_SPEED if used == 1 else speed)
                    player.update(2 * JUMP_DURATION, controls)
                    self.assertTrue(player.grounded)
                    self.assertEqual(player.jump_count, 0)
                    controls.set_key("space", False)
                    controls.set_key("space", True)
                    player.update(0, controls)
                    self.assertEqual((player.state, player.jump_count), ("JUMP", 1))

    def test_final_stage_inactive_right_arrow_leaves_airborne_state_and_requests_untouched(self):
        stage = Stage(items=[Item("dagger", 500)], number=max(STAGE_BACKGROUNDS))
        player = Player(x=ARROW_X[1], foot_y=GROUND_Y + 200, vertical_speed=-100,
                        state="JUMP", jump_count=2, animation_time=0.6, weapon="steel_pipe", health=2)
        controls = Controls(held={"right", "rshift", "space"},
                            jump_requested=True, pickup_requested=True)
        before_player = vars(player).copy()
        before_controls = dict(vars(controls), held=controls.held.copy())
        before_items = stage.items[:]
        with patch("game.spawn_items") as spawn:
            for _ in range(3):
                self.assertFalse(stage.try_transition(player, controls))
            spawn.assert_not_called()
        self.assertEqual(stage.number, max(STAGE_BACKGROUNDS))
        self.assertEqual(stage.items, before_items)
        self.assertEqual(vars(player), before_player)
        self.assertEqual(vars(controls), before_controls)
