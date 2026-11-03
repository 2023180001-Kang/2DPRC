"""Exercise the actual canvas with synthetic SDL events and save screenshots."""

from ctypes import byref, c_int, c_ubyte
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from PIL import Image
import pico2d.pico2d as core
import sdl2

import main
from events import poll_events
from rendering import draw_character, draw_health
from resources import IMAGE_FILES, ROOT, ResourceError, load_images
from settings import GRAVITY, GROUND_Y, JUMP_SPEED, PLAYER_HALF_WIDTH, WIDTH


def push(kind, value=None):
    event = sdl2.SDL_Event()
    if kind in ("down", "up"):
        event.type = sdl2.SDL_KEYDOWN if kind == "down" else sdl2.SDL_KEYUP
        event.key.windowID = sdl2.SDL_GetWindowID(core.window)
        event.key.keysym.sym = {"left": sdl2.SDLK_LEFT, "right": sdl2.SDLK_RIGHT,
                               "lshift": sdl2.SDLK_LSHIFT, "rshift": sdl2.SDLK_RSHIFT,
                               "r": sdl2.SDLK_r, "space": sdl2.SDLK_SPACE}[value]
    elif kind == "quit":
        event.type = sdl2.SDL_QUIT
    else:
        event.type = sdl2.SDL_WINDOWEVENT
        event.window.windowID = sdl2.SDL_GetWindowID(core.window)
        event.window.event = {
            "focus": sdl2.SDL_WINDOWEVENT_FOCUS_GAINED if value else sdl2.SDL_WINDOWEVENT_FOCUS_LOST,
            "close": sdl2.SDL_WINDOWEVENT_CLOSE,
        }[kind]
    if sdl2.SDL_PushEvent(byref(event)) != 1:
        raise RuntimeError(f"SDL_PushEvent failed: {sdl2.SDL_GetError()!r}")


def capture(path):
    width, height = c_int(), c_int()
    if sdl2.SDL_GetRendererOutputSize(core.renderer, byref(width), byref(height)) < 0:
        raise RuntimeError(sdl2.SDL_GetError())
    pitch = width.value * 4
    pixels = (c_ubyte * (pitch * height.value))()
    if sdl2.SDL_RenderReadPixels(core.renderer, None, sdl2.SDL_PIXELFORMAT_RGBA32,
                               pixels, pitch) < 0:
        raise RuntimeError(sdl2.SDL_GetError())
    Image.frombytes("RGBA", (width.value, height.value), bytes(pixels)).save(path)


def verify_jumping(output):
    actions = {
        0: [("focus", True)],
        1: [("down", "space"), ("up", "space")],
        8: [("down", "space")],
        9: [("up", "space")],
        100: [("down", "right"), ("down", "lshift"), ("down", "space")],
        105: [("up", "right"), ("down", "left")],
        191: [("up", "space")],
        200: [("down", "space"), ("up", "space")],
        205: [("focus", False)],
        206: [("focus", True)],
        291: [("quit", None)],
    }
    records, screenshots = [], []
    tick = -1

    def feed(controls):
        nonlocal tick
        tick += 1
        if tick == 0:
            poll_events(controls)
        for kind, value in actions.get(tick, []):
            push(kind, value)
        return poll_events(controls)

    def observe(image, player):
        draw_character(image, player)
        records.append({"state": player.state, "foot_y": player.foot_y,
                        "vertical_speed": player.vertical_speed, "row": player.row,
                        "frame": player.frame, "x": player.x, "facing": player.facing})

    def observe_health(image, player):
        draw_health(image, player)
        assert player.health == 3
        shot = None
        if tick < 100 and player.state == "JUMP":
            if player.vertical_speed > 0:
                shot = "jump-rise"
            elif "jump-apex" not in screenshots:
                shot = "jump-apex"
            elif player.foot_y < GROUND_Y + 96:
                shot = "jump-fall"
        elif tick < 100 and "jump-rise" in screenshots:
            shot = "jump-land"
        if tick in (102, 110):
            shot = "jump-run-right" if tick == 102 else "jump-run-left"
        if shot and shot not in screenshots:
            capture(output / f"{shot}.png")
            screenshots.append(shot)

    with (patch("main.poll_events", side_effect=feed),
          patch("main.draw_character", side_effect=observe),
          patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=310)
    assert result["frames"] == 291, result
    for tick, state in {0: "IDLE", 1: "JUMP", 8: "JUMP", 90: "IDLE", 100: "JUMP",
                        105: "JUMP", 190: "RUN", 200: "JUMP", 205: "JUMP", 290: "IDLE"}.items():
        assert records[tick]["state"] == state, (tick, records[tick])
    assert records[105]["facing"] == -1
    assert records[105]["frame"] >= records[104]["frame"]
    assert records[90]["foot_y"] == records[190]["foot_y"] == records[290]["foot_y"] == GROUND_Y
    assert all(record["row"] == 3 for record in records if record["state"] == "JUMP")
    assert abs(JUMP_SPEED ** 2 / (2 * GRAVITY) - 192) < 1e-6
    assert all(GROUND_Y <= record["foot_y"] <= GROUND_Y + 192 + 1e-6 for record in records)
    assert max(record["foot_y"] for record in records) >= GROUND_Y + 190
    assert all(PLAYER_HALF_WIDTH <= record["x"] <= WIDTH - PLAYER_HALF_WIDTH for record in records)
    assert len(screenshots) == 6, screenshots
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    result.update({"scripted_jump": "PASS", "screenshots": screenshots,
                   "peak_height": max(record["foot_y"] for record in records) - GROUND_Y})
    return result


