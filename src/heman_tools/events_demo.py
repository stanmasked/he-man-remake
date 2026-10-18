"""Headless interaction exercise for the independently designed desktop course."""
import argparse
import json
from pathlib import Path

from .scene import SceneControls
from .scene_interactions import (
    advance_interactive, new_interactive_scene, synthetic_interactive_world,
)


def replay(ticks: int = 240) -> dict:
    if not isinstance(ticks, int) or not 1 <= ticks <= 3600:
        raise ValueError("ticks must be 1..3600")
    world = synthetic_interactive_world()
    state = new_interactive_scene(world)
    for tick in range(ticks):
        controls = SceneControls(
            axis=1.0 if 25 <= tick < 210 else 0.0,
            jump=tick in (70, 140),
        )
        state = advance_interactive(state, world, controls)
    return {
        "frames": state.scene.frame,
        "actor_x": round(state.scene.actor.x, 5),
        "actor_feet_y": round(state.scene.actor.feet_y, 5),
        "camera_x": round(state.scene.camera_x, 5),
        "checkpoint": state.checkpoint,
        "pickups": list(state.collected),
        "triggers": list(state.activated_triggers),
        "hazards_hit": state.hazard_hits,
        "respawns": state.scene.respawns,
        "completed": state.completed,
        "disclaimer": "Synthetic host interactions, not original He-Man level scripts or Switch gameplay.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run synthetic He-Man host interaction replay")
    parser.add_argument("--ticks", type=int, default=240)
    parser.add_argument("--out", type=Path, help="optional local_reports/ JSON output")
    args = parser.parse_args(argv)
    result = json.dumps(replay(args.ticks), indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result, encoding="utf-8")
        print(f"Host interaction report: {args.out}")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
