"""Exercise the actual canvas with synthetic SDL events and save screenshots."""

from ctypes import byref, c_int, c_ubyte
import json
from pathlib import Path
from random import Random
import tempfile
from unittest.mock import patch

from PIL import Image
import pico2d.pico2d as core
import sdl2

import main
from events import poll_events
from game import Item, Stage, spawn_items
from rendering import draw_background, draw_character, draw_health, draw_items, draw_pickup_hint
from resources import IMAGE_FILES, ROOT, ResourceError, load_images
from settings import (
    AIR_DROP_HEIGHT, CHARACTER_SCALE, FRAME_BOTTOM_PADDING, FRAME_HEIGHT, GRAVITY, GROUND_Y, HEIGHT,
    ITEM_WIDTHS, JUMP_SPEED, PICKUP_RADIUS, PLAYER_HALF_WIDTH, PORTAL_WIDTH, PORTAL_X,
    SECOND_STAGE_SPAWN_X, WIDTH,
)


def push(kind, value=None):
    event = sdl2.SDL_Event()
    if kind in ("down", "up"):
        event.type = sdl2.SDL_KEYDOWN if kind == "down" else sdl2.SDL_KEYUP
        event.key.windowID = sdl2.SDL_GetWindowID(core.window)
        event.key.keysym.sym = {"left": sdl2.SDLK_LEFT, "right": sdl2.SDLK_RIGHT,
                               "lshift": sdl2.SDLK_LSHIFT, "rshift": sdl2.SDLK_RSHIFT,
                               "r": sdl2.SDLK_r, "space": sdl2.SDLK_SPACE, "f": sdl2.SDLK_f}[value]
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


def verify_double_jumping(output):
    items = [Item("steel_pipe", WIDTH / 2), Item("dagger", WIDTH / 2 - 250),
             Item("dagger", WIDTH / 2 + 250)]
    actions = {
        0: [("focus", True), ("down", "f"), ("up", "f")],
        1: [("down", "space"), ("down", "right"), ("down", "rshift")],
        2: [("down", "space")],
        10: [("up", "space")],
        20: [("down", "space"), ("up", "right"), ("down", "left")],
        21: [("up", "space")],
        30: [("down", "space")],
        40: [("up", "left"), ("up", "rshift")],
        150: [("up", "space"), ("down", "space")],
        151: [("up", "space")],
        155: [("focus", False)],
        156: [("focus", True)],
        165: [("down", "space"), ("up", "space")],
        170: [("down", "space"), ("up", "space")],
        261: [("quit", None)],
    }
    shots = {0: "double-ground-armed", 1: "double-first-rise", 20: "double-second-launch",
             30: "double-third-ignored", 130: "double-landed-held", 155: "double-focus-preserved",
             165: "double-relaunch-after-focus", 260: "double-landed-reset"}
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
        assert player.weapon == "steel_pipe" and len(items) == 2
        assert player.foot_y + (FRAME_HEIGHT - FRAME_BOTTOM_PADDING) * CHARACTER_SCALE <= HEIGHT
        records.append({"count": player.jump_count, "height": player.foot_y - GROUND_Y,
                        "speed": player.vertical_speed, "animation": player.animation_time,
                        "facing": player.facing, "state": player.state})

    def observe_health(image, player):
        draw_health(image, player)
        assert player.health == 3
        shot = shots.get(tick)
        if shot is None and tick < 130 and player.jump_count == 2 and player.vertical_speed <= 0:
            shot = "double-peak"
        if shot and shot not in screenshots:
            capture(output / f"{shot}.png")
            screenshots.append(shot)

    with (patch("main.spawn_items", return_value=items) as spawn,
          patch("main.poll_events", side_effect=feed),
          patch("main.draw_character", side_effect=observe),
          patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=280)
        spawn.assert_called_once_with()
    assert result["frames"] == 261, result
    for tick, count in {0: 0, 1: 1, 2: 1, 19: 1, 20: 2, 30: 2, 130: 0,
                        150: 1, 155: 1, 156: 1, 165: 2, 170: 2, 260: 0}.items():
        assert records[tick]["count"] == count, (tick, records[tick])
    for launch, previous in ((20, 19), (165, 164)):
        assert records[launch]["speed"] > records[previous]["speed"]
        assert records[launch]["animation"] < records[previous]["animation"]
    assert records[30]["speed"] <= records[29]["speed"]
    assert records[170]["speed"] <= records[169]["speed"]
    assert records[130]["state"] == records[260]["state"] == "IDLE"
    assert records[130]["height"] == records[260]["height"] == 0
    assert records[1]["facing"] == 1 and records[20]["facing"] == -1
    peak = max(record["height"] for record in records)
    assert 192 < peak <= 384 + 1e-6
    assert len(screenshots) == 9, screenshots
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    result.update({"status": "PASS", "peak_height": peak, "screenshots": screenshots,
                   "final_jump_count": records[-1]["count"], "final_weapon": "steel_pipe"})
    return result


