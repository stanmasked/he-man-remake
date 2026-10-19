"""Instrument two real X presses AFTER a genuine native defeat/respawn.

Patch only a temporary, pinned NeXium debug_boot Rust runner, never the NRO.
Capture raw guest frame_rx output; source gameplay is not modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as capture_frames

FRAMES = (62, 79, 115, 170)
HID_EVENTS = (
    (65, "buttons=X"),
    (74, "buttons="),
    (84, "buttons=X"),
    (93, "buttons="),
)


def instrument(source: str) -> str:
    result = capture_frames(source)
    original = "if matches!(frames, 30 | 120 | 300) {"
    replacement = "if matches!(frames, 62 | 79 | 115 | 170) {"
    if result.count(original) != 2:
        raise ValueError("Pinned upstream guest frame receivers changed")
    result = result.replace(original, replacement)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + replacement
        if result.count(anchor) != 1:
            raise ValueError("Missing unique pinned NeXium frame receiver")
        events = (
            "if matches!(frames, 65 | 74 | 84 | 93) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = if matches!(frames, 65 | 84) { "buttons=X" } else { "buttons=" };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_RESPAWN_SWORD_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            "}",
        )
        rust_code = "\n".join(indent + line for line in events)
        result = result.replace(
            anchor,
            indent + "frames += 1;\n" + rust_code + "\n" + indent + replacement,
            1,
        )
    if result.count("HEMAN_RESPAWN_SWORD_HID frame=") != 2:
        raise ValueError("Missing one or both true NeXium HID inject sites")
    if result.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Missing true source framebuffer receive sites")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    a = p.parse_args()
    pth = a.rust_source
    pth.write_text(instrument(pth.read_text()))
    print("Installed genuine post-respawn X-button actions and guest PNG captures")


if __name__ == "__main__":
    raise SystemExit(main())
