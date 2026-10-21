"""Private-only exact-name level-object -> physics -> shape *resource chain*.

This is stronger evidence than inferring float32 physics fields, but it
remains file metadata, not runtime link resolution. Class-name equality
with a physics resource stem and a physics reference string equality
with a validated shape stem are distinct, separately counted signals.

Never disclose source names, coordinates, shape vertices, individual
object placements, geometry assets or source hashes. All CI fixtures
are synthetic, and all original IPA inspection stays owner-private.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .objects import parse_level_objects
from .physics_records import parse_physics_structure
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, MAX_SHAPES,
    PHYSICS_DIR, SHAPE_DIR, _paired,
)
from .shapes import parse_shape

LEVEL_DIR = "levels/"
MAX_LEVELS = 256
FIRST_LEVEL = "MULevel1-1.lvl"


def summarize_level_physics_shape_chains(
    level_data: dict[str, bytes],
    physics_data: dict[str, bytes],
    shape_data: dict[str, bytes],
) -> dict:
    """Only summary counters return; all original resource IDs stay local.

    Exact full name matches, never substring or fuzzy matching:
      .lvl LevelObject.class_name == basename(.ps2d or .pstruct2d)
      physics main-record string == basename(.shape)
    These are *resource-reference candidates*, not proof that original
    iOS execution creates colliders or attaches these shapes to actors.
    """
    if (not all(isinstance(x, dict) for x in (level_data, physics_data, shape_data))
            or not 1 <= len(level_data) <= MAX_LEVELS
            or not 1 <= len(physics_data) <= MAX_PHYSICS
            or not 1 <= len(shape_data) <= MAX_SHAPES):
        raise ValueError("Missing or oversized original source resource group")

    shape_stems = set()
    for name, raw in shape_data.items():
        if (not isinstance(name,str) or not name.endswith(".shape")
                or len(name) <= 6 or "/" in name or "\\" in name
                or type(raw) is not bytes):
            raise ValueError("Unsafe original shape resource label")
        parse_shape(raw)   # Validate exact source shape structure privately.
        shape_stems.add(name[:-6])

    physical_references: dict[str, tuple[str, ...]] = {}
    for name, raw in physics_data.items():
        if (not isinstance(name,str)
                or not name.endswith((".ps2d",".pstruct2d"))
                or "/" in name or "\\" in name or type(raw) is not bytes):
            raise ValueError("Unsafe original physics resource label")
        stem = name.rsplit(".", 1)[0]
        if not stem or stem in physical_references:
            raise ValueError("Ambiguous original physics resource basename")
        decoded = parse_physics_structure(raw)
        physical_references[stem] = tuple(
            ref for record in decoded.records
            for ref in record.shape_reference_strings
        )

    # Count only observed class-name matches, never implicit string
    # properties, unqualified names or references found in opaque bytes.
    total_objects = linked_instances = chain_instances = 0
    levels_with_match = 0
    levels_with_complete_chain = 0
    used_stems: set[str] = set()
    used_chain_stems: set[str] = set()
    first = None
    for name, raw in level_data.items():
        if (not isinstance(name,str) or not name.endswith(".lvl")
                or "/" in name or "\\" in name or type(raw) is not bytes):
            raise ValueError("Unsafe original level source label")
        level = parse_level_objects(raw)
        if level.level_name != name:
            raise ValueError("Original level embedded name does not match resource")
        total_objects += len(level.objects)
        class_matches = [
            obj.class_name for obj in level.objects
            if obj.class_name in physical_references
        ]
        chained_matches = [
            stem for stem in class_matches
            if any(ref in shape_stems for ref in physical_references[stem])
        ]
        linked_instances += len(class_matches)
        chain_instances += len(chained_matches)
        levels_with_match += bool(class_matches)
        levels_with_complete_chain += bool(chained_matches)
        used_stems.update(class_matches)
        used_chain_stems.update(chained_matches)
        if name == FIRST_LEVEL:
            local_stems = set(class_matches)
            local_shape_refs = [
                ref for stem in local_stems
                for ref in physical_references[stem]
                if ref in shape_stems
            ]
            first = {
                "source_objects": len(level.objects),
                "objects_with_exact_class_name_physics_resource_stem": len(class_matches),
                "distinct_matching_physics_resources": len(local_stems),
                "objects_with_class_physics_shape_name_chain": len(chained_matches),
                "validated_shape_name_reference_occurrences": len(local_shape_refs),
                "distinct_shape_names_in_completed_local_chains": len(set(local_shape_refs)),
            }

    if first is None:
        raise ValueError("Required first level is absent in owner-private source")
    distinct_used_shape_refs = [
        ref for stem in used_stems for ref in physical_references[stem]
        if ref in shape_stems
    ]
    used_physics_with_shape = sum(
        any(ref in shape_stems for ref in physical_references[stem])
        for stem in used_stems
    )
    if not (chain_instances <= linked_instances <= total_objects and
            used_physics_with_shape <= len(used_stems)):
        raise ValueError("Inconsistent original cross-resource chain counts")

    return {
        "classification": "owner_private_original_level_physics_shape_exact_name_chains",
        "paired_original_levels_examined": len(level_data),
        "paired_original_physics_resources_examined": len(physics_data),
        "paired_original_shape_resources_validated": len(shape_data),
        "original_level_object_instances_decoded": total_objects,
        "levels_with_exact_class_name_physics_resource_stem": levels_with_match,
        "level_objects_with_exact_class_name_physics_resource_stem": linked_instances,
        "distinct_matched_physics_resource_stems": len(used_stems),
        "levels_with_complete_class_physics_shape_name_chain": levels_with_complete_chain,
        "level_objects_with_complete_class_physics_shape_name_chain": chain_instances,
        "physics_resources_with_at_least_one_valid_shape_name_match": used_physics_with_shape,
        "matched_physics_main_record_shape_name_occurrences": len(distinct_used_shape_refs),
        "distinct_validated_shape_names_referenced_in_chains": len(set(distinct_used_shape_refs)),
        "first_level": first,
        "original_source_resolution_packs_byte_identical": True,
        "class_name_and_shape_name_exact_matches_are_verified": True,
        "game_engine_runtime_resource_bindings_verified": False,
        "original_collision_body_shape_ownership_verified": False,
        "player_hitbox_sensors_materials_or_physics_verified": False,
        "original_ios_to_switch_gameplay_parity_verified": False,
        "safe_for_automatic_original_collision_import": False,
        "original_names_coordinates_shapes_pixels_or_hashes_in_output": False,
    }


def audit_private_level_physics_shape_chains(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original iOS archive not found")
    with ZipFile(ipa) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_MEMBERS:
            raise ValueError("Original ZIP index beyond fixed safety limit")
        index = {e.filename:e for e in entries}
        if len(index) != len(entries):
            raise ValueError("Duplicate original iOS ZIP member")
        levels = _paired(archive,index,LEVEL_DIR,(".lvl",),
                         max_items=MAX_LEVELS)
        physics = _paired(archive,index,PHYSICS_DIR,(".ps2d",".pstruct2d"),
                          max_items=MAX_PHYSICS)
        shapes = _paired(archive,index,SHAPE_DIR,(".shape",),
                         max_items=MAX_SHAPES)
        return summarize_level_physics_shape_chains(levels, physics, shapes)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    out=private_output_path(args.out)
    report=audit_private_level_physics_shape_chains(args.ipa)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",
                   encoding="utf-8")
    print("Source-only aggregate class->physics->shape name census saved privately.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
