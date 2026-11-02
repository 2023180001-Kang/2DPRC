"""Run the pico2d movement prototype."""

import argparse
import sys
from time import perf_counter, sleep

import pico2d

from events import poll_events
from game import Controls, Player
from resources import ResourceError, load_images
from rendering import draw_background, draw_character
from settings import HEIGHT, TARGET_FPS, WIDTH


def run(frame_limit=None):
    pico2d.open_canvas(WIDTH, HEIGHT, sync=True)
    images = {}
    try:
        images = load_images()
        player = Player()
        controls = Controls()
        running = True
        frames = 0
        started = previous = perf_counter()
        while running:
            frame_started = perf_counter()
            dt = frame_started - previous
            previous = frame_started
            running = poll_events(controls)
            if not running:
                break
            player.update(dt, controls)
            pico2d.clear_canvas()
            draw_background(images["background"])
            draw_character(images["character"], player)
            pico2d.update_canvas()
            frames += 1
            sleep(max(0.0, 1.0 / TARGET_FPS - (perf_counter() - frame_started)))
            if frame_limit is not None and frames >= frame_limit:
                break
        elapsed = perf_counter() - started
        return {"frames": frames, "seconds": elapsed, "fps": frames / elapsed}
    finally:
        images.clear()
        pico2d.close_canvas()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, help="Exit after N rendered frames")
    args = parser.parse_args()
    if args.frames is not None and args.frames < 1:
        parser.error("--frames must be positive")
    try:
        result = run(frame_limit=args.frames)
    except ResourceError as error:
        print(f"Resource error: {error}", file=sys.stderr)
        sys.exit(1)
    if args.frames is not None:
        print(result)
