"""Verify full-speed turns after a running kill using actual SDL key events."""

import json
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Enemy, Player, Stage
from rendering import draw_health
from resources import ROOT
from settings import RUN_SPEED
from tools.verify_runtime import capture, push


def verify_case(output, weapon, direction, contact):
    enemy = Enemy(x=640, facing=-direction)
    player = Player(x=640 - direction * 500, facing=direction, weapon=weapon)
    stage = Stage([], enemy=enemy)
    forward = "right" if direction > 0 else "left"
    reverse = "left" if direction > 0 else "right"
    shift = "lshift" if direction > 0 else "rshift"
    label = f"{weapon or 'unarmed'}-{forward}-{'contact' if contact else 'immediate'}"
    tick, clock = -1, 0.0
    attack_tick = hit_tick = turn_tick = None
    before_turn = None
    shots, speeds = [], []

    def feed(controls):
        nonlocal tick, clock, attack_tick, hit_tick, turn_tick, before_turn
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
            push("down", forward)
            push("down", shift)
        if attack_tick is None and direction * (enemy.x - player.x) <= 145:
            assert abs(player.horizontal_speed - direction * RUN_SPEED) < 1e-6
            attack_tick = tick
            push("down", "a")
        if enemy.state == "DYING" and hit_tick is None:
            hit_tick = tick
            turn_tick = tick + (6 if contact else 0)
            push("up", "a")
        if tick == turn_tick:
            if contact:
                assert player.horizontal_speed == 0
            before_turn = player.x
            push("up", forward)
            push("down", reverse)
        if turn_tick is not None and tick >= turn_tick + 8:
            push("quit")
        return poll_events(controls)

    def observe(image, current):
        draw_health(image, current)
        assert current.health == 3 and stage.number == 1
        checkpoint = None
        if enemy.state == "DYING" and hit_tick is None:
            checkpoint = "hit"
        if turn_tick is not None and tick >= turn_tick:
            assert abs(current.horizontal_speed + direction * RUN_SPEED) < 1e-6
            assert -direction * (current.x - before_turn) > 0
            speeds.append(current.horizontal_speed)
            if tick == turn_tick:
                checkpoint = "turn"
            elif tick == turn_tick + 6:
                checkpoint = "running-away"
        if checkpoint:
            filename = f"kill-turn-{label}-{checkpoint}.png"
            capture(output / filename)
            shots.append(filename)

    with (patch("main.Player", return_value=player), patch("main.Stage", return_value=stage),
          patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_health", side_effect=observe)):
        result = main.run(frame_limit=120)
    assert turn_tick is not None and len(speeds) == 8 and len(shots) == 3
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"weapon": weapon, "direction": direction, "body_contact_before_turn": contact,
            "frames": result["frames"], "attack_tick": attack_tick, "hit_tick": hit_tick,
            "turn_tick": turn_tick, "turn_speeds": speeds, "full_speed_turn": "PASS",
            "screenshots": shots}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    cases = [verify_case(output, weapon, direction, contact)
             for weapon in (None, "dagger", "steel_pipe")
             for direction in (1, -1) for contact in (False, True)]
    result = {"fixed_dt": 1 / 60, "frames": sum(case["frames"] for case in cases), "cases": cases}
    (output / "kill-turn-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
