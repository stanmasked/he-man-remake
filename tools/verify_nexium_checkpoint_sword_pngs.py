"""Genuine guest HUD proof: checkpoint, native defeat, respawn, two X hits.

No direct emulator/guest memory reads, game state overrides or fake frame
generation. All pixels must come from NeXium's original guest frame_rx.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from instrument_nexium_checkpoint_sword import FRAMES, HID_EVENTS

ALIVE = (101, 121, 231)
EMPTY = (81, 59, 73)
ENEMY = (109, 200, 225)
FLAG_YELLOW = (119, 205, 255)
FLAG_GREEN = (166, 228, 119)
COUNTER_OFF = (81, 61, 40)
COUNTER_ON = (138, 213, 66)
DENSE = tuple(range(116, 131))


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    states = {}
    for frame in FRAMES:
        path = folder / f"raster-frame-{frame:04}.png"
        if not path.is_file():
            raise FileNotFoundError(f"Real NeXium guest frame missing: {frame}")
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError(f"Frame {frame} is not genuine PNG")
            rgb = image.convert("RGB")
        pixels, colors, x = describe(rgb)
        if pixels != 192 or colors < 8:
            raise ValueError(f"Frame {frame} lacks C99 renderer world-x marker")
        hp_ticks = [rgb.getpixel((t, 18)) for t in (18, 36, 54)]
        enemy_ticks = [rgb.getpixel((t, 18)) for t in (226, 244)]
        if any(v not in (ALIVE, EMPTY) for v in hp_ticks):
            raise ValueError(f"Frame {frame}: invalid player HP RGB")
        hp = sum(v == ALIVE for v in hp_ticks)
        if hp_ticks != [ALIVE] * hp + [EMPTY] * (3 - hp):
            raise ValueError(f"Frame {frame}: noncontiguous player HP")
        if any(v not in (ENEMY, EMPTY) for v in enemy_ticks):
            raise ValueError(f"Frame {frame}: invalid enemy HP RGB")
        enemy_hp = sum(v == ENEMY for v in enemy_ticks)
        if enemy_ticks != [ENEMY] * enemy_hp + [EMPTY] * (2 - enemy_hp):
            raise ValueError(f"Frame {frame}: noncontiguous enemy HP")
        flag = FLAG_YELLOW if frame == 30 else FLAG_GREEN
        if rgb.getpixel((207, 250)) != flag:
            raise ValueError(f"Frame {frame}: checkpoint flag not grounded")
        counter = rgb.getpixel((522, 62))
        if counter not in (COUNTER_OFF, COUNTER_ON):
            raise ValueError(f"Frame {frame}: corrupt native respawn indicator")
        states[frame] = {"frame": frame, "player_hp": hp, "enemy_hp": enemy_hp,
                         "marker_x": round(x, 2), "native_counter": counter,
                         "colors": colors}

    approach_x = states[80]["marker_x"]
    if not any(abs(approach_x - v) < 0.51 for v in (205.5, 209.5)):
        raise ValueError("Unexpected predeath real D-pad distance")
    for frame, expected_hp, enemy_hp, respawn, x in (
        (30, 3, 2, COUNTER_OFF, 125.5),
        (80, 2, 2, COUNTER_OFF, approach_x),
        (105, 1, 2, COUNTER_OFF, approach_x),
        (140, 2, 1, COUNTER_ON, 205.5),
        (160, 2, 0, COUNTER_ON, 205.5),
        (185, 2, 0, COUNTER_ON, 205.5),
    ):
        state = states[frame]
        if (state["player_hp"], state["enemy_hp"],
                state["native_counter"]) != (expected_hp, enemy_hp, respawn):
            raise ValueError(f"Frame {frame}: invalid combat/respawn HP state")
        if abs(state["marker_x"] - x) > 3:
            raise ValueError(f"Frame {frame}: incorrect world-x marker")

    death = [f for f in DENSE if states[f]["player_hp"] == 0]
    if len(death) != 1 or death[0] == DENSE[-1]:
        raise ValueError(f"Native death frame absent, duplicated or terminal: {death}")
    died_at = death[0]
    recovered = died_at + 1
    if states[recovered]["player_hp"] != 3:
        raise ValueError("Real guest missing immediate native HP restoration")
    for f in DENSE:
        state = states[f]
        if state["enemy_hp"] != 2:
            raise ValueError("Enemy attacked before native defeat/recovery")
        expected_x = approach_x if f <= died_at else 205.5
        if abs(state["marker_x"] - expected_x) > 0.51:
            raise ValueError("Character moved before death or missed checkpoint recovery")
        counter = COUNTER_OFF if f <= died_at else COUNTER_ON
        if state["native_counter"] != counter:
            raise ValueError("Wrong native respawn marker chronology")
        if f < died_at and state["player_hp"] != 1:
            raise ValueError("Predeath contact damage progression was altered")
        if f > recovered and state["player_hp"] not in (2, 3):
            raise ValueError("Postrespawn contact damage immunity is broken")
    log_path = folder / "raster-runner.log"
    events = set(log_path.read_text().splitlines())
    for frame in FRAMES:
        if not any(line.startswith(f"HEMAN_GUEST_FRAME_PNG frame={frame} ")
                   for line in events):
            raise ValueError(f"Missing genuine frame_rx log for frame {frame}")
    for frame, action in HID_EVENTS:
        if f"HEMAN_CHECKPOINT_SWORD_HID frame={frame} {action}" not in events:
            raise ValueError(f"Missing exact real NeXium HID event {frame}: {action}")
    return {
        "checkpoint_and_natural_death_confirmed": True,
        "natural_death_frame": died_at,
        "native_recovery_frame": recovered,
        "real_postrespawn_x_attacks": True,
        "enemy_health_after_each_attack": [states[140]["enemy_hp"],
                                           states[160]["enemy_hp"]],
        "hero_health_after_victory": states[185]["player_hp"],
        "guest_frames": list(FRAMES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: real NeXium checkpoint native defeat, X strikes 2->1->0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
