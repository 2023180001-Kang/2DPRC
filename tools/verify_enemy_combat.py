"""Verify enemy melee and actual HP gauge pixels through the SDL game loop."""

import json
from unittest.mock import patch

from PIL import Image, ImageChops
import sdl2

import main
from events import poll_events
from game import Enemy, Player, Stage
from rendering import draw_health
from resources import ROOT
from settings import (
    ENEMY_ATTACK_HIT_TIME, GROUND_Y, HEALTH_BAR_WIDTH, HEALTH_FILL_BOUNDS, HUD_MARGIN,
)
from tools.verify_runtime import capture, push


def verify_case(output, label, facing=1, dodge=None, counter=False):
    player = Player(x=640, facing=facing)
    enemy = Enemy(x=640 + facing * (300 if dodge is None and not counter else 64))
    stage = Stage([], enemy=enemy)
    tick, clock = -1, 0.0
    health_changes, attacks, shots = [], [], []
    poses = set()
    previous_health = None
    previous_state = None
    zero_tick = None
    baseline_hud = None
    attack_x = attack_facing = None

    def feed(controls):
        nonlocal tick, clock
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
        if tick == 1:
            if dodge == "retreat":
                push("down", "left")
                push("down", "lshift")
            elif dodge == "jump":
                push("down", "space")
            elif dodge == "behind":
                player.x = enemy.x + 64
        if tick == 2 and dodge == "jump":
            push("up", "space")
        if tick == 10 and counter:
            push("down", "a")
            push("up", "a")
        if ((dodge and tick == 60) or (counter and tick == 100)
                or (zero_tick is not None and tick >= zero_tick + 60)):
            push("quit")
        return poll_events(controls)

    def screenshot(checkpoint):
        filename = f"enemy-combat-{label}-{checkpoint}.png"
        capture(output / filename)
        shots.append(filename)
        return output / filename

    def verify_gauge(path, health):
        nonlocal baseline_hud
        scale = HEALTH_BAR_WIDTH / 2129
        left, top, right, bottom = HEALTH_FILL_BOUNDS
        with Image.open(path) as screen:
            y = round(HUD_MARGIN + (top + bottom) / 2 * scale)
            for fraction in (1 / 6, 1 / 2, 5 / 6):
                x = round(HUD_MARGIN + (left + (right - left) * fraction) * scale)
                r, g, b = screen.getpixel((x, y))[:3]
                if fraction < health / 3:
                    assert b > g + 15 and g > r + 15, (health, fraction, (r, g, b))
                else:
                    assert (r, g, b) == (3, 7, 15), (health, fraction, (r, g, b))
            hud = screen.crop((HUD_MARGIN, HUD_MARGIN, HUD_MARGIN + HEALTH_BAR_WIDTH, 77)).convert("RGB")
            if baseline_hud is None:
                baseline_hud = hud
            else:
                bounds = ImageChops.difference(baseline_hud, hud).getbbox()
                assert bounds is not None
                x1, y1, x2, y2 = bounds
                assert left * scale - 2 <= x1 and x2 <= right * scale + 2
                assert top * scale - 2 <= y1 and y2 <= bottom * scale + 2

    def observe(image, current):
        nonlocal previous_health, previous_state, zero_tick, attack_x, attack_facing
        draw_health(image, current)
        assert 0 <= current.health <= 3
        if enemy.state == "ATTACK":
            assert enemy.row == 2 and not stage.visible_arrows
            if previous_state != "ATTACK":
                attacks.append(tick)
                attack_x, attack_facing = enemy.x, enemy.facing
            assert (enemy.x, enemy.facing) == (attack_x, attack_facing)
            if len(attacks) == 1 and enemy.frame not in poses:
                poses.add(enemy.frame)
                screenshot(f"attack-frame-{enemy.frame}")
        if current.health != previous_health:
            if previous_health is not None:
                assert previous_health - current.health == 1
                assert enemy.attack_hit and tick - attacks[-1] >= round(ENEMY_ATTACK_HIT_TIME * 60)
            health_changes.append({"tick": tick, "health": current.health})
            verify_gauge(screenshot(f"hp-{current.health}"), current.health)
            previous_health = current.health
            if current.health == 0:
                zero_tick = tick
        if counter and enemy.state != previous_state and enemy.state in ("DYING", "DEAD"):
            screenshot(enemy.state.lower())
        previous_state = enemy.state

    with (patch("main.Player", return_value=player), patch("main.Stage", return_value=stage),
          patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_health", side_effect=observe)):
        result = main.run(frame_limit=600)
    if dodge:
        assert player.health == 3 and enemy.attack_hit
        assert len(attacks) == 1 and poses == set(range(8))
    elif counter:
        assert player.health == 3 and enemy.defeated and stage.visible_arrows == (1,)
    else:
        assert [record["health"] for record in health_changes] == [3, 2, 1, 0]
        assert len(attacks) == 3 and poses == set(range(8))
        assert all(b - a >= 76 for a, b in zip(attacks, attacks[1:]))
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"case": label, "frames": result["frames"], "status": "PASS",
            "health_changes": health_changes, "attack_start_ticks": attacks,
            "screenshots": shots, "gauge_pixels_and_portrait_frame": "PASS"}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    cases = [verify_case(output, "enemy-on-right", 1), verify_case(output, "enemy-on-left", -1)]
    cases += [verify_case(output, f"dodge-{dodge}", dodge=dodge) for dodge in ("retreat", "jump", "behind")]
    cases.append(verify_case(output, "counterattack", counter=True))
    result = {"fixed_dt": 1 / 60, "cases": cases}
    (output / "enemy-combat-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
