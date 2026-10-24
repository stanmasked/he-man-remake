"""Read-only census of candidate Thumb BL call sites in an owner-held iOS app.

Limited to explicitly selected, already-named symbol-table functions.
The parser decodes a Thumb-2 BL encoding and resolves exact defined-symbol
addresses. This is static machine-code evidence, not a verified executable
control-flow graph, a runtime trace, or gameplay collision behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
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

MAX_SYMBOLS = 200_000
MAX_STRING_TABLE_BYTES = 16 * 1024 * 1024
MAX_SYMBOL_NAME_BYTES = 8192
MAX_SECTION_BYTES = 16 * 1024 * 1024
MAX_ANCHOR_CODE_BYTES = 65536
MAX_ANCHORS = 8

# These are structural candidate selectors, not an assertion about reachability.
# The emitted report uses generic labels and contains no original symbol names.
ANCHOR_SELECTORS = {
    "shape_to_physics_bridge": "BodyOwnerHelper22createB2ShapeFromShape",
    "collision_event_handler": "EntityCollisionManager18onAABBIntersection",
    "world_entity_shape_query": "CWorldEntity17getCollisionShape",
    "tile_shape_query": "Tile17getCollisionShape",
    "shape_resource_loader": "Shape2D10customLoad",
}


def decode_thumb_bl(first: int, second: int, address: int) -> int | None:
    """Decode a Thumb-2 BL *candidate*; return target or None.

    Thumb BL: first halfword 11110 S imm10, second 11 J1 1 J2 imm11.
    PC of a Thumb branch is the address of the first halfword + 4.
    Reject BLX and B.W forms; no attempt to infer executed instructions.
    """
    if (first & 0xF800) != 0xF000 or (second & 0xD000) != 0xD000:
        return None
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = 1 - (j1 ^ sign)
    i2 = 1 - (j2 ^ sign)
    displacement = (
        (sign << 24) | (i1 << 23) | (i2 << 22)
        | ((first & 0x3FF) << 12) | ((second & 0x7FF) << 1)
    )
    if sign:
        displacement -= 1 << 25
    return (address + 4 + displacement) & 0xFFFFFFFF


def _name(raw: bytes) -> str:
    if not raw or len(raw) > MAX_SYMBOL_NAME_BYTES:
        raise ValueError("empty or oversized Mach-O symbol name")
    try:
        name = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("non-ASCII Mach-O symbol name") from exc
    if any(ord(ch) < 32 for ch in name):
        raise ValueError("control character in Mach-O symbol name")
    return name


def _target_group(names: list[str]) -> str:
    lower = " ".join(names).casefold()
    if "b2" in lower and ("shape" in lower or "physics" in lower):
        return "physics_shape_api"
    if "shape2d" in lower:
        return "shape2d_api"
    if "gomsg" in lower or "sendmessage" in lower:
        return "game_message_api"
    if "file_read" in lower or "io_read" in lower:
        return "resource_read_api"
    if "collision" in lower or "aabb" in lower:
        return "collision_aabb_api"
    if "physics" in lower:
        return "physics_api"
    return "other_text_defined_api"


def summarize_thumb_bl_references(binary: bytes) -> dict:
    if not isinstance(binary, bytes) or not 28 <= len(binary) <= MAX_EXECUTABLE_BYTES:
        raise ValueError("original executable size outside safety bound")
    header = inspect_macho_header(binary)
    if binary[:4] == b"\xce\xfa\xed\xfe":
        endian = "<"
    elif binary[:4] == b"\xfe\xed\xfa\xce":
        endian = ">"
    else:
        raise ValueError("unsupported Mach-O header for Thumb census")
    _, _, _, _, ncmds, command_bytes, _ = struct.unpack_from(
        endian + "IiiIIII", binary, 0
    )
    end_commands = 28 + command_bytes
    offset = 28
    section_no = 0
    text_section = None
    symtab = None
    for _ in range(ncmds):
        command, size = struct.unpack_from(endian + "II", binary, offset)
        if command == 1:
            if size < 56:
                raise ValueError("truncated segment command")
            segment_name = binary[offset + 8:offset + 24].split(b"\x00", 1)[0]
            section_count = struct.unpack_from(endian + "I", binary, offset + 48)[0]
            if section_count > 4096 or size != 56 + section_count * 68:
                raise ValueError("bad Mach-O segment section envelope")
            for number in range(section_count):
                at = offset + 56 + number * 68
                label, segment, addr, section_size, fileoff = struct.unpack_from(
                    endian + "16s16sIII", binary, at
                )
                section_no += 1
                label = label.split(b"\x00", 1)[0]
                segment = segment.split(b"\x00", 1)[0]
                if label == b"__text" and segment == b"__TEXT" and segment_name == b"__TEXT":
                    if text_section is not None:
                        raise ValueError("duplicate executable text section")
                    if (section_size < 4 or section_size > MAX_SECTION_BYTES
                            or fileoff > len(binary)
                            or section_size > len(binary) - fileoff):
                        raise ValueError("executable text section exceeds bounds")
                    text_section = (section_no, addr, section_size, fileoff)
        elif command == 2:
            if symtab is not None or size != 24:
                raise ValueError("duplicate or malformed LC_SYMTAB")
            symtab = struct.unpack_from(endian + "IIII", binary, offset + 8)
        offset += size
    if offset != end_commands:
        raise ValueError("unreconciled Mach-O commands")
    if text_section is None or symtab is None:
        raise ValueError("Mach-O text section or symbol table missing")
    symoff, count, stroff, strsize = symtab
    if not 1 <= count <= MAX_SYMBOLS or not 1 <= strsize <= MAX_STRING_TABLE_BYTES:
        raise ValueError("symbol or string table size outside limits")
    if (symoff < end_commands or symoff > len(binary)
            or count * 12 > len(binary) - symoff
            or stroff < symoff + count * 12 or stroff > len(binary)
            or strsize > len(binary) - stroff):
        raise ValueError("symbol/string table outside executable")

    section_index, text_addr, text_size, text_file_offset = text_section
    string_table = binary[stroff:stroff + strsize]
    symbol_at = defaultdict(list)
    for index in range(count):
        strx, kind, section, desc, value = struct.unpack_from(
            endian + "IBBHI", binary, symoff + 12 * index
        )
        if (kind & 0xE0) or ((kind & 0x0E) != 0x0E) or section != section_index or not strx:
            continue
        if strx >= strsize:
            raise ValueError("symbol string offset outside table")
        end = string_table.find(b"\x00", strx)
        if end < 0:
            raise ValueError("symbol name not NUL-terminated")
        symbol_name = _name(string_table[strx:end])
        entry = value & ~1
        if not text_addr <= entry < text_addr + text_size:
            raise ValueError("defined text symbol outside text section")
        symbol_at[entry].append((symbol_name, bool(desc & 0x8)))

    addresses = sorted(symbol_at)
    if not addresses:
        raise ValueError("no defined text symbols")
    if len(ANCHOR_SELECTORS) > MAX_ANCHORS:
        raise ValueError("too many static analysis anchors")
    anchors = []
    total_candidates = total_resolved = 0
    for anchor_label, selector in ANCHOR_SELECTORS.items():
        matches = [
            addr for addr, names in symbol_at.items()
            if any(selector in name for name, _ in names)
        ]
        if len(matches) != 1:
            raise ValueError("expected one defined text symbol for selected anchor")
        start = matches[0]
        if not any(thumb for name, thumb in symbol_at[start] if selector in name):
            raise ValueError("selected anchor is not marked Thumb")
        # Bound to the next defined text symbol; aliases at the same address
        # do not create an empty interval.
        import bisect
        position = bisect.bisect_right(addresses, start)
        end = addresses[position] if position < len(addresses) else text_addr + text_size
        code_size = end - start
        if code_size < 2 or code_size > MAX_ANCHOR_CODE_BYTES or code_size % 2:
            raise ValueError("selected function's estimated interval exceeds safe limits")
        start_file = text_file_offset + start - text_addr
        if start_file < text_file_offset or start_file + code_size > text_file_offset + text_size:
            raise ValueError("selected function outside executable text")
        codes = binary[start_file:start_file + code_size]
        target_groups = Counter()
        candidates = resolved = 0
        for local in range(0, len(codes) - 3, 2):
            first, second = struct.unpack_from(endian + "HH", codes, local)
            target = decode_thumb_bl(first, second, start + local)
            if target is None:
                continue
            candidates += 1
            names = symbol_at.get(target)
            if names is not None:
                resolved += 1
                target_groups[_target_group([name for name, _ in names])] += 1
        total_candidates += candidates
        total_resolved += resolved
        anchors.append({
            "anchor": anchor_label,
            "estimated_text_bytes": code_size,
            "thumb_flag_present": True,
            "thumb_bl_candidate_sites": candidates,
            "sites_resolving_exact_defined_text_symbol": resolved,
            "unresolved_or_nonexact_site_count": candidates - resolved,
            "resolved_target_groups": dict(sorted(target_groups.items())),
        })
    return {
        "schema": "heman-stage262-thumb-direct-bl-census-v1",
        "macho_architecture": header["architecture"],
        "selected_anchor_count": len(anchors),
        "selected_anchor_thumb_bl_candidate_sites": total_candidates,
        "selected_anchor_exact_defined_target_sites": total_resolved,
        "selected_anchors": anchors,
        "source_symbol_names_in_report": False,
        "source_callsite_addresses_or_instruction_bytes_in_report": False,
        "static_instruction_candidate_not_verified_control_flow": True,
        "original_shape2d_to_physics_bridge_static_evidence": (
            next(a for a in anchors if a["anchor"] == "shape_to_physics_bridge")
            ["resolved_target_groups"].get("shape2d_api", 0) > 0
            and next(a for a in anchors if a["anchor"] == "shape_to_physics_bridge")
            ["resolved_target_groups"].get("physics_shape_api", 0) > 0
        ),
        "original_runtime_resource_binding_verified": False,
        "original_collision_alpha_usage_verified": False,
        "original_collision_response_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
    }


def inspect_private_ipa_thumb_calls(ipa: Path) -> dict:
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be a regular non-symlink file")
    preflight = inspect_private_ipa_launch(ipa)
    with zipfile.ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > 100_000:
            raise ValueError("excessive IPA member count")
        index = {item.filename: item for item in infos}
        if len(index) != len(infos):
            raise ValueError("duplicate IPA entry")
        apps = {
            name.split("/")[1] for name in index
            if name.startswith("Payload/") and len(name.split("/")) >= 3
            and name.split("/")[1].endswith(".app")
        }
        if len(apps) != 1:
            raise ValueError("expected exactly one application bundle")
        prefix = f"Payload/{next(iter(apps))}/"
        plist = plistlib.loads(_member(archive, index, prefix + "Info.plist", MAX_PLIST_BYTES))
        if not isinstance(plist, dict):
            raise ValueError("Info.plist must be a dictionary")
        executable = _string(plist.get("CFBundleExecutable"), "executable")
        if executable.startswith(".") or "/" in executable or "\\" in executable:
            raise ValueError("unsafe executable name")
        binary = _member(archive, index, prefix + executable, MAX_EXECUTABLE_BYTES)
    report = summarize_thumb_bl_references(binary)
    if report["macho_architecture"] != preflight["macho_metadata"]["architecture"]:
        raise ValueError("Mach-O architecture mismatch")
    report["private_source"] = {
        "executable_size_bytes": len(binary),
        "executable_sha256": hashlib.sha256(binary).hexdigest(),
        "executable_extracted_to_disk": False,
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    options = parser.parse_args(argv)
    out = private_output_path(options.out)
    report = inspect_private_ipa_thumb_calls(options.ipa)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print("Stage262 candidate direct-call census saved privately; runtime collision remains unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
