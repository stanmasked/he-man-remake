"""A true NeXium guest-HID experiment for opt-in synthetic aerial ZL.

Instruments a temporary copy of pinned NeXium, never the compiled NRO or
guest RAM. Video and game-state success must come from actual guest frames.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from instrument_nexium_frames import instrument as add_guest_pngs

FRAMES = (75, 105, 125, 143, 145, 148, 152, 158, 183, 193, 211, 231, 245)
# First-room Right->native CLEAR->A. New room: Right, native A jump,
# then ZL while airborne. Test a rejected second ZL while cooling, and
# Minus pause/resume, then natural B respawn. Timings are EXPERIMENTAL;
# failed guest evidence requires revision, never patching source state.
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (78, "buttons="),
    (90, "buttons=A"),
    (95, "buttons="),
    (110, "buttons=DRIGHT"),
    (140, "buttons=DRIGHT,A"),
    (143, "buttons=DRIGHT"),
    (144, "buttons=DRIGHT,ZL"),
    (146, "buttons=DRIGHT"),
    (150, "buttons=DRIGHT,ZL"),
    (152, "buttons=DRIGHT"),
    (170, "buttons="),
    (175, "buttons=MINUS"),
    (178, "buttons="),
    (200, "buttons=MINUS"),
    (203, "buttons="),
    (235, "buttons=B"),
    (238, "buttons="),
)


def instrument(source: str) -> str:
    patched = add_guest_pngs(source)
    base = "if matches!(frames, 30 | 120 | 300) {"
    replacement = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if patched.count(base) != 2:
        raise ValueError("Pinned NeXium frame receiver has changed")
    patched = patched.replace(base, replacement)
    actions: dict[str, list[int]] = {}
    for frame, action in HID_EVENTS:
        actions.setdefault(action, []).append(frame)
    arms = [
        '    ' + ' | '.join(map(str, frames)) + ' => "' + action + '",'
        for action, frames in actions.items()
    ]
    schedule = ' | '.join(str(frame) for frame, _ in HID_EVENTS)
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + replacement
        if patched.count(anchor) != 1:
            raise ValueError("A genuine guest frame loop could not be found")
        statements = [
            f"if matches!(frames, {schedule}) {{",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = match frames {',
            *arms,
            '        _ => unreachable!(),',
            '    };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_SMASH_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            '}',
        ]
        insertion = "\n".join(indent + line for line in statements)
        patched = patched.replace(
            anchor, indent + "frames += 1;\n" + insertion + "\n" +
            indent + replacement, 1)
    if (patched.count("HEMAN_SMASH_HID frame=") != 2
            or patched.count("HEMAN_GUEST_FRAME_PNG frame=") != 2):
        raise ValueError("Missing guest HID or PNG recorder")
    return patched


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    args = p.parse_args()
    original = args.rust_source.read_text()
    args.rust_source.write_text(instrument(original))
    print("Inserted source-only ZL/HID and frame-receiver probes into NeXium")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
