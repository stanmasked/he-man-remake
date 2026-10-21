"""Private-only float32 *plausibility* diagnostics for typed physics payloads.

This is NOT a numeric decoder of source physics. Float32 interpretation is
deliberately tested as a falsifiable HYPOTHESIS at all four candidate byte
offsets, both byte orders, with counts only. Plausible values can occur by
chance (notably all-zero bytes); never designate a winning field layout,
original coordinates, collision material, joint, or Switch importer.

Every source resource remains in the owner's IPA outside public GitHub.
CI generates synthetic physics resources only.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_opaque_probe import _capture_opaque
from .physics_records import _read_text, PhysicsRecordFormatError
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, MAX_ITEM_BYTES, PHYSICS_DIR, _paired,
)
from .physics_typed_trailer import (
    VARIANT_OPAQUE_SIZES, parse_typed_trailer_counts,
)

_U32 = struct.Struct("<I")
LOWER_ABS_NORMAL = 1e-8
UPPER_ABS_NORMAL = 1e4
ALIGNMENTS = (0, 1, 2, 3)
BYTE_ORDERS = (("little_endian", "<"), ("big_endian", ">"))


def _typed_payloads(trailer: bytes, declared: int) -> dict[int, list[bytes]]:
    """Use Stage147's STRICT original envelope, then retain payloads locally.

    Return private bytes only to the in-process numeric scanner; public
    reports contain neither payload values nor individual file locations.
    """
    accepted = parse_typed_trailer_counts(trailer, declared)
    output: dict[int, list[bytes]] = {variant: [] for variant in VARIANT_OPAQUE_SIZES}
    at = 0
    for _ in range(declared):
        _private_name, at = _read_text(trailer, at, allow_empty=True)
        variant = _U32.unpack_from(trailer, at)[0]
        at += _U32.size
        size = VARIANT_OPAQUE_SIZES[variant]
        output[variant].append(trailer[at:at+size])
        at += size
    if at != len(trailer):
        raise PhysicsRecordFormatError("Opaque typed payload rewalk did not reach EOF")
    if {k:len(v) for k,v in output.items()} != accepted:
        raise PhysicsRecordFormatError("Opaque typed payload counts diverged")
    return output


def _classify_float32(value: float) -> str:
    """Classify candidate *bits*, never infer an original field type."""
    if not math.isfinite(value):
        return "not_finite"
    if value == 0:
        return "exact_zero"
    magnitude = abs(value)
    if magnitude < LOWER_ABS_NORMAL:
        return "nonzero_below_window"
    if magnitude > UPPER_ABS_NORMAL:
        return "nonzero_above_window"
    return "nonzero_within_window"


def summarize_private_payload_numeric_controls(
    original_physics: dict[str, bytes],
) -> dict:
    if (not isinstance(original_physics, dict) or
            not 1 <= len(original_physics) <= MAX_PHYSICS):
        raise ValueError("Missing or excessive private physics files")
    grouped: dict[int, list[bytes]] = defaultdict(list)
    source_files_with_typed_records = 0
    for name, source in original_physics.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name or
                type(source) is not bytes or
                not 1 <= len(source) <= MAX_ITEM_BYTES):
            raise ValueError("Invalid private physics resource")
        _main_blocks, declared, tail = _capture_opaque(source)
        if not declared:
            continue
        source_files_with_typed_records += 1
        decoded = _typed_payloads(tail, declared)
        for variant, values in decoded.items():
            grouped[variant].extend(values)

    report_variants: dict[str, dict] = {}
    for variant, size in VARIANT_OPAQUE_SIZES.items():
        originals = grouped[variant]
        if not originals:
            raise ValueError("Missing required variant in owner-private comparison")
        if any(len(payload) != size for payload in originals):
            raise ValueError("Unexpected private variant byte length")
        fixed_positions = sum(
            len({payload[i] for payload in originals}) == 1
            for i in range(size)
        )
        controls: dict[str, dict] = {}
        for position in ALIGNMENTS:
            lanes = (size - position) // 4
            if lanes < 1:
                raise ValueError("Not enough bytes for float32 control")
            for order_name, struct_prefix in BYTE_ORDERS:
                tally = {
                    "exact_zero": 0,
                    "nonzero_within_window": 0,
                    "nonzero_below_window": 0,
                    "nonzero_above_window": 0,
                    "not_finite": 0,
                }
                for payload in originals:
                    for lane in range(lanes):
                        value = struct.unpack_from(
                            struct_prefix+"f", payload, position+4*lane
                        )[0]
                        tally[_classify_float32(value)] += 1
                total = len(originals)*lanes
                if sum(tally.values()) != total:
                    raise ValueError("Unaccounted candidate float32 observations")
                controls["offset_"+str(position)+"_"+order_name] = {
                    "candidate_lanes_per_record": lanes,
                    "examined_candidate_float32_bits": total,
                    **tally,
                    "in_heuristic_window_including_zero":
                        tally["exact_zero"] + tally["nonzero_within_window"],
                }
        report_variants["variant_"+str(variant)] = {
            "opaque_payload_byte_count": size,
            "sampled_typed_records": len(originals),
            "distinct_payload_bit_patterns": len(set(originals)),
            "byte_positions_identical_across_variant_records": fixed_positions,
            "byte_positions_varying_across_variant_records": size-fixed_positions,
            "float32_alignment_and_byte_order_controls": controls,
        }
    return {
        "classification": "owner_private_typed_payload_float32_hypothesis_controls",
        "paired_original_physics_files_examined": len(original_physics),
        "source_files_with_typed_record_trailers": source_files_with_typed_records,
        "typed_payload_record_count": sum(len(v) for v in grouped.values()),
        "tested_alignment_offsets": list(ALIGNMENTS),
        "tested_byte_orders": [name for name,_ in BYTE_ORDERS],
        "heuristic_abs_nonzero_lower_bound": LOWER_ABS_NORMAL,
        "heuristic_abs_nonzero_upper_bound": UPPER_ABS_NORMAL,
        "variants": report_variants,
        "heuristic_plausibility_proves_float_field_type": False,
        "byte_alignment_or_endianness_of_original_numeric_fields_verified": False,
        "source_joint_constraint_sensor_material_meaning_verified": False,
        "source_level_one_object_collision_binding_verified": False,
        "original_game_physics_and_switch_runtime_parity_verified": False,
        "automatic_original_geometry_import_permitted": False,
        "original_strings_raw_bytes_coordinates_and_file_hashes_in_report": False,
    }


def audit_private_payload_numeric_controls(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Private original iOS IPA not found")
    with ZipFile(ipa) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_MEMBERS:
            raise ValueError("Private archive index is too large")
        by_name = {e.filename:e for e in entries}
        if len(by_name) != len(entries):
            raise ValueError("Duplicate original archive member")
        sources = _paired(archive, by_name, PHYSICS_DIR,
                          (".ps2d", ".pstruct2d"), max_items=MAX_PHYSICS)
        return summarize_private_payload_numeric_controls(sources)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    output = private_output_path(args.out)
    report = audit_private_payload_numeric_controls(args.ipa)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n",
                      encoding="utf-8")
    print("Private aggregate numeric hypothesis controls saved under local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
