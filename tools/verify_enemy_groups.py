"""Exercise real six-enemy entry, SDL counterattacks, travel and restart."""

import json
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Player, Stage
from rendering import draw_enemy, draw_health
from resources import ROOT, load_images
from settings import ARROW_X, STAGE_BACKGROUNDS, WIDTH
from tools.verify_runtime import capture, push


def verify_case(output, number):
    player = Player()
    stage = Stage([], number=number)
    original_enemies = stage.enemies
    original_positions = [enemy.x for enemy in original_enemies]
    stages, players, shots, attempted, impacts = [], [], [], set(), []
    tick, clock, phase = -1, 0.0, "combat"
    drawn = []
    previous_feedback = 0.0
    load_count = 0
    all_visible = False

    def make_stage(items):
        current = stage if not stages else Stage(items)
        stages.append(current)
        return current

    def make_player():
        current = player if not players else Player()
        players.append(current)
        return current

    def remember_load():
        nonlocal load_count
        load_count += 1
        return load_images()

    def feed(controls):
        nonlocal tick, clock, phase
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
            push("down", "h")
        elif tick == 1:
            push("up", "h")
        for key in ("left", "right", "a"):
            push("up", key)
        if phase == "combat":
            for index, enemy in enumerate(original_enemies):
                if enemy.state == "ATTACK" and enemy.attack_hit:
                    attempted.add(index)
            if not player.attacking:
                candidates = [enemy for enemy in original_enemies if enemy.alive
                              and abs(enemy.x - player.x) <= 100]
                for enemy in sorted(candidates, key=lambda enemy: abs(enemy.x - player.x)):
                    if original_enemies.index(enemy) in attempted:
                        push("down", "right" if enemy.x >= player.x else "left")
                        push("down", "a")
                        break
            if stage.cleared:
                assert attempted == set(range(6)), (number, attempted)
                assert 1 in stage.visible_arrows
                if number < max(STAGE_BACKGROUNDS):
                    player.x = ARROW_X[1]
                    phase = "next"
                else:
                    player.x = ARROW_X[1]
                    phase = "final"
        elif phase == "next":
            assert stage.number == number + 1 and len(stage.enemies) == 6
            assert not stage.cleared and 1 not in stage.visible_arrows
            player.x = ARROW_X[-1]
            phase = "return"
        elif phase == "return":
            assert stage.number == number and stage.enemies is original_enemies and stage.cleared
            push("down", "r")
            phase = "restart"
        elif phase == "final":
            assert stage.number == number and stage.enemies is original_enemies
            push("down", "r")
            phase = "restart"
        elif phase == "restart":
            assert len(stages) == len(players) == 2
            fresh = stages[-1]
            assert fresh.number == 1 and len(fresh.enemies) == 6
            assert all(enemy.alive for enemy in fresh.enemies)
            assert set(fresh._enemies_by_stage) == {1}
            assert players[-1].health == 100 and not players[-1].hit_test_mode
            push("up", "r")
            phase = "done"
        elif phase == "done":
            push("quit")
        assert tick < 1800, (number, phase, attempted, vars(player),
                             [(enemy.x, enemy.state) for enemy in original_enemies])
        return poll_events(controls)

    def observe_enemy(image, enemy, **kwargs):
        drawn.append(enemy)
        draw_enemy(image, enemy, **kwargs)

    def observe_health(image, current):
        nonlocal all_visible, previous_feedback
        draw_health(image, current)
        active = stages[-1]
        assert len(drawn) == 6 and all(a is b for a, b in zip(drawn, active.enemies))
        drawn.clear()
        if phase == "combat":
            assert current.health == 100 and current.hit_test_mode
            assert all(enemy.foot_y == stage.ground_y for enemy in stage.enemies)
            if not stage.cleared:
                assert 1 not in stage.visible_arrows
            if current.hit_feedback_time > previous_feedback + 1e-9:
                impacts.append(tick)
            previous_feedback = current.hit_feedback_time
            if not all_visible and all(80 < enemy.x < WIDTH - 80 for enemy in original_enemies):
                all_visible = True
                assert all(enemy.alive for enemy in original_enemies)
                name = f"enemy-groups-{number}-six-approaching.png"
                capture(output / name)
                shots.append(name)
            if stage.cleared:
                name = f"enemy-groups-{number}-all-defeated.png"
                capture(output / name)
                shots.append(name)
        if phase == "done":
            name = f"enemy-groups-{number}-restart.png"
            capture(output / name)
            shots.append(name)

    with (patch("main.Stage", side_effect=make_stage), patch("main.Player", side_effect=make_player),
          patch("main.load_images", side_effect=remember_load), patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_enemy", side_effect=observe_enemy), patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=1810)
    assert phase == "done" and load_count == 1
    assert all_visible and impacts and len(shots) == 3
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"stage": number, "frames": result["frames"], "fixed_dt": 1 / 60,
            "spawn_x": original_positions, "attackers": sorted(attempted),
            "hit_effect_ticks": impacts, "all_six_drawn_each_frame": "PASS",
            "all_six_counterattacked_with_sdl_a": "PASS", "full_death_gate": "PASS",
            "travel_and_return": "PASS" if number < 6 else "final_exit_stays",
            "restart_six_enemies": "PASS", "image_loads": load_count, "screenshots": shots}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    results = [verify_case(output, number) for number in STAGE_BACKGROUNDS]
    (output / "enemy-groups-runtime.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
