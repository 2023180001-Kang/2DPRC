"""Verify recognition, pursuit and map persistence in the actual SDL loop."""

import json
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Enemy, Player, Stage
from rendering import draw_health
from resources import ROOT
from settings import (
    ARROW_X, ENEMY_BODY_HALF_WIDTH, ENEMY_DETECTION_RANGE, ENEMY_LOSE_RANGE,
    ENEMY_STOP_DISTANCE, GROUND_Y, PLAYER_BODY_HALF_WIDTH, PLAYER_HALF_WIDTH, WIDTH,
)
from tools.verify_runtime import capture, push


def verify(output):
    player = Player(x=128)
    # Exercise pursuit independently while the attack cooldown is active.
    first, second = Enemy(x=1000, attack_cooldown=1000), Enemy(x=600, attack_cooldown=1000)
    stage = Stage([], enemy=first)
    tick, clock, phase, phase_tick = -1, 0.0, "outside", 0
    pending_shot = "outside-detection"
    shots, checkpoints, records = [], [], []
    frozen_second = None
    death_x = None

    def keys(down=(), up=()):
        for key in up:
            push("up", key)
        for key in down:
            push("down", key)

    def change(next_phase, shot=None):
        nonlocal phase, phase_tick, pending_shot
        phase, phase_tick = next_phase, tick
        if shot:
            pending_shot = shot
            checkpoints.append(shot)

    def feed(controls):
        nonlocal tick, clock, frozen_second, death_x
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
        enemy = stage.enemy
        distance = abs(player.x - enemy.x)
        elapsed = tick - phase_tick
        if phase == "outside":
            assert not enemy.aware and enemy.x == 1000
            if elapsed >= 15:
                keys(down=("right",))
                change("approach")
        elif phase == "approach" and enemy.aware:
            assert enemy.state == "CHASE" and enemy.facing == -1
            keys(down=("left",), up=("right",))
            change("brake_left", "detected-chasing-left")
        elif phase == "brake_left" and player.horizontal_speed <= 0:
            keys(up=("left",))
            change("wait_left")
        elif phase == "wait_left" and enemy.state == "IDLE":
            assert enemy.aware and abs(distance - ENEMY_STOP_DISTANCE) < 1e-6
            change("hold_left", "stopped-before-player")
        elif phase == "hold_left" and elapsed >= 15:
            keys(down=("right", "lshift", "space"))
            change("jump_over")
        elif phase == "jump_over":
            keys(up=("space",))
            if player.x > enemy.x + 140:
                assert enemy.aware and enemy.facing == 1 and player.foot_y > GROUND_Y
                keys(down=("left",), up=("right", "lshift"))
                change("brake_right", "jump-over-reversed-chase")
        elif phase == "brake_right" and player.horizontal_speed <= 0:
            keys(up=("left",))
            change("wait_right")
        elif phase == "wait_right" and enemy.state == "IDLE" and player.grounded:
            assert enemy.aware and enemy.facing == 1
            assert abs(distance - ENEMY_STOP_DISTANCE) < 1e-6
            change("hold_right", "stopped-on-other-side")
        elif phase == "hold_right" and elapsed >= 15:
            # Relocate the target to the farther screen edge to exercise loss
            # deterministically, independent of the earlier jump landing x.
            player.x = PLAYER_HALF_WIDTH if enemy.x > WIDTH / 2 else WIDTH - PLAYER_HALF_WIDTH
            assert abs(player.x - enemy.x) > ENEMY_LOSE_RANGE
            change("lose")
        elif phase == "lose":
            assert not enemy.aware and enemy.state == "IDLE"
            change("lost", "lost-target-idle")
        elif phase == "lost" and elapsed >= 15:
            player.x = enemy.x - 200 if enemy.x > WIDTH / 2 else enemy.x + 200
            player.facing = 1 if player.x < enemy.x else -1
            change("reacquire")
        elif phase == "reacquire" and enemy.aware:
            assert enemy.state == "CHASE"
            change("wait_attack", "reacquired-target")
        elif phase == "wait_attack" and distance <= 130:
            assert enemy.state == "CHASE" and distance > 100
            keys(down=("a",))
            change("attack", "attack-while-enemy-chases")
        elif phase == "attack" and enemy.state == "DYING":
            assert player.attacking and not enemy.aware
            death_x = enemy.x
            keys(up=("a",))
            change("dying", "hit-stops-chase")
        elif phase == "dying":
            assert enemy.x == death_x
            if enemy.defeated:
                assert stage.visible_arrows == (1,)
                change("dead", "dead-unlocks-exit")
        elif phase == "dead" and elapsed >= 15:
            player.x = ARROW_X[1]
            change("enter_second")
        elif phase == "enter_second":
            assert stage.number == 2 and enemy is second
            assert not enemy.aware and stage.visible_arrows == (-1,)
            keys(down=("right",))
            change("approach_second", "second-map-idle")
        elif phase == "approach_second" and enemy.aware:
            assert stage.number == 2 and enemy.state == "CHASE"
            keys(up=("right",))
            change("second_chasing", "second-map-chase")
        elif phase == "second_chasing":
            # Record before leaving; no off-map clock or movement may run.
            player.x, player.horizontal_speed = ARROW_X[-1], 0
            change("leave_second")
        elif phase == "leave_second":
            assert stage.number == 1 and stage.enemy is first
            frozen_second = vars(second).copy()
            change("off_map", "returned-first-map")
        elif phase == "off_map":
            assert vars(second) == frozen_second
            if elapsed >= 30:
                player.x = ARROW_X[1]
                change("revisit_second")
        elif phase == "revisit_second":
            assert stage.number == 2 and stage.enemy is second
            assert vars(second) == frozen_second
            change("resume", "second-map-state-restored")
        elif phase == "resume" and elapsed >= 15:
            assert second.x < frozen_second["x"] and second.aware
            change("done", "second-map-chase-resumed")
        elif phase == "done" and elapsed >= 10:
            push("quit")
        assert tick < 1100, (phase, vars(player), vars(enemy))
        return poll_events(controls)

    def observe(image, current):
        nonlocal pending_shot
        draw_health(image, current)
        enemy = stage.enemy
        assert current.health == 3
        assert enemy.row in (0, 1, 3) and enemy.foot_y == GROUND_Y
        if enemy.alive:
            assert 1 not in stage.visible_arrows
        if (enemy.alive and current.foot_y < GROUND_Y + 136 - 1e-6):
            assert abs(enemy.x - current.x) >= ENEMY_BODY_HALF_WIDTH + PLAYER_BODY_HALF_WIDTH - 1e-6
        records.append({"tick": tick, "phase": phase, "stage": stage.number,
                        "player_x": current.x, "player_y": current.foot_y,
                        "enemy_x": enemy.x, "state": enemy.state, "aware": enemy.aware,
                        "facing": enemy.facing, "frame": enemy.frame, "health": current.health})
        if pending_shot:
            filename = f"enemy-ai-{pending_shot}.png"
            capture(output / filename)
            shots.append(filename)
            pending_shot = None

    with (patch("main.Player", return_value=player), patch("main.Stage", return_value=stage),
          patch("game.spawn_enemy", return_value=second) as spawn,
          patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_health", side_effect=observe)):
        result = main.run(frame_limit=1110)
    assert phase == "done" and second.aware and first.defeated
    spawn.assert_called_once()
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"frames": result["frames"], "fixed_dt": 1 / 60,
            "detection_range": ENEMY_DETECTION_RANGE, "lose_range": ENEMY_LOSE_RANGE,
            "detection_chase_stop_turn_loss_reacquire": "PASS", "no_contact_damage_during_cooldown": "PASS",
            "hit_stops_chase_and_death_unlocks": "PASS", "off_map_pause_and_revisit": "PASS",
            "checkpoints": checkpoints, "screenshots": shots, "records": records}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    result = verify(output)
    (output / "enemy-ai-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
