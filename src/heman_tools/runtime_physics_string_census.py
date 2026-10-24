"""Private-only static string census for the original iOS Mach-O.

This identifies candidate engine type names and message identifiers embedded in
the executable. Printable strings are not proof of call sites, object creation,
runtime resource binding, or actual collision response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import stat
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

MAX_DISTINCT_STRINGS = 500_000
MIN_STRING_LENGTH = 5
MAX_STRING_LENGTH = 512
MAX_IPA_MEMBERS = 100_000
APP_PREFIX = "Payload/"


def _ascii_runs(data: bytes):
    """Yield bounded printable ASCII runs; never decode or export binary data."""
    start = None
    overflow = False
    for offset, value in enumerate(data):
        if 0x20 <= value <= 0x7E:
            if start is None:
                start = offset
                overflow = False
            elif offset - start >= MAX_STRING_LENGTH:
                overflow = True
        else:
            if (start is not None and not overflow
                    and MIN_STRING_LENGTH <= offset - start <= MAX_STRING_LENGTH):
                yield data[start:offset].decode("ascii")
            start = None
            overflow = False
    if (start is not None and not overflow
            and MIN_STRING_LENGTH <= len(data) - start <= MAX_STRING_LENGTH):
        yield data[start:].decode("ascii")


def summarize_runtime_strings(binary: bytes) -> dict:
    """Return category counts and presence flags only, never source strings."""
    if not isinstance(binary, bytes) or not 28 <= len(binary) <= MAX_EXECUTABLE_BYTES:
        raise ValueError("executable bytes outside the bounded input range")
    macho = inspect_macho_header(binary)
    strings = set(_ascii_runs(binary))
    if len(strings) > MAX_DISTINCT_STRINGS:
        raise ValueError("executable has too many distinct printable strings")

    def count(predicate):
        return sum(1 for value in strings if predicate(value))

    def has_exact(value):
        return value in strings

    physics_words = count(lambda s: "physic" in s.casefold())
    collision_words = count(lambda s: "collis" in s.casefold())
    sensor_words = count(lambda s: "sensor" in s.casefold())
    platform_words = count(lambda s: "platform" in s.casefold())
    tilemap_words = count(lambda s: "tilemap" in s.casefold()
                          or "tile_map" in s.casefold())
    shape_words = count(lambda s: "shape" in s.casefold())
    message_ids = {s for s in strings if re.fullmatch(r"CMSG_[A-Za-z0-9_]+", s)}
    collision_sensor_messages = {
        s for s in message_ids
        if "COLLISION" in s.upper() or "SENSOR" in s.upper()
        or "AABB" in s.upper()
    }
    physics_type_names = {
        s for s in strings
        if re.fullmatch(r"C(?:Entity)?Physics[A-Za-z0-9_]*", s)
    }
    sensor_type_names = {
        s for s in strings
        if re.fullmatch(r"C(?:Line|Proximity|State)?Sensor", s)
    }
    platform_type_names = {
        s for s in strings
        if re.fullmatch(r"C(?:Static|Shaky|Time)?Platform", s)
    }
    tilemap_type_names = {
        s for s in strings
        if re.fullmatch(r"C(?:Infinite)?TileMap(?:Layer)?", s)
    }
    physics_format_type_names = {
        s for s in strings
        if re.fullmatch(r"(?:PhysicsStruct2D(?:Data)?|Shape2D[A-Z]*)", s)
    }
    manager_type_names = {
        s for s in strings
        if re.fullmatch(r"[A-Za-z0-9_]*CollisionManager", s)
    }

    return {
        "schema": "heman-stage260-runtime-physics-string-census-v1",
        "macho": {
            "architecture": macho["architecture"],
            "thin_32_bit_macho": macho["thin_32_bit_macho"],
            "load_commands_structurally_valid": macho["load_commands_structurally_valid"],
        },
        "distinct_printable_ascii_strings": len(strings),
        "substring_candidate_counts": {
            "physics": physics_words,
            "collision": collision_words,
            "sensor": sensor_words,
            "platform": platform_words,
            "tilemap": tilemap_words,
            "shape": shape_words,
        },
        "candidate_identifier_counts": {
            "physics_type_names": len(physics_type_names),
            "sensor_type_names": len(sensor_type_names),
            "platform_type_names": len(platform_type_names),
            "tilemap_type_names": len(tilemap_type_names),
            "physics_format_type_names": len(physics_format_type_names),
            "collision_manager_type_names": len(manager_type_names),
            "message_identifiers": len(message_ids),
            "collision_or_sensor_message_identifiers": len(collision_sensor_messages),
        },
        "candidate_groups_present": {
            "physics_type_names": bool(physics_type_names),
            "sensor_type_names": bool(sensor_type_names),
            "platform_type_names": bool(platform_type_names),
            "tilemap_type_names": bool(tilemap_type_names),
            "physics_format_type_names": bool(physics_format_type_names),
            "collision_manager_type_names": bool(manager_type_names),
            "collision_or_sensor_message_identifiers": bool(collision_sensor_messages),
        },
        "raw_string_values_in_report": False,
        "source_paths_or_resource_names_in_report": False,
        "static_strings_are_runtime_call_evidence": False,
        "original_collision_alpha_usage_verified": False,
        "original_physics_resource_binding_verified": False,
        "original_collision_response_verified": False,
        "original_ios_gameplay_trace_compared": False,
        "native_switch_collision_import_authorized": False,
    }


def inspect_private_ipa_runtime_strings(ipa: Path) -> dict:
    """Inspect the executable in memory; never extract or persist source bytes."""
    if not ipa.is_file() or ipa.is_symlink():
        raise ValueError("IPA must be a regular non-symlink file")
    # This validates archive paths, duplicate members, the Info.plist and
    # executable Mach-O header before the selected member is read a second time.
    preflight = inspect_private_ipa_launch(ipa)
    with zipfile.ZipFile(ipa, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_IPA_MEMBERS:
            raise ValueError("excessive IPA member count")
        index = {info.filename: info for info in infos}
        if len(index) != len(infos):
            raise ValueError("duplicate IPA entry")
        app_dirs = sorted({
            name.split("/")[1] for name in index
            if name.startswith(APP_PREFIX)
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
        if (executable_name.startswith(".") or "/" in executable_name
                or "\\" in executable_name):
            raise ValueError("unsafe executable name")
        binary = _member(
            archive, index, prefix + executable_name, MAX_EXECUTABLE_BYTES
        )
    report = summarize_runtime_strings(binary)
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
    report = inspect_private_ipa_runtime_strings(args.ipa)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Stage260 static runtime-string census saved under local_reports/; no gameplay semantics inferred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
