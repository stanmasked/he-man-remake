"""Stage160: test associations inside *non-one* first-u32 sprite records.

Report aggregate-only relationships between a serialized header word
and known-cut-name suffix lengths / candidate grammar outcomes. Raw
first-u32 values are keys in memory ONLY; they are never written to
GitHub, JSON, logs, or returned to the caller. The known 64, 162, 576
lengths are observational categories, not frame layouts.

This is a falsification aid: even a deterministic length per header
value would not establish original frames, playback timing or types.
Public tests use exclusively fictional paired screen resources.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import struct

from .collision_inventory import private_output_path
from .sprite_repo_wad_index import (
    SCREENS, SpriteIndexFormatError, parse_sprite_repository, _text,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_cut_name_candidates import (
    CUT_WAD, _source_token,
)
from .sprite_sequence_header_controls import WAD_PATH
from .sprite_sequence_failure_strata import (
    _count_group, _COUNT_GROUPS, _TAIL_GROUPS,
    summarize_sequence_firstword_failure_strata,
    audit_private_sequence_firstword_failure_strata,
)
from .sprite_sequence_nested_grammar import count_complete_name_paths

_PAIR = struct.Struct("<II")
_WORD = struct.Struct("<I")
_SPRITE_START_AFTER_KEY = 8 + 20 + 13


def _known_single_suffix_length(
    record: bytes, token_position: int, cut_keys: frozenset[str],
) -> int | None:
    """Return private raw suffix length if the first name is indexed."""
    status, name = _source_token(record, token_position)
    if status != "valid" or name not in cut_keys:
        return None
    remaining = len(record) - 4 - (token_position + 2 + 2 * len(name))
    if remaining < 0:
        raise SpriteIndexFormatError("Invalid indexed single-name suffix")
    return remaining


def _motif(length: int | None) -> str:
    if length is None:
        return "initial_name_missing"
    return {64: "suffix_64", 162: "suffix_162",
            576: "suffix_576"}.get(length, "other_suffix")


def _one_pack_nonunit(
    index: tuple, wad: bytes, cut_keys: frozenset[str],
) -> dict:
    """Keep exact header values and suffix lengths inside this invocation."""
    groups = {}
    counts = Counter()
    motif_counts = Counter()
    motif_distinct_values = defaultdict(set)
    for record in _intervals(index, wad):
        _private_name, pos = _text(record, 0)
        _marker, candidate_count = _PAIR.unpack_from(record, pos)
        if candidate_count == 0:
            continue
        first_word = _WORD.unpack_from(record, pos + 8)[0]
        if first_word == 1:
            continue
        group = groups.setdefault(first_word, {
            "records": 0, "count_groups": set(), "known_single_lengths": [],
            "outcomes": Counter(),
        })
        group["records"] += 1
        group["count_groups"].add(_count_group(candidate_count))
        counts[_count_group(candidate_count)] += 1
        outcome = count_complete_name_paths(
            record, candidate_count, cut_keys,
            terminal_base=64, step_bytes=82,
        )
        group["outcomes"][outcome] += 1
        if candidate_count == 1:
            length = _known_single_suffix_length(
                record, pos + _SPRITE_START_AFTER_KEY, cut_keys,
            )
            motif = _motif(length)
            motif_counts[motif] += 1
            motif_distinct_values[motif].add(first_word)
            if length is not None:
                group["known_single_lengths"].append(length)

    eligible = [g for g in groups.values()
                if len(g["known_single_lengths"]) >= 2]
    support = Counter(
        "one_record" if g["records"] == 1 else
        "two_to_nine_records" if g["records"] < 10 else
        "ten_plus_records"
        for g in groups.values()
    )
    return {
        "nonunit_records": sum(g["records"] for g in groups.values()),
        "distinct_nonunit_values": len(groups),
        "largest_nonunit_value_group": max(
            (g["records"] for g in groups.values()), default=0,
        ),
        "nonunit_value_support": {
            k: support[k]
            for k in ("one_record", "two_to_nine_records",
                      "ten_plus_records")
        },
        "nonunit_candidate_count_groups": {
            label: counts[label] for label in _COUNT_GROUPS
        },
        "nonunit_values_shared_across_multiple_count_groups": sum(
            len(g["count_groups"]) > 1 for g in groups.values()
        ),
        "nonunit_values_shared_between_single_and_multi_count": sum(
            "one" in g["count_groups"] and len(g["count_groups"]) > 1
            for g in groups.values()
        ),
        "nonunit_values_with_both_unfitted_and_fitted_paths": sum(
            (g["outcomes"][-1] + g["outcomes"][0] > 0) and
            (g["outcomes"][1] + g["outcomes"][2] > 0)
            for g in groups.values()
        ),
        "nonunit_single_candidate_suffix_motifs": {
            label: {
                "records": motif_counts[label],
                "distinct_nonunit_first_u32_values":
                    len(motif_distinct_values[label]),
            } for label in _TAIL_GROUPS
        },
        "nonunit_values_with_two_or_more_known_single_suffixes":
            len(eligible),
        "eligible_nonunit_values_with_uniform_exact_suffix_length": sum(
            len(set(g["known_single_lengths"])) == 1 for g in eligible
        ),
        "eligible_nonunit_values_with_variable_exact_suffix_length": sum(
            len(set(g["known_single_lengths"])) > 1 for g in eligible
        ),
    }


def summarize_sequence_nonunit_header_associations(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Strict paired screen validation then in-memory value associations."""
    baseline = summarize_sequence_firstword_failure_strata(
        sequence_repos, sequence_wads, cut_repos
    )
    cut_index = parse_sprite_repository(
        cut_repos[SCREENS[0]], expected_label="SpriteCutData",
        expected_wad=CUT_WAD,
    )
    cut_keys = frozenset(row.key for row in cut_index)
    seq_index = parse_sprite_repository(
        sequence_repos[SCREENS[0]], expected_label="SpriteSeqData",
        expected_wad=WAD_PATH,
    )
    scans = [_one_pack_nonunit(seq_index, sequence_wads[s], cut_keys)
             for s in SCREENS]
    if scans[0] != scans[1]:
        raise SpriteIndexFormatError(
            "Nonunit header associations diverged across screen packs"
        )
    result = scans[0]
    baseline_nonunit = baseline[
        "grammar_result_by_first_prefix_word"]["first_u32_other"]
    if result["nonunit_records"] != sum(baseline_nonunit.values()):
        raise SpriteIndexFormatError("Nonunit source record count mismatch")
    expected_motifs = baseline[
        "single_candidate_initial_name_suffix_motifs_by_first_word"
    ]["first_u32_other"]
    for motif in _TAIL_GROUPS:
        if (result["nonunit_single_candidate_suffix_motifs"][
                motif]["records"] != expected_motifs[motif]):
            raise SpriteIndexFormatError("Nonunit suffix motif mismatch")

    return {
        "classification":
            "owner_private_nonunit_sprite_firstword_association_controls",
        **result,
        "cross_resolution_aggregate_associations_match": True,
        "raw_nonunit_header_values_or_name_strings_exported": False,
        "individual_suffix_lengths_or_record_offsets_exported": False,
        "fixed_suffix_length_proves_nested_frame_layout": False,
        "header_value_proven_sprite_type_or_child_count": False,
        "original_frame_durations_or_playback_verified": False,
        "automatic_original_asset_import_permitted": False,
    }


def audit_private_sequence_nonunit_header_associations(ipa: Path) -> dict:
    """Reuse the Stage159 safe ZIP reader; never export its source bytes."""
    # Stage159's ZIP controls reject oversized members, duplicate names,
    # selected symlinks and malformed paired assets. This entry point
    # reopens the archive for the new correlations, with identical guards.
    from zipfile import ZipFile
    from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read
    from .sprite_repo_wad_index import MAX_REPO_BYTES, MAX_WAD_BYTES
    from .sprite_sequence_header_controls import REPO_PATH
    from .sprite_sequence_cut_name_candidates import CUT_REPO

    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        indexed = {info.filename: info for info in members}
        if len(indexed) != len(members):
            raise ValueError("Duplicate original ZIP member")
        seqs, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            seqs[screen] = _safe_read(
                archive, indexed.get(prefix + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                archive, indexed.get(prefix + WAD_PATH), MAX_WAD_BYTES)
            cuts[screen] = _safe_read(
                archive, indexed.get(prefix + CUT_REPO), MAX_REPO_BYTES)
    return summarize_sequence_nonunit_header_associations(
        seqs, wads, cuts
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = audit_private_sequence_nonunit_header_associations(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Owner-private nonunit sprite prefix correlations stored locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