def verify_item_spawns(output):
    layouts = []
    for seed, count in ((1, 3), (0, 4), (5, 5)):
        items = spawn_items(Random(seed))
        assert len(items) == count
        assert {item.kind for item in items} == set(ITEM_WIDTHS)
        seen = []

        def observe_items(images, current):
            draw_items(images, current)
            assert tuple(current) == tuple(items)
            seen.append(tuple(current))

        def observe_health(image, player):
            draw_health(image, player)
            if len(seen) == 1:
                capture(output / f"items-{count}.png")

        with (patch("main.spawn_items", return_value=items) as spawn,
              patch("main.draw_items", side_effect=observe_items),
              patch("main.draw_health", side_effect=observe_health)):
            assert main.run(frame_limit=3)["frames"] == 3
            spawn.assert_called_once_with()
        assert len(seen) == 3
        assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
        layouts.append({"seed": seed, "count": count, "screenshot": f"items-{count}.png",
                        "items": [{"kind": item.kind, "x": item.x, "foot_y": item.foot_y,
                                   "width": ITEM_WIDTHS[item.kind]} for item in items]})
    return {"status": "PASS", "layouts": layouts}


def verify_pickup(output):
    items = [Item("dagger", WIDTH / 2 + 80), Item("steel_pipe", WIDTH / 2 + 90),
             Item("dagger", WIDTH / 2 + 250)]
    initial = tuple(items)
    actions = {
        0: [("focus", True), ("down", "f"), ("up", "f")],
        1: [("down", "right"), ("down", "lshift")],
        8: [("up", "right"), ("up", "lshift"), ("down", "f"), ("up", "f")],
        9: [("down", "f")],
        10: [("down", "f")],
        11: [("down", "f")],
        12: [("down", "right"), ("down", "lshift")],
        13: [("up", "right"), ("up", "lshift")],
        20: [("up", "f")],
        25: [("down", "left"), ("down", "rshift")],
        26: [("up", "left"), ("up", "rshift")],
        30: [("down", "f"), ("up", "f")],
        40: [("down", "space"), ("up", "space")],
        125: [("down", "f"), ("up", "f")],
        130: [("down", "right")],
        131: [("up", "right")],
        150: [("down", "space"), ("up", "space")],
        155: [("down", "f"), ("up", "f"), ("focus", False)],
        156: [("focus", True)],
        200: [("down", "right"), ("down", "lshift")],
        215: [("up", "right"), ("up", "lshift")],
        236: [("quit", None)],
    }
    shots = {7: "pickup-near-before", 8: "pickup-dagger-right", 9: "pickup-pipe-right",
             12: "pickup-run-pipe-right", 25: "pickup-run-pipe-left", 30: "pickup-dagger-left",
             125: "pickup-pipe-left", 130: "pickup-walk-pipe-right", 220: "pickup-after-drop"}
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
        kinds = [item.kind for item in items] + ([player.weapon] if player.weapon else [])
        assert sorted(kinds) == sorted(item.kind for item in initial)
        records.append({"weapon": player.weapon, "x": player.x, "foot_y": player.foot_y,
                        "state": player.state, "facing": player.facing, "floor": tuple(items)})

    def observe_health(image, player):
        draw_health(image, player)
        assert player.health == 3
        shot = shots.get(tick)
        if player.state == "JUMP" and player.vertical_speed <= 0:
            shot = "pickup-jump-dagger" if player.weapon == "dagger" else "pickup-jump-pipe"
        if shot and shot not in screenshots:
            capture(output / f"{shot}.png")
            screenshots.append(shot)

    with (patch("main.spawn_items", return_value=items) as spawn,
          patch("main.poll_events", side_effect=feed),
          patch("main.draw_character", side_effect=observe),
          patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=260)
        spawn.assert_called_once_with()
    assert result["frames"] == 236, result
    assert records[0]["weapon"] is records[7]["weapon"] is None
    assert abs(records[7]["x"] - initial[0].x) <= PICKUP_RADIUS
    expected = {8: "dagger", 9: "steel_pipe", 11: "steel_pipe", 12: "steel_pipe",
                25: "steel_pipe", 30: "dagger", 45: "dagger", 120: "dagger",
                125: "steel_pipe", 130: "steel_pipe", 155: "steel_pipe", 235: "steel_pipe"}
    for tick, weapon in expected.items():
        assert records[tick]["weapon"] == weapon, (tick, records[tick])
        assert len(records[tick]["floor"]) == 2
    assert initial[0] not in records[8]["floor"] and initial[1] not in records[9]["floor"]
    for tick, kind in ((9, "dagger"), (30, "steel_pipe"), (125, "dagger")):
        record = records[tick]
        assert Item(kind, record["x"], GROUND_Y) in record["floor"]
    for tick, state in {12: "RUN", 25: "RUN", 45: "JUMP", 120: "IDLE", 130: "WALK",
                        155: "JUMP", 235: "IDLE"}.items():
        assert records[tick]["state"] == state, (tick, records[tick])
    assert records[12]["facing"] == 1 and records[25]["facing"] == -1
    assert len(screenshots) == 11, screenshots
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    result.update({"status": "PASS", "screenshots": screenshots, "initial_count": len(initial),
                   "final_weapon": records[-1]["weapon"], "final_floor_count": len(items)})
    return result


