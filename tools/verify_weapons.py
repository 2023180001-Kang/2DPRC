"""Verify armed poses and actual SDL input in the game loop; save evidence."""

import json
from unittest.mock import patch

import pico2d
import pico2d.pico2d as core
import sdl2

import main
from events import poll_events
from game import Enemy, Item, Player
from rendering import draw_character, draw_health, draw_held_weapon
from resources import ROOT, load_images, release_images
from settings import ANIMATIONS, ARMED_ANIMATION_ROWS, ATTACK_FPS, GROUND_Y, RUN_SPEED, WIDTH
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
        1: [("down", "a")],
        2: [("down", "z"), ("up", "z")],
        10: [("up", "a"), ("down", "a")],
        42: [("up", "a")],
        45: [("down", "left"), ("down", "a"), ("up", "a")],
        60: [("up", "left")],
        65: [("down", "f"), ("up", "f")],
        70: [("down", "a"), ("up", "a")],
        105: [("down", "f"), ("up", "f")],
        107: [("down", "a"), ("up", "a")],
        110: [("down", "f"), ("up", "f")],
        115: [("down", "a"), ("up", "a"), ("down", "space"), ("up", "space")],
        125: [("down", "space"), ("up", "space")],
        130: [("down", "f"), ("up", "f")],
        140: [("down", "a"), ("focus", False)],
        141: [("focus", True)],
        220: [("down", "f"), ("up", "f")],
        225: [("down", "right"), ("down", "lshift")],
        290: [("up", "right"), ("up", "lshift"), ("down", "left"), ("down", "rshift")],
        355: [("up", "left"), ("up", "rshift")],
        380: [("quit", None)],
    }
    checkpoints = {
        0: ("dagger", "IDLE"), 8: ("dagger", "ATTACK"), 40: ("dagger", "IDLE"),
        50: ("dagger", "ATTACK"), 65: ("steel_pipe", "WALK"), 78: ("steel_pipe", "ATTACK"),
        105: (None, "IDLE"), 107: (None, "ATTACK"),
        115: ("steel_pipe", "ATTACK"), 128: ("steel_pipe", "ATTACK"),
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
        if tick == 2:
            assert "a" in controls.held and "z" not in controls.held
        if tick == 140:
            assert not controls.attack_requested and not controls.held
        return result

    def observe(image, current):
        draw_character(image, current)
        assert image.h == 1280
        if tick in checkpoints:
            assert (current.weapon, current.display_state) == checkpoints[tick], (tick, vars(current))
        if tick == 128:
            assert current.jump_count == 2
        records.append({"tick": tick, "x": current.x, "row": current.row, "frame": current.frame,
                        "state": current.display_state, "weapon": current.weapon,
                        "horizontal_speed": current.horizontal_speed})

    def observe_health(image, current):
        draw_health(image, current)
        if tick in checkpoints or tick in (245, 310):
            filename = f"weapon-gameplay-{tick:03d}.png"
            capture(output / filename)
            shots.append(filename)

    stages = []
    draw_arrows = main.draw_stage_arrows

    def observe_stage(images, number, elapsed, **kwargs):
        stages.append(number)
        draw_arrows(images, number, elapsed, **kwargs)

    with (patch("main.Player", return_value=player), patch("main.spawn_items", return_value=items),
          patch("game.spawn_enemy", side_effect=lambda *args, **kwargs: Enemy(state="DEAD", foot_y=GROUND_Y - 1000)),
          patch("main.poll_events", side_effect=feed), patch("main.perf_counter", side_effect=lambda: clock),
          patch("main.sleep"), patch("main.draw_character", side_effect=observe),
          patch("main.draw_health", side_effect=observe_health),
          patch("main.draw_stage_arrows", side_effect=observe_stage)):
        result = main.run(frame_limit=390)
    assert result["frames"] == 380
    assert stages[225] == 1 and 2 in stages[225:290] and stages[370] == 1
    assert 0 < records[225]["horizontal_speed"] < records[230]["horizontal_speed"] < RUN_SPEED
    assert abs(records[260]["horizontal_speed"] - RUN_SPEED) < 1e-6
    assert 0 < records[290]["horizontal_speed"] < RUN_SPEED
    assert -RUN_SPEED < records[310]["horizontal_speed"] < 0
    assert records[354]["horizontal_speed"] < records[355]["horizontal_speed"] < records[360]["horizontal_speed"] < 0
    assert records[360]["horizontal_speed"] < records[370]["horizontal_speed"] < records[375]["horizontal_speed"] < 0
    assert records[379]["horizontal_speed"] == 0
    coast_distance = records[354]["x"] - records[379]["x"]
    assert 120 < coast_distance < 150
    assert abs(records[260]["x"] - records[259]["x"] - RUN_SPEED / 60) < 1e-6
    assert abs(records[340]["x"] - records[339]["x"] + RUN_SPEED / 60) < 1e-6
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"frames": result["frames"], "fixed_dt": 1 / 60, "run_speed": RUN_SPEED,
            "checkpoints": "PASS", "bidirectional_stage_run": "PASS", "smooth_acceleration": "PASS",
            "friction_coast": "PASS", "coast_distance": coast_distance,
            "speed_samples": [records[tick] for tick in (225, 230, 240, 250, 290, 299, 310, 355, 360, 370, 375, 379)],
            "screenshots": shots}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    result = {"pose_screenshots": verify_pose_gallery(output), "gameplay": verify_gameplay(output)}
    (output / "weapons-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
