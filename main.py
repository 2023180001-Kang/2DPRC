"""Run the pico2d movement prototype."""

import argparse
import sys
from time import perf_counter, sleep

import pico2d
import pico2d.pico2d as core

from events import poll_events
from game import Controls, Player, Stage, spawn_items
from resources import ResourceError, load_images, release_images
from rendering import (
    draw_background, draw_character, draw_falling_items, draw_health, draw_held_weapon, draw_items, draw_pickup_hint,
    draw_stage_arrows,
)
from settings import HEIGHT, TARGET_FPS, WIDTH


def run(frame_limit=None):
    images = {}
    # pico2d 1.5.1 cleanup expects these globals even after partial startup.
    core.window = core.renderer = None
    core.audio_on = False
    try:
        pico2d.open_canvas(WIDTH, HEIGHT, sync=True)
        if not core.window or not core.renderer:
            raise RuntimeError(f"Cannot create canvas: {core.SDL_GetError()!r}")
        pico2d.hide_lattice()
        core.SDL_SetWindowTitle(core.window, b"2DPRC | Arrows: walk | Shift: run | Space: jump | F: pickup/swap/drop | Z: attack")
        images = load_images()
        player = Player()
        stage = Stage(items=spawn_items())
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
            stage.update(dt)
            player.pick_up(stage.items, controls)
            player.update(dt, controls)
            stage.try_transition(player, controls)
            pico2d.clear_canvas()
            draw_background(images[stage.background_key])
            draw_stage_arrows(images, stage.number, stage.arrow_time)
            draw_items(images, stage.items)
            draw_character(images[player.character_key], player)
            draw_held_weapon(images, player)
            draw_falling_items(images, stage.items)
            draw_pickup_hint(images, stage.items, player)
            draw_health(images["health_bar"], player)
            pico2d.update_canvas()
            frames += 1
            sleep(max(0.0, 1.0 / TARGET_FPS - (perf_counter() - frame_started)))
            if frame_limit is not None and frames >= frame_limit:
                break
        elapsed = perf_counter() - started
        return {"frames": frames, "seconds": elapsed, "fps": frames / elapsed, "stage": stage.number}
    finally:
        try:
            release_images(images)
        finally:
            pico2d.close_canvas()
            core.window = core.renderer = None
            core.audio_on = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, help="Exit after N rendered frames")
    args = parser.parse_args()
    if args.frames is not None and args.frames < 1:
        parser.error("--frames must be positive")
    try:
        result = run(frame_limit=args.frames)
    except (ResourceError, RuntimeError) as error:
        print(f"Game error: {error}", file=sys.stderr)
        sys.exit(1)
    if args.frames is not None:
        print(result)
