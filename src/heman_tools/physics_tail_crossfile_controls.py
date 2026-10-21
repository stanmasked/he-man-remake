"""Cross-file holdout and width sensitivity controls for speculative iOS tails.

The only parsed original structures are the already validated main
physics records and declared unknown tail lengths. This module requires
candidate name tokens to come from the *same* or OTHER source files,
and probes public FIXED width caps; it never returns source strings,
file-specific candidate offsets, padding widths, or original bytes.

All results are falsification evidence. There is no physical-joint,
hitbox, collision material, level placement or runtime game claim.
Owner's IPA must never enter public GitHub/CI; unit fixtures are fake.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_opaque_probe import _capture_opaque
from .physics_records import parse_physics_structure
from .physics_shape_census import (
    MAX_MEMBERS, MAX_PHYSICS, MAX_ITEM_BYTES, PHYSICS_DIR, _paired,
)
from .physics_tail_lexicon_constraints import (
    MAX_LEXICAL_GROUPS, MAX_LEXICAL_TAIL_BYTES,
    lexically_constrained_paths,
)

WIDTH_CAPS = (16, 32, 48, 96)
CONTROL_MODES = (
    "all_sources",
    "heldout_other_sources",
    "same_source_only",
    "shared_across_at_least_two_sources",
    "exclusively_other_sources",
)


def summarize_crossfile_tail_controls(physics: dict[str, bytes]) -> dict:
    """Return only aggregate 0/1/2+ categories for predeclared controls."""
    if (not isinstance(physics, dict) or
            not 1 <= len(physics) <= MAX_PHYSICS):
        raise ValueError("Missing or excessive source physics files")

    parsed: list[tuple[frozenset[str], int, bytes]] = []
    sources_per_label: Counter[str] = Counter()
    for name, raw in physics.items():
        if (not isinstance(name, str) or
                not name.endswith((".ps2d", ".pstruct2d")) or
                "/" in name or "\\" in name or
                type(raw) is not bytes or
                not 1 <= len(raw) <= MAX_ITEM_BYTES):
            raise ValueError("Invalid private source physics resource")
        rows = parse_physics_structure(raw)
        own_labels = frozenset(row.label for row in rows.records if row.label)
        sources_per_label.update(own_labels)  # One vote per FILE, not record.
        _opaque_blocks, group_count, trailer = _capture_opaque(raw)
        if group_count and (group_count > MAX_LEXICAL_GROUPS or
                            len(trailer) > MAX_LEXICAL_TAIL_BYTES):
            raise ValueError("Source trailer outside bounded candidate domain")
        parsed.append((own_labels, group_count, trailer))

    universe = frozenset(sources_per_label)
    shared = frozenset(label for label, files in sources_per_label.items()
                       if files >= 2)
    candidates = sum(group_count > 0 for _, group_count, _ in parsed)
    multi_group_candidates = sum(group_count > 1 for _, group_count, _ in parsed)
    controls: dict[str, dict[str, dict[str, int]]] = {}
    for mode in CONTROL_MODES:
        width_table: dict[str, dict[str, int]] = {}
        for max_width in WIDTH_CAPS:
            no_fit = unique = ambiguous = 0
            multi_no_fit = multi_unique = multi_ambiguous = 0
            for own, group_count, trailer in parsed:
                if group_count == 0:
                    continue
                if mode == "all_sources":
                    allowed = universe
                elif mode == "heldout_other_sources":
                    allowed = frozenset(
                        label for label in universe
                        if sources_per_label[label] > int(label in own)
                    )
                elif mode == "same_source_only":
                    allowed = own
                elif mode == "shared_across_at_least_two_sources":
                    allowed = shared
                else:
                    allowed = frozenset(
                        label for label in universe
                        if label not in own and sources_per_label[label] > 0
                    )
                paths = lexically_constrained_paths(
                    trailer, group_count, allowed, max_padding=max_width
                )
                no_fit += paths == 0
                unique += paths == 1
                ambiguous += paths == 2
                if group_count > 1:
                    multi_no_fit += paths == 0
                    multi_unique += paths == 1
                    multi_ambiguous += paths == 2
            if (no_fit + unique + ambiguous != candidates or
                    multi_no_fit + multi_unique + multi_ambiguous
                    != multi_group_candidates):
                raise ValueError("Inconsistent cross-file hypothesis accounting")
            width_table["cap_" + str(max_width)] = {
                "no_complete_frame": no_fit,
                "one_complete_frame": unique,
                "ambiguous_multiple_frames": ambiguous,
                "multi_group_no_complete_frame": multi_no_fit,
                "multi_group_one_complete_frame": multi_unique,
                "multi_group_ambiguous_multiple_frames": multi_ambiguous,
            }
        controls[mode] = width_table

    baseline = controls["all_sources"]["cap_96"]
    heldout = controls["heldout_other_sources"]["cap_96"]
    same = controls["same_source_only"]["cap_96"]
    return {
        "classification": "owner_private_physics_crossfile_holdout_and_width_sensitivity",
        "paired_physics_files_examined": len(physics),
        "files_with_unknown_nonempty_trailer": candidates,
        "multi_group_unknown_trailer_files": multi_group_candidates,
        "different_nonempty_main_record_labels": len(universe),
        "main_record_labels_seen_in_two_or_more_source_files": len(shared),
        "predeclared_maximum_unknown_width_tiers": list(WIDTH_CAPS),
        "controls": controls,
        "global_vs_heldout_unique_candidate_counts_equal":
            baseline["one_complete_frame"] == heldout["one_complete_frame"],
        "global_vs_same_source_unique_candidate_counts_equal":
            baseline["one_complete_frame"] == same["one_complete_frame"],
        "cross_file_lexical_agreement_proves_true_record_boundaries": False,
        "max_width_threshold_implies_original_field_size": False,
        "individual_trailer_segments_decoded": False,
        "original_physics_and_collision_semantics_verified": False,
        "automatically_import_source_geometry_to_switch": False,
        "original_file_labels_offsets_bytes_and_candidate_paths_in_output": False,
    }


def audit_private_crossfile_controls(ipa: Path) -> dict:
    """Original IPA read-only locally; reports are aggregate and gitignored."""
    if not ipa.is_file():
        raise ValueError("Privately held original iOS archive not found")
    with ZipFile(ipa) as z:
        rows = z.infolist()
        if len(rows) > MAX_MEMBERS:
            raise ValueError("Original ZIP index exceeds safe bound")
        indexed = {info.filename: info for info in rows}
        if len(indexed) != len(rows):
            raise ValueError("Duplicate original ZIP member")
        resource_files = _paired(z, indexed, PHYSICS_DIR,
                                 (".ps2d", ".pstruct2d"),
                                 max_items=MAX_PHYSICS)
        return summarize_crossfile_tail_controls(resource_files)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    destination = private_output_path(args.out)
    summary = audit_private_crossfile_controls(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, sort_keys=True, indent=2)+"\n",
                           encoding="utf-8")
    print("Source-private heldout/width aggregate saved under ignored local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
