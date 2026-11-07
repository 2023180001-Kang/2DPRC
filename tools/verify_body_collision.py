"""Verify contact idle, double-jump clearance and corpse platforms via SDL."""

import json
from unittest.mock import patch

import sdl2

import main
from events import poll_events
from game import Enemy, Player, Stage
from rendering import draw_health
from resources import ROOT
from settings import CORPSE_HEIGHT, GROUND_Y, PLAYER_BODY_HALF_WIDTH
from tools.verify_runtime import capture, push


def verify(output):
    player, enemy = Player(), Enemy(x=800)
    stage = Stage([], enemy=enemy)
    tick, clock, phase, phase_tick = -1, 0.0, "approach", 0
    records, screenshots, checkpoints = [], [], []
    pending_shot = None

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
        nonlocal tick, clock
        tick += 1
        clock = (tick + 1) / 60
        left, _, right, top = enemy.collision_bounds
        left -= PLAYER_BODY_HALF_WIDTH
        right += PLAYER_BODY_HALF_WIDTH
        if tick == 0:
            poll_events(controls)
            push("focus", True)
            keys(down=("right", "lshift"))
        if phase == "approach" and player.x >= left - 1e-7:
            change("push_live", "live-contact")
        elif phase == "push_live" and tick - phase_tick >= 15:
            assert player.display_state == "IDLE"
            keys(down=("space",))
            change("jump_live")
        elif phase == "jump_live":
            keys(up=("space",))
            if tick - phase_tick == 20:
                keys(down=("space",))
                change("double_live", "live-double-jump")
        elif phase == "double_live":
            keys(up=("space",))
            assert player.jump_count == 2
            if player.x > right + 20:
                assert enemy.alive and stage.visible_arrows == ()
                keys(down=("left",), up=("right", "lshift"))
                change("brake_live", "live-jump-cleared")
        elif phase == "brake_live" and player.horizontal_speed <= 0:
            keys(up=("left",))
            change("land_live")
        elif phase == "land_live" and player.grounded:
            assert player.x > right
            keys(down=("left", "lshift"))
            change("return_live", "live-beyond-landed")
        elif phase == "return_live" and player.x <= right + 1e-7:
            change("push_live_right", "live-right-contact")
        elif phase == "push_live_right" and tick - phase_tick >= 15:
            assert player.display_state == "IDLE"
            if player.grounded:
                keys(down=("a",))
                change("kill", "contact-attack")
        elif phase == "kill":
            keys(up=("a",))
            if enemy.defeated:
                change("push_corpse", "corpse-contact")
        elif phase == "push_corpse" and tick - phase_tick >= 20:
            assert abs(player.x - right) < 1e-6 and player.display_state == "IDLE"
            keys(down=("space",))
            change("jump_on")
        elif phase == "jump_on":
            keys(up=("space",))
            if player.x <= enemy.x + 5:
                keys(down=("right",), up=("left", "lshift"))
                change("brake_above")
        elif phase == "brake_above" and player.horizontal_speed >= 0:
            keys(up=("right",))
            change("land_on")
        elif phase == "land_on" and player.grounded:
            assert abs(player.foot_y - top) < 1e-6
            change("stand_on", "corpse-top-landing")
        elif phase == "stand_on" and tick - phase_tick >= 15:
            assert abs(player.foot_y - top) < 1e-6
            keys(down=("left",))
            change("walk_off", "standing-on-corpse")
        elif phase == "walk_off" and player.x <= left and not player.grounded:
            change("fall_off", "walk-off-fall")
        elif phase == "fall_off" and player.grounded:
            assert player.foot_y == GROUND_Y
            keys(down=("right", "lshift"), up=("left",))
            change("return_left", "walk-off-landed")
        elif phase == "return_left" and player.x >= left - 1e-7:
            change("push_left", "corpse-left-contact")
        elif phase == "push_left" and tick - phase_tick >= 15:
            assert player.display_state == "IDLE"
            keys(down=("space",))
            change("jump_over")
        elif phase == "jump_over":
            keys(up=("space",))
            if player.x > right + 20:
                keys(down=("left",), up=("right", "lshift"))
                change("brake_beyond", "jump-over-corpse")
        elif phase == "brake_beyond" and player.horizontal_speed <= 0:
            keys(up=("left",))
            change("land_beyond")
        elif phase == "land_beyond" and player.grounded:
            assert player.x > right and player.foot_y == GROUND_Y
            change("done", "beyond-corpse-landed")
        elif phase == "done" and tick - phase_tick >= 20:
            push("quit")
        assert tick < 800, (phase, vars(player))
        return poll_events(controls)

    def observe(image, current):
        nonlocal pending_shot
        draw_health(image, current)
        left, _, right, top = enemy.collision_bounds
        if left - PLAYER_BODY_HALF_WIDTH + 1e-6 < current.x < right + PLAYER_BODY_HALF_WIDTH - 1e-6:
            assert current.foot_y >= top - 1e-6
        if phase in ("push_live", "push_live_right", "push_corpse", "push_left"):
            assert current.grounded and current.horizontal_speed == 0 and current.display_state == "IDLE"
        if phase == "kill" and current.attacking:
            assert current.display_state == "ATTACK"
        assert current.health == 100
        records.append({"tick": tick, "phase": phase, "x": current.x, "foot_y": current.foot_y,
                        "speed": current.horizontal_speed, "enemy": enemy.state, "support": current.support_y,
                        "display_state": current.display_state, "jumps": current.jump_count})
        if pending_shot:
            filename = f"collision-{pending_shot}.png"
            capture(output / filename)
            screenshots.append(filename)
            pending_shot = None

    # Keep this obstacle course stationary; verify_enemy_ai covers live pursuit.
    with (patch.object(enemy, "update", side_effect=lambda dt, player=None: Enemy.update(enemy, dt)),
          patch("main.Player", return_value=player), patch("main.Stage", return_value=stage),
          patch("main.poll_events", side_effect=feed), patch("main.perf_counter", side_effect=lambda: clock),
          patch("main.sleep"), patch("main.draw_health", side_effect=observe)):
        result = main.run(frame_limit=810)
    assert phase == "done" and len(screenshots) == 14
    assert enemy.defeated and stage.visible_arrows == (1,)
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"frames": result["frames"], "fixed_dt": 1 / 60,
            "live_enemy_blocking": "PASS", "live_double_jump_clearance": "PASS", "contact_idle": "PASS",
            "contact_attack": "PASS", "corpse_sides": "PASS",
            "corpse_landing_and_standing": "PASS", "walk_off_fall": "PASS", "jump_over": "PASS",
            "corpse_top": GROUND_Y + CORPSE_HEIGHT, "screenshots": screenshots}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    result = verify(output)
    (output / "body-collision-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
