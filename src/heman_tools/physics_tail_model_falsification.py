"""Private-only comparative falsification of two opaque trailer framing models.

Stage143's constant-width candidate patterns fail to describe all 13
original iOS trailers. A more permissive per-group variable-width model
can fit unrelated data many ways. Count exact-EOF parses (0, 1, or >=2),
never choose a path or export individual field widths/strings.

No actual source data is included here; GitHub tests use synthetic bytes.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_records import (
    _read_text, MAX_OPAQUE_TAIL_BYTES, MAX_RECORDS,
    PhysicsRecordFormatError,
)
from .physics_opaque_probe import _capture_opaque
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, PHYSICS_DIR, _paired,
)
from .physics_tail_candidates import (
    candidate_tail_boundaries, MAX_FIXED_BYTES_PER_GROUP,
)

PATH_AMBIGUOUS = 2  # Saturation sentinel: "two or more", not an exact count.


def complete_variable_width_paths(
    trailer: bytes,
    group_count: int,
    *,
    opaque_first: bool = False,
    max_width: int = MAX_FIXED_BYTES_PER_GROUP,
) -> int:
    """Return 0, 1 or 2 (>=2) exact-EOF record segmentations.

    Candidate record: [u16/UTF16 label][0..max_width arbitrary bytes]
      or reversed, optionally changing the byte count for EACH item.

    Crucially: this tests *only* total byte consumption. No discovered
    lengths/positions, text, geometry or individual candidate paths
    may be published. Saturating the path count prevents combinatorial
    explosions and avoids implying exact path cardinalities.
    """
    if (type(trailer) is not bytes or
            not 1 <= len(trailer) <= MAX_OPAQUE_TAIL_BYTES or
            type(group_count) is not int or not 1 <= group_count <= MAX_RECORDS or
            type(opaque_first) is not bool or
            type(max_width) is not int or
            not 0 <= max_width <= MAX_FIXED_BYTES_PER_GROUP):
        raise ValueError("Invalid candidate framing input")

    @lru_cache(maxsize=None)
    def label_end(at: int) -> int:
        if at < 0 or at > len(trailer):
            return -1
        try:
            _unused_string, finish = _read_text(trailer, at, allow_empty=True)
        except PhysicsRecordFormatError:
            return -1
        return finish

    @lru_cache(maxsize=None)
    def paths(index: int, offset: int) -> int:
        if index == group_count:
            return int(offset == len(trailer))
        remaining = group_count - index - 1
        # Every later label requires at least a two-byte u16 length.
        if offset + 2 * (remaining + 1) > len(trailer):
            return 0
        total = 0
        if opaque_first:
            for width in range(max_width + 1):
                start = offset + width
                if start + 2 * (remaining + 1) > len(trailer):
                    break
                end = label_end(start)
                if end == -1:
                    continue
                total += paths(index + 1, end)
                if total >= PATH_AMBIGUOUS:
                    return PATH_AMBIGUOUS
        else:
            end = label_end(offset)
            if end == -1:
                return 0
            for width in range(max_width + 1):
                after = end + width
                if after + 2 * remaining > len(trailer):
                    break
                total += paths(index + 1, after)
                if total >= PATH_AMBIGUOUS:
                    return PATH_AMBIGUOUS
        return total

    return paths(0, 0)


def summarize_variable_tail_hypotheses(
    original_source_files: dict[str, bytes]
) -> dict:
    """Aggregate comparison; never disclose individual source-file outcomes."""
    if (not isinstance(original_source_files, dict) or
            not 1 <= len(original_source_files) <= MAX_PHYSICS):
        raise ValueError("Missing or excessive private physics resources")

    total_groups = 0
    nonempty = 0
    fixed_zero = fixed_unique = fixed_ambiguous = 0
    suffix_zero = suffix_unique = suffix_ambiguous = 0
    prefix_zero = prefix_unique = prefix_ambiguous = 0
    multi_group = multi_suffix_ambiguous = 0
    one_group = 0
    for name, source in original_source_files.items():
        if (not isinstance(name, str) or not
                name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name or
                type(source) is not bytes):
            raise ValueError("Invalid source-only physics resource")
        _blocks, declared, trailer = _capture_opaque(source)
        if not declared:
            continue
        nonempty += 1
        total_groups += declared
        if declared == 1:
            one_group += 1
        else:
            multi_group += 1
        fixed = len(candidate_tail_boundaries(trailer, declared))
        suffix = complete_variable_width_paths(trailer, declared)
        prefix = complete_variable_width_paths(
            trailer, declared, opaque_first=True
        )
        fixed_zero += fixed == 0
        fixed_unique += fixed == 1
        fixed_ambiguous += fixed >= 2
        suffix_zero += suffix == 0
        suffix_unique += suffix == 1
        suffix_ambiguous += suffix >= 2
        prefix_zero += prefix == 0
        prefix_unique += prefix == 1
        prefix_ambiguous += prefix >= 2
        if declared > 1 and suffix >= 2:
            multi_suffix_ambiguous += 1

    if fixed_zero + fixed_unique + fixed_ambiguous != nonempty:
        raise ValueError("Inconsistent fixed-width hypothesis census")
    if suffix_zero + suffix_unique + suffix_ambiguous != nonempty:
        raise ValueError("Inconsistent variable-width hypothesis census")
    if prefix_zero + prefix_unique + prefix_ambiguous != nonempty:
        raise ValueError("Inconsistent prefix-first hypothesis census")
    return {
        "classification": "private_original_physics_tail_hypothesis_falsification",
        "examined_paired_physics_resource_count": len(original_source_files),
        "nonempty_trailer_count": nonempty,
        "declared_unknown_trailer_groups": total_groups,
        "single_group_trailers_inherently_weak_evidence": one_group,
        "multi_group_trailers": multi_group,
        "fixed_width_models_zero_match_files": fixed_zero,
        "fixed_width_models_unique_match_files": fixed_unique,
        "fixed_width_models_ambiguous_match_files": fixed_ambiguous,
        "variable_suffix_width_zero_match_files": suffix_zero,
        "variable_suffix_width_unique_match_files": suffix_unique,
        "variable_suffix_width_ambiguous_match_files": suffix_ambiguous,
        "variable_prefix_width_zero_match_files": prefix_zero,
        "variable_prefix_width_unique_match_files": prefix_unique,
        "variable_prefix_width_ambiguous_match_files": prefix_ambiguous,
        "multi_group_variable_suffix_width_ambiguous_files":
            multi_suffix_ambiguous,
        "all_variable_width_candidate_ways_are_saturated_at_two": True,
        "a_fitting_model_proves_source_layout": False,
        "actual_repeated_item_boundaries_verified": False,
        "source_physics_numeric_fields_decoded": False,
        "original_level_shape_binding_verified": False,
        "source_original_physics_fidelity_verified": False,
        "safe_for_switch_geometry_import": False,
        "original_source_names_bytes_widths_paths_in_report": False,
    }


def audit_private_variable_tail_models(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA not found")
    with ZipFile(ipa) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_MEMBERS:
            raise ValueError("Oversized private archive index")
        index = {item.filename: item for item in entries}
        if len(index) != len(entries):
            raise ValueError("Duplicate private archive entry")
        sources = _paired(
            archive, index, PHYSICS_DIR, (".ps2d", ".pstruct2d"),
            max_items=MAX_PHYSICS
        )
        return summarize_variable_tail_hypotheses(sources)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args(argv)
    target = private_output_path(arguments.out)
    report = audit_private_variable_tail_models(arguments.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n",
                      encoding="utf-8")
    print("Private aggregate trailer model comparison saved to ignored local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
