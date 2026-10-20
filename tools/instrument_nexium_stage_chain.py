"""Inject true Right/A events into pinned NeXium and capture original guest PNGs.

Instrument only temporary emulator frame_rx code; never patch guest RAM,
rewrite screenshots or introduce original-game assets into public CI.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from instrument_nexium_frames import instrument as instrument_frames

FRAMES = (30, 75, 105, 140, 180, 240)
# Right reaches the actual C99 HM_EXIT; release, then A starts new room.
# A is released before moving in the newly initialized second room.
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (78, "buttons="),
    (90, "buttons=A"),
    (95, "buttons="),
    (110, "buttons=DRIGHT"),
    (165, "buttons="),
)


def instrument(source: str) -> str:
    output = instrument_frames(source)
    original = "if matches!(frames, 30 | 120 | 300) {"
    capture = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(original) != 2:
        raise ValueError("Pinned NeXium guest receiver loops changed")
    output = output.replace(original, capture)
    schedule = " | ".join(str(f) for f, _ in HID_EVENTS)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + capture
        if output.count(anchor) != 1:
            raise ValueError("Missing exactly one guest receiver anchor")
        ins = (
            f"if matches!(frames, {schedule}) {{",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            "    let action = match frames {",
            '        45 | 110 => "buttons=DRIGHT",',
            '        90 => "buttons=A",',
            '        78 | 95 | 165 => "buttons=",',
            '        _ => unreachable!(),',
            "    };",
            "    std::fs::write(&path, action)?;",
            '    writeln!(log, "HEMAN_CHAIN_HID frame={} {}", frames, action)?;',
            "    log.flush()?;",
            "}",
        )
        snippet = "\n".join(indent + x for x in ins)
        output = output.replace(
            anchor, indent + "frames += 1;\n" + snippet + "\n" + indent + capture,
            1,
        )
    if output.count("HEMAN_CHAIN_HID frame=") != 2:
        raise ValueError("Both genuine guest loops must capture stage input")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both genuine guest PNG captures must remain")
    return output


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    args = p.parse_args()
    path = args.rust_source
    path.write_text(instrument(path.read_text()))
    print("Installed native two-room HID + guest PNG hooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
