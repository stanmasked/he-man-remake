"""Owner-private exact indexed sprite WAD record-interval *framing* checks.

Stage153 verified repository index keys and offsets. This stage
checks that offsets partition each entire WAD into positive, bounded
records and compares *only initial structural headers* across screen
packs. Sequence: key then u32 of unknown meaning; cut: key then a
second UTF-16 token; single-frame: a different leading UTF-16 token.

No sprite/image/frame/timing parsing or actor-state mapping occurs.
Original strings, raw offsets, byte arrays and per-record identities
must never enter the aggregate report or public GitHub.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .sprite_repo_wad_index import (
    _FAMILIES, _text, _matching_wad_keys, parse_sprite_repository,
    MAX_REPO_BYTES, MAX_WAD_BYTES, SpriteIndexFormatError,
)
from .physics_shape_census import (
    PREFIX, SCREENS, MAX_MEMBERS, _safe_read,
)

MAX_RECORD_BYTES = 32768
MIN_RECORD_BYTES = 4
_U32 = struct.Struct("<I")


def _intervals(entries, wad: bytes) -> tuple[bytes, ...]:
    """Return privately held slices bounded by the next index offset."""
    if type(wad) is not bytes or not 1 <= len(wad) <= MAX_WAD_BYTES:
        raise SpriteIndexFormatError("Invalid indexed WAD byte count")
    spans = []
    current = 0
    for i, entry in enumerate(entries):
        if entry.offset != current:
            raise SpriteIndexFormatError("Gap or overlap in indexed WAD")
        end = entries[i + 1].offset if i + 1 < len(entries) else len(wad)
        size = end - current
        if not MIN_RECORD_BYTES <= size <= MAX_RECORD_BYTES:
            raise SpriteIndexFormatError("Empty or oversized indexed WAD record")
        spans.append(wad[current:end])
        current = end
    if current != len(wad) or not spans:
        raise SpriteIndexFormatError("Indexed records do not consume WAD")
    return tuple(spans)


def summarize_sprite_record_intervals(
    repositories: dict[str, dict[str, bytes]],
    wads: dict[str, dict[str, bytes]],
) -> dict:
    """Strict source framing, with privacy-preserving aggregates only."""
    if (not isinstance(repositories, dict) or not isinstance(wads, dict)
            or set(repositories) != set(SCREENS)
            or set(wads) != set(SCREENS)):
        raise ValueError("Original source screen packs are incomplete")
    results = {}
    all_records = 0
    for label, repo_path, wad_path, require_key in _FAMILIES:
        repo_pack = []
        wad_pack = []
        for screen in SCREENS:
            if (not isinstance(repositories[screen], dict)
                    or not isinstance(wads[screen], dict)
                    or repo_path not in repositories[screen]
                    or wad_path not in wads[screen]):
                raise ValueError("Original indexed sprite resource is missing")
            repo_pack.append(repositories[screen][repo_path])
            wad_pack.append(wads[screen][wad_path])
        if repo_pack[0] != repo_pack[1]:
            raise SpriteIndexFormatError("Indexed sprite registries are not paired")
        entries = parse_sprite_repository(repo_pack[0],
                                          expected_label=label,
                                          expected_wad=wad_path)
        per_pack = [_intervals(entries, w) for w in wad_pack]
        if require_key:
            for wad in wad_pack:
                if _matching_wad_keys(entries, wad, require_key=True) != len(entries):
                    raise SpriteIndexFormatError("Incomplete WAD key matches")

        sizes = [len(x) for x in per_pack[0]]
        if [len(x) for x in per_pack[1]] != sizes:
            raise SpriteIndexFormatError("Screen-specific WAD intervals have differing sizes")
        exactly_same = 0
        first_token_equal = 0
        first_token_matching_repo = 0
        second_token_equal = 0
        marker_counts: Counter[str] = Counter()
        for i, row in enumerate(entries):
            first, second = per_pack[0][i], per_pack[1][i]
            exactly_same += first == second
            leading_tokens = []
            leading_ends = []
            for payload in (first, second):
                name, at = _text(payload, 0)
                leading_tokens.append(name)
                leading_ends.append(at)
            first_token_equal += leading_tokens[0] == leading_tokens[1]
            first_token_matching_repo += leading_tokens[0] == row.key
            if require_key and (
                leading_tokens[0] != row.key or leading_tokens[1] != row.key
            ):
                raise SpriteIndexFormatError("Indexed WAD first token does not match")
            if label == "SpriteSeqData":
                marker_values = []
                for payload, at in zip((first, second), leading_ends):
                    if at + _U32.size > len(payload):
                        raise SpriteIndexFormatError("Incomplete sequence record marker")
                    marker_values.append(_U32.unpack_from(payload, at)[0])
                if marker_values[0] != marker_values[1]:
                    raise SpriteIndexFormatError("Sequence marker diverges between screen packs")
                marker = marker_values[0]
                category = ("zero" if marker == 0 else
                            "all_bits_one" if marker == 0xFFFFFFFF else
                            "other")
                marker_counts[category] += 1
            elif label == "SpriteCutData":
                after = []
                for payload, at in zip((first, second), leading_ends):
                    extra, end = _text(payload, at)
                    if end >= len(payload):
                        raise SpriteIndexFormatError("Cut record has no data after second token")
                    after.append(extra)
                if after[0] != after[1]:
                    raise SpriteIndexFormatError("Cut secondary token diverges across screen packs")
                second_token_equal += 1
            else:
                # Single-frame WAD's key lookup is different; keep it
                # independent of the matching behavior of seq/cut.
                if any(at >= len(payload) for payload, at in zip(
                        (first, second), leading_ends)):
                    raise SpriteIndexFormatError("Single-frame header consumes whole record")

        results[label] = {
            "indexed_record_count": len(entries),
            "all_records_partition_entire_wad": True,
            "positive_bounded_interval_count": len(entries),
            "smallest_interval_bytes": min(sizes),
            "largest_interval_bytes": max(sizes),
            "complete_record_bytes_identical_between_packs": exactly_same,
            "first_utf16_headers_equal_between_packs": first_token_equal,
            "first_utf16_headers_matching_repository_key": first_token_matching_repo,
            "secondary_utf16_headers_equal_between_packs": second_token_equal,
            "sequence_following_u32_marker_zero": marker_counts["zero"],
            "sequence_following_u32_marker_all_bits_one": marker_counts["all_bits_one"],
            "sequence_following_u32_marker_other": marker_counts["other"],
            "sequence_marker_meaning_verified": False,
            "cut_secondary_token_meaning_verified": False,
            "single_frame_first_token_is_repo_key_proven": False,
        }
        all_records += len(entries)

    return {
        "classification": "private_original_indexed_sprite_wad_record_intervals",
        "source_indexed_wad_record_total": all_records,
        "source_screen_packs": len(SCREENS),
        "max_accepted_record_interval_bytes": MAX_RECORD_BYTES,
        "all_indexed_record_intervals_validated": True,
        "sprite_frame_count_or_duration_decoded": False,
        "sprite_pixel_data_decoded": False,
        "source_actor_state_to_animation_verified": False,
        "source_animation_driven_colliders_verified": False,
        "original_switch_gameplay_parity_verified": False,
        "source_original_asset_export_permitted": False,
        "source_record_keys_raw_bytes_offsets_and_sprites_in_report": False,
        "families": results,
    }


def audit_private_sprite_record_intervals(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA was not found")
    with ZipFile(ipa) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise ValueError("Original source index exceeds safe limit")
        index = {m.filename:m for m in members}
        if len(index) != len(members):
            raise ValueError("Original ZIP has duplicate resource member")
        repos, wads = {}, {}
        for screen in SCREENS:
            repos[screen], wads[screen] = {}, {}
            for _, rp, wp, _ in _FAMILIES:
                repos[screen][rp] = _safe_read(
                    archive, index.get(PREFIX+screen+"/"+rp), MAX_REPO_BYTES)
                wads[screen][wp] = _safe_read(
                    archive, index.get(PREFIX+screen+"/"+wp), MAX_WAD_BYTES)
        return summarize_sprite_record_intervals(repos, wads)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    summary = audit_private_sprite_record_intervals(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, sort_keys=True, indent=2)+"\n",
                           encoding="utf-8")
    print("Owner-private sprite interval aggregate written under ignored local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
