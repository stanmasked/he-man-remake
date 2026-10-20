"""Fail-closed optical receipt of real synthetic guest FINISH and B retry.

Checks actual 640x360 guest frame_rx PNGs and exact injection logs, never
screenshot overlays or emulator splash images. Not original iOS evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from instrument_nexium_finale import FRAMES, HID_EVENTS

STAGE_ONE = (103, 73, 53)   # 0xff354967 as little-endian screenshot RGB
STAGE_TWO = (191, 230, 241) # 0xfff1e6bf
CLEAR_BORDER = (80, 105, 33)
CLEAR_LETTER = (134, 212, 240)
FINISH_BORDER = (109, 200, 225)   # 0xffe1c86d
FINISH_GLYPH = (191, 230, 241)    # 0xfff1e6bf
FINISH_UNDERLINE = (138, 213, 66) # 0xff42d58a
CYAN_HEIGHT = (0, 255, 255)       # 0xffffff00


def _height_marker(image) -> int:
    # The real raster scene draws a stationary HUD ruler x472..485 and a
    # cyan marker of world-space foot Y. Its shift proves native A jump
    # independently of camera, backdrop and patrolling enemy motion.
    ys = [y for y in range(80, 340)
          if image.getpixel((476, y)) == CYAN_HEIGHT]
    if len(ys) != 9 or max(ys) - min(ys) != 8:
        raise ValueError("No unique real guest world-Y indicator")
    return min(ys)


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    logs = (folder / "raster-runner.log").read_text().splitlines()
    for frame, event in HID_EVENTS:
        prefix = f"HEMAN_FINALE_HID frame={frame} "
        rows = [line for line in logs if line.startswith(prefix)]
        if rows != [prefix + event]:
            raise ValueError(f"Missing or repeated actual guest HID edge {frame}")

    stages, clear, finish, xs, heights, hashes, freeze_bytes = (
        {}, {}, {}, {}, {}, {}, {})
    for frame in FRAMES:
        prefix = f"HEMAN_GUEST_FRAME_PNG frame={frame} "
        records = [line for line in logs if line.startswith(prefix)]
        expected = prefix + "dimensions=640x360 path="
        if len(records) != 1 or not records[0].startswith(expected):
            raise ValueError(f"Missing/duplicate/malformed guest PNG attestation {frame}")
        screenshot = folder / f"raster-frame-{frame:04}.png"
        if not screenshot.is_file():
            raise FileNotFoundError(screenshot)
        recorded = Path(records[0][len(expected):])
        if not recorded.is_absolute() or recorded.resolve() != screenshot.resolve():
            raise ValueError(f"Captured guest PNG path disagrees at {frame}")
        with Image.open(screenshot) as source:
            if source.format != "PNG":
                raise ValueError("Guest capture does not contain a PNG")
            rgb = source.convert("RGB")
        if rgb.size != (640, 360):
            raise ValueError(f"Wrong genuine guest dimensions at frame {frame}")
        count, colors, world_x = describe(rgb)
        if count != 192 or colors < 8:
            raise ValueError(f"Missing real synthetic guest player marker at {frame}")
        color = rgb.getpixel((404, 9))
        if color not in (STAGE_ONE, STAGE_TWO) or rgb.getpixel((408, 9)) != STAGE_TWO:
            raise ValueError(f"Missing source-rendered stage identifier at {frame}")
        stages[frame] = 1 if color == STAGE_ONE else 2
        clear[frame] = (
            rgb.getpixel((547, 47)) == CLEAR_BORDER and
            rgb.getpixel((553, 53)) == CLEAR_LETTER)
        has_border = rgb.getpixel((208, 120)) == FINISH_BORDER
        has_glyph = rgb.getpixel((258, 155)) == FINISH_GLYPH
        has_underline = rgb.getpixel((254, 201)) == FINISH_UNDERLINE
        if len(set((has_border, has_glyph, has_underline))) != 1:
            raise ValueError(f"Partially drawn FINISH panel at frame {frame}")
        finish[frame] = has_border
        heights[frame] = _height_marker(rgb)
        xs[frame] = round(world_x, 2)
        payload = rgb.tobytes()
        hashes[frame] = hashlib.sha256(payload).hexdigest()
        if frame in (490, 515):
            freeze_bytes[frame] = payload

    if [stages[f] for f in FRAMES] != [1, 2, 2, 2, 2, 2, 2, 2, 2]:
        raise ValueError("No genuine first-room CLEAR/A transition into stage 2")
    # The raster scene draws the original native CLEAR HUD for *any*
    # completed room. Thus terminal stage-2 FINISH deliberately coexists
    # with a top-right CLEAR badge; only pre-exit and post-B frames must
    # lack that badge. This is independent of the center FINISH overlay.
    if [f for f in FRAMES if clear[f]] != [75, 465, 490, 515]:
        raise ValueError("Native CLEAR badges disagree with actual room exits")
    if heights[365] > heights[330] - 25:
        raise ValueError("Injected native A jump did not raise real world-Y indicator")
    if [finish[f] for f in FRAMES] != [
            False, False, False, False, True, True, True, False, False]:
        raise ValueError("Second-room native FINISH/B restart sequence absent")
    if freeze_bytes[490] != freeze_bytes[515]:
        raise ValueError("Guest gameplay/viewport advanced after native final completion")
    if xs[515] - xs[565] < 180:
        raise ValueError("Real B edge did not return native stage-2 player to spawn")
    if abs(xs[565] - xs[590]) > 6:
        raise ValueError("Restarted stage-2 player drifted without input")
    if hashes[565] == hashes[515]:
        raise ValueError("Post-B stage-2 game framebuffer did not change")

    return {
        "guest_frame_numbers": list(FRAMES),
        "guest_hid_edges": [list(item) for item in HID_EVENTS],
        "stage_identifiers": [stages[f] for f in FRAMES],
        "real_first_room_clear": True,
        "native_jump_visible": True,
        "terminal_finish_frames": [f for f in FRAMES if finish[f]],
        "final_two_guest_frames_byte_identical": True,
        "native_B_restart_confirmed": True,
        "last_stage_remained_stage_two": True,
        "original_ios_gameplay_fidelity_verified": False,
        "png_sha256": {str(f): hashes[f] for f in FRAMES},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.directory), sort_keys=True, indent=2))
    print("PASS: genuine guest FINISH, stopped session, real B restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
