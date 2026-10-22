"""Stage165: owner-private modular geometry of lexical sprite-cut anchors.

Measure gaps after *indexed* length-prefixed sprite-cut names, including
the final opaque suffix before the independently validated terminal u32.
Compare the previously proposed stride 82 with adjacent 81 and 83 as
falsification controls. Neither a name nor a matching width is a proven
frame boundary. Original names, gap sequences, offsets, bytes, raw header
words and per-record data remain exclusively in private memory.
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
    _text, parse_sprite_repository,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from .sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD, _source_token
from .sprite_sequence_cut_anchor_scan import (
    _FIRST_CUT, _packed_cut_names, _scan_known_cut_anchors,
)
from .sprite_sequence_failure_strata import _PREFIX_GROUPS, _COUNT_GROUPS, _count_group
from .sprite_sequence_cut_decoy_controls import summarize_sequence_cut_decoy_controls

_HEAD = struct.Struct("<II")
_U32 = struct.Struct("<I")
_STRIDE = 82
_ADJACENT_STRIDES = (81, 82, 83)
_GAP_BASES = (76, 97, 118)
_GAP_LABELS = ("gap_76_plus_82n", "gap_97_plus_82n",
               "gap_118_plus_82n", "other_gap")
_TAIL_LABELS = ("tail_64_plus_82n", "other_tail")


def _gap_class(length: int) -> str:
    if type(length) is not int or length < 0:
        raise ValueError("Invalid private lexical gap")
    for base, label in zip(_GAP_BASES, _GAP_LABELS):
        if length >= base and (length - base) % _STRIDE == 0:
            return label
    return "other_gap"


def _tail_class(length: int) -> str:
    if type(length) is not int or length < 0:
        raise ValueError("Invalid private tail length")
    if length >= 64 and (length - 64) % _STRIDE == 0:
        return "tail_64_plus_82n"
    return "other_tail"


def _paired_name_geometry(
    record: bytes, after_record_name: int,
    keys: frozenset[str], packed: dict[int, frozenset[bytes]],
) -> tuple[tuple[int, ...], int] | None:
    """Extract private gap lengths; NOT animation duration/frame slices."""
    at = after_record_name + _FIRST_CUT
    status, first_key = _source_token(record, at)
    if status != "valid" or first_key not in keys:
        return None
    previous = at + 2 + 2 * len(first_key)
    gaps = []
    for position, token in _scan_known_cut_anchors(record, previous, packed):
        if position < previous:
            raise SpriteIndexFormatError("Overlapping lexical source anchors")
        gaps.append(position - previous)
        previous = position + len(token)
    tail = len(record) - 4 - previous
    if tail < 0:
        raise SpriteIndexFormatError("Lexical anchor overlaps source trailer")
    return tuple(gaps), tail


def summarize_sequence_modular_anchor_geometry(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Verify Stage164 paired sources and reconcile source-only geometry."""
    parent = summarize_sequence_cut_decoy_controls(
        sequence_repos, sequence_wads, cut_repos
    )
    index = parse_sprite_repository(
        sequence_repos[SCREENS[0]],
        expected_label="SpriteSeqData", expected_wad=WAD_PATH,
    )
    cut_index = parse_sprite_repository(
        cut_repos[SCREENS[0]],
        expected_label="SpriteCutData", expected_wad=CUT_WAD,
    )
    keys = frozenset(row.key for row in cut_index)
    packed = _packed_cut_names(keys)
    spans = [_intervals(index, sequence_wads[s]) for s in SCREENS]
    buckets = {
        word: {count: Counter() for count in _COUNT_GROUPS}
        for word in _PREFIX_GROUPS
    }

    for first, second in zip(*spans):
        pair = []
        for rec in (first, second):
            _, name_end = _text(rec, 0)
            count = _HEAD.unpack_from(rec, name_end)[1]
            if count == 0:
                pair.append(None)
                continue
            word = _U32.unpack_from(rec, name_end + 8)[0]
            geometry = _paired_name_geometry(rec, name_end, keys, packed)
            pair.append((count, word, geometry))
        if pair[0] is None and pair[1] is None:
            continue
        if pair[0] is None or pair[1] is None:
            raise SpriteIndexFormatError("Mismatched source nonzero counts")
        count_a, word_a, geo_a = pair[0]
        count_b, word_b, geo_b = pair[1]
        if (count_a != count_b or word_a != word_b or
                (geo_a is None) != (geo_b is None)):
            raise SpriteIndexFormatError("Paired source lexical headers differ")
        if geo_a is None:
            continue
        category = "first_u32_one" if word_a == 1 else "first_u32_other"
        entry = buckets[category][_count_group(count_a)]
        entry["known_first_cut_records"] += 1
        gaps_a, tail_a = geo_a
        entry["indexed_secondary_name_intervals"] += len(gaps_a)
        entry["has_secondary_name"] += bool(gaps_a)
        entry["gap_geometries_agree_between_source_packs"] += geo_a == geo_b
        entry[_tail_class(tail_a)] += 1
        for gap in gaps_a:
            entry[_gap_class(gap)] += 1

        # A tail of exactly 64 bytes is a nondiscriminating baseline;
        # test only tails longer than that against 81, 82 and 83.
        if tail_a > 64:
            entry["tail_longer_than_64"] += 1
            for stride in _ADJACENT_STRIDES:
                entry[f"long_tail_64_plus_{stride}n"] += (
                    (tail_a - 64) % stride == 0
                )

    parent_groups = parent["controls_by_firstword_and_unknown_count"]
    report = {}
    for group in _PREFIX_GROUPS:
        report[group] = {}
        for count in _COUNT_GROUPS:
            c = buckets[group][count]
            upstream = parent_groups[group][count]
            if c["known_first_cut_records"] != upstream[
                "known_first_cut_records"
            ]:
                raise SpriteIndexFormatError("Stage164 first-name totals differ")
            if sum(c[k] for k in _TAIL_LABELS) != c["known_first_cut_records"]:
                raise SpriteIndexFormatError("Missing source tail geometry")
            if sum(c[k] for k in _GAP_LABELS) != c[
                "indexed_secondary_name_intervals"
            ]:
                raise SpriteIndexFormatError("Missing source gap geometry")
            if c["has_secondary_name"] != upstream[
                "real_later_cut_in_first_screen"
            ]:
                raise SpriteIndexFormatError("Stage164 secondary-name totals differ")
            report[group][count] = {
                "known_first_cut_records": c["known_first_cut_records"],
                "records_with_secondary_indexed_names": c["has_secondary_name"],
                "inter_name_gap_count": c["indexed_secondary_name_intervals"],
                "inter_name_gap_modular_classes": {
                    label: c[label] for label in _GAP_LABELS
                },
                "terminal_gap_modular_classes": {
                    label: c[label] for label in _TAIL_LABELS
                },
                "tails_longer_than_base_64": c["tail_longer_than_64"],
                "nonbaseline_tail_hits_by_stride": {
                    str(s): c[f"long_tail_64_plus_{s}n"]
                    for s in _ADJACENT_STRIDES
                },
                "gap_geometry_identical_across_screen_packs":
                    c["gap_geometries_agree_between_source_packs"],
            }
    return {
        "classification": "owner_private_sprite_cut_anchor_modular_geometry",
        "hypothesis_stride_bytes": _STRIDE,
        "negative_control_strides": list(_ADJACENT_STRIDES),
        "hypothesis_intername_gap_bases": list(_GAP_BASES),
        "hypothesis_terminal_tail_base": 64,
        "by_firstword_and_declared_count": report,
        "stage164_independent_registered_name_controls_reconciled": True,
        "lexical_anchor_locations_proven_frame_boundaries": False,
        "modular_widths_prove_animation_timing": False,
        "original_sprite_import_to_switch_permitted": False,
        "raw_names_values_positions_gap_series_or_bytes_exported": False,
    }


def audit_private_sequence_modular_anchor_geometry(ipa: Path) -> dict:
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
                archive, lookup.get(root + REPO_PATH), MAX_REPO_BYTES
            )
            wads[screen] = _safe_read(
                archive, lookup.get(root + WAD_PATH), MAX_WAD_BYTES
            )
            cuts[screen] = _safe_read(
                archive, lookup.get(root + CUT_REPO), MAX_REPO_BYTES
            )
    return summarize_sequence_modular_anchor_geometry(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    target = private_output_path(args.out)
    summary = audit_private_sequence_modular_anchor_geometry(args.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Owner-private sprite anchor gap geometry stored locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
