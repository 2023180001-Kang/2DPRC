"""Verify factory entrance walking, pursuit, jumping and weapon drops at its ground."""

import json
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Enemy, Player, Stage
from rendering import draw_health
from resources import ROOT
from tools.verify_runtime import capture, push


def verify(output):
    player = Player(x=128, weapon="steel_pipe")
    enemy = Enemy(x=600, foot_y=70, attack_cooldown=1000)
    stage = Stage([], number=5, enemy=enemy)
    tick, clock, phase, phase_tick = -1, 0.0, "walk", 0
    pending_shot = "grounded-entry"
    shots, records = [], []

    def change(next_phase, shot=None):
        nonlocal phase, phase_tick, pending_shot
        phase, phase_tick = next_phase, tick
        pending_shot = shot

    def feed(controls):
        nonlocal tick, clock, pending_shot
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
            push("down", "right")
        age = tick - phase_tick
        if phase == "walk" and enemy.aware:
            assert enemy.state == "CHASE"
            change("follow", "walking-and-pursuit")
        elif phase == "follow" and player.horizontal_speed == 0:
            assert abs(player.x - enemy.x) <= 56 + 1e-6
            change("contact", "grounded-contact")
        elif phase == "contact" and age >= 10:
            push("up", "right")
            push("down", "left")
            push("down", "space")
            change("jump")
        elif phase == "jump":
            push("up", "space")
            if player.foot_y > 220 and "factory-ground-jump.png" not in shots:
                pending_shot = "jump"
            if age > 8 and player.grounded:
                assert player.foot_y == 70
                push("up", "left")
                change("landed", "jump-landed")
        elif phase == "landed" and age >= 10:
            push("down", "f")
            change("ground_drop")
        elif phase == "ground_drop" and stage.items and player.weapon is None:
            assert stage.items[0].foot_y == stage.items[0].ground_y == 70
            push("up", "f")
            change("ground_drop_hold", "ground-drop")
        elif phase == "ground_drop_hold" and age >= 3:
            push("down", "f")
            change("repick")
        elif phase == "repick" and player.weapon is not None:
            push("up", "f")
            push("down", "space")
            change("jump_drop")
        elif phase == "jump_drop":
            push("up", "space")
            if player.foot_y > 130:
                push("down", "f")
                change("air_drop", "air-drop-release")
        elif phase == "air_drop":
            push("up", "f")
            assert stage.items[0].ground_y == 70
            if not stage.items[0].falling and player.grounded:
                assert stage.items[0].foot_y == player.foot_y == 70
                change("done", "air-drop-landed")
        elif phase == "done" and age >= 5:
            push("quit")
        assert tick < 500, (phase, vars(player), vars(enemy))
        return poll_events(controls)

    def observe(image, current):
        nonlocal pending_shot
        draw_health(image, current)
        assert enemy.foot_y == stage.ground_y == current.ground_y == 70
        if current.grounded:
            assert current.foot_y == 70
        assert current.health == 100 and stage.number == 5
        assert len(stage.items) + int(current.weapon is not None) == 1
        records.append({"tick": tick, "phase": phase, "player_x": current.x,
                        "player_y": current.foot_y, "enemy_x": enemy.x, "enemy_y": enemy.foot_y,
                        "ground_y": current.ground_y, "grounded": current.grounded})
        if pending_shot:
            filename = f"factory-ground-{pending_shot}.png"
            capture(output / filename)
            shots.append(filename)
            pending_shot = None

    with (patch("main.Player", return_value=player), patch("main.Stage", return_value=stage),
          patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_health", side_effect=observe)):
        result = main.run(frame_limit=510)
    assert phase == "done" and len(shots) == 8
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"frames": result["frames"], "ground_y": stage.ground_y,
            "walk_and_pursuit": "PASS", "jump_and_landing": "PASS", "weapon_drop_floor": "PASS",
            "screenshots": shots, "records": records}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    result = verify(output)
    (output / "factory-ground-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
