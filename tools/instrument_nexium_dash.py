"""Inject a true ZR+Right dash after genuine CLEAR->A stage transition.

Only instrument temporary pinned NeXium guest frame receiver; never modify
NRO/RAM, fabricate screenshots, or submit commercial game resources.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as instrument_frames

FRAMES = (75, 105, 115, 125, 140, 180, 240)
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (78, "buttons="),
    (90, "buttons=A"),
    (95, "buttons="),
    (110, "buttons=DRIGHT"),
    (120, "buttons=DRIGHT,ZR"),
    (128, "buttons=DRIGHT"),
    (165, "buttons="),
)


def instrument(source: str) -> str:
    output = instrument_frames(source)
    before = "if matches!(frames, 30 | 120 | 300) {"
    after = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(before) != 2:
        raise ValueError("NeXium upstream frame receivers changed")
    output = output.replace(before, after)
    schedule = " | ".join(str(frame) for frame, _ in HID_EVENTS)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + after
        if output.count(anchor) != 1:
            raise ValueError("Required distinct upstream guest frame receiver missing")
        ins = (
            f"if matches!(frames, {schedule}) {{",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            "    let action = match frames {",
            '        45 | 110 | 128 => "buttons=DRIGHT",',
            '        120 => "buttons=DRIGHT,ZR",',
            '        90 => "buttons=A",',
            '        78 | 95 | 165 => "buttons=",',
            "        _ => unreachable!(),",
            "    };",
            "    std::fs::write(&path, action)?;",
            '    writeln!(log, "HEMAN_DASH_HID frame={} {}", frames, action)?;',
            "    log.flush()?;",
            "}",
        )
        insertion = "\n".join(indent + x for x in ins)
        output = output.replace(anchor, indent + "frames += 1;\n" +
                                insertion + "\n" + indent + after, 1)
    if output.count("HEMAN_DASH_HID frame=") != 2:
        raise ValueError("Both NeXium guest HID capture loops are required")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both genuine guest PNG capture loops are required")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    args.rust_source.write_text(instrument(args.rust_source.read_text()))
    print("Installed genuine guest room-2 ZR dash and PNG hooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
