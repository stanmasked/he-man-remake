"""Local-only Level 1-1 source-readiness gate, assembled from existing parsers.

Do NOT export copyrighted geometry, object identities, per-tile positions,
point coordinates, texture names, filenames of source-linked resources, or
the owner's full IPA. These aggregate structural checks DO NOT grant permission
to use an original iOS map as a working collision model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

from .collision_components import inspect_private_pair
from .collision_inventory import private_output_path
from .first_level_pair_audit import compare_pair
from .objects import parse_level_objects
from .paired_mapfile_links import audit_private_ipa as audit_paired_links
from .waypoints import parse_waypoints

LEVEL = "MULevel1-1.lvl"
MAP = "MUMap1-1.map"
ZIP_LEVEL = "Payload/MOTU.app/screen-med/levels/" + LEVEL
MAX_LEVEL_BYTES = 8_000_000

# Only fixed, public meaning of blockers, never release a private map name
# or any individual geometry location.
KNOWN_STRUCTURAL_CHECKS = (
    "identical_level_and_map_bytes",
    "explicit_map_reference_candidates_cross_pack",
    "collision_layer_occupancy_topology_cross_pack",
    "full_level_object_table_parses",
    "named_point_group_links_parse",
)
RUNTIME_UNVERIFIED = (
    "original_collision_material_semantics",
    "original_sprite_shape_owner_matching",
    "object_to_tile_coordinate_transform",
    "moving_platform_one_way_slope_rules",
    "original_enemy_ai_damage_and_camera_trace",
    "original_ios_capture_or_reliable_trace",
    "physical_switch_collision_and_frame_pacing",
)


def _count(value: object, name: str, limit: int = 100000) -> int:
    if type(value) is not int or not 0 <= value <= limit:
        raise ValueError("invalid aggregate structural counter: " + name)
    return value


def summarize_level1_readiness(
    pair: dict, links: dict, topology: dict, object_count: int,
    named_groups: int, points: int, point_links: int,
) -> dict:
    """Return counts and fixed booleans only; no source-owned coordinates."""
    if not all(isinstance(r, dict) for r in (pair, links, topology)):
        raise ValueError("missing structural source reports")
    if (pair.get("level") != LEVEL or pair.get("candidate_map") != MAP or
            links.get("level") != LEVEL or topology.get("map") != MAP):
        raise ValueError("inconsistent first-level source identity")
    for key in ("level_to_map_binding_verified", "collision_type_verified",
                "original_gameplay_trace_verified", "automatic_collision_export_permitted"):
        if pair.get(key) is not False:
            raise ValueError("unverified original iOS assertion in source pair")
    for key in ("runtime_map_binding_verified", "collision_semantics_verified",
                "coordinate_scale_verified", "original_gameplay_trace_verified",
                "automatic_collision_export_permitted"):
        if links.get(key) is not False:
            raise ValueError("unverified original source-level map association")
    if (topology.get("runtime_collision_type_verified") is not False or
            topology.get("automatic_collision_export_permitted") is not False or
            topology.get("screen_packs") != ["screen-med", "screen-xlarge"]):
        raise ValueError("invalid collision topology source or runtime assertion")
    level_pair = pair.get("selected_pairs")
    if not isinstance(level_pair, dict):
        raise ValueError("missing original resource file-pair evidence")
    if not isinstance(links.get("structural_blockers"), list):
        raise ValueError("missing structural blockers")
    screen_data = topology.get("screens")
    if not isinstance(screen_data, dict) or set(screen_data) != {"screen-med", "screen-xlarge"}:
        raise ValueError("missing both original collision topology inventories")
    med, large = screen_data["screen-med"], screen_data["screen-xlarge"]
    if not isinstance(med, dict) or not isinstance(large, dict):
        raise ValueError("bad collision topology schema")
    for src in (med, large):
        for label in ("collision_categories_verified", "coordinate_alignment_verified",
                      "original_gameplay_physics_verified", "automatic_collision_export_permitted"):
            if src.get(label) is not False:
                raise ValueError("original collision semantics not established")
    count_objects = _count(object_count, "objects")
    count_groups = _count(named_groups, "named_groups")
    count_points = _count(points, "points")
    count_edges = _count(point_links, "point_links")
    cells = _count(med.get("occupied_cells"), "occupied_cells")
    components = _count(med.get("component_count_4_connected"), "components")
    if count_edges and not count_points:
        raise ValueError("link count without path points")
    if components > cells:
        raise ValueError("topology component count exceeds occupied cells")
    if (links.get("structural_blockers") and
            not all(isinstance(s, str) for s in links["structural_blockers"])):
        raise ValueError("malformed private structural blocker")
    checks = {
        "identical_level_and_map_bytes": (
            pair.get("cross_pack_bytes_identical") is True
            and isinstance(level_pair.get("level"), dict)
            and level_pair["level"].get("exact_bytes_equal") is True
            and isinstance(level_pair.get("map"), dict)
            and level_pair["map"].get("exact_bytes_equal") is True
        ),
        "explicit_map_reference_candidates_cross_pack": (
            links.get("cross_pack_candidate_consistency") is True
            and links.get("cross_pack_selected_bytes_identical") is True
            and not links["structural_blockers"]
            and set(links.get("candidate_links", {}))
                == {"LevelTileMap", "LevelTileMapOverlay"}
        ),
        "collision_layer_occupancy_topology_cross_pack": (
            topology.get("source_map_bytes_identical") is True
            and topology.get("derived_topology_identical") is True
            and med.get("occupied_cells") == large.get("occupied_cells")
            and med.get("component_count_4_connected") == large.get("component_count_4_connected")
        ),
        "full_level_object_table_parses": True,
        "named_point_group_links_parse": True,
    }
    if set(checks) != set(KNOWN_STRUCTURAL_CHECKS):
        raise ValueError("source readiness check schema drift")
    return {
        "classification": "private_first_level_structural_readiness_only",
        "source": "owner_private_ios_v2_level1_1",
        "aggregate_counts": {
            "level_objects": count_objects,
            "named_path_groups": count_groups,
            "path_points": count_points,
            "path_link_references": count_edges,
            "candidate_collision_occupied_cells": cells,
            "four_connected_occupancy_components": components,
        },
        "structural_checks": checks,
        "structural_checks_passed": sum(checks.values()),
        "structural_checks_total": len(checks),
        "blocker_counts": {
            "structural": sum(not v for v in checks.values()),
            "unverified_runtime_semantics": len(RUNTIME_UNVERIFIED),
        },
        "remaining_runtime_questions": list(RUNTIME_UNVERIFIED),
        "ready_for_automatic_collision_import": False,
        "real_ios_gameplay_fidelity_verified": False,
        "actual_switch_hardware_tested": False,
        "private_coordinates_in_output": False,
        "source_resource_names_or_hashes_in_output": False,
        "original_game_bytes_in_output": False,
    }


def audit_private_first_level(ipa: Path) -> dict:
    """Only original owner-local ZIP reads; never writes or extracts an asset."""
    if not ipa.is_file():
        raise ValueError("Missing privately held original IPA")
    paired = compare_pair(ipa, LEVEL, MAP)
    links = audit_paired_links(ipa, LEVEL)
    topology = inspect_private_pair(ipa, MAP)
    with zipfile.ZipFile(ipa, "r") as z:
        matches = [a for a in z.infolist() if a.filename == ZIP_LEVEL]
        if len(matches) != 1 or matches[0].flag_bits & 1 or (
                not 32 <= matches[0].file_size <= MAX_LEVEL_BYTES
        ):
            raise ValueError("Unsafe or missing source first-level descriptor")
        info = matches[0]
        if info.is_dir():
            raise ValueError("Source first-level member is a directory")
        raw = z.read(info)
    objects = parse_level_objects(raw)
    points = parse_waypoints(raw)
    if objects.level_name != LEVEL or points.level_name != LEVEL:
        raise ValueError("Unexpected source level identity")
    return summarize_level1_readiness(
        paired, links, topology, len(objects.objects),
        len(points.groups), points.total_points, points.total_links
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ipa", required=True, type=Path,
                   help="Original IPA stored privately, never uploaded")
    p.add_argument("--out", required=True, type=Path,
                   help="Ignored local_reports/ JSON, never a public artifact")
    args = p.parse_args(argv)
    out = private_output_path(args.out)
    result = audit_private_first_level(args.ipa)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("First original level structure checked privately; only aggregate blockers and counts saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
