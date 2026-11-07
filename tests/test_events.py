from ctypes import byref, memmove, sizeof
import unittest
from unittest.mock import patch

import sdl2

from events import KEY_NAMES, poll_events
from game import Controls, Item, Player
from settings import GROUND_Y, JUMP_DURATION, JUMP_SPEED


class EventTests(unittest.TestCase):
    def setUp(self):
        self.queue = []
        self.poll = patch("events.sdl2.SDL_PollEvent", side_effect=self.next_event)
        self.poll.start()
        self.addCleanup(self.poll.stop)

    def next_event(self, pointer):
        if not self.queue:
            return 0
        memmove(pointer, byref(self.queue.pop(0)), sizeof(sdl2.SDL_Event))
        return 1

    def key(self, down=True, repeat=False, keycode=sdl2.SDLK_SPACE):
        event = sdl2.SDL_Event()
        event.type = sdl2.SDL_KEYDOWN if down else sdl2.SDL_KEYUP
        event.key.keysym.sym = keycode
        event.key.repeat = repeat
        self.queue.append(event)

    def focus(self, gained):
        event = sdl2.SDL_Event()
        event.type = sdl2.SDL_WINDOWEVENT
        event.window.event = (sdl2.SDL_WINDOWEVENT_FOCUS_GAINED if gained
                              else sdl2.SDL_WINDOWEVENT_FOCUS_LOST)
        self.queue.append(event)

    def test_space_tap_in_one_event_batch_is_preserved(self):
        controls = Controls()
        self.key()
        self.key(down=False)
        self.assertTrue(poll_events(controls))
        self.assertTrue(controls.jump_requested)
        self.assertNotIn("space", controls.held)

    def test_repeated_sdl_keydown_does_not_request_jump(self):
        for keycode in (sdl2.SDLK_SPACE, sdl2.SDLK_f, sdl2.SDLK_a, sdl2.SDLK_r, sdl2.SDLK_h,
                        sdl2.SDLK_LSHIFT, sdl2.SDLK_RSHIFT):
            with self.subTest(keycode=keycode):
                controls = Controls()
                self.key(repeat=True, keycode=keycode)
                poll_events(controls)
                self.assertFalse(controls.jump_requested)
                self.assertFalse(controls.pickup_requested)
                self.assertFalse(controls.attack_requested)
                self.assertFalse(controls.restart_requested)
                self.assertFalse(controls.hit_test_requested)
                self.assertFalse(controls.held)
                self.key(keycode=keycode)
                poll_events(controls)
                controls.jump_requested = False
                controls.pickup_requested = False
                controls.attack_requested = False
                controls.restart_requested = controls.hit_test_requested = False
                for _ in range(3):
                    self.key(repeat=True, keycode=keycode)
                poll_events(controls)
                self.assertEqual(controls.held, {KEY_NAMES[keycode]})
                self.assertFalse(controls.jump_requested)
                self.assertFalse(controls.pickup_requested)
                self.assertFalse(controls.attack_requested)
                self.assertFalse(controls.restart_requested)
                self.assertFalse(controls.hit_test_requested)
                self.key(down=False, keycode=keycode)
                poll_events(controls)
                self.assertFalse(controls.held)
                self.assertIs(controls.running, False)

    def test_shift_mapping_and_releases_in_either_order(self):
        self.assertEqual(KEY_NAMES[sdl2.SDLK_LSHIFT], "lshift")
        self.assertEqual(KEY_NAMES[sdl2.SDLK_RSHIFT], "rshift")
        self.assertEqual(KEY_NAMES[sdl2.SDLK_r], "r")
        for first, last in ((sdl2.SDLK_LSHIFT, sdl2.SDLK_RSHIFT),
                            (sdl2.SDLK_RSHIFT, sdl2.SDLK_LSHIFT)):
            with self.subTest(first=first):
                controls, player = Controls(), Player()
                for keycode in (sdl2.SDLK_r, sdl2.SDLK_RIGHT):
                    self.key(keycode=keycode)
                poll_events(controls)
                player.update(0, controls)
                self.assertEqual(controls.held, {"right", "r"})
                self.assertEqual(player.state, "WALK")
                for keycode in (first, last):
                    self.key(keycode=keycode)
                poll_events(controls)
                self.assertEqual(controls.held, {"right", "r", "lshift", "rshift"})
                self.assertIs(controls.running, True)
                self.key(down=False, keycode=first)
                poll_events(controls)
                player.update(0, controls)
                self.assertEqual(controls.held, {"right", "r", KEY_NAMES[last]})
                self.assertIs(controls.running, True)
                self.assertEqual(player.state, "RUN")
                self.key(down=False, keycode=last)
                poll_events(controls)
                player.update(0, controls)
                self.assertEqual(controls.held, {"right", "r"})
                self.assertIs(controls.running, False)
                self.assertEqual(player.state, "WALK")

    def test_focus_loss_clears_pending_jump_and_held_keys(self):
        controls = Controls()
        for keycode in (sdl2.SDLK_LEFT, sdl2.SDLK_LSHIFT, sdl2.SDLK_RSHIFT):
            self.key(keycode=keycode)
        self.key()
        self.key(keycode=sdl2.SDLK_f)
        poll_events(controls)
        self.assertEqual(controls.held, {"left", "lshift", "rshift", "space", "f"})
        self.assertIs(controls.running, True)
        self.focus(False)
        poll_events(controls)
        self.assertFalse(controls.jump_requested)
        self.assertFalse(controls.pickup_requested)
        self.assertFalse(controls.held)
        self.assertIs(controls.running, False)
        player = Player()
        player.update(0.1, controls)
        self.assertTrue(player.grounded)

    def test_r_and_h_taps_survive_release_but_not_focus_loss(self):
        for keycode, requested in ((sdl2.SDLK_r, "restart_requested"),
                                   (sdl2.SDLK_h, "hit_test_requested")):
            controls = Controls()
            self.key(keycode=keycode)
            self.key(down=False, keycode=keycode)
            poll_events(controls)
            self.assertTrue(getattr(controls, requested))
            self.assertFalse(controls.held)
            self.focus(False)
            self.key(keycode=keycode)
            poll_events(controls)
            self.assertFalse(getattr(controls, requested))
            self.assertFalse(controls.held)
            self.focus(True)
            self.key(keycode=keycode)
            poll_events(controls)
            self.assertTrue(getattr(controls, requested))

    def test_focus_loss_during_jump_still_allows_landing(self):
        controls, player = Controls(), Player()
        self.key()
        poll_events(controls)
        player.update(0.1, controls)
        self.focus(False)
        poll_events(controls)
        player.update(JUMP_DURATION - 0.1, controls)
        self.assertEqual((player.foot_y, player.state), (GROUND_Y, "IDLE"))

    def test_space_requires_focus_and_works_after_regaining_focus(self):
        controls = Controls()
        self.focus(False)
        self.key()
        poll_events(controls)
        self.assertFalse(controls.jump_requested)
        self.focus(True)
        self.key()
        poll_events(controls)
        self.assertTrue(controls.jump_requested)

    def test_f_tap_in_one_batch_picks_up_once(self):
        controls, player = Controls(), Player()
        items = [Item("dagger", player.x)]
        self.key(keycode=sdl2.SDLK_f)
        self.key(down=False, keycode=sdl2.SDLK_f)
        poll_events(controls)
        self.assertTrue(controls.pickup_requested)
        self.assertNotIn("f", controls.held)
        self.assertTrue(player.pick_up(items, controls))
        self.assertEqual((player.weapon, items), ("dagger", []))
        self.assertFalse(player.pick_up(items, controls))

    def test_a_tap_attacks_and_focus_loss_discards_pending_attack(self):
        controls, player = Controls(), Player(weapon="dagger")
        self.key(keycode=sdl2.SDLK_a)
        self.key(down=False, keycode=sdl2.SDLK_a)
        poll_events(controls)
        self.assertTrue(controls.attack_requested)
        player.update(0, controls)
        self.assertTrue(player.attacking)
        self.key(keycode=sdl2.SDLK_a)
        self.focus(False)
        poll_events(controls)
        self.assertFalse(controls.attack_requested)
        self.assertFalse(controls.held)
        player.update(0.1, controls)
        self.assertAlmostEqual(player.attack_time, 0.1)

    def test_z_is_no_longer_an_attack_key(self):
        controls = Controls()
        self.key(keycode=sdl2.SDLK_z)
        self.key(down=False, keycode=sdl2.SDLK_z)
        poll_events(controls)
        self.assertFalse(controls.attack_requested)
        self.assertFalse(controls.held)

    def test_focus_loss_discards_pickup_and_f_requires_new_press(self):
        controls, player = Controls(), Player()
        items = [Item("steel_pipe", player.x)]
        self.key(keycode=sdl2.SDLK_f)
        self.focus(False)
        self.key(keycode=sdl2.SDLK_f)
        poll_events(controls)
        self.assertFalse(controls.pickup_requested)
        self.assertFalse(player.pick_up(items, controls))
        self.focus(True)
        self.key(keycode=sdl2.SDLK_f)
        poll_events(controls)
        self.assertTrue(player.pick_up(items, controls))

    def test_fresh_airborne_space_allows_only_second_launch(self):
        controls, player = Controls(), Player()
        self.key()
        poll_events(controls)
        player.update(0, controls)
        self.assertEqual(player.jump_count, 1)
        self.key(repeat=True)
        poll_events(controls)
        player.update(0, controls)
        self.assertEqual(player.jump_count, 1)
        self.key(down=False)
        self.key()
        poll_events(controls)
        player.update(0, controls)
        self.assertEqual((player.jump_count, player.vertical_speed), (2, JUMP_SPEED))
        player.update(0.1, controls)
        speed = player.vertical_speed
        self.key(down=False)
        self.key()
        poll_events(controls)
        player.update(0, controls)
        self.assertEqual((player.jump_count, player.vertical_speed), (2, speed))
        self.assertFalse(controls.jump_requested)

    def test_focus_changes_preserve_used_jumps_until_landing(self):
        for used in (1, 2):
            with self.subTest(used=used):
                controls, player = Controls(), Player()
                for _ in range(used):
                    self.key()
                    self.key(down=False)
                    poll_events(controls)
                    player.update(0, controls)
                player.update(0.1, controls)
                speed = player.vertical_speed
                self.focus(False)
                poll_events(controls)
                self.assertEqual(player.jump_count, used)
                self.focus(True)
                self.key()
                self.key(down=False)
                poll_events(controls)
                player.update(0, controls)
                self.assertEqual(player.jump_count, 2)
                self.assertEqual(player.vertical_speed, JUMP_SPEED if used == 1 else speed)
                player.update(2 * JUMP_DURATION, controls)
                self.assertEqual(player.jump_count, 0)
                self.key()
                self.key(down=False)
                poll_events(controls)
                player.update(0, controls)
                self.assertEqual(player.jump_count, 1)
