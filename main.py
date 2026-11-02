"""Run the pico2d movement prototype."""

import argparse
from time import perf_counter, sleep

import pico2d

from settings import HEIGHT, TARGET_FPS, WIDTH


def run(frame_limit=None):
    pico2d.open_canvas(WIDTH, HEIGHT, sync=True)
    try:
        running = True
        frames = 0
        started = previous = perf_counter()
        while running:
            frame_started = perf_counter()
            dt = frame_started - previous
            previous = frame_started
            for event in pico2d.get_events():
                if event.type == pico2d.SDL_QUIT:
                    running = False
            if not running:
                break
            pico2d.clear_canvas()
            pico2d.update_canvas()
            frames += 1
            sleep(max(0.0, 1.0 / TARGET_FPS - (perf_counter() - frame_started)))
            if frame_limit is not None and frames >= frame_limit:
                break
        elapsed = perf_counter() - started
        return {"frames": frames, "seconds": elapsed, "fps": frames / elapsed}
    finally:
        pico2d.close_canvas()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, help="Exit after N rendered frames")
    args = parser.parse_args()
    if args.frames is not None and args.frames < 1:
        parser.error("--frames must be positive")
    result = run(frame_limit=args.frames)
    if args.frames is not None:
        print(result)
