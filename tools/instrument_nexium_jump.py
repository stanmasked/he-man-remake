"""Instrument real NeXium HID A-button press and capture guest jump frames."""
from __future__ import annotations
import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as instrument_frames

def instrument_jump(source: str) -> str:
    source = instrument_frames(source)
    original = "if matches!(frames, 30 | 120 | 300) {"
    if source.count(original) != 2:
        raise ValueError("Pinned upstream guest capture loops changed")
    source = source.replace(original, "if matches!(frames, 30 | 65 | 120) {")
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + "if matches!(frames, 30 | 65 | 120) {"
        if source.count(anchor) != 1:
            raise ValueError("Pinned upstream guest consumer frame counter changed")
        lines = [
            "if matches!(frames, 45 | 58) {",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let value = if frames == 45 { "buttons=A" } else { "buttons=" };',
            '    std::fs::write(&path, value)?;',
            '    writeln!(log, "HEMAN_JUMP_HID frame={} {}", frames, value)?;',
            '    log.flush()?;',
            "}",
        ]
        source = source.replace(anchor, indent + "frames += 1;\n"
                                + "\n".join(indent + line for line in lines)
                                + "\n" + indent
                                + "if matches!(frames, 30 | 65 | 120) {", 1)
    if source.count("HEMAN_JUMP_HID frame=") != 2:
        raise ValueError("Missing exactly two frame loop hooks")
    return source

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    args = p.parse_args()
    path = args.rust_source
    modified = instrument_jump(path.read_text())
    path.write_text(modified)
    print("Instrumented guest A-button jump and PNG frame capture")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
