"""Private-only Mach-O symbol-table census for original physics/collision code candidates.

Defined symbols in the executable's __text section are stronger static evidence
than printable strings alone, but they do not establish runtime reachability,
call paths, resource binding, or actual collision response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import zipfile

from .collision_inventory import private_output_path
from .ios_launch_preflight import (
    MAX_EXECUTABLE_BYTES,
    MAX_PLIST_BYTES,
    _member,
    _string,
    inspect_macho_header,
    inspect_private_ipa_launch,
)

LC_SEGMENT = 0x1
LC_SYMTAB = 0x2
MACH_HEADER_SIZE = 28
SEGMENT_COMMAND_SIZE = 56
SECTION_SIZE = 68
SYMTAB_COMMAND_SIZE = 24
NLIST32_SIZE = 12
MAX_SYMBOLS = 200_000
MAX_STRING_TABLE_BYTES = 16 * 1024 * 1024
MAX_SYMBOL_NAME_BYTES = 8192
ZERO_FILL_SECTION_TYPES = {0x1, 0xC, 0x12}


def _fixed_name(raw: bytes, label: str) -> str:
    name = raw.split(b"\x00", 1)[0]
    try:
        decoded = name.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid Mach-O {label} name") from exc
    if any(ord(ch) < 32 for ch in decoded):
        raise ValueError(f"invalid Mach-O {label} control character")
    return decoded


def summarize_macho_symbols(binary: bytes) -> dict:
    """Parse bounded nlist32 entries; output only category counts and flags."""
    if not isinstance(binary, bytes) or not MACH_HEADER_SIZE <= len(binary) <= MAX_EXECUTABLE_BYTES:
        raise ValueError("executable bytes outside the bounded input range")
    macho = inspect_macho_header(binary)
    if binary[:4] == b"\xce\xfa\xed\xfe":
        order = "<"
    elif binary[:4] == b"\xfe\xed\xfa\xce":
        order = ">"
    else:
        raise ValueError("unsupported Mach-O byte order")

    _, _, _, _, ncmds, sizeofcmds, _ = struct.unpack_from(order + "IiiIIII", binary, 0)
    command_end = MACH_HEADER_SIZE + sizeofcmds
    cursor = MACH_HEADER_SIZE
    section_ordinal = 0
    text_sections = []
    symtab = None

    for _ in range(ncmds):
        if cursor + 8 > command_end:
            raise ValueError("truncated Mach-O load command")
        cmd, cmdsize = struct.unpack_from(order + "II", binary, cursor)
        if cmdsize < 8 or cmdsize % 4 or cmdsize > command_end - cursor:
            raise ValueError("invalid Mach-O load command size")

        if cmd == LC_SEGMENT:
            if cmdsize < SEGMENT_COMMAND_SIZE:
                raise ValueError("truncated Mach-O segment command")
            segment_name = _fixed_name(binary[cursor + 8:cursor + 24], "segment")
            nsects = struct.unpack_from(order + "I", binary, cursor + 48)[0]
            if nsects > 4096 or cmdsize != SEGMENT_COMMAND_SIZE + nsects * SECTION_SIZE:
                raise ValueError("Mach-O section count does not match segment size")
            section_cursor = cursor + SEGMENT_COMMAND_SIZE
            for _section in range(nsects):
                section_name = _fixed_name(binary[section_cursor:section_cursor + 16], "section")
                section_segment = _fixed_name(
                    binary[section_cursor + 16:section_cursor + 32], "section segment"
                )
                addr, size, offset, align, reloff, nreloc, flags, reserved1, reserved2 = (
                    struct.unpack_from(order + "IIIIIIIII", binary, section_cursor + 32)
                )
                section_ordinal += 1
                if section_segment != segment_name:
                    raise ValueError("section segment name contradicts parent segment")
                section_type = flags & 0xFF
                if size and section_type not in ZERO_FILL_SECTION_TYPES:
                    if offset > len(binary) or size > len(binary) - offset:
                        raise ValueError("Mach-O section exceeds executable bounds")
                if segment_name == "__TEXT" and section_name == "__text":
                    text_sections.append(section_ordinal)
                section_cursor += SECTION_SIZE

        elif cmd == LC_SYMTAB:
            if cmdsize != SYMTAB_COMMAND_SIZE or symtab is not None:
                raise ValueError("malformed or duplicate Mach-O symbol-table command")
            symoff, nsyms, stroff, strsize = struct.unpack_from(
                order + "IIII", binary, cursor + 8
            )
            symtab = (symoff, nsyms, stroff, strsize)
        cursor += cmdsize

    if cursor != command_end:
        raise ValueError("Mach-O load commands do not reconcile")
    if len(text_sections) != 1:
        raise ValueError("expected exactly one __TEXT,__text section")
    if symtab is None:
        raise ValueError("Mach-O symbol table is absent")

    symoff, nsyms, stroff, strsize = symtab
    table_bytes = nsyms * NLIST32_SIZE
    if not 1 <= nsyms <= MAX_SYMBOLS:
        raise ValueError("Mach-O symbol count outside supported bound")
    if not 1 <= strsize <= MAX_STRING_TABLE_BYTES:
        raise ValueError("Mach-O string table outside supported bound")
    if (symoff < command_end or symoff > len(binary)
            or table_bytes > len(binary) - symoff
            or stroff < symoff + table_bytes
            or stroff > len(binary) or strsize > len(binary) - stroff):
        raise ValueError("Mach-O symbol or string table exceeds executable bounds")

    strings = binary[stroff:stroff + strsize]
    text_section = text_sections[0]
    category_total = {
        "physics": 0,
        "collision": 0,
        "sensor": 0,
        "platform": 0,
        "tilemap": 0,
        "shape2d": 0,
    }
    category_text = dict(category_total)
    named_entries = 0
    text_entries = 0
    symbol_names = set()

    for index in range(nsyms):
        strx, n_type, n_sect, n_desc, n_value = struct.unpack_from(
            order + "IBBHI", binary, symoff + index * NLIST32_SIZE
        )
        if n_type & 0xE0:  # STAB/debug symbol, not an ordinary nlist entry
            continue
        if strx == 0:
            continue
        if strx >= len(strings):
            raise ValueError("Mach-O symbol name offset outside string table")
        terminator = strings.find(b"\x00", strx)
        if terminator < 0 or terminator - strx > MAX_SYMBOL_NAME_BYTES:
            raise ValueError("unterminated or overlong Mach-O symbol name")
        raw_name = strings[strx:terminator]
        if not raw_name:
            continue
        try:
            name = raw_name.decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("non-ASCII Mach-O symbol name") from exc
        if any(ord(ch) < 32 for ch in name):
            raise ValueError("Mach-O symbol name contains control characters")
        named_entries += 1
        symbol_names.add(name)
        lower = name.casefold()
        categories = {
            "physics": "physic" in lower,
            "collision": "collis" in lower,
            "sensor": "sensor" in lower,
            "platform": "platform" in lower,
            "tilemap": "tilemap" in lower or "tile_map" in lower,
            "shape2d": "shape2d" in lower,
        }
        is_text_defined = (n_type & 0x0E) == 0x0E and n_sect == text_section
        if is_text_defined:
            text_entries += 1
        for category, matched in categories.items():
            if matched:
                category_total[category] += 1
                if is_text_defined:
                    category_text[category] += 1

    return {
        "schema": "heman-stage261-macho-symbol-census-v1",
        "macho": {
            "architecture": macho["architecture"],
            "thin_32_bit_macho": macho["thin_32_bit_macho"],
            "load_commands_structurally_valid": macho["load_commands_structurally_valid"],
            "text_section_ordinal": text_section,
        },
        "symbol_table_entries": nsyms,
        "named_non_debug_symbol_entries": named_entries,
        "distinct_symbol_names": len(symbol_names),
        "text_section_defined_symbol_entries": text_entries,
        "category_symbol_entry_counts": category_total,
        "text_section_category_symbol_entry_counts": category_text,
        "raw_symbol_names_in_report": False,
        "source_paths_or_resource_names_in_report": False,
        "static_symbol_presence_proves_call_path": False,
        "original_runtime_resource_binding_verified": False,
        "original_collision_response_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
    }


def inspect_private_ipa_symbol_table(ipa: Path) -> dict:
    """Read the executable member in memory and persist only private aggregates."""
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be a regular non-symlink file")
    preflight = inspect_private_ipa_launch(ipa)
    with zipfile.ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > 100_000:
            raise ValueError("excessive IPA member count")
        index = {info.filename: info for info in infos}
        if len(index) != len(infos):
            raise ValueError("duplicate IPA entry")
        app_dirs = sorted({
            name.split("/")[1] for name in index
            if name.startswith("Payload/")
            and len(name.split("/")) >= 3
            and name.split("/")[1].endswith(".app")
        })
        if len(app_dirs) != 1:
            raise ValueError("expected exactly one app bundle")
        prefix = f"Payload/{app_dirs[0]}/"
        plist_raw = _member(archive, index, prefix + "Info.plist", MAX_PLIST_BYTES)
        plist = plistlib.loads(plist_raw)
        if not isinstance(plist, dict):
            raise ValueError("Info.plist must be a dictionary")
        executable_name = _string(plist.get("CFBundleExecutable"), "executable name")
        if executable_name.startswith(".") or "/" in executable_name or "\\" in executable_name:
            raise ValueError("unsafe executable name")
        binary = _member(
            archive, index, prefix + executable_name, MAX_EXECUTABLE_BYTES
        )
    report = summarize_macho_symbols(binary)
    if report["macho"]["architecture"] != preflight["macho_metadata"]["architecture"]:
        raise ValueError("Mach-O architecture changed between bounded reads")
    report["private_source"] = {
        "executable_size_bytes": len(binary),
        "executable_sha256": hashlib.sha256(binary).hexdigest(),
        "ipa_member_extracted_to_disk": False,
        "raw_executable_bytes_in_report": False,
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    output = private_output_path(args.out)
    report = inspect_private_ipa_symbol_table(args.ipa)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Stage261 Mach-O symbol census saved under local_reports/; no call graph inferred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
