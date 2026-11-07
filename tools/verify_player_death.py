"""Verify lethal knockback, body clearance, death clips and locked controls via SDL."""

import json
from unittest.mock import patch

from PIL import Image
import pico2d
import pico2d.pico2d as core
import sdl2

import main
import rendering
from events import poll_events
from game import Enemy, Item, Player, Stage
from rendering import draw_character, draw_health
from resources import ROOT, load_images, release_images
from settings import (
    PLAYER_DEATH_FPS, PLAYER_DEATH_FRAMES, WIDTH, STAGE_GROUND_Y,
    PLAYER_DEATH_KNOCKBACK_DISTANCE, PLAYER_DEATH_KNOCKBACK_DURATION,
    PLAYER_DEATH_CLEARANCE, PLAYER_HALF_WIDTH,
)
from tools.verify_runtime import capture, push


def verify_gallery(output):
    images = {}
    core.window = core.renderer = None
    core.audio_on = False
    try:
        pico2d.open_canvas(WIDTH, 760, sync=True)
        pico2d.hide_lattice()
        images = load_images()
        pico2d.clear_canvas()
        for row, (kind, facing) in enumerate((("BACKWARD", 1), ("BACKWARD", -1),
                                              ("FORWARD", 1), ("FORWARD", -1))):
            for index in range(len(PLAYER_DEATH_FRAMES[kind])):
                player = Player(x=80 + index * 160, foot_y=580 - row * 180, health=0,
                                state="DYING", death_kind=kind, death_time=index / PLAYER_DEATH_FPS,
                                facing=facing)
                draw_character(images["character"], player)
        filename = "player-death-poses.png"
        capture(output / filename)
        pico2d.update_canvas()
    finally:
        release_images(images)
        pico2d.close_canvas()
        core.window = core.renderer = None
        core.audio_on = False
    return filename


