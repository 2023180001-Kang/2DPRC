"""Run the pico2d movement prototype."""

import pico2d

from settings import HEIGHT, WIDTH


def run(frame_limit=None):
    pico2d.open_canvas(WIDTH, HEIGHT, sync=True)
    try:
        running = True
        frames = 0
        while running:
            for event in pico2d.get_events():
                if event.type == pico2d.SDL_QUIT:
                    running = False
            if not running:
                break
            pico2d.clear_canvas()
            pico2d.update_canvas()
            frames += 1
            if frame_limit is not None and frames >= frame_limit:
                break
    finally:
        pico2d.close_canvas()


if __name__ == "__main__":
    run()
