"""Local-only, read-only inspection of a single level from a user's IPA."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import zipfile

from .lvl import LevelFormatError
from .objects import parse_level_objects

PREFIX = "Payload/MOTU.app/screen-med/levels/"


def audit_objects(ipa: Path, level: str) -> dict:
    if not level.endswith(".lvl") or "/" in level or "\\" in level or level in {".", ".."}:
        raise ValueError("--level must be a bare .lvl filename")
    with zipfile.ZipFile(ipa, "r") as archive:
        info = archive.getinfo(PREFIX + level)
        if info.file_size > 8_000_000:
            raise LevelFormatError("level exceeds 8 MB size limit")
        parsed = parse_level_objects(archive.read(info))
    if parsed.level_name != level:
        raise LevelFormatError("embedded level name differs from archive entry")
    return {
        "level": parsed.level_name,
        "object_count": len(parsed.objects),
        "trailer_bytes": parsed.trailer_bytes,
        "trailer_record_count_hint": parsed.trailer_record_count_hint,
        "trailer_decoded": False,
        "objects": [asdict(obj) for obj in parsed.objects],
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Inspect a local He-Man iOS level without extracting it")
    p.add_argument("--ipa", required=True, type=Path)
    p.add_argument("--level", default="MULevel1-1.lvl")
    p.add_argument("--out", type=Path, help="local report outside git (recommended: local_reports/)")
    args = p.parse_args(argv)
    report = audit_objects(args.ipa, args.level)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Decoded {report['object_count']} objects; local report at {args.out}")
    else:
        print(f"{report['level']}: {report['object_count']} objects; "
              f"{report['trailer_bytes']} opaque trailing bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
