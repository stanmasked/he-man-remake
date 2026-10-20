"""Fail-closed optical proof of experimental three-room real NeXium gameplay.

This accepts only genuine pinned guest frame_rx PNG/HID evidence, never
mock screenshots, synthetic success flags, edited assets or old-run files.
The existing source C99 logic must earn all HM_EXIT completions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from instrument_nexium_three_room import FRAMES, HID_EVENTS

WHITE = (191, 230, 241)
FACE = (103, 73, 53)
GOLD = (109, 200, 225)
CLEAR_BORDER = (80, 105, 33)
CLEAR_LETTER = (134, 212, 240)
RETRY_GREEN = (138, 213, 66)
CYAN_HEIGHT = (0, 255, 255)
PROGRESS_COLOR = (42, 248, 178)  # world-x 0..900 source-only third-room HUD

DIGITS = {
    1: "010110010010111",
    2: "111001111100111",
    3: "111001111001111",
}
EXPECTED_STAGES = (
    1, 2, 2, 2, 2, 2, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3,
)
EXPECTED_CLEAR = frozenset((75, 465, 505, 1045, 1080, 1120))
EXPECTED_FINISH = frozenset((1045, 1080, 1120))


def _digit(rgb) -> int:
    if rgb.getpixel((393, 4)) != GOLD or rgb.getpixel((398, 8)) != FACE:
        raise ValueError("Missing genuine stage badge border/face")
    bits = []
    for row in range(5):
        for col in range(3):
            pixel = rgb.getpixel((405 + col * 4, 10 + row * 4))
            if pixel not in (WHITE, FACE):
                raise ValueError("Unrecognized native stage HUD color")
            bits.append("1" if pixel == WHITE else "0")
    glyph = "".join(bits)
    for stage, expected in DIGITS.items():
        if glyph == expected:
            return stage
    raise ValueError("Invalid or truncated stage 1/2/3 glyph")


def _world_y(rgb) -> int:
    cells = [y for y in range(80, 340)
             if rgb.getpixel((476, y)) == CYAN_HEIGHT]
    if len(cells) != 9 or cells[-1] - cells[0] != 8:
        raise ValueError("Missing unique real guest world-Y HUD ruler")
    return cells[0]



def _progress_world_x(rgb, stage: int) -> int | None:
    """Read stage-3 *real source player.x* without legacy x210 clamping.

    The opt-in NRO draws a 4x10 uniquely colored cursor; the third room
    marker moves with native physics and cannot be set by the verifier.
    Never treat a host-generated sample as a guest attestation.
    """
    xs = []
    for x in range(70, 530):
        for y in range(330, 340):
            if rgb.getpixel((x, y)) == PROGRESS_COLOR:
                xs.append(x)
    if stage != 3:
        if xs:
            raise ValueError("Third-room progress HUD leaked into stage 1/2")
        return None
    if len(xs) != 40:
        raise ValueError("Missing real source world-X third-room HUD cursor")
    unique = sorted(set(xs))
    if len(unique) != 4 or unique[-1] - unique[0] != 3:
        raise ValueError("Broken third-room world-X cursor geometry")
    return 2 * (unique[0] - 70)


def _overlay(rgb) -> bool:
    fields = (
        rgb.getpixel((208, 120)) == GOLD,
        rgb.getpixel((258, 155)) == WHITE,
        rgb.getpixel((254, 201)) == RETRY_GREEN,
        rgb.getpixel((311, 210)) == RETRY_GREEN,
        rgb.getpixel((315, 213)) == WHITE,
        rgb.getpixel((322, 218)) == WHITE,
    )
    if len(set(fields)) != 1:
        raise ValueError("Partial FINISH/B overlay is not a real completion")
    return fields[0]


def verify(folder: Path) -> dict:
    from PIL import Image
    from verify_nexium_guest_pngs import describe

    lines = (folder / "raster-runner.log").read_text().splitlines()
    expected_hid = [
        f"HEMAN_THREE_HID frame={frame} {action}"
        for frame, action in HID_EVENTS
    ]
    observed_hid = [line for line in lines
                    if line.startswith("HEMAN_THREE_HID frame=")]
    if observed_hid != expected_hid:
        raise ValueError("Missing, duplicated or extra real guest HID transcript")
    observed_png = [line for line in lines
                    if line.startswith("HEMAN_GUEST_FRAME_PNG frame=")]
    expected_headers = [
        f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        for frame in FRAMES
    ]
    if len(observed_png) != len(FRAMES) or any(
            not line.startswith(prefix)
            for line, prefix in zip(observed_png, expected_headers)):
        raise ValueError("Missing/duplicated/unexpected guest PNG attestation")
    if "Production runner complete" not in "\n".join(lines):
        raise ValueError("Pinned real NeXium production runner never completed")
    for frame, action in HID_EVENTS:
        prefix = f"HEMAN_THREE_HID frame={frame} "
        matches = [line for line in lines if line.startswith(prefix)]
        if matches != [prefix + action]:
            raise ValueError(f"Missing, repeated, or wrong guest HID at {frame}")
    values: dict[int, dict] = {}
    frozen = {}
    for frame in FRAMES:
        start = f"HEMAN_GUEST_FRAME_PNG frame={frame} dimensions=640x360 path="
        rows = [line for line in lines
                if line.startswith(f"HEMAN_GUEST_FRAME_PNG frame={frame} ")]
        if len(rows) != 1 or not rows[0].startswith(start):
            raise ValueError(f"Missing or duplicated 640x360 guest attestation {frame}")
        png = folder / f"raster-frame-{frame:04}.png"
        if not png.is_file():
            raise FileNotFoundError(f"Missing authentic NeXium PNG: {png}")
        origin = Path(rows[0][len(start):])
        if not origin.is_absolute() or origin.resolve() != png.resolve():
            raise ValueError(f"Cross-session guest PNG path at {frame}")
        with Image.open(png) as opened:
            if opened.format != "PNG":
                raise ValueError(f"Guest {frame} is not PNG")
            rgb = opened.convert("RGB")
        if rgb.size != (640, 360):
            raise ValueError(f"Wrong NeXium framebuffer size at {frame}")
        count, colors, world_x = describe(rgb)
        if count != 192 or colors < 8:
            raise ValueError(f"Missing source synthetic world marker at {frame}")
        clear = (
            rgb.getpixel((547, 47)) == CLEAR_BORDER,
            rgb.getpixel((553, 53)) == CLEAR_LETTER,
        )
        if len(set(clear)) != 1:
            raise ValueError(f"Incomplete native CLEAR HUD at {frame}")
        bytes_rgb = rgb.tobytes()
        if frame in (1080, 1120):
            frozen[frame] = bytes_rgb
        stage = _digit(rgb)
        values[frame] = {
            "stage": stage,
            "full_world_x": _progress_world_x(rgb, stage),
            "clear": clear[0],
            "finish": _overlay(rgb),
            "world_x_marker": round(world_x, 2),
            "world_y_marker": _world_y(rgb),
            "respawn": rgb.getpixel((522, 62)) == RETRY_GREEN,
            "sha256": hashlib.sha256(bytes_rgb).hexdigest(),
        }

    if tuple(values[f]["stage"] for f in FRAMES) != EXPECTED_STAGES:
        raise ValueError("Guest three-stage sequence 1→2→3 was not observed")
    if {f for f in FRAMES if values[f]["clear"]} != EXPECTED_CLEAR:
        raise ValueError("Missing earned CLEAR or premature CLEAR at stage 1/2/3")
    if {f for f in FRAMES if values[f]["finish"]} != EXPECTED_FINISH:
        raise ValueError("FINISH must appear ONLY at real third exit, then clear on B")
    if values[75]["world_x_marker"] - values[105]["world_x_marker"] < 90:
        raise ValueError("Native first-to-second room spawn reset missing")
    if values[505]["world_x_marker"] - values[535]["world_x_marker"] < 170:
        raise ValueError("Fresh A did not reset genuine stage-3 spawn")
    if values[650]["world_x_marker"] - values[535]["world_x_marker"] < 150:
        raise ValueError("Real D-pad movement not observed in third room")
    # World-X marker intentionally clamps at x210. It cannot alone
    # attest traversal of the x678 hazard or x842 goal. Source-native
    # respawn + earned HM_EXIT / FINISH must supply those receipts.
    if values[820]["respawn"] or not values[850]["respawn"]:
        raise ValueError("Stage-3 native hazard/respawn signal missing")
    if not values[930]["respawn"] or values[1170]["respawn"]:
        raise ValueError("Native hazard state did not persist or reset after B")
    if values[970]["world_y_marker"] > values[945]["world_y_marker"] - 25:
        raise ValueError("Real stage-3 A jump did not move the world-Y marker")
    # Critical optical evidence beyond the old x210-saturated magenta HUD:
    # actual world-X advances through checkpoint x434, hazard x678, exit x842.
    # Ranges tolerate a few guest-vs-host frame scheduling differences.
    bounds = {
        535: (45, 100), 650: (265, 325), 820: (600, 665),
        850: (435, 495), 930: (585, 652), 945: (615, 679),
        970: (670, 744), 1045: (814, 868),
        1080: (814, 868), 1120: (814, 868),
        1170: (45, 85), 1190: (45, 85),
    }
    for frame, (lo, hi) in bounds.items():
        x = values[frame]["full_world_x"]
        if x is None or not lo <= x <= hi:
            raise ValueError(f"Native source world-X guest cursor wrong at {frame}: {x}")
    if values[820]["full_world_x"] - values[850]["full_world_x"] < 100:
        raise ValueError("Native third-room hazard did not reset real world-X")
    if values[1045]["full_world_x"] - values[970]["full_world_x"] < 70:
        raise ValueError("No native traversal from jump through third-room exit")
    if frozen[1080] != frozen[1120]:
        raise ValueError("Game advanced after source-native third-stage FINISH")
    if abs(values[1190]["world_x_marker"] - values[1170]["world_x_marker"]) > 6:
        raise ValueError("Stage 3 drifted after native B restart")
    if values[1170]["world_x_marker"] > 150:
        raise ValueError("Stage-3 B failed to restore the real starting position")
    if values[1170]["sha256"] == values[1120]["sha256"]:
        raise ValueError("Final-stage native replay image never changed")

    return {
        "real_guest_frames": list(FRAMES),
        "real_guest_hid_events": [list(pair) for pair in HID_EVENTS],
        "stage_sequence": [values[f]["stage"] for f in FRAMES],
        "clear_samples": sorted(EXPECTED_CLEAR),
        "finish_samples": sorted(EXPECTED_FINISH),
        "genuine_stage3_hazard_respawn_seen": True,
        "genuine_stage3_jump_seen": True,
        "real_guest_unclamped_world_x": {
            str(f): values[f]["full_world_x"] for f in FRAMES
            if values[f]["stage"] == 3
        },
        "native_stage3_FINISH_frozen": True,
        "genuine_B_retry_stage3_seen": True,
        "original_ios_physics_fidelity_verified": False,
        "guest_frame_sha256": {str(f): values[f]["sha256"] for f in FRAMES},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
    print("PASS: authentic NeXium guest three-room CLEAR, FINISH and B replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
