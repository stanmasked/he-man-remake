"""Use real NeXium D-pad then X presses to defeat enemy after checkpoint death.

Only patch the pinned temporary upstream Rust debug_boot guest receivers.
The test-only devkitPro NRO runs unchanged C99 checkpoint/combat logic.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as capture

FRAMES = (30, 80, 105, *range(116, 131), 140, 160, 185)
# Keep both X presses strictly AFTER the dense 116..130 death/recovery
# evidence: an early attack would make the truthful enemy-HP=2 invariant
# through frame 130 contradict the very action being tested.
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (66, "buttons="),
    (133, "buttons=X"),
    (140, "buttons="),
    (153, "buttons=X"),
    (160, "buttons="),
)


def instrument(source: str) -> str:
    output = capture(source)
    original = "if matches!(frames, 30 | 120 | 300) {"
    replacement = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(original) != 2:
        raise ValueError("Pinned upstream guest receiver capture sites changed")
    output = output.replace(original, replacement)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + replacement
        if output.count(anchor) != 1:
            raise ValueError("Expected unique pinned NeXium frame receiver")
        events = (
            "if matches!(frames, 45 | 66 | 133 | 140 | 153 | 160) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = match frames {',
            '        45 => "buttons=DRIGHT",',
            '        133 | 153 => "buttons=X",',
            '        _ => "buttons=",',
            '    };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_CHECKPOINT_SWORD_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            "}",
        )
        code = "\n".join(indent + line for line in events)
        output = output.replace(
            anchor, indent + "frames += 1;\n" + code + "\n"
            + indent + replacement, 1,
        )
    if output.count("HEMAN_CHECKPOINT_SWORD_HID frame=") != 2:
        raise ValueError("Both pinned guest HID sites required")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both real guest frame capture sites required")
    return output


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    a = p.parse_args()
    path = a.rust_source
    path.write_text(instrument(path.read_text()))
    print("NeXium guest checkpoint-death then real X sword script installed")


if __name__ == "__main__":
    raise SystemExit(main())
