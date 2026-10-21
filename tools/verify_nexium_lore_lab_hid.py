"""Require genuine pinned NeXium kernel NPAD receipts for the lore lab.

Runner-side HEMAN_LORE_HID messages prove only scheduled file writes.
Actual kernel [hid-publish] events confirm that NPAD shared memory was
updated. Each distinct pressed/release state is mandatory, even L/R/Y/X.
Synthetic test logs are NOT guest/runtime evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from instrument_nexium_lore_lab import HID_EVENTS
from verify_nexium_hid_publication import BUTTON_BITS, read_publications

LAB_BITS = {**BUTTON_BITS, "L": 1 << 6, "R": 1 << 7}


def expected_masks() -> tuple[int, ...]:
    values = []
    for frame, packet in HID_EVENTS:
        if frame < 1 or not packet.startswith("buttons="):
            raise ValueError("Invalid source-authored guest HID schedule")
        mask = 0
        for name in filter(None, packet[8:].split(",")):
            if name not in LAB_BITS:
                raise ValueError(f"Unknown pinned guest HID button {name}")
            mask |= LAB_BITS[name]
        values.append(mask)
    return tuple(values)


def verify(text: str) -> dict:
    entries = read_publications(text)
    if not entries:
        raise ValueError("No real pinned kernel HID publication records")
    compressed = []
    for entry in entries:
        if not compressed or compressed[-1] != entry["buttons"]:
            compressed.append(entry["buttons"])
    if compressed and compressed[0] == 0:
        compressed.pop(0)
    expected = list(expected_masks())
    if compressed != expected:
        raise ValueError(
            "Pinned NeXium missed or added real NPAD button transitions: "
            f"published={compressed} expected={expected}"
        )
    return {
        "real_pinned_kernel_npad_edges_verified": True,
        "exclusive_controller_injection_verified": True,
        "kernel_shared_memory_samples": len(entries),
        "verified_guest_button_edges": len(expected),
        "observed_unique_button_kinds": sorted({
            name for _, packet in HID_EVENTS for name in packet[8:].split(",")
            if name
        }),
        "real_guest_pngs_verified_here": False,
        "original_ios_gameplay_fidelity_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_stdout", type=Path)
    args = parser.parse_args()
    result = verify(args.kernel_stdout.read_text(errors="replace"))
    print(json.dumps(result, sort_keys=True, indent=2))
    print("PASS: pinned kernel published every lore-lab real NPAD edge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