def verify_case(output, facing, front, weapon, *, edge=False, stage_number=1):
    airborne = weapon == "dagger"
    source_side = facing * (1 if front else -1)
    start_x = (PLAYER_HALF_WIDTH if source_side > 0 else WIDTH - PLAYER_HALF_WIDTH) if edge else 640
    ground_y = STAGE_GROUND_Y[stage_number]
    player = Player(x=start_x, facing=facing, health=1, weapon=weapon,
                    foot_y=ground_y + (60 if airborne else 0), ground_y=ground_y, support_y=ground_y,
                    vertical_speed=200 if airborne else 0,
                    state="JUMP" if airborne else "IDLE", jump_count=int(airborne))
    enemy = Enemy(x=start_x + source_side * 64, foot_y=ground_y)
    items = [Item("dagger", player.x, foot_y=ground_y, ground_y=ground_y)]
    stage = Stage(items, enemy=enemy, number=stage_number)
    expected_kind = "BACKWARD" if front else "FORWARD"
    label = f"{expected_kind.lower()}-{'right' if facing > 0 else 'left'}-{weapon or 'unarmed'}"
    label += "-edge" if edge else (f"-stage-{stage_number}" if stage_number != 1 else "")
    tick, clock = -1, 0.0
    lethal_tick = complete_tick = None
    frames, shots = set(), []
    records = []

    def feed(controls):
        nonlocal tick, clock
        tick += 1
        clock = (tick + 1) / 60
        if tick == 0:
            poll_events(controls)
            push("focus", True)
        if lethal_tick is not None and tick == lethal_tick + 1:
            for key in ("left" if facing > 0 else "right", "lshift", "rshift", "space", "a", "f"):
                push("down", key)
        if tick == 100:
            push("quit")
        return poll_events(controls)

    def observe_hand(image, current, **kwargs):
        assert not current.incapacitated, "A weapon hand overlay was drawn during death"
        draw_character(image, current, **kwargs)

    def observe_character(image, current, **kwargs):
        draw_character(image, current, **kwargs)
        assert image.h == 1280
        if current.incapacitated:
            assert current.character_key == "character" and current.row == 4

    def screenshot(checkpoint):
        filename = f"player-death-{label}-{checkpoint}.png"
        capture(output / filename)
        shots.append(filename)
        return output / filename

    def observe_health(image, current):
        nonlocal lethal_tick, complete_tick
        draw_health(image, current)
        if tick == 0:
            screenshot("alive")
        if current.incapacitated:
            if lethal_tick is None:
                lethal_tick = tick
                assert enemy.state == "ATTACK"
                if airborne:
                    assert current.foot_y > ground_y
            assert (current.health, current.death_kind, current.facing) == (0, expected_kind, facing)
            assert enemy.facing == -source_side, "Enemy turned away from its lethal attack direction"
            progress = min(current.death_time / PLAYER_DEATH_KNOCKBACK_DURATION, 1)
            expected_x = max(PLAYER_HALF_WIDTH, min(WIDTH - PLAYER_HALF_WIDTH,
                start_x - source_side * PLAYER_DEATH_KNOCKBACK_DISTANCE * (1 - (1 - progress) ** 2)))
            assert abs(current.x - expected_x) < 1e-7
            assert current.horizontal_speed == 0 and not current.attacking and enemy.alive
            assert current.weapon == weapon and stage.items == items and len(items) == 1
            assert current.pickup_target(items) is None and stage.number == stage_number
            if current.frame not in frames:
                frames.add(current.frame)
                path = screenshot(f"frame-{current.frame}")
                with Image.open(path) as screen:
                    assert screen.getpixel((280, 44))[:3] == (3, 7, 15)
            if tick == lethal_tick + 10:
                before = (current.death_kind, current.death_time, current.facing)
                assert not current.take_damage(source_x=start_x - source_side * 64)
                assert (current.death_kind, current.death_time, current.facing) == before
            if current.state == "DEAD":
                assert current.frame == PLAYER_DEATH_FRAMES[expected_kind][-1]
                assert current.foot_y == ground_y
                assert abs(current.x - enemy.x) >= PLAYER_DEATH_CLEARANCE - 1e-7
                if complete_tick is None:
                    complete_tick = tick
                    screenshot("last-pose-held")
        records.append({"tick": tick, "health": current.health, "state": current.state,
                        "kind": current.death_kind, "frame": current.frame,
                        "foot_y": current.foot_y, "x": current.x, "facing": current.facing,
                        "enemy_x": enemy.x, "enemy_facing": enemy.facing,
                        "separation": abs(current.x - enemy.x)})

    with (patch("main.Player", return_value=player), patch("main.Stage", return_value=stage),
          patch("main.poll_events", side_effect=feed),
          patch("main.perf_counter", side_effect=lambda: clock), patch("main.sleep"),
          patch("main.draw_character", side_effect=observe_character),
          patch("rendering.draw_character", side_effect=observe_hand),
          patch("main.draw_health", side_effect=observe_health)):
        result = main.run(frame_limit=110)
    assert result["frames"] == 100 and lethal_tick is not None and complete_tick is not None
    assert player.state == "DEAD" and frames == set(PLAYER_DEATH_FRAMES[expected_kind])
    assert enemy.state == "IDLE" and not enemy.aware
    assert not sdl2.SDL_WasInit(sdl2.SDL_INIT_VIDEO)
    return {"kind": expected_kind, "facing": facing, "weapon": weapon, "airborne": airborne,
            "edge": edge, "stage_number": stage_number, "knockback_and_clearance": "PASS",
            "frames": result["frames"], "lethal_tick": lethal_tick, "complete_tick": complete_tick,
            "source_frames": sorted(frames), "clip_and_direction": "PASS", "controls_and_last_pose": "PASS",
            "enemy_attack_facing_preserved": "PASS",
            "screenshots": shots, "records": records}


if __name__ == "__main__":
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    gallery = verify_gallery(output)
    cases = [verify_case(output, facing, front, weapon)
             for facing in (1, -1) for front in (True, False)
             for weapon in (None, "dagger", "steel_pipe")]
    cases += [verify_case(output, facing, front, None, edge=True)
              for facing in (1, -1) for front in (True, False)]
    cases += [verify_case(output, facing, front, "dagger", stage_number=5)
              for facing in (1, -1) for front in (True, False)]
    result = {"fixed_dt": 1 / 60, "gallery": gallery,
              "frames": sum(case["frames"] for case in cases), "cases": cases}
    (output / "player-death-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({**result, "cases": [{k: v for k, v in case.items() if k != "records"}
                                         for case in cases]}, indent=2))
