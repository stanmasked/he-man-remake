"""Fail-closed equality of the real NeXium HID script and both C99 preflights.

This is a static contract, not actual guest input or framebuffer proof.
Manual copies of controller timing in two C programs have drifted before;
the source-authoritative Python HID_EVENTS must match every C switch case,
not just a subset. Also validates all 18 optical capture frame numbers.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from instrument_nexium_three_room import FRAMES, HID_EVENTS
from verify_nexium_three_room_pngs import EXPECTED_STAGES

ROOT = Path(__file__).resolve().parents[1]
HOST_SOURCES = (
    "native/tests/test_three_room_hid_timing.c",
    "native/tests/test_three_room_optical_oracle.c",
)

_C_CASES = re.compile(r"((?:\s*case\s+\d+u\s*:\s*)+)return\s*([^;]+);")
_C_NUMBER = re.compile(r"case\s+(\d+)u\s*:")
_C_SAMPLE = re.compile(r"static const unsigned sample_frames\[\]\s*=\s*\{([^}]+)\};", re.S)


def c_hid_events(source: str) -> tuple[tuple[int, str], ...]:
    """Read exactly the C switch that computes held buttons per game frame.

    Reject unknown expressions or unexpected control flow rather than
    silently ignoring an event that could change the real game route.
    """
    block = re.search(
        r"static unsigned buttons_at\(unsigned f, unsigned old\)\s*\{"
        r"(?P<body>.*?)\n\}", source, re.S,
    )
    if not block:
        raise ValueError("C99 input schedule function absent")
    body = block.group("body")
    switch = re.search(r"switch\(f\)\s*\{(.*?)default\s*:\s*return\s+old\s*;", body, re.S)
    if not switch:
        raise ValueError("Native schedule is not a switch with old-state default")
    arm_body = switch.group(1)
    arms = list(_C_CASES.finditer(arm_body))
    if not arms:
        raise ValueError("No native controller edges")
    residue = _C_CASES.sub("", arm_body).strip()
    if residue:
        raise ValueError("Unexpected or unrecognized C99 HID schedule code")

    events: dict[int, str] = {}
    for arm in arms:
        frames = [int(n) for n in _C_NUMBER.findall(arm.group(1))]
        expression = re.sub(r"\s+", "", arm.group(2))
        if not frames or len(set(frames)) != len(frames):
            raise ValueError("Duplicate C99 frame within a case group")
        for frame in frames:
            if frame in events:
                raise ValueError(f"Duplicate C99 HID edge at frame {frame}")
            if expression == "R":
                action = "buttons=DRIGHT"
            elif expression == "0u":
                action = "buttons="
            elif expression == "R|A":
                action = "buttons=DRIGHT,A"
            elif expression == "f==1140u?B:A":
                action = "buttons=B" if frame == 1140 else "buttons=A"
            else:
                raise ValueError(
                    f"Unsupported C99 button mapping at frame {frame}: {expression}"
                )
            events[frame] = action
    return tuple(sorted(events.items()))


def c_sample_frames(source: str) -> tuple[int, ...]:
    matches = _C_SAMPLE.findall(source)
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous C99 framebuffer sampling table")
    return tuple(int(n) for n in re.findall(r"(\d+)u", matches[0]))


def verify(
    root: Path = ROOT,
    hid_events: tuple[tuple[int, str], ...] = HID_EVENTS,
    sample_frames: tuple[int, ...] = FRAMES,
) -> dict:
    if not sample_frames or tuple(sorted(set(sample_frames))) != sample_frames:
        raise ValueError("Guest sample frames must be strictly increasing and unique")
    if len(sample_frames) != len(EXPECTED_STAGES):
        raise ValueError("Guest stages and sample frames disagree")
    if not hid_events or tuple(sorted(set(hid_events))) != hid_events:
        raise ValueError("Python HID edges must be strictly ordered and unique")
    if len({f for f, _ in hid_events}) != len(hid_events):
        raise ValueError("Python HID frame numbers are repeated")
    if any(f <= 0 or f > sample_frames[-1] for f, _ in hid_events):
        raise ValueError("Python HID edge outside source capture window")
    if any(not action.startswith("buttons=") for _, action in hid_events):
        raise ValueError("Unsupported native guest controller packet")
    if (90, "buttons=A") not in hid_events or (
        510, "buttons=A"
    ) not in hid_events or (1140, "buttons=B") not in hid_events:
        raise ValueError("Mandatory genuine stage transitions/replay missing")
    if (470, "buttons=") not in hid_events:
        raise ValueError("Second-room post-CLEAR release edge changed")
    if (952, "buttons=DRIGHT,A") not in hid_events:
        raise ValueError("Native third-room hazard jump changed")

    expected = tuple(hid_events)
    for path in HOST_SOURCES:
        source = (root / path).read_text(encoding="utf-8")
        observed = c_hid_events(source)
        if observed != expected:
            added = [e for e in observed if e not in expected]
            missing = [e for e in expected if e not in observed]
            raise ValueError(
                f"HID mismatch in {path}: missing={missing} unexpected={added}"
            )
    oracle_source = (root / HOST_SOURCES[1]).read_text(encoding="utf-8")
    if c_sample_frames(oracle_source) != sample_frames:
        raise ValueError("Host RGB frame samples diverge from actual NeXium captures")

    workflow = (
        root / ".github/workflows/nexium-patched-three-room.yml"
    ).read_text(encoding="utf-8")
    for token in (
        "instrument_nexium_three_room.py",
        "verify_nexium_three_room_pngs.py",
        "HEMAN_FRAME_CAPTURE_DIR",
        "NEXIUM_HID_INJECT_EXCLUSIVE",
        "heman_three_room_probe.nro",
    ):
        if token not in workflow:
            raise ValueError(f"Actual NeXium workflow no longer uses {token}")

    return {
        "controller_edges": len(expected),
        "capture_frames": len(sample_frames),
        "native_preflight_sources_checked": list(HOST_SOURCES),
        "pixel_samples_match_guest_script": True,
        "real_nexium_guest_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(verify(args.root), sort_keys=True, indent=2))
    print("PASS: C99 preflights and NeXium injector have the same exact HID schedule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
