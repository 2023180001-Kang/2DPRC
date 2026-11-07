"""Exercise real SDL enemy encounters and locked progression; capture evidence."""

import json
from random import Random
from unittest.mock import patch

import pico2d
import pico2d.pico2d as core
import sdl2

import main
from events import poll_events
from game import Enemy, Player, Stage, spawn_enemy
from rendering import draw_enemy, draw_health
from resources import ROOT, load_images, release_images
from settings import ARROW_X, ATTACK_RANGE, ENEMY_CHASE_FPS, ENEMY_DEATH_FPS, WIDTH
from tools.verify_runtime import capture, push


def verify_gallery(output):
    images, shots = {}, []
    core.window = core.renderer = None
    core.audio_on = False
    try:
        pico2d.open_canvas(WIDTH, 620, sync=True)
        pico2d.hide_lattice()
        images = load_images()
        for facing in (1, -1):
            pico2d.clear_canvas()
            for frame in range(8):
                draw_enemy(images["enemy"], Enemy(x=80 + frame * 160, foot_y=440,
                                                 facing=facing, animation_time=frame / 6))
                draw_enemy(images["enemy"], Enemy(x=80 + frame * 160, foot_y=240,
                                                 facing=facing, state="CHASE",
                                                 animation_time=frame / ENEMY_CHASE_FPS))
                draw_enemy(images["enemy"], Enemy(x=80 + frame * 160, foot_y=40,
                                                facing=facing, state="DYING",
                                                animation_time=frame / ENEMY_DEATH_FPS))
            filename = f"enemy-poses-{'right' if facing > 0 else 'left'}.png"
            capture(output / filename)
            shots.append(filename)
            pico2d.update_canvas()
    finally:
        release_images(images)
        pico2d.close_canvas()
        core.window = core.renderer = None
        core.audio_on = False
    return shots


def verify_encounters(output):
    player = Player()
    stages, spawned, records, shots = [], [], [], []
    tick, clock = -1, 0.0
    expected = {
        0: (1, "IDLE", ()), 1: (1, "IDLE", ()), 10: (1, "DYING", ()),
        30: (1, "DYING", ()), 69: (1, "DYING", ()), 70: (1, "DEAD", (1,)),
        75: (2, "IDLE", (-1,)), 80: (2, "IDLE", (-1,)), 85: (2, "DYING", (-1,)),
        90: (1, "DEAD", (1,)), 100: (2, "DYING", (-1,)),
        160: (2, "DEAD", (-1, 1)), 165: (2, "DEAD", (-1, 1)), 175: (2, "DEAD", (-1, 1)),
    }

    def create_enemy(rng=None, spawn_x=WIDTH / 2, *, stage_number=1):
        enemy = spawn_enemy(Random(100 + stage_number), spawn_x=spawn_x, stage_number=stage_number)
        spawned.append((stage_number, enemy))
        return enemy

    def create_stage(items):
        stage = Stage(items)
        stages.append(stage)
        return stage

    def feed(controls):
        nonlocal tick, clock
        tick += 1
        clock = (tick + 1) / 60
        stage = stages[0]
        if tick == 0:
            poll_events(controls)
            push("focus", True)
        if tick in (1, 11, 75, 80, 100, 165, 175):
            player.x = ARROW_X[1]
        if tick == 10:
            player.x, player.facing = stage.enemy.x - 70, 1
            push("down", "a")
            push("up", "a")
        if tick == 69:
            player.x = 800
        if tick == 85:
            player.x, player.facing, player.weapon = stage.enemy.x + 70, -1, "steel_pipe"
            push("down", "a")
            push("up", "a")
        if tick in (90, 170):
            player.x = ARROW_X[-1]
        if tick == 180:
            push("quit")
        return poll_events(controls)

    draw_arrows = main.draw_stage_arrows

    def observe_arrows(images, number, elapsed, *, directions):
        stage = stages[0]
        assert directions == stage.visible_arrows
        if tick in expected:
            expected_number, expected_state, expected_directions = expected[tick]
            assert (number, directions) == (expected_number, expected_directions)
            assert stage.enemy.alive if expected_state == "IDLE" else stage.enemy.state == expected_state
        if tick == 69:
            assert stage.enemy.frame == 7 and not stage.enemy.defeated
        draw_arrows(images, number, elapsed, directions=directions)

    def observe_enemy(image, enemy):
        draw_enemy(image, enemy)
        assert image.h == 1024 and enemy.row in (0, 1, 3)
        stage = stages[0]
        records.append({"tick": tick, "stage": stage.number, "x": enemy.x,
                        "state": enemy.state, "frame": enemy.frame,
                        "animation_time": enemy.animation_time, "arrows": stage.visible_arrows})
        if tick == 10:
            assert player.weapon is None and enemy.state == "DYING"
        if tick == 85:
            assert player.weapon == "steel_pipe" and enemy.state == "DYING"

    def observe_health(image, current):
        draw_health(image, current)
        assert current.health == 3
        if tick in expected:
            filename = f"enemy-gameplay-{tick:03d}.png"
            capture(output / filename)
            shots.append(filename)

    with (patch("game.spawn_enemy", side_effect=create_enemy), patch("main.Stage", side_effect=create_stage),
          patch("main.Player", return_value=player), patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_stage_arrows", side_effect=observe_arrows),
          patch("main.draw_enemy", side_effect=observe_enemy), patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=190)
    assert result["frames"] == 180
    assert [number for number, _ in spawned] == [1, 2]
    assert records[90]["stage"] == 1 and records[100]["stage"] == 2
    second_before_return = records[89]["animation_time"] + 1 / 60
    assert abs(records[100]["animation_time"] - second_before_return) < 1e-8
    for number in (1, 2):
        # Chasing can change x before the hit; dying/dead positions stay fixed.
        assert len({record["x"] for record in records
                    if record["stage"] == number and record["state"] in ("DYING", "DEAD")}) == 1
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"frames": result["frames"], "fixed_dt": 1 / 60, "spawned_per_map": {"1": 1, "2": 1},
            "live_and_dying_exit_blocked": "PASS", "unlock_after_full_death": "PASS",
            "return_and_no_respawn": "PASS", "off_map_death_paused": "PASS",
            "final_map_no_third_stage": "PASS", "screenshots": shots}


