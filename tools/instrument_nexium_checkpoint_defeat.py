"""Capture real checkpoint activation, contact defeat and auto respawn in NeXium.

Only instrument temporary pinned upstream Rust debug_boot; guest NRO receives
a real D-pad event and runs unchanged game physics/combat/reset logic.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as capture

FRAMES = (30, 80, 105, *range(116, 131), 145)
HID_EVENTS = ((45, "buttons=DRIGHT"), (66, "buttons="))


def instrument(source: str) -> str:
    output = capture(source)
    before = "if matches!(frames, 30 | 120 | 300) {"
    frame_match = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(before) != 2:
        raise ValueError("Pinned NeXium guest frame receive paths changed")
    output = output.replace(before, frame_match)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + frame_match
        if output.count(anchor) != 1:
            raise ValueError("Missing unique pinned frame insertion point")
        events = (
            "if matches!(frames, 45 | 66) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = if frames == 45 { "buttons=DRIGHT" } else { "buttons=" };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_CHECKPOINT_DEFEAT_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            "}",
        )
        rust = "\n".join(indent + item for item in events)
        output = output.replace(
            anchor, indent + "frames += 1;\n" + rust + "\n"
            + indent + frame_match, 1,
        )
    if output.count("HEMAN_CHECKPOINT_DEFEAT_HID frame=") != 2:
        raise ValueError("Both real HID receiver paths are mandatory")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both real framebuffer capture paths are mandatory")
    return output


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    args = p.parse_args()
    path = args.rust_source
    path.write_text(instrument(path.read_text()))
    print("Instrumented native contact-death checkpoint guest/HID evidence")


if __name__ == "__main__":
    raise SystemExit(main())
