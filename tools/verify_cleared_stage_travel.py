"""Verify partial-combat retreat and physical travel through a cleared exit via SDL."""

import json
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Controls, Enemy, Player, Stage
from rendering import draw_health
from resources import ROOT
from settings import ARROW_X, STAGE_GROUND_Y
from tools.verify_runtime import capture, push


def verify_case(output, source, running=False):
    ground = STAGE_GROUND_Y[source]
    # Reproduce bodies left at a cleared map's right exit. Only the initial
    # first entry is positioned directly; retreat and re-entry use SDL movement.
    bodies = [Enemy(x=x, foot_y=ground, state="DEAD") for x in (200, 400, 600, 800, 1000, 1200)]
    stage = Stage([], number=source, enemies=bodies)
    player = Player(x=ARROW_X[1])
    assert stage.try_transition(player, Controls())
    target_enemies, target_items = stage.enemies, stage.items
    stages, players, shots = [], [], []
    tick, clock, phase = -1, 0.0, "fight"
    snapshots = None
    back_tick = reentry_tick = None
    walk_start = None
    label = f"{source}-{'run' if running else 'walk'}"

    def make_stage(items):
        current = stage if not stages else Stage(items)
        stages.append(current)
        return current

    def make_player():
        current = player if not players else Player()
        players.append(current)
        return current

    def keys(down=(), up=()):
        for key in up:
            push("up", key)
        for key in down:
            push("down", key)

    def feed(controls):
        nonlocal tick, clock, phase, snapshots, back_tick, reentry_tick, walk_start
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
            push("down", "h")
        elif tick == 1:
            push("up", "h")
        if phase == "fight":
            keys(up=("a", "left"))
            if target_enemies[0].state == "DYING":
                phase = "wait_death"
            elif abs(target_enemies[0].x - player.x) <= 100 and not player.attacking:
                keys(down=("left", "a"))
        elif phase == "wait_death" and target_enemies[0].defeated:
            assert sum(enemy.alive for enemy in target_enemies) == 5
            assert not stage.cleared and 1 not in stage.visible_arrows
            keys(down=("left", "lshift", "space"))
            phase = "retreat"
        elif phase == "retreat":
            keys(up=("space",))
            if stage.number == source:
                keys(up=("left", "lshift"))
                assert stage.cleared and stage.enemies is bodies
                assert stage.collision_enemies == () and 1 in stage.visible_arrows
                back_tick = tick
                snapshots = [vars(enemy).copy() for enemy in target_enemies]
                phase = "land"
        elif phase == "land" and player.grounded:
            keys(down=("right",) + (("lshift",) if running else ()))
            walk_start = player.x
            phase = "reenter"
        elif phase == "reenter":
            if stage.number == source + 1:
                assert stage.enemies is target_enemies and stage.items is target_items
                assert [vars(enemy) for enemy in target_enemies] == snapshots
                assert sum(enemy.alive for enemy in target_enemies) == 5
                assert not stage.cleared and 1 not in stage.visible_arrows
                assert stage.cleared_stages == {source}
                assert walk_start < 1194 and player.grounded
                reentry_tick = tick
                keys(up=("right", "lshift"))
                phase = "reentered"
        elif phase == "reentered":
            keys(down=("r",))
            phase = "restart"
        elif phase == "restart":
            assert len(stages) == 2 and len(players) == 2
            assert stages[-1].number == 1 and stages[-1].cleared_stages == set()
            assert len(stages[-1].enemies) == 6 and not stages[-1].cleared
            assert players[-1].health == 100 and not players[-1].hit_test_mode
            keys(up=("r",))
            phase = "done"
        elif phase == "done":
            push("quit")
        assert tick < 1200, (source, phase, vars(player),
                             [(enemy.x, enemy.state) for enemy in target_enemies])
        return poll_events(controls)

    def observe(image, current):
        draw_health(image, current)
        checkpoint = None
        if phase == "retreat" and not shots:
            checkpoint = "partial-combat"
        elif phase == "reenter" and len(shots) == 1:
            checkpoint = "cleared-route-walking"
        elif phase == "reentered" and len(shots) == 2:
            checkpoint = "partial-combat-reentered"
        elif phase == "done" and len(shots) == 3:
            checkpoint = "restart"
        if checkpoint:
            filename = f"cleared-travel-{label}-{checkpoint}.png"
            capture(output / filename)
            shots.append(filename)

    with (patch("main.Stage", side_effect=make_stage), patch("main.Player", side_effect=make_player),
          patch("main.poll_events", side_effect=feed), patch("main.perf_counter", side_effect=lambda: clock),
          patch("main.sleep"), patch("main.draw_health", side_effect=observe)):
        result = main.run(frame_limit=1210)
    assert phase == "done" and len(shots) == 4
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"source": source, "target": source + 1, "running": running,
            "frames": result["frames"], "fixed_dt": 1 / 60,
            "back_tick": back_tick, "reentry_tick": reentry_tick,
            "walk_start_x": walk_start, "remaining_enemies": 5,
            "physical_reentry_without_jump": "PASS", "off_map_state_preserved": "PASS",
            "new_stage_still_locked": "PASS", "restart_resets_clears": "PASS", "screenshots": shots}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    results = [verify_case(output, source, running=source % 2 == 0) for source in range(1, 6)]
    (output / "cleared-travel-runtime.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
