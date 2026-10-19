"""Capture real NeXium player movement after a native defeat and respawn.

Only modify temporary pinned upstream Rust debug_boot runner at CI time.
Use real HID injection and actual guest PNG pixels, never memory edits.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as instrument_frames

FRAMES = (62, 90, 160, 220)
RIGHT_PRESS_FRAME = 80
RIGHT_RELEASE_FRAME = 120


def instrument(source: str) -> str:
    output = instrument_frames(source)
    old = "if matches!(frames, 30 | 120 | 300) {"
    new = "if matches!(frames, 62 | 90 | 160 | 220) {"
    if output.count(old) != 2:
        raise ValueError("Pinned upstream frame capture paths changed")
    output = output.replace(old, new)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + new
        if output.count(anchor) != 1:
            raise ValueError("Pinned frame receiver insertion point missing")
        events = (
            "if matches!(frames, 80 | 120) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = if frames == 80 { "buttons=DRIGHT" } else { "buttons=" };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_RESPAWN_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            "}",
        )
        code = "\n".join(indent + entry for entry in events)
        output = output.replace(
            anchor,
            indent + "frames += 1;\n" + code + "\n" + indent + new,
            1,
        )
    if output.count("HEMAN_RESPAWN_HID frame=") != 2:
        raise ValueError("Both pinned guest receiver paths are required")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both genuine guest capture paths are required")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    path = args.rust_source
    updated = instrument(path.read_text())
    path.write_text(updated)
    print("Instrumented NeXium native respawn plus real D-pad Right movement")


if __name__ == "__main__":
    main()
