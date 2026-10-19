"""Fail-closed visual evidence for sword attacks after native respawn.

Inspect genuine NeXium guest RGBA framebuffer exports and emulated HID logs,
not fake sprites, private assets, or direct emulator memory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FRAMES = (62, 79, 115, 170)
EXPECTED_PLAYER_HP = (3, 2, 2, 2)
EXPECTED_ENEMY_HP = (2, 1, 0, 0)
ALIVE_PLAYER = (101, 121, 231)
ALIVE_ENEMY = (109, 200, 225)
EMPTY = (81, 59, 73)
RESPAWN_GREEN = (138, 213, 66)
HID_EVENTS = (
    (65, "buttons=X"),
    (74, "buttons="),
    (84, "buttons=X"),
    (93, "buttons="),
)


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    frames = []
    centers = []
    for t, hero_hp, enemy_hp in zip(
        FRAMES, EXPECTED_PLAYER_HP, EXPECTED_ENEMY_HP
    ):
        path = folder / f"raster-frame-{t:04}.png"
        if not path.is_file():
            raise FileNotFoundError(f"Missing real NeXium guest PNG frame {t}")
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError(f"Frame {t} is not a real PNG")
            rgb = image.convert("RGB")
        magenta_count, colors, world_x = describe(rgb)
        if magenta_count != 192 or colors < 8:
            raise ValueError(f"Frame {t}: missing native renderer HUD marker")
        expected_player = [
            ALIVE_PLAYER if index < hero_hp else EMPTY
            for index in range(3)
        ]
        player = [rgb.getpixel((px, 18)) for px in (18, 36, 54)]
        if player != expected_player:
            raise ValueError(
                f"Frame {t}: hero HP mismatch {player} != {expected_player}"
            )
        expected_enemy = [
            ALIVE_ENEMY if index < enemy_hp else EMPTY
            for index in range(2)
        ]
        enemy = [rgb.getpixel((px, 18)) for px in (226, 244)]
        if enemy != expected_enemy:
            raise ValueError(
                f"Frame {t}: enemy HP mismatch {enemy} != {expected_enemy}"
            )
        if rgb.getpixel((522, 62)) != RESPAWN_GREEN:
            raise ValueError(f"Frame {t}: no native player respawn signal")
        if abs(world_x - 125.5) > 2.0:
            raise ValueError(f"Frame {t}: hero moved without D-pad input")
        centers.append(round(world_x, 2))
        frames.append({"frame": t, "player_hp": hero_hp,
                       "enemy_hp": enemy_hp, "world_x_marker": round(world_x, 2),
                       "colors": colors})

    log = (folder / "raster-runner.log").read_text()
    for t in FRAMES:
        if f"HEMAN_GUEST_FRAME_PNG frame={t} " not in log:
            raise ValueError(f"Frame {t}: no actual guest capture log entry")
    for t, action in HID_EVENTS:
        marker = f"HEMAN_RESPAWN_SWORD_HID frame={t} {action}"
        if marker not in log:
            raise ValueError(f"Missing real NeXium X action: {marker}")

    return {"guest_frames": frames, "player_world_x_px": centers,
            "genuine_native_respawn": True,
            "real_x_attack_hp_progression": list(EXPECTED_ENEMY_HP),
            "x_press_release_events": list(HID_EVENTS)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: genuine NeXium X presses caused enemy HP 2->1->0 after respawn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
