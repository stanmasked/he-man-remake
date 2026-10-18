"""Instrument pinned NeXium debug_boot guest PNG capture and real HID injection.

Works only in a temporary pinned upstream checkout; neither the guest NRO
nor user-provided proprietary game data is patched.
"""
from __future__ import annotations
import argparse
from pathlib import Path

from instrument_nexium_frames import instrument as instrument_frames


def instrument_input(source: str) -> str:
    source = instrument_frames(source)
    if "HEMAN_HID_SCHEDULE" in source:
        raise ValueError("HID input already instrumented")
    # Both the primary production loop and its final-drain path may receive
    # the threshold frame number. Inject from the frame consumer exactly
    # once for each frame, without clocks, keyboard focus or sleeps.
    refs = (
        ("            frames += 1;\n            if matches!(frames, 30 | 120 | 300) {", "            "),
        ("        frames += 1;\n        if matches!(frames, 30 | 120 | 300) {", "        "),
    )
    for anchor, indent in refs:
        if source.count(anchor) != 1:
            raise ValueError("Pinned upstream frame loop changed")
        events = [
            "if matches!(frames, 45 | 105) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let text = if frames == 45 { "buttons=DRIGHT" } else { "buttons=" };',
            '    std::fs::write(&path, text)?;',
            '    writeln!(log, "HEMAN_HID_SCHEDULE frame={} {}", frames, text)?;',
            '    log.flush()?;',
            "}",
        ]
        # NeXium's original HID parser reads the file on a ~25ms cadence.
        injection = "\n".join(indent + line for line in events)
        source = source.replace(anchor,
            indent + "frames += 1;\n" + injection + "\n" +
            indent + "if matches!(frames, 30 | 120 | 300) {", 1)
    if source.count('HEMAN_HID_SCHEDULE frame=') != 2:
        raise ValueError("Missing injected event hooks")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rust_source", type=Path)
    args = parser.parse_args()
    original = args.rust_source.read_text()
    updated = instrument_input(original)
    args.rust_source.write_text(updated)
    print("Instrumented pinned NeXium guest frame capture and HID input schedule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
