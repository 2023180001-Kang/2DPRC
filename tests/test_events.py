from ctypes import byref, memmove, sizeof
import unittest
from unittest.mock import patch

import sdl2

from events import poll_events
from game import Controls, Player
from settings import GROUND_Y


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

    def key(self, down=True, repeat=False):
        event = sdl2.SDL_Event()
        event.type = sdl2.SDL_KEYDOWN if down else sdl2.SDL_KEYUP
        event.key.keysym.sym = sdl2.SDLK_SPACE
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
        controls = Controls()
        self.key(repeat=True)
        poll_events(controls)
        self.assertFalse(controls.jump_requested)
        self.assertFalse(controls.held)

    def test_focus_loss_clears_pending_jump_and_held_keys(self):
        controls = Controls({"left", "r"})
        self.key()
        self.focus(False)
        poll_events(controls)
        self.assertFalse(controls.jump_requested)
        self.assertFalse(controls.held)
        player = Player()
        player.update(0.1, controls)
        self.assertTrue(player.grounded)

    def test_focus_loss_during_jump_still_allows_landing(self):
        controls, player = Controls(), Player()
        self.key()
        poll_events(controls)
        player.update(0.1, controls)
        self.focus(False)
        poll_events(controls)
        player.update(0.7, controls)
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
