"""Fail closed unless actual guest PNGs show damage, immunity and respawn.

Inspect the C99 scene's *live* player HUD at five guest frames and
the native player respawn counter's independently colored HUD marker.
No controller injection, renderer state overrides or original IPA assets.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

FRAMES = (10, 25, 40, 61, 62)
EXPECTED_HEALTH = (2, 2, 1, 0, 3)
EXPECTED_RESPAWNS = (0, 0, 0, 0, 1)
ALIVE=(101,121,231)
EMPTY=(81,59,73)
ENEMY_ALIVE=(109,200,225)
COUNTER_EMPTY=(81,61,40)
COUNTER_ACTIVE=(138,213,66)
HP_X=(18,36,54)


def verify(directory: Path) -> dict:
    # The constants above intentionally import without optional Pillow:
    # source-only CI can test the byte/color contract without GUI packages.
    from PIL import Image
    from verify_nexium_guest_pngs import describe
    states=[]
    marker_x=[]
    raw_hp=[]
    counters=[]
    for frame,health,respawns in zip(
        FRAMES, EXPECTED_HEALTH, EXPECTED_RESPAWNS
    ):
        path=directory/f"raster-frame-{frame:04}.png"
        if not path.is_file():
            raise FileNotFoundError(f"Missing real NeXium guest PNG {path}")
        with Image.open(path) as raw:
            if raw.format != "PNG":
                raise ValueError(f"Guest frame {frame} is not PNG")
            rgb=raw.convert("RGB")
        count,colors,world_x=describe(rgb)
        if count!=192 or colors<8:
            raise ValueError(f"Guest character/world marker missing at frame {frame}")
        expected_ticks=[ALIVE if idx<health else EMPTY for idx in range(3)]
        hp_ticks=[rgb.getpixel((x,18)) for x in HP_X]
        if hp_ticks!=expected_ticks:
            raise ValueError(
                f"Frame {frame} player HP mismatch: "
                f"actual={hp_ticks} expected={expected_ticks}"
            )
        enemy=[rgb.getpixel((x,18)) for x in (226,244)]
        if enemy != [ENEMY_ALIVE,ENEMY_ALIVE]:
            raise ValueError(f"Enemy reset/state corruption at frame {frame}: {enemy}")
        counter=rgb.getpixel((522,62))
        expected_counter=COUNTER_ACTIVE if respawns else COUNTER_EMPTY
        if counter!=expected_counter:
            raise ValueError(
                f"Frame {frame}: expected native respawn indicator "
                f"{expected_counter}, saw {counter}"
            )
        if abs(world_x-125.5)>2.0:
            raise ValueError(f"Unexpected player world-x movement: {world_x}")
        states.append({"frame":frame,"player_hp":health,"respawns":respawns,
                       "colors":colors})
        marker_x.append(round(world_x,2))
        raw_hp.append(hp_ticks)
        counters.append(counter)
    if not (raw_hp[0]==raw_hp[1] and raw_hp[1]!=raw_hp[2]):
        raise ValueError("No immunity interval before the second contact hit")
    if raw_hp[3] == raw_hp[4] or counters[3] == counters[4]:
        raise ValueError("Defeat and subsequent native respawn not distinguished")
    log=(directory/"raster-runner.log").read_text()
    for frame in FRAMES:
        if f"HEMAN_GUEST_FRAME_PNG frame={frame} " not in log:
            raise ValueError(f"No evidence for captured guest frame {frame}")
    return {"states":states,"world_x_marker_px":marker_x,
            "respawn_marker_rgb":counters,
            "player_hp_ticks_rgb":raw_hp,
            "invulnerability_preserved_hp":True,
            "native_defeat_and_recovery_visible":True}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder",type=Path)
    args=p.parse_args()
    print(json.dumps(verify(args.folder),indent=2,sort_keys=True))
    print("PASS: NeXium guest HP 2->2->1->0->3, damage immunity and native respawn")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
