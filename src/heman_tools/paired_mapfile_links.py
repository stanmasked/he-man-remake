"""Cross-check explicit mapFileName candidates across both private screen packs.

An exact typed-property reference establishes a textual relationship only.
It NEVER authenticates source-game runtime binding or collision physics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .level_map_links import _private_report_path, audit_local_ipa

SCREENS = ("screen-med", "screen-xlarge")
CLASSES = ("LevelTileMap", "LevelTileMapOverlay")
EXPLICIT_REFERENCE = "typed_string_property_exact:mapFileName"
MAX_OBJECTS = 4096
MAX_STRUCTURES = 64


def _simple_map(value: object) -> str:
    if (not isinstance(value, str) or len(value) <= 4
            or len(value) > 255 or not value.endswith(".map")
            or "/" in value or "\\" in value or not value.isprintable()):
        raise ValueError("invalid candidate map basename")
    return value


def _extract(report: dict, screen: str) -> dict:
    if not isinstance(report, dict) or report.get("screen") != screen:
        raise ValueError("report belongs to a different screen pack")
    for field in ("map_binding_confirmed", "collision_semantics_confirmed",
                  "real_game_object_link_confirmed"):
        if report.get(field) is not False:
            raise ValueError("input must not claim authenticated gameplay")
    rows = report.get("map_objects")
    structures = report.get("candidate_map_structures")
    if (not isinstance(rows, list) or not isinstance(structures, list)
            or len(rows) > MAX_OBJECTS or len(structures) > MAX_STRUCTURES
            or type(report.get("map_object_count")) is not int
            or report["map_object_count"] != len(rows)):
        raise ValueError("invalid map-object or structure collection")
    by_file = {}
    for item in structures:
        if not isinstance(item, dict):
            raise ValueError("invalid map structure record")
        filename = _simple_map(item.get("filename"))
        if filename in by_file:
            raise ValueError("duplicate candidate map structure")
        n = item.get("collision_layer_name_occurrences")
        count = item.get("layer_count")
        if (type(n) is not int or type(count) is not int
                or not (0 <= n <= count <= 32)
                or item.get("structural_parse_passed") is not True
                or item.get("unique_named_collision_layer") is not (n == 1)
                or item.get("solid_tile_semantics_established") is not False):
            raise ValueError("inconsistent collision-layer structure")
        by_file[filename] = (count, n)
    seen_indices = set()
    explicit = {}
    blockers = []
    for obj in rows:
        if not isinstance(obj, dict):
            raise ValueError("invalid map-class object")
        index = obj.get("object_index")
        cls = obj.get("object_class")
        if (type(index) is not int or index < 0 or index in seen_indices
                or cls not in CLASSES):
            raise ValueError("invalid or duplicate map object identity")
        seen_indices.add(index)
        candidates = obj.get("candidate_maps")
        if not isinstance(candidates, list) or len(candidates) > MAX_STRUCTURES:
            raise ValueError("invalid candidate list")
        expected = ("no_exact_candidate" if not candidates else
                    "one_exact_candidate" if len(candidates) == 1 else
                    "ambiguous_multiple_candidates")
        if obj.get("candidate_status") != expected:
            raise ValueError("candidate status contradicts references")
        typed = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("invalid candidate")
            filename = _simple_map(candidate.get("filename"))
            reasons = candidate.get("evidence")
            if (not isinstance(reasons, list) or
                    not all(isinstance(s, str) for s in reasons)):
                raise ValueError("invalid reference evidence")
            if EXPLICIT_REFERENCE in reasons:
                typed.append(filename)
            if filename not in by_file:
                raise ValueError("referenced map lacks parsed structure")
        if len(candidates) != 1 or len(typed) != 1:
            blockers.append("missing_unique_mapFileName_reference:" + cls)
            continue
        filename = typed[0]
        layers, collision = by_file[filename]
        if cls in explicit:
            blockers.append("duplicate_" + cls + "_objects")
        explicit[cls] = (index, filename, layers, collision)
    for cls in CLASSES:
        if cls not in explicit:
            blockers.append("missing_" + cls + "_mapFileName")
    if len(explicit) == 2:
        if explicit[CLASSES[0]][1] == explicit[CLASSES[1]][1]:
            blockers.append("primary_and_overlay_share_same_resource")
        if explicit[CLASSES[0]][3] != 1:
            blockers.append("primary_map_lacks_one_named_collision_layer")
        if explicit[CLASSES[1]][3] != 0:
            blockers.append("overlay_contains_collision_layer")
    return {"links": explicit, "blockers": blockers}


def audit_paired_reports(medium: dict, xlarge: dict) -> dict:
    if (not isinstance(medium, dict) or not isinstance(xlarge, dict)
            or medium.get("level") != xlarge.get("level")
            or not isinstance(medium.get("level"), str)):
        raise ValueError("different or missing level identities")
    a, b = (_extract(medium, SCREENS[0]), _extract(xlarge, SCREENS[1]))
    blockers = sorted(set(a["blockers"] + b["blockers"]))
    if a["links"] != b["links"]:
        blockers.append("screen_pack_explicit_references_or_layers_differ")
    return {
        "level": medium["level"],
        "screen_packs": list(SCREENS),
        "explicit_reference_property": "mapFileName",
        "candidate_links": {
            cls: {"object_index": a["links"][cls][0],
                  "map_filename": a["links"][cls][1],
                  "layer_count": a["links"][cls][2],
                  "named_collision_layers": a["links"][cls][3]}
            for cls in CLASSES if cls in a["links"]
        },
        "cross_pack_candidate_consistency": not blockers,
        "structural_blockers": blockers,
        "runtime_map_binding_verified": False,
        "collision_semantics_verified": False,
        "coordinate_scale_verified": False,
        "original_gameplay_trace_verified": False,
        "automatic_collision_export_permitted": False,
    }


def audit_private_ipa(ipa: Path, level: str = "MULevel1-1.lvl") -> dict:
    return audit_paired_reports(
        audit_local_ipa(ipa, level, screen=SCREENS[0]),
        audit_local_ipa(ipa, level, screen=SCREENS[1]),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--level", default="MULevel1-1.lvl")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    target = _private_report_path(args.out)
    report = audit_private_ipa(args.ipa, args.level)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Checked two source-private mapFileName reports without exporting geometry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