def verify_running_attacks(output):
    """Start outside reach, then hit while holding run and A in the real loop."""
    results = []
    for weapon in (None, "dagger", "steel_pipe"):
        for facing in (1, -1):
            enemy = Enemy(x=WIDTH / 2, facing=-facing)
            stage = Stage([], enemy=enemy)
            player = Player(x=enemy.x - facing * 500, facing=facing, weapon=weapon)
            tick, clock = -1, 0.0
            attack_tick = hit_tick = dead_tick = None
            shots = []
            label = f"{weapon or 'unarmed'}-{'right' if facing > 0 else 'left'}"

            def feed(controls):
                nonlocal tick, clock, attack_tick
                tick += 1
                clock = (tick + 1) / 60
                if tick == 0:
                    poll_events(controls)
                    push("focus", True)
                    push("down", "right" if facing > 0 else "left")
                    push("down", "lshift")
                distance = facing * (enemy.x - player.x)
                if attack_tick is None and distance <= 145:
                    assert distance > ATTACK_RANGE
                    attack_tick = tick
                    push("down", "a")
                if dead_tick is not None and tick > dead_tick + 12:
                    push("quit")
                return poll_events(controls)

            def observe(image, current):
                nonlocal hit_tick, dead_tick
                draw_health(image, current)
                checkpoint = None
                if tick == attack_tick:
                    assert enemy.alive and current.attacking
                    assert facing * (enemy.x - current.x) > ATTACK_RANGE
                    checkpoint = "started-outside-range"
                if enemy.state == "DYING" and hit_tick is None:
                    hit_tick = tick
                    assert attack_tick is not None and hit_tick > attack_tick
                    assert current.attacking and current.attack_hit
                    assert stage.visible_arrows == ()
                    checkpoint = "hit-during-run"
                if enemy.defeated and dead_tick is None:
                    dead_tick = tick
                    assert stage.visible_arrows == (1,)
                    checkpoint = "dead-and-unlocked"
                if enemy.state == "DYING":
                    assert stage.visible_arrows == ()
                if checkpoint:
                    filename = f"enemy-running-{label}-{checkpoint}.png"
                    capture(output / filename)
                    shots.append(filename)

            with (patch("main.Stage", return_value=stage), patch("main.Player", return_value=player),
                  patch("main.poll_events", side_effect=feed),
                  patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
                  patch("main.draw_health", side_effect=observe)):
                result = main.run(frame_limit=220)
            assert hit_tick is not None and dead_tick is not None and len(shots) == 3
            assert stage.number == 1 and player.health == 3
            assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
            results.append({"weapon": weapon, "facing": facing, "frames": result["frames"],
                            "attack_tick": attack_tick, "hit_tick": hit_tick, "dead_tick": dead_tick,
                            "running_hit_and_unlock": "PASS", "screenshots": shots})
    return results


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    result = {"pose_screenshots": verify_gallery(output), "encounters": verify_encounters(output),
              "running_attacks": verify_running_attacks(output)}
    (output / "enemies-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
