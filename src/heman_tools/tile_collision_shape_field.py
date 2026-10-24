"""Private static evidence for Tile collision-shape field serialization.

Evidence tiers:
1. A direct Thumb BL candidate from Tile::fileIn to Tile::setCollisionShape.
2. Writes to the same candidate Tile field by fileIn and setter.
3. Getter loads from that field and conditionally reads a nested pointer.

A linear machine-code scan is not control-flow reachability or physics
semantics. Never export original bytes, symbol names or method addresses.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import zipfile

from .collision_inventory import private_output_path
from .ios_launch_preflight import (
    MAX_EXECUTABLE_BYTES, MAX_PLIST_BYTES, _member, _string,
    inspect_macho_header, inspect_private_ipa_launch,
)
from .thumb_bl_call_census import decode_thumb_bl, _name

MAX_SYMBOLS = 200_000
MAX_STRING_BYTES = 16 * 1024 * 1024
MAX_FUNCTION_BYTES = 2048
MAX_TEXT_BYTES = 16 * 1024 * 1024
SELECTORS = {
    "tile_deserializer": "Tile6fileInE",
    "shape_reference_setter": "Tile17setCollisionShapeE",
    "shape_reference_getter": "Tile17getCollisionShapeE",
}


def thumb_imm_word_transfer(halfword: int) -> dict | None:
    """Decode 16-bit Thumb LDR/STR register-plus-imm5*4 addressing only."""
    kind = halfword & 0xF800
    if kind not in (0x6000, 0x6800):
        return None
    return {
        "operation": "str" if kind == 0x6000 else "ldr",
        "source_or_dest": halfword & 0x7,
        "base": (halfword >> 3) & 0x7,
        "offset_bytes": ((halfword >> 6) & 0x1F) * 4,
    }


def thumb_movs_zero(halfword: int, reg: int) -> bool:
    """Check the small Thumb MOVS register,#0 encoding."""
    return (halfword & 0xF800) == 0x2000 and (halfword & 0x700) == reg << 8 and (halfword & 0xFF) == 0


