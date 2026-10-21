"""Bounded read-only decoder for the observed .ps2d/.pstruct2d record envelope.

Evidence only: a record's 50-byte payload and any nonzero-count trailer
remain OPAQUE. Text references are source strings, not proof of physical
shape ownership, hitbox type, gameplay semantics or runtime linking.

The owner's original IPA must never be uploaded to public CI.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import struct
from pathlib import Path

from .collision_inventory import private_output_path
from .physics_shape_census import (
    PREFIX, SCREENS, SHAPE_DIR, PHYSICS_DIR, MAX_MEMBERS,
    MAX_SHAPES, MAX_PHYSICS, _paired,
)
from .shapes import parse_shape
from zipfile import ZipFile

MAX_FILE_BYTES = 1_000_000
MAX_RECORDS = 512
MAX_REFERENCES_PER_RECORD = 64
MAX_TEXT_UNITS = 512
MAX_OPAQUE_TAIL_BYTES = 8192
_FIXED_OPAQUE_BYTES = 50
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")


class PhysicsRecordFormatError(ValueError):
    """Reject incomplete, contradictory or unsupported record envelopes."""


@dataclass(frozen=True)
class PhysicsRecord:
    label: str
    shape_reference_strings: tuple[str, ...]


@dataclass(frozen=True)
class ParsedPhysicsStructure:
    records: tuple[PhysicsRecord, ...]
    trailing_group_count: int
    trailing_opaque_bytes: int


def _read_text(data: bytes, at: int, *, allow_empty: bool) -> tuple[str, int]:
    if at + 2 > len(data):
        raise PhysicsRecordFormatError("Truncated length-prefixed field")
    count = _U16.unpack_from(data, at)[0]
    if count > MAX_TEXT_UNITS or (not allow_empty and not count):
        raise PhysicsRecordFormatError("Unsupported source identifier length")
    at += 2
    if at + count * 2 > len(data):
        raise PhysicsRecordFormatError("Truncated source identifier")
    try:
        value = data[at:at + count * 2].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as exc:
        raise PhysicsRecordFormatError("Invalid source UTF-16LE identifier") from exc
    if any(ord(char) < 32 for char in value):
        raise PhysicsRecordFormatError("Source identifier contains control characters")
    return value, at + count * 2


def parse_physics_structure(data: bytes) -> ParsedPhysicsStructure:
    """Parse the observed record prefix and count, leaving unknown bytes opaque.

    Layout observed in 81 owner-local sources:
    u32 records; repeat (u16 UTF16 local label, 50 opaque bytes,
    u32 references, repeat(u16 UTF16 reference)); then a u32 trailer
    record count followed by optional unclassified trailer bytes.

    We do NOT claim the 50 bytes represent floats, collision layers,
    masks or world transforms. Zero trailer count requires exact EOF.
    """
    if not isinstance(data, bytes) or not 8 <= len(data) <= MAX_FILE_BYTES:
        raise PhysicsRecordFormatError("Invalid physics source byte length")
    count = _U32.unpack_from(data)[0]
    if not 1 <= count <= MAX_RECORDS:
        raise PhysicsRecordFormatError("Invalid physics record count")
    cursor = 4
    parsed = []
    for _ in range(count):
        label, cursor = _read_text(data, cursor, allow_empty=True)
        if cursor + _FIXED_OPAQUE_BYTES + 4 > len(data):
            raise PhysicsRecordFormatError("Truncated opaque physics record")
        cursor += _FIXED_OPAQUE_BYTES
        references = _U32.unpack_from(data, cursor)[0]
        cursor += 4
        if not 1 <= references <= MAX_REFERENCES_PER_RECORD:
            raise PhysicsRecordFormatError("Invalid physics shape-string count")
        strings = []
        for _ in range(references):
            name, cursor = _read_text(data, cursor, allow_empty=False)
            strings.append(name)
        parsed.append(PhysicsRecord(label, tuple(strings)))
    if cursor + 4 > len(data):
        raise PhysicsRecordFormatError("Missing physics trailer count")
    trailer_count = _U32.unpack_from(data, cursor)[0]
    cursor += 4
    remaining = len(data) - cursor
    if (trailer_count > MAX_RECORDS or remaining > MAX_OPAQUE_TAIL_BYTES
            or (trailer_count == 0 and remaining != 0)
            or (trailer_count != 0 and remaining == 0)):
        raise PhysicsRecordFormatError("Inconsistent or oversized opaque physics trailer")
    return ParsedPhysicsStructure(tuple(parsed), trailer_count, remaining)


def summarize_physics_records(
    sources: dict[str, bytes], shapes: dict[str, bytes]
) -> dict:
    """Aggregate only; raw source identifiers never appear in returned JSON."""
    if not sources or not shapes or len(sources) > MAX_PHYSICS or len(shapes) > MAX_SHAPES:
        raise ValueError("Missing or oversized source aggregate")
    shape_stems = set()
    for name, contents in shapes.items():
        if (not isinstance(name, str) or not name.endswith(".shape") or
                not isinstance(contents, bytes)):
            raise ValueError("Invalid source shape entry")
        parse_shape(contents)
        shape_stems.add(name[:-6])
    total_records = total_strings = directly_matching = 0
    parsed_labels = 0
    zero_tail = unknown_tail = 0
    distinct_strings = set()
    matched_stems = set()
    max_ref = 0
    for name, contents in sources.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                not isinstance(contents, bytes)):
            raise ValueError("Invalid source physics entry")
        result = parse_physics_structure(contents)
        total_records += len(result.records)
        if result.trailing_group_count:
            unknown_tail += 1
        else:
            zero_tail += 1
        for record in result.records:
            parsed_labels += bool(record.label)
            total_strings += len(record.shape_reference_strings)
            max_ref = max(max_ref, len(record.shape_reference_strings))
            for candidate in record.shape_reference_strings:
                distinct_strings.add(candidate)
                if candidate in shape_stems:
                    directly_matching += 1
                    matched_stems.add(candidate)
    return {
        "classification": "owner_private_source_physics_record_envelope_census",
        "paired_physics_structures": len(sources),
        "paired_shape_library_entries": len(shapes),
        "parsed_physics_records": total_records,
        "physics_records_with_nonempty_local_label": parsed_labels,
        "length_prefixed_reference_strings": total_strings,
        "reference_strings_matching_shape_stems": directly_matching,
        "distinct_reference_strings": len(distinct_strings),
        "distinct_matching_shape_stems": len(matched_stems),
        "maximum_strings_in_one_record": max_ref,
        "files_with_empty_opaque_trailer": zero_tail,
        "files_with_uninterpreted_nonempty_trailer": unknown_tail,
        "fixed_record_payload_bytes": _FIXED_OPAQUE_BYTES,
        "record_envelope_parse_verified": True,
        "fifty_byte_record_payload_fields_decoded": False,
        "nonempty_trailer_payload_fields_decoded": False,
        "string_means_runtime_shape_reference_proven": False,
        "source_game_collision_semantics_verified": False,
        "ready_for_switch_geometry_import": False,
        "source_bytes_paths_names_coordinates_in_report": False,
    }


def audit_private_physics_records(ipa: Path) -> dict:
    """Use original, privately held IPA only on the owner's own environment."""
    if not ipa.is_file():
        raise ValueError("Original private IPA not found")
    with ZipFile(ipa) as zipfile:
        entries = zipfile.infolist()
        if len(entries) > MAX_MEMBERS:
            raise ValueError("Oversized source archive index")
        by_name = {row.filename: row for row in entries}
        if len(by_name) != len(entries):
            raise ValueError("Duplicate archive member")
        physics = _paired(zipfile, by_name, PHYSICS_DIR,
                          (".ps2d", ".pstruct2d"), max_items=MAX_PHYSICS)
        shapes = _paired(zipfile, by_name, SHAPE_DIR,
                         (".shape",), max_items=MAX_SHAPES)
        return summarize_physics_records(physics, shapes)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ipa", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    target = private_output_path(args.out)
    report = audit_private_physics_records(args.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n",
                      encoding="utf-8")
    print("Owner-private physics-record aggregate saved under ignored local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
