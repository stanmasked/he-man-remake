"""Stage168: private native frame-time ledger and paired-resolution checks.

Original ARMv7 SpriteFrame::getTime exposes the second signed 32-bit
frame header field. SpriteSequence::getAnimationTime sums this field.
The saved integer is *not* necessarily a known number of milliseconds:
no runtime timebase or gameplay timing is claimed by this module.

Public output comprises only coarse counts; names, original values,
per-sequence traces, raw WADs and object references remain private.
Synthetic-only fixtures are used in GitHub CI.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read
from .sprite_repo_wad_index import (
    SCREENS, MAX_REPO_BYTES, MAX_WAD_BYTES, SpriteIndexFormatError,
    parse_sprite_repository,
)
from .sprite_wad_record_intervals import _intervals
from .sprite_sequence_header_controls import REPO_PATH, WAD_PATH
from .sprite_sequence_cut_name_candidates import CUT_REPO
from .sprite_sequence_native_loader_structure import (
    _parse_native_sequence, summarize_native_sequence_loader_structure,
)

_I32_MIN = -(1 << 31)
_I32_MAX = (1 << 31) - 1
_TIME_CLASSES = ("negative", "zero", "one_to_nine",
                 "ten_to_ninety_nine", "hundred_to_nine_ninety_nine",
                 "one_thousand_or_more")
_FIELD_SIGNS = ("negative", "zero", "positive")
_BOOL_CATEGORIES = ("zero", "one", "other_nonzero")


def _time_bucket(value: int) -> str:
    if type(value) is not int:
        raise ValueError("Invalid signed native time")
    if value < 0:
        return "negative"
    if value == 0:
        return "zero"
    if value < 10:
        return "one_to_nine"
    if value < 100:
        return "ten_to_ninety_nine"
    if value < 1000:
        return "hundred_to_nine_ninety_nine"
    return "one_thousand_or_more"


def _sign(value: int) -> str:
    if type(value) is not int:
        raise ValueError("Invalid signed native header field")
    return "negative" if value < 0 else "zero" if value == 0 else "positive"


def _bool_category(value: int) -> str:
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError("Invalid native boolean byte")
    return "zero" if value == 0 else "one" if value == 1 else "other_nonzero"


def summarize_native_sequence_time_ledger(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Strict source-only totals, never source strings/record-level duration."""
    baseline = summarize_native_sequence_loader_structure(
        sequence_repos, sequence_wads, cut_repos,
    )
    index = parse_sprite_repository(
        sequence_repos[SCREENS[0]], expected_label="SpriteSeqData",
        expected_wad=WAD_PATH,
    )
    packed = [_intervals(index, sequence_wads[s]) for s in SCREENS]
    seq_counts = []
    time_counts = []
    bool_counts = []
    total_time_counts = []
    sequences = []
    for screen_records in packed:
        stats, times, bools, totals = Counter(), Counter(), Counter(), Counter()
        parsed = []
        for indexed, record in zip(index, screen_records):
            seq = _parse_native_sequence(record)
            if seq.key != indexed.key:
                raise SpriteIndexFormatError("Native sequence index differs")
            parsed.append(seq)
            stats["sequences"] += 1
            stats["empty_sequences"] += len(seq.frames) == 0
            stats["loop_" + _sign(seq.loop_field)] += 1
            stats["third_" + _sign(seq.third_field)] += 1

            frame_values = [f.numerical_header[1] for f in seq.frames]
            duration_sum = sum(frame_values)
            if not (_I32_MIN <= duration_sum <= _I32_MAX):
                stats["total_exceeds_signed_32_bit"] += 1
            totals[_time_bucket(duration_sum)] += 1
            stats["sequences_with_any_zero_time_frame"] += any(
                t == 0 for t in frame_values
            )
            stats["nonempty_sequences_with_all_zero_time_frames"] += (
                bool(frame_values) and all(t == 0 for t in frame_values)
            )
            stats["sequences_with_any_negative_time_frame"] += any(
                t < 0 for t in frame_values
            )
            stats["sequences_with_positive_total_time"] += duration_sum > 0
            stats["third_field_equals_sum_of_frame_times"] += (
                seq.third_field == duration_sum
            )

            for f in seq.frames:
                stats["frames"] += 1
                times[_time_bucket(f.numerical_header[1])] += 1
                bools[_bool_category(f.boolean_byte)] += 1
        seq_counts.append(stats)
        time_counts.append(times)
        bool_counts.append(bools)
        total_time_counts.append(totals)
        sequences.append(parsed)

    if seq_counts[0] != seq_counts[1]:
        # Some time-derived values may legitimately differ between screen
        # packs. Structural counters alone are compared below.
        structural = ("sequences", "empty_sequences", "frames")
        if any(seq_counts[0][k] != seq_counts[1][k] for k in structural):
            raise SpriteIndexFormatError("Paired native time census structure differs")

    census = baseline["per_original_resolution_pack"]
    for side in (0, 1):
        if seq_counts[side]["sequences"] != census["sequence_records"]:
            raise SpriteIndexFormatError("Stage167 source sequence total differs")
        if seq_counts[side]["frames"] != census["frames"]:
            raise SpriteIndexFormatError("Stage167 source frame total differs")
        if seq_counts[side]["empty_sequences"] != census["zero_frame_records"]:
            raise SpriteIndexFormatError("Stage167 source empty-sequence total differs")
        if sum(time_counts[side].values()) != census["frames"]:
            raise SpriteIndexFormatError("Missing native frame time category")
        if sum(bool_counts[side].values()) != census["frames"]:
            raise SpriteIndexFormatError("Missing native frame bool category")
        if sum(total_time_counts[side].values()) != census["sequence_records"]:
            raise SpriteIndexFormatError("Missing native total time category")

    comparisons = Counter()
    for a, b in zip(*sequences):
        if len(a.frames) != len(b.frames):
            raise SpriteIndexFormatError("Paired native frame counts differ")
        ta = tuple(f.numerical_header[1] for f in a.frames)
        tb = tuple(f.numerical_header[1] for f in b.frames)
        ba = tuple(f.boolean_byte for f in a.frames)
        bb = tuple(f.boolean_byte for f in b.frames)
        comparisons["sequences_with_identical_frame_time_values"] += ta == tb
        comparisons["sequences_with_any_frame_time_difference"] += ta != tb
        comparisons["individual_frame_time_differences"] += sum(
            x != y for x, y in zip(ta, tb)
        )
        comparisons["sequences_with_identical_bool_values"] += ba == bb
        comparisons["sequences_with_any_bool_difference"] += ba != bb
        comparisons["sequences_with_same_total_time"] += sum(ta) == sum(tb)

    if sum(comparisons[k] for k in (
            "sequences_with_identical_frame_time_values",
            "sequences_with_any_frame_time_difference",
    )) != census["sequence_records"]:
        raise SpriteIndexFormatError("Paired native timing counts incomplete")
    if sum(comparisons[k] for k in (
            "sequences_with_identical_bool_values",
            "sequences_with_any_bool_difference",
    )) != census["sequence_records"]:
        raise SpriteIndexFormatError("Paired native boolean counts incomplete")

    per_pack = {}
    for side, screen in enumerate(SCREENS):
        stats = seq_counts[side]
        per_pack[screen] = {
            "sequence_records": stats["sequences"],
            "frame_records": stats["frames"],
            "empty_sequences": stats["empty_sequences"],
            "frame_time_value_buckets": {
                k: time_counts[side][k] for k in _TIME_CLASSES
            },
            "sequence_total_time_buckets": {
                k: total_time_counts[side][k] for k in _TIME_CLASSES
            },
            "frame_bool_byte_buckets": {
                k: bool_counts[side][k] for k in _BOOL_CATEGORIES
            },
            "sequence_loop_field_sign_buckets": {
                k: stats["loop_"+k] for k in _FIELD_SIGNS
            },
            "sequence_third_field_sign_buckets": {
                k: stats["third_"+k] for k in _FIELD_SIGNS
            },
            "sequences_with_any_zero_time_frame":
                stats["sequences_with_any_zero_time_frame"],
            "nonempty_sequences_with_all_zero_time_frames":
                stats["nonempty_sequences_with_all_zero_time_frames"],
            "sequences_with_any_negative_time_frame":
                stats["sequences_with_any_negative_time_frame"],
            "sequences_with_positive_total_time":
                stats["sequences_with_positive_total_time"],
            "sequences_whose_total_exceeds_signed_32_bit":
                stats["total_exceeds_signed_32_bit"],
            "sequence_third_field_equals_frame_time_sum":
                stats["third_field_equals_sum_of_frame_times"],
        }

    return {
        "classification": "owner_private_native_sprite_frame_time_ledger",
        "per_source_resolution_pack": per_pack,
        "paired_resolution_comparison": dict(comparisons),
        "stage167_source_structure_reconciled": True,
        "frame_time_is_second_native_frame_header_integer": True,
        "original_getAnimationTime_sums_frame_time_values": True,
        "signed_int32_overflow_checked": True,
        "zero_frame_time_is_not_silently_discarded": True,
        "milliseconds_per_time_unit_calibrated": False,
        "playback_tick_looping_policy_validated": False,
        "source_art_or_runtime_state_import_enabled": False,
        "raw_time_values_names_positions_images_or_traces_exported": False,
    }


def audit_private_native_sequence_time_ledger(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        lookup = {i.filename: i for i in infos}
        if len(lookup) != len(infos):
            raise ValueError("Duplicate original ZIP member")
        seq_repo, seq_wad, cut_repo = {}, {}, {}
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            seq_repo[screen] = _safe_read(
                archive, lookup.get(root + REPO_PATH), MAX_REPO_BYTES
            )
            seq_wad[screen] = _safe_read(
                archive, lookup.get(root + WAD_PATH), MAX_WAD_BYTES
            )
            cut_repo[screen] = _safe_read(
                archive, lookup.get(root + CUT_REPO), MAX_REPO_BYTES
            )
    return summarize_native_sequence_time_ledger(seq_repo, seq_wad, cut_repo)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    output = private_output_path(args.out)
    result = audit_private_native_sequence_time_ledger(args.ipa)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Owner-private native sprite frame-time aggregates written locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
