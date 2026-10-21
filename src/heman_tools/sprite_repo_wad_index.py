"""Read-only verification of the original iOS sprite .repo -> .wad index.

Observed common .repo framing (three families):
  u16 UTF-16 repository name, u16 reserved zero, u32 entry count
  repeated:
    u16 UTF-16 index key
    u32 reserved zero
    u16 UTF-16 WAD relative path
    u32 offset into WAD

The sequence and cut WADs store that same length-prefixed UTF-16 key
at EVERY indexed offset. The single-frame WAD has a different record
header: its offsets are bounded, but key-at-offset equality is NOT
required. We do not parse animation frames or infer actor animation.

All owner IPA bytes and key strings remain only in local memory.
Public CI uses imaginary .repo/.wad fixtures.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import struct
from zipfile import ZipFile

from .collision_inventory import private_output_path
from .physics_shape_census import PREFIX, SCREENS, MAX_MEMBERS, _safe_read

MAX_REPO_BYTES = 1_000_000
MAX_WAD_BYTES = 8_000_000
MAX_ENTRIES = 5000
MAX_TEXT_UNITS = 512
_FAMILIES = (
    ("SpriteSeqData", "meta/SpriteSeqData.repo", "sprite/SpriteSeqData.wad", True),
    ("SpriteCutData", "meta/SpriteCutData.repo", "sprite/SpriteResData.wad", True),
    ("SingleFrameSpriteData", "meta/SingleFrameSpriteData.repo",
     "singleFrameSprite/SingleFrameSpriteData.wad", False),
)


class SpriteIndexFormatError(ValueError):
    """Invalid or inconsistent observed index envelope."""


@dataclass(frozen=True)
class IndexEntry:
    key: str
    offset: int


def _text(raw: bytes, cursor: int) -> tuple[str, int]:
    if cursor + 2 > len(raw):
        raise SpriteIndexFormatError("Truncated source UTF-16 length")
    units = struct.unpack_from("<H", raw, cursor)[0]
    cursor += 2
    if not 1 <= units <= MAX_TEXT_UNITS or cursor + 2*units > len(raw):
        raise SpriteIndexFormatError("Invalid source UTF-16 length")
    try:
        value = raw[cursor:cursor+2*units].decode("utf-16le", "strict")
    except UnicodeDecodeError as exc:
        raise SpriteIndexFormatError("Invalid source UTF-16 identifier") from exc
    if any(ord(c) < 32 for c in value):
        raise SpriteIndexFormatError("Control character in source identifier")
    return value, cursor+2*units


def parse_sprite_repository(raw: bytes, *, expected_label: str,
                            expected_wad: str) -> tuple[IndexEntry, ...]:
    """Return private index entries in memory, never in report or GitHub."""
    if type(raw) is not bytes or not 12 <= len(raw) <= MAX_REPO_BYTES:
        raise SpriteIndexFormatError("Invalid sprite repository byte length")
    title, at = _text(raw, 0)
    if title != expected_label:
        raise SpriteIndexFormatError("Unexpected repository identifier")
    if at + 6 > len(raw):
        raise SpriteIndexFormatError("Missing repository count")
    reserved = struct.unpack_from("<H", raw, at)[0]
    count = struct.unpack_from("<I", raw, at+2)[0]
    if reserved != 0 or not 1 <= count <= MAX_ENTRIES:
        raise SpriteIndexFormatError("Invalid source repository header")
    at += 6
    result = []
    seen = set()
    previous = -1
    for _ in range(count):
        key, at = _text(raw, at)
        if at + 4 > len(raw):
            raise SpriteIndexFormatError("Truncated repository entry marker")
        marker = struct.unpack_from("<I", raw, at)[0]
        at += 4
        if marker != 0 or key in seen:
            raise SpriteIndexFormatError("Nonzero marker or repeated resource key")
        seen.add(key)
        target, at = _text(raw, at)
        if target != expected_wad:
            raise SpriteIndexFormatError("Unexpected repository WAD reference")
        if at + 4 > len(raw):
            raise SpriteIndexFormatError("Missing sprite resource offset")
        offset = struct.unpack_from("<I", raw, at)[0]
        at += 4
        if offset <= previous:
            raise SpriteIndexFormatError("Non-increasing sprite resource offset")
        previous = offset
        result.append(IndexEntry(key, offset))
    if at != len(raw) or result[0].offset != 0:
        raise SpriteIndexFormatError("Unconsumed repository data or nonzero first offset")
    return tuple(result)


def _matching_wad_keys(entries: tuple[IndexEntry, ...], wad: bytes,
                       *, require_key: bool) -> int:
    """Validate every offset. For two families also match full key at WAD."""
    if type(wad) is not bytes or not 1 <= len(wad) <= MAX_WAD_BYTES:
        raise SpriteIndexFormatError("Invalid sprite WAD size")
    count = 0
    for row in entries:
        if row.offset >= len(wad):
            raise SpriteIndexFormatError("Sprite repository offset exceeds WAD")
        if require_key:
            key, _after = _text(wad, row.offset)
            if key != row.key:
                raise SpriteIndexFormatError("Sprite WAD entry key mismatch")
            count += 1
    return count


def summarize_sprite_repo_wad_index(
    repositories: dict[str, dict[str, bytes]],
    wads: dict[str, dict[str, bytes]],
) -> dict:
    """Validate pack pairing, WAD indices, then return only coarse counts."""
    if (not isinstance(repositories,dict) or not isinstance(wads,dict)
            or set(repositories)!=set(SCREENS) or set(wads)!=set(SCREENS)):
        raise ValueError("Missing iOS screen resource pack")
    result = {}
    total = confirmed = 0
    for label, repo_path, wad_path, require_key in _FAMILIES:
        blobs = []
        archives = []
        for screen in SCREENS:
            if (not isinstance(repositories[screen],dict)
                    or not isinstance(wads[screen],dict)):
                raise ValueError("Invalid source resource group")
            if repo_path not in repositories[screen] or wad_path not in wads[screen]:
                raise ValueError("Missing indexed sprite resource family")
            blobs.append(repositories[screen][repo_path])
            archives.append(wads[screen][wad_path])
        if blobs[0] != blobs[1]:
            raise SpriteIndexFormatError("Source sprite repository bytes differ")
        entries = parse_sprite_repository(
            blobs[0],expected_label=label,expected_wad=wad_path)
        matches = [_matching_wad_keys(entries,archive,require_key=require_key)
                   for archive in archives]
        if matches[0] != matches[1]:
            raise SpriteIndexFormatError("Screen-pack WAD lookup differs")
        differences = (
            sum(a != b for a,b in zip(archives[0],archives[1]))
            + abs(len(archives[0])-len(archives[1]))
        )
        result[label] = {
            "index_entries":len(entries),
            "both_packs_offsets_within_WAD":True,
            "full_name_verified_at_indexed_offset_in_each_pack":
                bool(require_key and matches[0]==len(entries)),
            "full_name_header_not_assumed_for_this_family":not require_key,
            "name_verified_entries_per_screen":matches[0],
            "WAD_bytes_per_screen":[len(x) for x in archives],
            "WAD_differing_byte_positions":differences,
        }
        total += len(entries)
        confirmed += matches[0]
    return {
        "classification":"private_original_sprite_repository_to_wad_index",
        "paired_screen_pack_repository_count":len(_FAMILIES),
        "source_repository_entries_total":total,
        "strict_named_wad_index_entries_per_pack":confirmed,
        "separate_single_frame_WAD_header_not_decoded":True,
        "registry_to_wad_offset_and_named_header_verified":True,
        "sprite_frame_structures_decoded":False,
        "level_object_to_animation_lookup_verified":False,
        "active_animation_or_hitbox_switching_verified":False,
        "source_original_gameplay_parity_verified":False,
        "switch_original_asset_import_permitted":False,
        "raw_sprite_names_bytes_offsets_frames_and_hashes_in_report":False,
        "families":result,
    }


def audit_private_sprite_repo_wad_index(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Original owner-private IPA not found")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos)>MAX_MEMBERS:
            raise ValueError("Original source ZIP exceeds index bound")
        table = {info.filename:info for info in infos}
        if len(table)!=len(infos):
            raise ValueError("Duplicate source ZIP member")
        repos, wads = {}, {}
        for screen in SCREENS:
            repos[screen] = {}
            wads[screen] = {}
            for _, rp, wp, _ in _FAMILIES:
                repos[screen][rp] = _safe_read(
                    archive,table.get(PREFIX+screen+"/"+rp),MAX_REPO_BYTES)
                wads[screen][wp] = _safe_read(
                    archive,table.get(PREFIX+screen+"/"+wp),MAX_WAD_BYTES)
        return summarize_sprite_repo_wad_index(repos,wads)


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    destination=private_output_path(args.out)
    result=audit_private_sprite_repo_wad_index(args.ipa)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                           encoding="utf-8")
    print("Owner-private sprite WAD index aggregate saved to ignored local_reports.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
