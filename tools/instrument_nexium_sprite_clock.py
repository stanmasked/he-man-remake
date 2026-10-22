"""Capture chosen guest frames from a temporary pinned NeXium runner checkout."""
from __future__ import annotations
import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as instrument_frames

FRAME_SET = "matches!(frames, 6 | 12 | 18 | 30 | 36 | 120 | 300)"

def instrument(source: str) -> str:
    source = instrument_frames(source)
    original = "matches!(frames, 30 | 120 | 300)"
    if source.count(original) != 2:
        raise ValueError("Expected both pinned NeXium frame loops to be instrumented")
    source = source.replace(original, FRAME_SET)
    if source.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Missing guest frame capture points")
    return source

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    if not args.rust_source.is_file():
        parser.error("Rust source file is missing")
    original = args.rust_source.read_text()
    args.rust_source.write_text(instrument(original))
    print("Instrumented pinned NeXium runner for synthetic sprite-clock frames")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
