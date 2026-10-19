"""Capture native checkpoint activation and B-reset in real NeXium guest.

Instrument only a temporary pinned upstream debug_boot Rust checkout.
Guest NRO/gameplay/memory are unchanged; controller buttons use normal HID.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as frame_capture

FRAMES = (30, 95, 145, 195, 230)
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (78, "buttons="),
    (107, "buttons=B"),
    (117, "buttons="),
    (160, "buttons=DRIGHT"),
    (174, "buttons="),
)


def instrument(source: str) -> str:
    result = frame_capture(source)
    expected = "if matches!(frames, 30 | 120 | 300) {"
    replacement = "if matches!(frames, 30 | 95 | 145 | 195 | 230) {"
    if result.count(expected) != 2:
        raise ValueError("Pinned guest framebuffer receive paths changed")
    result = result.replace(expected, replacement)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + replacement
        if result.count(anchor) != 1:
            raise ValueError("Unique pinned NeXium frame receiver missing")
        events = (
            "if matches!(frames, 45 | 78 | 107 | 117 | 160 | 174) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = match frames {',
            '        45 | 160 => "buttons=DRIGHT",',
            '        107 => "buttons=B",',
            '        _ => "buttons=",',
            '    };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_CHECKPOINT_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            "}",
        )
        code = "\n".join(indent + line for line in events)
        result = result.replace(
            anchor, indent + "frames += 1;\n" + code + "\n"
            + indent + replacement, 1,
        )
    if result.count("HEMAN_CHECKPOINT_HID frame=") != 2:
        raise ValueError("Both pinned NeXium HID paths are mandatory")
    if result.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both pinned guest capture paths are mandatory")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    pth = args.rust_source
    pth.write_text(instrument(pth.read_text()))
    print("Installed checkpoint D-pad/B/D-pad HID schedule and real guest captures")


if __name__ == "__main__":
    raise SystemExit(main())