def verify_drop_and_hint(output):
    items = [Item("dagger", WIDTH / 2 + 80), Item("steel_pipe", WIDTH / 2 + 90)]
    initial_kinds = sorted(item.kind for item in items)
    actions = {
        0: [("focus", True)],
        1: [("down", "right"), ("down", "lshift")],
        8: [("up", "right"), ("up", "lshift"), ("down", "f"), ("up", "f")],
        9: [("down", "f")],
        10: [("down", "f")],
        12: [("down", "right"), ("down", "lshift")],
        20: [("up", "f")],
        40: [("up", "right"), ("up", "lshift")],
        50: [("down", "f")],
        51: [("down", "f")],
        60: [("up", "f"), ("down", "f")],
        64: [("up", "f")],
        65: [("down", "space"), ("up", "space")],
        66: [("down", "f"), ("up", "f")],
        150: [("quit", None)],
    }
    shots = {0: "hint-out-of-range", 7: "hint-near-before-pickup", 9: "hint-after-swap",
             45: "hint-away-before-drop", 50: "f-drop-on-ground", 51: "f-drop-held-no-repickup",
             60: "f-repickup", 66: "hint-airborne-drop", 140: "f-landed-unarmed"}
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

    def observe_hint(images, current, player):
        target = draw_pickup_hint(images, current, player)
        index = player.pickup_target(current)
        assert target is (None if index is None else current[index])
        kinds = [item.kind for item in current] + ([player.weapon] if player.weapon else [])
        assert sorted(kinds) == initial_kinds
        records.append({"weapon": player.weapon, "x": player.x, "state": player.state,
                        "floor": tuple(current), "hint": target})

    def observe_health(image, player):
        draw_health(image, player)
        assert player.health == 3
        if tick in shots:
            capture(output / f"{shots[tick]}.png")

    with (patch("main.spawn_items", return_value=items),
          patch("main.poll_events", side_effect=feed),
          patch("main.draw_pickup_hint", side_effect=observe_hint),
          patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=160)
    assert result["frames"] == 150, result
    assert records[0]["hint"] is None
    assert records[7]["hint"].kind == "dagger"
    assert records[8]["weapon"] == "dagger" and records[9]["weapon"] == "steel_pipe"
    assert records[9]["hint"].kind == "dagger"
    assert records[45]["weapon"] == "steel_pipe" and records[45]["hint"] is None
    dropped = Item("steel_pipe", records[50]["x"], GROUND_Y)
    for frame in (50, 51, 59):
        assert records[frame]["weapon"] is None
        assert dropped in records[frame]["floor"]
        assert records[frame]["hint"] == dropped
    assert records[60]["weapon"] == "steel_pipe" and dropped not in records[60]["floor"]
    assert records[60]["hint"] is None
    assert records[66]["state"] == "JUMP" and records[66]["hint"] is None
    assert records[66]["weapon"] is records[140]["weapon"] is None
    assert records[66]["floor"][-1].falling
    assert records[140]["floor"][-1] == Item("steel_pipe", records[66]["x"])
    assert records[140]["hint"] == records[140]["floor"][-1]
    assert records[140]["state"] == "IDLE"
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    result.update({"status": "PASS", "drop_and_repickup": "PASS", "hint_target": "PASS",
                   "held_f_no_repeat": "PASS", "airborne_drop": "PASS",
                   "screenshots": list(shots.values())})
    return result


