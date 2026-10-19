"""Real NeXium post-victory B reset and two fresh X attacks, guest-only.

Uses the unchanged Stage 052 guest probe and its original real controller
script. Instruments both pinned Rust frame_rx receivers, not emulator memory.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from instrument_nexium_checkpoint_sword import (
    FRAMES as BASE_FRAMES,
    HID_EVENTS as BASE_HID_EVENTS,
    instrument as base_instrument,
)

RETRY_FRAMES = (*range(190, 212), 220, 242, 270)
FRAMES = (*BASE_FRAMES, *RETRY_FRAMES)
# The second X arrives before the next 30-frame contact hit after B.
# X frames 205/221 are 16 apart (>15 native sword cooldown), and both
# follow the real B release at 201; no guest state is overridden.
RETRY_EVENTS = (
    (194, "buttons=B"),
    (201, "buttons="),
    (205, "buttons=X"),
    (212, "buttons="),
    (221, "buttons=X"),
    (228, "buttons="),
)
HID_EVENTS = (*BASE_HID_EVENTS, *RETRY_EVENTS)


def instrument(source: str) -> str:
    output = base_instrument(source)
    original = "if matches!(frames, " + " | ".join(map(str, BASE_FRAMES)) + ") {"
    replacement = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(original) != 2:
        raise ValueError("Pinned Stage 052 guest capture sites changed")
    output = output.replace(original, replacement)

    for indent in ("            ", "        "):
        # Anchor at a line boundary: eight spaces must not falsely match
        # a suffix of the twelve-space guest receiver branch.
        anchor = "\n" + indent + replacement
        if output.count(anchor) != 1:
            raise ValueError("Expected one pinned guest receiver per branch")
        code = (
            "if matches!(frames, 194 | 201 | 205 | 212 | 221 | 228) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            "    let action = match frames {",
            '        194 => "buttons=B",',
            '        205 | 221 => "buttons=X",',
            '        _ => "buttons=",',
            "    };",
            "    std::fs::write(&path, action)?;",
            '    writeln!(log, "HEMAN_POSTVICTORY_HID frame={} {}", frames, action)?;',
            "    log.flush()?;",
            "}",
        )
        patch = "\n".join(indent + line for line in code)
        output = output.replace(anchor, "\n" + patch + anchor, 1)

    if output.count("HEMAN_POSTVICTORY_HID frame=") != 2:
        raise ValueError("Both pinned guest receivers must inject B and X")
    if output.count("HEMAN_CHECKPOINT_SWORD_HID frame=") != 2:
        raise ValueError("Existing genuine Stage 052 X attacks were lost")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Guest PNG capture patch is missing")
    return output


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    args = p.parse_args()
    if not args.rust_source.is_file():
        p.error("Pinned upstream Rust source file is missing")
    args.rust_source.write_text(instrument(args.rust_source.read_text()))
    print("NeXium B-after-victory and two new X presses instrumented")


if __name__ == "__main__":
    raise SystemExit(main())
