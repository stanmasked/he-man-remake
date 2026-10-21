"""Privacy-safe controls for duplicate and zero-inflated float32 *hypotheses*.

Build on Stage147's strict typed payload envelope and Stage148's
plausibility classification. Compare all four offsets/both endiannesses
both per occurrence and after removing identical whole payloads.
Zero is NEVER counted as positive evidence. Per-lane candidate diversity
is reported only as a count of slots, not source offsets or values.

No original game physics, field types, coordinates or hitbox semantics
are inferred. Source IPA is never used by public CI.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_opaque_probe import _capture_opaque
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, MAX_ITEM_BYTES, PHYSICS_DIR, _paired,
)
from .physics_payload_numeric_controls import (
    ALIGNMENTS, BYTE_ORDERS, LOWER_ABS_NORMAL, UPPER_ABS_NORMAL,
    _classify_float32, _typed_payloads,
)
from .physics_typed_trailer import VARIANT_OPAQUE_SIZES

_CATEGORIES = (
    "exact_zero", "nonzero_within_window", "nonzero_below_window",
    "nonzero_above_window", "not_finite",
)


def numeric_candidate_summary(blocks: list[bytes], *, offset: int,
                              endian: str) -> dict:
    """Count candidate bit-interpretation categories; never return raw floats.

    A lane is *informative* only if at least one payload carries an
    in-window NONZERO value there. It is *diverse* only if there are two
    different such candidate values. This is a statistical diagnostic,
    not a source field-layout declaration.
    """
    if (not isinstance(blocks, list) or not blocks
            or any(type(b) is not bytes for b in blocks)
            or type(offset) is not int or offset not in ALIGNMENTS
            or endian not in ("<", ">")):
        raise ValueError("Invalid bounded candidate payload sample")
    size = len(blocks[0])
    if not 4 <= size <= 64 or any(len(b) != size for b in blocks):
        raise ValueError("Mismatched or invalid opaque payload sizes")
    lanes = (size - offset) // 4
    if lanes < 1:
        raise ValueError("No complete float32 candidate lanes")

    totals = {name:0 for name in _CATEGORIES}
    lanes_with_nonzero = 0
    lanes_with_diverse_nonzero = 0
    for lane in range(lanes):
        qualifying_bits = set()
        for payload in blocks:
            start = offset + 4 * lane
            value = struct.unpack_from(endian+"f", payload, start)[0]
            classification = _classify_float32(value)
            totals[classification] += 1
            if classification == "nonzero_within_window":
                qualifying_bits.add(payload[start:start+4])
        lanes_with_nonzero += bool(qualifying_bits)
        lanes_with_diverse_nonzero += len(qualifying_bits) >= 2

    if sum(totals.values()) != len(blocks) * lanes:
        raise ValueError("Unaccounted numeric candidate lanes")
    return {
        "sampled_payloads": len(blocks),
        "candidate_lanes_per_payload": lanes,
        "total_candidate_bit_interpretations": len(blocks)*lanes,
        **totals,
        "lanes_with_any_nonzero_in_heuristic_window": lanes_with_nonzero,
        "lanes_with_distinct_nonzero_in_heuristic_window":
            lanes_with_diverse_nonzero,
    }


def summarize_duplicate_aware_numeric_controls(
    original_physics: dict[str, bytes]
) -> dict:
    if (not isinstance(original_physics, dict)
            or not 1 <= len(original_physics) <= MAX_PHYSICS):
        raise ValueError("Missing or excessive private physics files")
    typed: dict[int, list[bytes]] = defaultdict(list)
    bearing_trailers = 0
    for name, contents in original_physics.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name
                or type(contents) is not bytes
                or not 1 <= len(contents) <= MAX_ITEM_BYTES):
            raise ValueError("Invalid private physics resource")
        _main, declared, trailer = _capture_opaque(contents)
        if not declared:
            continue
        bearing_trailers += 1
        parsed = _typed_payloads(trailer, declared)
        for variant, values in parsed.items():
            typed[variant].extend(values)

    by_variant = {}
    for variant, expected_size in VARIANT_OPAQUE_SIZES.items():
        occurrences = typed[variant]
        if not occurrences or any(len(x) != expected_size for x in occurrences):
            raise ValueError("Missing or malformed original variant sample")
        # Dict keys preserve insertion order; all private byte keys remain
        # local and are NEVER placed in the public JSON summary.
        unique = list(dict.fromkeys(occurrences))
        comparisons = {}
        for offset in ALIGNMENTS:
            for name, endianness in BYTE_ORDERS:
                key = "offset_"+str(offset)+"_"+name
                comparisons[key] = {
                    "all_record_occurrences": numeric_candidate_summary(
                        occurrences, offset=offset, endian=endianness
                    ),
                    "distinct_payload_patterns_only": numeric_candidate_summary(
                        unique, offset=offset, endian=endianness
                    ),
                }
        le1 = comparisons["offset_1_little_endian"][
            "distinct_payload_patterns_only"]["nonzero_within_window"]
        be0 = comparisons["offset_0_big_endian"][
            "distinct_payload_patterns_only"]["nonzero_within_window"]
        by_variant["variant_"+str(variant)] = {
            "opaque_bytes_per_record": expected_size,
            "total_record_occurrences": len(occurrences),
            "distinct_payload_patterns": len(unique),
            "duplicate_record_occurrences": len(occurrences)-len(unique),
            "comparisons": comparisons,
            "deduplicated_nonzero_le_offset_1_minus_be_offset_0": le1-be0,
            "difference_is_not_field_identification": True,
        }
    return {
        "classification": "private_opaque_physics_duplicate_aware_float32_controls",
        "original_physics_source_files_examined": len(original_physics),
        "physics_files_with_typed_trailer": bearing_trailers,
        "typed_trailer_record_count": sum(map(len, typed.values())),
        "heuristic_nonzero_magnitude_lower": LOWER_ABS_NORMAL,
        "heuristic_nonzero_magnitude_upper": UPPER_ABS_NORMAL,
        "alignment_offsets_checked": list(ALIGNMENTS),
        "byte_orders_checked": [x for x, _ in BYTE_ORDERS],
        "variants": by_variant,
        "zero_is_never_positive_numeric_evidence": True,
        "repeated_identical_payloads_count_once_in_deduplicated_controls": True,
        "original_float32_numeric_field_layout_verified": False,
        "original_coordinate_or_joint_meaning_verified": False,
        "source_object_to_shape_collision_binding_verified": False,
        "original_ios_gameplay_or_switch_hardware_parity_verified": False,
        "allow_automatic_original_geometry_import": False,
        "source_payload_bytes_string_names_offsets_hashes_in_report": False,
    }


def audit_private_duplicate_aware_numeric_controls(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA not found")
    with ZipFile(ipa) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_MEMBERS:
            raise ValueError("Excessive private ZIP archive index")
        by_name = {entry.filename:entry for entry in entries}
        if len(by_name) != len(entries):
            raise ValueError("Duplicate ZIP archive member")
        sources = _paired(archive, by_name, PHYSICS_DIR,
                          (".ps2d", ".pstruct2d"), max_items=MAX_PHYSICS)
        return summarize_duplicate_aware_numeric_controls(sources)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    opts = ap.parse_args(argv)
    target = private_output_path(opts.out)
    summary = audit_private_duplicate_aware_numeric_controls(opts.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, sort_keys=True, indent=2)+"\n",
                      encoding="utf-8")
    print("Private aggregate numeric controls saved to ignored local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
