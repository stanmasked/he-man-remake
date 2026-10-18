"""Generate a local SVG diagram from a privately held IPA; no assets uploaded."""
import argparse
from pathlib import Path
import zipfile

from .objects import parse_level_objects
from .waypoints import parse_waypoints
from .map_viewer import render_level_svg
from .lvl import LevelFormatError


def render_ipa(ipa: Path, level: str, *, min_x=None, max_x=None) -> str:
    if not level.endswith(".lvl") or '/' in level or '\\' in level:
        raise ValueError("--level must be a bare .lvl filename")
    with zipfile.ZipFile(ipa) as archive:
        info = archive.getinfo(f"Payload/MOTU.app/screen-med/levels/{level}")
        if info.file_size > 8_000_000:
            raise LevelFormatError("oversized level")
        data = archive.read(info)
    objects = parse_level_objects(data)
    if objects.level_name != level:
        raise LevelFormatError("level identity mismatch")
    graph = parse_waypoints(data)
    return render_level_svg(objects, graph, min_x=min_x, max_x=max_x)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate asset-free level-coordinate SVG from local purchased IPA")
    p.add_argument('--ipa', type=Path, required=True)
    p.add_argument('--level', default='MULevel1-1.lvl')
    p.add_argument('--out', type=Path, required=True, help='save to local_reports/; do not commit')
    p.add_argument('--min-x', type=float)
    p.add_argument('--max-x', type=float)
    args = p.parse_args(argv)
    svg = render_ipa(args.ipa, args.level, min_x=args.min_x, max_x=args.max_x)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding='utf-8')
    print(f"SVG saved to {args.out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
