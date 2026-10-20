"""Experimental *real* NeXium guest HID/Png path for three authored rooms.

Only instruments the temporary pinned emulator's two frame_rx loops.
The AArch64 NRO, game state, geometry and resulting PNG bytes are unchanged.
An incorrectly timed route MUST FAIL until evidence supports new timings.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from instrument_nexium_frames import instrument as instrument_frames

FRAMES = (
    75, 105, 330, 365, 465, 505, 535, 650, 820, 850,
    930, 945, 970, 1045, 1080, 1120, 1170, 1190,
)
# First-room native exit 75 and transition A90; actual room-2 jump A350
# over the x570 hazard, earning room-2 CLEAR near frame465. Fresh A510
# enters room 3. Walk to real x678 hazard, checkpoint respawn, then A957
# is the hypothesized landing-safe jump leading to x842 native exit.
# B1140 is only issued after final FINISH has been sampled. These input
# frames are a HYPOTHESIS until NeXium records real guest PNG/HID results.
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (78, "buttons="),
    (90, "buttons=A"),
    (95, "buttons="),
    (110, "buttons=DRIGHT"),
    (350, "buttons=DRIGHT,A"),
    (353, "buttons=DRIGHT"),
    (500, "buttons="),
    (510, "buttons=A"),
    (515, "buttons="),
    (530, "buttons=DRIGHT"),
    (957, "buttons=DRIGHT,A"),
    (960, "buttons=DRIGHT"),
    (1080, "buttons="),
    (1140, "buttons=B"),
    (1143, "buttons="),
)


def instrument(source: str) -> str:
    output = instrument_frames(source)
    old = "if matches!(frames, 30 | 120 | 300) {"
    new = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(old) != 2:
        raise ValueError("Pinned emulator receiver signature changed")
    output = output.replace(old, new)
    schedule = " | ".join(str(f) for f, _ in HID_EVENTS)
    groups: dict[str, list[int]] = {}
    for frame, action in HID_EVENTS:
        groups.setdefault(action, []).append(frame)
    arms = [
        "        " + " | ".join(map(str, frames)) + ' => "' + action + '",'
        for action, frames in groups.items()
    ]
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + new
        if output.count(anchor) != 1:
            raise ValueError("Exactly one guest frame_rx loop is required")
        stmts = [
            f"if matches!(frames, {schedule}) {{",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            "    let action = match frames {",
            *arms,
            "        _ => unreachable!(),",
            "    };",
            "    std::fs::write(&path, action)?;",
            '    writeln!(log, "HEMAN_THREE_HID frame={} {}", frames, action)?;',
            "    log.flush()?;",
            "}",
        ]
        inserted = "\n".join(indent + line for line in stmts)
        output = output.replace(
            anchor, indent + "frames += 1;\n" + inserted + "\n" + indent + new, 1
        )
    if output.count("HEMAN_THREE_HID frame=") != 2:
        raise ValueError("Both guest paths must inject controller commands")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both guest paths must preserve source PNG capture")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    args.rust_source.write_text(instrument(args.rust_source.read_text()))
    print("Installed three-room guest HID and real PNG evidence hooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
