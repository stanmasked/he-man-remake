"""Stage161: owner-private paired-screen opaque sprite-suffix parity census.

For *single-candidate* original sequences only, compare bytes after
the independently indexed first cut key and before the established
terminal u32. Bucket by first header u32 == 1 vs != 1 and Stage159
coarse residual motifs. The actual bytes, names, offsets, differing
positions, per-record results and raw header values remain private.

Matching suffix bytes would not prove a frame layout or identify
timing; differing bytes would not independently establish pixel data.
The public tests use fabricated paired screen packs exclusively.
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
from .sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD, _source_token
from .sprite_sequence_failure_strata import (
    _PREFIX_GROUPS, _TAIL_GROUPS,
    summarize_sequence_firstword_failure_strata,
)
from .sprite_sequence_nonunit_header_associations import _motif

_HEAD = struct.Struct("<II")
_U32 = struct.Struct("<I")
_CUT_OFFSET_AFTER_KEY = 8 + 20 + 13
_DELTA_BANDS = ("identical", "changed_1_4", "changed_5_16",
                "changed_17_64", "changed_65_plus")


def _delta_band(first: bytes, second: bytes) -> str:
    """Only a coarse comparison; never return changed positions or bytes."""
    if type(first) is not bytes or type(second) is not bytes:
        raise ValueError("Invalid private opaque suffix pair")
    if len(first) != len(second):
        raise SpriteIndexFormatError("Paired source suffix lengths disagree")
    changed = sum(a != b for a, b in zip(first, second))
    if not changed:
        return "identical"
    if changed <= 4:
        return "changed_1_4"
    if changed <= 16:
        return "changed_5_16"
    if changed <= 64:
        return "changed_17_64"
    return "changed_65_plus"


def _cut_suffix(record: bytes, position: int,
                cut_keys: frozenset[str]) -> tuple[str, bytes | None]:
    """Read a private single-candidate tail without decoding its semantics."""
    status, token = _source_token(record, position)
    if status != "valid" or token not in cut_keys:
        return "initial_name_missing", None
    end = position + 2 + 2 * len(token)
    if end > len(record) - 4:
        raise SpriteIndexFormatError("Known source token crosses final u32")
    suffix = record[end:-4]
    return _motif(len(suffix)), suffix


def summarize_sequence_single_suffix_screen_parity(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Compare paired opaque suffixes; return aggregates with strict totals."""
    baseline = summarize_sequence_firstword_failure_strata(
        sequence_repos, sequence_wads, cut_repos
    )
    cut_rows = parse_sprite_repository(
        cut_repos[SCREENS[0]], expected_label="SpriteCutData",
        expected_wad=CUT_WAD,
    )
    cut_keys = frozenset(row.key for row in cut_rows)
    seq_rows = parse_sprite_repository(
        sequence_repos[SCREENS[0]], expected_label="SpriteSeqData",
        expected_wad=WAD_PATH,
    )
    spans = [_intervals(seq_rows, sequence_wads[screen])
             for screen in SCREENS]
    counts = {group: {motif: Counter() for motif in _TAIL_GROUPS}
              for group in _PREFIX_GROUPS}

    for first, second in zip(*spans):
        _, first_pos = _text(first, 0)
        _, second_pos = _text(second, 0)
        first_count = _HEAD.unpack_from(first, first_pos)[1]
        second_count = _HEAD.unpack_from(second, second_pos)[1]
        if first_count != second_count:
            raise SpriteIndexFormatError("Paired sprite candidate counts differ")
        if first_count != 1:
            continue
        first_word = _U32.unpack_from(first, first_pos + 8)[0]
        second_word = _U32.unpack_from(second, second_pos + 8)[0]
        if first_word != second_word:
            raise SpriteIndexFormatError("Paired first prefix words differ")
        group = "first_u32_one" if first_word == 1 else "first_u32_other"
        motif_a, suffix_a = _cut_suffix(
            first, first_pos + _CUT_OFFSET_AFTER_KEY, cut_keys)
        motif_b, suffix_b = _cut_suffix(
            second, second_pos + _CUT_OFFSET_AFTER_KEY, cut_keys)
        if motif_a != motif_b or ((suffix_a is None) != (suffix_b is None)):
            raise SpriteIndexFormatError("Paired sprite suffix motif differs")
        bucket = counts[group][motif_a]
        bucket["records"] += 1
        if suffix_a is not None:
            bucket[_delta_band(suffix_a, suffix_b)] += 1

    expected = baseline[
        "single_candidate_initial_name_suffix_motifs_by_first_word"
    ]
    for group in _PREFIX_GROUPS:
        for motif in _TAIL_GROUPS:
            if counts[group][motif]["records"] != expected[group][motif]:
                raise SpriteIndexFormatError("Paired suffix census mismatch")

    report = {}
    for group in _PREFIX_GROUPS:
        report[group] = {}
        for motif in _TAIL_GROUPS:
            counter = counts[group][motif]
            report[group][motif] = {
                "records": counter["records"],
                "compared_pairs": sum(counter[label] for label in _DELTA_BANDS),
                "screen_suffix_difference_bands": {
                    label: counter[label] for label in _DELTA_BANDS
                },
            }
            if motif != "initial_name_missing" and (
                report[group][motif]["compared_pairs"] != counter["records"]
            ):
                raise SpriteIndexFormatError("Incomplete suffix comparisons")
    return {
        "classification":
            "owner_private_single_sequence_suffix_cross_screen_parity",
        "single_candidate_known_cut_suffix_screen_pair_census": report,
        "all_original_screen_pack_source_checks_reused": True,
        "unknown_cut_names_never_treated_as_suffixes": True,
        "no_per_record_or_changed_byte_positions_exported": True,
        "no_raw_sprite_bytes_names_fields_or_exact_suffix_lengths_exported": True,
        "identical_suffix_proves_metadata_or_frame_layout": False,
        "different_suffix_proves_graphics_pixels": False,
        "original_frame_count_or_timing_decoded": False,
        "switch_original_sprite_import_allowed": False,
    }


def audit_private_sequence_single_suffix_screen_parity(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        lookup = {info.filename: info for info in members}
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
    return summarize_sequence_single_suffix_screen_parity(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    path = private_output_path(args.out)
    report = audit_private_sequence_single_suffix_screen_parity(args.ipa)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print("Private paired-screen sprite suffix comparison saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
