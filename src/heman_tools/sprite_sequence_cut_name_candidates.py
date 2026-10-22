"""Source-private, independently indexed sprite sequence -> cut key candidates.

The five-u32 sequence prefix after the candidate count is structurally
validated by Stage156. At relative byte +13 *after* that prefix, inspect
a u16-length-prefixed UTF-16 token as a hypothesis. Test membership
against the independently validated SpriteCutData.repo index. A small
fixed set of alternative offsets is a negative control.

This only proves lexical references at a reproducible byte position,
NOT nested frame boundaries, per-frame timing, actual sprite playback
or ownership of a collider. No original names, values, offsets, bytes,
frames, or individual source-file identities enter the report.
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
from .sprite_sequence_header_controls import (
    REPO_PATH, WAD_PATH, summarize_sequence_structural_fields,
)
from .sprite_sequence_prefix_invariants import summarize_sequence_prefix_invariants

CUT_REPO = "meta/SpriteCutData.repo"
CUT_WAD = "sprite/SpriteResData.wad"
# Relative to the end of the first five u32 words after the unknown
# sequence candidate count. Only 13 is the test hypothesis.
TEST_OFFSETS = (0,4,8,12,13,14,16,20,24,32)
CANDIDATE_OFFSET = 13
MAX_TOKEN_UNITS = 128
_ZERO = struct.Struct("<H")
_COUNTS = struct.Struct("<II")


def _source_token(record: bytes, at: int) -> tuple[str, str | None]:
    """Return status + PRIVATE token, never an original record offset."""
    stop = len(record)-4  # Stage155's separate ending u32.
    if at+2 > stop:
        return "short", None
    units = _ZERO.unpack_from(record,at)[0]
    if units == 0:
        return "empty", None
    if units > MAX_TOKEN_UNITS or at+2+2*units > stop:
        return "out_of_bounds", None
    try:
        token = record[at+2:at+2+2*units].decode("utf-16le","strict")
    except UnicodeDecodeError:
        return "invalid_utf16", None
    if not all(32 <= ord(char) <= 126 for char in token):
        return "nonprintable", None
    return "valid", token


def summarize_sequence_cut_name_candidates(
    sequences: dict[str, bytes],
    wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Only aggregated lexical match counters, with both-pack consistency."""
    if (not all(isinstance(group,dict) and set(group)==set(SCREENS)
                and all(type(v) is bytes for v in group.values())
                for group in (sequences,wads,cut_repos))):
        raise ValueError("Incomplete original source paired animation files")

    # Reuse verified strict sequence envelope (including two original
    # legitimate screen-specific five-word prefix differences).
    structural = summarize_sequence_prefix_invariants(sequences,wads)

    if cut_repos[SCREENS[0]] != cut_repos[SCREENS[1]]:
        raise SpriteIndexFormatError("Source cut key repository pack mismatch")
    cut_entries = parse_sprite_repository(
        cut_repos[SCREENS[0]],expected_label="SpriteCutData",expected_wad=CUT_WAD)
    cut_keys = frozenset(item.key for item in cut_entries)
    sequence_index = parse_sprite_repository(
        sequences[SCREENS[0]],expected_label="SpriteSeqData",expected_wad=WAD_PATH)
    seq_keys = frozenset(item.key for item in sequence_index)
    spans={screen:_intervals(sequence_index,wads[screen]) for screen in SCREENS}
    control={str(offset):Counter() for offset in TEST_OFFSETS}
    selected=Counter()
    for i,entry in enumerate(sequence_index):
        rows=[spans[screen][i] for screen in SCREENS]
        positions=[]
        count_values=[]
        for rec in rows:
            key,at=_text(rec,0)
            if key!=entry.key or at+12>len(rec):
                raise SpriteIndexFormatError("Sprite sequence WAD header unexpectedly differs")
            _marker,count=_COUNTS.unpack_from(rec,at)
            count_values.append(count)
            positions.append(at+8+20)
        if count_values[0]!=count_values[1]:
            raise SpriteIndexFormatError("Source sequence candidate count pack mismatch")
        if count_values[0]==0:
            continue
        for relative in TEST_OFFSETS:
            parsed=[_source_token(rec,base+relative)
                    for rec,base in zip(rows,positions)]
            if parsed[0]!=parsed[1]:
                raise SpriteIndexFormatError("Source nested UTF-16 candidate differs across screen packs")
            status,token=parsed[0]
            tally=control[str(relative)]
            tally[status]+=1
            if status=="valid":
                tally["known_cut_key"] += token in cut_keys
                tally["unmatched_cut_key"] += token not in cut_keys
                tally["also_known_sequence_key"] += token in seq_keys
                tally["known_cut_and_sequence_key"] += token in cut_keys and token in seq_keys
    samples = structural["nonzero_candidate_records_with_complete_five_word_prefix"]
    if any(sum(control[str(off)][s] for s in (
        "short","empty","out_of_bounds","invalid_utf16","nonprintable","valid"
    ))!=samples for off in TEST_OFFSETS):
        raise SpriteIndexFormatError("Incomplete UTF-16 offset negative control")
    main=control[str(CANDIDATE_OFFSET)]
    return {
        "classification":"private_sprite_sequence_to_cut_repository_lexical_candidates",
        "indexed_sequence_records":structural["indexed_sequence_record_count"],
        "nonzero_candidate_sequences_checked":samples,
        "independently_indexed_cut_resource_names":len(cut_keys),
        "hypothesis_offset_after_five_u32_prefix_bytes":CANDIDATE_OFFSET,
        "candidate_valid_utf16_ascii_records":main["valid"],
        "candidate_exact_cut_resource_key_matches":main["known_cut_key"],
        "candidate_valid_but_not_in_cut_registry":main["unmatched_cut_key"],
        "candidate_valid_names_also_present_as_sequence_keys":
            main["also_known_sequence_key"],
        "candidate_valid_names_in_both_cut_and_sequence_indexes":
            main["known_cut_and_sequence_key"],
        "candidate_empty_utf16_records":main["empty"],
        "candidate_too_short_for_utf16_length":main["short"],
        "candidate_other_invalid_framings":
            main["out_of_bounds"]+main["invalid_utf16"]+main["nonprintable"],
        "predeclared_offset_controls": {
            "relative_"+str(off):{
                "well_formed_utf16_ascii":control[str(off)]["valid"],
                "matching_independent_cut_registry":
                    control[str(off)]["known_cut_key"],
            }
            for off in TEST_OFFSETS
        },
        "source_screen_packs_candidate_tokens_equal":True,
        "lexical_cross_registry_match_proves_data_reference":False,
        "unknown_count_equals_animation_frames_verified":False,
        "nested_sequence_frame_boundaries_decoded":False,
        "sprite_frame_timing_and_duration_verified":False,
        "original_actor_state_to_sprite_sequence_link_verified":False,
        "source_hitbox_state_changes_verified":False,
        "switch_original_sprite_import_permitted":False,
        "original_source_names_strings_bytes_values_or_offsets_in_report":False,
    }


