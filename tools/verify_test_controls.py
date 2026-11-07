"""Verify H hit testing and R campaign restart using actual SDL key events."""

import json
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Enemy, Item, Player, Stage
from rendering import camera_offset, draw_health
from resources import ROOT, load_images
from settings import GROUND_Y, STAGE_GROUND_Y, WIDTH
from tools.verify_runtime import capture, push


def verify_case(output, side):
    ground = STAGE_GROUND_Y[5]
    initial_player = Player(health=10, weapon="dagger", foot_y=ground,
                            support_y=ground, ground_y=ground)
    initial_stage = Stage([Item("steel_pipe", 500, foot_y=ground, ground_y=ground)],
                          number=5, enemy=Enemy(x=640 + side * 64, foot_y=ground))
    initial_stage._items_by_stage[2] = []
    initial_stage._enemies_by_stage[2] = Enemy(state="DEAD")
    players, stages, shots, records = [], [], [], []
    tick, clock = -1, 0.0
    protected_hits = 0
    previous_feedback = 0.0
    disable_tick = lethal_tick = restart_tick = None

    def create_player():
        player = initial_player if not players else Player()
        players.append(player)
        return player

    def create_stage(**kwargs):
        stage = initial_stage if not stages else Stage(**kwargs)
        stages.append(stage)
        return stage

    def feed(controls):
        nonlocal tick, clock, disable_tick, restart_tick
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
            push("down", "h")
        if tick == 1:
            push("down", "h")  # Held H must not toggle a second time.
        if protected_hits == 12 and disable_tick is None:
            disable_tick = tick
            push("up", "h")
            push("down", "h")
            push("up", "h")
        if lethal_tick is not None:
            if tick == lethal_tick + 5:
                restart_tick = tick
                push("up", "r")
                for key in ("left", "lshift", "space", "a", "f", "h", "r"):
                    push("down", key)
            if tick == lethal_tick + 15:
                push("quit")
        return poll_events(controls)

    def screenshot(label):
        filename = f"test-controls-{'right' if side > 0 else 'left'}-{label}.png"
        capture(output / filename)
        shots.append(filename)

    def observe(image, current):
        nonlocal protected_hits, previous_feedback, lethal_tick
        draw_health(image, current)
        stage = stages[-1]
        if current is initial_player:
            if current.hit_test_mode:
                assert current.health == 10 and not current.incapacitated
                if previous_feedback <= 1e-9 and current.hit_feedback_time > 1e-9:
                    protected_hits += 1
                    assert camera_offset(current) != (0, 0)
                    if protected_hits in (1, 12):
                        screenshot(f"protected-hit-{protected_hits}")
            if current.incapacitated and lethal_tick is None:
                lethal_tick = tick
                assert disable_tick is not None and protected_hits == 12
                screenshot("mode-off-lethal")
            previous_feedback = current.hit_feedback_time
        else:
            assert restart_tick is not None and len(players) == len(stages) == 2
            assert stage.number == 1 and current.health == 100
            assert current.weapon is None and not current.hit_test_mode
            assert current.x == WIDTH / 2 and current.foot_y == GROUND_Y
            assert current.state == "IDLE" and current.jump_count == 0
            assert not current.attacking and current.horizontal_speed == 0
            assert (current.hurt_time, current.hit_feedback_time, current.death_time) == (0, 0, 0)
            assert set(stage._items_by_stage) == set(stage._enemies_by_stage) == {1}
            assert stage.enemy.alive and 3 <= len(stage.items) <= 5
            if tick == restart_tick:
                assert stage.arrow_time == 0
                screenshot("restart-first-stage")
        records.append({"tick": tick, "stage": stage.number, "hp": current.health,
                        "hit_test_mode": current.hit_test_mode, "state": current.state,
                        "camera": camera_offset(current)})

    with (patch("main.Player", side_effect=create_player),
          patch("main.Stage", side_effect=create_stage),
          patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_health", side_effect=observe),
          patch("main.load_images", wraps=load_images) as resources):
        result = main.run(frame_limit=1100)
    assert protected_hits == 12 and lethal_tick is not None and restart_tick == lethal_tick + 5
    assert len(players) == len(stages) == 2
    resources.assert_called_once()
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"side": side, "status": "PASS", "frames": result["frames"],
            "protected_hits": protected_hits, "mode_off_tick": disable_tick,
            "lethal_tick": lethal_tick, "restart_tick": restart_tick,
            "screenshots": shots, "records": records}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    cases = [verify_case(output, side) for side in (-1, 1)]
    result = {"fixed_dt": 1 / 60, "cases": cases}
    (output / "test-controls-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"cases": [{key: value for key, value in case.items() if key != "records"}
                                for case in cases]}, indent=2))
