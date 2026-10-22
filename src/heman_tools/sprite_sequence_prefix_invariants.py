"""Owner-private structural controls for a five-word sprite sequence prefix.

Stage155 established [indexed UTF16 key][u32 marker][u32 candidate
count] and an unknown final u32. In each *nonzero-candidate* record,
the 20 bytes immediately after candidate count can be read as five
little-endian u32 words. Compare those words across resolution packs,
but DO NOT assume the third word is invariant: two original records
show legitimately different values across source packs.

No word is a proven frame count, sprite ID, time unit, size or loop bit.
Only aggregate counters leave the owner's private local environment.
Public CI contains invented ZIP/repository/WAD data.
"""
from __future__ import annotations

import argparse
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
from .sprite_sequence_header_controls import (
    REPO_PATH, WAD_PATH, summarize_sequence_structural_fields,
)

_WORDS = struct.Struct("<5I")
_HEAD = struct.Struct("<II")
MAX_FIRST_WORD = 1024


def summarize_sequence_prefix_invariants(
    repositories: dict[str, bytes],
    wads: dict[str, bytes],
) -> dict:
    """Count five-word consistency independently of guessed field meanings.

    Confirm the strict Stage155 sequence header, then inspect at most
    one 20-byte prefix per nonzero-candidate interval. Third-word
    mismatch is a **reported** phenomenon, NOT a decoding failure.
    """
    stage155 = summarize_sequence_structural_fields(repositories, wads)
    entries = parse_sprite_repository(
        repositories[SCREENS[0]],
        expected_label="SpriteSeqData",
        expected_wad=WAD_PATH,
    )
    parts = [_intervals(entries,wads[screen]) for screen in SCREENS]
    nonzero = zero = first_equal = third_equal = all_equal = 0
    second_zero = fifth_zero = fourth_zero = fourth_nonzero = 0
    second_equal = fourth_equal = fifth_equal = 0
    first_max = 0
    first_zero = 0
    for i,row in enumerate(entries):
        decoded = []
        for pack in parts:
            record = pack[i]
            name, pos = _text(record,0)
            if name != row.key or pos+12>len(record):
                raise SpriteIndexFormatError("Unexpected sequence record header")
            _marker,count = _HEAD.unpack_from(record,pos)
            mid_start = pos+8
            if count == 0:
                if len(record) != pos+12:
                    raise SpriteIndexFormatError("Zero-candidate record is not minimal")
                decoded.append(None)
                continue
            # The final four bytes are *not* part of the 20-byte prefix.
            if len(record) < mid_start + _WORDS.size + 4:
                raise SpriteIndexFormatError("Incomplete five-word prefix")
            words = _WORDS.unpack_from(record,mid_start)
            if words[0] > MAX_FIRST_WORD:
                raise SpriteIndexFormatError("First prefix word exceeds safety budget")
            if words[1] != 0 or words[4] != 0:
                raise SpriteIndexFormatError("Observed reserved zero prefix changed")
            decoded.append(words)
        if (decoded[0] is None) != (decoded[1] is None):
            raise SpriteIndexFormatError("Record candidate count disagrees")
        if decoded[0] is None:
            zero += 1
            continue
        nonzero += 1
        a,b=decoded
        if a[0] != b[0] or a[1] != b[1] or a[3] != b[3] or a[4] != b[4]:
            raise SpriteIndexFormatError("Stable sequence prefix words diverged")
        first_equal += a[0] == b[0]
        third_equal += a[2] == b[2]
        second_equal += a[1] == b[1]
        fourth_equal += a[3] == b[3]
        fifth_equal += a[4] == b[4]
        second_zero += a[1] == 0
        fourth_zero += a[3] == 0
        fourth_nonzero += a[3] != 0
        fifth_zero += a[4] == 0
        first_zero += a[0] == 0
        first_max = max(first_max,a[0])
        all_equal += a == b

    # Recompute this count without relying on the serialized source
    # item's per-record offsets in published output.
    records_with_payload_after_prefix = 0
    for i, row in enumerate(entries):
        name,pos = _text(parts[0][i],0)
        marker,count=_HEAD.unpack_from(parts[0][i],pos)
        if count:
            records_with_payload_after_prefix += (
                len(parts[0][i]) > pos + 8 + _WORDS.size + 4
            )

    if zero+nonzero!=len(entries) or (
        nonzero != len(entries)-stage155["candidate_count_zero_records"]
    ):
        raise SpriteIndexFormatError("Sequence prefix accounting discrepancy")

    return {
        "classification":"owner_private_sprite_sequence_five_word_prefix_invariants",
        "indexed_sequence_record_count":len(entries),
        "zero_candidate_minimal_records":zero,
        "nonzero_candidate_records_with_complete_five_word_prefix":nonzero,
        "first_word_equal_across_screen_packs":first_equal,
        "first_word_zero_records":first_zero,
        "maximum_first_word_observed":first_max,
        "second_word_zero_records":second_zero,
        "second_word_equal_across_screen_packs":second_equal,
        "third_word_equal_across_screen_packs":third_equal,
        "third_word_different_across_screen_packs":nonzero-third_equal,
        "fourth_word_zero_records":fourth_zero,
        "fourth_word_nonzero_records":fourth_nonzero,
        "fourth_word_equal_across_screen_packs":fourth_equal,
        "fifth_word_zero_records":fifth_zero,
        "fifth_word_equal_across_screen_packs":fifth_equal,
        "entire_five_word_prefix_identical_between_packs":all_equal,
        "records_with_additional_opaque_bytes_after_five_word_prefix":
            records_with_payload_after_prefix,
        "potential_resolution_specific_third_word_preserved_as_evidence":True,
        "sequence_prefix_field_names_or_semantics_verified":False,
        "sequence_frame_count_duration_and_animation_layout_verified":False,
        "actor_state_or_collision_shape_switching_verified":False,
        "original_sprite_bytes_or_images_export_permitted":False,
        "original_names_record_offsets_raw_fields_or_hashes_in_output":False,
    }


def audit_private_sequence_prefix_invariants(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Original owner-private IPA missing")
    with ZipFile(ipa) as z:
        infos=z.infolist()
        if len(infos)>MAX_MEMBERS:
            raise ValueError("Source ZIP member budget exceeded")
        index={i.filename:i for i in infos}
        if len(index)!=len(infos):
            raise ValueError("Duplicate private source ZIP name")
        repos,wads={},{}
        for screen in SCREENS:
            prefix=PREFIX+screen+"/"
            repos[screen]=_safe_read(z,index.get(prefix+REPO_PATH),MAX_REPO_BYTES)
            wads[screen]=_safe_read(z,index.get(prefix+WAD_PATH),MAX_WAD_BYTES)
        return summarize_sequence_prefix_invariants(repos,wads)


def main(argv=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args(argv)
    report=audit_private_sequence_prefix_invariants(args.ipa)
    destination=private_output_path(args.out)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",
                           encoding="utf-8")
    print("Aggregate source-private five-word prefix audit recorded under local_reports.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
