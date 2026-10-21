"""Read-only, source-private validation of original iOS physics trailer framing.

Observed in the owner's private v2.0.0 IPA: u16 UTF-16 text identifier,
u32 variant discriminator, then opaque byte payload:
  variant 0 => 33 opaque bytes; variant 1 => 25; variant 2 => 34.

All 44 declared items in 13 trailer-bearing sources consume exact EOF.
The discriminator's game *meaning* and payload fields remain UNKNOWN.
Never expose original names, field bytes, coordinates, hashes or paths.
Public CI uses only fabricated test resources.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_opaque_probe import _capture_opaque
from .physics_records import (
    _read_text, MAX_OPAQUE_TAIL_BYTES, MAX_RECORDS,
    PhysicsRecordFormatError,
)
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, PHYSICS_DIR, _paired,
)

# Opaque block sizes exclude the four-byte discriminator.
VARIANT_OPAQUE_SIZES = {0: 33, 1: 25, 2: 34}
_U32 = struct.Struct("<I")


def parse_typed_trailer_counts(trailer: bytes, declared: int) -> dict[int, int]:
    """Validate complete item boundaries; return only type *counts*.

    Model per item: [u16 number-of-UTF16-units][UTF16-LE text]
                    [u32 discriminator][fixed opaque block].
    This does NOT interpret the text or any opaque byte, nor prove the
    discriminator represents a joint type. No source-specific offsets leave.
    """
    if (type(trailer) is not bytes or
            not 1 <= len(trailer) <= MAX_OPAQUE_TAIL_BYTES or
            type(declared) is not int or not 1 <= declared <= MAX_RECORDS):
        raise ValueError("Invalid bounded typed-trailer input")
    position = 0
    tally: Counter[int] = Counter()
    for _ in range(declared):
        _private_label, position = _read_text(trailer, position, allow_empty=True)
        if position + _U32.size > len(trailer):
            raise PhysicsRecordFormatError("Missing trailer variant discriminator")
        variant = _U32.unpack_from(trailer, position)[0]
        position += _U32.size
        if variant not in VARIANT_OPAQUE_SIZES:
            raise PhysicsRecordFormatError("Unrecognized trailer variant")
        size = VARIANT_OPAQUE_SIZES[variant]
        if position + size > len(trailer):
            raise PhysicsRecordFormatError("Truncated typed trailer payload")
        position += size
        tally[variant] += 1
    if position != len(trailer):
        raise PhysicsRecordFormatError("Typed trailer has unconsumed bytes")
    return {variant: tally[variant] for variant in sorted(VARIANT_OPAQUE_SIZES)}


def summarize_typed_trailer_framing(physics: dict[str, bytes]) -> dict:
    """Only fixed, coarse aggregate counters. Never print private names."""
    if (not isinstance(physics, dict) or
            not 1 <= len(physics) <= MAX_PHYSICS):
        raise ValueError("Missing or excessive private physics resources")
    total_items = 0
    trailers = 0
    types: Counter[int] = Counter()
    empty_trailers = 0
    for name, raw in physics.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name or
                type(raw) is not bytes):
            raise ValueError("Invalid private physics source member")
        _opaque, declared, tail = _capture_opaque(raw)
        if not declared:
            empty_trailers += 1
            continue
        item_types = parse_typed_trailer_counts(tail, declared)
        if sum(item_types.values()) != declared:
            raise PhysicsRecordFormatError("Typed trailer item count differs")
        types.update(item_types)
        total_items += declared
        trailers += 1
    if empty_trailers + trailers != len(physics):
        raise ValueError("Typed trailer census size mismatch")
    return {
        "classification": "owner_private_original_physics_trailer_typed_framing",
        "paired_physics_source_files_examined": len(physics),
        "source_files_with_no_trailer": empty_trailers,
        "source_files_with_typed_trailer": trailers,
        "declared_trailer_items_fully_framed": total_items,
        "variant_0_item_count": types[0],
        "variant_1_item_count": types[1],
        "variant_2_item_count": types[2],
        "variant_0_opaque_payload_bytes": VARIANT_OPAQUE_SIZES[0],
        "variant_1_opaque_payload_bytes": VARIANT_OPAQUE_SIZES[1],
        "variant_2_opaque_payload_bytes": VARIANT_OPAQUE_SIZES[2],
        "all_declared_items_reach_exact_tail_end": True,
        "observed_structural_variant_framing_verified": True,
        "discriminator_original_runtime_meaning_verified": False,
        "opaque_variant_payload_fields_decoded": False,
        "previous_main_record_50_byte_payload_fields_decoded": False,
        "original_ios_joint_collider_or_material_semantics_verified": False,
        "original_level1_object_to_shape_ownership_verified": False,
        "original_ios_runtime_gameplay_fidelity_verified": False,
        "safe_for_automatic_switch_geometry_import": False,
        "original_names_bytes_positions_hashes_and_paths_in_report": False,
    }


def audit_private_typed_trailers(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private iOS source archive was not found")
    with ZipFile(ipa) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("Oversized private iOS ZIP index")
        index = {member.filename: member for member in members}
        if len(index) != len(members):
            raise ValueError("Duplicate private ZIP member")
        physics = _paired(archive, index, PHYSICS_DIR,
                          (".ps2d", ".pstruct2d"), max_items=MAX_PHYSICS)
        return summarize_typed_trailer_framing(physics)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    opts = parser.parse_args(argv)
    destination = private_output_path(opts.out)
    report = audit_private_typed_trailers(opts.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n",
                           encoding="utf-8")
    print("Aggregate typed framing verified locally; original bytes stay private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