def verify_air_drop(output):
    cases = []
    for number in (1, 2):
        for kind in ITEM_WIDTHS:
            stages, players, records, screenshots = [], [], [], []
            tick, dropped_at, landed_at, repicked_at = -1, None, None, None
            drop_x, drop_y = None, None
            direction = "left" if kind == "dagger" else "right"
            phase = "armed"

            def make_stage(items):
                stage = Stage(items=items, number=number)
                stages.append(stage)
                return stage

            def feed(controls):
                nonlocal tick, phase, dropped_at, landed_at, repicked_at, drop_x, drop_y
                tick += 1
                if tick == 0:
                    poll_events(controls)
                    push("focus", True)
                    push("down", "f")
                    push("up", "f")
                elif tick in (1, 20):
                    push("down", "space")
                    push("up", "space")
                elif phase == "armed" and players[-1].jump_count == 2 and players[-1].vertical_speed <= 0:
                    player = players[-1]
                    drop_x, drop_y = player.x, player.foot_y + AIR_DROP_HEIGHT
                    push("down", "f")
                    push("down", direction)
                    phase, dropped_at = "falling", tick
                elif phase == "falling":
                    age = tick - dropped_at
                    if age in (1, 2):
                        push("down", "f")
                    if age == 6:
                        push("up", direction)
                    if players[-1].grounded and not stages[0].items[-1].falling:
                        phase, landed_at = "landed", tick
                elif phase == "landed" and tick - landed_at == 5:
                    push("up", "f")
                    push("down", "f")
                    phase, repicked_at = "repicked", tick
                elif phase == "repicked" and tick - repicked_at == 5:
                    push("quit")
                return poll_events(controls)

            def observe_character(image, player):
                draw_character(image, player)
                players.append(player)

            def observe_hint(images, items, player):
                target = draw_pickup_hint(images, items, player)
                assert len(items) + int(player.weapon is not None) == 1
                if items and items[0].falling:
                    assert target is None and player.weapon is None
                records.append({"items": tuple(items), "weapon": player.weapon, "hint": target})

            def observe_health(image, player):
                draw_health(image, player)
                assert player.health == 3
                items = stages[0].items
                shot = None
                if tick == 0:
                    assert player.weapon == kind
                    shot = "armed"
                elif phase == "falling":
                    item = items[0]
                    assert player.weapon is None and item.x == drop_x
                    if tick == dropped_at:
                        assert player.state == "JUMP" and item.falling
                        assert item.foot_y == drop_y and item.vertical_speed == 0
                        shot = "released"
                    elif item.falling and item.foot_y - GROUND_Y < 80:
                        shot = "near-ground"
                    elif item.falling and drop_y - item.foot_y > 60:
                        shot = "falling"
                elif phase == "landed":
                    assert items[0] == Item(kind, drop_x)
                    assert player.weapon is None and player.grounded
                    assert records[-1]["hint"] == items[0]
                    shot = "landed"
                elif phase == "repicked":
                    assert player.weapon == kind and not items
                    shot = "repicked"
                filename = f"air-drop-{number}-{kind}-{shot}"
                if shot and filename not in screenshots:
                    capture(output / f"{filename}.png")
                    screenshots.append(filename)

            with (patch("main.Stage", side_effect=make_stage),
                  patch("main.spawn_items", return_value=[Item(kind, WIDTH / 2)]),
                  patch("main.poll_events", side_effect=feed),
                  patch("main.draw_character", side_effect=observe_character),
                  patch("main.draw_pickup_hint", side_effect=observe_hint),
                  patch("main.draw_health", side_effect=observe_health)):
                result = main.run(frame_limit=300)
            assert result["stage"] == number and phase == "repicked"
            assert result["frames"] < 300 and len(screenshots) == 6, (result, screenshots)
            falling = [record["items"][0] for record in records
                       if record["items"] and record["items"][0].falling]
            assert len(falling) > 5 and all(item.x == drop_x for item in falling)
            assert all(a.foot_y > b.foot_y and a.vertical_speed > b.vertical_speed
                       for a, b in zip(falling, falling[1:]))
            assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
            result.update({"status": "PASS", "kind": kind, "release_height": drop_y - GROUND_Y,
                           "falling_frames": len(falling), "screenshots": screenshots})
            cases.append(result)
    return {"status": "PASS", "cases": cases}


