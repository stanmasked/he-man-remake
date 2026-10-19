"""Verify true NeXium checkpoint auto-respawn after three native contact hits.

Read only actual guest frame_rx PNGs and emulated-controller event logs.
A native zero-HP frame must precede a distinct recovered checkpoint frame.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from instrument_nexium_checkpoint_defeat import FRAMES, HID_EVENTS

ALIVE = (101, 121, 231)
EMPTY = (81, 59, 73)
ENEMY = (109, 200, 225)
FLAG_OFF = (119, 205, 255)
FLAG_ON = (166, 228, 119)
RESPAWN_OFF = (81, 61, 40)
RESPAWN_ON = (138, 213, 66)
DENSE = tuple(range(116, 131))


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    snapshots = {}
    for frame in FRAMES:
        path = folder / f"raster-frame-{frame:04}.png"
        if not path.is_file():
            raise FileNotFoundError(f"Missing real checkpoint guest PNG {frame}")
        with Image.open(path) as source:
            if source.format != "PNG":
                raise ValueError(f"Frame {frame} is not PNG")
            rgb = source.convert("RGB")
        markers, colors, world_x = describe(rgb)
        if markers != 192 or colors < 8:
            raise ValueError(f"Frame {frame}: missing original HUD world marker")
        pixels = [rgb.getpixel((x, 18)) for x in (18, 36, 54)]
        if any(p not in (ALIVE, EMPTY) for p in pixels):
            raise ValueError(f"Frame {frame}: corrupt player health HUD")
        health = sum(p == ALIVE for p in pixels)
        if pixels != [ALIVE] * health + [EMPTY] * (3 - health):
            raise ValueError(f"Frame {frame}: noncontiguous player HP HUD")
        if [rgb.getpixel((x, 18)) for x in (226, 244)] != [ENEMY, ENEMY]:
            raise ValueError(f"Frame {frame}: enemy HP changed without attacks")
        expected_flag = FLAG_OFF if frame == 30 else FLAG_ON
        if rgb.getpixel((207, 250)) != expected_flag:
            raise ValueError(f"Frame {frame}: incorrect checkpoint flag color")
        counter = rgb.getpixel((522, 62))
        if counter not in (RESPAWN_OFF, RESPAWN_ON):
            raise ValueError(f"Frame {frame}: invalid native respawn marker")
        snapshots[frame] = (health, counter, world_x, colors)

    for frame, health, counter, center in (
        (30, 3, RESPAWN_OFF, 125.5),
        (80, 2, RESPAWN_OFF, 209.5),
        (105, 1, RESPAWN_OFF, 209.5),
        (145, 2, RESPAWN_ON, 205.5),
    ):
        actual_hp, actual_counter, actual_x, _ = snapshots[frame]
        if actual_hp != health or actual_counter != counter:
            raise ValueError(f"Frame {frame}: unexpected HP/respawn state")
        if abs(actual_x - center) > 3.0:
            raise ValueError(f"Frame {frame}: wrong world x marker")

    zeros = [t for t in DENSE if snapshots[t][0] == 0]
    if len(zeros) != 1:
        raise ValueError(f"Expected exactly one visible natural death frame: {zeros}")
    death = zeros[0]
    if death == DENSE[-1]:
        raise ValueError("No space left to observe native recovery")
    recovery = death + 1
    if snapshots[recovery][0] != 3:
        raise ValueError("Native next-frame combat recovery not observed")
    if any(snapshots[t][1] != RESPAWN_OFF for t in DENSE if t <= death):
        raise ValueError("Respawn indicator activated before actual defeat")
    if any(snapshots[t][1] != RESPAWN_ON for t in DENSE if t >= recovery):
        raise ValueError("Native respawn marker did not persist after recovery")
    if any(abs(snapshots[t][2] - 209.5) > 3.0 for t in DENSE if t <= death):
        raise ValueError("Player moved away from enemy before defeat")
    if any(abs(snapshots[t][2] - 205.5) > 3.0 for t in DENSE if t >= recovery):
        raise ValueError("Automatic respawn returned to spawn, not checkpoint")
    if any(snapshots[t][0] != 1 for t in DENSE if t < death):
        raise ValueError("Contact cooldown/defeat health progression changed")
    # Normal enemy contact works after native recovery, but two fresh hits
    # cannot occur before the next 30-frame cooldown.
    if any(snapshots[t][0] not in (2, 3) for t in DENSE if t > recovery):
        raise ValueError("Player lost multiple HP immediately after recovery")
    # Reject a spoofed release: "buttons=DRIGHT" has the prefix
    # "buttons=" but is NOT the requested fully released controller.
    log = (folder / "raster-runner.log").read_text()
    log_lines = set(log.splitlines())
    for frame in FRAMES:
        if not any(line.startswith(f"HEMAN_GUEST_FRAME_PNG frame={frame} ")
                   for line in log_lines):
            raise ValueError(f"Missing actual guest capture log for {frame}")
    for frame, action in HID_EVENTS:
        if f"HEMAN_CHECKPOINT_DEFEAT_HID frame={frame} {action}" not in log_lines:
            raise ValueError(f"Missing real D-pad checkpoint event at {frame}")

    return {
        "checkpoint_activated_through_genuine_dpad": True,
        "health_before_death": [snapshots[t][0] for t in (30, 80, 105)],
        "native_death_frame": death,
        "native_recovery_frame": recovery,
        "respawn_world_x": round(snapshots[recovery][2], 2),
        "final_hp_at_frame_145": snapshots[145][0],
        "native_respawn_marker": True,
        "guest_frames": list(FRAMES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: natural 3-hit defeat, next-frame checkpoint respawn in real NeXium")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
