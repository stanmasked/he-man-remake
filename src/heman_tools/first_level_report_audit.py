"""Cross-check three private reports before first-level geometry review.

No source IPA/maps/images are loaded here, and no game physics or object
ownership is inferred. Contradictory report identities fail closed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .frame_alignment import _private_path

_MAX_REPORT_BYTES = 1_000_000
_MAX_RECORDS = 4096
_STATUSES = ("no_exact_candidate", "one_candidate_only",
             "ambiguous_multiple_candidates")


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > 100_000_000:
        raise ValueError(f"{label} must be a bounded integer")
    return value


def _name(value: object, suffix: str, label: str) -> str:
    if (not isinstance(value, str) or len(value) <= len(suffix)
            or not value.endswith(suffix) or len(value) > 512
            or "/" in value or "\\" in value or not value.isprintable()):
        raise ValueError(f"{label} must be one simple {suffix} filename")
    return value


def audit_level_report_consistency(links: dict, shapes: dict,
                                   collision: dict) -> dict:
    """Check internal consistency and explicit candidate links only.

    A valid report *never* promotes a collision mask. A single textual link
    remains unverified original-game behavior.
    """
    if any(not isinstance(v, dict) for v in (links, shapes, collision)):
        raise ValueError("all inputs must be report JSON objects")
    level = _name(links.get("level"), ".lvl", "level")
    if shapes.get("level") != level:
        raise ValueError("shape report belongs to a different level")
    screen = links.get("screen")
    if screen not in ("screen-med", "screen-xlarge"):
        raise ValueError("invalid map-link screen")
    if collision.get("screen") != screen:
        raise ValueError("collision inventory uses a different screen pack")
    if collision.get("layer") != "collision":
        raise ValueError("collision inventory does not identify the collision layer")
    if links.get("map_binding_confirmed") is not False:
        raise ValueError("map links must remain unverified candidates")
    if links.get("real_game_object_link_confirmed") is not False:
        raise ValueError("real-game object links must remain unverified")
    if shapes.get("ownership_confirmed") is not False:
        raise ValueError("shape ownership is not independently verified")

    map_name = _name(collision.get("map"), ".map", "collision map")
    map_rows = links.get("map_objects")
    structures = links.get("candidate_map_structures")
    shape_rows = shapes.get("shapes")
    status_counts = shapes.get("status_counts")
    if (not isinstance(map_rows, list) or not isinstance(structures, list)
            or not isinstance(shape_rows, list) or not isinstance(status_counts, dict)
            or len(map_rows) > _MAX_RECORDS
            or len(structures) > _MAX_RECORDS
            or len(shape_rows) > _MAX_RECORDS):
        raise ValueError("missing or oversized candidate report collections")
    if _integer(links.get("map_object_count"), "map_object_count") != len(map_rows):
        raise ValueError("map object count differs from data")
    if _integer(shapes.get("shape_count"), "shape_count") != len(shape_rows):
        raise ValueError("shape count differs from data")
    if _integer(shapes.get("object_count"), "object_count") < len(map_rows):
        raise ValueError("shape report object count is less than map objects")

    shape_counts = {key: _integer(status_counts.get(key), key)
                    for key in _STATUSES}
    if sum(shape_counts.values()) != len(shape_rows):
        raise ValueError("shape candidate status totals inconsistent")
    observed = {key: 0 for key in _STATUSES}
    for entry in shape_rows:
        if not isinstance(entry, dict):
            raise ValueError("invalid shape candidate row")
        status = entry.get("candidate_status")
        if status not in observed:
            raise ValueError("invalid shape candidate status")
        observed[status] += 1
    if observed != shape_counts:
        raise ValueError("shape candidate statuses do not match report summary")

    relevant = []
    for record in structures:
        if not isinstance(record, dict):
            raise ValueError("invalid candidate map summary")
        if record.get("filename") == map_name:
            relevant.append(record)
    if len(relevant) != 1:
        raise ValueError("selected collision map requires exactly one structure")

    references = []
    seen_indices = set()
    for row in map_rows:
        if not isinstance(row, dict) or not isinstance(row.get("candidate_maps"), list):
            raise ValueError("invalid map-object record")
        index = _integer(row.get("object_index"), "object_index")
        if index in seen_indices:
            raise ValueError("duplicate map object index")
        seen_indices.add(index)
        cand = row["candidate_maps"]
        status = ("no_exact_candidate" if not cand else
                  "one_exact_candidate" if len(cand) == 1 else
                  "ambiguous_multiple_candidates")
        if row.get("candidate_status") != status:
            raise ValueError("map-object status mismatches candidates")
        if (status == "one_exact_candidate"
                and isinstance(cand[0], dict)
                and cand[0].get("filename") == map_name):
            references.append(index)

    layer = relevant[0]
    layer_occurrences = _integer(layer.get("collision_layer_name_occurrences"),
                                 "collision_layer_name_occurrences")
    if layer.get("unique_named_collision_layer") is not (layer_occurrences == 1):
        raise ValueError("candidate map collision layer flag is contradictory")

    occupied = _integer(collision.get("occupied_cells"), "occupied_cells")
    empty = _integer(collision.get("empty_cells"), "empty_cells")
    columns = _integer(collision.get("columns"), "columns", minimum=1)
    rows = _integer(collision.get("rows"), "rows", minimum=1)
    if occupied + empty != columns * rows:
        raise ValueError("collision cell counts mismatch grid dimensions")
    if len(references) != 1 or layer_occurrences != 1:
        blockers = []
        if len(references) != 1:
            blockers.append("selected_map_lacks_one_unique_text_reference")
        if layer_occurrences != 1:
            blockers.append("selected_map_lacks_one_collision_layer")
    else:
        blockers = []
    blockers.extend(("shape_ownership_unverified",
                     "tile_collision_semantics_unverified",
                     "original_gameplay_trace_not_crosschecked"))
    return {
        "level": level,
        "screen": screen,
        "candidate_map": map_name,
        "single_exact_text_reference": len(references) == 1,
        "one_named_collision_layer": layer_occurrences == 1,
        "occupied_candidate_cells": occupied,
        "total_shape_definitions": len(shape_rows),
        "shape_candidates_without_exact_match":
            shape_counts["no_exact_candidate"],
        "shape_candidates_ambiguous":
            shape_counts["ambiguous_multiple_candidates"],
        "unresolved_requirements": blockers,
        "authentic_collision_verified": False,
        "automatic_collision_export_permitted": False,
        "interpretation": (
            "Internal consistency of private reports only. No proof of "
            "authentic source-game map ownership, geometry or collision."
        ),
    }


def _read_private_report(path: Path) -> dict:
    target = _private_path(path)
    if target.stat().st_size > _MAX_REPORT_BYTES:
        raise ValueError("private report exceeds 1 MB")
    return json.loads(target.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", required=True, type=Path)
    parser.add_argument("--shapes", required=True, type=Path)
    parser.add_argument("--collision", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    output = _private_path(args.out)
    sources = [_private_path(p) for p in
               (args.links, args.shapes, args.collision)]
    if output in sources or len(set(sources)) != 3:
        raise ValueError("report sources and output must be different files")
    summary = audit_level_report_consistency(
        *(_read_private_report(p) for p in sources))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print("Cross-report first-level evidence audited privately; "
          "no collision export performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
