"""Local-only point-group audit. Game data never leave the user's machine."""
import argparse
import json
from pathlib import Path
import zipfile
from dataclasses import asdict

from .lvl import LevelFormatError
from .waypoints import parse_waypoints


def audit_waypoints(ipa: Path, level: str, screen: str = "screen-med") -> dict:
    if not level.endswith(".lvl") or "/" in level or "\\" in level:
        raise ValueError("--level must be a bare .lvl filename")
    if screen not in {"screen-med", "screen-xlarge"}:
        raise ValueError("invalid screen group")
    path = f"Payload/MOTU.app/{screen}/levels/{level}"
    with zipfile.ZipFile(ipa) as archive:
        info = archive.getinfo(path)
        if info.file_size > 8_000_000:
            raise LevelFormatError("oversized level")
        result = parse_waypoints(archive.read(info))
    if result.level_name != level:
        raise LevelFormatError("level name mismatch")
    return {
        "level": result.level_name,
        "groups_count": len(result.groups),
        "points_count": result.total_points,
        "links_count": result.total_links,
        "groups": [asdict(g) for g in result.groups],
        "note": "Raw graph links have unknown runtime semantics.",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Inspect point groups from a local iOS IPA")
    p.add_argument("--ipa", required=True, type=Path)
    p.add_argument("--level", default="MULevel1-1.lvl")
    p.add_argument("--screen", default="screen-med", choices=["screen-med", "screen-xlarge"])
    p.add_argument("--out", type=Path, help="Optional private JSON report under local_reports/")
    args = p.parse_args(argv)
    report = audit_waypoints(args.ipa, args.level, args.screen)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Analysed {report['points_count']} points in {report['groups_count']} groups")
    else:
        print(f"{report['level']}: {report['points_count']} points, {report['groups_count']} groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
