"""Verify six-map progression, death gates, item placement and round trips via SDL."""

import json
from random import Random
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Enemy, Player, spawn_items
from rendering import draw_background, draw_health
from resources import ROOT, load_images
from settings import (
    ARROW_SPAWN_PADDING, ARROW_SWAY_AMPLITUDE, ARROW_WIDTH, ARROW_X, ITEM_WIDTHS,
    STAGE_ARROWS, STAGE_BACKGROUNDS, STAGE_ENTRY_LEFT_X, STAGE_GROUND_Y, WIDTH,
)
from tools.verify_runtime import capture, push


def verify(output):
    player = Player()
    stages, snapshots, enemy_spawns, item_spawns, images = [], {}, [], [], {}
    tick, clock, phase, expected = -1, 0.0, "live_gate", 1
    stage_entry = WIDTH / 2
    shots, seen, records = [], set(), []

    def make_enemy(rng=None, spawn_x=WIDTH / 2, *, stage_number=1):
        enemy_spawns.append(stage_number)
        return Enemy(x=940 if stage_number == 1 else 640, foot_y=STAGE_GROUND_Y[stage_number])

    def make_items(rng=None, spawn_x=WIDTH / 2, *, stage_number=1):
        item_spawns.append(stage_number)
        items = spawn_items(Random(10 + stage_number), spawn_x=spawn_x, stage_number=stage_number)
        assert 3 <= len(items) <= 5 and {item.kind for item in items} == {"dagger", "steel_pipe"}
        for item in items:
            for direction in STAGE_ARROWS[stage_number]:
                clearance = (ARROW_WIDTH / 2 + ARROW_SWAY_AMPLITUDE + ARROW_SPAWN_PADDING
                             + ITEM_WIDTHS[item.kind] / 2)
                assert abs(item.x - ARROW_X[direction]) > clearance
        return items

    stage_class = main.Stage

    def make_stage(items):
        stage = stage_class(items)
        stages.append(stage)
        return stage

    def remember_images():
        loaded = load_images()
        images.update(loaded)
        return loaded

    def keys(down=(), up=()):
        for key in up:
            push("up", key)
        for key in down:
            push("down", key)

    def feed(controls):
        nonlocal tick, clock, phase, expected, stage_entry
        tick += 1
        clock = (tick + 1) / 60
        stage = stages[0]
        enemy = stage.enemy
        if tick == 0:
            poll_events(controls)
            push("focus", True)
        if phase == "live_gate":
            assert stage.number == expected and enemy.alive
            stage_entry = player.x
            player.x, player.horizontal_speed = ARROW_X[1], 0
            phase = "live_locked"
        elif phase == "live_locked":
            assert stage.number == expected and 1 not in stage.visible_arrows
            player.x, player.facing = stage_entry, 1
            keys(down=("right", "lshift"))
            phase = "approach"
        elif phase == "approach" and enemy.x - player.x <= 145:
            assert enemy.alive
            keys(down=("a",))
            phase = "attack"
        elif phase == "attack" and enemy.state == "DYING":
            keys(up=("a", "right", "lshift"))
            player.x, player.horizontal_speed = ARROW_X[1], 0
            phase = "dying_gate"
        elif phase == "dying_gate":
            assert stage.number == expected and not enemy.defeated
            if enemy.frame == 7:
                player.x = 1000
                phase = "finish_death"
        elif phase == "finish_death" and enemy.defeated:
            assert 1 in stage.visible_arrows
            snapshots[stage.number] = (enemy, stage.items, tuple(stage.items))
            player.x = ARROW_X[1]
            if expected < 6:
                expected += 1
                phase = "entered"
            else:
                phase = "final_exit"
        elif phase == "entered":
            assert stage.number == expected and enemy.alive and 1 not in stage.visible_arrows
            phase = "live_gate"
        elif phase == "final_exit":
            assert stage.number == 6 and len(enemy_spawns) == 6 and len(item_spawns) == 6
            player.x = ARROW_X[-1]
            expected, phase = 5, "backtrack"
        elif phase == "backtrack":
            assert stage.number == expected
            saved_enemy, saved_items, contents = snapshots[expected]
            assert stage.enemy is saved_enemy and stage.items is saved_items
            assert tuple(stage.items) == contents and stage.enemy.defeated
            if expected > 1:
                player.x = ARROW_X[-1]
                expected -= 1
            else:
                player.x = ARROW_X[1]
                expected, phase = 2, "revisit"
        elif phase == "revisit":
            assert stage.number == expected
            saved_enemy, saved_items, contents = snapshots[expected]
            assert stage.enemy is saved_enemy and stage.items is saved_items
            assert tuple(stage.items) == contents and stage.enemy.defeated
            if expected < 6:
                player.x = ARROW_X[1]
                expected += 1
            else:
                phase = "done"
        elif phase == "done":
            push("quit")
        assert tick < 1100, (phase, stage.number, vars(player), vars(enemy))
        return poll_events(controls)

    def observe_background(image):
        stage = stages[0]
        assert image is images[stage.background_key]
        assert (image.w, image.h) == (1672, 941)
        draw_background(image)

    def observe_health(image, current):
        draw_health(image, current)
        stage = stages[0]
        enemy = stage.enemy
        assert current.health == 100
        assert current.ground_y == current.foot_y == enemy.foot_y == stage.ground_y
        checkpoint = None
        if phase == "live_locked":
            assert 1 not in stage.visible_arrows
            checkpoint = "live-locked"
        elif phase == "dying_gate":
            assert stage.number == expected and 1 not in stage.visible_arrows
            checkpoint = "last-frame-locked" if enemy.frame == 7 else "dying-locked"
        elif phase == "finish_death" and enemy.defeated:
            assert 1 in stage.visible_arrows
            checkpoint = "cleared"
        if checkpoint and (stage.number, checkpoint) not in seen:
            seen.add((stage.number, checkpoint))
            filename = f"campaign-{stage.number}-{checkpoint}.png"
            capture(output / filename)
            shots.append(filename)
        records.append({"tick": tick, "stage": stage.number, "background": stage.background_key,
                        "enemy_state": enemy.state, "enemy_frame": enemy.frame,
                        "arrows": stage.visible_arrows, "items": len(stage.items),
                        "ground_y": stage.ground_y, "player_y": current.foot_y, "enemy_y": enemy.foot_y})

    with (patch("main.Player", return_value=player), patch("main.Stage", side_effect=make_stage),
          patch("main.spawn_items", side_effect=lambda: make_items()),
          patch("game.spawn_items", side_effect=make_items), patch("game.spawn_enemy", side_effect=make_enemy),
          patch("main.load_images", side_effect=remember_images),
          patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_background", side_effect=observe_background),
          patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=1110)
    assert phase == "done" and result["stage"] == 6
    assert enemy_spawns == item_spawns == [1, 2, 3, 4, 5, 6]
    assert len(snapshots) == 6 and len(shots) == 24
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"frames": result["frames"], "fixed_dt": 1 / 60,
            "enemy_spawns": enemy_spawns, "item_spawns": item_spawns,
            "six_map_order_and_backgrounds": "PASS", "full_death_gates": "PASS",
            "arrow_spawn_exclusion": "PASS", "round_trip_no_respawn": "PASS",
            "last_stage_no_extra_destination": "PASS", "screenshots": shots, "records": records}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    result = verify(output)
    (output / "campaign-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