def verify_portal(output):
    layouts = []
    for seed, count in ((1, 3), (0, 4), (5, 5)):
        stages, screenshots = [], []
        loaded, players = {}, []
        tick, entered_at, picked_at, jumped_at = -1, None, None, None
        phase, expected_weapon = "first", None
        initial_items, picked_items = None, None

        def make_stage(items):
            stage = Stage(items=items)
            stages.append(stage)
            return stage

        def remember_images():
            nonlocal loaded
            loaded = load_images()
            return loaded

        def feed(controls):
            nonlocal tick, phase, expected_weapon, picked_at, jumped_at
            tick += 1
            if tick == 0:
                poll_events(controls)
                push("focus", True)
                push("down", "f")
                push("up", "f")
            elif tick == 1:
                push("down", "right")
                push("down", "lshift")
            elif stages[0].number == 2:
                player = players[-1]
                if tick - entered_at == 5:
                    assert player.x == SECOND_STAGE_SPAWN_X and not controls.held
                    push("down", "right")
                    push("down", "lshift")
                    phase = "approach"
                elif phase == "approach":
                    index = player.pickup_target(stages[0].items)
                    if index is not None:
                        expected_weapon = stages[0].items[index].kind
                        push("up", "right")
                        push("up", "lshift")
                        push("down", "f")
                        push("up", "f")
                        phase, picked_at = "picked", tick
                elif phase == "picked" and tick - picked_at == 5:
                    push("down", "space")
                    push("up", "space")
                    phase, jumped_at = "jump", tick
                elif phase == "jump" and tick - jumped_at > 10 and player.grounded:
                    push("quit")
            return poll_events(controls)

        def observe_background(image):
            assert image is loaded[stages[0].background_key]
            draw_background(image)

        def observe_character(image, player):
            draw_character(image, player)
            players.append(player)

        def observe_health(image, player):
            nonlocal entered_at, initial_items, picked_items
            draw_health(image, player)
            stage = stages[0]
            shot = None
            if tick == 0:
                assert stage.number == 1 and player.weapon == "steel_pipe"
                shot = "first-map"
            elif stage.number == 1 and player.x >= PORTAL_X - PORTAL_WIDTH / 2 - 32:
                shot = "approach"
            elif stage.number == 2:
                assert player.health == 3
                if entered_at is None:
                    entered_at = tick
                    initial_items = tuple(stage.items)
                    assert len(initial_items) == count
                    assert {item.kind for item in initial_items} == set(ITEM_WIDTHS)
                    assert player.weapon == "steel_pipe" and player.state == "IDLE"
                    assert (player.x, player.foot_y) == (SECOND_STAGE_SPAWN_X, GROUND_Y)
                    shot = "second-spawn"
                elif phase in ("first", "approach"):
                    assert tuple(stage.items) == initial_items
                elif phase == "picked":
                    assert player.weapon == expected_weapon and len(stage.items) == count
                    if picked_items is None:
                        picked_items = tuple(stage.items)
                    assert tuple(stage.items) == picked_items
                    shot = "second-pickup"
                elif phase == "jump":
                    assert tuple(stage.items) == picked_items and player.weapon == expected_weapon
                    shot = "second-jump"
            filename = f"portal-{seed}-{shot}"
            if shot and filename not in screenshots:
                capture(output / f"{filename}.png")
                screenshots.append(filename)

        first_items = [Item("steel_pipe", WIDTH / 2), Item("dagger", 250), Item("dagger", 500)]
        with (patch("main.Stage", side_effect=make_stage),
              patch("main.spawn_items", return_value=first_items),
              patch("game.spawn_items", side_effect=lambda rng=None, spawn_x=WIDTH / 2:
                    spawn_items(Random(seed), spawn_x=spawn_x)) as spawn,
              patch("main.load_images", side_effect=remember_images),
              patch("main.poll_events", side_effect=feed),
              patch("main.draw_background", side_effect=observe_background),
              patch("main.draw_character", side_effect=observe_character),
              patch("main.draw_health", side_effect=observe_health)):
            result = main.run(frame_limit=600)
            spawn.assert_called_once_with(None, spawn_x=SECOND_STAGE_SPAWN_X)
        assert result["stage"] == 2 and phase == "jump" and players[-1].grounded
        assert result["frames"] < 600 and len(screenshots) == 5, (result, screenshots)
        assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
        result.update({"seed": seed, "count": count, "status": "PASS",
                       "screenshots": screenshots, "transition_frame": entered_at})
        layouts.append(result)
    return {"status": "PASS", "layouts": layouts}


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

    # Exercise both movement boundaries on map 2; the actual portal path is checked separately.
    with (patch("main.Stage", side_effect=lambda items: Stage(items=items, number=2)),
          patch("main.poll_events", side_effect=feed),
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
            for missing in ("character", "health_bar", "dagger", "steel_pipe", "second_background", "portal"):
                try:
                    main.run(frame_limit=1)
                except ResourceError as error:
                    assert Path(IMAGE_FILES[missing]).name in str(error)
                else:
                    raise AssertionError(f"Missing {missing} must fail")
                assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
                fixture = Path(directory) / IMAGE_FILES[missing]
                fixture.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGBA", (16, 16), "white").save(fixture)
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    result.update({"scripted_input": "PASS", "window_close": "PASS", "partial_load_cleanup": "PASS",
                   "health_bar_load_cleanup": "PASS", "health_hud": "PASS",
                   "item_load_cleanup": "PASS", "item_spawns": verify_item_spawns(output),
                   "screenshots": list(shots.values()), "checkpoints": [records[tick] for tick in expected],
                   "jump": verify_jumping(output), "pickup": verify_pickup(output),
                   "double_jump": verify_double_jumping(output),
                   "drop_and_hint": verify_drop_and_hint(output),
                   "portal": verify_portal(output), "stage_image_load_cleanup": "PASS",
                   "air_drop": verify_air_drop(output)})
    (output / "runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    verify()
