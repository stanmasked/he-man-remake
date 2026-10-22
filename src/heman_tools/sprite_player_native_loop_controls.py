"""Stage170: bounded source-free native SpritePlayer replay decision oracle.

Owner-private ARMv7 evidence: SpritePlayer::advancedFrameIndex calls
SpriteSequence::getNumberOfFrames and uses the current index plus one
modulo frame count; at the total timestamp it either holds the final
frame (no replay remaining) or subtracts the full animation duration
and decrements the finite replay counter. A negative sequence loop
setting skips that decrement. SpritePlayer::isFinished uses a STRICT
'elapsed > end-of-current-frame' comparison, not >=, plus zero remaining
replays. The original 'reset' copies the sequence loop field to the
remaining-replay counter.

This reference models the indexed nonnegative elapsed-time path only.
It is NOT a complete runtime engine, texture animator or tick policy.
No original asset, frame trace, disassembly or per-record value belongs
in public GitHub; original source audit exports coarse counts only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
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
from .sprite_sequence_native_frame_boundaries import (
    build_keyframe_boundaries,
    summarize_native_frame_boundary_controls,
)

_I32_MAX = (1 << 31) - 1
_MAX_STEPS = 16384


@dataclass(frozen=True)
class NativePlayerState:
    frame_index: int
    elapsed_ticks: int
    remaining_replays: int


def _validate_state(
    boundaries: tuple[int, ...], loop_setting: int,
    state: NativePlayerState,
) -> int:
    if (not isinstance(state, NativePlayerState)
            or type(loop_setting) is not int
            or not -(1 << 31) <= loop_setting <= _I32_MAX
            or type(state.frame_index) is not int
            or type(state.elapsed_ticks) is not int
            or not 0 <= state.elapsed_ticks <= _I32_MAX
            or type(state.remaining_replays) is not int
            or not -(1 << 31) <= state.remaining_replays <= _I32_MAX
            or type(boundaries) is not tuple or not boundaries
            or boundaries[0] != 0
            or any(type(v) is not int or not 0 <= v <= _I32_MAX
                   for v in boundaries)
            or any(a > b for a, b in zip(boundaries, boundaries[1:]))):
        raise ValueError("Invalid bounded native player state")
    n = len(boundaries) - 1
    if n > 1024 or not (state.frame_index == -1 if n == 0
                        else 0 <= state.frame_index < n):
        raise ValueError("Native frame index out of range")
    if loop_setting < 0 and state.remaining_replays != loop_setting:
        raise ValueError("Infinite-loop remaining counter diverged")
    if loop_setting >= 0 and not 0 <= state.remaining_replays <= loop_setting:
        raise ValueError("Finite replay count out of bounds")
    return n


def is_native_finished(
    boundaries: tuple[int, ...], loop_setting: int, state: NativePlayerState,
) -> bool:
    """Original player's source-attached, nonnegative-time finish gate.

    A missing resource is a separate case, not represented by these
    arrays. An empty sequence is considered finished. For nonempty,
    finish only when currently on last frame, elapsed is strictly
    *greater than* that frame's right boundary, and no replay remains.
    """
    n = _validate_state(boundaries, loop_setting, state)
    if n == 0:
        return True
    if state.frame_index != n - 1:
        return False
    return (state.elapsed_ticks > boundaries[state.frame_index + 1]
            and state.remaining_replays == 0)


def advance_native_player(
    boundaries: tuple[int, ...], loop_setting: int,
    state: NativePlayerState, *, max_steps: int = _MAX_STEPS,
) -> NativePlayerState:
    """Reproduce bounded advancedFrameIndex decisions, with no tick input.

    Caller supplies an already accumulated nonnegative signed time
    from original calc(); pure time conversion is deliberately excluded.

    This is *not* a safe playback scheduler for zero-total unbounded
    replay: impossible progress and excessive iterations fail closed.
    """
    n = _validate_state(boundaries, loop_setting, state)
    if type(max_steps) is not int or not 1 <= max_steps <= _MAX_STEPS:
        raise ValueError("Invalid native bounded transition budget")
    if n == 0:
        return state
    total = boundaries[-1]
    previous = state.frame_index
    next_index = (previous + 1) % n
    elapsed = state.elapsed_ticks
    remaining = state.remaining_replays
    for _ in range(max_steps):
        if next_index <= previous:
            # A wrap at the final frame is not a replay yet when the
            # timestamp is still before the *total* boundary.
            if elapsed < total:
                next_index = n  # original end sentinel
            else:
                if loop_setting >= 0:
                    if remaining == 0:
                        break
                    remaining -= 1
                if total == 0:
                    raise ValueError("Zero-duration native replay cannot progress")
                elapsed -= total

        if elapsed < boundaries[next_index]:
            break
        previous = next_index
        next_index = (next_index + 1) % n
    else:
        raise ValueError("Native player transition budget exhausted")
    return NativePlayerState(previous, elapsed, remaining)


def summarize_native_player_loop_controls(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Check native loop-field classes in both packs, export counts only."""
    parent = summarize_native_frame_boundary_controls(
        sequence_repos, sequence_wads, cut_repos,
    )
    index = parse_sprite_repository(
        sequence_repos[SCREENS[0]],
        expected_label="SpriteSeqData", expected_wad=WAD_PATH,
    )
    censes = []
    for screen in SCREENS:
        counters = Counter()
        for row, record in zip(
                index, _intervals(index, sequence_wads[screen])):
            seq = _parse_native_sequence(record)
            if row.key != seq.key:
                raise SpriteIndexFormatError("Native resource lookup differs")
            try:
                boundaries = build_keyframe_boundaries(
                    tuple(f.numerical_header[1] for f in seq.frames)
                )
            except ValueError as exc:
                raise SpriteIndexFormatError("Unsupported private native time") from exc
            loop = seq.loop_field
            state = NativePlayerState(-1 if not seq.frames else 0, 0, loop)
            count = len(seq.frames)
            counters["sequences"] += 1
            counters["sequences_with_no_frames"] += count == 0
            counters["infinite_replay_settings"] += loop < 0
            counters["zero_replay_settings"] += loop == 0
            counters["positive_finite_replay_settings"] += loop > 0
            counters["initially_finished"] += is_native_finished(
                boundaries, loop, state)
            if count:
                try:
                    advanced = advance_native_player(
                        boundaries, loop, state)
                except ValueError as exc:
                    raise SpriteIndexFormatError(
                        "Original bounded native player failed") from exc
                counters["initially_advanced_index_kept"] += (
                    advanced.frame_index == state.frame_index
                )
                counters["initially_advanced_index_changed"] += (
                    advanced.frame_index != state.frame_index
                )
                counters["single_frame_sequences"] += count == 1
                counters["multiple_frame_sequences"] += count > 1
        expected = parent["per_original_resolution_pack"][screen]
        if (counters["sequences"] != expected["sequences"]
                or counters["sequences_with_no_frames"] !=
                expected["empty_sequences"]):
            raise SpriteIndexFormatError("Stage169 source totals disagree")
        if (counters["infinite_replay_settings"] +
            counters["zero_replay_settings"] +
            counters["positive_finite_replay_settings"] !=
            counters["sequences"]):
            raise SpriteIndexFormatError("Incomplete native replay classes")
        censes.append(dict(counters))
    if censes[0] != censes[1]:
        raise SpriteIndexFormatError("Native screen replay categories differ")
    return {
        "classification": "owner_private_native_player_replay_sign_census",
        "per_original_resolution_pack": censes[0],
        "all_native_source_loop_fields_agree_across_packs": True,
        "stage169_source_boundaries_reconciled": True,
        "negative_loop_setting_skips_finite_replay_decrement": True,
        "finite_counter_decrements_on_completed_wrap": True,
        "finished_requires_strictly_past_last_frame_end": True,
        "native_tick_seconds_and_float_conversion_verified": False,
        "runtime_mesh_texture_and_collision_playback_verified": False,
        "original_record_loop_values_frame_names_and_timestamps_exported": False,
    }


def audit_private_native_player_loop_controls(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as z:
        infos = z.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive source ZIP members")
        lookup = {i.filename: i for i in infos}
        if len(lookup) != len(infos):
            raise ValueError("Duplicate original ZIP member")
        repos, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            repos[screen] = _safe_read(
                z, lookup.get(prefix + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                z, lookup.get(prefix + WAD_PATH), MAX_WAD_BYTES)
            cuts[screen] = _safe_read(
                z, lookup.get(prefix + CUT_REPO), MAX_REPO_BYTES)
    return summarize_native_player_loop_controls(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    result = audit_private_native_player_loop_controls(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("Owner-private native replay-class aggregate saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
