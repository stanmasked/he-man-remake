"""Falsify bounded *candidate* nested layouts of indexed iOS sprite sequences.

The original owner-held IPA contains 2,351 nonzero-count sprite
sequences. Stage157 found a source-cut resource-name candidate after
five u32 words plus 13 opaque bytes in most of them. This module
tests whether the UNKNOWN count and repeated independently indexed
cut names can form a strict exact-EOF segmentation.

Hypothetical grammar (all bytes opaque except UTF-16 names):
    first name starts 13 bytes after the five-u32 prefix;
    between one candidate-name END and next candidate-name START:
       64 + 82*k + either 12 or 33 opaque bytes;
    after final candidate-name END and before final u32:
       64 + 82*k opaque bytes.
    0 <= k <= 20; the declared count determines number of names.

The widths 64,82,12,33 and 13 are hypotheses, NOT verified frame
sizes, lengths, duration fields or an original engine serializer.
Exact-EOF saturation to 0/1/2+ prevents ambiguous paths from being
silently chosen. Predeclared null controls vary base/stride.

Original sprites, reference names, per-record boundaries, bytes and
candidate paths stay in owner's private runtime, never public CI.
"""
from __future__ import annotations

import argparse
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import (
    SCREENS, MAX_REPO_BYTES, MAX_WAD_BYTES, SpriteIndexFormatError,
    _text, parse_sprite_repository,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from .sprite_sequence_cut_name_candidates import (
    CUT_REPO, CUT_WAD, _source_token,
    summarize_sequence_cut_name_candidates,
)

MAX_PADDING_UNITS = 20
MAX_NESTED_CANDIDATES = 45
MAX_SEQUENCE_BYTES = 32768
NESTED_PREAMBLES = (12, 33)
STRUCTURED_PREFIX = 8 + 20 + 13
# These controls were declared before the original private census.
MODEL_WIDTHS = (
    ("hypothesis_64_82", 64, 82),
    ("negative_base_63_82", 63, 82),
    ("negative_base_65_82", 65, 82),
    ("negative_stride_64_80", 64, 80),
    ("negative_stride_64_84", 64, 84),
)
_TWO_WORDS = struct.Struct("<II")


def count_complete_name_paths(
    sequence: bytes,
    declared: int,
    cut_keys: frozenset[str],
    *,
    terminal_base: int = 64,
    step_bytes: int = 82,
) -> int:
    """Return -1 first cut name absent, 0 no complete path, 1 or 2+.

    This is only a tiny, explicitly constrained *falsification model*.
    No original child offsets, names or opaque fields are returned.
    """
    if (type(sequence) is not bytes
            or not 32 <= len(sequence) <= MAX_SEQUENCE_BYTES
            or type(declared) is not int
            or not 1 <= declared <= MAX_NESTED_CANDIDATES
            or not isinstance(cut_keys, frozenset)
            or not cut_keys
            or any(not isinstance(x, str) or not x for x in cut_keys)
            or type(terminal_base) is not int
            or not 0 <= terminal_base <= 128
            or type(step_bytes) is not int
            or not 1 <= step_bytes <= 256):
        raise ValueError("Invalid bounded source-private grammar input")
    try:
        _private_key, at = _text(sequence, 0)
    except SpriteIndexFormatError as exc:
        raise ValueError("Invalid hypothetical sequence envelope") from exc
    if at + 8 + 20 + 4 > len(sequence):
        raise SpriteIndexFormatError("Incomplete hypothetical sequence header")
    _marker, recorded = _TWO_WORDS.unpack_from(sequence, at)
    if recorded != declared:
        raise SpriteIndexFormatError("Hypothesis count disagrees with record header")
    stop = len(sequence) - 4

    @lru_cache(maxsize=None)
    def known_cut_name_end(pos: int) -> int:
        status, name = _source_token(sequence, pos)
        if status == "valid" and name in cut_keys:
            # Name is ASCII per the source-private evidence validator.
            return pos + 2 + 2*len(name)
        return -1

    first = known_cut_name_end(at + STRUCTURED_PREFIX)
    if first < 0:
        return -1

    @lru_cache(maxsize=None)
    def paths(index: int, previous_name_end: int) -> int:
        if index == declared:
            rest = stop - previous_name_end - terminal_base
            return int(rest >= 0 and rest % step_bytes == 0
                       and rest // step_bytes <= MAX_PADDING_UNITS)
        ways = 0
        for padding_units in range(MAX_PADDING_UNITS + 1):
            for additional_prefix in NESTED_PREAMBLES:
                next_pos = (previous_name_end + terminal_base
                            + step_bytes*padding_units + additional_prefix)
                if next_pos + 2 > stop:
                    continue
                next_end = known_cut_name_end(next_pos)
                if next_end >= 0:
                    ways += paths(index + 1, next_end)
                    if ways >= 2:
                        return 2
        return ways

    return paths(1, first)


def summarize_nested_sequence_grammar_controls(
    seq_repos: dict[str, bytes],
    seq_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Compare all declared models across both screen packs; aggregates only."""
    lexical = summarize_sequence_cut_name_candidates(
        seq_repos, seq_wads, cut_repos)
    cut_entries = parse_sprite_repository(
        cut_repos[SCREENS[0]], expected_label="SpriteCutData",
        expected_wad=CUT_WAD)
    cut_keys = frozenset(item.key for item in cut_entries)
    index = parse_sprite_repository(
        seq_repos[SCREENS[0]], expected_label="SpriteSeqData",
        expected_wad=WAD_PATH)
    records = {screen: _intervals(index, seq_wads[screen])
               for screen in SCREENS}
    result = {}
    for label, base, stride in MODEL_WIDTHS:
        by_screen = []
        for screen in SCREENS:
            bucket = Counter()
            for record in records[screen]:
                _, p = _text(record, 0)
                count = _TWO_WORDS.unpack_from(record, p)[1]
                if count == 0:
                    continue
                status = count_complete_name_paths(
                    record, count, cut_keys,
                    terminal_base=base, step_bytes=stride)
                bucket[status] += 1
            by_screen.append(bucket)
        if by_screen[0] != by_screen[1]:
            raise SpriteIndexFormatError(
                "Nested candidate grammar differs across original screen packs")
        c = by_screen[0]
        nonzero = lexical["nonzero_candidate_sequences_checked"]
        if sum(c.values()) != nonzero:
            raise SpriteIndexFormatError(
                "Incomplete original private nested candidate accounting")
        result[label] = {
            "source_records_without_matching_initial_cut_key": c[-1],
            "source_records_with_first_key_but_no_exact_EOF_parse": c[0],
            "source_records_with_exactly_one_complete_parse": c[1],
            "source_records_with_multiple_complete_parses": c[2],
        }
    return {
        "classification":
            "owner_private_sprite_sequence_nested_cut_name_grammar_falsification",
        "nonzero_sequence_records": lexical["nonzero_candidate_sequences_checked"],
        "independent_cut_registry_entries":
            lexical["independently_indexed_cut_resource_names"],
        "source_cut_name_candidate_at_first_nested_position":
            lexical["candidate_exact_cut_resource_key_matches"],
        "predeclared_second_item_preamble_byte_choices": list(NESTED_PREAMBLES),
        "max_hypothetical_opaque_extension_blocks": MAX_PADDING_UNITS,
        "hypotheses_and_negative_controls": result,
        "identical_model_classification_across_both_screen_packs": True,
        "zero_fit_or_ambiguous_never_promoted_to_valid_frames": True,
        "grammar_proves_original_nested_record_boundaries": False,
        "source_unknown_count_proven_frame_count": False,
        "original_frame_timing_or_sequence_playback_verified": False,
        "original_actor_animation_to_collision_link_verified": False,
        "original_asset_import_to_switch_enabled": False,
        "private_source_keys_offsets_payloads_and_paths_in_report": False,
    }


def audit_private_nested_sequence_grammar(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Source archive exceeds safe member budget")
        indexed = {info.filename: info for info in infos}
        if len(indexed) != len(infos):
            raise ValueError("Duplicate source ZIP member")
        seqs, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            seqs[screen] = _safe_read(
                archive, indexed.get(root + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                archive, indexed.get(root + WAD_PATH), MAX_WAD_BYTES)
            cuts[screen] = _safe_read(
                archive, indexed.get(root + CUT_REPO), MAX_REPO_BYTES)
        return summarize_nested_sequence_grammar_controls(seqs, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    target = private_output_path(args.out)
    result = audit_private_nested_sequence_grammar(args.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                      encoding="utf-8")
    print("Private sprite nested-grammar aggregate stored under local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
