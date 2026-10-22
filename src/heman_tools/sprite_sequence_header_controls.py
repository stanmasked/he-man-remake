"""Source-private structural controls for original indexed sprite sequences.

Stage153 resolved .repo -> .wad offsets, Stage154 bounded every record.
For each sequence record the first two u32 fields after the UTF-16 key
are (marker, unknown candidate count). Its remaining body has at least
one u32, also observed at the end of each record. Those values are
checked in both resolution packs. No u32 is called a frame count, FPS,
duration, looping bit or original animation playback setting.

All original identifiers, offsets, bytes and frames stay owner-private.
Public tests operate on invented repositories and WAD records only.
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
    SCREENS, MAX_REPO_BYTES, MAX_WAD_BYTES,
    SpriteIndexFormatError, _matching_wad_keys,
    parse_sprite_repository, _text,
)
from .sprite_wad_record_intervals import _intervals
from .physics_shape_census import PREFIX, MAX_MEMBERS, _safe_read

REPO_PATH = "meta/SpriteSeqData.repo"
WAD_PATH = "sprite/SpriteSeqData.wad"
MAX_CANDIDATE_COUNT = 1024
_U32 = struct.Struct("<I")


def _bucket(value: int) -> str:
    if value == 0:
        return "zero"
    if value == 1:
        return "one"
    if value <= 4:
        return "two_through_four"
    if value <= 10:
        return "five_through_ten"
    if value <= 45:
        return "eleven_through_forty_five"
    return "greater_than_forty_five"


def summarize_sequence_structural_fields(
    repositories: dict[str, bytes],
    wads: dict[str, bytes],
) -> dict:
    """Check all indexed sequence records and return aggregate counters."""
    if (not isinstance(repositories, dict) or not isinstance(wads, dict)
            or set(repositories) != set(SCREENS) or set(wads) != set(SCREENS)
            or any(type(x) is not bytes for x in repositories.values())
            or any(type(x) is not bytes for x in wads.values())):
        raise ValueError("Missing paired source sequence resources")

    original = repositories[SCREENS[0]]
    if original != repositories[SCREENS[1]]:
        raise SpriteIndexFormatError("Sequence index metadata differs between packs")
    entries = parse_sprite_repository(
        original, expected_label="SpriteSeqData", expected_wad=WAD_PATH
    )
    spans = []
    for screen in SCREENS:
        wad = wads[screen]
        if _matching_wad_keys(entries, wad, require_key=True) != len(entries):
            raise SpriteIndexFormatError("Sequence indexed name lookup incomplete")
        spans.append(_intervals(entries, wad))
    if [len(v) for v in spans[0]] != [len(v) for v in spans[1]]:
        raise SpriteIndexFormatError("Sequence record sizes differ between packs")

    field_categories: Counter[str] = Counter()
    marker_categories: Counter[str] = Counter()
    ending_categories: Counter[str] = Counter()
    header_parity = trailing_parity = 0
    no_children_minimal = 0
    first_following_field_equal = 0
    for record_index, row in enumerate(entries):
        per_pack = []
        for record in (spans[0][record_index], spans[1][record_index]):
            name, pos = _text(record, 0)
            if name != row.key:
                raise SpriteIndexFormatError("Sequence header key mismatch")
            if pos + 12 > len(record):
                raise SpriteIndexFormatError("Truncated sequence candidate fields")
            marker, candidate = struct.unpack_from("<II", record, pos)
            if candidate > MAX_CANDIDATE_COUNT:
                raise SpriteIndexFormatError("Sequence candidate count exceeds safety cap")
            trailing = _U32.unpack_from(record, len(record) - 4)[0]
            first_remaining = _U32.unpack_from(record, pos + 8)[0]
            if candidate == 0 and len(record) != pos + 12:
                # The private source's three zero-count records have
                # only the trailing u32. Preserve that strict control.
                raise SpriteIndexFormatError("Zero-candidate sequence has extra bytes")
            if candidate > 0 and len(record) <= pos + 12:
                raise SpriteIndexFormatError("Nonzero-candidate sequence has no payload")
            if trailing not in (0, 1):
                raise SpriteIndexFormatError("Unsupported ending u32 category")
            per_pack.append((marker, candidate, trailing, first_remaining))
        first, second = per_pack
        if first[:2] != second[:2]:
            raise SpriteIndexFormatError("Sequence leading fields differ across packs")
        if first[2] != second[2]:
            raise SpriteIndexFormatError("Sequence ending field differs across packs")
        if first[3] != second[3]:
            raise SpriteIndexFormatError("Sequence first remaining field differs across packs")
        header_parity += 1
        trailing_parity += 1
        first_following_field_equal += 1
        marker, candidate, trailing, _first_remaining = first
        field_categories[_bucket(candidate)] += 1
        marker_categories[
            "zero" if marker == 0 else
            "all_bits_one" if marker == 0xFFFFFFFF else "other"
        ] += 1
        ending_categories["zero" if trailing == 0 else "one"] += 1
        no_children_minimal += candidate == 0

    if sum(field_categories.values()) != len(entries):
        raise ValueError("Incomplete source indexed count accounting")
    return {
        "classification": "owner_private_sprite_sequence_u32_header_controls",
        "sequence_records_examined": len(entries),
        "candidate_count_zero_records": field_categories["zero"],
        "candidate_count_one_records": field_categories["one"],
        "candidate_count_two_through_four_records":
            field_categories["two_through_four"],
        "candidate_count_five_through_ten_records":
            field_categories["five_through_ten"],
        "candidate_count_eleven_through_forty_five_records":
            field_categories["eleven_through_forty_five"],
        "candidate_count_greater_than_forty_five_records":
            field_categories["greater_than_forty_five"],
        "zero_candidate_records_with_only_one_final_u32": no_children_minimal,
        "sequence_marker_zero_records": marker_categories["zero"],
        "sequence_marker_all_bits_one_records": marker_categories["all_bits_one"],
        "sequence_marker_other_records": marker_categories["other"],
        "last_record_u32_zero": ending_categories["zero"],
        "last_record_u32_one": ending_categories["one"],
        "paired_matching_first_two_u32_fields": header_parity,
        "paired_matching_last_u32_field": trailing_parity,
        "paired_matching_first_postcount_u32_field": first_following_field_equal,
        "all_repository_indexed_records_checked": True,
        "unknown_u32_count_means_actual_animation_frames": False,
        "ending_u32_means_looping_or_playback_setting": False,
        "duration_timing_sprite_frames_decoded": False,
        "source_object_state_to_sequence_binding_verified": False,
        "original_hitbox_animation_changes_verified": False,
        "safe_for_source_sprite_import_to_switch": False,
        "original_keys_offsets_sprite_bytes_and_values_in_report": False,
    }


def audit_private_sequence_structural_fields(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original iOS IPA not found")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Original ZIP index exceeds safety budget")
        indexed = {info.filename: info for info in infos}
        if len(indexed) != len(infos):
            raise ValueError("Duplicate source archive member")
        repos = {}
        wads = {}
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            repos[screen] = _safe_read(
                archive, indexed.get(prefix + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                archive, indexed.get(prefix + WAD_PATH), MAX_WAD_BYTES)
        return summarize_sequence_structural_fields(repos, wads)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    output = private_output_path(args.out)
    report = audit_private_sequence_structural_fields(args.ipa)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                      encoding="utf-8")
    print("Private sequence u32 structural census written under ignored local_reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
