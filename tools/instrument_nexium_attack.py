"""Inject two real NeXium HID X-button presses into the pinned guest runner.

Only a temporary upstream Rust debug_boot checkout is instrumented. Actual
game logic, session state and normal production devkitPro NRO are unmodified.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as record_guest_frames


def instrument_attacks(source: str) -> str:
    source = record_guest_frames(source)
    old_frames = "if matches!(frames, 30 | 120 | 300) {"
    if source.count(old_frames) != 2:
        raise ValueError("Pinned upstream guest frame loops no longer match")
    source = source.replace(old_frames, "if matches!(frames, 30 | 65 | 120) {")
    for indent in ("            ", "        "):
        anchor = (indent + "frames += 1;\n"
                  + indent + "if matches!(frames, 30 | 65 | 120) {")
        if source.count(anchor) != 1:
            raise ValueError("Expected a unique pinned NeXium frame consumer")
        events = [
            "if matches!(frames, 45 | 58 | 85 | 98) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = if matches!(frames, 45 | 85) { "buttons=X" } else { "buttons=" };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_ATTACK_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            "}",
        ]
        code = "\n".join(indent + item for item in events)
        source = source.replace(
            anchor,
            indent + "frames += 1;\n" + code + "\n"
            + indent + "if matches!(frames, 30 | 65 | 120) {", 1,
        )
    if source.count("HEMAN_ATTACK_HID frame=") != 2:
        raise ValueError("Missing one or both guest receiver paths")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    path = args.rust_source
    updated = instrument_attacks(path.read_text())
    path.write_text(updated)
    print("Pinned NeXium frame receiver: two X presses and PNG snapshots installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