def audit_private_sequence_cut_name_candidates(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Original owner-private IPA not found")
    with ZipFile(ipa) as archive:
        members=archive.infolist()
        if len(members)>MAX_MEMBERS:
            raise ValueError("Oversized owner-private IPA resource index")
        index={m.filename:m for m in members}
        if len(index)!=len(members):
            raise ValueError("Duplicate original source ZIP filename")
        seqs,wads,cuts={},{},{}
        for screen in SCREENS:
            root=PREFIX+screen+"/"
            seqs[screen]=_safe_read(
                archive,index.get(root+REPO_PATH),MAX_REPO_BYTES)
            wads[screen]=_safe_read(
                archive,index.get(root+WAD_PATH),MAX_WAD_BYTES)
            cuts[screen]=_safe_read(
                archive,index.get(root+CUT_REPO),MAX_REPO_BYTES)
        return summarize_sequence_cut_name_candidates(seqs,wads,cuts)


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ipa",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    opts=ap.parse_args(argv)
    output=private_output_path(opts.out)
    aggregate=audit_private_sequence_cut_name_candidates(opts.ipa)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(aggregate,sort_keys=True,indent=2)+"\n",
                      encoding="utf-8")
    print("Owner-private sequence/cut lexical evidence recorded as aggregate only.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
