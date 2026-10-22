"""Stage163: source-private, width-free lexical sprite-cut anchor census.

Scan bytes strictly *after* the independently indexed first cut name
of a SpriteSeqData record for other exact length-prefixed UTF-16 names
present in SpriteCutData.repo. This does NOT assume Stage158's proposed
64/82-byte stride or any animation frame layout.

Additional names are candidate lexical anchors only: matches may occur
in unrelated opaque fields. Count matches, compare their private
positions+tokens between original screen packs, and expose only coarse
cross-tabulated aggregate counts by header group and declared count
bucket. Never export original names, byte positions, payloads or raw
header words. CI uses fabricated paired records exclusively.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import (
    SCREENS, MAX_REPO_BYTES, MAX_WAD_BYTES, SpriteIndexFormatError,
    parse_sprite_repository, _text,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from .sprite_sequence_cut_name_candidates import (
    CUT_REPO, CUT_WAD, _source_token,
)
from .sprite_sequence_failure_strata import (
    _PREFIX_GROUPS, _COUNT_GROUPS, _count_group,
    summarize_sequence_firstword_failure_strata,
)
from .sprite_sequence_nested_grammar import MAX_SEQUENCE_BYTES

_PAIR = struct.Struct("<II")
_U32 = struct.Struct("<I")
_FIRST_CUT = 8 + 20 + 13
_MAX_ANCHORS = 512
_CLASSES = (
    "initial_cut_name_missing",
    "one_candidate_no_later_cut_name",
    "one_candidate_with_later_cut_name",
    "multi_candidate_no_later_cut_name",
    "multi_candidate_some_but_below_count",
    "multi_candidate_matches_count_minus_one",
    "multi_candidate_above_count_minus_one",
)


def _packed_cut_names(keys: frozenset[str]) -> dict[int, frozenset[bytes]]:
    """Use in-memory exact serialized tokens rather than guessed widths."""
    if not isinstance(keys, frozenset) or not keys:
        raise ValueError("Empty or invalid independently indexed cut keys")
    grouped: dict[int, set[bytes]] = {}
    for key in keys:
        if not isinstance(key, str) or not key:
            raise ValueError("Invalid cut key")
        if not (1 <= len(key) <= 128 and
                all(32 <= ord(ch) <= 126 for ch in key)):
            continue  # Stage157 only accepts bounded printable ASCII.
        grouped.setdefault(len(key), set()).add(
            struct.pack("<H", len(key)) + key.encode("utf-16le"))
    if not grouped:
        raise ValueError("No eligible source-cut UTF-16 tokens")
    return {n: frozenset(v) for n, v in grouped.items()}


def _scan_known_cut_anchors(
    record: bytes, after_first_name: int,
    packed: dict[int, frozenset[bytes]],
) -> tuple[tuple[int, bytes], ...]:
    """Private position+token pairs; never put them in a public report.

    Greedy non-overlapping scan. This is only a lexical diagnostic;
    neither the returned position nor a match implies a nested frame.
    """
    if (type(record) is not bytes or not 0 <= after_first_name <= len(record)-4
            or len(record) > MAX_SEQUENCE_BYTES):
        raise ValueError("Invalid bounded private sprite record")
    end = len(record)-4
    pos = after_first_name
    found: list[tuple[int, bytes]] = []
    while pos + 2 <= end:
        length = _U16.unpack_from(record, pos)[0]
        possible = packed.get(length)
        size = 2 + 2 * length
        if possible is not None and pos + size <= end:
            token = record[pos:pos+size]
            if token in possible:
                found.append((pos, token))
                if len(found) > _MAX_ANCHORS:
                    raise SpriteIndexFormatError(
                        "Excessive lexical anchors in source record")
                pos += size
                continue
        pos += 1
    return tuple(found)


_U16 = struct.Struct("<H")


def _lexical_class(count: int, first_known: bool, later_count: int) -> str:
    if not first_known:
        return "initial_cut_name_missing"
    if count == 1:
        return ("one_candidate_with_later_cut_name" if later_count else
                "one_candidate_no_later_cut_name")
    if later_count == 0:
        return "multi_candidate_no_later_cut_name"
    if later_count < count-1:
        return "multi_candidate_some_but_below_count"
    if later_count == count-1:
        return "multi_candidate_matches_count_minus_one"
    return "multi_candidate_above_count_minus_one"


def summarize_sequence_lexical_cut_anchor_scan(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Hypothesis-free scan, guarded by complete Stage159 source checks."""
    baseline = summarize_sequence_firstword_failure_strata(
        sequence_repos, sequence_wads, cut_repos)
    indexed_cuts = parse_sprite_repository(
        cut_repos[SCREENS[0]], expected_label="SpriteCutData",
        expected_wad=CUT_WAD)
    cut_keys = frozenset(row.key for row in indexed_cuts)
    packed = _packed_cut_names(cut_keys)
    indexed_sequences = parse_sprite_repository(
        sequence_repos[SCREENS[0]], expected_label="SpriteSeqData",
        expected_wad=WAD_PATH)
    paired = [_intervals(indexed_sequences, sequence_wads[s])
              for s in SCREENS]
    by_group = {
        word_group: {count_group: Counter() for count_group in _COUNT_GROUPS}
        for word_group in _PREFIX_GROUPS
    }

    for a, b in zip(*paired):
        names = []
        for record in (a, b):
            _, pos = _text(record, 0)
            _marker, count = _PAIR.unpack_from(record, pos)
            if count == 0:
                names.append(None)
                continue
            word = _U32.unpack_from(record, pos+8)[0]
            start = pos+_FIRST_CUT
            status, first = _source_token(record, start)
            if status == "valid" and first in cut_keys:
                end_of_first = start + 2 + 2*len(first)
                anchors = _scan_known_cut_anchors(record, end_of_first, packed)
                names.append((count, word, True, anchors))
            else:
                names.append((count, word, False, ()))

        if names[0] is None and names[1] is None:
            continue
        if names[0] is None or names[1] is None:
            raise SpriteIndexFormatError("Paired lexical candidate count differs")
        count_a, word_a, known_a, anchors_a = names[0]
        count_b, word_b, known_b, anchors_b = names[1]
        if (count_a != count_b or word_a != word_b or known_a != known_b):
            raise SpriteIndexFormatError("Paired lexical source fields diverged")

        word_group = ("first_u32_one" if word_a == 1
                      else "first_u32_other")
        bucket = by_group[word_group][_count_group(count_a)]
        bucket["records"] += 1
        classification = _lexical_class(
            count_a, known_a, len(anchors_a))
        bucket[classification] += 1
        # Differences are observations, not errors: the screen packs
        # can have distinct opaque suffix content.
        if known_a:
            key = ("later_anchor_lists_identical_across_packs"
                   if anchors_a == anchors_b
                   else "later_anchor_lists_differ_across_packs")
            bucket[key] += 1

    grouped_output = {}
    for word_group in _PREFIX_GROUPS:
        grouped_output[word_group] = {}
        for count_group in _COUNT_GROUPS:
            c = by_group[word_group][count_group]
            classes = {label: c[label] for label in _CLASSES}
            if sum(classes.values()) != c["records"]:
                raise SpriteIndexFormatError("Incomplete lexical anchor accounting")
            if (c["later_anchor_lists_identical_across_packs"] +
                c["later_anchor_lists_differ_across_packs"] !=
                c["records"] - c["initial_cut_name_missing"]):
                raise SpriteIndexFormatError("Incomplete paired anchor comparison")
            grouped_output[word_group][count_group] = {
                "records": c["records"],
                "candidate_lexical_anchor_classes": classes,
                "later_anchor_lists_identical_across_packs":
                    c["later_anchor_lists_identical_across_packs"],
                "later_anchor_lists_differ_across_packs":
                    c["later_anchor_lists_differ_across_packs"],
            }

    for word_group in _PREFIX_GROUPS:
        expected = baseline[
            "grammar_result_by_first_prefix_word"][word_group]
        actual = grouped_output[word_group]
        if sum(v["records"] for v in actual.values()) != sum(expected.values()):
            raise SpriteIndexFormatError("Stage159 firstword totals differ")
        missing = sum(v["candidate_lexical_anchor_classes"][
            "initial_cut_name_missing"] for v in actual.values())
        if missing != expected["no_independent_initial_cut_key"]:
            raise SpriteIndexFormatError("Stage159 missing cut-key count differs")
    return {
        "classification": "owner_private_width_free_sprite_cut_lexical_anchor_scan",
        "hypothetical_opaque_stride_required_for_scan": False,
        "bounded_maximum_name_anchor_count_per_record": _MAX_ANCHORS,
        "source_cut_registry_tokens_considered": sum(
            len(v) for v in packed.values()),
        "candidate_lexical_anchor_status_by_firstword_and_count":
            grouped_output,
        "paired_first_name_and_header_safety_reused": True,
        "source_sprite_animation_boundaries_verified": False,
        "source_unknown_count_proven_to_equal_child_names": False,
        "source_frame_duration_or_playback_verified": False,
        "automated_source_sprite_import_permitted": False,
        "source_names_header_values_offsets_and_bytes_exported": False,
    }


def audit_private_sequence_lexical_cut_anchor_scan(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive source ZIP members")
        lookup = {info.filename: info for info in infos}
        if len(lookup) != len(infos):
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
    return summarize_sequence_lexical_cut_anchor_scan(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    dest = private_output_path(args.out)
    report = audit_private_sequence_lexical_cut_anchor_scan(args.ipa)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print("Private width-free sprite cut lexical census saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
