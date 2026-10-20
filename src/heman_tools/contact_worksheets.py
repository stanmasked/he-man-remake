"""Create blank, non-evidentiary private worksheets for five fixed scenarios.

Never generates iOS measurements, claims successful observations or exports
proprietary source bytes. Blank forms MUST fail the Stage 076/077 validators.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from .contact_scenarios import SCENARIOS, FPS, scripted_controls
from .frame_alignment import _private_path


def blank_scenario(scenario_id: str) -> dict:
    if type(scenario_id) is not str or scenario_id not in SCENARIOS:
        raise ValueError("unknown scenario ID")
    rows = [{
        "frame": i,
        "control": {"horizontal": horizontal, "jump": jump},
        "feet_screen_xy": None,
        "anchor_screen_xy": None,
        "contact": None,
    } for i, (horizontal, jump) in enumerate(scripted_controls(scenario_id))]
    def capture(platform: str) -> dict:
        return {
            "platform": platform,
            "capture_id": None,
            "evidence_kind": None,
            "stationary_anchor_id": None,
            "pixels_per_unit": None,
            "observations": deepcopy(rows),
        }
    return {
        "template_only": True,
        "scenario_id": scenario_id,
        "fps": FPS,
        "manual_initial_condition": SCENARIOS[scenario_id]["precondition"],
        "reference": capture("ios"),
        "candidate": capture("switch"),
    }


def blank_suite() -> dict:
    return {
        "template_only": True,
        "traces": [blank_scenario(name) for name in SCENARIOS],
        "captured_original_ios_gameplay": False,
        "original_gameplay_physics_verified": False,
        "automatic_collision_export_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--scenario", choices=tuple(SCENARIOS))
    group.add_argument("--suite", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    destination = _private_path(args.out)
    # Never overwrite private observations or an existing worksheet.
    if destination.exists() or destination.is_symlink():
        raise ValueError("refusing to overwrite existing private worksheet")
    content = blank_suite() if args.suite else blank_scenario(args.scenario)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as output:
        json.dump(content, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print("Wrote BLANK contact worksheet; not gameplay evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
