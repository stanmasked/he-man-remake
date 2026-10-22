"""Private-only failure strata for the *hypothetical* nested sprite grammar.

Stage158's 64/82 grammar fits some original sequences and fails 677
others. This diagnostic stratifies exact-EOF outcomes by two independently
serialized u32 observations:
  - candidate-count (1, 2, 3-4, 5-10, 11+)
  - first of Stage156's five u32 words (equals one vs other).

For candidate-count 1, classify opaque bytes remaining after the
Stage157 independently indexed initial cut-key candidate, with a
separate 64-byte motif and two contrasting 162/576-byte motifs.

No original keys, coordinates, WAD bytes, individual u32 values or
source record offsets are emitted. Correlation proves NO timing, frame
count, resource ownership, sprite dimensions or runtime collision rule.
All public tests are fictional paired IPA archives.
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
from .sprite_sequence_cut_name_candidates import (
    CUT_REPO, CUT_WAD, _source_token,
    summarize_sequence_cut_name_candidates,
)
from .sprite_sequence_nested_grammar import count_complete_name_paths

_U32 = struct.Struct("<I")
_U32_PAIR = struct.Struct("<II")
_OUTCOMES = (-1, 0, 1, 2)
_COUNT_GROUPS = ("one", "two", "three_four", "five_ten", "eleven_plus")
_PREFIX_GROUPS = ("first_u32_one", "first_u32_other")
_TAIL_GROUPS = ("initial_name_missing", "suffix_64", "suffix_162",
                "suffix_576", "other_suffix")


def _count_group(declared: int) -> str:
    if declared == 1:
        return "one"
    if declared == 2:
        return "two"
    if declared <= 4:
        return "three_four"
    if declared <= 10:
        return "five_ten"
    return "eleven_plus"


def _outcomes(c: Counter) -> dict:
    return {
        "no_independent_initial_cut_key": c[-1],
        "initial_key_but_no_complete_grammar_path": c[0],
        "exactly_one_complete_candidate_path": c[1],
        "multiple_complete_candidate_paths": c[2],
    }


def _single_tail_category(record: bytes, at: int,
                          cut_keys: frozenset[str]) -> str:
    status, name = _source_token(record, at)
    if status != "valid" or name not in cut_keys:
        return "initial_name_missing"
    # _source_token accepts bounded printable ASCII (one UTF-16 code unit
    # per character). The per-record byte position is never exported.
    after_name = at + 2 + 2 * len(name)
    leftover = len(record) - 4 - after_name
    return {
        64: "suffix_64",
        162: "suffix_162",
        576: "suffix_576",
    }.get(leftover, "other_suffix")


def summarize_sequence_firstword_failure_strata(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Correlate prior grammar success with source header words, privately."""
    lexical = summarize_sequence_cut_name_candidates(
        sequence_repos, sequence_wads, cut_repos
    )
    keys = frozenset(entry.key for entry in parse_sprite_repository(
        cut_repos[SCREENS[0]],
        expected_label="SpriteCutData", expected_wad=CUT_WAD
    ))
    entries = parse_sprite_repository(
        sequence_repos[SCREENS[0]],
        expected_label="SpriteSeqData", expected_wad=WAD_PATH
    )
    source_results = []
    for screen in SCREENS:
        records = _intervals(entries, sequence_wads[screen])
        by_first = defaultdict(Counter)
        by_count = defaultdict(Counter)
        singles = defaultdict(Counter)
        for record in records:
            _private_sequence_key, cursor = _text(record, 0)
            _marker, declared = _U32_PAIR.unpack_from(record, cursor)
            if declared == 0:
                continue
            first_word = _U32.unpack_from(record, cursor + 8)[0]
            group = ("first_u32_one" if first_word == 1
                     else "first_u32_other")
            outcome = count_complete_name_paths(
                record, declared, keys, terminal_base=64, step_bytes=82
            )
            by_first[group][outcome] += 1
            by_count[_count_group(declared)][outcome] += 1
            if declared == 1:
                singles[group][_single_tail_category(
                    record, cursor + 8 + 20 + 13, keys)] += 1

        if sum(sum(c.values()) for c in by_first.values()) != lexical[
                "nonzero_candidate_sequences_checked"]:
            raise SpriteIndexFormatError("Incomplete original sequence groups")
        source_results.append((by_first, by_count, singles))

    a, b = source_results
    def normalized(item):
        by_first, by_count, singles = item
        return (
            {group:_outcomes(by_first[group]) for group in _PREFIX_GROUPS},
            {group:_outcomes(by_count[group]) for group in _COUNT_GROUPS},
            {group:{key:singles[group][key] for key in _TAIL_GROUPS}
             for group in _PREFIX_GROUPS}
        )

    if normalized(a) != normalized(b):
        raise SpriteIndexFormatError(
            "Original resolution-pack grammar failure strata diverged"
        )
    first, count, single = normalized(a)
    single_total = sum(sum(c.values()) for c in single.values())
    if single_total != sum(count["one"].values()):
        raise SpriteIndexFormatError("Single-count motif accounting differs")

    return {
        "classification":
            "owner_private_nested_sprite_grammar_firstword_stratification",
        "nonzero_unknown_candidate_count_records":
            lexical["nonzero_candidate_sequences_checked"],
        "independent_cut_registry_entries":
            lexical["independently_indexed_cut_resource_names"],
        "exact_eof_model_terminal_base_bytes":64,
        "exact_eof_model_opaque_stride_bytes":82,
        "grammar_result_by_first_prefix_word":first,
        "grammar_result_by_unknown_candidate_count_group":count,
        "single_candidate_initial_name_suffix_motifs_by_first_word":single,
        "cross_resolution_aggregate_classifications_match":True,
        "independent_lexical_name_match_counts_as_frame_proof":False,
        "first_prefix_word_controls_nested_record_count_verified":False,
        "sixty_four_byte_suffix_proves_fixed_frame_layout":False,
        "original_sprite_timing_or_animation_playback_verified":False,
        "original_actor_state_and_hitbox_switching_verified":False,
        "automatic_source_sprite_import_to_switch_permitted":False,
        "source_names_raw_values_offsets_pixels_and_hashes_exported":False,
    }


def audit_private_sequence_firstword_failure_strata(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Original owner-private IPA not found")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        index = {info.filename:info for info in infos}
        if len(index) != len(infos):
            raise ValueError("Duplicate original ZIP member")
        seqs, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            seqs[screen] = _safe_read(
                archive, index.get(prefix + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                archive, index.get(prefix + WAD_PATH), MAX_WAD_BYTES)
            cuts[screen] = _safe_read(
                archive, index.get(prefix + CUT_REPO), MAX_REPO_BYTES)
        return summarize_sequence_firstword_failure_strata(
            seqs, wads, cuts
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    dest = private_output_path(args.out)
    result = audit_private_sequence_firstword_failure_strata(args.ipa)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n",
                    encoding="utf-8")
    print("Owner-private aggregate sprite grammar failure strata saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
