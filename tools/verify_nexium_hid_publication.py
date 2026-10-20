"""Fail closed unless pinned NeXium *kernel* published the intended HID edges.

A runner-side HEMAN_THREE_HID line only certifies that debug_boot wrote a
controller file. The pinned upstream nexium-kernel/src/hid_state.rs polls
that file no more often than 25 ms and logs real "[hid-publish]" samples
when NEXIUM_HID_TRACE=1. This check requires matching kernel samples,
including their Npad shared-memory button values and exclusive input.
Receiver frames and kernel HID sampling are not the same clock.

Only authentic raster-stdout.log from the real NeXium CI job qualifies.
Unit tests using manufactured logs exercise the reader; never treat them
as execution evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from instrument_nexium_three_room import HID_EVENTS

BUTTON_BITS = {
    "A": 1 << 0,
    "B": 1 << 1,
    "X": 1 << 2,
    "Y": 1 << 3,
    "ZL": 1 << 8,
    "ZR": 1 << 9,
    "DLEFT": 1 << 12,
    "DUP": 1 << 13,
    "DRIGHT": 1 << 14,
    "DDOWN": 1 << 15,
}
ANSI = re.compile(r"\x1b\[[0-9;]*m")
TRACE = re.compile(
    r"\[hid-publish\]\s+sample=(?P<sample>\d+)\s+"
    r"entry=(?P<entry>\d+)\s+requested=(?P<requested>0x[0-9a-fA-F]+)\s+"
    r"injected=(?P<injected>None|Some\(ControllerInput\s*\{.*?\}\))\s+"
    r"npad=\[(?P<npad>[^\]]+)\].*?"
    r"exclusive=(?P<exclusive>true|false)\s+"
    r"mapped=(?P<mapped>0x[0-9a-fA-F]+)"
)
BUTTON = re.compile(r"\bbuttons:\s*(\d+)\b")


def expected_masks() -> tuple[int, ...]:
    masks = []
    for frame, packet in HID_EVENTS:
        if frame < 1 or not packet.startswith("buttons="):
            raise ValueError("Malformed source NeXium HID event")
        mask = 0
        for button in filter(None, packet[len("buttons="):].split(",")):
            if button not in BUTTON_BITS:
                raise ValueError(f"Unrecognized HID button: {button}")
            mask |= BUTTON_BITS[button]
        masks.append(mask)
    return tuple(masks)


def read_publications(log: str) -> list[dict]:
    records = []
    last_sample = None
    for line in ANSI.sub("", log).splitlines():
        if "[hid-publish]" not in line:
            continue
        found = TRACE.search(line)
        if not found:
            raise ValueError("Malformed pinned NeXium kernel HID publication")
        groups = found.groupdict()
        if groups["exclusive"] != "true":
            raise ValueError("Kernel HID was not exclusive to the test")
        sample = int(groups["sample"])
        if last_sample is not None and sample <= last_sample:
            raise ValueError("Guest HID sampling number did not increase")
        last_sample = sample
        mapped = int(groups["mapped"], 16) != 0
        injected = groups["injected"]
        matched = BUTTON.search(injected)
        if injected != "None" and not matched:
            raise ValueError("Unexpected injected controller structure")
        mask = int(matched.group(1)) if matched else 0
        # Rust's {:x?} formatter prints array cells in hexadecimal.
        try:
            layouts = tuple(int(token.strip(), 16)
                            for token in groups["npad"].split(","))
        except ValueError as e:
            raise ValueError("Malformed shared-memory NPAD layout") from e
        if len(layouts) != 7:
            raise ValueError("Pinned NeXium must report all seven NPAD layouts")
        if not mapped:
            # Pinned kernel can publish an initial neutral state before
            # the guest has mapped NPAD shared memory. It proves nothing.
            # Never accept an un-mapped button or mid-run unmapping.
            if mask != 0 or records or any(layouts):
                raise ValueError("Kernel HID was not mapped into shared memory")
            continue
        if mask != 0 and mask not in layouts:
            raise ValueError(
                f"Injected HID 0x{mask:x} never reached a real NPAD layout"
            )
        if mask == 0 and any(layouts):
            raise ValueError("NPAD buttons remained pressed after release")
        records.append({
            "sample": sample, "buttons": mask,
            "mapped": mapped,
        })
    return records


def verify(log: str) -> dict:
    publications = read_publications(log)
    if not publications:
        raise ValueError("No authentic NeXium kernel [hid-publish] events")
    compressed = []
    for record in publications:
        if not compressed or compressed[-1] != record["buttons"]:
            compressed.append(record["buttons"])
    # Before the first scripted edge the kernel can publish its neutral
    # initial state. No other unscheduled edges are allowed: missing a
    # 3-frame A/B press in the real 25ms HID poll must FAIL, not pass.
    if compressed and compressed[0] == 0:
        compressed.pop(0)
    expected = list(expected_masks())
    if compressed != expected:
        raise ValueError(
            f"NeXium did not consume the exact HID state transitions: "
            f"published={compressed} expected={expected}"
        )
    pressed = [m for m in expected if m != 0]
    return {
        "kernel_hid_publication_trace_valid": True,
        "exclusive_input_confirmed": True,
        "npad_shared_memory_confirmed": True,
        "kernel_samples_observed": len(publications),
        "real_kernel_button_transitions": len(expected),
        "distinct_pressed_edges": len(pressed),
        "native_guest_frame_rx_png_proven_here": False,
        "original_ios_fidelity_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raster_stdout", type=Path)
    args = parser.parse_args()
    result = verify(args.raster_stdout.read_text(errors="replace"))
    print(json.dumps(result, sort_keys=True, indent=2))
    print("PASS: pinned NeXium kernel actually published every real guest HID "
          "edge into NPAD shared memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
