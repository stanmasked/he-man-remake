"""Fail-closed genuine NeXium guest PNG evidence for B-retry after victory.

This verifier first runs the immutable Stage 052 checkpoint death/X victory
contract, then observes a real new B press resetting the defeated enemy and
two new X attacks. It never reads or changes emulator RAM.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from instrument_nexium_postvictory_b import RETRY_FRAMES, RETRY_EVENTS
from verify_nexium_checkpoint_sword_pngs import (
    ALIVE, EMPTY, ENEMY, FLAG_GREEN, COUNTER_ON,
    verify as verify_first_victory,
)


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    first = verify_first_victory(folder)
    states = {}
    for frame in RETRY_FRAMES:
        path = folder / f"raster-frame-{frame:04}.png"
        if not path.is_file():
            raise FileNotFoundError(f"Missing original guest retry PNG: {frame}")
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError(f"Frame {frame}: non-PNG retry evidence")
            rgb = image.convert("RGB")
        nmarkers, colors, marker_x = describe(rgb)
        if nmarkers != 192 or colors < 8 or abs(marker_x - 205.5) > 0.51:
            raise ValueError(f"Frame {frame}: world x=90 marker missing")
        if rgb.getpixel((207, 250)) != FLAG_GREEN:
            raise ValueError(f"Frame {frame}: checkpoint unexpectedly inactive")
        if rgb.getpixel((522, 62)) != COUNTER_ON:
            raise ValueError(f"Frame {frame}: native respawn marker missing")
        hero_bar = [rgb.getpixel((x, 18)) for x in (18, 36, 54)]
        enemy_bar = [rgb.getpixel((x, 18)) for x in (226, 244)]
        if any(p not in (ALIVE, EMPTY) for p in hero_bar):
            raise ValueError(f"Frame {frame}: corrupt hero HP RGB")
        if any(p not in (ENEMY, EMPTY) for p in enemy_bar):
            raise ValueError(f"Frame {frame}: corrupt enemy HP RGB")
        hp = hero_bar.count(ALIVE)
        enemy_hp = enemy_bar.count(ENEMY)
        if hero_bar != [ALIVE] * hp + [EMPTY] * (3 - hp):
            raise ValueError(f"Frame {frame}: disordered hero HP")
        if enemy_bar != [ENEMY] * enemy_hp + [EMPTY] * (2 - enemy_hp):
            raise ValueError(f"Frame {frame}: disordered enemy HP")
        states[frame] = (hp, enemy_hp)

    # All pre-reset captures must still show the defeated enemy. Manual B
    # is scheduled on frame 194, and observed on a later guest game step.
    if any(states[f][1] != 0 for f in (190, 191, 192, 193)):
        raise ValueError("Enemy respawned before real B input")

    # A real reset should briefly restore the whole 3/2 HP encounter
    # before a fresh contact hit; exact HID-to-frame delivery can vary.
    restored = [f for f in range(195, 205) if states[f] == (3, 2)]
    if not restored:
        raise ValueError("B press did not restore 3/2 native combat HP")
    if states[204][1] != 2:
        raise ValueError("Restored enemy changed HP before post-B sword")
    if any(states[f][1] != 2 for f in range(restored[0], 205)):
        raise ValueError("Enemy HP changed before first post-B X")
    for frame, expected in ((220, (2, 1)), (242, (2, 0)),
                            (270, (2, 0))):
        if states[frame] != expected:
            raise ValueError(f"Frame {frame}: wrong second-victory combat HP")

    log_path = folder / "raster-runner.log"
    log_lines = set(log_path.read_text().splitlines())
    for frame in RETRY_FRAMES:
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} "
        if not any(line.startswith(prefix) for line in log_lines):
            raise ValueError(f"Missing genuine retry frame_rx record {frame}")
    for frame, action in RETRY_EVENTS:
        line = f"HEMAN_POSTVICTORY_HID frame={frame} {action}"
        if line not in log_lines:
            raise ValueError(f"Missing exact postvictory HID event {frame}")

    return {
        "first_natural_death_frame": first["natural_death_frame"],
        "first_native_recovery_frame": first["native_recovery_frame"],
        "initial_sword_victory": first["enemy_health_after_each_attack"],
        "postvictory_b_reset_observed_frame": restored[0],
        "postvictory_second_sword_victory": [
            states[220][1], states[242][1]],
        "hero_hp_after_second_victory": states[270][0],
        "retry_guest_frames": list(RETRY_FRAMES),
        "real_B_and_X_events": [list(event) for event in RETRY_EVENTS],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: real NeXium checkpoint victory -> B reset -> two new X kills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
