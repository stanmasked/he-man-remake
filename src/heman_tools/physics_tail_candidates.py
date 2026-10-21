"""Falsifiable *candidate* framing models for opaque physics trailers.

No iOS physics semantics inferred. Given the outer group's declared count,
test two deliberately restrictive UTF-16 name + equal-width opaque padding
models. Exact EOF for EVERY group is required, not merely the first label.
Result is only a census of plausible byte boundaries; never source geometry,
shape ownership, joint type or permission to import collision data.

Only owner-local IPA is inspected; public CI generates synthetic bytes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_opaque_probe import _capture_opaque
from .physics_records import (
    MAX_OPAQUE_TAIL_BYTES,
    MAX_RECORDS,
    PhysicsRecordFormatError,
    _read_text,
)
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, PHYSICS_DIR, _paired
)

MAX_FIXED_BYTES_PER_GROUP = 96
LAYOUT_NAME_THEN_OPAQUE = "utf16_name_then_fixed_opaque"
LAYOUT_OPAQUE_THEN_NAME = "fixed_opaque_then_utf16_name"


def _fits_model(trailer: bytes, count: int, width: int,
                *, opaque_first: bool) -> bool:
    pos = 0
    for _ in range(count):
        if opaque_first:
            pos += width
            if pos > len(trailer):
                return False
        try:
            _unused_string, pos = _read_text(trailer, pos, allow_empty=True)
        except PhysicsRecordFormatError:
            return False
        if not opaque_first:
            pos += width
            if pos > len(trailer):
                return False
    return pos == len(trailer)


def candidate_tail_boundaries(trailer: bytes, group_count: int,
                              *, max_fixed_bytes: int = MAX_FIXED_BYTES_PER_GROUP
                              ) -> tuple[tuple[str, int], ...]:
    """Find exact-EOF hypothetical layouts; no decoded opaque payload fields.

    Try exactly these models, each with one common unknown fixed width:
    (a) [u16/UTF16 label][N opaque bytes] repeated group_count times;
    (b) [N opaque bytes][u16/UTF16 label] repeated group_count times.
    An N=0 layout is identical for both, so it is returned only once.

    This is a bounded hypothesis search, NOT verification of the layout.
    For one group a valid first UTF-16 label is especially weak evidence:
    all remaining bytes can be reclassified as a single opaque suffix.
    """
    if (not isinstance(trailer, bytes) or not 1 <= len(trailer) <= MAX_OPAQUE_TAIL_BYTES or
            type(group_count) is not int or
            not 1 <= group_count <= MAX_RECORDS or
            type(max_fixed_bytes) is not int or
            not 0 <= max_fixed_bytes <= MAX_FIXED_BYTES_PER_GROUP):
        raise ValueError("Invalid bounded trailer candidate input")
    found: list[tuple[str, int]] = []
    for width in range(max_fixed_bytes + 1):
        if group_count * (2 + width) > len(trailer):
            continue
        if _fits_model(trailer, group_count, width, opaque_first=False):
            found.append((LAYOUT_NAME_THEN_OPAQUE, width))
        if width and _fits_model(trailer, group_count, width, opaque_first=True):
            found.append((LAYOUT_OPAQUE_THEN_NAME, width))
    return tuple(found)


def summarize_tail_boundary_candidates(
    source_files: dict[str, bytes]
) -> dict:
    """Source-private files in, *only aggregate numbers* out."""
    if (not isinstance(source_files, dict) or
            not 1 <= len(source_files) <= MAX_PHYSICS):
        raise ValueError("Missing or excessive source physics files")
    nonzero, declared_groups, zero_candidates, one_candidate = 0, 0, 0, 0
    multiple_candidates, all_candidates = 0, 0
    name_first, opaque_first = 0, 0
    single_group_files, multiple_group_files = 0, 0
    multi_group_with_candidate = multi_group_unique = 0
    max_candidates = 0
    total_bytes = 0
    for name, original in source_files.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name or
                not isinstance(original, bytes)):
            raise ValueError("Invalid private source member")
        _blocks, declared, trailer = _capture_opaque(original)
        if not declared:
            continue
        nonzero += 1
        declared_groups += declared
        total_bytes += len(trailer)
        candidates = candidate_tail_boundaries(trailer, declared)
        count = len(candidates)
        all_candidates += count
        max_candidates = max(max_candidates, count)
        zero_candidates += count == 0
        one_candidate += count == 1
        multiple_candidates += count > 1
        name_first += sum(kind == LAYOUT_NAME_THEN_OPAQUE for kind, _ in candidates)
        opaque_first += sum(kind == LAYOUT_OPAQUE_THEN_NAME for kind, _ in candidates)
        if declared == 1:
            single_group_files += 1
        else:
            multiple_group_files += 1
            multi_group_with_candidate += count > 0
            multi_group_unique += count == 1
    return {
        "classification": "private_physics_trailer_falsifiable_candidate_framing_only",
        "source_physics_files_examined": len(source_files),
        "nonempty_trailer_files": nonzero,
        "declared_trailer_groups": declared_groups,
        "uninterpreted_trailer_bytes": total_bytes,
        "files_with_no_complete_candidate": zero_candidates,
        "files_with_one_complete_candidate": one_candidate,
        "files_with_ambiguous_multiple_candidates": multiple_candidates,
        "total_candidate_framings": all_candidates,
        "maximum_candidate_framings_in_one_file": max_candidates,
        "name_then_fixed_opaque_candidate_framings": name_first,
        "fixed_opaque_then_name_candidate_framings": opaque_first,
        "single_group_trailers_non_discriminating": single_group_files,
        "multi_group_trailers_examined": multiple_group_files,
        "multi_group_trailers_with_any_candidate": multi_group_with_candidate,
        "multi_group_trailers_with_exactly_one_candidate": multi_group_unique,
        "candidate_fixed_width_search_maximum": MAX_FIXED_BYTES_PER_GROUP,
        "hypothesis_consumes_entire_tail_by_construction": True,
        "original_trailer_layout_verified": False,
        "original_trailer_item_semantics_verified": False,
        "original_physics_record_payload_decoded": False,
        "level_object_to_collision_shape_binding_verified": False,
        "safe_for_switch_geometry_import": False,
        "original_bytes_names_widths_offsets_in_report": False,
    }


def audit_private_candidate_trailers(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Privately held original IPA not found")
    with ZipFile(ipa) as z:
        info = z.infolist()
        if len(info) > MAX_MEMBERS:
            raise ValueError("Excessive private ZIP index")
        indexed = {item.filename: item for item in info}
        if len(indexed) != len(info):
            raise ValueError("Duplicate private ZIP member")
        sources = _paired(z, indexed, PHYSICS_DIR,
                          (".ps2d", ".pstruct2d"), max_items=MAX_PHYSICS)
        return summarize_tail_boundary_candidates(sources)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    out = private_output_path(args.out)
    report = audit_private_candidate_trailers(args.ipa)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8")
    print("Only private aggregate trailer hypothesis counts written in local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
