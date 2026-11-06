"""Verify armed poses and actual SDL input in the game loop; save evidence."""

import json
from unittest.mock import patch

import pico2d
import pico2d.pico2d as core
import sdl2

import main
from events import poll_events
from game import Item, Player
from rendering import draw_character, draw_health, draw_held_weapon
from resources import ROOT, load_images, release_images
from settings import ANIMATIONS, ARMED_ANIMATION_ROWS, ATTACK_FPS, RUN_SPEED, WIDTH
from tools.verify_runtime import capture, push


def verify_pose_gallery(output):
    images = {}
    core.window = core.renderer = None
    core.audio_on = False
    shots = []
    try:
        pico2d.open_canvas(WIDTH, 960, sync=True)
        pico2d.hide_lattice()
        images = load_images()
        for weapon in ("dagger", "steel_pipe"):
            for facing in (1, -1):
                pico2d.clear_canvas()
                for row, state in enumerate(ARMED_ANIMATION_ROWS):
                    for frame in range(8):
                        player = Player(x=80 + frame * 160, foot_y=800 - row * 176,
                                        weapon=weapon, facing=facing,
                                        state="IDLE" if state == "ATTACK" else state)
                        if state == "ATTACK":
                            player.attack_time = frame / ATTACK_FPS
                        else:
                            player.animation_time = frame / ANIMATIONS[state][1]
                        draw_character(images[player.character_key], player)
                        draw_held_weapon(images, player)
                filename = f"weapon-poses-{weapon}-{'right' if facing > 0 else 'left'}.png"
                capture(output / filename)
                shots.append(filename)
                pico2d.update_canvas()
    finally:
        release_images(images)
        pico2d.close_canvas()
        core.window = core.renderer = None
        core.audio_on = False
    return shots


def verify_gameplay(output):
    player = Player()
    items = [Item("dagger", player.x), Item("steel_pipe", 900), Item("dagger", 250)]
    actions = {
        0: [("focus", True), ("down", "f"), ("up", "f")],
        1: [("down", "z")],
        10: [("up", "z"), ("down", "z")],
        42: [("up", "z")],
        45: [("down", "left"), ("down", "z"), ("up", "z")],
        60: [("up", "left")],
        65: [("down", "f"), ("up", "f")],
        70: [("down", "z"), ("up", "z")],
        105: [("down", "f"), ("up", "f")],
        110: [("down", "f"), ("up", "f")],
        115: [("down", "z"), ("up", "z"), ("down", "space"), ("up", "space")],
        125: [("down", "space"), ("up", "space")],
        130: [("down", "f"), ("up", "f")],
        140: [("down", "z"), ("focus", False)],
        141: [("focus", True)],
        220: [("down", "f"), ("up", "f")],
        225: [("down", "right"), ("down", "lshift")],
        270: [("up", "right"), ("up", "lshift"), ("down", "left"), ("down", "rshift")],
        320: [("up", "left"), ("up", "rshift")],
        330: [("quit", None)],
    }
    checkpoints = {
        0: ("dagger", "IDLE"), 8: ("dagger", "ATTACK"), 40: ("dagger", "IDLE"),
        50: ("dagger", "ATTACK"), 65: ("steel_pipe", "IDLE"), 78: ("steel_pipe", "ATTACK"),
        105: (None, "IDLE"), 115: ("steel_pipe", "ATTACK"), 128: ("steel_pipe", "ATTACK"),
        130: (None, "JUMP"), 140: (None, "JUMP"), 220: ("steel_pipe", "IDLE"),
    }
    tick, clock = -1, 0.0
    records, shots = [], []

    def feed(controls):
        nonlocal tick, clock
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
        if tick == 65:
            player.x = 900
        if tick == 105:
            player.x = 600
        for kind, value in actions.get(tick, []):
            push(kind, value)
        result = poll_events(controls)
        if tick == 140:
            assert not controls.attack_requested and not controls.held
        return result

    def observe(image, current):
        draw_character(image, current)
        assert image.h == (1280 if current.weapon else 1024)
        if tick in checkpoints:
            assert (current.weapon, current.display_state) == checkpoints[tick], (tick, vars(current))
        if tick == 128:
            assert current.jump_count == 2
        records.append({"tick": tick, "x": current.x, "row": current.row, "frame": current.frame,
                        "state": current.display_state, "weapon": current.weapon})

    def observe_health(image, current):
        draw_health(image, current)
        if tick in checkpoints or tick in (245, 280):
            filename = f"weapon-gameplay-{tick:03d}.png"
            capture(output / filename)
            shots.append(filename)

    stages = []
    draw_arrows = main.draw_stage_arrows

    def observe_stage(images, number, elapsed):
        stages.append(number)
        draw_arrows(images, number, elapsed)

    with (patch("main.Player", return_value=player), patch("main.spawn_items", return_value=items),
          patch("main.poll_events", side_effect=feed), patch("main.perf_counter", side_effect=lambda: clock),
          patch("main.sleep"), patch("main.draw_character", side_effect=observe),
          patch("main.draw_health", side_effect=observe_health),
          patch("main.draw_stage_arrows", side_effect=observe_stage)):
        result = main.run(frame_limit=340)
    assert result["frames"] == 330
    assert stages[225] == 1 and 2 in stages[225:270] and stages[320] == 1
    assert abs(records[230]["x"] - records[229]["x"] - RUN_SPEED / 60) < 1e-6
    assert abs(records[280]["x"] - records[279]["x"] + RUN_SPEED / 60) < 1e-6
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"frames": result["frames"], "fixed_dt": 1 / 60, "run_speed": RUN_SPEED,
            "checkpoints": "PASS", "bidirectional_stage_run": "PASS", "screenshots": shots}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    result = {"pose_screenshots": verify_pose_gallery(output), "gameplay": verify_gameplay(output)}
    (output / "weapons-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
