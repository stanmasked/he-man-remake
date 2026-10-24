"""Static Thumb BL incoming-site census for selected collision/shape functions.

Uses owner-private Mach-O bytes in memory, labels containing no original
method names, and exact branch-target matching. Linear disassembly is a
candidate detector only: calls via vtables, registers, BLX or dynamic dispatch
are not counted, and static candidate sites do not prove runtime execution.
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter, defaultdict
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
from .thumb_bl_call_census import ANCHOR_SELECTORS, _name, decode_thumb_bl

MAX_SYMBOLS = 200_000
MAX_STRING_BYTES = 16 * 1024 * 1024
MAX_TEXT_BYTES = 16 * 1024 * 1024


def _classify_caller(names: list[str]) -> str:
    labels = " ".join(names).casefold()
    if "ctilemap" in labels and "initializecollision" in labels:
        return "tilemap_collision_initializer"
    if "collisionmap" in labels and ("c1e" in labels or "c2e" in labels):
        return "collision_map_constructor"
    if "attack" in labels or "melee" in labels or "shoot" in labels:
        return "combat_attack_related"
    if "shape2d" in labels or "geometry" in labels:
        return "shape_geometry_related"
    if "debris" in labels or "worldentity" in labels:
        return "world_entity_related"
    return "other_named_text_function"


def summarize_thumb_inbound_references(binary: bytes) -> dict:
    if not isinstance(binary, bytes) or not 28 <= len(binary) <= MAX_EXECUTABLE_BYTES:
        raise ValueError("input executable is outside supported size range")
    header = inspect_macho_header(binary)
    if binary[:4] == b"\xce\xfa\xed\xfe":
        endian = "<"
    elif binary[:4] == b"\xfe\xed\xfa\xce":
        endian = ">"
    else:
        raise ValueError("unsupported Mach-O byte order")
    _, _, _, _, commands, command_size, _ = struct.unpack_from(
        endian + "IiiIIII", binary, 0
    )
    cursor = 28
    command_end = cursor + command_size
    section_ordinal = 0
    text_region = None
    symtab = None
    for _ in range(commands):
        kind, cmdsize = struct.unpack_from(endian + "II", binary, cursor)
        if kind == 1:
            if cmdsize < 56:
                raise ValueError("invalid Mach-O segment command")
            segment = binary[cursor + 8:cursor + 24].split(b"\x00", 1)[0]
            count = struct.unpack_from(endian + "I", binary, cursor + 48)[0]
            if count > 4096 or cmdsize != 56 + count * 68:
                raise ValueError("Mach-O segment section envelope is invalid")
            for sec in range(count):
                at = cursor + 56 + sec * 68
                label, parent, addr, size, file_offset = struct.unpack_from(
                    endian + "16s16sIII", binary, at
                )
                section_ordinal += 1
                if (label.split(b"\x00", 1)[0] == b"__text"
                        and parent.split(b"\x00", 1)[0] == b"__TEXT"
                        and segment == b"__TEXT"):
                    if text_region is not None:
                        raise ValueError("duplicate Mach-O text section")
                    if (size < 4 or size > MAX_TEXT_BYTES
                            or file_offset > len(binary)
                            or size > len(binary) - file_offset):
                        raise ValueError("Mach-O text section exceeds file bounds")
                    text_region = (section_ordinal, addr, size, file_offset)
        if kind == 2:
            if symtab is not None or cmdsize != 24:
                raise ValueError("invalid or duplicate Mach-O symbol table")
            symtab = struct.unpack_from(endian + "IIII", binary, cursor + 8)
        cursor += cmdsize
    if cursor != command_end or text_region is None or symtab is None:
        raise ValueError("incomplete Mach-O text and symbol envelope")
    sec_index, text_addr, text_size, text_offset = text_region
    symoff, nsyms, stroff, strsize = symtab
    if not 1 <= nsyms <= MAX_SYMBOLS or not 1 <= strsize <= MAX_STRING_BYTES:
        raise ValueError("oversized Mach-O symbol/string index")
    if (symoff < command_end or symoff > len(binary)
            or nsyms * 12 > len(binary) - symoff
            or stroff < symoff + nsyms * 12
            or stroff > len(binary) or strsize > len(binary) - stroff):
        raise ValueError("Mach-O symbol table offsets outside file")

    source_strings = binary[stroff:stroff + strsize]
    symbols = defaultdict(list)
    for index in range(nsyms):
        ref, ty, sec, desc, address = struct.unpack_from(
            endian + "IBBHI", binary, symoff + 12 * index
        )
        if (ty & 0xE0) or (ty & 0x0E) != 0x0E or sec != sec_index or ref == 0:
            continue
        if ref >= strsize:
            raise ValueError("Mach-O symbol name offset outside string table")
        end = source_strings.find(b"\x00", ref)
        if end < 0:
            raise ValueError("unterminated Mach-O symbol name")
        label = _name(source_strings[ref:end])
        address &= ~1
        if not text_addr <= address < text_addr + text_size:
            raise ValueError("text symbol outside executable text section")
        symbols[address].append((label, bool(desc & 8)))
    addresses = sorted(symbols)
    if not addresses:
        raise ValueError("no code symbol index")

    inbound = {}
    targets = {}
    for role, selector in ANCHOR_SELECTORS.items():
        matches = [addr for addr, names in symbols.items()
                   if any(selector in name for name, _ in names)]
        if len(matches) != 1:
            raise ValueError("expected exactly one named anchor for inbound census")
        target = matches[0]
        if not any(thumb for name, thumb in symbols[target] if selector in name):
            raise ValueError("selected anchor lacks Thumb code marker")
        targets[target] = role
        inbound[role] = {"sites": 0, "caller_addrs": set(), "groups": Counter(),
                         "uncertain_caller_sites": 0}

    # Only Thumb BL candidate halfword pairs; indirect calls and
    # ARM/Thumb BLX are excluded. No claim that these instructions execute.
    code = binary[text_offset:text_offset + text_size]
    for off in range(0, text_size - 3, 2):
        first, second = struct.unpack_from(endian + "HH", code, off)
        target = decode_thumb_bl(first, second, text_addr + off)
        if target not in targets:
            continue
        role = targets[target]
        matched = inbound[role]
        matched["sites"] += 1
        call_addr = text_addr + off
        idx = bisect.bisect_right(addresses, call_addr) - 1
        if idx < 0:
            matched["uncertain_caller_sites"] += 1
            continue
        caller_addr = addresses[idx]
        names = symbols[caller_addr]
        if not any(thumb for _, thumb in names):
            matched["uncertain_caller_sites"] += 1
            continue
        matched["caller_addrs"].add(caller_addr)
        matched["groups"][_classify_caller([name for name, _ in names])] += 1

    results = []
    for role in ANCHOR_SELECTORS:
        x = inbound[role]
        results.append({
            "target_role": role,
            "candidate_bl_inbound_sites": x["sites"],
            "distinct_nearest_named_caller_entries": len(x["caller_addrs"]),
            "caller_category_site_counts": dict(sorted(x["groups"].items())),
            "sites_with_unresolved_or_non_thumb_caller": x["uncertain_caller_sites"],
        })
    tile = next(x for x in results if x["target_role"] == "tile_shape_query")
    bridge = next(x for x in results if x["target_role"] == "shape_to_physics_bridge")
    return {
        "schema": "heman-stage263-thumb-inbound-candidate-v1",
        "macho_architecture": header["architecture"],
        "selected_targets": results,
        "total_selected_inbound_bl_candidates": sum(x["candidate_bl_inbound_sites"] for x in results),
        "tilemap_to_tile_shape_static_candidate": bool(
            tile["caller_category_site_counts"].get("tilemap_collision_initializer")
        ),
        "combat_to_shape_bridge_static_candidate": bool(
            bridge["caller_category_site_counts"].get("combat_attack_related")
        ),
        "source_symbol_names_addresses_instruction_bytes_in_report": False,
        "static_bl_candidate_not_reachable_control_flow": True,
        "indirect_vtable_or_blx_calls_checked": False,
        "original_runtime_resource_binding_verified": False,
        "original_collision_alpha_usage_verified": False,
        "original_collision_response_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
    }


def inspect_private_ipa_inbound(ipa: Path) -> dict:
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be a regular non-symlink file")
    preflight = inspect_private_ipa_launch(ipa)
    with zipfile.ZipFile(ipa, "r") as archive:
        info = archive.infolist()
        if len(info) > 100_000:
            raise ValueError("excessive IPA member count")
        index = {item.filename: item for item in info}
        if len(index) != len(info):
            raise ValueError("duplicate IPA member")
        apps = {name.split("/")[1] for name in index
                if name.startswith("Payload/") and len(name.split("/")) >= 3
                and name.split("/")[1].endswith(".app")}
        if len(apps) != 1:
            raise ValueError("expected exactly one application bundle")
        root = f"Payload/{next(iter(apps))}/"
        plist = plistlib.loads(_member(archive, index, root + "Info.plist", MAX_PLIST_BYTES))
        if not isinstance(plist, dict):
            raise ValueError("malformed app plist")
        executable = _string(plist.get("CFBundleExecutable"), "executable")
        if executable.startswith(".") or "/" in executable or "\\" in executable:
            raise ValueError("unsafe app executable name")
        binary = _member(archive, index, root + executable, MAX_EXECUTABLE_BYTES)
    report = summarize_thumb_inbound_references(binary)
    if report["macho_architecture"] != preflight["macho_metadata"]["architecture"]:
        raise ValueError("inconsistent original executable architecture")
    report["private_source"] = {
        "executable_size_bytes": len(binary),
        "executable_sha256": hashlib.sha256(binary).hexdigest(),
        "source_executable_extracted": False,
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    opts = parser.parse_args(argv)
    output = private_output_path(opts.out)
    report = inspect_private_ipa_inbound(opts.ipa)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Stage263 inbound BL candidates saved privately; gameplay behavior remains unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
