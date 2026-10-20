"""Private, read-only *candidate* cross-reference scan for iOS level objects and shapes.

Exact string coincidences do NOT prove shape ownership, placement, collision
semantics, transform scale or authentic game behavior. Never export source data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import zipfile

from .lvl import LevelFormatError
from .objects import ParsedLevel, parse_level_objects
from .shapes import Shape, parse_shape

_LEVEL_ROOT = "Payload/MOTU.app/screen-med/levels/"
_SHAPE_ROOT = "Payload/MOTU.app/screen-med/geometry/"
_MAX_LEVEL = 8_000_000
_MAX_SHAPE = 1024 * 1024
_MAX_SHAPES = 4096
_MAX_ALL_SHAPES = 16_000_000


def candidate_crossrefs(level: ParsedLevel,
                        shapes: dict[str, Shape]) -> dict:
    """Summarize exact-name coincidences without inferring actual ownership."""
    records = []
    counts = Counter()
    for filename, shape in sorted(shapes.items()):
        if not filename.endswith(".shape") or filename in {".shape", ""}:
            raise ValueError("shape key must be a .shape basename")
        if "/" in filename or "\\" in filename:
            raise ValueError("shape key must not be a path")
        stem = filename[:-6]
        reference = shape.reference
        found = []
        for obj in level.objects:
            evidence = set()
            if obj.instance_name and obj.instance_name == stem:
                evidence.add("filename_eq_instance")
            if reference and obj.instance_name and obj.instance_name == reference:
                evidence.add("reference_eq_instance")
            for prop in obj.properties:
                if prop.kind != "string" or not isinstance(prop.value, str):
                    continue
                if prop.value and prop.value == stem:
                    evidence.add("filename_eq_string_property")
                if reference and prop.value and prop.value == reference:
                    evidence.add("reference_eq_string_property")
            if evidence:
                found.append({"object_index": obj.index,
                              "evidence": sorted(evidence)})
        status = ("no_exact_candidate" if not found else
                  "one_candidate_only" if len(found) == 1 else
                  "ambiguous_multiple_candidates")
        counts[status] += 1
        records.append({"shape": filename, "kind": shape.kind,
                        "flags": shape.flags, "reference": reference,
                        "candidate_status": status,
                        "candidate_objects": found})
    return {
        "level": level.level_name,
        "object_count": len(level.objects),
        "shape_count": len(records),
        "status_counts": {key: counts[key] for key in (
            "no_exact_candidate", "one_candidate_only",
            "ambiguous_multiple_candidates")},
        "shapes": records,
        "ownership_confirmed": False,
        "interpretation": (
            "Exact textual coincidences only. No ownership, object-to-shape "
            "transform, scale, collision mask, hazard or physics proven."
        ),
    }


def inspect_private_ipa(ipa: Path, level_name: str) -> dict:
    """Read one level and bounded .shape definitions without extracting files."""
    if (not isinstance(level_name, str) or
            len(level_name) <= 4 or not level_name.endswith(".lvl") or
            "/" in level_name or "\\" in level_name or
            "\x00" in level_name or "\r" in level_name or "\n" in level_name):
        raise ValueError("expected a simple .lvl basename")
    path = _LEVEL_ROOT + level_name
    with zipfile.ZipFile(ipa, "r") as archive:
        entries = archive.infolist()
        levels = [info for info in entries if info.filename == path]
        if len(levels) != 1:
            raise ValueError("expected exactly one requested level")
        if levels[0].file_size > _MAX_LEVEL:
            raise LevelFormatError("oversized level entry")
        parsed = parse_level_objects(archive.read(levels[0]))
        if parsed.level_name != level_name:
            raise LevelFormatError("embedded level name mismatch")
        geometry = [info for info in entries
                    if info.filename.startswith(_SHAPE_ROOT)
                    and info.filename.endswith(".shape")]
        if len(geometry) > _MAX_SHAPES or sum(info.file_size for info in geometry) > _MAX_ALL_SHAPES:
            raise LevelFormatError("too many or oversized .shape entries")
        shapes = {}
        for info in geometry:
            name = info.filename[len(_SHAPE_ROOT):]
            if (not name or "/" in name or "\\" in name or name in shapes):
                raise ValueError("duplicate or nested .shape entry")
            if info.file_size > _MAX_SHAPE:
                raise LevelFormatError("oversized .shape entry")
            shapes[name] = parse_shape(archive.read(info))
    return candidate_crossrefs(parsed, shapes)


def private_report_path(path: Path) -> Path:
    """Fail closed for paths outside an ignored, real local_reports root."""
    root = Path.cwd() / "local_reports"
    if root.is_symlink():
        raise ValueError("local_reports must not be a symbolic link")
    target = path.resolve()
    resolved = root.resolve()
    if (target == resolved or not target.is_relative_to(resolved)
            or target.suffix != ".json"):
        raise ValueError("report must be .json inside local_reports/")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--level", default="MULevel1-1.lvl")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report_path = private_report_path(args.out)
    report = inspect_private_ipa(args.ipa, args.level)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Inspected {report['shape_count']} private shape definitions. "
          "Full candidate evidence saved in local_reports/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
