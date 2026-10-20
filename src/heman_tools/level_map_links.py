"""Private-only, read-only links between a level's map objects and .map resources.

Exact identifier coincidence is candidate evidence, never proof of runtime
ownership, terrain solidity, level traversal or authentic iOS gameplay.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import zipfile

from .lvl import LevelFormatError
from .objects import ParsedLevel, parse_level_objects
from .tilemap import MAX_FILE as MAX_MAP_FILE, parse_tilemap

_LEVEL_LIMIT = 8_000_000
_MAX_MAP_ENTRIES = 4096
_MAX_CANDIDATE_MAPS = 64
_TARGET_CLASSES = frozenset(("LevelTileMap", "LevelTileMapOverlay"))
_SCREENS = frozenset(("screen-med", "screen-xlarge"))


def _filename(name: str, suffix: str) -> str:
    if (not isinstance(name, str) or len(name) <= len(suffix)
            or not name.endswith(suffix) or "/" in name or "\\" in name
            or not name.isprintable() or "\x00" in name):
        raise ValueError(f"expected one simple {suffix} basename")
    return name


def candidate_map_links(level: ParsedLevel, map_names: list[str]) -> dict:
    """Find *exact* map-name/stem equality among relevant object metadata."""
    if len(map_names) > _MAX_MAP_ENTRIES:
        raise ValueError("too many map names")
    if len(set(map_names)) != len(map_names):
        raise ValueError("duplicate map names")
    for name in map_names:
        _filename(name, ".map")

    rows = []
    referenced = set()
    for obj in level.objects:
        if obj.class_name not in _TARGET_CLASSES:
            continue
        matches = defaultdict(set)
        for filename in map_names:
            stem = filename[:-4]
            if obj.instance_name in (filename, stem):
                matches[filename].add("object_instance_exact")
            for prop in obj.properties:
                if prop.kind != "string" or not isinstance(prop.value, str):
                    continue
                if prop.value and prop.value in (filename, stem):
                    matches[filename].add("typed_string_property_exact:" + prop.name)
        status = ("no_exact_candidate" if not matches else
                  "one_exact_candidate" if len(matches) == 1 else
                  "ambiguous_multiple_candidates")
        rows.append({
            "object_index": obj.index,
            "object_class": obj.class_name,
            "candidate_status": status,
            "candidate_maps": [
                {"filename": name, "evidence": sorted(reason)}
                for name, reason in sorted(matches.items())
            ],
        })
        referenced.update(matches)
    if len(referenced) > _MAX_CANDIDATE_MAPS:
        raise ValueError("too many matching map candidates")
    return {
        "level": level.level_name,
        "map_object_count": len(rows),
        "available_map_count": len(map_names),
        "exact_candidate_map_count": len(referenced),
        "map_objects": rows,
        "candidate_map_names": sorted(referenced),
        "map_binding_confirmed": False,
        "collision_semantics_confirmed": False,
        "interpretation": (
            "Only exact text coincidences from level objects and map archive "
            "names. A candidate is not proof of resource ownership, game-world "
            "geometry, solidity, overlays or any original iOS mechanics."
        ),
    }


def audit_local_ipa(ipa: Path, level: str = "MULevel1-1.lvl",
                    screen: str = "screen-med") -> dict:
    """Inspect one private level and structurally decode only referenced maps."""
    _filename(level, ".lvl")
    if screen not in _SCREENS:
        raise ValueError("unsupported screen pack")
    base = f"Payload/MOTU.app/{screen}/"
    level_path = base + "levels/" + level
    prefix = base + "maps/"
    with zipfile.ZipFile(ipa, "r") as archive:
        entries = archive.infolist()
        level_entries = [z for z in entries if z.filename == level_path]
        if len(level_entries) != 1:
            raise ValueError("expected exactly one requested level entry")
        if level_entries[0].file_size > _LEVEL_LIMIT:
            raise LevelFormatError("level exceeds bounded read limit")
        parsed = parse_level_objects(archive.read(level_entries[0]))
        if parsed.level_name != level:
            raise LevelFormatError("embedded level name does not match entry")

        map_infos = {}
        for entry in entries:
            if not entry.filename.startswith(prefix) or not entry.filename.endswith(".map"):
                continue
            name = entry.filename[len(prefix):]
            _filename(name, ".map")  # reject nested, ambiguous paths
            if name in map_infos:
                raise ValueError("duplicate .map entry")
            if entry.file_size > MAX_MAP_FILE:
                raise ValueError("oversized .map resource")
            map_infos[name] = entry
            if len(map_infos) > _MAX_MAP_ENTRIES:
                raise ValueError("too many .map entries")

        report = candidate_map_links(parsed, list(map_infos))
        map_summaries = []
        for filename in report.pop("candidate_map_names"):
            decoded = parse_tilemap(archive.read(map_infos[filename]))
            named = sum(layer.name == "collision" for layer in decoded.layers)
            map_summaries.append({
                "filename": filename,
                "layer_count": len(decoded.layers),
                "unique_named_collision_layer": named == 1,
                "collision_layer_name_occurrences": named,
                "structural_parse_passed": True,
                "solid_tile_semantics_established": False,
            })
    report.update({"screen": screen, "candidate_map_structures": map_summaries,
                   "real_game_object_link_confirmed": False})
    return report


def _private_report_path(path: Path) -> Path:
    root = Path.cwd() / "local_reports"
    if root.is_symlink():
        raise ValueError("local_reports must not be a symbolic link")
    dest, resolved = path.resolve(), root.resolve()
    if dest == resolved or not dest.is_relative_to(resolved) or dest.suffix != ".json":
        raise ValueError("output must be private JSON inside local_reports/")
    return dest


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ipa", type=Path, required=True)
    p.add_argument("--level", default="MULevel1-1.lvl")
    p.add_argument("--screen", choices=sorted(_SCREENS), default="screen-med")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    target = _private_report_path(args.out)
    result = audit_local_ipa(args.ipa, args.level, args.screen)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"Checked {result['map_object_count']} map-class objects; "
          "source-private audit saved under local_reports/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
