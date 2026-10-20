"""Offline parity check on two privately held iOS screen packs.

Only aggregate metadata is returned. Identical assets do not prove collision,
level-map ownership, scale, or original gameplay behavior.
"""
from __future__ import annotations
import argparse
import json
import stat
from pathlib import Path
import struct
import zipfile

BASE = "Payload/MOTU.app/"
SCREENS = ("screen-med", "screen-xlarge")
LIMIT = 16 * 1024 * 1024


def _basename(name: str, extension: str) -> str:
    if (not isinstance(name, str) or not name.endswith(extension)
            or len(name) <= len(extension) or len(name) > 255
            or any(ch in name for ch in ("/", "\\"))
            or not name.isprintable()):
        raise ValueError("invalid resource basename")
    return name


def compare_pair(ipa: Path, level="MULevel1-1.lvl",
                 map_name="MUMap1-1.map") -> dict:
    _basename(level, ".lvl")
    _basename(map_name, ".map")
    if not ipa.is_file() or not zipfile.is_zipfile(ipa):
        raise ValueError("not an IPA ZIP")
    assets = (("level", "levels", level), ("map", "maps", map_name))
    with zipfile.ZipFile(ipa) as archive:
        entries = archive.infolist()
        if len(entries) > 100_000 or len({e.filename for e in entries}) != len(entries):
            raise ValueError("duplicate or oversized ZIP index")
        by_name = {entry.filename: entry for entry in entries}
        comparison = {}
        for kind, directory, filename in assets:
            data = []
            for screen in SCREENS:
                path = BASE + screen + "/" + directory + "/" + filename
                entry = by_name.get(path)
                if (entry is None or entry.is_dir() or entry.flag_bits & 1
                        or not 4 <= entry.file_size <= LIMIT):
                    raise ValueError("missing, encrypted or oversized resource pair")
                if stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFLNK:
                    raise ValueError("missing, encrypted or oversized resource pair")
                block = archive.read(entry)
                if len(block) != entry.file_size:
                    raise ValueError("incomplete resource")
                data.append(block)
            headers = [struct.unpack("<I", item[:4])[0] for item in data]
            comparison[kind] = {
                "bytes_per_screen": dict(zip(SCREENS, map(len, data))),
                "first_u32_per_screen": dict(zip(SCREENS, headers)),
                "exact_bytes_equal": data[0] == data[1],
                "standard_header_observed": (
                    all(v == 1 for v in headers) if kind == "level"
                    else all(v in (1, 2, 3) for v in headers)
                ),
            }
    return {
        "schema_version": 1,
        "level": level,
        "candidate_map": map_name,
        "screen_variants": list(SCREENS),
        "selected_pairs": comparison,
        "cross_pack_bytes_identical": all(
            row["exact_bytes_equal"] for row in comparison.values()),
        "level_to_map_binding_verified": False,
        "collision_type_verified": False,
        "original_gameplay_trace_verified": False,
        "automatic_collision_export_permitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--level", default="MULevel1-1.lvl")
    parser.add_argument("--map", dest="map_name", default="MUMap1-1.map")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd() / "local_reports"
    if root.is_symlink():
        parser.error("report root cannot be a symlink")
    target = args.out.resolve()
    if not target.is_relative_to(root.resolve()) or target.suffix != ".json":
        parser.error("output must remain inside local_reports/")
    result = compare_pair(args.ipa, args.level, args.map_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Completed source-private resource pairing audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
