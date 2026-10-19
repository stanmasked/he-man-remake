"""Capture exact native contact-damage milestones in NeXium guest frames.

Nothing is injected into guest input or game memory. A very nearby
synthetic enemy deals contact damage through the real C99 combat loop.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as instrument_guest_frames

TIMELINE = (10, 25, 40, 61, 62)


def instrument(source: str) -> str:
    result = instrument_guest_frames(source)
    original = "matches!(frames, 30 | 120 | 300)"
    replacement = "matches!(frames, 10 | 25 | 40 | 61 | 62)"
    if result.count(original) != 2:
        raise ValueError("Pinned NeXium frame receive layout unexpected")
    result = result.replace(original, replacement)
    if result.count(replacement) != 2:
        raise ValueError("Missing one of two guest frame receive paths")
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source",type=Path)
    args=parser.parse_args()
    path=args.rust_source
    modified=instrument(path.read_text())
    path.write_text(modified)
    print("Patched temporary NeXium debug_boot to capture damage/respawn frames")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
