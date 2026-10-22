"""Stage167: structural SpriteSequence -> SpriteFrame -> Symbol loader.

Format evidence: independently reverse-engineered *control flow* in the
owner's ARMv7 game executable. No executable disassembly, original bytes,
resource identifiers, or copyrighted art are committed here.

Original loader:
 - after UTF-16LE sequence name: 3 signed 32-bit fields; the second
   is the sequence's number of frames (the first is exposed as getLoop)
 - each frame: 4 signed 32-bit fields, 1-byte boolean, signed 32-bit
   symbol count; the second frame integer is exposed as getTime
 - each symbol: 2 signed 32-bit fields, UTF-16LE name with u16 count,
   4 signed 32-bit fields, 6 f32, 4 signed 32-bit fields, 3 signed
   32-bit fields.

Each symbol therefore has exactly 76 fixed scalar bytes plus the
serialized UTF-16LE name (2+2*code_units). A two-code-unit name makes
an 82-byte serialized symbol; 82 is NOT a confirmed frame size.

Parser objects are owner-private and never serialized. Public returns
are aggregate-only. CI operates on fabricated source packs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
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
from .sprite_sequence_cut_name_candidates import CUT_REPO, CUT_WAD
from .sprite_sequence_nested_grammar import MAX_SEQUENCE_BYTES

MAX_NATIVE_FRAMES = 1024
MAX_NATIVE_SYMBOLS_PER_FRAME = 3000
FIXED_SYMBOL_SCALAR_BYTES = 76
FRAME_HEADER_BYTES = 21
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_I32 = struct.Struct("<i")


@dataclass(frozen=True)
class _PrivateFrame:
    numerical_header: tuple[int, int, int, int]
    boolean_byte: int
    symbol_names: tuple[str, ...]
    symbol_prefixes: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _PrivateSequence:
    key: str
    loop_field: int
    third_field: int
    frames: tuple[_PrivateFrame, ...]


class _RecordReader:
    def __init__(self, raw: bytes):
        if type(raw) is not bytes or len(raw) > MAX_SEQUENCE_BYTES:
            raise ValueError("Invalid bounded sprite sequence record")
        self.raw = raw
        self.pos = 0

    def take(self, size: int) -> bytes:
        if (type(size) is not int or size < 0 or
                self.pos + size > len(self.raw)):
            raise SpriteIndexFormatError("Truncated serialized sprite field")
        start = self.pos
        self.pos += size
        return self.raw[start:self.pos]

    def s32(self) -> int:
        return _I32.unpack(self.take(4))[0]

    def u8(self) -> int:
        return self.take(1)[0]

    def utf16(self, *, allow_empty: bool = False) -> str:
        units = _U16.unpack(self.take(2))[0]
        if units > 512 or (not allow_empty and units == 0):
            raise SpriteIndexFormatError("Invalid serialized resource name length")
        try:
            result = self.take(2 * units).decode("utf-16le", "strict")
        except UnicodeDecodeError as exc:
            raise SpriteIndexFormatError("Invalid serialized UTF-16LE") from exc
        if any(ord(ch) < 32 for ch in result):
            raise SpriteIndexFormatError("Control character in resource key")
        return result


def _parse_native_sequence(record: bytes) -> _PrivateSequence:
    """Strict original-order parse; requires exact EOF, no width guesses."""
    reader = _RecordReader(record)
    key = reader.utf16()
    loop = reader.s32()
    frame_count = reader.s32()
    third = reader.s32()
    if frame_count < 0 or frame_count > MAX_NATIVE_FRAMES:
        raise SpriteIndexFormatError("Invalid native frame count")
    frames = []
    for _ in range(frame_count):
        numerical = tuple(reader.s32() for _ in range(4))
        boolean = reader.u8()  # original reader reads exactly one byte
        symbol_count = reader.s32()
        if symbol_count < 0 or symbol_count > MAX_NATIVE_SYMBOLS_PER_FRAME:
            raise SpriteIndexFormatError("Invalid native frame symbol count")
        names = []
        prefields = []
        for _ in range(symbol_count):
            prefields.append((reader.s32(), reader.s32()))
            names.append(reader.utf16(allow_empty=True))
            # All scalar reads retained for byte layout validation only.
            for _ in range(4):
                reader.s32()
            reader.take(6 * 4)  # original f32 fields, opaque here
            for _ in range(4 + 3):
                reader.s32()
        frames.append(_PrivateFrame(numerical, boolean, tuple(names),
                                    tuple(prefields)))
    if reader.pos != len(record):
        raise SpriteIndexFormatError("Native sequence has unread trailing bytes")
    return _PrivateSequence(key, loop, third, tuple(frames))


def summarize_native_sequence_loader_structure(
    sequence_repos: dict[str, bytes],
    sequence_wads: dict[str, bytes],
    cut_repos: dict[str, bytes],
) -> dict:
    """Audit every original record, preserving only safe aggregate counts."""
    if (set(sequence_repos) != set(SCREENS) or
            set(sequence_wads) != set(SCREENS) or
            set(cut_repos) != set(SCREENS)):
        raise ValueError("Original paired resolution source packs required")
    baseline = summarize_sequence_structural_fields(
        sequence_repos, sequence_wads,
    )
    if cut_repos[SCREENS[0]] != cut_repos[SCREENS[1]]:
        raise SpriteIndexFormatError("Paired indexed sprite-cut repository differs")
    cuts = parse_sprite_repository(
        cut_repos[SCREENS[0]],
        expected_label="SpriteCutData", expected_wad=CUT_WAD,
    )
    indexed_keys = frozenset(x.key for x in cuts)
    rows = parse_sprite_repository(
        sequence_repos[SCREENS[0]],
        expected_label="SpriteSeqData", expected_wad=WAD_PATH,
    )
    spans = [_intervals(rows, sequence_wads[screen]) for screen in SCREENS]
    totals = []
    parsed = []
    for pack in spans:
        census = Counter()
        items = []
        for row, record in zip(rows, pack):
            item = _parse_native_sequence(record)
            if item.key != row.key:
                raise SpriteIndexFormatError("Native sprite sequence key mismatch")
            items.append(item)
            census["sequence_records"] += 1
            census["frames"] += len(item.frames)
            census["zero_frame_records"] += len(item.frames) == 0
            for frame in item.frames:
                census["symbols"] += len(frame.symbol_names)
                census["zero_symbol_frames"] += len(frame.symbol_names) == 0
                for key in frame.symbol_names:
                    if key in indexed_keys:
                        census["indexed_symbol_references"] += 1
                    else:
                        census["unindexed_symbol_references"] += 1
                        census["unindexed_two_unit_names"] += len(key) == 2
        totals.append(census)
        parsed.append(items)
    if totals[0] != totals[1]:
        raise SpriteIndexFormatError("Native source structure census differs")
    if totals[0]["sequence_records"] != baseline["sequence_records_examined"]:
        raise SpriteIndexFormatError("Native indexed record total differs")
    if totals[0]["zero_frame_records"] != baseline[
        "candidate_count_zero_records"]:
        raise SpriteIndexFormatError("Native zero-frame total differs")
    agreement = Counter()
    for first, second in zip(*parsed):
        if len(first.frames) != len(second.frames):
            raise SpriteIndexFormatError("Paired native frame counts differ")
        agreement["sequence_loop_fields_equal"] += (
            first.loop_field == second.loop_field
        )
        agreement["sequence_third_fields_equal"] += (
            first.third_field == second.third_field
        )
        counts_equal = all(len(a.symbol_names) == len(b.symbol_names)
                           for a, b in zip(first.frames, second.frames))
        agreement["per_frame_symbol_counts_equal"] += counts_equal
        refs_equal = all(a.symbol_names == b.symbol_names for a, b in
                         zip(first.frames, second.frames))
        agreement["per_frame_symbol_names_equal"] += refs_equal
        agreement["all_frame_numeric_headers_equal"] += all(
            a.numerical_header == b.numerical_header
            for a,b in zip(first.frames, second.frames)
        )
        agreement["all_frame_bool_bytes_equal"] += all(
            a.boolean_byte == b.boolean_byte
            for a,b in zip(first.frames, second.frames)
        )
    public_census = {
        label: totals[0][label] for label in (
            "sequence_records", "frames", "zero_frame_records", "symbols",
            "zero_symbol_frames", "indexed_symbol_references",
            "unindexed_symbol_references", "unindexed_two_unit_names",
        )
    }
    if public_census["indexed_symbol_references"] + public_census[
            "unindexed_symbol_references"] != public_census["symbols"]:
        raise SpriteIndexFormatError("Native source symbol totals incomplete")
    return {
        "classification": "private_armv7_verified_sprite_sequence_frame_symbol_loader",
        "per_original_resolution_pack": public_census,
        "paired_pack_equalities": dict(agreement),
        "frame_count_from_native_sequence_getNumberOfFrames": True,
        "frame_time_native_field_index": 1,
        "serialized_frame_header_bytes": FRAME_HEADER_BYTES,
        "serialized_symbol_scalar_bytes_excluding_name":
            FIXED_SYMBOL_SCALAR_BYTES,
        "two_utf16_code_unit_symbol_serialized_bytes": 82,
        "complete_exact_EOF_native_load_order_verified": True,
        "frame_count_matches_previous_unknown_candidate_u32": True,
        "rendered_frame_timing_units_calibrated": False,
        "runtime_texture_mapping_and_collision_bindings_verified": False,
        "original_asset_bytes_names_offsets_or_per_record_data_exported": False,
        "safe_to_publish_original_graphics": False,
    }


def audit_private_native_sequence_loader_structure(ipa: Path) -> dict:
    if not ipa.is_file():
        raise ValueError("Owner-private original IPA missing")
    with ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValueError("Excessive original ZIP members")
        lookup = {info.filename: info for info in infos}
        if len(lookup) != len(infos):
            raise ValueError("Duplicate original ZIP member")
        repos, wads, cuts = {}, {}, {}
        for screen in SCREENS:
            prefix = PREFIX + screen + "/"
            repos[screen] = _safe_read(
                archive, lookup.get(prefix + REPO_PATH), MAX_REPO_BYTES)
            wads[screen] = _safe_read(
                archive, lookup.get(prefix + WAD_PATH), MAX_WAD_BYTES)
            cuts[screen] = _safe_read(
                archive, lookup.get(prefix + CUT_REPO), MAX_REPO_BYTES)
    return summarize_native_sequence_loader_structure(repos, wads, cuts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    result = audit_private_native_sequence_loader_structure(args.ipa)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("Private native sprite loader aggregate saved locally.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
