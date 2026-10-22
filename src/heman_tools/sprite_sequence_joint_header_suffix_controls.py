"""Stage162: joint firstword/length/screen-parity falsification, privately.

The numeric first u32 of the established five-u32 source sequence prefix
is treated only as an opaque *grouping key*. This diagnostic asks whether
records sharing that key can disagree on exact opaque suffix length and/or
whether the same suffix bytes differ between source resolution packs.

Only anonymous counts and four coarse "uniform/variable" x
"identical/changed" categories are returned. Original firstword values,
resource names, raw bytes, individual record positions and exact
per-record suffix lengths are NEVER returned, printed or committed.

The reports are evidence against oversimplified layout hypotheses, not
proof of frames, sprite ownership or animation time.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import (
    SCREENS, MAX_REPO_BYTES, MAX_WAD_BYTES,
    SpriteIndexFormatError, parse_sprite_repository, _text,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from .sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD
from .sprite_sequence_nonunit_header_associations import (
    summarize_sequence_nonunit_header_associations,
)
from .sprite_sequence_suffix_screen_parity import (
    _cut_suffix, summarize_sequence_single_suffix_screen_parity,
)

_PAIR = struct.Struct("<II")
_U32 = struct.Struct("<I")
_CUT_POSITION_AFTER_KEY = 8 + 20 + 13
_PROFILE_LABELS = (
    "uniform_length_all_screen_suffixes_identical",
    "uniform_length_some_screen_suffixes_changed",
    "variable_length_all_screen_suffixes_identical",
    "variable_length_some_screen_suffixes_changed",
)


def summarize_sequence_joint_header_suffix_controls(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Run independent Stage160/161 audits before comparing joint evidence."""
    nonunit = summarize_sequence_nonunit_header_associations(
        sequence_repos, sequence_wads, cut_repos,
    )
    screen = summarize_sequence_single_suffix_screen_parity(
        sequence_repos, sequence_wads, cut_repos,
    )
    seq_rows = parse_sprite_repository(
        sequence_repos[SCREENS[0]],
        expected_label="SpriteSeqData", expected_wad=WAD_PATH,
    )
    cut_rows = parse_sprite_repository(
        cut_repos[SCREENS[0]],
        expected_label="SpriteCutData", expected_wad=CUT_WAD,
    )
    cut_keys = frozenset(row.key for row in cut_rows)
    paired = [_intervals(seq_rows, sequence_wads[s]) for s in SCREENS]

    # Only private, in-memory grouping keys and exact lengths.
    headers: dict[int, list[tuple[int, bool, str]]] = defaultdict(list)
    total_equal = total_changed = 0
    for a, b in zip(*paired):
        _, pos_a = _text(a, 0)
        _, pos_b = _text(b, 0)
        count_a = _PAIR.unpack_from(a, pos_a)[1]
        count_b = _PAIR.unpack_from(b, pos_b)[1]
        if count_a != count_b:
            raise SpriteIndexFormatError("Paired sprite counts differ")
        if count_a != 1:
            continue

        word_a = _U32.unpack_from(a, pos_a + 8)[0]
        word_b = _U32.unpack_from(b, pos_b + 8)[0]
        if word_a != word_b:
            raise SpriteIndexFormatError("Paired first words differ")
        if word_a == 1:
            continue

        motif_a, suffix_a = _cut_suffix(
            a, pos_a + _CUT_POSITION_AFTER_KEY, cut_keys,
        )
        motif_b, suffix_b = _cut_suffix(
            b, pos_b + _CUT_POSITION_AFTER_KEY, cut_keys,
        )
        if motif_a != motif_b:
            raise SpriteIndexFormatError("Paired single suffix motifs differ")
        if suffix_a is None and suffix_b is None:
            continue
        if suffix_a is None or suffix_b is None or len(suffix_a) != len(suffix_b):
            raise SpriteIndexFormatError("Paired known suffixes diverged")
        equal = suffix_a == suffix_b
        headers[word_a].append((len(suffix_a), equal, motif_a))
        total_equal += equal
        total_changed += not equal

    profile = Counter()
    singletons = 0
    mixed_motifs = 0
    different_exact_lengths_in_other = 0
    for entries in headers.values():
        if len(entries) == 1:
            singletons += 1
            continue
        distinct_lengths = {length for length, _, _ in entries}
        distinct_motifs = {motif for _, _, motif in entries}
        if len(distinct_motifs) > 1:
            mixed_motifs += 1
        other_lengths = {length for length, _, motif in entries
                         if motif == "other_suffix"}
        if len(other_lengths) > 1:
            different_exact_lengths_in_other += 1
        uniform = len(distinct_lengths) == 1
        identical = all(is_equal for _, is_equal, _ in entries)
        label = (
            ("uniform_length_" if uniform else "variable_length_") +
            ("all_screen_suffixes_identical" if identical
             else "some_screen_suffixes_changed")
        )
        profile[label] += 1

    eligible = sum(profile.values())
    if eligible != nonunit["nonunit_values_with_two_or_more_known_single_suffixes"]:
        raise SpriteIndexFormatError("Repeated firstword group counts disagree")
    if sum(profile[k] for k in _PROFILE_LABELS[:2]) != nonunit[
            "eligible_nonunit_values_with_uniform_exact_suffix_length"]:
        raise SpriteIndexFormatError("Uniform suffix classification differs")
    if sum(profile[k] for k in _PROFILE_LABELS[2:]) != nonunit[
            "eligible_nonunit_values_with_variable_exact_suffix_length"]:
        raise SpriteIndexFormatError("Variable suffix classification differs")

    indexed_nonunit_singles = screen[
        "single_candidate_known_cut_suffix_screen_pair_census"
    ]["first_u32_other"]
    independently_compared = sum(
        row["compared_pairs"] for motif, row in indexed_nonunit_singles.items()
        if motif != "initial_name_missing"
    )
    if total_equal + total_changed != independently_compared:
        raise SpriteIndexFormatError("Stage161 compared suffix count differs")
    stage161_identical = sum(
        row["screen_suffix_difference_bands"]["identical"]
        for row in indexed_nonunit_singles.values()
    )
    if stage161_identical != total_equal:
        raise SpriteIndexFormatError("Stage161 identical suffix count differs")

    if len(headers) != singletons + eligible:
        raise SpriteIndexFormatError("Singleton/repeated group accounting differs")
    return {
        "classification":
            "owner_private_joint_nonunit_header_suffix_screen_controls",
        "nonunit_known_single_candidate_pairs_compared":
            total_equal + total_changed,
        "nonunit_known_single_candidate_suffix_identical_pairs": total_equal,
        "nonunit_known_single_candidate_suffix_changed_pairs": total_changed,
        "distinct_nonunit_firstword_values_with_known_single_suffix":
            len(headers),
        "singleton_nonunit_firstword_values_with_known_single_suffix":
            singletons,
        "eligible_repeated_nonunit_firstword_groups": eligible,
        "eligible_repeated_nonunit_firstword_groups_by_joint_profile": {
            label: profile[label] for label in _PROFILE_LABELS
        },
        "repeated_nonunit_firstword_groups_with_multiple_length_motifs":
            mixed_motifs,
        "repeated_nonunit_firstword_groups_with_multiple_exact_other_lengths":
            different_exact_lengths_in_other,
        "stage160_and_stage161_private_aggregate_controls_agree": True,
        "singletons_are_evidence_of_fixed_serialized_layout": False,
        "header_value_proven_to_select_nested_record_type": False,
        "suffix_byte_changes_prove_sprite_pixels": False,
        "original_frame_boundaries_timing_and_states_verified": False,
        "private_values_names_bytes_offsets_or_positions_exported": False,
        "original_asset_import_permitted": False,
    }


def audit_private_sequence_joint_header_suffix_controls(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("Excessive source ZIP members")
        lookup = {i.filename: i for i in members}
        if len(lookup) != len(members):
            raise ValueError("Duplicate original ZIP member")
        repos, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            repos[screen] = _safe_read(
                archive, lookup.get(root + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                archive, lookup.get(root + WAD_PATH), MAX_WAD_BYTES)
            cuts[screen] = _safe_read(
                archive, lookup.get(root + CUT_REPO), MAX_REPO_BYTES)
    return summarize_sequence_joint_header_suffix_controls(repos, wads, cuts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    path = private_output_path(args.out)
    result = audit_private_sequence_joint_header_suffix_controls(args.ipa)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")
    print("Private joint firstword/suffix evidence summary written locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
