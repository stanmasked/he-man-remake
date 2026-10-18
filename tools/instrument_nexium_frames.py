"""Add evidence-only PNG recording to pinned NeXium's debug_boot Rust runner.

Patches a TEMPORARY checked-out upstream Rust source file at CI build time.
The distribution/game .nro bytes are never changed.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def instrument(source: str) -> str:
    if "HEMAN_GUEST_FRAME_PNG" in source:
        raise ValueError("NeXium debug_boot has already been instrumented")
    additions = (
        ("            frames += 1;\n            if frames <= 3 {",
         "            frames += 1;\n"
         "            if matches!(frames, 30 | 120 | 300) {\n"
         "                heman_record_frame(&frame, frames, log)?;\n"
         "            }\n"
         "            if frames <= 3 {"),
        ("        frames += 1;\n        if frames <= 3 {",
         "        frames += 1;\n"
         "        if matches!(frames, 30 | 120 | 300) {\n"
         "            heman_record_frame(&frame, frames, log)?;\n"
         "        }\n"
         "        if frames <= 3 {"),
    )
    for before, after in additions:
        if source.count(before) != 1:
            raise ValueError("Pinned upstream NeXium debug_boot source changed")
        source = source.replace(before, after, 1)
    # Function is invoked with the inferred frame type at each call site:
    # this version is appended as a macro to avoid taking a dependency on
    # the emulator's internal frame struct name.
    before = (
        "                heman_record_frame(&frame, frames, log)?;",
        "            heman_record_frame(&frame, frames, log)?;",
    )
    for line in before:
        indent = line[:len(line)-len(line.lstrip())]
        frame_code = [
            'let dir = std::env::var("HEMAN_FRAME_CAPTURE_DIR")',
            '    .map_err(|_| "HEMAN_FRAME_CAPTURE_DIR must be set")?;',
            'std::fs::create_dir_all(&dir)?;',
            'let path = format!("{dir}/raster-frame-{frames:04}.png");',
            'if frame.pixels.len() != (frame.width as usize) * (frame.height as usize) * 4 {',
            '    return Err(format!("unexpected raw frame byte length: {}", frame.pixels.len()).into());',
            '}',
            'image::save_buffer(&path, &frame.pixels, frame.width, frame.height, image::ColorType::Rgba8)?;',
            'writeln!(log, "HEMAN_GUEST_FRAME_PNG frame={} dimensions={}x{} path={}",',
            '         frames, frame.width, frame.height, path)?;',
            'log.flush()?;',
        ]
        replacement = '\n'.join(indent + item for item in frame_code)
        if source.count(line) != 1:
            raise ValueError("frame capture call injection mismatch")
        source = source.replace(line, replacement, 1)
    if source.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("missing both nested runner frame loops")
    return source


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    args = p.parse_args()
    if not args.rust_source.is_file():
        p.error("Rust source file is missing")
    original = args.rust_source.read_text()
    modified = instrument(original)
    args.rust_source.write_text(modified)
    print(f"Instrumented pinned NeXium debug_boot in temporary checkout: {args.rust_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
