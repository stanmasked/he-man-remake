"""Private-only Level1 shape-kind, flag and object-property consistency census.

Links are *exact metadata strings*, not real iOS collider instantiation.
Compare a first-level class -> physics-resource basename -> validated
shape-name chain against the full 409-shape control population and the
typed properties of linked Level1 objects.

No original resource names, property names/values, positions, vertices,
file hashes or shape geometry are exported. Public CI is synthetic only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .level_physics_shape_chains import FIRST_LEVEL, MAX_LEVELS
from .objects import parse_level_objects
from .physics_records import parse_physics_structure
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, MAX_SHAPES,
    PHYSICS_DIR, SHAPE_DIR, _paired,
)
from .shapes import parse_shape

_PROPERTY_KINDS = ("bool", "int", "float", "string")


def _safe_name(name: str, suffix: str) -> bool:
    return (isinstance(name, str) and name.endswith(suffix)
            and len(name) > len(suffix)
            and "/" not in name and "\\" not in name and "\x00" not in name)


def summarize_level1_shape_flags_and_properties(
    level_bytes: bytes,
    physics: dict[str, bytes],
    shapes: dict[str, bytes],
) -> dict:
    """Only aggregate nonidentifying counts; all raw original data stay local."""
    if (type(level_bytes) is not bytes
            or not isinstance(physics, dict) or not isinstance(shapes, dict)
            or not 1 <= len(physics) <= MAX_PHYSICS
            or not 1 <= len(shapes) <= MAX_SHAPES):
        raise ValueError("Missing or excessive private source data")

    level = parse_level_objects(level_bytes)
    if level.level_name != FIRST_LEVEL:
        raise ValueError("Source level embedded name is not first level")

    source_shapes = {}
    for name, raw in shapes.items():
        if not _safe_name(name, ".shape") or type(raw) is not bytes:
            raise ValueError("Unsafe original shape candidate")
        source_shapes[name[:-6]] = parse_shape(raw)

    refs_by_physics = {}
    for name, raw in physics.items():
        if (not isinstance(name, str)
                or not name.endswith((".ps2d", ".pstruct2d"))
                or "/" in name or "\\" in name or "\x00" in name
                or type(raw) is not bytes):
            raise ValueError("Unsafe original physics candidate")
        stem = name.rsplit(".", 1)[0]
        if not stem or stem in refs_by_physics:
            raise ValueError("Ambiguous physical resource filename stem")
        record_file = parse_physics_structure(raw)
        refs_by_physics[stem] = tuple(
            reference for record in record_file.records
            for reference in record.shape_reference_strings
        )

    linked = [obj for obj in level.objects
              if obj.class_name in refs_by_physics]
    linked_physics = {obj.class_name for obj in linked}
    named_references = [
        reference for stem in linked_physics
        for reference in refs_by_physics[stem]
        if reference in source_shapes
    ]
    linked_shape_stems = set(named_references)
    linked_shapes = [source_shapes[stem] for stem in linked_shape_stems]
    library_shapes = list(source_shapes.values())

    property_counter = Counter(
        prop.kind for obj in linked for prop in obj.properties
    )
    if any(kind not in _PROPERTY_KINDS for kind in property_counter):
        raise ValueError("Unsupported source typed property category")
    strings = [
        prop.value for obj in linked for prop in obj.properties
        if prop.kind == "string"
    ]
    if any(not isinstance(value, str) for value in strings):
        raise ValueError("Invalid original typed string value")

    # An embedded shape "reference" string can link to another resource.
    # Compare only literal object labels; no heuristics or inferred owners.
    identities = {
        label for obj in linked
        for label in (obj.class_name, obj.group_name,
                      obj.instance_name, obj.state)
        if label
    }
    shape_ref_texts = [shape.reference for shape in linked_shapes
                       if shape.reference]

    def four_vertex_flag1(shape) -> bool:
        return shape.kind == "polygon" and len(shape.vertices) == 4 and shape.flags == 1

    def identity_linear(matrix) -> bool:
        return (
            len(matrix) == 9 and all(math.isfinite(v) for v in matrix)
            and all(abs(matrix[i] - target) <= 1e-6
                    for i, target in
                    ((0, 1.), (1, 0.), (2, 0.),
                     (3, 0.), (4, 1.), (5, 0.), (8, 1.)))
        )

    return {
        "classification": "private_first_level_linked_shape_flags_and_typed_properties",
        "level1_total_objects": len(level.objects),
        "level1_exact_class_name_matching_physics_instances": len(linked),
        "level1_distinct_matched_physics_resources": len(linked_physics),
        "level1_physics_main_record_valid_shape_name_occurrences":
            len(named_references),
        "level1_distinct_validated_linked_shape_resources":
            len(linked_shapes),
        "level1_linked_polygon_shape_count":
            sum(s.kind == "polygon" for s in linked_shapes),
        "level1_linked_circle_shape_count":
            sum(s.kind == "circle" for s in linked_shapes),
        "level1_linked_four_vertex_polygon_count":
            sum(s.kind == "polygon" and len(s.vertices) == 4
                for s in linked_shapes),
        "level1_linked_shapes_with_flag_exactly_one":
            sum(s.flags == 1 for s in linked_shapes),
        "level1_linked_four_vertex_polygons_with_flag_one":
            sum(four_vertex_flag1(s) for s in linked_shapes),
        "level1_linked_shape_embedded_reference_nonempty":
            len(shape_ref_texts),
        "level1_linked_shape_embedded_reference_exact_object_identity_matches":
            sum(value in identities for value in shape_ref_texts),
        "level1_linked_objects_with_no_typed_properties":
            sum(not obj.properties for obj in linked),
        "level1_linked_objects_with_one_typed_property":
            sum(len(obj.properties) == 1 for obj in linked),
        "level1_linked_objects_with_multiple_typed_properties":
            sum(len(obj.properties) > 1 for obj in linked),
        "level1_linked_typed_bool_property_count": property_counter["bool"],
        "level1_linked_typed_int_property_count": property_counter["int"],
        "level1_linked_typed_float_property_count": property_counter["float"],
        "level1_linked_typed_string_property_count": property_counter["string"],
        "level1_linked_typed_string_values_matching_physics_stems":
            sum(value in refs_by_physics for value in strings),
        "level1_linked_typed_string_values_matching_shape_stems":
            sum(value in source_shapes for value in strings),
        "level1_linked_objects_with_identity_linear_affine_component":
            sum(identity_linear(obj.matrix) for obj in linked),
        "global_validated_shape_resources": len(library_shapes),
        "global_polygon_shape_count":
            sum(shape.kind == "polygon" for shape in library_shapes),
        "global_circle_shape_count":
            sum(shape.kind == "circle" for shape in library_shapes),
        "global_four_vertex_polygons_with_flag_one":
            sum(four_vertex_flag1(shape) for shape in library_shapes),
        "name_matched_class_physics_shape_chain_observed": bool(linked_shapes),
        "original_flag_one_meaning_verified": False,
        "original_shape_embedded_reference_runtime_role_verified": False,
        "typed_string_property_runtime_physics_role_verified": False,
        "original_collision_trigger_sensor_or_material_type_verified": False,
        "original_player_hitbox_or_gameplay_fidelity_verified": False,
        "automatic_switch_collision_import_permitted": False,
        "original_object_names_values_vertices_coords_or_hashes_in_report": False,
    }


def audit_private_level1_shape_flags_and_properties(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA not found")
    with ZipFile(ipa) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("Oversized original source ZIP index")
        index = {m.filename: m for m in members}
        if len(index) != len(members):
            raise ValueError("Duplicate original source ZIP member")
        levels = _paired(archive, index, "levels/", (".lvl",),
                         max_items=MAX_LEVELS)
        physics = _paired(archive, index, PHYSICS_DIR,
                          (".ps2d", ".pstruct2d"), max_items=MAX_PHYSICS)
        shapes = _paired(archive, index, SHAPE_DIR,
                         (".shape",), max_items=MAX_SHAPES)
        if FIRST_LEVEL not in levels:
            raise ValueError("Original first level resource is missing")
        return summarize_level1_shape_flags_and_properties(
            levels[FIRST_LEVEL], physics, shapes
        )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    destination = private_output_path(args.out)
    report = audit_private_level1_shape_flags_and_properties(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n",
                           encoding="utf-8")
    print("Aggregate Level1 shape and object-property census saved privately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
