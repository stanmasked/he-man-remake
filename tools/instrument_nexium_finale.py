"""Inject a genuine Right/A/B guest path to native second-room FINISH.

Only patches a temporary pinned NeXium frame receiver at CI build time;
never changes the compiled NRO, guest RAM, commercial assets or PNG bytes.
The actual exit must be reached by normal game physics. Failure to reach it
is evidence of an incomplete experiment, not a reason to fake a screenshot.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from instrument_nexium_frames import instrument as instrument_frames

FRAMES = (75, 105, 330, 365, 465, 490, 515, 565, 590)
# Stage 1 native Right exit and A -> stage 2.
# Room 2: Right across native checkpoint, A jump near x≈528 to avoid
# the unchanged x570 hazard, then advance toward genuine x735 exit.
# B is only pressed AFTER the FINISH panel has been sampled three times.
# Timings are experimental and must be validated by real guest pixels.
HID_EVENTS = (
    (45, "buttons=DRIGHT"),
    (78, "buttons="),
    (90, "buttons=A"),
    (95, "buttons="),
    (110, "buttons=DRIGHT"),
    (350, "buttons=DRIGHT,A"),
    (353, "buttons=DRIGHT"),
    (500, "buttons="),
    (540, "buttons=B"),
    (543, "buttons="),
)


def instrument(source: str) -> str:
    output = instrument_frames(source)
    base = "if matches!(frames, 30 | 120 | 300) {"
    cap = "if matches!(frames, " + " | ".join(map(str, FRAMES)) + ") {"
    if output.count(base) != 2:
        raise ValueError("Pinned NeXium genuine guest receivers changed")
    output = output.replace(base, cap)
    schedule = " | ".join(str(frame) for frame, _ in HID_EVENTS)
    actions = {}
    for frame, event in HID_EVENTS:
        actions.setdefault(event, []).append(frame)
    arms = []
    for action, frames in actions.items():
        arms.append('        ' + ' | '.join(map(str, frames))
                    + ' => "' + action + '",')
    for indent in ("            ", "        "):
        anchor = indent + "frames += 1;\n" + indent + cap
        if output.count(anchor) != 1:
            raise ValueError("Missing one distinct NeXium guest loop")
        statements = [
            f"if matches!(frames, {schedule}) {{",
            '    let path = std::env::var("NEXIUM_HID_INJECT")?;',
            '    let action = match frames {',
            *arms,
            '        _ => unreachable!(),',
            '    };',
            '    std::fs::write(&path, action)?;',
            '    writeln!(log, "HEMAN_FINALE_HID frame={} {}", frames, action)?;',
            '    log.flush()?;',
            '}',
        ]
        snippet = "\n".join(indent + item for item in statements)
        output = output.replace(
            anchor, indent + "frames += 1;\n" + snippet + "\n" +
            indent + cap, 1)
    if output.count("HEMAN_FINALE_HID frame=") != 2:
        raise ValueError("Guest controller hooks not installed twice")
    if output.count("HEMAN_GUEST_FRAME_PNG frame=") != 2:
        raise ValueError("Both authentic guest PNG capture loops required")
    return output


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rust_source", type=Path)
    args = p.parse_args()
    path = args.rust_source
    path.write_text(instrument(path.read_text()))
    print("Installed native second-room FINISH / B guest-frame instrumentation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
