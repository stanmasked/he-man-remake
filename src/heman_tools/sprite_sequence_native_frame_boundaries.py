"""Stage169: source-free reference for native SpritePlayer keyframe boundaries.

Independent owner-private ARMv7 control-flow evidence:
  SpritePlayer::buildKeyFrameTimeStamps allocates frame_count+1 integers,
  writes timestamp[0]=0, and accumulates SpriteFrame::getTime values.
  SpritePlayer::computeCurrentFrameIndex returns the frame whose
  interval [timestamp[i],timestamp[i+1]) contains nonnegative elapsed
  time; after total time it clamps to the last frame. Zero-duration
  intervals are skipped by the strict end boundary.

This narrowly models NONNEGATIVE elapsed time and index selection.
It deliberately does not model the separate loop/replay function,
actual image rendering, collision checks, or the upstream timebase.
Only synthesized frame-time values are used in public CI.
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
from .sprite_sequence_native_loader_structure import _parse_native_sequence
from .sprite_sequence_native_timing_ledger import (
    summarize_native_sequence_time_ledger,
)

_I32_MAX = (1 << 31) - 1
_MAX_FRAMES = 1024


def build_keyframe_boundaries(frame_times: tuple[int, ...]) -> tuple[int, ...]:
    """Return cumulative *native integer* ticks, including leading zero.

    Nonnegative times match the real original v2.0.0 source observations.
    A negative duration is left for a distinct verified runtime policy
    rather than accepting nonmonotonic frame boundaries silently.
    """
    if type(frame_times) is not tuple or len(frame_times) > _MAX_FRAMES:
        raise ValueError("Invalid bounded native frame time sequence")
    result = [0]
    for duration in frame_times:
        if type(duration) is not int or duration < 0 or duration > _I32_MAX:
            raise ValueError("Unsupported native frame duration")
        next_total = result[-1] + duration
        if next_total > _I32_MAX:
            raise ValueError("Native total duration exceeds signed i32")
        result.append(next_total)
    return tuple(result)


def frame_index_at_elapsed_ticks(
    boundaries: tuple[int, ...], elapsed_ticks: int,
) -> int:
    """Strict-right-boundary selection; clamped, with loop disabled.

    The original scan returns the first interval with end > elapsed
    for elapsed >= 0, otherwise the last frame. For a zero-frame
    sequence it returns -1.
    """
    if (type(boundaries) is not tuple or not boundaries or
            boundaries[0] != 0 or len(boundaries) > _MAX_FRAMES + 1
            or type(elapsed_ticks) is not int or
            not 0 <= elapsed_ticks <= _I32_MAX or
            any(type(v) is not int or v < 0 or v > _I32_MAX
                for v in boundaries) or
            any(b < a for a, b in zip(boundaries, boundaries[1:]))):
        raise ValueError("Invalid nonnegative native keyframe boundary query")
    number_of_frames = len(boundaries) - 1
    if not number_of_frames:
        return -1
    for frame_index in range(number_of_frames):
        if elapsed_ticks < boundaries[frame_index + 1]:
            return frame_index
    return number_of_frames - 1


def summarize_native_frame_boundary_controls(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Validate all original intervals without exporting any frame traces."""
    parent = summarize_native_sequence_time_ledger(
        sequence_repos, sequence_wads, cut_repos,
    )
    index = parse_sprite_repository(
        sequence_repos[SCREENS[0]],
        expected_label="SpriteSeqData", expected_wad=WAD_PATH,
    )
    private_sequences = []
    censes = []
    for screen in SCREENS:
        rows = _intervals(index, sequence_wads[screen])
        local = []
        counters = Counter()
        for entry, row in zip(index, rows):
            seq = _parse_native_sequence(row)
            if seq.key != entry.key:
                raise SpriteIndexFormatError("Native source index mismatch")
            values = tuple(f.numerical_header[1] for f in seq.frames)
            try:
                bounds = build_keyframe_boundaries(values)
            except ValueError as exc:
                raise SpriteIndexFormatError(
                    "Native source time bounds are not yet supported"
                ) from exc
            if len(bounds) != len(seq.frames) + 1:
                raise SpriteIndexFormatError("Native frame boundaries incomplete")
            start = frame_index_at_elapsed_ticks(bounds, 0)
            at_end = frame_index_at_elapsed_ticks(bounds, bounds[-1])
            if at_end != len(seq.frames) - 1:
                raise SpriteIndexFormatError("Original last-frame clamp disagrees")
            local.append((len(values), bounds, start))
            counters["sequences"] += 1
            counters["frames"] += len(values)
            counters["empty_sequences"] += not values
            counters["sequences_with_zero_duration_frames"] += any(
                value == 0 for value in values
            )
            counters["zero_duration_frames"] += sum(value == 0 for value in values)
            counters["single_frame_sequences"] += len(values) == 1
            counters["two_or_more_frame_sequences"] += len(values) >= 2
            counters["sequences_starting_on_frame_zero"] += (
                bool(values) and start == 0
            )
            counters["sequences_skipping_initial_zero_frames"] += (
                bool(values) and start > 0
            )
            counters["sequences_with_positive_total"] += bounds[-1] > 0
            counters["sequences_with_zero_total"] += bounds[-1] == 0
            counters["last_frame_clamp_confirmed"] += True
        censes.append(counters)
        private_sequences.append(local)

    pair_counters = Counter()
    for a, b in zip(*private_sequences):
        if a[0] != b[0]:
            raise SpriteIndexFormatError("Paired original frame counts differ")
        pair_counters["sequences_with_same_total_native_ticks"] += (
            a[1][-1] == b[1][-1]
        )
        pair_counters["sequences_with_identical_cumulative_boundaries"] += (
            a[1] == b[1]
        )
        pair_counters["sequences_with_different_cumulative_boundaries"] += (
            a[1] != b[1]
        )
        pair_counters["sequences_with_same_start_frame"] += a[2] == b[2]

    exported = {}
    for i, screen in enumerate(SCREENS):
        expected = parent["per_source_resolution_pack"][screen]
        c = censes[i]
        if c["sequences"] != expected["sequence_records"] or (
                c["frames"] != expected["frame_records"]
                or c["empty_sequences"] != expected["empty_sequences"]):
            raise SpriteIndexFormatError("Stage168 source ledger counts differ")
        if c["zero_duration_frames"] != expected[
                "frame_time_value_buckets"]["zero"]:
            raise SpriteIndexFormatError("Stage168 zero-time controls differ")
        if c["sequences_with_positive_total"] != expected[
                "sequences_with_positive_total_time"]:
            raise SpriteIndexFormatError("Stage168 cumulative time totals differ")
        exported[screen] = dict(c)

    if sum(pair_counters[k] for k in (
            "sequences_with_identical_cumulative_boundaries",
            "sequences_with_different_cumulative_boundaries",
    )) != censes[0]["sequences"]:
        raise SpriteIndexFormatError("Paired cumulative time counts incomplete")
    if pair_counters[
            "sequences_with_identical_cumulative_boundaries"] != parent[
                "paired_resolution_comparison"][
                    "sequences_with_identical_frame_time_values"]:
        raise SpriteIndexFormatError("Stage168 cross-resolution time parity differs")

    return {
        "classification": "owner_private_native_sprite_cumulative_frame_boundaries",
        "per_original_resolution_pack": exported,
        "paired_resolution_evidence": dict(pair_counters),
        "stage168_timing_and_stage167_source_index_reconciled": True,
        "native_cumulative_boundaries_start_at_zero": True,
        "frame_intervals_use_strict_exclusive_right_edge": True,
        "zero_duration_frames_skipped_on_nonnegative_elapsed": True,
        "index_after_end_clamped_to_last_without_looping": True,
        "upstream_tick_timescale_in_seconds_verified": False,
        "negative_elapsed_and_negative_frame_policy_verified": False,
        "infinite_finite_loop_replay_semantics_implemented": False,
        "sprite_rendering_and_actor_hitbox_parity_verified": False,
        "raw_frame_timestamps_source_names_images_or_offsets_exported": False,
    }


def audit_private_native_frame_boundary_controls(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as z:
        entries = z.infolist()
        if len(entries) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        lookup = {entry.filename: entry for entry in entries}
        if len(lookup) != len(entries):
            raise ValueError("Duplicate original ZIP member")
        repos, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            root = PREFIX + screen + "/"
            repos[screen] = _safe_read(
                z, lookup.get(root + REPO_PATH), MAX_REPO_BYTES
            )
            wads[screen] = _safe_read(
                z, lookup.get(root + WAD_PATH), MAX_WAD_BYTES
            )
            cuts[screen] = _safe_read(
                z, lookup.get(root + CUT_REPO), MAX_REPO_BYTES
            )
    return summarize_native_frame_boundary_controls(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    target = private_output_path(args.out)
    summary = audit_private_native_frame_boundary_controls(args.ipa)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Private native frame-boundary audit saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
