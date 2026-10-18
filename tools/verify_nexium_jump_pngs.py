"""Check that real NeXium A input changes guest world height and lands."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops
from verify_nexium_guest_pngs import describe

FRAMES=(30,65,120)

def validate(directory: Path) -> dict:
    centers=[];magenta_x=[];frames=[]
    for index in FRAMES:
        path=directory / f"raster-frame-{index:04}.png"
        if not path.exists():
            raise FileNotFoundError(path)
        with Image.open(path) as raw:
            if raw.format != "PNG":
                raise ValueError(f"Frame {index} is not PNG")
            img=raw.convert("RGB")
        count,colors,x=describe(img)
        if count<100 or colors<8:
            raise ValueError("Missing original scene or player-x HUD marker")
        ys=[]
        for y in range(76,334):
            for col in range(471,488):
                r,g,b=img.getpixel((col,y))
                if r<=60 and g>=195 and b>=195:
                    ys.append(y)
        if len(ys)<100:
            raise ValueError(f"Guest world-height cyan marker missing in frame {index}")
        centers.append(sum(ys)/len(ys))
        magenta_x.append(x)
        frames.append(img)
    pre,airborne,landed=centers
    if pre-airborne<20.0:
        raise ValueError(f"Guest did not jump upward after real A button: {centers}")
    if abs(pre-landed)>5.0:
        raise ValueError(f"Guest did not return to original ground height: {centers}")
    if max(magenta_x)-min(magenta_x)>5:
        raise ValueError(f"Guest drifted horizontally without directional input: {magenta_x}")
    diff=ImageChops.difference(frames[0],frames[1])
    track_changed=sum(1 for y in range(76,334) for col in range(471,488)
                      if max(diff.getpixel((col,y)))>=45)
    if track_changed<140:
        raise ValueError(f"World height HUD did not visually move: {track_changed} pixels")
    log=(directory/"raster-runner.log").read_text()
    for msg in ("HEMAN_JUMP_HID frame=45 buttons=A",
                "HEMAN_JUMP_HID frame=58 buttons="):
        if msg not in log:
            raise ValueError(f"Guest HID press/release event missing: {msg}")
    return {"frames":list(FRAMES),
            "world_height_marker_y":[round(y,2) for y in centers],
            "jump_up_screen_px":round(pre-airborne,2),
            "landed_error_screen_px":round(abs(pre-landed),2),
            "world_x_marker":[round(x,2) for x in magenta_x],
            "height_hud_changed_pixels":track_changed}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder",type=Path)
    args=p.parse_args()
    print(json.dumps(validate(args.folder),indent=2,sort_keys=True))
    print("PASS: real NeXium A caused vertical jump and return to ground")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
