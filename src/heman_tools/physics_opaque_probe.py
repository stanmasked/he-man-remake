"""Private-only evidence on unknown physics payloads, no guessed field meaning.

The 50-byte sections and nonzero trailers remain OPAQUE. First-tail
length-prefixed UTF-16 is only a candidate prefix, never a proven
complete linked group format. Published counts contain no original
coordinates, strings, bytes, names, offsets or hashes.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, PHYSICS_DIR, _paired
)
from .physics_records import (
    _FIXED_OPAQUE_BYTES, _read_text, parse_physics_structure,
    PhysicsRecordFormatError
)

_U32 = struct.Struct("<I")


def _capture_opaque(data: bytes) -> tuple[list[bytes], int, bytes]:
    """Re-walk an already validated envelope; never expose bytes in report."""
    parsed = parse_physics_structure(data)
    cursor = 4
    blocks = []
    for expected in parsed.records:
        label, cursor = _read_text(data, cursor, allow_empty=True)
        if label != expected.label:
            raise PhysicsRecordFormatError("Inconsistent source label")
        block = data[cursor:cursor + _FIXED_OPAQUE_BYTES]
        if len(block) != _FIXED_OPAQUE_BYTES:
            raise PhysicsRecordFormatError("Incomplete opaque record")
        blocks.append(block)
        cursor += _FIXED_OPAQUE_BYTES
        count = _U32.unpack_from(data, cursor)[0]
        cursor += 4
        actual_refs = []
        for _ in range(count):
            reference, cursor = _read_text(data, cursor, allow_empty=False)
            actual_refs.append(reference)
        if tuple(actual_refs) != expected.shape_reference_strings:
            raise PhysicsRecordFormatError("Inconsistent private references")
    groups = _U32.unpack_from(data, cursor)[0]
    cursor += 4
    trailer = data[cursor:]
    if (groups != parsed.trailing_group_count or
            len(trailer) != parsed.trailing_opaque_bytes):
        raise PhysicsRecordFormatError("Inconsistent opaque trailer")
    return blocks, groups, trailer


def _candidate_first_utf16(trailer: bytes) -> tuple[bool, bool]:
    """Can the *beginning* be one valid u16-length UTF16? Not a group parser."""
    if len(trailer) < 2:
        return False, False
    try:
        value, end = _read_text(trailer, 0, allow_empty=True)
    except PhysicsRecordFormatError:
        return False, False
    # The actual group record remains unknown beyond this initial token.
    return (end <= len(trailer), len(value) == 0)


def summarize_opaque_parameter_evidence(
    sources: dict[str, bytes]
) -> dict:
    """Only fixed aggregate counters, NEVER individual record data or names."""
    if not isinstance(sources, dict) or not 1 <= len(sources) <= MAX_PHYSICS:
        raise ValueError("Missing or excessive source physics files")
    blocks = []
    nonempty_count = total_groups = total_tail_bytes = 0
    possible_start = empty_initial_labels = 0
    smallest_tail, largest_tail = None, None
    for name, raw in sources.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name or
                not isinstance(raw, bytes)):
            raise ValueError("Invalid private physics source member")
        current, count, tail = _capture_opaque(raw)
        blocks.extend(current)
        if count:
            nonempty_count += 1
            total_groups += count
            total_tail_bytes += len(tail)
            smallest_tail = len(tail) if smallest_tail is None else min(smallest_tail, len(tail))
            largest_tail = len(tail) if largest_tail is None else max(largest_tail, len(tail))
            valid_prefix, empty = _candidate_first_utf16(tail)
            possible_start += valid_prefix
            empty_initial_labels += valid_prefix and empty

    if not blocks:
        raise ValueError("No source physics parameter blocks")
    varied_offsets = sum(
        len({block[position] for block in blocks}) > 1
        for position in range(_FIXED_OPAQUE_BYTES)
    )
    return {
        "classification": "owner_private_opaque_physics_statistical_evidence",
        "physics_resources_examined": len(sources),
        "opaque_50_byte_blocks_examined": len(blocks),
        "distinct_50_byte_block_patterns": len(set(blocks)),
        "50_byte_positions_varying_across_records": varied_offsets,
        "50_byte_positions_constant_across_records": _FIXED_OPAQUE_BYTES-varied_offsets,
        "50_byte_blocks_entirely_zero": sum(not any(block) for block in blocks),
        "resources_with_nonzero_trailer_count": nonempty_count,
        "declared_unknown_trailer_group_total": total_groups,
        "total_nonzero_trailer_bytes": total_tail_bytes,
        "minimum_nonzero_trailer_bytes": smallest_tail or 0,
        "maximum_nonzero_trailer_bytes": largest_tail or 0,
        "nonzero_trailers_with_candidate_initial_utf16_prefix": possible_start,
        "candidate_initial_utf16_labels_empty": empty_initial_labels,
        "candidate_initial_utf16_labels_nonempty": possible_start-empty_initial_labels,
        "unknown_trailer_group_record_boundaries_decoded": False,
        "opaque_50_byte_parameter_fields_decoded": False,
        "source_runtime_physics_semantics_verified": False,
        "level1_shape_ownership_verified": False,
        "switch_collision_import_allowed": False,
        "original_source_strings_payloads_and_offsets_in_report": False,
    }


def audit_private_physics_opaque(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner private original IPA missing")
    with ZipFile(ipa) as archive:
        index_list = archive.infolist()
        if len(index_list) > MAX_MEMBERS:
            raise ValueError("Oversized source ZIP index")
        by_name = {item.filename: item for item in index_list}
        if len(by_name) != len(index_list):
            raise ValueError("Duplicate ZIP member")
        sources = _paired(
            archive, by_name, PHYSICS_DIR, (".ps2d", ".pstruct2d"),
            max_items=MAX_PHYSICS
        )
        return summarize_opaque_parameter_evidence(sources)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    target = private_output_path(args.out)
    report = audit_private_physics_opaque(args.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n",
                      encoding="utf-8")
    print("Opaque physics source aggregate privately recorded in local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
