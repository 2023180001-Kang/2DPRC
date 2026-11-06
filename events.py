"""Poll SDL events directly so focus-loss events are not discarded."""

from ctypes import byref

import sdl2

KEY_NAMES = {
    sdl2.SDLK_LEFT: "left", sdl2.SDLK_RIGHT: "right",
    sdl2.SDLK_LSHIFT: "lshift", sdl2.SDLK_RSHIFT: "rshift",
    sdl2.SDLK_SPACE: "space", sdl2.SDLK_f: "f", sdl2.SDLK_z: "z",
}


def poll_events(controls):
    running = True
    event = sdl2.SDL_Event()
    while sdl2.SDL_PollEvent(byref(event)):
        if event.type == sdl2.SDL_QUIT:
            running = False
        elif event.type == sdl2.SDL_WINDOWEVENT:
            if event.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
                running = False
            elif event.window.event == sdl2.SDL_WINDOWEVENT_FOCUS_LOST:
                controls.focused = False
                controls.held.clear()
                controls.jump_requested = False
                controls.pickup_requested = False
                controls.attack_requested = False
            elif event.window.event == sdl2.SDL_WINDOWEVENT_FOCUS_GAINED:
                controls.focused = True
        elif event.type in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
            if not event.key.repeat:
                controls.set_key(
                    KEY_NAMES.get(event.key.keysym.sym), event.type == sdl2.SDL_KEYDOWN
                )
    return running