def verify():
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    actions = {
        0: [("focus", True)],
        1: [("down", "right")],
        10: [("down", "r")],
        11: [("up", "r")],
        31: [("down", "lshift")],
        40: [("down", "rshift")],
        41: [("up", "lshift")],
        182: [("up", "rshift")],
        183: [("up", "right")],
        184: [("down", "rshift")],
        185: [("down", "left")],
        200: [("down", "lshift")],
        201: [("up", "rshift")],
        422: [("down", "right")],
        423: [("up", "left")],
        450: [("focus", False)],
        451: [("focus", True), ("down", "left")],
        481: [("up", "left")],
        482: [("quit", None)],
    }
    shots = {0: "idle", 15: "walk-right", 80: "run-right", 181: "right-boundary",
             240: "run-left", 421: "left-boundary", 450: "focus-lost", 460: "walk-left"}
    records = []
    tick = -1

    def feed(controls):
        nonlocal tick
        tick += 1
        if tick == 0:
            poll_events(controls)
        for kind, value in actions.get(tick, []):
            push(kind, value)
        return poll_events(controls)

    def observe(image, player):
        draw_character(image, player)
        records.append({"tick": tick, "state": player.state, "x": player.x,
                        "facing": player.facing, "frame": player.frame, "foot_y": player.foot_y})

    def observe_health(image, player):
        draw_health(image, player)
        assert player.health == 3
        if tick in shots:
            capture(output / f"{shots[tick]}.png")

    with (patch("main.poll_events", side_effect=feed),
          patch("main.draw_character", side_effect=observe),
          patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=500)

    expected = {0: ("IDLE", 1), 1: ("WALK", 1), 10: ("WALK", 1), 11: ("WALK", 1),
                31: ("RUN", 1), 40: ("RUN", 1), 41: ("RUN", 1), 182: ("WALK", 1),
                183: ("IDLE", 1), 184: ("IDLE", 1), 185: ("RUN", -1),
                200: ("RUN", -1), 201: ("RUN", -1),
                422: ("IDLE", -1), 423: ("RUN", 1), 450: ("IDLE", 1),
                451: ("WALK", -1), 481: ("IDLE", -1)}
    assert result["frames"] == 482, result
    for tick, (state, facing) in expected.items():
        assert (records[tick]["state"], records[tick]["facing"]) == (state, facing), records[tick]
    assert records[181]["x"] == WIDTH - PLAYER_HALF_WIDTH
    assert records[421]["x"] == PLAYER_HALF_WIDTH
    assert all(record["foot_y"] == GROUND_Y for record in records)
    assert all(PLAYER_HALF_WIDTH <= record["x"] <= WIDTH - PLAYER_HALF_WIDTH for record in records)
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)

    def close_window(controls):
        push("close")
        return poll_events(controls)

    with patch("main.poll_events", side_effect=close_window):
        assert main.run(frame_limit=3)["frames"] == 0
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)

    with tempfile.TemporaryDirectory(dir=output) as directory:
        Image.new("RGBA", (16, 16), "black").save(Path(directory) / IMAGE_FILES["background"])
        with patch("main.load_images", side_effect=lambda: load_images(directory)):
            try:
                main.run(frame_limit=1)
            except ResourceError as error:
                assert "character.png" in str(error)
            else:
                raise AssertionError("Missing character must fail")
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    result.update({"scripted_input": "PASS", "window_close": "PASS", "partial_load_cleanup": "PASS",
                   "screenshots": list(shots.values()), "checkpoints": [records[tick] for tick in expected],
                   "jump": verify_jumping(output)})
    (output / "runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    verify()