def _macho_methods(binary: bytes) -> tuple[dict, bytes]:
    header = inspect_macho_header(binary)
    if binary[:4] == b"\xce\xfa\xed\xfe":
        endian = "<"
    elif binary[:4] == b"\xfe\xed\xfa\xce":
        endian = ">"
    else:
        raise ValueError("unsupported Mach-O byte order")
    _, _, _, _, commands, command_size, _ = struct.unpack_from(
        endian + "IiiIIII", binary, 0)
    cursor, section_ordinal = 28, 0
    symtab = text = None
    for _ in range(commands):
        cmd, size = struct.unpack_from(endian + "II", binary, cursor)
        if cmd == 1:
            if size < 56:
                raise ValueError("truncated segment command")
            parent = binary[cursor + 8:cursor + 24].split(b"\x00", 1)[0]
            nsects = struct.unpack_from(endian + "I", binary, cursor + 48)[0]
            if nsects > 4096 or size != 56 + 68 * nsects:
                raise ValueError("malformed segment section table")
            for i in range(nsects):
                pos = cursor + 56 + i * 68
                name, segment, addr, length, fileoff = struct.unpack_from(
                    endian + "16s16sIII", binary, pos)
                section_ordinal += 1
                if (parent == b"__TEXT"
                        and segment.split(b"\x00", 1)[0] == b"__TEXT"
                        and name.split(b"\x00", 1)[0] == b"__text"):
                    if text is not None:
                        raise ValueError("duplicate Mach-O text section")
                    if (length < 8 or length > MAX_TEXT_BYTES
                            or fileoff > len(binary)
                            or length > len(binary) - fileoff):
                        raise ValueError("text section outside executable")
                    text = (section_ordinal, addr, length, fileoff)
        if cmd == 2:
            if size != 24 or symtab is not None:
                raise ValueError("invalid or repeated Mach-O symtab")
            symtab = struct.unpack_from(endian + "IIII", binary, cursor + 8)
        cursor += size
    if cursor != 28 + command_size or symtab is None or text is None:
        raise ValueError("missing or inconsistent Mach-O symbol/text region")
    symoff, nsyms, stroff, strsize = symtab
    if not 1 <= nsyms <= MAX_SYMBOLS or not 1 <= strsize <= MAX_STRING_BYTES:
        raise ValueError("symbol table size exceeds bounds")
    if (symoff < 28 + command_size or symoff > len(binary)
            or nsyms * 12 > len(binary) - symoff
            or stroff < symoff + nsyms * 12
            or stroff > len(binary) or strsize > len(binary) - stroff):
        raise ValueError("symbol and string table bounds invalid")

    strtab = binary[stroff:stroff + strsize]
    defined = {}
    for i in range(nsyms):
        index, kind, section, desc, value = struct.unpack_from(
            endian + "IBBHI", binary, symoff + 12 * i)
        if (kind & 0xE0) or (kind & 0x0E) != 0x0E or section != text[0] or not index:
            continue
        if index >= strsize:
            raise ValueError("symbol name offset outside string table")
        end = strtab.find(b"\x00", index)
        if end < 0:
            raise ValueError("unterminated symbol name")
        name = _name(strtab[index:end])
        addr = value & ~1
        if not text[1] <= addr < text[1] + text[2]:
            raise ValueError("text symbol address outside text section")
        defined.setdefault(addr, []).append((name, bool(desc & 8)))

    addresses = sorted(defined)
    methods = {}
    for role, selector in SELECTORS.items():
        selected = [(addr, name, thumb)
                    for addr, aliases in defined.items()
                    for name, thumb in aliases if selector in name]
        if len(selected) != 1:
            raise ValueError("selected Tile method must be uniquely defined")
        addr, _, thumb = selected[0]
        if not thumb:
            raise ValueError("selected Tile method has no Thumb flag")
        after = bisect_right(addresses, addr)
        next_addr = addresses[after] if after < len(addresses) else text[1] + text[2]
        length = next_addr - addr
        if length < 4 or length > MAX_FUNCTION_BYTES or length % 2:
            raise ValueError("selected function envelope outside bounds")
        fileoff = text[3] + (addr - text[1])
        if fileoff < text[3] or fileoff + length > text[3] + text[2]:
            raise ValueError("selected Tile function outside text bytes")
        methods[role] = {
            "entry_address": addr,
            "bytes": binary[fileoff:fileoff + length],
        }
    return methods, binary


