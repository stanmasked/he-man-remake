"""Instrument real NeXium frame_rx and Minus/Right pause/resume HID edges.

Modifies only a temporary checkout of pinned upstream debug_boot.rs; neither
guest state nor ROM/NRO data nor captured PNG pixels are ever fabricated.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from instrument_nexium_frames import instrument as instrument_frames

FRAMES = (30, 70, 110, 135, 175, 220, 300)
# frame 85 enters pause, frame 90 releases Minus but requests Right while
# frozen, frame 145 resumes, frame 150 re-presses Right, 205 releases Right.
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (85, "buttons=MINUS"),
    (90, "buttons=DRIGHT"),
    (145, "buttons=MINUS"),
    (150, "buttons=DRIGHT"),
    (205, "buttons="),
)


def instrument(source: str) -> str:
    output = instrument_frames(source)
    original = "if matches!(frames, 30 | 120 | 300) {"
    capture = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(original) != 2:
        raise ValueError("Pinned NeXium frame_rx loops no longer match")
    output = output.replace(original, capture)
    schedule = " | ".join(str(f) for f, _ in HID_EVENTS)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + capture
        if output.count(anchor) != 1:
            raise ValueError("Expected exactly one of each pinned frame receiver")
        instructions = (
            f"if matches!(frames, {schedule}) {{",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            "    let action = match frames {",
            '        45 | 90 | 150 => "buttons=DRIGHT",',
            '        85 | 145 => "buttons=MINUS",',
            '        205 => "buttons=",',
            '        _ => unreachable!(),',
            "    };",
            "    std::fs::write(&path, action)?;",
            '    writeln!(log, "HEMAN_PAUSE_HID frame={} {}", frames, action)?;',
            "    log.flush()?;",
            "}",
        )
        snippet = "\n".join(indent + x for x in instructions)
        output = output.replace(
            anchor,
            indent + "frames += 1;\n" + snippet + "\n" + indent + capture,
            1,
        )
    if output.count("HEMAN_PAUSE_HID frame=") != 2:
        raise ValueError("Both real guest frame receivers must record HID")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both original guest PNG capture sites required")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    file = args.rust_source
    file.write_text(instrument(file.read_text()))
    print("Installed genuine Minus pause/resume and PNG capture hooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
