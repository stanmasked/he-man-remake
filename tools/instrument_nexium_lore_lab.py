"""Stage112: evidence-only pinned NeXium runner HID and framebuffer taps.

The genuine AArch64 NRO is NOT patched. The TEMPORARY emulator debug_boot
Rust source is modified in CI, with fail-closed matching of both paths.
Published HID kernel samples, not scheduled writes, certify NPAD delivery.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from instrument_nexium_frames import instrument as instrument_frames

# Guest receiver frames, not host-clock timestamps. The source-game
# animation rate / exact injected button sampling are NOT assumed.
FRAMES = (30, 60, 130, 165, 215, 265, 305, 345, 395, 445, 485, 530)
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (121, "buttons="),
    (145, "buttons=L"),          # save in RAM
    (157, "buttons="),
    (180, "buttons=B"),          # restart, still retaining saved RAM
    (195, "buttons="),
    (230, "buttons=R"),          # load prior snapshot
    (245, "buttons="),
    (275, "buttons=Y"),          # explicitly SYNTHETIC upgrade
    (290, "buttons="),
    (310, "buttons=DLEFT"),      # return to previsited gate
    (352, "buttons="),
    (365, "buttons=X"),          # fresh real NPAD X at gate
    (380, "buttons="),
    (410, "buttons=DRIGHT"),     # return to hidden Bio
    (439, "buttons="),
    (460, "buttons=L"),          # save fully earned state
    (475, "buttons="),
    (497, "buttons=R"),          # restore; no duplicated lore rewards
    (510, "buttons="),
)


def instrument(source: str) -> str:
    if tuple(frame for frame, _ in HID_EVENTS) != tuple(sorted(
        set(frame for frame, _ in HID_EVENTS)
    )):
        raise ValueError("HID frame sequence must be strictly increasing")
    if max(frame for frame, _ in HID_EVENTS) >= max(FRAMES):
        raise ValueError("Guest receiver must capture a post-route PNG")
    output = instrument_frames(source)
    before = "if matches!(frames, 30 | 120 | 300) {"
    after = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(before) != 2:
        raise ValueError("Pinned guest frame_rx layout drifted")
    output = output.replace(before, after)
    schedule = " | ".join(str(frame) for frame, _ in HID_EVENTS)
    groups: dict[str, list[int]] = {}
    for frame, event in HID_EVENTS:
        if not event.startswith("buttons="):
            raise ValueError("Invalid guest HID packet")
        groups.setdefault(event, []).append(frame)
    arms = [
        "        " + " | ".join(map(str, frames)) +
        ' => "' + event + '",'
        for event, frames in groups.items()
    ]
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + after
        if output.count(anchor) != 1:
            raise ValueError("Expected exactly one pinned guest frame_rx path")
        lines = [
            f"if matches!(frames, {schedule}) {{",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            "    let text = match frames {",
            *arms,
            "        _ => unreachable!(),",
            "    };",
            "    std::fs::write(&path, text)?;",
            '    writeln!(log, "HEMAN_LORE_HID frame={} {}", frames, text)?;',
            "    log.flush()?;",
            "}",
        ]
        insertion = "\n".join(indent + item for item in lines)
        output = output.replace(
            anchor, indent + "frames += 1;\n" + insertion +
            "\n" + indent + after, 1
        )
    if output.count("HEMAN_LORE_HID frame=") != 2 or (
        output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2
    ):
        raise ValueError("Missing real guest HID or PNG hooks")
    return output


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rust_source", type=Path)
    args = ap.parse_args()
    args.rust_source.write_text(instrument(args.rust_source.read_text()))
    print("Stage112 pinned debug_boot instrumented (HID+frame_rx PNG only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
