"""Instrument real pinned NeXium frame_rx for native exit CLEAR proof.

The independent, asset-free guest NRO is compiled with EXIT_PROBE=1;
no guest memory, game state or PNG pixels are altered by this tool.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_hid import instrument_input

FRAMES = (30, 60, 80, 120, 300)
INPUT_EVENTS = ((45, "buttons=DRIGHT"), (105, "buttons="))


def instrument(source: str) -> str:
    output = instrument_input(source)
    old = "if matches!(frames, 30 | 120 | 300) {"
    new = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(old) != 2:
        raise ValueError("Pinned NeXium frame_rx capture sites changed")
    output = output.replace(old, new)
    if output.count("HEMAN_HID_SCHEDULE frame=") != 2:
        raise ValueError("Both genuine D-pad input receiver sites required")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both genuine PNG capture sites required")
    return output


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rust_source", type=Path)
    args = ap.parse_args()
    if not args.rust_source.is_file():
        ap.error("Pinned upstream debug_boot Rust file missing")
    args.rust_source.write_text(instrument(args.rust_source.read_text()))
    print("Installed real NeXium D-pad → source-authored HM_EXIT PNG captures")


if __name__ == "__main__":
    raise SystemExit(main())