def summarize_tile_shape_field_chain(binary: bytes) -> dict:
    methods, _ = _macho_methods(binary)
    deserializer = methods["tile_deserializer"]
    setter = methods["shape_reference_setter"]
    getter = methods["shape_reference_getter"]

    def scan(method):
        code = method["bytes"]
        words = [struct.unpack_from("<H", code, i)[0] for i in range(0, len(code), 2)]
        transfers = []
        for i, word in enumerate(words):
            transfer = thumb_imm_word_transfer(word)
            if transfer:
                transfers.append((i, transfer))
        return words, transfers

    file_words, file_transfers = scan(deserializer)
    set_words, set_transfers = scan(setter)
    get_words, get_transfers = scan(getter)

    # Cross-reference the field touched by all three methods, instead of
    # hardcoding an original object's member offset in the public source.
    file_stores = {t["offset_bytes"] for _, t in file_transfers
                   if t["operation"] == "str"}
    setter_stores = {t["offset_bytes"] for _, t in set_transfers
                     if t["operation"] == "str"}
    getter_loads = {t["offset_bytes"] for _, t in get_transfers
                    if t["operation"] == "ldr"}
    common = sorted(file_stores & setter_stores & getter_loads)
    # Same base-object offset can also appear on different registers; this is
    # a candidate structural join, not verified alias/data flow.
    if len(common) != 1:
        raise ValueError("field-access join is ambiguous or absent")
    offset = common[0]

    file_init = [(i, t) for i, t in file_transfers
                 if t["operation"] == "str" and t["offset_bytes"] == offset
                 and any(thumb_movs_zero(file_words[k], t["source_or_dest"])
                         for k in range(max(0, i - 8), i))]
    setter_write = [(i, t) for i, t in set_transfers
                    if t["operation"] == "str" and t["offset_bytes"] == offset]
    getter_read = [(i, t) for i, t in get_transfers
                   if t["operation"] == "ldr" and t["offset_bytes"] == offset]
    direct_calls = []
    for i in range(len(file_words) - 1):
        destination = decode_thumb_bl(
            file_words[i], file_words[i + 1],
            deserializer["entry_address"] + i * 2
        )
        if destination == setter["entry_address"]:
            direct_calls.append(i)

    # The getter accesses one nested field after the candidate Tile member.
    # The offset must differ from the common Tile-object offset.
    nested = []
    for i, t in get_transfers:
        if t["operation"] != "ldr" or t["offset_bytes"] == offset:
            continue
        if any(i > j and i - j <= 6 and t["base"] == member["source_or_dest"]
               for j, member in getter_read):
            nested.append((i, t))

    structurally_joined = bool(file_init and setter_write and getter_read
                               and direct_calls and nested)
    return {
        "schema": "heman-stage264-tile-collision-shape-field-v1",
        "selected_thumb_methods": len(methods),
        "deserializer_to_setter_direct_bl_candidates": len(direct_calls),
        "one_candidate_member_offset_shared_across_methods": len(common) == 1,
        "candidate_member_offset_bytes": offset,
        "deserializer_zero_initialization_candidates": len(file_init),
        "setter_field_write_candidates": len(setter_write),
        "getter_field_read_candidates": len(getter_read),
        "getter_nested_pointer_read_candidates": len(nested),
        "structural_chain_complete": structurally_joined,
        "method_name_or_instruction_bytes_in_report": False,
        "static_instruction_patterns_not_proven_runtime_aliases": True,
        "collision_shape_resource_type_verified": False,
        "original_tile_alpha_used_for_collision_verified": False,
        "original_tile_collision_runtime_response_verified": False,
        "ios_gameplay_parity_verified": False,
        "native_switch_collision_import_authorized": False,
        "boundary": (
            "This is a read-only join of instruction encodings and defined-symbol "
            "addresses. Neither reachability nor runtime object aliases are proven."
        ),
    }


def inspect_private_ipa_tile_shape_field(ipa: Path) -> dict:
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be a regular non-symlink file")
    baseline = inspect_private_ipa_launch(ipa)
    with zipfile.ZipFile(ipa) as archive:
        infos = archive.infolist()
        if len(infos) > 100000:
            raise ValueError("too many IPA members")
        index = {x.filename: x for x in infos}
        if len(index) != len(infos):
            raise ValueError("duplicate IPA member")
        apps = {x.split("/")[1] for x in index
                if x.startswith("Payload/") and len(x.split("/")) >= 3
                and x.split("/")[1].endswith(".app")}
        if len(apps) != 1:
            raise ValueError("expected exactly one app bundle")
        root = "Payload/" + next(iter(apps)) + "/"
        plist = plistlib.loads(_member(archive,index,root+"Info.plist",MAX_PLIST_BYTES))
        if not isinstance(plist,dict):
            raise ValueError("invalid app plist")
        executable = _string(plist.get("CFBundleExecutable"), "executable")
        if executable.startswith(".") or "/" in executable or "\\" in executable:
            raise ValueError("unsafe executable name")
        binary = _member(archive,index,root+executable,MAX_EXECUTABLE_BYTES)
    report = summarize_tile_shape_field_chain(binary)
    report["private_source"] = {
        "executable_size_bytes": len(binary),
        "executable_sha256": hashlib.sha256(binary).hexdigest(),
        "private_executable_extracted_to_disk": False,
    }
    if inspect_macho_header(binary)["architecture"] != baseline["macho_metadata"]["architecture"]:
        raise ValueError("original executable architecture mismatch")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args = parser.parse_args(argv)
    destination = private_output_path(args.out)
    report = inspect_private_ipa_tile_shape_field(args.ipa)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("Stage264 static Tile member evidence saved privately; collision semantics remain unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
